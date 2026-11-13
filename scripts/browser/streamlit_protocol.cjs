// Read lifecycle messages before React rendering can coalesce UI states.
const assert = require('node:assert/strict');
const path = require('node:path');
const {execFileSync} = require('node:child_process');
const {setTimeout:delay} = require('node:timers/promises');
const protobuf = require('protobufjs/light');
const descriptor = JSON.parse(execFileSync(
  process.env.CROCHET_TEST_PYTHON || path.join(__dirname,'../../.venv/bin/python'),
  [path.join(__dirname,'streamlit_protocol.py')],{encoding:'utf8'}));
const root = protobuf.Root.fromJSON(descriptor.schema);
const forward = root.lookupType('ForwardMsg');
const back = root.lookupType('BackMsg');
const logs = new WeakMap();

const decodeBack = payload => back.decode(payload);

function observeRuns(page) {
  if (logs.has(page)) return;
  const log = {sequence:0,events:[],sockets:0,error:null};
  logs.set(page,log);
  const record = event => {
    log.events.push({...event,sequence:++log.sequence});
    if (log.events.length > 256) log.events.shift();
  };
  page.on('websocket',socket => {
    if (!new URL(socket.url()).pathname.endsWith('/_stcore/stream')) return;
    log.sockets++;
    socket.on('framesent',frame => {
      try {
        const state = decodeBack(frame.payload).rerun_script;
        if (!state) return;
        record({type:'request',fileIds:(state.widget_states?.widgets || []).flatMap(widget =>
          (widget.file_uploader_state_value?.uploaded_file_info || []).map(file => file.file_id))});
      } catch (error) { log.error = error; }
    });
    socket.on('framereceived',frame => {
      try {
        const message = forward.decode(frame.payload);
        const run = message.metadata?.run;
        if (Object.hasOwn(message,'new_session')) {
          assert(run?.script_run_id,'Streamlit new_session has no run identity.');
          record({type:'start',id:run.script_run_id,fragments:run.fragment_ids || []});
        }
        if (Object.hasOwn(message,'script_finished') && run?.script_run_id) {
          record({type:'finish',id:run.script_run_id,status:message.script_finished});
        }
      } catch (error) { log.error = error; }
    });
    socket.on('close',() => { log.error = new Error('Streamlit WebSocket closed during upload.'); });
  });
  page.on('close',() => { log.error = new Error('Page closed during upload.'); });
}

function runLog(page) {
  const log = logs.get(page);
  assert(log?.sockets,'observeRuns(page) must be installed before navigating to Streamlit.');
  if (log.error) throw log.error;
  return log;
}

function completedUploadRun(events, after, fileId) {
  const request = events.find(event => event.sequence > after && event.type === 'request'
    && event.fileIds.includes(fileId));
  if (!request) return null;
  for (const start of events.filter(event => event.sequence > request.sequence
       && event.type === 'start' && !event.fragments.length)) {
    const finish = events.find(event => event.sequence > start.sequence
      && event.type === 'finish' && event.id === start.id);
    if (finish?.status === 1) throw new Error(`Streamlit upload run ${start.id} failed to compile.`);
    // An interrupted run (2) does not satisfy the barrier; wait for its rerun.
    if (finish?.status === 0) return start.id;
  }
  return null;
}

async function waitForUploadRun(page, after, fileId) {
  const deadline = Date.now() + 45000;
  while (Date.now() < deadline) {
    const log = runLog(page);
    const id = completedUploadRun(log.events,after,fileId);
    if (id) return id;
    await delay(25);
  }
  throw new Error(`No completed Streamlit run acknowledged uploaded file ${fileId} within 45000ms.`);
}

module.exports = {observeRuns,runLog,waitForUploadRun,completedUploadRun,decodeBack,
                  streamlitVersion:descriptor.streamlit_version};
