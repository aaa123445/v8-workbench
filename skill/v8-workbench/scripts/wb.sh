#!/usr/bin/env bash
# v8-workbench CLI 包装。
# 作用：把配置从固定位置读出来，让 agent 不用每次传 --url / --key。
#
# 配置查找顺序：
#   1. 已有环境变量 V8WB_URL / V8WB_KEY
#   2. ~/.v8wb/config     （KEY=VALUE 格式）
#   3. ./.v8wb            （项目级覆盖，便于一个仓库连不同环境）

set -euo pipefail

_load_cfg() {
  local f="$1"
  [ -f "$f" ] || return 0
  while IFS='=' read -r k v; do
    case "$k" in
      ''|\#*) continue ;;
    esac
    k="$(echo "$k" | tr -d '[:space:]')"
    v="$(echo "$v" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's/^["'\'']//' -e 's/["'\'']$//')"
    case "$k" in
      V8WB_URL) : "${V8WB_URL:=$v}" ;;
      V8WB_KEY) : "${V8WB_KEY:=$v}" ;;
    esac
  done < "$f"
}

_load_cfg "$HOME/.v8wb/config"
_load_cfg "./.v8wb"

export V8WB_URL="${V8WB_URL:-http://127.0.0.1:8770}"
export V8WB_KEY="${V8WB_KEY:-}"

# 优先用已安装的 wb，回退到 python -m
if command -v wb >/dev/null 2>&1; then
  exec wb "$@"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
if [ -x "$ROOT/.venv/bin/python" ]; then
  exec "$ROOT/.venv/bin/python" -m cli.wb "$@"
fi
exec python3 -m cli.wb "$@"
