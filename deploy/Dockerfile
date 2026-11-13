FROM node:22-alpine AS frontend
WORKDIR /web
COPY web/package*.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
COPY docs/ /docs/
RUN npm run build

FROM python:3.12-slim

WORKDIR /app

# 运行依赖先装，利用层缓存
COPY pyproject.toml ./
RUN pip install --no-cache-dir \
        "fastapi>=0.115" "uvicorn[standard]>=0.30" "pydantic>=2.7" \
        "httpx>=0.27" "pyyaml>=6.0" "python-multipart>=0.0.9" "mcp>=1.2"

COPY server ./server
COPY cli ./cli
COPY ingest ./ingest
COPY --from=frontend /web/dist ./web/dist

ENV V8WB_DATA_DIR=/data \
    V8WB_HOST=0.0.0.0 \
    V8WB_PORT=8770 \
    PYTHONUNBUFFERED=1

VOLUME ["/data"]
EXPOSE 8770

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8770/health',timeout=4).status==200 else 1)"

CMD ["python", "-c", "import uvicorn; uvicorn.run('server.api.http_app:app', host='0.0.0.0', port=8770, log_level='info')"]
