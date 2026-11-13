#!/usr/bin/env bash
# Run after git pull. Preserve database, API Keys, service and TLS configuration.
set -euo pipefail
APP_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
bash "$APP_DIR/deploy/build-client.sh"
bash "$APP_DIR/deploy/build-web.sh"
systemctl restart v8wb
for attempt in $(seq 1 20); do
  if curl -fsS --max-time 3 http://127.0.0.1/health; then
    echo
    echo '更新完成；现有 API Key 与 HTTPS 配置保留。'
    exit 0
  fi
  sleep 1
done
echo '健康检查失败，请检查 systemctl status v8wb 和应用日志。' >&2
exit 1
