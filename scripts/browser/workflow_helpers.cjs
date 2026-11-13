// Synchronization for the real Streamlit browser checks, not application code.
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const {runLog,waitForUploadRun} = require('./streamlit_protocol.cjs');
const playwrightModule = process.env.CROCHET_PLAYWRIGHT_MODULE || path.join(__dirname,'node_modules/playwright');
const {expect} = require(path.join(playwrightModule,'test'));

async function reveal(locator) {
  for (const details of await locator.locator('xpath=ancestor::details').all()) {
    if (await details.getAttribute('open') === null) {
      await details.locator(':scope > summary').click();
    }
  }
}

async function settle(page) {
  // Keep the existing debounce allowance, then check the app state itself.
  // The toolbar's running indicator can be absent while Python is still busy.
  await page.waitForTimeout(300);
  const app = page.getByTestId('stApp');
  await expect(app).toHaveAttribute('data-test-connection-state','CONNECTED',{timeout:45000});
  await expect(app).toHaveAttribute('data-test-script-state','notRunning',{timeout:45000});
  await expect(page.getByTestId('stSkeleton')).toHaveCount(0,{timeout:45000});
  assert.equal(await page.getByTestId('stException').count(),0,
               'Streamlit reported an uncaught application exception.');
}

async function upload(page, holder, file) {
  await settle(page);
  const after = runLog(page).sequence;
  const [response] = await Promise.all([
    page.waitForResponse(response => response.request().method() === 'PUT'
      && new URL(response.url()).pathname.includes('/_stcore/upload_file/'),{timeout:45000}),
    holder.locator('input[type="file"]').setInputFiles(file),
  ]);
  assert(response.ok(),`Streamlit upload failed: HTTP ${response.status()}`);
  const fileId = decodeURIComponent(new URL(response.url()).pathname.split('/').at(-1));
  await waitForUploadRun(page,after,fileId);
  // Let the renderer process the received messages, then check current UI state.
  await page.evaluate(() => new Promise((resolve,reject) => {
    const timer = setTimeout(() => reject(new Error('Renderer did not resume within 45000ms.')),45000);
    requestAnimationFrame(() => requestAnimationFrame(() => { clearTimeout(timer); resolve(); }));
  }));
  await settle(page);
}

async function download(page, locator, output) {
  await settle(page);
  await reveal(locator);
  // Both promises get rejection handlers immediately. A failed click must not
  // leave an event waiter that later masks it when the browser closes.
  const [value] = await Promise.all([
    page.waitForEvent('download',{timeout:45000}),
    locator.click(),
  ]);
  assert.equal(await value.failure(),null);
  await value.saveAs(output);
  await settle(page);
  return fs.readFile(output);
}

module.exports = {reveal,settle,upload,download};
