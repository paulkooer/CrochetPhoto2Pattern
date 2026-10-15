// Optional browser smoke test: install Playwright in your test environment, then
// node scripts/check_mask_canvas.cjs. Uses only a synthetic image and local files.
const {chromium} = require(process.env.CROCHET_PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
(async () => {
 const browser = await chromium.launch({executablePath:process.env.CROCHET_CHROME_EXECUTABLE || undefined, headless:true});
 try {
 const page = await browser.newPage({viewport:{width:800,height:900}});
 const errors=[]; page.on('pageerror',e=>errors.push(String(e)));
 await page.goto(pathToFileURL(path.join(__dirname, '../app/ui/mask_canvas/index.html')).href);
 const base = Array.from({length:3200},(_,i)=>Math.floor(i/40)>=30&&Math.floor(i/40)<70&&i%40>=12&&i%40<28?'1':'0').join('');
 const args={image_token:'a'.repeat(64),width:40,height:80,base_pixels:base,current_pixels:base,image_url:'data:image/svg+xml,'+encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="40" height="80"><rect width="40" height="80" fill="white"/><rect x="12" y="30" width="16" height="40" fill="red"/></svg>')};
 await page.evaluate(a=>{window.sent=[];window.addEventListener('message',e=>{if(e.data.type==='streamlit:setComponentValue')window.sent.push(e.data.value)});window.postMessage({type:'streamlit:render',args:a},'*')},args);
 await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('拖动'));
 const box=await page.locator('#canvas').boundingBox();
 async function click(x,y){const n=await page.evaluate(()=>window.sent.length);await page.mouse.click(box.x+box.width*x/40,box.y+box.height*y/80);await page.waitForFunction(n=>window.sent.length>n,n)}
 async function button(id){const n=await page.evaluate(()=>window.sent.length);await page.locator(id).click();await page.waitForFunction(n=>window.sent.length>n,n)}
 await click(20,8);
 await page.waitForFunction(()=>window.sent.length===1);
 assert.equal(await page.evaluate(()=>window.sent.at(-1).pixels[8*40+20]),'1');
 await page.locator('#mode').selectOption('0'); await click(20,45);
 assert.equal(await page.evaluate(()=>window.sent.at(-1).pixels[45*40+20]),'0');
 await button('#undo');
 assert.equal(await page.evaluate(()=>window.sent.at(-1).pixels[45*40+20]),'1');
 await button('#undo');
 assert.equal(await page.evaluate(()=>window.sent.at(-1).pixels),base);
 await page.locator('#mode').selectOption('1');
 const beforeStroke=await page.evaluate(()=>window.sent.length);
 await page.mouse.move(box.x+box.width*0.2,box.y+box.height*0.15);await page.mouse.down();
 await page.mouse.move(box.x+box.width*0.8,box.y+box.height*0.15,{steps:5});await page.mouse.up();await page.waitForFunction(n=>window.sent.length>n,beforeStroke);
 const painted=await page.evaluate(()=>window.sent.at(-1).pixels);
 for(let x=8;x<32;x++)assert.equal(painted[12*40+x],'1');
 await button('#reset');assert.equal(await page.evaluate(()=>window.sent.at(-1).pixels),base);
 if (process.env.CROCHET_CANVAS_SCREENSHOT) await page.screenshot({path:process.env.CROCHET_CANVAS_SCREENSHOT});
 assert.deepEqual(errors,[]);
 console.log('PASS: add, erase, undo, continuous stroke, reset; no browser errors');
 } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exit(1)});
