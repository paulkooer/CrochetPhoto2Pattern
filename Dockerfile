FROM python:3.12-slim

# opencv-headless 在 slim 基础镜像需要 libglib
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir .

EXPOSE 8501
# Key 通过环境变量注入（勿把 .env 打进镜像，见 .dockerignore）
CMD ["streamlit", "run", "app/main.py", "--server.address=0.0.0.0", "--server.port=8501"]
