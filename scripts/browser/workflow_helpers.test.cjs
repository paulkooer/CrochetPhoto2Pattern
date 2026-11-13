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
const {observeRuns,completedUploadRun} = require('./streamlit_protocol.cjs');

async function newPage() {
  const page = await browser.newPage();
  observeRuns(page);
  return page;
}

// A synchronous DOM read is deliberate: waiting here would mask an early return.
const tailNow = page => page.evaluate(() => document.querySelector('.st-key-sync_tail')?.textContent);

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
  const page = await newPage();
  try {
    await page.goto(baseURL + '/?slow_tail=1&delay_request=1');
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
    assert.equal(await tailNow(page),'synthetic.json:{"value":42}',
                 'upload() returned before its rerun rendered the final marker.');
    assert.equal(await page.getByTestId('stApp').getAttribute('data-test-script-state'),'notRunning');
    await page.getByRole('button',{name:'Apply synthetic input',exact:true}).click();
    await settle(page);
    await expect(page.getByTestId('stAlertContainer')).toContainText('Applied: {"value":42}');
  } finally {
    await page.close();
  }
});

test('a hidden toolbar indicator does not make a running script ready',async () => {
  const page = await newPage();
  try {
    await page.goto(baseURL + '/?slow_tail=1');
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
  const page = await newPage();
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

for (const rate of [1,8]) {
  test(`zero-delay uploads retain their final marker at CPU throttle ${rate}x`,async () => {
    let noVisibleRunning = 0;
    for (let i = 0; i < 6; i++) {
      const page = await newPage();
      try {
        if (rate > 1) {
          const session = await page.context().newCDPSession(page);
          await session.send('Emulation.setCPUThrottlingRate',{rate});
        }
        await page.goto(baseURL + '/?fast=1');
        for (const prefix of ['fresh','replacement']) {
          const name = `${prefix}-${i}.json`;
          const body = JSON.stringify({prefix,i});
          await settle(page);
          await page.evaluate(() => {
            const app = document.querySelector('[data-testid="stApp"]');
            globalThis.__runningVisible = false;
            globalThis.__runningProbe = new MutationObserver(records => {
              if (app.getAttribute('data-test-script-state') === 'running'
                  || records.some(record => record.oldValue === 'running')) globalThis.__runningVisible = true;
            });
            globalThis.__runningProbe.observe(app,{attributes:true,attributeOldValue:true,
                                                   attributeFilter:['data-test-script-state']});
          });
          await upload(page,page.locator('.st-key-sync_file'),{
            name,mimeType:'application/json',buffer:Buffer.from(body),
          });
          assert.equal(await tailNow(page),`${name}:${body}`);
          if (!await page.evaluate(() => globalThis.__runningVisible)) noVisibleRunning++;
          await page.evaluate(() => globalThis.__runningProbe.disconnect());
        }
      } finally { await page.close(); }
    }
    console.log(`fast uploads at ${rate}x: 12 passed; running absent from DOM in ${noVisibleRunning}`);
  });
}

test('an upload HTTP error retains its status instead of timing out on a nonexistent rerun',async () => {
  const page = await newPage();
  try {
    await page.goto(baseURL);
    await page.route('**/_stcore/upload_file/**',route => route.fulfill({status:500,body:'synthetic failure'}));
    await assert.rejects(upload(page,page.locator('.st-key-sync_file'),{
      name:'failed.json',mimeType:'application/json',buffer:Buffer.from('{}'),
    }),/HTTP 500/);
  } finally { await page.close(); }
});

test('run correlation rejects stale requests, wrong file IDs, unrelated finishes and interrupted runs',() => {
  const events = [
    {sequence:1,type:'request',fileIds:['old']},
    {sequence:2,type:'request',fileIds:['new']},
    {sequence:3,type:'start',id:'run-1',fragments:[]},
    {sequence:4,type:'finish',id:'other-run',status:0},
  ];
  assert.equal(completedUploadRun(events,1,'old'),null);
  assert.equal(completedUploadRun(events,1,'wrong'),null);
  assert.equal(completedUploadRun(events,1,'new'),null);
  events.push({sequence:5,type:'finish',id:'run-1',status:2});
  assert.equal(completedUploadRun(events,1,'new'),null);
  events.push({sequence:6,type:'start',id:'run-2',fragments:[]},
              {sequence:7,type:'finish',id:'run-2',status:0});
  assert.equal(completedUploadRun(events,1,'new'),'run-2');
  assert.equal(completedUploadRun(events,1,'old'),null);
  assert.equal(completedUploadRun(events,7,'new'),null);
});
