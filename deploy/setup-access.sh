#!/usr/bin/env bash
# 一次性配置：生成本机专用 SSH 密钥，并把公钥装到目标服务器。
#
# 用法（在你自己终端里跑，会提示输一次服务器密码）：
#   bash deploy/setup-access.sh root@129.153.88.107
#
# 跑完后本目录下会有 .deploy/id_ed25519，后续免密登录。

set -euo pipefail

TARGET="${1:-root@129.153.88.107}"
KEY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/.deploy"
KEY="$KEY_DIR/id_ed25519"

mkdir -p "$KEY_DIR"
chmod 700 "$KEY_DIR"

if [ ! -f "$KEY" ]; then
  echo "==> 生成密钥 $KEY"
  ssh-keygen -t ed25519 -f "$KEY" -N "" -C "v8-workbench-deploy"
else
  echo "==> 密钥已存在，复用 $KEY"
fi

echo "==> 将公钥安装到 $TARGET（需要输入服务器密码）"
ssh-copy-id -i "$KEY.pub" "$TARGET" 2>/dev/null || {
  # 有些精简系统没有 ssh-copy-id，手工追加
  PUB="$(cat "$KEY.pub")"
  ssh "$TARGET" "mkdir -p ~/.ssh && chmod 700 ~/.ssh && grep -qxF '$PUB' ~/.ssh/authorized_keys 2>/dev/null || echo '$PUB' >> ~/.ssh/authorized_keys; chmod 600 ~/.ssh/authorized_keys"
}

echo "==> 验证免密登录"
if ssh -i "$KEY" -o BatchMode=yes -o ConnectTimeout=10 "$TARGET" 'echo OK; uname -a; cat /etc/os-release 2>/dev/null | head -3'; then
  echo
  echo "✅ 配置完成。SSH 密钥：$KEY"
else
  echo "❌ 免密登录失败，请检查服务器是否允许密钥登录" >&2
  exit 1
fi
