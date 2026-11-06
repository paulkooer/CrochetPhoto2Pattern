// Optional real-browser regression. Uses a local app and synthetic input only.
// Setup and evidence scope: docs/browser-regression.md.
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const {execFileSync} = require('node:child_process');
const {createHash} = require('node:crypto');
const playwrightModule = process.env.CROCHET_PLAYWRIGHT_MODULE || path.join(__dirname,'browser/node_modules/playwright');
const {chromium} = require(playwrightModule);
const {expect} = require(path.join(playwrightModule,'test'));

const baseURL = process.env.CROCHET_BROWSER_URL || 'http://127.0.0.1:18502';
assert(['127.0.0.1', 'localhost', '[::1]'].includes(new URL(baseURL).hostname),
       'Use an isolated local test server, never a production history database.');
const key = (scope, name) => scope.locator(`[class~="st-key-${name}"]`);
const headCheck = (scope,rid) => key(scope,`sheet_part_${rid}_0`).locator('input[type="checkbox"]').first();
const syntheticSVG = `<svg xmlns="http://www.w3.org/2000/svg" width="320" height="640">
<rect width="320" height="640" fill="white"/>
<circle cx="160" cy="110" r="65" fill="#e6b28c"/>
<rect x="100" y="180" width="120" height="240" rx="35" fill="#1677b8"/>
<rect x="65" y="200" width="32" height="180" rx="15" fill="#e6b28c"/>
<rect x="223" y="200" width="32" height="180" rx="15" fill="#e6b28c"/>
<rect x="110" y="420" width="36" height="170" rx="15" fill="#303030"/>
<rect x="174" y="420" width="36" height="170" rx="15" fill="#303030"/>
</svg>`;

async function reveal(locator) {
  for (const details of await locator.locator('xpath=ancestor::details').all()) {
    if (await details.getAttribute('open') === null) {
      await details.locator(':scope > summary').click();
    }
  }
}

async function settle(page) {
  // Give the websocket update a turn, then wait for visible computation to finish.
  await page.waitForTimeout(300);
  await page.locator('[data-testid="stStatusWidget"]').waitFor({state: 'hidden', timeout: 45000});
  assert.equal(await page.locator('[data-testid="stException"]').count(), 0,
               'Streamlit reported an uncaught application exception.');
}

async function clickKey(page, scope, name) {
  const holder = key(scope,name);
  await holder.waitFor({state:'attached'});
  await reveal(holder);
  // Tooltips can contain an aria-hidden copy of their trigger. Click the live button.
  const button = holder.getByRole('button');
  await button.click();
  await settle(page);
}

async function fillKey(page, scope, name, value) {
  const field = key(scope, name).locator('input:not([type="file"]), textarea').first();
  await field.waitFor({state:'attached'});
  await reveal(field);
  await field.fill(value);
  await field.press('Tab');
  await settle(page);
}

async function chooseSelect(page, scope, name, label) {
  const holder = key(scope, name);
  await holder.waitFor({state:'attached'});
  await reveal(holder);
  const input = holder.locator('input').first();
  await input.scrollIntoViewIfNeeded();
  const option = page.getByRole('option', {name: label, exact: true});
  // Above 25 options the menu is virtual. fill() leaves the filter text in the
  // box and the menu closes before that row exists, so the text is not a
  // selection. Real keystrokes mount the focused match. Enter commits only the
  // focused option; ArrowDown moves off it. The custom-name field appears only
  // after Streamlit accepts「自定义颜色名…」.
  const custom = label === '自定义颜色名…'
    ? key(scope, name.replace(/_pick$/, '_custom')).locator('input')
    : null;
  for (let attempt = 0; attempt < 3; attempt++) {
    await input.click();
    await input.fill(label);
    if (await option.count() === 0) {
      await holder.getByRole('button', {name: 'Open', exact: true}).click();
    }
    if (await option.count() === 0) {
      await input.click();
      await input.press(process.platform === 'darwin' ? 'Meta+A' : 'Control+A');
      await input.pressSequentially(label, {delay: 15});
    }
    try {
      await expect(option).toBeVisible({timeout: 2500});
      await expect(option).toHaveAttribute('data-focused', 'true', {timeout: 2500});
    } catch {
      await page.keyboard.press('Escape');
      continue;
    }
    await input.press('Enter');
    await input.blur().catch(() => {});
    await settle(page);
    if (custom) {
      if (await custom.count()) return;
      continue;
    }
    if (await input.inputValue() === label) return;
  }
  throw new Error(`could not select ${label}`);
}

async function setSwatch(page, scope, name, hex) {
  const holder = key(scope, name);
  await holder.waitFor({state:'attached'});
  await reveal(holder);
  await holder.getByRole('button', {name: /color picker/}).click();
  const dialog = page.getByRole('dialog', {name: /color picker/});
  await dialog.waitFor({state:'visible'});
  const input = dialog.locator('input').first();
  await input.click({clickCount: 3});
  await input.fill(hex.replace('#', ''));
  await input.press('Enter');
  await page.keyboard.press('Escape');
  await settle(page);
}

async function resultId(scope, previousId) {
  const holder = scope.locator('[class*="st-key-hist_save_"]').first();
  await holder.waitFor({state:'attached'});
  // A rerun may briefly leave the old result on screen after the click returns.
  if (previousId) await expect(holder).not.toHaveClass(new RegExp(`st-key-hist_save_${previousId}(?:\\s|$)`),{timeout:45000});
  return holder.evaluate(e => [...e.classList].find(c => c.startsWith('st-key-hist_save_'))
                             .slice('st-key-hist_save_'.length));
}

async function download(page, locator, output) {
  await reveal(locator);
  const waiting = page.waitForEvent('download', {timeout:45000});
  await locator.click();
  const value = await waiting;
  assert.equal(await value.failure(), null);
  await value.saveAs(output);
  await settle(page);
  return fs.readFile(output);
}

async function headProgress(page, scope, rid, checked) {
  const input = headCheck(scope,rid);
  await reveal(input);
  if (await input.isChecked() !== checked) {
    const label = input.locator('xpath=ancestor::label');
    await label.evaluate(el => el.scrollIntoView({block:'center'}));
    await label.click();
  }
  await settle(page);
  await expect(input).toBeChecked({checked});
}

(async () => {
  const output = process.env.CROCHET_BROWSER_OUTPUT || await fs.mkdtemp(path.join(os.tmpdir(), 'crochet-browser-'));
  await fs.mkdir(output, {recursive:true});
  const report = {
    source_commit:execFileSync('git', ['rev-parse','HEAD'], {cwd:path.join(__dirname,'..'),encoding:'utf8'}).trim(),
    harness_sha256:createHash('sha256').update(await fs.readFile(__filename)).digest('hex'),
    working_tree_clean:!execFileSync('git',['status','--porcelain'],{cwd:path.join(__dirname,'..'),encoding:'utf8'}).trim(),
    github_head_commit:process.env.CROCHET_BROWSER_HEAD_SHA || null,
    base_url:baseURL, input:'synthetic SVG/PNG and CLI-generated manual garment pattern', checks:[], page_errors:[],
    blocked_external_requests:[], physical_validation:false,
  };
  const browser = await chromium.launch({
    executablePath:process.env.CROCHET_CHROME_EXECUTABLE || undefined, headless:true,
    args:['--disable-background-networking','--disable-component-update'],
  });
  report.browser = browser.version();
  let lastPage;
  const record = name => {report.checks.push({name,status:'pass'}); console.log(`PASS ${name}`);};
  async function context(viewport = {width:1440,height:1100}) {
    const ctx = await browser.newContext({viewport,acceptDownloads:true});
    await ctx.route('**/*', route => {
      const hostname = new URL(route.request().url()).hostname;
      if (['127.0.0.1','localhost','[::1]'].includes(hostname)) return route.continue();
      report.blocked_external_requests.push(route.request().url());
      return route.abort();
    });
    ctx.on('page', p => p.on('pageerror', e => report.page_errors.push(String(e))));
    return ctx;
  }
  try {
    const ctx = await context();
    const page = lastPage = await ctx.newPage();
    await page.setContent(syntheticSVG);
    const photo = path.join(output, 'synthetic-doll.png');
    await page.locator('svg').screenshot({path:photo});
    await page.goto(baseURL);
    // Sidebar information architecture: the gauge comes first; the three ways to
    // open existing work sit together under one heading.
    const sidebarOutline = page.locator('[data-testid="stSidebar"]')
      .locator('h3, [data-testid="stExpander"] summary [data-testid="stMarkdownContainer"]');
    await expect(sidebarOutline).toHaveText(['编织密度（小样）','塑形选项（进阶）','打开已有工作',
                                             '打开备份图解','打开试钩包','我的图解（历史）']);
    await page.locator('[data-testid="stSidebar"]').screenshot({path:path.join(output,'sidebar-information-architecture.png')});
    record('sidebar lists the gauge first and groups the existing-work entries');
    const photoTab = page.getByRole('tab', {name:'照片分析（本地）',exact:true});
    const manualTab = page.getByRole('tab', {name:'手动输入',exact:true});
    await photoTab.focus();
    await photoTab.press('ArrowRight');
    await expect(manualTab).toBeFocused();
    await expect(manualTab).toHaveCSS('outline-width','2px');
    await expect(manualTab).toHaveCSS('outline-color','rgb(29, 36, 64)');
    await manualTab.press('ArrowLeft');
    await expect(photoTab).toBeFocused();
    await expect(photoTab).toHaveAttribute('aria-selected','true');
    await photoTab.click();
    const photoPanel = page.getByRole('tabpanel', {name:'照片分析（本地）',exact:true});
    await key(photoPanel,'photo_uploader').locator('input[type="file"]').setInputFiles(photo);
    await key(photoPanel,'btn_photo').getByRole('button').waitFor({state:'visible'});
    await clickKey(page,photoPanel,'btn_photo');
    const enable = photoPanel.locator('[class*="st-key-review_mask_enabled_"] input');
    await enable.waitFor({state:'visible'});
    record('upload PNG and prepare local photo review');

    await enable.locator('xpath=ancestor::label').click();
    await settle(page);
    const editor = page.frameLocator('iframe[title*="subject_mask_editor"]');
    await editor.locator('#canvas').waitFor({state:'visible'});
    // The iframe receives theme values from Python, rather than relying only on its fallbacks.
    const outerPalette = await page.evaluate(() => {
      const css = getComputedStyle(document.documentElement);
      return ['ink','edge','paper','sans'].map(name => css.getPropertyValue(`--${name}`).trim());
    });
    await expect.poll(() => editor.locator('html').evaluate(element =>
      ['ink','edge','paper','font'].map(name => element.style.getPropertyValue(`--${name}`).trim())
    )).toEqual(outerPalette);
    await page.evaluate(() => {
      window.__crochetMaskMessages = [];
      window.addEventListener('message', e => {
        if (e.data?.type === 'streamlit:setComponentValue' && typeof e.data.value?.pixels === 'string') {
          window.__crochetMaskMessages.push(e.data.value);
        }
      });
    });
    async function maskAction(action) {
      const before = await page.evaluate(() => window.__crochetMaskMessages.length);
      await action();
      await page.waitForFunction(n => window.__crochetMaskMessages.length > n, before);
      await settle(page);
      return page.evaluate(() => window.__crochetMaskMessages.at(-1));
    }
    async function paint(x,y) {
      await editor.locator('#canvas').scrollIntoViewIfNeeded();
      const box = await editor.locator('#canvas').boundingBox();
      return maskAction(() => page.mouse.click(box.x+box.width*x,box.y+box.height*y));
    }
    const added = await paint(0.06,0.06);
    assert.equal(added.use_original,false);
    await editor.locator('#mode').selectOption('0');
    const erased = await paint(0.5,0.5);
    assert.notEqual(erased.pixels,added.pixels);
    const undone = await maskAction(() => editor.locator('#undo').click());
    assert.equal(undone.pixels,added.pixels);
    const reset = await maskAction(() => editor.locator('#reset').click());
    assert.equal(reset.use_original,true);
    await editor.locator('#mode').selectOption('1');
    await paint(0.06,0.06);
    await page.screenshot({path:path.join(output,'photo-mask.png'),fullPage:true});
    record('embedded canvas add/erase/undo/reset reaches the Streamlit app');

    await photoPanel.getByText('单个玩偶，所需部件可用下方列表表达',{exact:true}).click();
    await settle(page);
    await expect(page.getByRole('tab',{name:'照片分析（本地）',exact:true}))
      .toHaveCSS('background-color','rgb(255, 225, 77)');
    await expect(photoPanel.getByText('单个玩偶，所需部件可用下方列表表达',{exact:true})
      .locator('xpath=ancestor::label[1]')).toHaveCSS('background-color','rgb(255, 244, 184)');
    const ratio = photoPanel.locator('[class*="st-key-review_ratio_"] input');
    await ratio.fill('0.3');await ratio.press('Tab');await settle(page);
    const generate = photoPanel.getByRole('button',{name:'确认并生成图解',exact:true});
    assert.equal(await generate.isEnabled(),true);
    await generate.click();await settle(page);
    let photoId = await resultId(photoPanel);
    record('complete subject/proportion/parts review and generate');

    // 2026-11-05 information architecture: provenance folds into a collapsed
    // sources panel; the structure table drops the developer coordinate column
    // and the coordinate legend moves into "查看结构 JSON".
    const sourcesPanel = photoPanel.locator('details').filter({hasText:'来源与限制'}).first();
    assert.equal(await sourcesPanel.getAttribute('open'),null,'The sources panel must start collapsed.');
    await sourcesPanel.locator(':scope > summary').click();
    await settle(page);
    await expect(photoPanel.getByText('✓ 比例与部件已经过人工确认；原始解析来源保留如下。',{exact:true})).toBeVisible();
    await expect(photoPanel.getByText('位置 / 旋转',{exact:true})).toHaveCount(0);
    await expect(photoPanel.getByText('当前基础色是图解正在使用的颜色。原始结构色是照片或模板最初记录的颜色，手工改色不会改写它。连接来自结构模板推断，并非单张照片的三维测量；坐标、位置和旋转细节见「查看结构 JSON」。',{exact:true})).toBeVisible();
    const structureJsonPanel = photoPanel.locator('details').filter({hasText:'查看结构 JSON'}).first();
    await structureJsonPanel.locator(':scope > summary').click();
    await settle(page);
    await expect(photoPanel.getByText(/结构 v2 坐标：/)).toBeVisible();
    record('result page folds sources by default and moves coordinates into the structure JSON');

    // A fragment rerun must not close the part panel or shrink the marked row.
    const sheet = key(photoPanel,`sheet_part_${photoId}_0`);
    const rounds = sheet.locator('input[type="checkbox"]');
    await reveal(rounds.first());
    const partDetails = rounds.first().locator('xpath=ancestor::details[1]');
    const progress = sheet.locator('[data-testid="stProgress"]');
    for (let i=0;i<3;i++) {
      const checkbox = rounds.nth(i);
      await checkbox.locator('xpath=ancestor::label').click();
      await expect(checkbox).toBeChecked();
      await expect(progress).toContainText(`(${i+1}/`);
      await expect(partDetails).toHaveAttribute('open','');
    }
    const firstRow = rounds.first().locator('xpath=ancestor::label');
    const widths = await firstRow.evaluate(element => ({
      row:element.getBoundingClientRect().width,
      panel:element.closest('[data-testid="stExpanderDetails"]').getBoundingClientRect().width,
    }));
    assert(widths.row >= widths.panel * 0.9, `Marked row does not fill the panel: ${JSON.stringify(widths)}`);
    await expect(firstRow).toHaveCSS('background-image',/rgb\(255,\s*244,\s*184\)/);
    await page.screenshot({path:path.join(output,'pattern-sheet-progress.png')});
    await sheet.getByRole('button',{name:'重置进度',exact:true}).click();
    await expect(progress).toContainText('(0/');
    await expect(partDetails).toHaveAttribute('open','');
    await expect(rounds.first()).not.toBeChecked();
    record('marker styles and repeated progress changes preserve the open, full-width part panel');

    const backupBytes = await download(page,key(photoPanel,`dl_backup_${photoId}`).getByRole('button'),path.join(output,'photo-backup.json'));
    const backup = JSON.parse(backupBytes);
    const params = JSON.parse(await download(page,key(photoPanel,`dl_json_${photoId}`).getByRole('button'),path.join(output,'photo-params.json')));
    assert.deepEqual(params.parts,backup.params.parts);
    assert.equal(backup.vision_meta.reviewed_by_user,true);
    assert.equal(backup.vision_meta.requires_subject_review,false);
    assert.equal(backup.geometry.mask_review,undefined);
    const markdown = await download(page,key(photoPanel,`dl_md_${photoId}`).getByRole('button'),path.join(output,'photo-pattern.md'));
    for (const part of params.parts) assert(markdown.toString().includes(part.name));
    await clickKey(page,photoPanel,`pdf_gen_${photoId}`);
    const pdf = await download(page,key(photoPanel,`dl_pdf_${photoId}`).getByRole('button'),path.join(output,'photo-pattern.pdf'));
    assert.equal(pdf.subarray(0,5).toString(),'%PDF-');
    record('download backup/JSON/Markdown/PDF and compare actual contents');

    // Old structure payloads can preserve arbitrary custom IDs without v2 instances.
    const legacy = structuredClone(backup);
    const legacyKeys = new Set(['name','shape','color','diameter_cm','height_cm','length_cm','count']);
    legacy.structure = {parts:backup.structure.parts.map((part,index) => ({
      ...Object.fromEntries(Object.entries(part).filter(([name]) => legacyKeys.has(name))),
      part_id:index % 2 ? ['legacy','custom'] : {legacy:'custom'},
    }))};
    assert(legacy.structure.parts.length > 0);
    const legacyPath = path.join(output,'legacy-structure-custom-id-input.json');
    await fs.writeFile(legacyPath,JSON.stringify(legacy));
    const legacyContext = await context();
    const legacyPage = lastPage = await legacyContext.newPage();
    await legacyPage.goto(baseURL);
    const legacySidebar = legacyPage.locator('[data-testid="stSidebar"]');
    await key(legacySidebar,'open_backup_file').locator('input[type="file"]').setInputFiles(legacyPath);
    await clickKey(legacyPage,legacySidebar,'open_backup_apply');
    const legacyPanel = legacyPage.getByRole('tabpanel',{name:'照片分析（本地）',exact:true});
    const legacyId = await resultId(legacyPanel);
    const legacyExport = JSON.parse(await download(legacyPage,key(legacyPanel,`dl_backup_${legacyId}`)
      .getByRole('button'),path.join(output,'legacy-structure-custom-id-export.json')));
    assert.deepEqual(legacyExport.structure,legacy.structure);
    await legacyPage.screenshot({path:path.join(output,'legacy-structure-custom-id.png'),fullPage:true});
    record('legacy custom structure IDs survive import, rendering and backup export');
    lastPage = page;
    await legacyContext.close();

    // Unknown historical review markers must remain data, not affirmative claims.
    const uncertain = structuredClone(backup);
    uncertain.vision_meta = {...uncertain.vision_meta, reviewed_by_user:'false',
      requires_subject_review:false, subject_scope_review:'not_reviewed', review_head_box:{invalid:true}};
    const uncertainPath = path.join(output,'unrecognized-review-input.json');
    await fs.writeFile(uncertainPath,JSON.stringify(uncertain));
    const uncertainContext = await context();
    const uncertainPage = lastPage = await uncertainContext.newPage();
    await uncertainPage.goto(baseURL);
    const uncertainSidebar = uncertainPage.locator('[data-testid="stSidebar"]');
    await key(uncertainSidebar,'open_backup_file').locator('input[type="file"]').setInputFiles(uncertainPath);
    await clickKey(uncertainPage,uncertainSidebar,'open_backup_apply');
    const uncertainPanel = uncertainPage.getByRole('tabpanel',{name:'照片分析（本地）',exact:true});
    const uncertainId = await resultId(uncertainPanel);
    const reviewWarning = uncertainPanel.getByText('复核记录无法识别，请重新核对主体、头部与部件。',{exact:true});
    await expect(reviewWarning).toBeVisible();
    await expect(uncertainPanel.getByText('✓ 比例与部件已经过人工确认；原始解析来源保留如下。',
                                         {exact:true})).toHaveCount(0);
    const uncertainSources = uncertainPanel.locator('details').filter({hasText:'来源与限制'}).first();
    await uncertainSources.locator(':scope > summary').click();
    await settle(uncertainPage);
    await expect(uncertainPanel.getByText('头部框记录无效或与分段不一致，无法确认人工框选来源。',
                                         {exact:true})).toBeVisible();
    const uncertainMarkdown = await download(uncertainPage,key(uncertainPanel,`dl_md_${uncertainId}`)
      .getByRole('button'),path.join(output,'unrecognized-review.md'));
    assert(uncertainMarkdown.toString().includes('主体复核：记录无法识别'));
    assert(!uncertainMarkdown.toString().includes('主体复核：用户已确认'));
    const uncertainExport = JSON.parse(await download(uncertainPage,key(uncertainPanel,`dl_backup_${uncertainId}`)
      .getByRole('button'),path.join(output,'unrecognized-review-export.json')));
    assert.deepEqual(uncertainExport.vision_meta,uncertain.vision_meta);
    await reviewWarning.scrollIntoViewIfNeeded();
    await uncertainPage.screenshot({path:path.join(output,'unrecognized-review.png')});
    record('unrecognized review markers remain in backup without false confirmation');
    lastPage = page;
    await uncertainContext.close();

    await page.getByRole('tab',{name:'手动输入',exact:true}).click();
    const manual = page.getByRole('tabpanel',{name:'手动输入',exact:true});
    await clickKey(page,manual,'btn_manual');
    let manualId = await resultId(manual);
    await headProgress(page,manual,manualId,true);
    const headDetails = headCheck(manual,manualId).locator('xpath=ancestor::div[@data-testid="stExpanderDetails"]');
    await expect(headDetails.getByText('肤色（待选色）',{exact:false}).first()).toBeVisible();
    const manualMarkdown = await download(page,key(manual,`dl_md_${manualId}`).getByRole('button'),
      path.join(output,'manual-placeholder-colors.md'));
    assert(manualMarkdown.toString().includes('**颜色**：肤色（待选色）'));
    assert(manualMarkdown.toString().includes('**颜色**：主体色（待选色）'));
    const manualBackup = JSON.parse(await download(page,key(manual,`dl_backup_${manualId}`).getByRole('button'),
      path.join(output,'manual-placeholder-colors.json')));
    assert.equal(manualBackup.params.parts.find(p => p.name === '头部').color,'skin');
    assert.equal(manualBackup.params.parts.find(p => p.name === '身体').color,'body');
    record('placeholder colors are clear in the result and Markdown while backup values stay unchanged');
    const notes = 'browser-smoke: head R1 completed';
    await fillKey(page,manual,`project_notes_${manualId}`,notes);
    const material = manual.getByRole('button',{name:'更新材料估算',exact:true,includeHidden:true});
    await reveal(material);await material.click();await settle(page);
    manualId = await resultId(manual,manualId);
    const storedId = manualId;
    const title = `browser-smoke-${Date.now()}`;
    await fillKey(page,manual,`hist_title_${manualId}`,title);
    await clickKey(page,manual,`hist_save_${manualId}`);
    const sidebar = page.locator('[data-testid="stSidebar"]');
    await fillKey(page,sidebar,'hist_search',title);
    await expect(key(sidebar,`hist_load_${storedId}`),'Saved title must be searchable before undo.').toHaveCount(1);
    await clickKey(page,manual,`edit_${manualId}_undo`);
    manualId = await resultId(manual,manualId);
    await clickKey(page,manual,`hist_save_${manualId}`);
    await fillKey(page,sidebar,'hist_search',title);
    await expect(sidebar.locator('[class*="st-key-hist_load_"]')).toHaveCount(1);
    await expect(key(sidebar,`hist_load_${storedId}`)).toHaveCount(1);
    record('first history save, undo and save keep the same stored record');

    await clickKey(page,manual,`project_save_${manualId}`);
    const dialog = page.getByRole('dialog');
    const projectFile = path.join(output,'crochet-project.json');
    const project = JSON.parse(await download(page,dialog.getByRole('button',{name:'下载工程 JSON',exact:true}),projectFile));
    assert.equal(project.project_state.notes,notes);
    assert.equal(Object.keys(project.project_state.completed_rounds).length,1);
    await dialog.getByRole('button',{name:'Close',exact:true}).click();
    await settle(page);
    record('project download contains the current progress and personal notes');

    await clickKey(page,sidebar,`hist_load_${storedId}`);
    await page.getByRole('tab',{name:'照片分析（本地）',exact:true}).click();
    photoId = await resultId(photoPanel,photoId);
    assert.notEqual(photoId,manualId);
    await headProgress(page,photoPanel,photoId,true);
    const clearPhoto = key(photoPanel,`sheet_part_${photoId}_0`).getByRole('button',{name:'重置进度',exact:true,includeHidden:true});
    await reveal(clearPhoto);await clearPhoto.click();await settle(page);
    await fillKey(page,photoPanel,`project_notes_${photoId}`,'photo workspace note');
    await page.getByRole('tab',{name:'手动输入',exact:true}).click();
    await expect(headCheck(manual,manualId)).toBeChecked();
    await expect(key(manual,`project_notes_${manualId}`).locator('textarea')).toHaveValue(notes);
    await page.screenshot({path:path.join(output,'history-isolation.png'),fullPage:true});
    record('manual-to-photo history load keeps two pages progress/notes isolated');

    const freshContext = await context();
    const fresh = lastPage = await freshContext.newPage();
    await fresh.goto(baseURL);
    const freshSidebar = fresh.locator('[data-testid="stSidebar"]');
    const uploader = key(freshSidebar,'open_backup_file').locator('input[type="file"]');
    await uploader.setInputFiles(projectFile);
    await clickKey(fresh,freshSidebar,'open_backup_apply');
    const restored = fresh.getByRole('tabpanel',{name:'照片分析（本地）',exact:true});
    const restoredId = await resultId(restored);
    const restoredNotes = key(restored,`project_notes_${restoredId}`).locator('textarea');
    await reveal(restoredNotes);
    await expect(restoredNotes).toHaveValue(notes,{timeout:15000});
    await expect(headCheck(restored,restoredId)).toBeChecked();
    await clickKey(fresh,restored,`project_save_${restoredId}`);
    const restoredProject = JSON.parse(await download(fresh,fresh.getByRole('dialog').getByRole('button',{name:'下载工程 JSON',exact:true}),path.join(output,'restored-project.json')));
    assert.deepEqual(restoredProject.project_state.completed_rounds,project.project_state.completed_rounds);
    assert.equal(restoredProject.project_state.notes,notes);
    assert.deepEqual(restoredProject.params,project.params);
    await fresh.getByRole('dialog').getByRole('button',{name:'Close',exact:true}).click();
    await settle(fresh);
    await fresh.screenshot({path:path.join(output,'project-restored.png'),fullPage:true});
    record('fresh browser context restores project, then re-exports identical work');

    await uploader.setInputFiles({name:'broken.json',mimeType:'application/json',buffer:Buffer.from('{broken')});
    await expect(freshSidebar.getByText('broken.json',{exact:true})).toBeVisible({timeout:45000});
    await settle(fresh);
    await clickKey(fresh,freshSidebar,'open_backup_apply');
    await expect(freshSidebar).toContainText('导入失败',{timeout:45000});
    assert.equal(await resultId(restored),restoredId);
    await expect(restoredNotes).toHaveValue(notes);
    await expect(headCheck(restored,restoredId)).toBeChecked();
    record('invalid import preserves the active project, progress and notes');

    const openControl = key(restored,`edit_${restoredId}_head_open`).locator('input');
    await reveal(openControl);
    await openControl.locator('xpath=ancestor::label').click();
    await settle(fresh);
    await fillKey(fresh,restored,`edit_${restoredId}_head_open_stitches`,'16');
    await clickKey(fresh,restored,`edit_${restoredId}_head_open_preview`);
    assert.equal(await resultId(restored),restoredId);
    const beforeOpen = JSON.parse(await download(fresh,key(restored,`dl_backup_${restoredId}`).getByRole('button'),path.join(output,'before-open.json')));
    assert.equal(beforeOpen.params.head_opening_stitches,undefined);
    await clickKey(fresh,restored,`edit_${restoredId}_preview_apply`);
    const openId = await resultId(restored,restoredId);
    const openBackup = JSON.parse(await download(fresh,key(restored,`dl_backup_${openId}`).getByRole('button'),path.join(output,'open-head-backup.json')));
    assert.equal(openBackup.params.head_opening_stitches,16);
    const openHead = openBackup.params.parts.find(p=>p.name==='头部');
    assert.equal(openHead.rounds.at(-1).stitches,16);
    assert.equal(openHead.opening_row,openHead.rounds.at(-1).row);
    await expect(headCheck(restored,openId)).not.toBeChecked();
    await clickKey(fresh,restored,`project_save_${openId}`);
    const openProjectFile = path.join(output,'open-head-project.json');
    await download(fresh,fresh.getByRole('dialog').getByRole('button',{name:'下载工程 JSON',exact:true}),openProjectFile);
    await fresh.getByRole('dialog').getByRole('button',{name:'Close',exact:true}).click();
    await settle(fresh);
    const openContext = await context();
    const reopened = lastPage = await openContext.newPage();
    await reopened.goto(baseURL);
    const openSidebar = reopened.locator('[data-testid="stSidebar"]');
    await key(openSidebar,'open_backup_file').locator('input[type="file"]').setInputFiles(openProjectFile);
    await clickKey(reopened,openSidebar,'open_backup_apply');
    const openPanel = reopened.getByRole('tabpanel',{name:'照片分析（本地）',exact:true});
    const reopenedId = await resultId(openPanel);
    const savedOpen = key(openPanel,`edit_${reopenedId}_head_open`).locator('input');
    await reveal(savedOpen);
    await expect(savedOpen).toBeChecked();
    await expect(key(openPanel,`edit_${reopenedId}_head_open_stitches`).locator('input')).toHaveValue('16');
    const reopenedNotes = key(openPanel,`project_notes_${reopenedId}`).locator('textarea');
    await reveal(reopenedNotes);
    await expect(reopenedNotes).toHaveValue(notes,{timeout:15000});
    await reopened.screenshot({path:path.join(output,'open-head-restored.png'),fullPage:true});
    await savedOpen.locator('xpath=ancestor::label').click();
    await settle(reopened);
    await clickKey(reopened,openPanel,`edit_${reopenedId}_head_open_preview`);
    await clickKey(reopened,openPanel,`edit_${reopenedId}_preview_apply`);
    const closedId = await resultId(openPanel,reopenedId);
    const closed = JSON.parse(await download(reopened,key(openPanel,`dl_backup_${closedId}`).getByRole('button'),path.join(output,'closed-head-backup.json')));
    assert.equal(closed.params.head_opening_stitches,undefined);
    const closedHead = closed.params.parts.find(p=>p.name==='头部');
    assert.equal(closedHead.rounds.at(-1).stitches,6);
    assert(closedHead.rounds.at(-1).notes.includes('无痕收口'));
    record('preview exact 16-stitch head opening, restore project in new context, then close again');

    const garmentInput = path.join(output,'garment-input.json');
    execFileSync(path.join(__dirname,'../.venv/bin/python'),[
      '-m','app.cli','--parts','头部,身体,手臂,帽子,裙子','--head','5.7','--height','36',
      '--gauge','custom','--stitches','30','--rows','32','--out',garmentInput,'--quiet',
    ],{cwd:path.join(__dirname,'..')});
    const garmentSource = JSON.parse(await fs.readFile(garmentInput));
    const garmentContext = await context();
    const garmentPage = lastPage = await garmentContext.newPage();
    await garmentPage.goto(baseURL);
    const garmentSidebar = garmentPage.locator('[data-testid="stSidebar"]');
    await key(garmentSidebar,'open_backup_file').locator('input[type="file"]').setInputFiles(garmentInput);
    await clickKey(garmentPage,garmentSidebar,'open_backup_apply');
    const garmentPanel = garmentPage.getByRole('tabpanel',{name:'照片分析（本地）',exact:true});
    const garmentId = await resultId(garmentPanel);
    await headProgress(garmentPage,garmentPanel,garmentId,true);
    const hatIndex = garmentSource.params.parts.findIndex(p=>p.name==='帽子');
    const hatCheck = key(garmentPanel,`sheet_part_${garmentId}_${hatIndex}`).locator('input[type="checkbox"]').first();
    await reveal(hatCheck);
    await hatCheck.locator('xpath=ancestor::label').click();
    await settle(garmentPage);
    const garmentPrefix = `edit_${garmentId}_partgauge0`;
    const independent = key(garmentPanel,`${garmentPrefix}_enabled`).locator('input');
    await reveal(independent);
    await independent.locator('xpath=ancestor::label').click();
    await settle(garmentPage);
    await fillKey(garmentPage,garmentPanel,`${garmentPrefix}_stitches`,'26');
    await fillKey(garmentPage,garmentPanel,`${garmentPrefix}_rows`,'28');
    await clickKey(garmentPage,garmentPanel,`${garmentPrefix}_preview`);
    assert.equal(await resultId(garmentPanel),garmentId);
    await clickKey(garmentPage,garmentPanel,`edit_${garmentId}_preview_apply`);
    const mixedId = await resultId(garmentPanel,garmentId);
    const mixed = JSON.parse(await download(garmentPage,key(garmentPanel,`dl_backup_${mixedId}`).getByRole('button'),path.join(output,'garment-mixed.json')));
    const hat = mixed.params.parts.find(p=>p.name==='帽子');
    assert.deepEqual(mixed.params.gauge,{stitches_per_10cm:30,rows_per_10cm:32});
    assert.deepEqual(hat.gauge,{stitches_per_10cm:26,rows_per_10cm:28});
    assert.equal(Math.max(...hat.rounds.map(r=>r.stitches)),54);
    for(const original of garmentSource.params.parts.filter(p=>p.name!=='帽子')) {
      assert.deepEqual(mixed.params.parts.find(p=>p.name===original.name).rounds,original.rounds);
    }
    await expect(headCheck(garmentPanel,mixedId)).toBeChecked();
    await expect(key(garmentPanel,`sheet_part_${mixedId}_${hatIndex}`).locator('input[type="checkbox"]').first()).not.toBeChecked();
    await expect(garmentPanel.getByRole('button',{name:'以当前图解新建试钩',exact:true,includeHidden:true})).toBeDisabled();
    await clickKey(garmentPage,garmentPanel,`project_save_${mixedId}`);
    const mixedProjectFile = path.join(output,'garment-project.json');
    await download(garmentPage,garmentPage.getByRole('dialog').getByRole('button',{name:'下载工程 JSON',exact:true}),mixedProjectFile);
    const mixedContext = await context();
    const mixedPage = lastPage = await mixedContext.newPage();
    await mixedPage.goto(baseURL);
    const mixedSidebar = mixedPage.locator('[data-testid="stSidebar"]');
    await key(mixedSidebar,'open_backup_file').locator('input[type="file"]').setInputFiles(mixedProjectFile);
    await clickKey(mixedPage,mixedSidebar,'open_backup_apply');
    const mixedPanel = mixedPage.getByRole('tabpanel',{name:'照片分析（本地）',exact:true});
    const recoveredId = await resultId(mixedPanel);
    const recoveredGauge = key(mixedPanel,`edit_${recoveredId}_partgauge0_enabled`).locator('input');
    await reveal(recoveredGauge);
    await expect(recoveredGauge).toBeChecked();
    await expect(key(mixedPanel,`edit_${recoveredId}_partgauge0_stitches`).locator('input')).toHaveValue(/^26(?:\.0+)?$/);
    await expect(key(mixedPanel,`edit_${recoveredId}_partgauge0_rows`).locator('input')).toHaveValue(/^28(?:\.0+)?$/);
    await expect(headCheck(mixedPanel,recoveredId)).toBeChecked();
    await mixedPage.screenshot({path:path.join(output,'garment-gauge-restored.png'),fullPage:true});
    record('independent 26x28 hat with 30x32 body, unchanged work, trial gate and fresh project recovery');

    // Bind a weighed sample at 30×32, then change only default gauge via a saved trial.
    await fillKey(mixedPage,mixedPanel,`edit_${recoveredId}_partgauge0_stitches`,'30');
    await fillKey(mixedPage,mixedPanel,`edit_${recoveredId}_partgauge0_rows`,'32');
    await clickKey(mixedPage,mixedPanel,`edit_${recoveredId}_partgauge0_preview`);
    await clickKey(mixedPage,mixedPanel,`edit_${recoveredId}_preview_apply`);
    const uniformId = await resultId(mixedPanel,recoveredId);
    const weighed = key(mixedPanel,`edit_${uniformId}_measured`).locator('input');
    await reveal(weighed);
    await weighed.locator('xpath=ancestor::label').click();
    await fillKey(mixedPage,mixedPanel,`edit_${uniformId}_swatchweight`,'5');
    await fillKey(mixedPage,mixedPanel,`edit_${uniformId}_swatchst`,'10');
    await fillKey(mixedPage,mixedPanel,`edit_${uniformId}_swatchrows`,'10');
    await mixedPanel.getByRole('button',{name:'更新材料估算',exact:true}).click();
    await settle(mixedPage);
    const weighedId = await resultId(mixedPanel,uniformId);
    const weighedHatCheck = key(mixedPanel,`sheet_part_${weighedId}_${hatIndex}`).locator('input[type="checkbox"]').first();
    await reveal(weighedHatCheck);
    await weighedHatCheck.locator('xpath=ancestor::label').click();
    await settle(mixedPage);
    const sampleSource = JSON.parse(await download(mixedPage,key(mixedPanel,`dl_backup_${weighedId}`).getByRole('button'),path.join(output,'swatch-source.json')));
    assert.deepEqual(sampleSource.params.yarn_spec.swatch_gauge,{stitches_per_10cm:30,rows_per_10cm:32});
    await fillKey(mixedPage,mixedPanel,'trial_id_result','synthetic-browser-swatch');
    await fillKey(mixedPage,mixedPanel,'trial_maker_result','synthetic');
    await mixedPanel.getByRole('button',{name:'以当前图解新建试钩',exact:true}).click();
    await settle(mixedPage);
    const savedSample = mixedPanel.locator('[class*="st-key-trial_fields_result_"][class*="_measured"]').first();
    await reveal(savedSample);
    const samplePrefix = await savedSample.evaluate(el=>[...el.classList].find(c=>c.startsWith('st-key-trial_fields_result_')).slice('st-key-'.length).replace(/measured$/,''));
    await savedSample.locator('input').locator('xpath=ancestor::label').click();
    await fillKey(mixedPage,mixedPanel,`${samplePrefix}stitches_per_10cm`,'26');
    await fillKey(mixedPage,mixedPanel,`${samplePrefix}rows_per_10cm`,'28');
    await mixedPanel.getByRole('button',{name:'保存记录并更新下载',exact:true}).click();
    await settle(mixedPage);
    await clickKey(mixedPage,mixedPanel,'trial_gauge_preview_result');
    await clickKey(mixedPage,mixedPanel,`edit_${weighedId}_preview_apply`);
    const adjustedId = await resultId(mixedPanel,weighedId);
    const adjusted = JSON.parse(await download(mixedPage,key(mixedPanel,`dl_backup_${adjustedId}`).getByRole('button'),path.join(output,'swatch-adjusted.json')));
    assert.deepEqual(adjusted.params.gauge,{stitches_per_10cm:26,rows_per_10cm:28});
    assert.deepEqual(adjusted.params.yarn_spec.swatch_gauge,sampleSource.params.yarn_spec.swatch_gauge);
    const fixedHat = adjusted.params.parts.find(p=>p.name==='帽子');
    assert.deepEqual(fixedHat,sampleSource.params.parts.find(p=>p.name==='帽子'));
    const fixedHatCount = fixedHat.quantity*fixedHat.rounds.reduce((sum,r)=>sum+r.stitches,0);
    const heuristicRate = .08*(10/26)*(10/28)/(.785*.625);
    const expectedGrams = (fixedHatCount*.05+(adjusted.params.total_stitches-fixedHatCount)*heuristicRate)*1.1;
    assert(Math.abs(adjusted.params.material_summary.grams-expectedGrams)<.03);
    assert.equal(adjusted.params.material_summary.basis,'mixed_swatch_and_heuristic');
    await expect(headCheck(mixedPanel,adjustedId)).not.toBeChecked();
    await expect(key(mixedPanel,`sheet_part_${adjustedId}_${hatIndex}`).locator('input[type="checkbox"]').first()).toBeChecked();
    await clickKey(mixedPage,mixedPanel,`project_save_${adjustedId}`);
    const sampleProject = path.join(output,'swatch-project.json');
    await download(mixedPage,mixedPage.getByRole('dialog').getByRole('button',{name:'下载工程 JSON',exact:true}),sampleProject);
    const sampleContext = await context();
    const samplePage = lastPage = await sampleContext.newPage();
    await samplePage.goto(baseURL);
    const sampleSidebar = samplePage.locator('[data-testid="stSidebar"]');
    await key(sampleSidebar,'open_backup_file').locator('input[type="file"]').setInputFiles(sampleProject);
    await clickKey(samplePage,sampleSidebar,'open_backup_apply');
    const samplePanel = samplePage.getByRole('tabpanel',{name:'照片分析（本地）',exact:true});
    const sampleId = await resultId(samplePanel);
    const recoveredSample = JSON.parse(await download(samplePage,key(samplePanel,`dl_backup_${sampleId}`).getByRole('button'),path.join(output,'swatch-restored.json')));
    assert.deepEqual(recoveredSample.params.yarn_spec,adjusted.params.yarn_spec);
    assert.deepEqual(recoveredSample.params.material_summary,adjusted.params.material_summary);
    await expect(key(samplePanel,`sheet_part_${sampleId}_${hatIndex}`).locator('input[type="checkbox"]').first()).toBeChecked();
    const recoveredOrigin = key(samplePanel,`edit_${sampleId}_swatchgauge_stitches`).locator('input');
    await reveal(recoveredOrigin);
    await expect(recoveredOrigin).toHaveValue(/^30(?:\.0+)?$/);
    await samplePage.screenshot({path:path.join(output,'swatch-origin-restored.png'),fullPage:true});
    record('weighed 30x32 sample stays bound after trial default changes to 26x28, with fixed hat and fresh recovery');

    await fillKey(samplePage,samplePanel,`project_notes_${sampleId}`,'Review labels before buying yarn');
    await fillKey(samplePage,samplePanel,`edit_${sampleId}_weight`,'60');
    await fillKey(samplePage,samplePanel,`edit_${sampleId}_length`,'150');
    await samplePanel.getByRole('button',{name:'预览材料估算修改',exact:true}).click();
    await settle(samplePage);
    await expect(samplePanel.getByText('线标（每团）',{exact:true})).toBeVisible();
    assert.equal(await resultId(samplePanel),sampleId);
    const previewUnchanged = JSON.parse(await download(samplePage,key(samplePanel,`dl_backup_${sampleId}`).getByRole('button'),path.join(output,'material-preview-before.json')));
    assert.deepEqual(previewUnchanged.params,recoveredSample.params);
    await clickKey(samplePage,samplePanel,`edit_${sampleId}_preview_cancel`);
    assert.equal(await resultId(samplePanel),sampleId);
    await samplePanel.getByRole('button',{name:'预览材料估算修改',exact:true}).click();
    await settle(samplePage);
    await clickKey(samplePage,samplePanel,`edit_${sampleId}_preview_apply`);
    const materialId = await resultId(samplePanel,sampleId);
    const appliedMaterials = JSON.parse(await download(samplePage,key(samplePanel,`dl_backup_${materialId}`).getByRole('button'),path.join(output,'material-applied.json')));
    assert.equal(appliedMaterials.params.yarn_spec.ball_weight_g,60);
    assert.equal(appliedMaterials.params.yarn_spec.ball_length_m,150);
    assert.deepEqual(appliedMaterials.params.parts,recoveredSample.params.parts);
    assert.deepEqual(appliedMaterials.params.yarn_spec.swatch_gauge,recoveredSample.params.yarn_spec.swatch_gauge);
    await clickKey(samplePage,samplePanel,`edit_${materialId}_undo`);
    const materialUndoId = await resultId(samplePanel,materialId);
    await expect(key(samplePanel,`edit_${materialUndoId}_redo`).getByRole('button')).toBeEnabled();
    const unchangedSubmit = samplePanel.getByRole('button',{name:'更新材料估算',exact:true});
    await reveal(unchangedSubmit);
    await unchangedSubmit.click();
    await settle(samplePage);
    await expect(samplePanel.getByText('设置与当前图解相同，已保留撤销、重做及完成进度。',{exact:true})).toBeVisible();
    assert.equal(await resultId(samplePanel),materialUndoId);
    await expect(key(samplePanel,`edit_${materialUndoId}_redo`).getByRole('button')).toBeEnabled();
    // Force a fresh rerun so the next identical notice acknowledges the size action.
    await fillKey(samplePage,samplePanel,`project_notes_${materialUndoId}`,'Review labels and unchanged sizes');
    const unchangedNotice = samplePanel.getByText('设置与当前图解相同，已保留撤销、重做及完成进度。',{exact:true});
    await expect(unchangedNotice).toHaveCount(0);
    await clickKey(samplePage,samplePanel,`sz_go_${materialUndoId}`);
    await expect(unchangedNotice).toBeVisible();
    assert.equal(await resultId(samplePanel),materialUndoId);
    await expect(key(samplePanel,`edit_${materialUndoId}_redo`).getByRole('button')).toBeEnabled();
    await expect(samplePanel.getByText('✅ 已按新尺寸重新生成图解（配色与塑形选项保持不变）！',{exact:true})).toHaveCount(0);
    const sizeUnchanged = JSON.parse(await download(samplePage,key(samplePanel,`dl_backup_${materialUndoId}`).getByRole('button'),path.join(output,'unchanged-size.json')));
    assert.deepEqual(sizeUnchanged.sizing,recoveredSample.sizing);
    assert.deepEqual(sizeUnchanged.params,recoveredSample.params);
    await clickKey(samplePage,samplePanel,`edit_${materialUndoId}_redo`);
    const materialRedoId = await resultId(samplePanel,materialUndoId);
    const materialRedone = JSON.parse(await download(samplePage,key(samplePanel,`dl_backup_${materialRedoId}`).getByRole('button'),path.join(output,'material-redone.json')));
    assert.deepEqual(materialRedone.params,appliedMaterials.params);
    await expect(key(samplePanel,`sheet_part_${materialRedoId}_${hatIndex}`).locator('input[type="checkbox"]').first()).toBeChecked();
    const keptNotes = key(samplePanel,`project_notes_${materialRedoId}`).locator('textarea');
    await reveal(keptNotes);
    await expect(keptNotes).toHaveValue('Review labels and unchanged sizes');
    await samplePage.screenshot({path:path.join(output,'material-preview-redo.png'),fullPage:true});
    record('material preview/cancel/apply and unchanged material/size after undo retain redo, provenance, notes and progress');

    // Chapter 5: both raw JSON editors share one panel that starts collapsed; the
    // downloads stay outside it and keep serving the applied pattern while a draft
    // is pending; the draft itself survives a full rerun started elsewhere.
    await samplePanel.locator('h2.sheet-h',{hasText:'局部修正'}).scrollIntoViewIfNeeded();
    await samplePage.screenshot({path:path.join(output,'local-corrections-collapsed.png')});
    const advancedPanel = samplePanel.locator('details').filter({hasText:'高级编辑（JSON）'}).first();
    await expect(advancedPanel.locator(':scope > summary')).toContainText('高级编辑（JSON）');
    assert.equal(await advancedPanel.getAttribute('open'),null,'The advanced JSON panel must start collapsed.');
    // 2026-11-05 mount latch: no editor textareas exist until the enable button
    // is clicked; the click mounts both editors in the same run.
    await advancedPanel.locator(':scope > summary').click();
    await settle(samplePage);
    await expect(advancedPanel.locator('textarea')).toHaveCount(0);
    record('advanced JSON editors stay unmounted until the enable button is clicked');
    await clickKey(samplePage,samplePanel,`json_open_${materialRedoId}`);
    await expect(advancedPanel.locator('textarea')).toHaveCount(2);
    const jsonArea = key(samplePanel,`json_edit_${materialRedoId}`).locator('textarea');
    for (const name of [`dl_backup_${materialRedoId}`,`dl_json_${materialRedoId}`,`dl_md_${materialRedoId}`]) {
      assert.equal(await key(samplePanel,name).locator('xpath=ancestor::details').count(),0,
                   `${name} must stay outside every collapsible panel.`);
    }
    const appliedParams = JSON.parse(await jsonArea.inputValue());
    const draft = structuredClone(appliedParams);
    draft.parts[0].rounds[0].notes += '；核对张力';
    const draftText = JSON.stringify(draft);
    await fillKey(samplePage,samplePanel,`json_edit_${materialRedoId}`,draftText);
    const draftNotice = samplePanel.getByText(/JSON 草稿/);
    await expect(draftNotice).toHaveCount(2);
    await samplePage.screenshot({path:path.join(output,'local-corrections-advanced.png')});
    await clickKey(samplePage,samplePanel,`edit_${materialRedoId}_size_preview`);
    await expect(samplePanel.getByText('修改影响预览 · 尚未应用',{exact:true})).toBeVisible();
    await expect(jsonArea).toHaveValue(draftText);
    await clickKey(samplePage,samplePanel,`edit_${materialRedoId}_preview_cancel`);
    assert.equal(await resultId(samplePanel),materialRedoId);
    await expect(jsonArea).toHaveValue(draftText);
    await expect(draftNotice).toHaveCount(2);
    const pendingDownload = JSON.parse(await download(samplePage,key(samplePanel,`dl_json_${materialRedoId}`).getByRole('button'),path.join(output,'draft-pending-download.json')));
    assert.deepEqual(pendingDownload,appliedParams);
    await clickKey(samplePage,samplePanel,`regen_${materialRedoId}`);
    const draftId = await resultId(samplePanel,materialRedoId);
    await expect(samplePanel.getByText(/已根据修正更新图解/)).toBeVisible();
    await expect(samplePanel.getByText(/JSON 草稿/)).toHaveCount(0);
    const appliedDraft = JSON.parse(await download(samplePage,key(samplePanel,`dl_json_${draftId}`).getByRole('button'),path.join(output,'draft-applied-download.json')));
    assert.equal(appliedDraft.parts[0].rounds[0].notes,draft.parts[0].rounds[0].notes);
    record('advanced JSON panel starts collapsed, keeps a draft through preview and cancel, and downloads stay applied until regeneration');

    // Part-level colour selection: preview lists the affected rounds and the
    // "yarn already worked keeps its colour" notice, cancel is read-only, and
    // apply/undo/redo keep the stitches and the completed rounds.
    {
      const colorPanel = samplePanel;
      // appliedDraft is the params object downloaded from the JSON editor.
      const headIndex = appliedDraft.parts.findIndex(part=>part.name==='头部');
      const armIndex = appliedDraft.parts.findIndex(part=>part.name==='手臂');
      assert(headIndex >= 0 && armIndex >= 0, 'the synthetic pattern should carry a head and an arm part');
      await colorPanel.locator('h2.sheet-h',{hasText:'局部修正'}).scrollIntoViewIfNeeded();
      await headProgress(samplePage,colorPanel,draftId,true);
      await clickKey(samplePage,colorPanel,`edit_${draftId}_color${headIndex}_preview`);
      await expect(colorPanel.getByText('修改影响预览 · 尚未应用',{exact:true})).toBeVisible();
      await expect(colorPanel.getByText('受影响的圈次（旧色 → 新色）',{exact:true})).toBeVisible();
      await expect(colorPanel.getByText(/已钩出的旧颜色不会因为图解改色而改变/).first()).toBeVisible();
      assert.equal(await resultId(colorPanel),draftId);
      const colorPreview = JSON.parse(await download(samplePage,key(colorPanel,`dl_backup_${draftId}`).getByRole('button'),path.join(output,'color-preview-before.json')));
      assert.deepEqual(colorPreview.params,appliedDraft);
      await samplePage.screenshot({path:path.join(output,'color-preview.png'),fullPage:true});
      await clickKey(samplePage,colorPanel,`edit_${draftId}_preview_cancel`);
      assert.equal(await resultId(colorPanel),draftId);
      assert.deepEqual(JSON.parse(await download(samplePage,key(colorPanel,`dl_json_${draftId}`).getByRole('button'),path.join(output,'color-cancel.json'))),appliedDraft);

      await clickKey(samplePage,colorPanel,`edit_${draftId}_color${headIndex}_preview`);
      await clickKey(samplePage,colorPanel,`edit_${draftId}_preview_apply`);
      const colorId = await resultId(colorPanel,draftId);
      const coloured = JSON.parse(await download(samplePage,key(colorPanel,`dl_backup_${colorId}`).getByRole('button'),path.join(output,'color-applied.json')));
      const colouredHead = coloured.params.parts[headIndex];
      assert.equal(colouredHead.color_origin,'manual');
      assert.notEqual(colouredHead.color,appliedDraft.parts[headIndex].color);
      assert.deepEqual(coloured.params.parts.map(part=>part.rounds.map(round=>round.stitches)),
                       appliedDraft.parts.map(part=>part.rounds.map(round=>round.stitches)));
      assert(JSON.stringify(coloured).includes('"color_origin"'));
      await expect(headCheck(colorPanel,colorId)).toBeChecked();
      await samplePage.screenshot({path:path.join(output,'color-applied.png'),fullPage:true});

      await clickKey(samplePage,colorPanel,`edit_${colorId}_undo`);
      const colorUndoId = await resultId(colorPanel,colorId);
      const colourUndone = JSON.parse(await download(samplePage,key(colorPanel,`dl_backup_${colorUndoId}`).getByRole('button'),path.join(output,'color-undo.json')));
      assert.deepEqual(colourUndone.params,appliedDraft);
      await clickKey(samplePage,colorPanel,`edit_${colorUndoId}_redo`);
      const colorRedoId = await resultId(colorPanel,colorUndoId);
      const colourRedone = JSON.parse(await download(samplePage,key(colorPanel,`dl_backup_${colorRedoId}`).getByRole('button'),path.join(output,'color-redo.json')));
      assert.deepEqual(colourRedone.params,coloured.params);
      await expect(headCheck(colorPanel,colorRedoId)).toBeChecked();
      record('colour panel previews the affected rounds and the worked-yarn notice, cancel is read-only, and apply/undo/redo keep stitches and completed rounds');

      // Per-copy colour: applied through the JSON editor so the flow reuses existing
      // idioms, then verified in Markdown, the DSL download and a backup restore.
      const perCopy = structuredClone(colourRedone.params);
      const armPart = perCopy.parts[armIndex];
      assert(armPart.quantity >= 2, 'the synthetic pattern should carry a paired arm part');
      armPart.instance_colors = ['蓝色',...Array(armPart.quantity-1).fill(null)];
      await fillKey(samplePage,colorPanel,`json_edit_${colorRedoId}`,JSON.stringify(perCopy));
      await clickKey(samplePage,colorPanel,`regen_${colorRedoId}`);
      const perCopyId = await resultId(colorPanel,colorRedoId);
      const perCopyFile = path.join(output,'color-per-copy.json');
      const perCopyBackup = JSON.parse(await download(samplePage,key(colorPanel,`dl_backup_${perCopyId}`).getByRole('button'),perCopyFile));
      assert.deepEqual(perCopyBackup.params.parts[armIndex].instance_colors,armPart.instance_colors);
      const colourMarkdown = (await download(samplePage,key(colorPanel,`dl_md_${perCopyId}`).getByRole('button'),path.join(output,'color-per-copy.md'))).toString();
      assert(colourMarkdown.includes('逐份配色') && colourMarkdown.includes('同针法部件') && colourMarkdown.includes('蓝色'));
      // The per-copy DSL text is asserted in tests/test_part_color_selection.py
      // (test_instance_colour_reaches_markdown_pdf_and_the_dsl); this flow keeps to
      // the panel, its exports that the brief lists, and the round-trip.
      await samplePage.screenshot({path:path.join(output,'color-per-copy.png'),fullPage:true});

      // A project file carries progress as well as the pattern, so restoring it
      // also proves the new colour fields survive the round-trip.
      await clickKey(samplePage,colorPanel,`project_save_${perCopyId}`);
      const colourProject = path.join(output,'color-project.json');
      await download(samplePage,samplePage.getByRole('dialog').getByRole('button',{name:'下载工程 JSON',exact:true}),colourProject);
      const colourContext = await context();
      const colourPage = lastPage = await colourContext.newPage();
      await colourPage.goto(baseURL);
      const colourSidebar = colourPage.locator('[data-testid="stSidebar"]');
      await key(colourSidebar,'open_backup_file').locator('input[type="file"]').setInputFiles(colourProject);
      await clickKey(colourPage,colourSidebar,'open_backup_apply');
      const colourRestorePanel = colourPage.getByRole('tabpanel',{name:'照片分析（本地）',exact:true});
      const colourRestoreId = await resultId(colourRestorePanel);
      const colourRestored = JSON.parse(await download(colourPage,key(colourRestorePanel,`dl_backup_${colourRestoreId}`).getByRole('button'),path.join(output,'color-restored.json')));
      assert.deepEqual(colourRestored.params.parts[armIndex].instance_colors,armPart.instance_colors);
      assert.equal(colourRestored.params.parts[headIndex].color_origin,'manual');
      await expect(headCheck(colourRestorePanel,colourRestoreId)).toBeChecked();
      await colourContext.close();
      lastPage = page;
      record('per-copy colour reaches the Markdown export and survives a project restore with progress');

      // The panel must stay usable on a phone: no horizontal page overflow.
      const narrowContext = await context({width:390,height:844});
      const narrowPage = lastPage = await narrowContext.newPage();
      await narrowPage.goto(baseURL);
      await narrowPage.getByRole('button',{name:'Expand sidebar',exact:true}).click();
      const narrowSidebar = narrowPage.locator('[data-testid="stSidebar"]');
      await key(narrowSidebar,'open_backup_file').locator('input[type="file"]').setInputFiles(perCopyFile);
      await clickKey(narrowPage,narrowSidebar,'open_backup_apply');
      const narrowPanel = narrowPage.getByRole('tabpanel',{name:'照片分析（本地）',exact:true});
      const narrowId = await resultId(narrowPanel);
      // The drawer has to be closed again before touching the main column: an open
      // drawer overlays tap targets on a phone-sized viewport.
      await narrowPage.locator('[data-testid="stSidebarCollapseButton"]').click();
      await settle(narrowPage);
      const narrowPart = key(narrowPanel,`edit_${narrowId}_color_part`);
      await reveal(narrowPart);
      await narrowPart.scrollIntoViewIfNeeded();
      await expect(narrowPart).toBeVisible();
      const overflow = await narrowPage.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth);
      assert(overflow <= 1,`the colour panel must not overflow a 390 px viewport (overflow ${overflow}px)`);
      await narrowPage.screenshot({path:path.join(output,'color-narrow.png'),fullPage:true});
      await narrowContext.close();
      lastPage = page;
      record('colour panel renders inside a 390 px viewport without horizontal overflow');

      // Custom name plus a display hex. The picker is a screen swatch, not a yarn code.
      // Undo, redo and a fresh project restore must keep the name and the hex together.
      // The project-save dialog from the previous flow stays open on this page.
      const leftoverDialog = samplePage.getByTestId('stDialog');
      if (await leftoverDialog.count()) {
        await leftoverDialog.getByRole('button', {name: 'Close', exact: true}).click();
        await settle(samplePage);
      }
      await colorPanel.locator('h2.sheet-h',{hasText:'局部修正'}).scrollIntoViewIfNeeded();
      await chooseSelect(samplePage, colorPanel, `edit_${perCopyId}_color${headIndex}_pick`, '自定义颜色名…');
      await fillKey(samplePage, colorPanel, `edit_${perCopyId}_color${headIndex}_custom`, '外婆家的藏青');
      await setSwatch(samplePage, colorPanel, `edit_${perCopyId}_color${headIndex}_swatch`, '#26374a');
      await clickKey(samplePage, colorPanel, `edit_${perCopyId}_color${headIndex}_preview`);
      await expect(colorPanel.getByText('修改影响预览 · 尚未应用',{exact:true})).toBeVisible();
      await clickKey(samplePage, colorPanel, `edit_${perCopyId}_preview_apply`);
      const swatchId = await resultId(colorPanel, perCopyId);
      const swatchBackup = JSON.parse(await download(samplePage, key(colorPanel, `dl_backup_${swatchId}`).getByRole('button'), path.join(output, 'color-swatch.json')));
      assert.equal(swatchBackup.params.display_colors['外婆家的藏青'], '#26374a');
      assert.equal(swatchBackup.params.parts[headIndex].color, '外婆家的藏青');
      assert.deepEqual(swatchBackup.params.parts.map(part => part.rounds.map(round => round.stitches)),
                       perCopyBackup.params.parts.map(part => part.rounds.map(round => round.stitches)));
      const swatchMarkdown = (await download(samplePage, key(colorPanel, `dl_md_${swatchId}`).getByRole('button'), path.join(output, 'color-swatch.md'))).toString();
      assert(swatchMarkdown.includes('外婆家的藏青（显示色 #26374a，屏幕示意，不是品牌色号）'));
      await clickKey(samplePage, colorPanel, `pdf_gen_${swatchId}`);
      const swatchPdf = await download(samplePage, key(colorPanel, `dl_pdf_${swatchId}`).getByRole('button'), path.join(output, 'color-swatch.pdf'));
      assert.equal(swatchPdf.subarray(0, 5).toString(), '%PDF-');
      // Open the Parade expander and wait until its own button is on screen.
      // Clicking while the block is still moving can hit the external manual
      // link; that navigation is aborted and closes the page.
      const paradeHolder = key(colorPanel, `dl_parade_${swatchId}`);
      const paradeDetails = paradeHolder.locator('xpath=ancestor::details').first();
      if (await paradeDetails.getAttribute('open') === null) {
        await paradeDetails.locator(':scope > summary').click();
        await settle(samplePage);
      }
      const paradeButton = paradeHolder.getByRole('button', {name: '下载 CrochetPARADE DSL', exact: true});
      await paradeButton.scrollIntoViewIfNeeded();
      await expect(paradeButton).toBeVisible();
      const swatchParade = (await download(samplePage, paradeButton, path.join(output, 'color-swatch-parade.txt'))).toString();
      assert(swatchParade.includes('# display swatch for 外婆家的藏青 — screen colour only, not a yarn brand code'));
      assert(swatchParade.includes('COLOR: #26374a'));
      assert(!swatchParade.includes('COLOR: #e8bfa8'));
      assert(!swatchParade.includes('COLOR: #9aa7b8'));
      await samplePage.screenshot({path: path.join(output, 'color-swatch.png'), fullPage: true});

      await clickKey(samplePage, colorPanel, `edit_${swatchId}_undo`);
      const swatchUndoId = await resultId(colorPanel, swatchId);
      const swatchUndone = JSON.parse(await download(samplePage, key(colorPanel, `dl_backup_${swatchUndoId}`).getByRole('button'), path.join(output, 'color-swatch-undo.json')));
      assert.equal(swatchUndone.params.display_colors, undefined);
      assert.equal(swatchUndone.params.parts[headIndex].color, perCopyBackup.params.parts[headIndex].color);
      await clickKey(samplePage, colorPanel, `edit_${swatchUndoId}_redo`);
      const swatchRedoId = await resultId(colorPanel, swatchUndoId);
      const swatchRedone = JSON.parse(await download(samplePage, key(colorPanel, `dl_backup_${swatchRedoId}`).getByRole('button'), path.join(output, 'color-swatch-redo.json')));
      assert.equal(swatchRedone.params.display_colors['外婆家的藏青'], '#26374a');
      assert.equal(swatchRedone.params.parts[headIndex].color, '外婆家的藏青');

      await clickKey(samplePage, colorPanel, `project_save_${swatchRedoId}`);
      const swatchProject = path.join(output, 'color-swatch-project.json');
      await download(samplePage, samplePage.getByRole('dialog').getByRole('button', {name: '下载工程 JSON', exact: true}), swatchProject);
      const swatchContext = await context();
      const swatchPage = lastPage = await swatchContext.newPage();
      await swatchPage.goto(baseURL);
      const swatchSidebar = swatchPage.locator('[data-testid="stSidebar"]');
      await key(swatchSidebar, 'open_backup_file').locator('input[type="file"]').setInputFiles(swatchProject);
      await clickKey(swatchPage, swatchSidebar, 'open_backup_apply');
      const swatchRestorePanel = swatchPage.getByRole('tabpanel', {name: '照片分析（本地）', exact: true});
      const swatchRestoreId = await resultId(swatchRestorePanel);
      const swatchRestored = JSON.parse(await download(swatchPage, key(swatchRestorePanel, `dl_backup_${swatchRestoreId}`).getByRole('button'), path.join(output, 'color-swatch-restored.json')));
      assert.equal(swatchRestored.params.display_colors['外婆家的藏青'], '#26374a');
      assert.equal(swatchRestored.params.parts[headIndex].color, '外婆家的藏青');
      await swatchContext.close();
      lastPage = page;
      record('custom display swatch stays with its name through Markdown, PDF, Parade, undo, redo and project restore');
    }

    // The legacy fixture saved one ambiguous head completion plus an unrelated hat completion.
    {
      const collisionContext = await context();
      const collisionPage = lastPage = await collisionContext.newPage();
      await collisionPage.goto(baseURL);
      const collisionSidebar = collisionPage.locator('[data-testid="stSidebar"]');
      const collisionFile = path.join(__dirname,'../tests/fixtures/progress_instance_collision/legacy-project.json');
      const collisionInput = JSON.parse(await fs.readFile(collisionFile));
      const collisionHeadIndex = collisionInput.params.parts.findIndex(part=>part.name==='头部');
      const collisionHatIndex = collisionInput.params.parts.findIndex(part=>part.name==='帽子');
      const collisionHeadRounds = collisionInput.params.parts[collisionHeadIndex].rounds.length;
      await key(collisionSidebar,'open_backup_file').locator('input[type="file"]').setInputFiles(collisionFile);
      await clickKey(collisionPage,collisionSidebar,'open_backup_apply');
      await expect(collisionSidebar.getByText(/无法区分属于哪份实体/)).toBeVisible();
      await collisionPage.screenshot({path:path.join(output,'collision-recovery-choice.png'),fullPage:true});
      await expect(collisionPage.locator('[class*="st-key-hist_save_"]')).toHaveCount(0);
      await clickKey(collisionPage,collisionSidebar,'open_backup_recover_ambiguous');
      const collisionPanel = collisionPage.getByRole('tabpanel',{name:'照片分析（本地）',exact:true});
      const collisionId = await resultId(collisionPanel);
      await expect(collisionPanel.getByText(/无法区分属于哪份实体，已暂不标记/)).toBeVisible();
      const headChecks = key(collisionPanel,`sheet_part_${collisionId}_${collisionHeadIndex}`)
        .locator('input[type="checkbox"]');
      const firstHead = headChecks.nth(0);
      const secondHead = headChecks.nth(collisionHeadRounds);
      const recoveredHat = key(collisionPanel,`sheet_part_${collisionId}_${collisionHatIndex}`)
        .locator('input[type="checkbox"]').first();
      await reveal(firstHead);
      await expect(firstHead).not.toBeChecked();
      await expect(secondHead).not.toBeChecked();
      await reveal(recoveredHat);
      await expect(recoveredHat).toBeChecked();
      await reveal(secondHead);
      await secondHead.locator('xpath=ancestor::label').click();
      await settle(collisionPage);
      await clickKey(collisionPage,collisionPanel,`project_save_${collisionId}`);
      const collisionProject = path.join(output,'collision-project.json');
      const collisionSaved = JSON.parse(await download(collisionPage,
        collisionPage.getByRole('dialog').getByRole('button',{name:'下载工程 JSON',exact:true}),collisionProject));
      assert.equal(collisionSaved.project_state.progress_identity_version,'2');
      const headCompleted = Object.keys(collisionSaved.project_state.completed_rounds)
        .map(value=>JSON.parse(value)).filter(value=>value[0]==='头部');
      assert.deepEqual(headCompleted,[['头部','copy2_',1]]);
      assert.equal(collisionSaved.project_state.notes,'原始合成备注');
      const collisionFreshContext = await context();
      const collisionFresh = lastPage = await collisionFreshContext.newPage();
      await collisionFresh.goto(baseURL);
      const freshSidebar = collisionFresh.locator('[data-testid="stSidebar"]');
      await key(freshSidebar,'open_backup_file').locator('input[type="file"]').setInputFiles(collisionProject);
      await clickKey(collisionFresh,freshSidebar,'open_backup_apply');
      const freshPanel = collisionFresh.getByRole('tabpanel',{name:'照片分析（本地）',exact:true});
      const freshId = await resultId(freshPanel);
      const freshChecks = key(freshPanel,`sheet_part_${freshId}_${collisionHeadIndex}`)
        .locator('input[type="checkbox"]');
      const freshFirst = freshChecks.nth(0);
      const freshSecond = freshChecks.nth(collisionHeadRounds);
      await reveal(freshFirst);
      await expect(freshFirst).not.toBeChecked();
      await expect(freshSecond).toBeChecked();
      const freshHat = key(freshPanel,`sheet_part_${freshId}_${collisionHatIndex}`)
        .locator('input[type="checkbox"]').first();
      await reveal(freshHat);
      await expect(freshHat).toBeChecked();
      await collisionFresh.screenshot({path:path.join(output,'collision-progress-restored.png'),fullPage:true});
      record('legacy collision requires recovery, then separate copy progress survives a fresh project restore');
    }
    const mobileContext = await context({width:390,height:844});
    const mobile = lastPage = await mobileContext.newPage();
    await mobile.goto(baseURL);
    const mobileTitle = mobile.locator('h1.sheet-hero__title [data-heading-text]');
    await expect(mobileTitle).toBeVisible();
    assert.equal(await mobileTitle.evaluate(element => element.getClientRects().length),1,
                 'Product title should fit on one line at a 390 px viewport.');
    await expect(mobile.locator('[data-testid="stHeader"]')).toHaveCSS('background-color','rgb(246, 247, 244)');
    await expect(mobile.getByRole('button',{name:'Deploy',exact:true})).toHaveCount(0);
    await mobile.screenshot({path:path.join(output,'pattern-sheet-mobile.png')});
    record('390 px viewport keeps the title on one line and the header opaque without Deploy');
    // The sidebar starts collapsed on a phone; opened, it must slide fully in and
    // show the same outline. Off-screen content already counts as "visible", so
    // wait for the drawer's actual position before judging it.
    await mobile.getByRole('button',{name:'Expand sidebar',exact:true}).click();
    const mobileSidebar = mobile.locator('[data-testid="stSidebar"]');
    await expect(mobileSidebar.locator('[data-testid="stSidebarCollapseButton"]')).toHaveCount(1);
    await expect.poll(() => mobileSidebar.evaluate(element => {
      const box = element.getBoundingClientRect();
      return [Math.round(box.left), Math.round(box.width)];
    })).toEqual([0, 300]);
    await expect(mobileSidebar.locator('h3, [data-testid="stExpander"] summary [data-testid="stMarkdownContainer"]'))
      .toHaveText(['编织密度（小样）','塑形选项（进阶）','打开已有工作','打开备份图解','打开试钩包','我的图解（历史）']);
    await mobile.screenshot({path:path.join(output,'pattern-sheet-mobile-sidebar.png')});
    record('390 px viewport opens the sidebar drawer with the same gauge-first outline');
    await mobileContext.close();
    lastPage = page;
    assert.deepEqual(report.page_errors,[]);
    report.status = 'pass';
    console.log(`PASS all ${report.checks.length} browser workflow checks; output ${output}`);
  } catch(error) {
    report.status='fail';report.error=String(error.stack || error);
    if(lastPage) {
      await lastPage.screenshot({path:path.join(output,'failure.png'),fullPage:true}).catch(()=>{});
      await fs.writeFile(path.join(output,'failure.html'),await lastPage.content()).catch(()=>{});
    }
    throw error;
  } finally {
    await fs.writeFile(path.join(output,'report.json'),JSON.stringify(report,null,2));
    await browser.close();
  }
})().catch(error=>{console.error(error);process.exitCode=1});
