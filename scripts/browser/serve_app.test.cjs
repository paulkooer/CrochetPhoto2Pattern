// A launcher in a worktree must override a shared virtualenv's editable app.
const assert = require('node:assert/strict');
const {execFileSync} = require('node:child_process');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const {test} = require('node:test');

test('server imports app from its own checkout using a shared virtualenv and foreign cwd',async () => {
  const temp = await fs.mkdtemp(path.join(os.tmpdir(),'crochet-server-source-'));
  try {
    const browserDir = path.join(temp,'scripts/browser');
    await fs.mkdir(browserDir,{recursive:true});
    await fs.mkdir(path.join(temp,'app'));
    await fs.writeFile(path.join(temp,'app/__init__.py'),'SOURCE_MARKER = "isolated checkout"\n');
    for (const file of ['serve_app.py','upload_ack.py']) {
      await fs.copyFile(path.join(__dirname,file),path.join(browserDir,file));
    }
    const source = JSON.parse(execFileSync(
      process.env.CROCHET_TEST_PYTHON || path.join(__dirname,'../../.venv/bin/python'),[
        '-c',`import json, runpy, sys
# Match direct script execution, whose first import path is scripts/browser.
sys.path.insert(0, sys.argv[2])
runpy.run_path(sys.argv[1], run_name="provenance_test")
import app
print(json.dumps({"file": app.__file__, "marker": app.SOURCE_MARKER}))`,
        path.join(browserDir,'serve_app.py'),browserDir,
      ],{cwd:path.join(__dirname,'../..'),encoding:'utf8'}));
    assert.equal(source.file,await fs.realpath(path.join(temp,'app/__init__.py')));
    assert.equal(source.marker,'isolated checkout');
  } finally { await fs.rm(temp,{recursive:true,force:true}); }
});
