// Do the doll designer's dependent defaults follow a changed target height?
// Usage: node doll_defaults.cjs <repo-root> <base-url> <out-dir>
const path = require('node:path');
const fs = require('node:fs');
const [repo, baseUrl, outDir] = process.argv.slice(2);
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
  if (await page.getByTestId('stException').count()) {
    throw new Error('Streamlit exception: ' + (await page.getByTestId('stException').first().innerText()).slice(0, 300));
  }
}
async function open(details) {
  await details.scrollIntoViewIfNeeded();
  if (await details.getAttribute('open') === null) await details.locator(':scope > summary').click();
}

(async () => {
  fs.mkdirSync(outDir, {recursive: true});
  const browser = await chromium.launch({headless: true});
  const context = await browser.newContext({acceptDownloads: true, viewport: {width: 1380, height: 1000}, locale: 'zh-CN'});
  const page = await context.newPage();
  await page.goto(baseUrl, {waitUntil: 'domcontentloaded'});
  await settle(page);
  await page.getByRole('tab', {name: '手动输入'}).click();
  await settle(page);
  const panel = page.getByRole('tabpanel').filter({hasText: '开衫工艺设计'}).first();
  const doll = panel.locator('details').filter({has: page.locator('summary:has-text("穿衣人偶结构原型")')}).first();
  await open(doll);
  await settle(page);
  const inner = doll.locator('details').filter({has: page.locator('summary:has-text("调整关键轮廓与构造")')}).first();
  await open(inner);
  await settle(page);
  const labels = ['原型目标总高（不含帽子，cm）', '原型头径（cm）', '手掌目标直径（cm）', '手腕目标直径（cm）',
                  '鞋底目标长度（cm）', '鞋底目标宽度（cm）', '上衣片目标长度（cm）'];
  const read = async () => {
    const values = {};
    for (const label of labels) values[label] = await doll.getByLabel(label, {exact: true}).inputValue();
    return values;
  };
  console.log('before (height 24):', JSON.stringify(await read()));
  const height = doll.getByLabel(labels[0], {exact: true});
  await height.fill('48');
  await height.press('Enter');
  await settle(page);
  console.log('after height -> 48 :', JSON.stringify(await read()));
  await doll.getByRole('button', {name: '生成穿衣人偶结构原型', exact: true}).click();
  await settle(page);
  const text = await doll.innerText();
  const error = text.match(/(设计参数需要调整|暂不能生成该结构)[^\n]*/);
  console.log('generate at 48:', error ? 'ERROR SHOWN: ' + error[0].slice(0, 160) : 'plan generated');
  const button = doll.getByRole('button', {name: '下载设计参数 JSON', exact: true});
  if (await button.count() && !(await button.isDisabled())) {
    await button.scrollIntoViewIfNeeded();
    const [event] = await Promise.all([page.waitForEvent('download', {timeout: 60000}), button.click()]);
    const file = path.join(outDir, 'doll-design-height48.json');
    await event.saveAs(file);
    const design = JSON.parse(fs.readFileSync(file, 'utf8'));
    const keys = ['height_cm', 'head_diameter_cm', 'leg_length_cm', 'body_diameter_cm', 'neck_diameter_cm',
                  'arm_length_cm', 'palm_diameter_cm', 'wrist_diameter_cm', 'foot_length_cm', 'foot_width_cm',
                  'bodice_length_cm', 'skirt_length_cm'];
    console.log('downloaded design at 48:', JSON.stringify(Object.fromEntries(keys.map(k => [k, design[k]]))));
    console.log('scaled starter would be :', JSON.stringify(Object.fromEntries(
      [['head_diameter_cm', 12], ['leg_length_cm', 12], ['body_diameter_cm', 7.2], ['neck_diameter_cm', 2.4],
       ['arm_length_cm', 12], ['palm_diameter_cm', 3], ['wrist_diameter_cm', 1.8], ['foot_length_cm', 6],
       ['foot_width_cm', 3.2], ['bodice_length_cm', 10.8], ['skirt_length_cm', 14]])));
  }
  await doll.screenshot({path: path.join(outDir, 'doll-height48.png')}).catch(() => {});
  await browser.close();
})().catch(error => { console.error('ABORTED', error.message.slice(0, 500)); process.exit(2); });
