#!/usr/bin/env bash
# TeamKB 团队知识共享平台服务器安装脚本
#
# 前提：项目已上传到 /opt/v8-workbench，且 80 端口已空闲
# 用法：sudo bash /opt/v8-workbench/deploy/install.sh
#
# 停用旧的 80 端口服务不在本脚本内，请先手动执行：
#   systemctl stop nginx && systemctl disable nginx
# （或你实际使用的 web 服务名）

set -euo pipefail

APP_DIR=/opt/v8-workbench
DATA_DIR=/var/lib/v8wb
LOG_DIR=/var/log/v8wb
SVC_USER=v8wb
PORT=80

log()  { printf '\033[36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33m!!\033[0m %s\n' "$*"; }
die()  { printf '\033[31mxx\033[0m %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "需要 root：sudo bash $0"
[ -d "$APP_DIR/server" ] || die "找不到 $APP_DIR/server，请先上传项目"

# 1. Python 3.11+
log "检查 Python"
PY=""
for c in python3.12 python3.11 python3; do
  command -v "$c" >/dev/null 2>&1 || continue
  v=$("$c" -c 'import sys;print("%d.%d"%sys.version_info[:2])' 2>/dev/null || echo 0.0)
  if [ "${v%%.*}" = "3" ] && [ "${v##*.}" -ge 11 ]; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  log "未找到 Python 3.11+，安装中"
  if   command -v apt-get >/dev/null 2>&1; then apt-get update -qq && apt-get install -y -qq python3 python3-venv python3-pip
  elif command -v dnf     >/dev/null 2>&1; then dnf install -y -q python3 python3-pip
  elif command -v yum     >/dev/null 2>&1; then yum install -y -q python3 python3-pip
  else die "请手动安装 Python 3.11+"; fi
  PY=python3
fi
log "使用 $PY ($($PY -V 2>&1))"

# 2. 用户与目录
log "准备用户与目录"
id -u "$SVC_USER" >/dev/null 2>&1 || useradd -r -s /bin/false -d "$APP_DIR" "$SVC_USER"
mkdir -p "$DATA_DIR" "$LOG_DIR"
chown -R "$SVC_USER":"$SVC_USER" "$DATA_DIR" "$LOG_DIR"

# 3. 依赖
log "安装 Python 依赖"
[ -d "$APP_DIR/.venv" ] || "$PY" -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install -q --upgrade pip
"$APP_DIR/.venv/bin/pip" install -q \
    "fastapi>=0.115" "uvicorn[standard]>=0.30" "pydantic>=2.7" \
    "httpx>=0.27" "pyyaml>=6.0" "python-multipart>=0.0.9" "mcp>=1.2"
chown -R "$SVC_USER":"$SVC_USER" "$APP_DIR"

# 3b. 构建 Vue 前端（Node 仅用于构建，运行时仍由 FastAPI 提供静态文件）
log "构建前端"
if ! command -v npm >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then
    apt-get update -qq && apt-get install -y -qq nodejs npm
  else
    die "请先安装 Node.js 20.19+ 和 npm"
  fi
fi
bash "$APP_DIR/deploy/build-client.sh"
bash "$APP_DIR/deploy/build-web.sh"
chown -R "$SVC_USER":"$SVC_USER" "$APP_DIR/web"

# 4. 端口检查（只检查，不处理）
if command -v ss >/dev/null 2>&1 && ss -lnt 2>/dev/null | awk '{print $4}' | grep -qE ':80$'; then
  warn "80 端口被占用："
  ss -lntp 2>/dev/null | grep -E ':80\s' | sed 's/^/    /' || true
  die "请先停用占用 80 的服务，再重新运行本脚本"
fi

# 5. systemd
log "写入 systemd 服务"
ADMIN_KEY="wb_ad_$(head -c 48 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 40)"

cat > /etc/systemd/system/v8wb.service <<UNIT
[Unit]
Description=V8 Workbench
After=network.target

[Service]
Type=simple
User=$SVC_USER
Group=$SVC_USER
WorkingDirectory=$APP_DIR
Environment=V8WB_DATA_DIR=$DATA_DIR
Environment=V8WB_HOST=0.0.0.0
Environment=V8WB_PORT=$PORT
Environment=V8WB_REQUIRE_AUTH=true
Environment=V8WB_BOOTSTRAP_ADMIN_KEY=$ADMIN_KEY
Environment=V8WB_YUQUE_ENABLED=true
Environment=V8WB_YUQUE_BOOK=seeyonkk/v8
Environment=V8WB_YUQUE_INTERVAL_MIN=1440
Environment=PYTHONUNBUFFERED=1
Environment=TZ=Asia/Shanghai
AmbientCapabilities=CAP_NET_BIND_SERVICE
CapabilityBoundingSet=CAP_NET_BIND_SERVICE
NoNewPrivileges=true
ExecStart=$APP_DIR/.venv/bin/python -c "import uvicorn; uvicorn.run('server.api.http_app:app', host='0.0.0.0', port=$PORT, log_level='info')"
Restart=always
RestartSec=5
StandardOutput=append:$LOG_DIR/app.log
StandardError=append:$LOG_DIR/app.log

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable v8wb >/dev/null 2>&1
systemctl restart v8wb

log "等待启动"
OK=0
for _ in $(seq 1 30); do
  if curl -sf --max-time 2 "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then OK=1; break; fi
  sleep 1
done
if [ "$OK" != "1" ]; then
  warn "健康检查失败，最近日志："
  tail -30 "$LOG_DIR/app.log" 2>/dev/null || true
  die "启动失败"
fi

log "服务已启动"
curl -s "http://127.0.0.1:$PORT/health"; echo

# 6. 填充知识库
# 优先用本地种子语料（如果存在），否则从语雀在线拉取。
if [ -d "$APP_DIR/seed/references" ]; then
  log "导入本地种子语料"
  sudo -u "$SVC_USER" env V8WB_DATA_DIR="$DATA_DIR" \
    "$APP_DIR/.venv/bin/python" "$APP_DIR/ingest/load_corpus.py" \
    --skill-dir "$APP_DIR/seed" 2>&1 | tail -5 || warn "语料导入失败"
else
  log "从语雀拉取知识库（首次全量约 1-3 分钟）"
  # 必须 cd 到 APP_DIR：heredoc 里的 import 依赖 cwd 在 sys.path 上，
  # 否则从任意目录执行本脚本都会 ModuleNotFoundError。
  sudo -u "$SVC_USER" env V8WB_DATA_DIR="$DATA_DIR" V8WB_YUQUE_BOOK=seeyonkk/v8 \
    sh -c "cd '$APP_DIR' && '$APP_DIR/.venv/bin/python' -" <<'PYSYNC' 2>&1 | tail -10 || warn "语雀同步失败，稍后可在管理页重试"
import sys
sys.path.insert(0, ".")

from server.core.container import get_container
from server.core.yuque import sync_book

c = get_container()
stat = sync_book(c.repo, "seeyonkk/v8", actor="install")
print(f"目录 {stat['toc']}  实抓 {stat['fetched']}  新增 {stat['created']}  "
      f"更新 {stat['updated']}  失败 {stat['failed']}")
if stat.get("errors"):
    for e in stat["errors"][:5]:
        print(f"  x {e['title']}: {e['error']}")
print("索引重建:", c.rebuild_index())
PYSYNC
fi

systemctl restart v8wb
for _ in $(seq 1 20); do
  curl -sf --max-time 2 "http://127.0.0.1:$PORT/health" >/dev/null 2>&1 && break
  sleep 1
done
log "当前知识库："
curl -s "http://127.0.0.1:$PORT/health"; echo

# 7. 保存凭据
umask 077
cat > /etc/v8wb.conf <<CONF
V8WB_ADMIN_KEY=$ADMIN_KEY
V8WB_URL=http://127.0.0.1:$PORT
CONF
chmod 600 /etc/v8wb.conf

cat <<EOF

========================================
  工作台已就绪

  页面      http://<你的域名>/
  API 文档  http://<你的域名>/docs

  初始管理员 Key（只显示这一次）：

      $ADMIN_KEY

  已保存到 /etc/v8wb.conf

  下一步
   1. 打开域名，右上角填入这个 Key
   2. 在「管理」页创建日常用的 reader / writer Key
   3. 之后编辑 /etc/systemd/system/v8wb.service，
      删除 V8WB_BOOTSTRAP_ADMIN_KEY 那一行，
      再 systemctl daemon-reload && systemctl restart v8wb

  日志  $LOG_DIR/app.log
  数据  $DATA_DIR
========================================

EOF
