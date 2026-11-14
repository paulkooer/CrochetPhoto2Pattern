"""Test-server instrumentation: acknowledge bytes returned by file_uploader.

Only serve_app.py installs this adapter. Production app/ and package imports do
not install it. This confirms widget delivery, not successful business parsing.
"""
from __future__ import annotations

import hashlib
import json
import threading
from functools import wraps

from streamlit.elements.widgets.file_uploader import FileUploaderMixin
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
from streamlit.runtime.scriptrunner import get_script_run_ctx
from streamlit.runtime.scriptrunner.script_runner import ScriptRunner, ScriptRunnerEvent

ACK_TYPE = "crochet_browser_upload_ack_v1"


def install_upload_ack() -> None:
    """Install before starting Streamlit, once per isolated test process."""
    if getattr(FileUploaderMixin._file_uploader, "_browser_upload_ack", False):
        return
    active = threading.local()
    original_thread = ScriptRunner._run_script_thread
    original_uploader = FileUploaderMixin._file_uploader

    @wraps(original_thread)
    def run_thread(self):
        def track_run(sender, event, **kwargs):
            if event is ScriptRunnerEvent.SCRIPT_STARTED:
                active.run = kwargs["run_descriptor"]

        self.on_event.connect(track_run, weak=False)
        try:
            return original_thread(self)
        finally:
            self.on_event.disconnect(track_run)

    @wraps(original_uploader)
    def file_uploader(self, *args, **kwargs):
        result = original_uploader(self, *args, **kwargs)
        files = result if isinstance(result, list) else [result]
        for uploaded in files:
            if uploaded is None:
                continue
            ctx = get_script_run_ctx()
            run = getattr(active, "run", None)
            if ctx is None or run is None:
                raise RuntimeError("Browser upload acknowledgement has no active run.")
            # getvalue leaves the application's stream cursor unchanged.
            digest = hashlib.sha256(uploaded.getvalue()).hexdigest()
            message = ForwardMsg()
            message.parent_message.message = json.dumps({
                "type": ACK_TYPE, "file_id": uploaded.file_id, "sha256": digest,
            })
            message.metadata.run.script_run_id = run.script_run_id
            message.metadata.run.fragment_ids.extend(run.fragment_ids)
            ctx.enqueue(message)
        return result

    file_uploader._browser_upload_ack = True
    ScriptRunner._run_script_thread = run_thread
    FileUploaderMixin._file_uploader = file_uploader
