"""The tab workspace as the UI sees it: the notes and title widgets are views of it.

A widget key holds the latest typed value but is namespaced to one result ID and
may be discarded by Streamlit, so the workspace keeps the text. Reading through
``live_workspace`` picks up what the user typed; a new widget starts from the
workspace, which is how notes and titles follow an edit to the new result.
"""
from __future__ import annotations

import streamlit as st

from app.services.workspace import workspace


def notes_key(rid: str) -> str:
    return f"project_notes_{rid}"


def title_key(rid: str) -> str:
    return f"hist_title_{rid}"


def live_workspace(result: dict, slot: str, *, create: bool = True) -> dict:
    """The tab's workspace for ``result`` with the current notes and title widget values."""
    ws = workspace(result, slot, st.session_state, create=create)
    for field, key in (("notes", notes_key(ws["result_id"])), ("title", title_key(ws["result_id"]))):
        if key in st.session_state:
            ws[field] = st.session_state[key]
    return ws


def seed_widget(key: str, value) -> None:
    """Start a widget from the workspace without overwriting what the user typed."""
    if key not in st.session_state:
        st.session_state[key] = value
