// Check that the immediate tail assertion rejects both early-return variants.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const {spawnSync} = require('node:child_process');
const helper = path.join(__dirname,'workflow_helpers.cjs');
const anchor = '  await waitForUploadRun(page,after,fileId);\n';

if (process.env.CROCHET_UPLOAD_MUTANT) {
  const original = Module._load;
  Module._load = function(request,parent,...rest) {
    if (request !== './workflow_helpers.cjs' || !parent.filename.endsWith('workflow_helpers.test.cjs')) {
      return original.call(this,request,parent,...rest);
    }
    let source = fs.readFileSync(helper,'utf8');
    assert(source.includes(anchor),'Upload completion mutator needs updating.');
    if (process.env.CROCHET_UPLOAD_MUTANT === 'no_run_wait') source = source.replace(anchor,'');
    else {
      assert.equal(process.env.CROCHET_UPLOAD_MUTANT,'response_only');
      const from = source.indexOf('  const fileId =');
      const to = source.indexOf('\n}\n\nasync function download',from);
      assert(from > 0 && to > from);
      source = source.slice(0,from) + source.slice(to);
    }
    const mutant = new Module(helper,parent);
    mutant.filename = helper;
    mutant.paths = Module._nodeModulePaths(__dirname);
    mutant._compile(source,helper);
    return mutant.exports;
  };
}

if (require.main === module) {
  for (const name of ['no_run_wait','response_only']) {
    const result = spawnSync(process.execPath,[
      '--require',__filename,'--test',
      '--test-name-pattern=^uploaded input waits for its Python rerun',
      path.join(__dirname,'workflow_helpers.test.cjs'),
    ],{env:{...process.env,CROCHET_UPLOAD_MUTANT:name},encoding:'utf8',timeout:30000});
    const output = result.stdout + result.stderr;
    assert.equal(result.status,1,`${name} must fail its regression:\n${output}`);
    assert(output.includes('upload() returned before its rerun rendered the final marker.'),
           `${name} failed for an unexpected reason:\n${output}`);
    console.log(`PASS mutation killed: ${name}; immediate final-marker assertion failed as intended`);
  }
}
