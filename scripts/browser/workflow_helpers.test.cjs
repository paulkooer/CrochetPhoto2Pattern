// Real-browser regressions for asynchronous upload and failure propagation.
const assert = require('node:assert/strict');
const {after,before,test} = require('node:test');
const {spawn} = require('node:child_process');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const net = require('node:net');
const {setTimeout:delay} = require('node:timers/promises');
const playwrightModule = process.env.CROCHET_PLAYWRIGHT_MODULE || path.join(__dirname,'node_modules/playwright');
const {chromium} = require(playwrightModule);
const {expect} = require(path.join(playwrightModule,'test'));
const {settle,upload,download} = require('./workflow_helpers.cjs');

let server,browser,temp,baseURL,serverExit;
before(async () => {
  temp = await fs.mkdtemp(path.join(os.tmpdir(),'crochet-sync-'));
  const socket = net.createServer();
  await new Promise(resolve => socket.listen(0,'127.0.0.1',resolve));
  const port = socket.address().port;
  await new Promise(resolve => socket.close(resolve));
  baseURL = `http://127.0.0.1:${port}`;
  const root = path.join(__dirname,'../..');
  server = spawn(process.env.CROCHET_TEST_PYTHON || path.join(root,'.venv/bin/python'),[
    '-m','streamlit','run',path.join(__dirname,'synchronization_fixture.py'),
    '--server.address=127.0.0.1',`--server.port=${port}`,'--server.headless=true',
    '--browser.gatherUsageStats=false',
  ],{cwd:root,stdio:['ignore','pipe','pipe']});
  let logs = '';
  server.stdout.on('data',value => {logs += value;});
  server.stderr.on('data',value => {logs += value;});
  serverExit = new Promise(resolve => server.once('exit',resolve));
  for (let attempt = 0; attempt < 150; attempt++) {
    try {
      const response = await fetch(`${baseURL}/_stcore/health`);
      if (response.ok) break;
    } catch {}
    assert(server.exitCode === null,logs);
    if (attempt === 149) throw new Error(`Fixture did not start: ${logs}`);
    await delay(100);
  }
  browser = await chromium.launch({headless:true,
    executablePath:process.env.CROCHET_CHROME_EXECUTABLE || undefined});
});
after(async () => {
  await browser?.close();
  server?.kill('SIGTERM');
  await serverExit;
  if (temp) await fs.rm(temp,{recursive:true,force:true});
});

test('uploaded input waits for its Python rerun before the next click',async () => {
  const page = await browser.newPage();
  try {
    await page.goto(baseURL);
    // The presentation-only toolbar indicator cannot be a readiness signal.
    await page.addStyleTag({content:'[data-testid="stStatusWidget"] { display:none !important; }'});
    let uploadFinished = false;
    await page.route('**/_stcore/upload_file/**',async route => {
      await delay(250);
      await route.continue();
    });
    page.on('response',response => {
      if (response.request().method() === 'PUT'
          && response.url().includes('/_stcore/upload_file/')) uploadFinished = response.ok();
    });
    await upload(page,page.locator('.st-key-sync_file'),{
      name:'synthetic.json',mimeType:'application/json',buffer:Buffer.from('{"value":42}'),
    });
    assert(uploadFinished,'The upload response must finish before returning.');
    assert.equal(await page.getByTestId('stApp').getAttribute('data-test-script-state'),'notRunning');
    await page.getByRole('button',{name:'Apply synthetic input',exact:true}).click();
    await settle(page);
    await expect(page.getByTestId('stAlertContainer')).toContainText('Applied: {"value":42}');
    assert.equal(await page.evaluate(() => Object.keys(globalThis.__crochetUploadWatches).length),0);
  } finally {
    await page.close();
  }
});

test('a hidden toolbar indicator does not make a running script ready',async () => {
  const page = await browser.newPage();
  try {
    await page.goto(baseURL);
    await settle(page);
    await page.addStyleTag({content:'[data-testid="stStatusWidget"] { display:none !important; }'});
    await Promise.all([
      page.waitForResponse(response => response.request().method() === 'PUT'
        && response.url().includes('/_stcore/upload_file/')),
      page.locator('.st-key-sync_file input[type="file"]').setInputFiles({
        name:'slow.json',mimeType:'application/json',buffer:Buffer.from('{}'),
      }),
    ]);
    await expect(page.getByRole('button',{name:'Apply synthetic input',exact:true})).toBeEnabled();
    await expect(page.getByTestId('stApp')).toHaveAttribute('data-test-script-state','running');
    await settle(page);
    assert.equal(await page.getByTestId('stApp').getAttribute('data-test-script-state'),'notRunning');
  } finally {
    await page.close();
  }
});

test('downloads retain bytes and a failed click keeps its original error',async () => {
  const page = await browser.newPage();
  try {
    await page.goto(baseURL);
    const bytes = await download(page,page.getByRole('button',{name:'Download synthetic output',exact:true}),
                                 path.join(temp,'output.txt'));
    assert.equal(bytes.toString(),'synthetic-output');
    page.setDefaultTimeout(100);
    await assert.rejects(download(page,page.locator('#missing-download'),path.join(temp,'missing.txt')),
                         /locator\.click: Timeout/);
  } finally {
    // Closing rejects the armed download waiter. node:test must not receive an
    // unhandled rejection after the original click error has been asserted.
    await page.close();
    await delay(50);
  }
});
