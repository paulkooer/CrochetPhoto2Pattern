"""Offline tests for bounded, atomic pose-model acquisition."""
import hashlib
import io
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import pytest

from app.models import pose


@pytest.fixture
def cache(monkeypatch, tmp_path):
    monkeypatch.delenv("CROCHET_POSE_MODEL", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    payload = b"verified-model"
    monkeypatch.setattr(pose, "MODEL_SHA256", hashlib.sha256(payload).hexdigest())
    # Module state from an earlier failure must not leak into this test.
    monkeypatch.setattr(pose, "_download_retry_after", 0.0)
    return tmp_path / ".cache" / "crochet_photo2pattern" / "pose_landmarker_lite.task"


def test_model_download_is_verified_and_atomically_published(cache, monkeypatch):
    def response(url, *, timeout):
        assert url == pose.MODEL_URL
        assert 0 < timeout <= 30
        assert not cache.exists()
        return io.BytesIO(b"verified-model")

    monkeypatch.setattr(pose.urllib.request, "urlopen", response)
    assert pose.model_path() == cache
    assert cache.read_bytes() == b"verified-model"
    assert list(cache.parent.iterdir()) == [cache]


def test_corrupt_download_cannot_replace_existing_cache(cache, monkeypatch):
    cache.parent.mkdir(parents=True)
    cache.write_bytes(b"old-corrupt-cache")
    monkeypatch.setattr(pose.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(b"bad"))
    assert pose.model_path() is None
    assert cache.read_bytes() == b"old-corrupt-cache"
    assert list(cache.parent.iterdir()) == [cache]


def test_read_failure_falls_back_without_deleting_cache(cache, monkeypatch):
    cache.parent.mkdir(parents=True)
    cache.write_bytes(b"verified-model")

    def denied(path):
        raise PermissionError("unreadable")

    monkeypatch.setattr(pose, "_sha256_of", denied)
    assert pose.model_path() is None
    assert cache.exists()


def test_failed_transfer_cleans_up_partial_download(cache, monkeypatch):
    class Interrupted(io.BytesIO):
        def read1(self, size=-1):
            if self.tell():
                raise TimeoutError("stalled transfer")
            return super().read(3)

    monkeypatch.setattr(pose.urllib.request, "urlopen", lambda *a, **k: Interrupted(b"partial"))
    assert pose.model_path() is None
    assert not list(cache.parent.iterdir())


def test_model_size_limit_is_enforced(cache, monkeypatch):
    monkeypatch.setattr(pose, "_MODEL_MAX_BYTES", 4)
    monkeypatch.setattr(pose.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(b"verified-model"))
    assert pose.model_path() is None
    assert not list(cache.parent.iterdir())


def test_transfer_deadline_is_enforced(cache, monkeypatch):
    # Third tick: the failure path stamps the negative-cache deadline.
    ticks = iter((0.0, 31.0, 31.0))
    monkeypatch.setattr(pose.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(pose.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(b"verified-model"))
    assert pose.model_path() is None
    assert not list(cache.parent.iterdir())
    assert pose._download_retry_after > 0


def test_failed_download_backs_off_within_the_process(cache, monkeypatch):
    calls = []

    def offline(*args, **kwargs):
        calls.append(1)
        raise OSError("network unreachable")

    monkeypatch.setattr(pose.urllib.request, "urlopen", offline)
    assert pose.model_path() is None
    assert pose.model_path() is None
    assert len(calls) == 1
    assert not cache.exists()


def test_backoff_expires_and_a_later_success_clears_it(cache, monkeypatch):
    calls = []
    state = {"online": False}

    def flaky(*args, **kwargs):
        calls.append(1)
        if state["online"]:
            return io.BytesIO(b"verified-model")
        raise OSError("network unreachable")

    monkeypatch.setattr(pose.urllib.request, "urlopen", flaky)
    monkeypatch.setattr(pose, "_MODEL_FAILURE_BACKOFF_SECONDS", 0.0)
    assert pose.model_path() is None
    state["online"] = True
    assert pose.model_path() == cache
    assert cache.read_bytes() == b"verified-model"
    assert len(calls) == 2
    assert pose._download_retry_after == 0.0


def test_valid_cache_bypasses_the_backoff(cache, monkeypatch):
    cache.parent.mkdir(parents=True)
    cache.write_bytes(b"verified-model")
    monkeypatch.setattr(pose, "_download_retry_after", float("inf"))
    assert pose.model_path() == cache


def test_concurrent_callers_share_one_verified_download(cache, monkeypatch):
    entered, release = Event(), Event()
    calls = []

    def response(*args, **kwargs):
        calls.append(1)
        entered.set()
        assert release.wait(3)
        return io.BytesIO(b"verified-model")

    monkeypatch.setattr(pose.urllib.request, "urlopen", response)
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(pose.model_path) for _ in range(4)]
        try:
            assert entered.wait(3)
        finally:
            release.set()
        assert [future.result(timeout=3) for future in futures] == [cache] * 4
    assert len(calls) == 1
    assert cache.read_bytes() == b"verified-model"


def test_user_supplied_model_never_downloads(tmp_path, monkeypatch):
    custom = tmp_path / "custom.task"
    custom.write_bytes(b"user-model")
    monkeypatch.setenv("CROCHET_POSE_MODEL", str(custom))
    assert pose.model_path() == custom
    monkeypatch.setenv("CROCHET_POSE_MODEL", str(tmp_path / "missing.task"))
    assert pose.model_path() is None
