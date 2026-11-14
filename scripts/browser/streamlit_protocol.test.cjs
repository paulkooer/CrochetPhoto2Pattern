const assert = require('node:assert/strict');
const {test} = require('node:test');
const {completedUploadRun} = require('./streamlit_protocol.cjs');
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

for (const variant of ['wrong-run','wrong-file','before-start','after-finish','interrupted','fragment']) {
  test(`content acknowledgement rejects ${variant}`,() => {
    const ack = {sequence:3,type:'ack',id:'run',fileId:'new',sha256:digest};
    const start = {sequence:2,type:'start',id:'run',fragments:[]};
    const finish = {sequence:4,type:'finish',id:'run',status:0};
    if (variant === 'wrong-run') ack.id = 'another-run';
    if (variant === 'wrong-file') ack.fileId = 'another-file';
    if (variant === 'before-start') ack.sequence = 1.5;
    if (variant === 'after-finish') ack.sequence = 5;
    if (variant === 'interrupted') finish.status = 2;
    if (variant === 'fragment') start.fragments = ['fragment'];
    const events = [{sequence:1,type:'request',fileIds:['new']},start,ack,finish];
    assert.equal(completedUploadRun(events,0,'new',digest),null);
  });
}
