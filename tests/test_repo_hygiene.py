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
    re.compile(r"ghp_[A-Za-z0-9]{30,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{30,}"),
    re.compile(r"AKIA[A-Z0-9]{16}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]


def test_gitignore_covers_env_and_secrets():
    text = (_REPO / ".gitignore").read_text(encoding="utf-8")
    for line in (
        ".env",
        ".streamlit/*",
        "!.streamlit/config.toml",
        ".hypothesis/",
        ".codegraph/",
        "/test-history-db-*",
        "/eval_data/",
        "/eval_outputs/",
        "/trial_data/",
        "/trial_outputs/",
    ):
        assert line in text, f".gitignore 缺少 {line}"


def test_release_metadata_is_consistent():
    pyproject = (_REPO / "pyproject.toml").read_text(encoding="utf-8")
    readme = (_REPO / "README.md").read_text(encoding="utf-8")
    changelog = (_REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    status = (_REPO / "docs" / "system-status.md").read_text(encoding="utf-8")

    match = re.search(r'^version = "(\d+\.\d+\.\d+)b(\d+)"$', pyproject, re.MULTILINE)
    assert match is not None, "Beta 阶段版本必须使用 PEP 440 的 X.Y.ZbN 格式"
    release_name = f"{match.group(1)}-beta.{match.group(2)}"

    assert f"## {release_name} - " in changelog
    assert "发布状态：Beta" in readme
    assert 'crochet2pattern-eval = "app.evaluation:main"' in pyproject
    assert 'crochet2pattern-trials = "app.trials:main"' in pyproject
    assert 'app = ["prompts/*.txt", "data/*.json"]' in pyproject
    assert (_REPO / "app" / "data" / "external-trial-evidence.json").is_file()
    assert "系统状态与发布门禁" in readme
    assert "G3 授权照片基线" in status
    assert "G4 实体试钩基线" in status
    assert "github.com/OWNER" not in readme + changelog


def test_repository_has_public_contribution_and_security_guidance():
    required = (
        "LICENSE",
        "CODE_OF_CONDUCT.md",
        "CODE_OF_CONDUCT_EN.md",
        "CONTRIBUTING.md",
        "CONTRIBUTING_EN.md",
        "SECURITY.md",
        "SECURITY_EN.md",
        "README_EN.md",
        "CHANGELOG_EN.md",
        "docs/README.md",
        "docs/system-status.en.md",
        "docs/evaluation.en.md",
        "docs/physical-trials.en.md",
        "docs/flow.en.md",
        "docs/3d-reconstruction-design.en.md",
        ".github/pull_request_template.md",
        ".github/ISSUE_TEMPLATE/bug_report.yml",
        ".github/ISSUE_TEMPLATE/feature_request.yml",
        ".github/ISSUE_TEMPLATE/config.yml",
    )
    for relative in required:
        assert (_REPO / relative).is_file(), f"公开仓库缺少 {relative}"

    readme = (_REPO / "README.md").read_text(encoding="utf-8")
    security = (_REPO / "SECURITY.md").read_text(encoding="utf-8")
    assert "数据与隐私" in readme
    assert "Security → Advisories" in security
    assert "不要用公开 Issue" in security


def test_bilingual_entry_points_cross_link_and_preserve_release_boundaries():
    pairs = (
        ("README.md", "README_EN.md"),
        ("CONTRIBUTING.md", "CONTRIBUTING_EN.md"),
        ("SECURITY.md", "SECURITY_EN.md"),
        ("CODE_OF_CONDUCT.md", "CODE_OF_CONDUCT_EN.md"),
        ("CHANGELOG.md", "CHANGELOG_EN.md"),
        ("docs/system-status.md", "docs/system-status.en.md"),
        ("docs/evaluation.md", "docs/evaluation.en.md"),
        ("docs/physical-trials.md", "docs/physical-trials.en.md"),
        ("docs/flow.md", "docs/flow.en.md"),
        ("docs/3d-reconstruction-design.md", "docs/3d-reconstruction-design.en.md"),
    )
    for chinese_path, english_path in pairs:
        chinese = (_REPO / chinese_path).read_text(encoding="utf-8")
        english = (_REPO / english_path).read_text(encoding="utf-8")
        assert Path(english_path).name in chinese
        assert Path(chinese_path).name in english

    english_readme = (_REPO / "README_EN.md").read_text(encoding="utf-8")
    english_status = (_REPO / "docs/system-status.en.md").read_text(encoding="utf-8")
    assert "Release status: Beta" in english_readme
    assert "Data and privacy" in english_readme
    assert "G3 Authorized-photo baseline" in english_status
    assert "G4 Physical-trial baseline" in english_status


def test_historical_audit_docs_point_to_authoritative_status():
    for relative in ("docs/optimization-brief.md", "docs/handoff-review.md"):
        text = (_REPO / relative).read_text(encoding="utf-8")
        assert "system-status.md" in text
        assert "历史" in text[:400]


def test_supported_python_matches_ci_and_lock():
    pyproject = (_REPO / "pyproject.toml").read_text(encoding="utf-8")
    workflow = (_REPO / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    lock = (_REPO / "uv.lock").read_text(encoding="utf-8")
    local_python = (_REPO / ".python-version").read_text(encoding="utf-8").strip()

    assert 'requires-python = ">=3.11"' in pyproject
    assert 'target-version = "py311"' in pyproject
    assert 'requires-python = ">=3.11"' in lock.split("[[package]]", 1)[0]
    assert local_python == "3.12"

    matrix = re.search(r"python-version: \[([^]]+)]", workflow)
    assert matrix is not None
    assert re.findall(r'"([^"]+)"', matrix.group(1)) == ["3.11", "3.12", "3.13", "3.14"]
    assert "UV_PYTHON: ${{ matrix.python-version }}" in workflow


def test_ci_consumes_lock_file_for_core_and_optional_dependencies():
    for relative in ("ci.yml", "extras.yml"):
        workflow = (_REPO / ".github/workflows" / relative).read_text(encoding="utf-8")
        assert "uv sync --locked" in workflow
        assert "uv run --locked" in workflow
        assert "pip install -e" not in workflow

    extras = (_REPO / ".github" / "workflows" / "extras.yml").read_text(
        encoding="utf-8"
    )
    assert 'UV_PYTHON: "3.11"' in extras

    security = (_REPO / ".github" / "workflows" / "security.yml").read_text(
        encoding="utf-8"
    )
    assert "uv sync --locked --extra dev --extra pdf --extra pose" in security
    assert "pip-audit==2.10.1" in security
    assert "pip-audit --local" in security
    assert "schedule:" in security

    for relative in ("ci.yml", "extras.yml", "security.yml"):
        workflow = (_REPO / ".github" / "workflows" / relative).read_text(
            encoding="utf-8"
        )
        assert "actions/checkout@v7" in workflow
        assert "actions/setup-python@v7" in workflow


def test_pose_extra_avoids_vulnerable_protobuf_and_unverified_python_versions():
    pyproject = (_REPO / "pyproject.toml").read_text(encoding="utf-8")
    lock = (_REPO / "uv.lock").read_text(encoding="utf-8")
    assert (
        'pose = ["mediapipe>=1.0.1,<2; python_version < \'3.13\'"]'
        in pyproject
    )
    assert '"protobuf>=6.33.5,<8"' in pyproject
    assert '"numpy>=2.3; python_version >= \'3.13\'"' in pyproject
    assert not re.search(r'name = "protobuf"\nversion = "[0-5]\.', lock)


def test_lock_contains_current_project_version():
    pyproject = (_REPO / "pyproject.toml").read_text(encoding="utf-8")
    lock = (_REPO / "uv.lock").read_text(encoding="utf-8")
    version = re.search(r'^version = "([^"]+)"$', pyproject, re.MULTILINE)
    assert version is not None
    package = re.search(
        r'\[\[package]]\nname = "crochet-photo2pattern"\nversion = "([^"]+)"',
        lock,
    )
    assert package is not None
    assert package.group(1) == version.group(1)


def test_public_streamlit_theme_is_present():
    config = (_REPO / ".streamlit/config.toml").read_text(encoding="utf-8")
    assert "[theme]" in config
    assert "primaryColor" in config


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


def test_no_real_api_keys_in_versionable_text_files():
    if shutil.which("git") is None:
        import pytest
        pytest.skip("git not available")
    try:
        out = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=_REPO, capture_output=True, text=True, check=True,
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
