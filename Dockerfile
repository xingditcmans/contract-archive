# ============================================================
#  合同归档管理系统 — Docker 镜像
#  构建: docker build -t contract-archive .
#  运行: docker-compose up -d
# ============================================================
FROM python:3.12-slim

# 配置 apt 和 pip 国内镜像源（加速安装）
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || true \
    && pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/

LABEL maintainer="contract-archive"
LABEL description="合同归档管理系统 Docker 镜像 — FastAPI + Vue 3 + SQLite"

# --------------- 系统依赖 ---------------
# PyMuPDF 需要 libgl1 + libglib；Tesseract 用于 OCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-chi-sim \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# --------------- Python 依赖 ---------------
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --------------- 复制应用代码 ---------------
COPY backend/ /app/backend/
COPY frontend/dist/ /app/frontend/dist/

# --------------- 运行时 ---------------
WORKDIR /app/backend

# 创建必要目录
RUN mkdir -p data uploads logs

EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -sf http://localhost:8000/health || exit 1

# 启动命令（uvicorn 在 Python 包内，用 -m 方式调用）
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
