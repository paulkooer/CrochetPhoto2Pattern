// Round 3: untouched size inputs follow the height, a hand-edited one stays, reset restores it.
// Usage: node r3_doll_follow_height.cjs <repo-root> <base-url> <out-dir>
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
  const context = await browser.newContext({viewport: {width: 1380, height: 1000}, locale: 'zh-CN'});
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
  const H = '原型目标总高（不含帽子，cm）', HEAD = '原型头径（cm）', PALM = '手掌目标直径（cm）', BODICE = '上衣片目标长度（cm）';
  const value = async label => doll.getByLabel(label, {exact: true}).inputValue();
  const set = async (label, text) => {
    const input = doll.getByLabel(label, {exact: true});
    await input.fill(text); await input.press('Enter'); await settle(page);
  };
  const state = async tag => console.log(tag, JSON.stringify({
    height: await value(H), head: await value(HEAD), palm: await value(PALM), bodice: await value(BODICE),
    handEditedNote: ((await inner.innerText()).match(/已手改、不随总高变化：[^\n]*/) || ['(none)'])[0],
    resetButton: await inner.getByRole('button', {name: '恢复为按总高比例的尺寸', exact: true}).count(),
  }));
  await state('start            ');
  await set(H, '25');   await state('height 25        ');   // 6*25/24 = 6.25, 1.5*25/24 = 1.5625
  await set(H, '31');   await state('height 31        ');   // untouched values must keep following
  await set(HEAD, '7'); await state('head typed 7     ');
  await set(H, '36');   await state('height 36        ');   // head stays 7; palm 2.25; bodice 8.1
  await inner.getByRole('button', {name: '恢复为按总高比例的尺寸', exact: true}).click();
  await settle(page);   await state('after reset      ');   // head 9
  await set(H, '24');   await state('height back to 24');
  await doll.screenshot({path: path.join(outDir, 'doll-follow-height.png')}).catch(() => {});
  await browser.close();
})().catch(error => { console.error('ABORTED', error.message.slice(0, 500)); process.exit(2); });
