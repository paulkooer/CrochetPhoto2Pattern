"""Synthetic Streamlit fixture with a slow tail after rendering an action."""
from __future__ import annotations

import time

import streamlit as st

st.set_page_config(page_title="Browser synchronization fixture")
uploaded = st.file_uploader("Synthetic input", type=["json"], key="sync_file")
apply = st.button("Apply synthetic input", disabled=uploaded is None, key="sync_apply")
if uploaded is not None:
    # The button is rendered before the run finishes, just as in the real app.
    time.sleep(2)
if apply and uploaded is not None:
    st.success("Applied: " + uploaded.getvalue().decode())
st.download_button("Download synthetic output", b"synthetic-output", "synthetic.txt")
