"""The per-tab progress record is the single source of truth for completed rounds."""
from app.services.progress_state import (
    capture_progress,
    completed_rounds,
    install_progress,
    progress_entries,
    progress_record_key,
)
from tests.test_app_smoke import _mock_result


def test_record_belongs_to_one_result_and_ignores_unknown_rounds():
    result = _mock_result("first")
    identities = [identity for identity, _, _ in progress_entries(result, "result")]
    state: dict = {}
    install_progress(result, "result", {identities[0]: True, identities[1]: False,
                                        '["头部", "missing", 1]': True}, state)
    assert state[progress_record_key("result")] == {"result_id": "first",
                                                     "completed": {identities[0]: True}}
    # A record left by another result is not this result's progress.
    assert completed_rounds({**result, "result_id": "second"}, "result", state) == {}
    assert completed_rounds(result, "manual_result", state) == {}


def test_capture_is_a_copy_limited_to_current_rounds():
    result = _mock_result("live")
    first, second = [identity for identity, _, _ in progress_entries(result, "result")][:2]
    state: dict = {}
    install_progress(result, "result", {first: True, second: True}, state)
    state[progress_record_key("result")]["completed"]['["头部", "stale", 1]'] = True
    captured = capture_progress(result, "result", state)
    assert captured == {first: True, second: True}
    captured.pop(first)
    assert completed_rounds(result, "result", state)[first] is True
