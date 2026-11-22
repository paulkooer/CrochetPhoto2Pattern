// Round 3: are long file-supplied notes readable (wrapped, not clipped) in the reader?
// Usage: node r3_reader_long_notes.cjs <repo-root> <base-url> <out-dir> <plan.json>
const path = require('node:path');
const fs = require('node:fs');
const [repo, baseUrl, outDir, planFile] = process.argv.slice(2);
const {chromium} = require(path.join(repo, 'scripts/browser/node_modules/playwright'));

async function settle(page) {
  for (let round = 0; round < 3; round += 1) {
    await page.waitForTimeout(350);
    await page.waitForFunction(() => {
      const el = document.querySelector('[data-testid="stApp"]');
      return el && el.getAttribute('data-test-script-state') === 'notRunning'
        && el.getAttribute('data-test-connection-state') === 'CONNECTED';
    }, null, {timeout: 90000});
  }
}

(async () => {
  fs.mkdirSync(outDir, {recursive: true});
  const browser = await chromium.launch({headless: true});
  const context = await browser.newContext({viewport: {width: 1380, height: 1000}, locale: 'zh-CN'});
  const page = await context.newPage();
  await page.goto(baseUrl, {waitUntil: 'domcontentloaded'});
  await settle(page);
  await page.getByRole('tab', {name: '手动输入'}).click();
  await settle(page);
  const panel = page.getByRole('tabpanel').filter({hasText: '开衫工艺设计'}).first();
  const reader = panel.locator('details').filter({has: page.locator('summary:has-text("人工工序图解（校验与阅读）")')}).first();
  await reader.scrollIntoViewIfNeeded();
  if (await reader.getAttribute('open') === null) await reader.locator(':scope > summary').click();
  await settle(page);
  await reader.locator('input[type="file"]').setInputFiles(planFile);
  await page.waitForTimeout(1200);
  await settle(page);
  await reader.getByRole('button', {name: '校验并载入工序', exact: true}).click();
  await settle(page);
  await page.waitForTimeout(1500);
  const text = await reader.innerText();
  console.log('plan accepted:', text.includes('工序设计核对稿'));
  const stats = await reader.locator('[data-testid="stText"]').evaluateAll(nodes => nodes.map(node => ({
    chars: node.innerText.length, clipped: node.scrollWidth > node.clientWidth + 1,
    lines: Math.round(node.getBoundingClientRect().height / parseFloat(getComputedStyle(node).lineHeight || '24')),
  })));
  console.log('file-supplied text blocks:', stats.length);
  console.log('longest block (chars):', Math.max(...stats.map(s => s.chars)));
  console.log('blocks wider than their container (clipped or scrolling sideways):', stats.filter(s => s.clipped).length);
  console.log('blocks over 120 chars shown on more than one line:',
              stats.filter(s => s.chars > 120 && s.lines > 1).length, 'of', stats.filter(s => s.chars > 120).length);
  console.log('note about facing side and buttonhole front is shown:', text.includes('朝向与前襟'));
  await reader.screenshot({path: path.join(outDir, 'reader-long-notes.png')}).catch(() => {});
  await browser.close();
})().catch(error => { console.error('ABORTED', error.message.slice(0, 500)); process.exit(2); });
