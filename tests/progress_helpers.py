"""Translate between checkbox keys and the progress record, using the renderer's mapping."""
from app.services.progress_state import completed_rounds, progress_entries


def progress_from_keys(result: dict, keys, slot: str = "result") -> dict[str, bool]:
    """Identities a user completes by ticking these checkbox keys."""
    keys = set(keys)
    return {identity: True for identity, key, _ in progress_entries(result, slot) if key in keys}


def checked_keys(result: dict, state, slot: str = "result") -> set[str]:
    """Checkbox keys the result page shows as completed for this record."""
    completed = completed_rounds(result, slot, state)
    return {key for identity, key, _ in progress_entries(result, slot) if completed.get(identity)}


def seed_progress(state, result: dict, keys, slot: str = "result") -> None:
    """Record completion for these checkbox keys, as ticking them would."""
    from app.services.progress_state import install_progress

    progress = progress_from_keys(result, keys, slot)
    assert len(progress) == len(set(keys)), f"not checkbox keys of this pattern: {sorted(keys)}"
    install_progress(result, slot, progress, state)
