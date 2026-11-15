const assert = require('node:assert/strict');
const {execFileSync} = require('node:child_process');
const {EventEmitter} = require('node:events');
const path = require('node:path');
const {test} = require('node:test');
const {completedUploadRun,observeRuns,runLog} = require('./streamlit_protocol.cjs');
const digest = 'a'.repeat(64);

test('queued older request cannot acknowledge uploaded content',() => {
  const events = [
    {sequence:1,type:'request',fileIds:[]},
    {sequence:2,type:'request',fileIds:['new-file']},
    {sequence:3,type:'start',id:'older-queued-run',fragments:[]},
    {sequence:4,type:'ack',id:'older-queued-run',fileId:'old-file',sha256:digest},
    {sequence:5,type:'finish',id:'older-queued-run',status:0},
  ];
  assert.equal(completedUploadRun(events,1,'new-file',digest),null,
               'A queued older run must not complete the upload without its content acknowledgement.');
  events.push({sequence:6,type:'start',id:'upload-run',fragments:[]},
              {sequence:7,type:'ack',id:'upload-run',fileId:'new-file',sha256:digest});
  assert.equal(completedUploadRun(events,1,'new-file',digest),null);
  events.push({sequence:8,type:'finish',id:'upload-run',status:0});
  assert.equal(completedUploadRun(events,1,'new-file',digest),'upload-run');
});

test('content acknowledgement rejects a different digest',() => {
  const events = [
    {sequence:1,type:'request',fileIds:['new']},
    {sequence:2,type:'start',id:'run',fragments:[]},
    {sequence:3,type:'ack',id:'run',fileId:'new',sha256:'b'.repeat(64)},
    {sequence:4,type:'finish',id:'run',status:0},
  ];
  assert.equal(completedUploadRun(events,0,'new',digest),null,
               'A different content digest must not complete the upload.');
});

test('content acknowledgement requires a request carrying the target file ID',() => {
  const events = [
    {sequence:1,type:'request',fileIds:['old-file']},
    {sequence:2,type:'start',id:'run',fragments:[]},
    {sequence:3,type:'ack',id:'run',fileId:'new',sha256:digest},
    {sequence:4,type:'finish',id:'run',status:0},
  ];
  assert.equal(completedUploadRun(events,0,'new',digest),null,
               'An acknowledgement without a request carrying the target file must not complete the upload.');
});

for (const variant of ['wrong-run','wrong-file','before-start','after-finish','interrupted',
                       'fragment','fragment-with-full-run-status']) {
  test(`content acknowledgement rejects ${variant}`,() => {
    const ack = {sequence:3,type:'ack',id:'run',fileId:'new',sha256:digest};
    const start = {sequence:2,type:'start',id:'run',fragments:[]};
    const finish = {sequence:4,type:'finish',id:'run',status:0};
    if (variant === 'wrong-run') ack.id = 'another-run';
    if (variant === 'wrong-file') ack.fileId = 'another-file';
    if (variant === 'before-start') ack.sequence = 1.5;
    if (variant === 'after-finish') ack.sequence = 5;
    if (variant === 'interrupted') finish.status = 2;
    if (variant.startsWith('fragment')) {
      start.fragments = ['fragment'];
      // 3 is Streamlit's actual fragment success status. The inconsistent 0
      // case separately protects the redundant fragment-ID guard.
      if (variant === 'fragment') finish.status = 3;
    }
    const events = [{sequence:1,type:'request',fileIds:['new']},start,ack,finish];
    assert.equal(completedUploadRun(events,0,'new',digest),null,
                 variant.startsWith('fragment') ? 'A fragment run must not complete a full-app upload.' : variant);
  });
}

test('observer ignores unrelated parent messages and still rejects malformed upload acknowledgements',() => {
  const frames = JSON.parse(execFileSync(
    process.env.CROCHET_TEST_PYTHON || path.join(__dirname,'../../.venv/bin/python'),[
      '-c',`import base64, json
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
ack = {"type": "crochet_browser_upload_ack_v1", "file_id": "new", "sha256": "a" * 64,
       "app_file": "/test/app/__init__.py"}
frames = []
for text in ["plain Streamlit message", "null", json.dumps({"type": "other"}),
             json.dumps(ack), json.dumps({"type": ack["type"]})]:
    msg = ForwardMsg()
    msg.parent_message.message = text
    msg.metadata.run.script_run_id = "run"
    frames.append(base64.b64encode(msg.SerializeToString()).decode())
print(json.dumps(frames))`,
    ],{encoding:'utf8'}));
  const page = new EventEmitter();
  const socket = new EventEmitter();
  socket.url = () => 'ws://127.0.0.1/_stcore/stream';
  observeRuns(page);
  page.emit('websocket',socket);
  for (const frame of frames.slice(0,4)) {
    socket.emit('framereceived',{payload:Buffer.from(frame,'base64')});
    assert.doesNotThrow(() => runLog(page));
  }
  assert.equal(runLog(page).events.length,1);
  assert.equal(runLog(page).events[0].type,'ack');
  assert.equal(runLog(page).serverAppFile,'/test/app/__init__.py');
  socket.emit('framereceived',{payload:Buffer.from(frames[4],'base64')});
  assert.throws(() => runLog(page),/Malformed upload content acknowledgement/);
});
