#!/usr/bin/env bash
# Build separately so a failed build leaves the current website untouched.
set -euo pipefail
APP_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
command -v npm >/dev/null || { echo '需要 Node.js 20.19+ 和 npm'; exit 1; }
node -e 'const [major, minor] = process.versions.node.split(".").map(Number); if (major < 20 || (major === 20 && minor < 19) || (major === 22 && minor < 12)) { console.error("需要 Node.js 20.19+ 或 22.12+"); process.exit(1) }'
cd "$APP_DIR/web"
npm ci --no-audit --no-fund
npm run build -- --outDir .build
mkdir -p dist/assets
# Retain old hashed assets for already-open browser tabs.
for entry in .build/*; do
  [ "$(basename "$entry")" = "index.html" ] && continue
  cp -a "$entry" dist/
done
cp .build/index.html dist/index.html.next
mv -f dist/index.html.next dist/index.html
rm -rf .build
