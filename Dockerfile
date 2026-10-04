# ── 构建阶段：依赖按 uv.lock 精确安装并缓存 ─────────────────────────────
# 旧版 `pip install .` 会现场解析最新兼容版（openai/anthropic 无上界），
# 与 uv.lock 脱节；现在镜像与 CI/本地共用同一把锁。uv 经 pip 装入临时
# venv，避免为构建阶段引入第二个基础镜像。
# 基础镜像按 OCI index 摘要固定（供应链防篡改；2026-10-03 核对）。
# 刷新方式：docker buildx imagetools inspect python:3.12-slim 取新摘要，
# 更新两处并重建验证——这是有意的维护动作，不随 tag 自动漂移。
FROM python:3.12-slim@sha256:dddfd7e07f9d15aeeca61529320492139d21cac7f0070c00609243e51e4e0016 AS builder

# 弱网/受限出口下的稳健参数：延长 HTTP 超时、降低下载并发
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy \
    UV_HTTP_TIMEOUT=120 UV_CONCURRENT_DOWNLOADS=2
WORKDIR /app

RUN python -m venv /opt/uv-venv \
    && /opt/uv-venv/bin/pip install --no-cache-dir \
    --timeout 60 --retries 10 uv

# 先只拷依赖清单：pyproject/uv.lock 不变时该层缓存命中，代码改动不重装依赖
COPY pyproject.toml uv.lock ./
RUN /opt/uv-venv/bin/uv sync --locked --no-install-project --no-dev

COPY app ./app
COPY README.md LICENSE ./
RUN /opt/uv-venv/bin/uv sync --locked --no-dev

# ── 运行阶段：非 root + 健康检查 ────────────────────────────────────────
FROM python:3.12-slim@sha256:dddfd7e07f9d15aeeca61529320492139d21cac7f0070c00609243e51e4e0016

# opencv-headless 在 slim 基础镜像需要 libglib
RUN (apt-get update || (sleep 5 && apt-get update)) \
    && apt-get install -y --no-install-recommends libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 appuser

WORKDIR /app
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --chown=appuser:appuser app ./app
COPY --chown=appuser:appuser .streamlit ./.streamlit

ENV PATH="/app/.venv/bin:$PATH" \
    # 图解历史写 ~/.crochet_photo2pattern（appuser 家目录，可写）
    HOME=/home/appuser \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
# 内存参考：上传解码上限 2048px（utils.images MAX_DECODED_SIDE），典型容器
# 预算 512MB–1GB 即可；大图网格量化/GrabCut 峰值另见 docs/system-status.md。

USER appuser
EXPOSE 8501
# Key 通过环境变量注入（勿把 .env 打进镜像，见 .dockerignore）
CMD ["streamlit", "run", "app/main.py", "--server.address=0.0.0.0", "--server.port=8501"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
    CMD ["python", "-c", \
         "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=4)"]
