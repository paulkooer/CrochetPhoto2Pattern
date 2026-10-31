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
    base_url:baseURL, input:'synthetic SVG rendered to PNG', checks:[], page_errors:[],
    blocked_external_requests:[], physical_validation:false,
  };
  const browser = await chromium.launch({
    executablePath:process.env.CROCHET_CHROME_EXECUTABLE || undefined, headless:true,
    args:['--disable-background-networking','--disable-component-update'],
  });
  report.browser = browser.version();
  let lastPage;
  const record = name => {report.checks.push({name,status:'pass'}); console.log(`PASS ${name}`);};
  async function context() {
    const ctx = await browser.newContext({viewport:{width:1440,height:1100},acceptDownloads:true});
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
    await page.getByRole('tab', {name:'📸 照片分析（本地）',exact:true}).click();
    const photoPanel = page.getByRole('tabpanel', {name:'📸 照片分析（本地）',exact:true});
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
    const ratio = photoPanel.locator('[class*="st-key-review_ratio_"] input');
    await ratio.fill('0.3');await ratio.press('Tab');await settle(page);
    const generate = photoPanel.getByRole('button',{name:'确认并生成图解',exact:true});
    assert.equal(await generate.isEnabled(),true);
    await generate.click();await settle(page);
    let photoId = await resultId(photoPanel);
    await expect(photoPanel.getByText('✓ 比例与部件已经过人工确认；原始解析来源保留如下。',{exact:true})).toHaveCount(1);
    record('complete subject/proportion/parts review and generate');

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

    await page.getByRole('tab',{name:'✏️ 手动输入',exact:true}).click();
    const manual = page.getByRole('tabpanel',{name:'✏️ 手动输入',exact:true});
    await clickKey(page,manual,'btn_manual');
    let manualId = await resultId(manual);
    await headProgress(page,manual,manualId,true);
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
    await page.getByRole('tab',{name:'📸 照片分析（本地）',exact:true}).click();
    photoId = await resultId(photoPanel,photoId);
    assert.notEqual(photoId,manualId);
    await headProgress(page,photoPanel,photoId,true);
    const clearPhoto = key(photoPanel,`sheet_part_${photoId}_0`).getByRole('button',{name:'↩️ 重置进度',exact:true,includeHidden:true});
    await reveal(clearPhoto);await clearPhoto.click();await settle(page);
    await fillKey(page,photoPanel,`project_notes_${photoId}`,'photo workspace note');
    await page.getByRole('tab',{name:'✏️ 手动输入',exact:true}).click();
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
    const restored = fresh.getByRole('tabpanel',{name:'📸 照片分析（本地）',exact:true});
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
    await clickKey(fresh,freshSidebar,'open_backup_apply');
    await expect(freshSidebar).toContainText('导入失败');
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
    const openPanel = reopened.getByRole('tabpanel',{name:'📸 照片分析（本地）',exact:true});
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
