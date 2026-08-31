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
def _hermetic_env(monkeypatch):
    for name in _EXTERNAL_ENV:
        monkeypatch.delenv(name, raising=False)
    # delenv 之后 load_dotenv() 会把 .env 里的 Key 重新灌入——禁用之
    monkeypatch.setattr("app.models.image_parser.load_dotenv",
                        lambda *a, **k: False)
    # 历史库重定向到临时目录（G5：相对路径会在仓库根产出文件且未 gitignore）
    monkeypatch.setenv("CROCHET_HISTORY_DB", "/tmp/_c2p_test_history.db")
