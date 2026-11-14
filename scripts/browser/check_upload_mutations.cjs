// Require the intended assertions to reject early-return and correlation mutants.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const {spawnSync} = require('node:child_process');
const helper = path.join(__dirname,'workflow_helpers.cjs');
const protocol = path.join(__dirname,'streamlit_protocol.cjs');
const anchor = '  await waitForUploadRun(page,after,fileId,sha256);\n';
const variants = [
  ...['no_run_wait','response_only'].map(name => ({
    name,file:helper,pattern:'^uploaded input waits for its Python rerun',
    failure:'upload() returned before its rerun rendered the final marker.',
    assertion:'immediate final-marker',
  })),
  {
    name:'start_after_action',file:protocol,
    pattern:'^run correlation rejects a full run that starts before the upload request$',
    from:'event.sequence > request.sequence',to:'event.sequence > after',
    failure:'A full run starting before the upload request must not complete that upload.',
    assertion:'request-order rejection',
  },
  {
    name:'include_fragment_runs',file:protocol,testFile:'streamlit_protocol.test.cjs',
    pattern:'^content acknowledgement rejects fragment-with-full-run-status$',
    from:' && !event.fragments.length',to:'',
    failure:'A fragment run must not complete a full-app upload.',
    assertion:'defensive fragment-ID rejection (synthetic full-run status)',
  },
  {
    name:'ignore_content_ack',file:protocol,testFile:'streamlit_protocol.test.cjs',
    pattern:'^queued older request cannot acknowledge uploaded content$',
    from:' && acknowledged',to:'',
    failure:'A queued older run must not complete the upload without its content acknowledgement.',
    assertion:'queued-request content rejection',
  },
  {
    name:'ignore_content_ack_browser',file:protocol,
    pattern:'^delayed older run messages cannot release upload before its content is rendered$',
    from:' && acknowledged',to:'',
    failure:'Delayed older run released upload() before target content rendered.',
    assertion:'real-browser immediate content marker under delayed server messages',
  },
  {
    name:'ignore_request_file_id',file:protocol,testFile:'streamlit_protocol.test.cjs',
    pattern:'^content acknowledgement requires a request carrying the target file ID$',
    from:'\n    && event.fileIds.includes(fileId)',to:'',
    failure:'An acknowledgement without a request carrying the target file must not complete the upload.',
    assertion:'target-file request rejection',
  },
  {
    name:'ignore_digest',file:protocol,testFile:'streamlit_protocol.test.cjs',
    pattern:'^content acknowledgement rejects a different digest$',
    from:' && event.sha256 === sha256',to:'',
    failure:'A different content digest must not complete the upload.',
    assertion:'content-digest rejection',
  },
];

if (process.env.CROCHET_UPLOAD_MUTANT) {
  const variant = variants.find(entry => entry.name === process.env.CROCHET_UPLOAD_MUTANT);
  assert(variant,'Unknown upload/correlation mutant.');
  const original = Module._load;
  let mutant;
  Module._load = function(request,parent,...rest) {
    if (request !== './' + path.basename(variant.file) || path.dirname(parent.filename) !== __dirname) {
      return original.call(this,request,parent,...rest);
    }
    if (mutant) return mutant.exports;
    let source = fs.readFileSync(variant.file,'utf8');
    if (variant.from) {
      assert.equal(source.split(variant.from).length,2,'Run correlation mutator needs updating.');
      source = source.replace(variant.from,variant.to);
    } else if (variant.name === 'no_run_wait') {
      assert(source.includes(anchor),'Upload completion mutator needs updating.');
      source = source.replace(anchor,'');
    } else {
      assert.equal(variant.name,'response_only');
      const from = source.indexOf('  const fileId =');
      const to = source.indexOf('\n}\n\nasync function download',from);
      assert(from > 0 && to > from);
      source = source.slice(0,from) + source.slice(to);
    }
    mutant = new Module(variant.file,parent);
    mutant.filename = variant.file;
    mutant.paths = Module._nodeModulePaths(__dirname);
    mutant._compile(source,variant.file);
    return mutant.exports;
  };
}

if (require.main === module) {
  for (const {name,pattern,failure,assertion,testFile} of variants) {
    const result = spawnSync(process.execPath,[
      '--require',__filename,'--test',
      `--test-name-pattern=${pattern}`,
      path.join(__dirname,testFile || 'workflow_helpers.test.cjs'),
    ],{env:{...process.env,CROCHET_UPLOAD_MUTANT:name},encoding:'utf8',timeout:30000});
    const output = result.stdout + result.stderr;
    assert.equal(result.status,1,`${name} must fail its regression:\n${output}`);
    assert(output.includes(failure),
           `${name} failed for an unexpected reason:\n${output}`);
    console.log(`PASS mutation killed: ${name}; ${assertion} assertion failed as intended`);
  }
}
