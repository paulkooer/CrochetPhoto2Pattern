"""共享测试夹具（F33）——测试套件 hermetic：任何环境配置都不得让
测试发出真实网络请求或产生计费。

根因：ImageParser.__init__ 无条件 load_dotenv() 并回落 os.getenv，
开发机 shell/.env 里的 OPENAI_API_KEY 会让未显式注入假 SDK 的用例
（如 test_cli_batch_directory）真实调用付费 Vision API。autouse 夹具
从进程环境摘除全部外部 Key 并禁用 load_dotenv——显式注入假 SDK 或
setenv 的用例不受影响。
"""
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
    # delenv 之后 load_dotenv() 会把 .env 里的 Key 重新灌入——禁用之
    monkeypatch.setattr("app.models.image_parser.load_dotenv",
                        lambda *a, **k: False)
    # 历史库重定向到每测试独立的临时目录（G5：相对路径会在仓库根产出
    # 文件且未 gitignore；固定 /tmp 路径在并行/多用户环境下互相踩踏）
    monkeypatch.setenv("CROCHET_HISTORY_DB", str(tmp_path / "history.db"))
    # Ordinary pipeline tests must not download pose weights or write to the
    # developer's model cache. Dedicated cache tests override this explicitly.
    monkeypatch.setenv("CROCHET_POSE_MODEL", str(tmp_path / "unconfigured-pose.task"))
