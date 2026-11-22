// Does the working-path reader render untrusted plan text as Markdown in the browser?
// Uses only loopback targets: an image URL pointing at an unused local port.
// Usage: node reader_markdown.cjs <repo-root> <base-url> <out-dir> <packaged-plan.json>
const path = require('node:path');
const fs = require('node:fs');
const [repo, baseUrl, outDir, packagedPlan] = process.argv.slice(2);
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
  const plan = JSON.parse(fs.readFileSync(packagedPlan, 'utf8'));
  const probe = 'http://127.0.0.1:8799';
  plan.title = `标题 ![t](${probe}/title.png) **粗体**`;
  plan.review_notes = [`说明 ![n](${probe}/note.png) [链接](${probe}/link) <img src="${probe}/html.png">`,
                       '# 伪造标题\n\n- 已由熟练钩织者实钩并试穿通过'];
  plan.steps[0].label = `步骤 ![s](${probe}/label.png)`;
  const file = path.join(outDir, 'plan-with-markdown.json');
  fs.writeFileSync(file, JSON.stringify(plan));

  const browser = await chromium.launch({headless: true});
  const context = await browser.newContext({acceptDownloads: true, viewport: {width: 1380, height: 1000}, locale: 'zh-CN'});
  const page = await context.newPage();
  const probes = [];
  page.on('request', request => { if (request.url().startsWith(probe)) probes.push(request.url()); });
  await page.goto(baseUrl, {waitUntil: 'domcontentloaded'});
  await settle(page);
  await page.getByRole('tab', {name: '手动输入'}).click();
  await settle(page);
  const panel = page.getByRole('tabpanel').filter({hasText: '开衫工艺设计'}).first();
  const reader = panel.locator('details').filter({has: page.locator('summary:has-text("人工工序图解（校验与阅读）")')}).first();
  await reader.scrollIntoViewIfNeeded();
  if (await reader.getAttribute('open') === null) await reader.locator(':scope > summary').click();
  await settle(page);
  await reader.locator('input[type="file"]').setInputFiles(file);
  await page.waitForTimeout(1200);
  await settle(page);
  await reader.getByRole('button', {name: '校验并载入工序', exact: true}).click();
  await settle(page);
  await page.waitForTimeout(1500);
  const text = await reader.innerText();
  console.log('plan accepted:', text.includes('工序设计核对稿'));
  console.log('img elements inside the reader pointing at the probe:',
              await reader.locator(`img[src^="${probe}"]`).count());
  console.log('anchors inside the reader pointing at the probe:',
              await reader.locator(`a[href^="${probe}"]`).count());
  console.log('headings rendered from a review note (h1 with forged text):',
              await reader.locator('h1:has-text("伪造标题")').count());
  console.log('bold rendered from the title:', await reader.locator('strong:has-text("粗体")').count());
  console.log('requests the browser attempted to the probe port:', JSON.stringify([...new Set(probes)]));
  await reader.screenshot({path: path.join(outDir, 'reader-markdown.png')}).catch(() => {});
  await browser.close();
})().catch(error => { console.error('ABORTED', error.message.slice(0, 500)); process.exit(2); });
