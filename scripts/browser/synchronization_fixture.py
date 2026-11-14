"""Synthetic Streamlit fixture with a slow tail after rendering an action."""
from __future__ import annotations

import time
from typing import Any, cast
from urllib.parse import parse_qs

import streamlit as st
from streamlit.proto.ClientState_pb2 import ClientState
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
from streamlit.runtime.app_session import AppSession

# In this isolated fixture only, hold a client rerun request before a new run
# starts. This leaves the old UI idle after the HTTP upload has completed.
if not hasattr(AppSession, "_browser_sync_original_rerun"):
    session_class = cast(Any, AppSession)
    session_class._browser_sync_original_rerun = AppSession._handle_rerun_script_request

    def delayed_request(self: AppSession, client_state: ClientState | None = None) -> None:
        if (client_state is not None
                and parse_qs(client_state.query_string).get("delay_request") == ["1"]):
            time.sleep(1)
        session_class._browser_sync_original_rerun(self, client_state)

    session_class._handle_rerun_script_request = delayed_request

# Fault injection for the content-ack regression. Delay server messages in FIFO
# order except the upload-URL reply, so a target request can reach the observer
# before an older run's start/finish. This is not a physical-link simulation.
if not hasattr(AppSession, "_browser_sync_original_forward"):
    forward_class = cast(Any, AppSession)
    forward_class._browser_sync_original_forward = AppSession._enqueue_forward_msg

    def delayed_forward(self: AppSession, message: ForwardMsg) -> None:
        original = forward_class._browser_sync_original_forward
        if (parse_qs(self._client_state.query_string).get("delay_forward") == ["1"]
                and message.WhichOneof("type") != "file_urls_response"):
            self._event_loop.call_soon_threadsafe(
                self._event_loop.call_later, 1.0, original, self, message,
            )
        else:
            original(self, message)

    forward_class._enqueue_forward_msg = delayed_forward

st.set_page_config(page_title="Browser synchronization fixture")
uploaded = st.file_uploader("Synthetic input", type=["json"], key="sync_file")
st.button("Queue older rerun", key="sync_older")
fast = st.query_params.get("fast") == "1"
apply = False
if not fast:
    apply = st.button("Apply synthetic input", disabled=uploaded is None, key="sync_apply")
    if uploaded is not None and st.query_params.get("slow_tail") == "1":
        # The button is rendered before the run finishes, just as in the real app.
        time.sleep(2)
with st.container(key="sync_tail"):
    st.text("initial" if uploaded is None else uploaded.name + ":" + uploaded.getvalue().decode())
if apply and uploaded is not None:
    st.success("Applied: " + uploaded.getvalue().decode())
if not fast:
    st.download_button("Download synthetic output", b"synthetic-output", "synthetic.txt")
