"""Repo hygiene guards — .env/密钥不得进入版本库。

CI 之外的成本几乎为零，但能拦住"把 .env 提交上去"这类最常见的泄漏事故。
"""
import re
import shutil
import subprocess
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent

# 真实密钥形态（足够长的 token）；.env.example 里的占位符不会被误伤
_KEY_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"sk-proj-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"sk-[A-Za-z0-9_\-]{32,}"),
]


def test_gitignore_covers_env_and_secrets():
    text = (_REPO / ".gitignore").read_text(encoding="utf-8")
    for line in (".env", ".streamlit/secrets.toml"):
        assert line in text, f".gitignore 缺少 {line}"


def test_env_file_not_tracked_by_git():
    if shutil.which("git") is None:
        import pytest
        pytest.skip("git not available")
    try:
        out = subprocess.run(
            ["git", "ls-files"], cwd=_REPO, capture_output=True, text=True, check=True,
        ).stdout
    except (subprocess.CalledProcessError, OSError):
        import pytest
        pytest.skip("not a git repository")
    tracked = out.splitlines()
    assert ".env" not in tracked, ".env 已被 git 跟踪！立即 git rm --cached .env"
    # 本地存在 .env 是正常的，但绝不能出现在跟踪列表里


def test_no_real_api_keys_in_tracked_text_files():
    if shutil.which("git") is None:
        import pytest
        pytest.skip("git not available")
    try:
        out = subprocess.run(
            ["git", "ls-files"], cwd=_REPO, capture_output=True, text=True, check=True,
        ).stdout
    except (subprocess.CalledProcessError, OSError):
        import pytest
        pytest.skip("not a git repository")

    for rel in out.splitlines():
        path = _REPO / rel
        if not path.is_file() or path.suffix not in (".py", ".txt", ".md", ".toml",
                                                     ".yml", ".yaml", ".example", ".cfg"):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pat in _KEY_PATTERNS:
            m = pat.search(text)
            assert m is None, f"{rel} 疑似包含真实 API Key（{m.group()[:12]}…）"
