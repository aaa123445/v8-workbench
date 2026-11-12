# 部署指南

## 前置要求

- 一台能公网访问或内网可达的 Linux 服务器
- Docker 20.10+ 与 Docker Compose v2
- 域名（可选，走 HTTPS 时需要）

服务器规格：1 核 1G 足够。工作台是轻量的——231 篇文档的索引只占几十 MB 内存。

## 一、容器部署（推荐）

```bash
git clone <repo> v8-workbench
cd v8-workbench/deploy

cp .env.example .env
```

生成初始管理员 key：

```bash
python3 -c "import secrets;print('wb_ad_'+secrets.token_urlsafe(24))"
```

填进 `.env` 的 `V8WB_BOOTSTRAP_ADMIN_KEY`。然后：

```bash
docker compose up -d
docker compose logs -f
```

看到 uvicorn 启动完成即可：

```bash
curl http://127.0.0.1:8770/health
# {"ok":true,"version":"0.1.0","documents":0,...}
```

`documents: 0` 是正常的，新库是空的。

## 二、导入知识

### 方式 A：导入现有语雀语料（推荐，离线）

如果你们本地已经有 `seeyon-v8-kk` skill 目录：

```bash
docker compose exec workbench \
  python ingest/load_corpus.py --skill-dir /data/seed
```

需要先把语料挂进容器。在 `docker-compose.yml` 的 volumes 加一行：

```yaml
volumes:
  - v8wb-data:/data
  - /path/to/seeyon-v8-kk:/data/seed:ro
```

231 篇导入约 3 秒。

### 方式 B：从语雀在线拉取

```bash
docker compose exec workbench \
  python -m cli.wb --url http://127.0.0.1:8770 \
  --key $V8WB_BOOTSTRAP_ADMIN_KEY sync
```

首次全量约 1-3 分钟。之后增量通常只有个位数。

如果知识库是私有的，在 `.env` 里设 `V8WB_YUQUE_TOKEN`。

### 验证

```bash
docker compose exec workbench \
  python -m cli.wb --url http://127.0.0.1:8770 \
  --key $V8WB_BOOTSTRAP_ADMIN_KEY search "组织同步"
```

## 三、签发日常用的 key

初始管理员 key 只用来做一次性配置，日常别用它。

```bash
# 团队只读
wb --url https://workbench.example.com --key <admin> key create team-reader --role reader

# 本地 agent 自动沉淀
wb key create local-agent --role writer --rpm 60 --daily 5000
```

key 只显示一次，记下来。

确认能用之后，把 `.env` 里的 `V8WB_BOOTSTRAP_ADMIN_KEY` 删掉并重启——虽然重复启动不会重复创建，但少一处泄露面总是好的。

## 四、配 HTTPS

工作台自己只监听 `127.0.0.1:8770`，对外走 Nginx。

```bash
# 证书
certbot certonly --standalone -d workbench.example.com

# 配置
sudo cp deploy/nginx.conf /etc/nginx/conf.d/v8wb.conf
sudo sed -i 's/workbench.example.com/你的域名/g' /etc/nginx/conf.d/v8wb.conf
sudo nginx -t && sudo systemctl reload nginx
```

`nginx.conf` 里已经做了两件事：
- `/docs` 和 `/openapi.json` 只允许内网访问
- 长请求超时给到 300s（语雀全量同步需要）

## 五、自动同步语雀

`.env` 里设：

```bash
V8WB_YUQUE_ENABLED=true
V8WB_YUQUE_INTERVAL_MIN=1440    # 每天一次
```

重启生效。同步在后台线程跑，容器启动时如果距上次超过间隔会先补一次。

看同步状态：

```bash
docker compose logs workbench | grep -i yuque
```

## 六、备份

所有数据在 `v8wb-data` 这个 volume 里，核心是一个 SQLite 文件。

```bash
# 热备份（WAL 模式下安全）
docker compose exec workbench \
  python -c "import sqlite3;s=sqlite3.connect('/data/v8wb.sqlite3');d=sqlite3.connect('/data/backup.sqlite3');s.backup(d)"

docker compose cp workbench:/data/backup.sqlite3 ./backup-$(date +%F).sqlite3
```

建议加进 crontab，每天一次。

恢复：把文件拷回 `/data/v8wb.sqlite3`，重启容器。

## 七、升级

```bash
git pull
docker compose build
docker compose up -d
```

数据在 volume 里，不受影响。索引会在启动时自动重建。

## 不用 Docker 的方式

```bash
python3.12 -m venv /opt/v8wb-venv
/opt/v8wb-venv/bin/pip install fastapi "uvicorn[standard]" pydantic httpx pyyaml python-multipart "mcp>=1.2"

# 装成 systemd 服务
sudo tee /etc/systemd/system/v8wb.service <<'EOF'
[Unit]
Description=V8 Workbench
After=network.target

[Service]
Type=simple
User=v8wb
WorkingDirectory=/opt/v8-workbench
Environment=V8WB_DATA_DIR=/var/lib/v8wb
Environment=V8WB_HOST=127.0.0.1
Environment=V8WB_PORT=8770
Environment=V8WB_BOOTSTRAP_ADMIN_KEY=<初始管理员key>
ExecStart=/opt/v8wb-venv/bin/python -c "import uvicorn; uvicorn.run('server.api.http_app:app', host='127.0.0.1', port=8770)"
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now v8wb
```

## 排错

**连不上**：确认 `docker compose ps` 里服务健康，`curl 127.0.0.1:8770/health` 有响应。外网连不上但本地能通，是 Nginx 或安全组的问题。

**401**：key 不对或已吊销。`wb key list` 看 key 前缀是否存在。注意 key 只在创建时显示一次。

**429**：配额超了。`wb key create` 时调大 `--rpm` / `--daily`，或者等次日重置。

**检索不到**：先 `wb stats` 看文档数是否为 0。为 0 说明知识没导入。有文档但搜不到，换更短的术语重试——完整句子会稀释 bigram 权重。

**语雀同步失败**：常见是公开 API 对个别文档返回 403/404，这是已知情况，不影响整体。看返回里的 `errors` 字段确认是不是个别文档。

**索引不更新**：写入后索引会自动重建。如果手动改了数据库，调 `POST /api/v1/admin/rebuild`。

## 安全清单

上线前逐项确认：

- [ ] `V8WB_BOOTSTRAP_ADMIN_KEY` 已从环境变量移除
- [ ] 日常使用 `reader` / `writer` key，不用 admin key
- [ ] 工作台只监听 `127.0.0.1`，对外走带 TLS 的反代
- [ ] `/docs` 和 `/openapi.json` 限制内网访问
- [ ] 每日配额已按实际用量设置，防止 key 泄露后被刷
- [ ] `v8wb-data` volume 有定期备份
- [ ] 服务器防火墙只开 443（和 22）
