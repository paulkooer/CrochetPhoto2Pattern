// Real-browser pass over the three construction entries of the manual tab.
// Independent helpers (no upload-ack instrumentation); Playwright is loaded
// read-only from the repository's scripts/browser/node_modules.
// Usage: node ui_pass.cjs <repo-root> <base-url> <out-dir> <packaged-examples-dir>
const path = require('node:path');
const fs = require('node:fs');
const crypto = require('node:crypto');
const [repo, baseUrl, outDir, examples] = process.argv.slice(2);
const {chromium} = require(path.join(repo, 'scripts/browser/node_modules/playwright'));

const sha = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const results = [];
function record(ok, name, detail = '') {
  results.push({ok, name, detail});
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? '  | ' + detail : ''}`);
}
function note(name, detail) { console.log(`NOTE  ${name}  | ${detail}`); }

async function settle(page) {
  const app = page.getByTestId('stApp');
  for (let round = 0; round < 3; round += 1) {
    await page.waitForTimeout(350);
    await app.waitFor({state: 'visible', timeout: 60000});
    await page.waitForFunction(() => {
      const el = document.querySelector('[data-testid="stApp"]');
      return el && el.getAttribute('data-test-script-state') === 'notRunning'
        && el.getAttribute('data-test-connection-state') === 'CONNECTED';
    }, null, {timeout: 90000});
  }
  const errors = await page.getByTestId('stException').count();
  if (errors) {
    const text = (await page.getByTestId('stException').first().innerText()).slice(0, 400);
    throw new Error('Streamlit exception on page: ' + text);
  }
}
function expander(scope, title) {
  return scope.locator('details').filter({has: scope.page ? scope.page().locator(`summary:has-text("${title}")`) : scope.locator(`summary:has-text("${title}")`)}).last();
}
async function open(details) {
  await details.scrollIntoViewIfNeeded();
  if (await details.getAttribute('open') === null) await details.locator(':scope > summary').click();
}
async function setNumber(page, scope, label, value) {
  const input = scope.getByLabel(label, {exact: true});
  await input.scrollIntoViewIfNeeded();
  await input.fill(String(value));
  await input.press('Enter');
  await settle(page);
}
async function download(page, button, file) {
  await button.scrollIntoViewIfNeeded();
  const [event] = await Promise.all([page.waitForEvent('download', {timeout: 60000}), button.click()]);
  if (await event.failure()) throw new Error('download failed: ' + await event.failure());
  await event.saveAs(file);
  await settle(page);
  return file;
}
const isDisabled = async button => (await button.count()) > 0 && await button.first().isDisabled();

(async () => {
  fs.mkdirSync(outDir, {recursive: true});
  const browser = await chromium.launch({headless: true});
  const context = await browser.newContext({acceptDownloads: true, viewport: {width: 1380, height: 1000}, locale: 'zh-CN'});
  const page = await context.newPage();
  const external = new Set();
  page.on('request', request => {
    const url = new URL(request.url());
    if (!['127.0.0.1', 'localhost'].includes(url.hostname) && !['data:', 'blob:'].includes(url.protocol)) external.add(url.origin);
  });
  const consoleErrors = [];
  page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text().slice(0, 200)); });

  await page.goto(baseUrl, {waitUntil: 'domcontentloaded'});
  await settle(page);
  const tabs = await page.getByRole('tab').allInnerTexts();
  note('tabs', JSON.stringify(tabs));
  await page.getByRole('tab', {name: '手动输入'}).click();
  await settle(page);
  const panel = page.getByRole('tabpanel').filter({hasText: '开衫工艺设计'}).first();
  const summaries = await panel.locator('details > summary').allInnerTexts();
  note('manual-tab expanders', JSON.stringify(summaries.map(s => s.trim().split('\n')[0])));

  // ---------------- A. Cardigan designer ----------------
  const card = panel.locator('details').filter({has: page.locator('summary:has-text("开衫工艺设计（试验）")')}).first();
  await open(card);
  await settle(page);
  const generate = card.getByRole('button', {name: '生成开衫工序设计', exact: true});
  // A1 default mode: no ribbing gauge -> staged draft only
  await generate.click();
  await settle(page);
  const a1 = await card.innerText();
  record(a1.includes('当前只生成到已有依据的阶段'), 'A1 default mode (no rib gauge) yields a staged draft, not a full design');
  const reportBtn = card.getByRole('button', {name: '下载开衫设计记录', exact: true});
  const report1 = JSON.parse(fs.readFileSync(await download(page, reportBtn, path.join(outDir, 'A1-report.json')), 'utf8'));
  record(report1.stage === 'hem_blocked' && report1.physical_execution_verified === false
         && report1.ready_for_whole_garment_trial === false, 'A1 report stage/flags', `stage=${report1.stage}`);
  await page.screenshot({path: path.join(outDir, 'A1-default-draft.png'), fullPage: false});

  // A2 switch to hypothetical gauges: old result must be marked stale, downloads disabled
  await card.getByText('用假设密度查看工程示例', {exact: true}).click();
  await settle(page);
  const a2 = await card.innerText();
  record(a2.includes('输入或生成器版本已改变'), 'A2 changing gauge mode marks the kept result as stale');
  const planBtn = card.getByRole('button', {name: '下载开衫工序 JSON', exact: true});
  record(await isDisabled(reportBtn) && await isDisabled(planBtn), 'A2 stale result: report and plan downloads are disabled in the browser');

  // A3 full generation with UI defaults; UI plan must equal CLI plan for the same request
  await generate.click();
  await settle(page);
  record((await card.innerText()).includes('已组合领肩、衣身、下摆、门襟扣眼及双袖'), 'A3 hypothetical gauges: integrated open-cuff design shown');
  const report3File = await download(page, reportBtn, path.join(outDir, 'A3-report.json'));
  const plan3File = await download(page, planBtn, path.join(outDir, 'A3-plan.json'));
  const report3 = JSON.parse(fs.readFileSync(report3File, 'utf8'));
  fs.writeFileSync(path.join(outDir, 'A3-request.json'), JSON.stringify(report3.request, null, 2));
  note('A3 request (as recorded by the UI)', JSON.stringify({hook_mm: report3.request.method.hook_mm,
    dimension_basis: report3.request.dimension_basis, body_rows: report3.stages.body.rows,
    sleeve_rows: report3.stages.body.sleeve_rows, stage: report3.stage}));

  // A4 prepare PDF, then change body length -> everything stale; regenerate -> old PDF must be gone
  const prepare = card.getByRole('button', {name: '准备开衫工序 PDF', exact: true});
  await prepare.click();
  await settle(page);
  const pdfBtn = card.getByRole('button', {name: '下载开衫工序 PDF', exact: true});
  record(await pdfBtn.count() === 1, 'A4 PDF prepared and offered');
  const pdf4 = await download(page, pdfBtn, path.join(outDir, 'A4-plan-odd.pdf'));
  record(fs.readFileSync(pdf4).subarray(0, 5).toString() === '%PDF-', 'A4 downloaded file is a PDF', `${fs.statSync(pdf4).size} bytes`);
  await setNumber(page, card, '腋下至下摆前的衣身长度 cm', '7.1');
  const stale4 = (await card.innerText()).includes('输入或生成器版本已改变');
  record(stale4 && await isDisabled(pdfBtn) && await isDisabled(planBtn) && await isDisabled(prepare),
         'A4 after editing body length: stale notice, PDF/plan/prepare all disabled');
  await generate.click();
  await settle(page);
  record(await pdfBtn.count() === 0, 'A4 regenerating removes the PDF prepared for the earlier input');
  const report5 = JSON.parse(fs.readFileSync(await download(page, reportBtn, path.join(outDir, 'A5-report-even.json')), 'utf8'));
  const plan5File = await download(page, planBtn, path.join(outDir, 'A5-plan-even.json'));
  note('A5 even-row design from the UI', JSON.stringify({body_rows: report5.stages.body.rows, stage: report5.stage,
    unresolved: report5.unresolved.length, plan_sha256: sha(plan5File).slice(0, 16)}));
  const a5 = await card.innerText();
  record(!/跳|不连续|领口方向/.test(a5), 'A5 (informational) UI shows no warning about band path continuity for even body rows',
         'expected: no such warning exists in this build');
  await card.screenshot({path: path.join(outDir, 'A5-even-body-result.png')}).catch(() => {});

  // A6 "own swatch" mode: which hook size does the UI let the user state?
  await card.getByText('填入自己的小样密度', {exact: true}).click();
  await settle(page);
  const inner = card.locator('details').filter({has: page.locator('summary:has-text("调整密度、边宽与扣眼")')}).first();
  await open(inner);
  await settle(page);
  const labels = await card.locator('label').allInnerTexts();
  const hookInputs = labels.filter(text => /钩针|针号|mm/.test(text));
  note('A6 own-swatch inputs mentioning hook size', JSON.stringify(hookInputs));
  record(hookInputs.length === 0, 'A6 (informational) own-swatch mode has no hook-size input', 'report/PDF still carry hook_mm=3.0');

  // ---------------- B. Dressed-doll prototype ----------------
  const doll = panel.locator('details').filter({has: page.locator('summary:has-text("穿衣人偶结构原型")')}).first();
  await open(doll);
  await settle(page);
  await doll.getByRole('button', {name: '生成穿衣人偶结构原型', exact: true}).click();
  await settle(page);
  const dollText = await doll.innerText();
  record(dollText.includes('结构原型 · 未实钩验证'), 'B1 doll prototype generated and labelled unverified');
  const dollMd = await download(page, doll.getByRole('button', {name: '下载逐部件说明 Markdown', exact: true}), path.join(outDir, 'B1-doll-plan.md'));
  const dollPlan = await download(page, doll.getByRole('button', {name: '下载结构方案 JSON', exact: true}), path.join(outDir, 'B1-doll-plan.json'));
  const starter = JSON.parse(fs.readFileSync(dollPlan, 'utf8')).design;
  note('B1 UI default design', JSON.stringify({hat: starter.hat, hair: starter.hair, height: starter.height_cm, layers: starter.skirt_layers}));
  for (const name of ['doll-wide-brim', 'doll-folded-cap']) {
    const packaged = path.join(examples, name, 'plan.md');
    if (sha(packaged) === sha(dollMd)) note('B1', `UI Markdown is byte-identical to packaged CLI example ${name}/plan.md`);
  }
  await doll.getByRole('button', {name: '准备结构原型 PDF', exact: true}).click();
  await settle(page);
  const dollPdf = doll.getByRole('button', {name: '下载结构原型 PDF', exact: true});
  record(await dollPdf.count() === 1, 'B2 doll PDF prepared and offered');
  await setNumber(page, doll, '原型目标总高（不含帽子，cm）', '30');
  const b3 = await doll.innerText();
  record(b3.includes('参数已改变，下方仍是上一份原型') && await isDisabled(dollPdf)
         && await isDisabled(doll.getByRole('button', {name: '下载逐部件说明 Markdown', exact: true})),
         'B3 after editing height: stale notice, Markdown and PDF downloads disabled');
  await doll.getByRole('button', {name: '生成穿衣人偶结构原型', exact: true}).click();
  await settle(page);
  record(await dollPdf.count() === 0, 'B3 regenerating removes the PDF prepared for the earlier design');

  // ---------------- C. Working-path reader ----------------
  const reader = panel.locator('details').filter({has: page.locator('summary:has-text("人工工序图解（校验与阅读）")')}).first();
  await open(reader);
  await settle(page);
  const upload = async file => {
    await reader.locator('input[type="file"]').setInputFiles(file);
    await page.waitForTimeout(1200);
    await settle(page);
  };
  const load = reader.getByRole('button', {name: '校验并载入工序', exact: true});
  await upload(path.join(examples, 'cardigan-open', 'path-plan.json'));
  await load.click();
  await settle(page);
  const c1 = await reader.innerText();
  record(c1.includes('工序设计核对稿 · 未实钩、未试穿') && c1.includes('参数生成开衫工序组合稿'), 'C1 packaged cardigan plan loads in the reader');
  const md = await download(page, reader.getByRole('button', {name: '下载逐步说明', exact: true}), path.join(outDir, 'C1-reader.md'));
  record(sha(md) === sha(path.join(examples, 'cardigan-open', 'path-explanation.md')),
         'C1 reader Markdown is byte-identical to the CLI Markdown for the same plan');
  await reader.getByRole('button', {name: '准备工序 PDF', exact: true}).click();
  await settle(page);
  const readerPdf = reader.getByRole('button', {name: '下载工序 PDF', exact: true});
  record(await readerPdf.count() === 1, 'C2 reader PDF prepared and offered');
  // C3 upload a different file without pressing "load": old plan stays, downloads must be disabled
  await upload(path.join(examples, 'armhole-demo', 'path-plan.json'));
  const c3 = await reader.innerText();
  record(c3.includes('上传内容已改变') && await isDisabled(readerPdf)
         && await isDisabled(reader.getByRole('button', {name: '下载逐步说明', exact: true})),
         'C3 new upload not yet loaded: stale notice, Markdown and PDF downloads disabled');
  await load.click();
  await settle(page);
  const c4 = await reader.innerText();
  record(c4.includes('袖窿工作路径演示小样') && await readerPdf.count() === 0, 'C4 loading the second plan replaces the view and drops the first plan\'s PDF');
  // C5 the even-body plan produced by the UI in A5 is accepted by the reader without warning
  await upload(plan5File);
  await load.click();
  await settle(page);
  const c5 = await reader.innerText();
  record(c5.includes('参数生成开衫工序组合稿') && !c5.includes('工序需要核对'), 'C5 (informational) reader accepts the even-body cardigan plan from A5 with no error');
  // C6 a rejected file must not replace the stored plan nor enable downloads for it
  const bad = path.join(outDir, 'C6-bad.json');
  fs.writeFileSync(bad, '{"title": "x", "title": "y", "steps": []}');
  await upload(bad);
  await load.click();
  await settle(page);
  const c6 = await reader.innerText();
  record(c6.includes('工序需要核对') && c6.includes('参数生成开衫工序组合稿')
         && await isDisabled(reader.getByRole('button', {name: '下载逐步说明', exact: true})),
         'C6 rejected upload: error shown, previous plan kept, its downloads stay disabled');

  // ---------------- D. Cross-module state ----------------
  const cardAfter = await card.innerText();
  const dollAfter = await doll.innerText();
  record(cardAfter.includes('输入或生成器版本已改变') || cardAfter.includes('已组合领肩'), 'D1 cardigan result still present after using the other two entries');
  record(dollAfter.includes('结构原型 · 未实钩验证'), 'D1 doll result still present after using the reader');
  record(external.size === 0, 'D2 no request left 127.0.0.1 during the whole pass', JSON.stringify([...external]));
  note('browser console errors', JSON.stringify(consoleErrors.slice(0, 5)));

  fs.writeFileSync(path.join(outDir, 'ui-pass-results.json'), JSON.stringify(results, null, 2));
  await browser.close();
  const failed = results.filter(r => !r.ok).length;
  console.log(`SUMMARY ${results.length - failed} passed, ${failed} failed`);
  process.exit(failed ? 1 : 0);
})().catch(error => { console.error('ABORTED', error.message.slice(0, 600)); process.exit(2); });
