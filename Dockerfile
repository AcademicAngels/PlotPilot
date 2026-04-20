# ── 阶段 1: 前端构建 ──
FROM node:20-alpine AS frontend-builder
WORKDIR /build
ARG NPM_REGISTRY=https://registry.npmjs.org
RUN npm config set registry ${NPM_REGISTRY}
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── 阶段 2: 生产镜像 ──
FROM python:3.12-slim AS production
WORKDIR /app

ARG PIP_INDEX_URL=https://pypi.org/simple

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc build-essential && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -i ${PIP_INDEX_URL} -r requirements.txt

COPY . .
COPY --from=frontend-builder /build/dist/ ./frontend/dist/

RUN mkdir -p data

ENV PYTHONPATH=/app

EXPOSE 8005
CMD ["python", "-m", "uvicorn", "interfaces.main:app", "--host", "0.0.0.0", "--port", "8005"]
