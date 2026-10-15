"""Isolate history, optional pose weights and legacy environment settings."""
import pytest

_EXTERNAL_ENV = (
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
    "OPENAI_BASE_URL", "ANTHROPIC_BASE_URL",
    "OPENAI_VISION_MODEL", "ANTHROPIC_VISION_MODEL",
)


@pytest.fixture(autouse=True)
def _hermetic_env(monkeypatch, tmp_path):
    for name in _EXTERNAL_ENV:
        monkeypatch.delenv(name, raising=False)
    # 历史库重定向到每测试独立的临时目录（G5：相对路径会在仓库根产出
    # 文件且未 gitignore；固定 /tmp 路径在并行/多用户环境下互相踩踏）
    monkeypatch.setenv("CROCHET_HISTORY_DB", str(tmp_path / "history.db"))
    monkeypatch.setenv("CROCHET_HISTORY_MODE", "single_user")
    # Ordinary pipeline tests must not download pose weights or write to the
    # developer's model cache. Dedicated cache tests override this explicitly.
    monkeypatch.setenv("CROCHET_POSE_MODEL", str(tmp_path / "unconfigured-pose.task"))
