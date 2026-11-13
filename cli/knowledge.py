"""Opt-in local knowledge submission and durable retry queue (no credentials stored)."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx

from server.core.knowledge import safe_payload

MAX_ATTEMPTS = 5


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temp = path.with_name(path.name + "." + os.urandom(5).hex() + ".tmp")
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(temp, path)


def queue_dir():
    return Path(
        os.environ.get("TEAMKB_QUEUE_DIR", str(Path.home() / ".teamkb" / "queue"))
    )


def read_payload(path):
    path = Path(path)
    if path.stat().st_size > 240000:
        raise ValueError("候选文件过大，最多 240 KB")
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("候选必须是 JSON 对象")
    safe_payload(value)
    return value


def validate_agent(payload):
    from server.api.knowledge import Proposal

    payload = Proposal(**{**payload, "source": "agent"}).model_dump()
    from server.core.knowledge import KnowledgeService

    quality = KnowledgeService.quality(None, payload)
    if not quality["eligible"]:
        raise ValueError("材料不满足自动沉淀要求：" + ", ".join(quality["missing"]))
    safe_payload(payload)
    return payload


def queue_id(url, payload):
    return hashlib.sha256(
        (
            url.rstrip("/")
            + "\n"
            + json.dumps(payload, sort_keys=True, ensure_ascii=False)
        ).encode()
    ).hexdigest()


def enqueue(url, payload):
    parsed = urlparse(url)
    if parsed.scheme not in {"https", "http"} or parsed.username or parsed.password:
        raise ValueError("服务地址必须是不含凭据的 HTTP(S) URL")
    safe_payload(payload)
    directory = queue_dir()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    ident = queue_id(url, payload)
    path = directory / (ident + ".json")
    if not path.exists():
        if len(list(directory.glob("*.json"))) >= 100:
            raise ValueError("本地队列已达 100 条，请先处理")
        write_json(
            path,
            dict(
                id=ident,
                url=url.rstrip("/"),
                payload=payload,
                status="queued",
                attempts=0,
                next_retry_at=0,
                created_at=time.time(),
            ),
        )
    return path


def send(c, payload):
    # Credentials are resolved at delivery time, never persisted in queue files.
    parsed = urlparse(c.url)
    if parsed.scheme not in {"https", "http"} or parsed.username or parsed.password:
        raise ValueError("服务地址必须是不含凭据的 HTTP(S) URL")
    with httpx.Client(timeout=c.timeout, follow_redirects=False) as client:
        return client.post(
            c.url + "/api/v1/contributions", json=payload, headers=c._headers()
        )


def deliver(c, payload):
    path = enqueue(c.url, payload)
    entry = json.loads(path.read_text())
    if entry["status"] in {"blocked", "exhausted"}:
        return {
            "status": entry["status"],
            "queue_id": entry["id"],
            "message": "请处理错误后使用 wb queue retry --reset",
        }
    if entry["next_retry_at"] > time.time():
        return {
            "status": "queued",
            "queue_id": entry["id"],
            "next_retry_at": entry["next_retry_at"],
        }
    entry["attempts"] += 1
    try:
        response = send(c, payload)
        if 200 <= response.status_code < 300:
            result = response.json()
            path.unlink(missing_ok=True)
            return result
        status = response.status_code
        retryable = status == 429 or status >= 500
        # Keep only a status; avoid persisting server responses that might echo secrets.
        entry["last_error"] = "HTTP " + str(status)
        if not retryable:
            entry["status"] = "blocked"
        else:
            entry["status"] = "queued"
        retry_after = response.headers.get("retry-after", "")
        delay = max(
            2 ** entry["attempts"] * 30,
            min(float(retry_after), 86400) if retry_after.isdigit() else 0,
        )
    except (httpx.RequestError, ValueError) as exc:
        entry["last_error"] = type(exc).__name__
        entry["status"] = "queued"
        delay = 2 ** entry["attempts"] * 30
    if entry["attempts"] >= MAX_ATTEMPTS and entry["status"] == "queued":
        entry["status"] = "exhausted"
    entry["next_retry_at"] = time.time() + min(delay, 86400)
    write_json(path, entry)
    return {
        "status": entry["status"],
        "queue_id": entry["id"],
        "attempts": entry["attempts"],
        "message": entry["last_error"],
    }


def complete(c, project):
    root = Path(project).resolve()
    config = root / ".teamkb" / "config.json"
    if not config.exists():
        return {"status": "disabled", "message": "项目未启用自动沉淀"}
    if not config.resolve().is_relative_to(root):
        raise ValueError("项目配置必须位于当前项目内")
    options = json.loads(config.read_text())
    if options.get("enabled") is not True:
        return {"status": "disabled"}
    candidate = (
        root / options.get("candidate_file", ".teamkb/candidate.json")
    ).resolve()
    if not candidate.is_relative_to(root):
        raise ValueError("候选文件必须位于当前项目内")
    if not candidate.exists():
        return {"status": "skipped", "message": "没有待提交的候选方案"}
    payload = validate_agent(read_payload(candidate))
    ident = queue_id(c.url, payload)
    state = root / ".teamkb" / "submitted.json"
    previous = json.loads(state.read_text()) if state.exists() else {}
    if previous.get("id") == ident:
        return {"status": "unchanged", "result": previous.get("result")}
    result = deliver(c, payload)
    if result.get("status") not in {"queued", "blocked", "exhausted"}:
        write_json(
            state,
            dict(
                id=ident,
                result={
                    k: result.get(k)
                    for k in ["id", "status", "action", "published_doc_id"]
                },
            ),
        )
    return result


def cmd(c, a):
    if a.cmd == "categories":
        out = c.call("GET", "/api/v1/categories")
    elif a.cmd == "standards":
        out = c.call("GET", "/api/v1/standards")
    elif a.cmd == "contributions":
        out = c.call("GET", "/api/v1/contributions" + ("/" + a.id if a.id else ""))
    elif a.cmd == "propose":
        payload = read_payload(a.file)
        if a.draft:
            out = c.call("POST", "/api/v1/contributions?submit=false", payload)
        else:
            out = deliver(c, validate_agent(payload))
    elif a.cmd == "agent":
        if a.action == "init":
            root = Path(a.project).resolve()
            path = root / ".teamkb" / "config.json"
            if path.exists():
                raise ValueError("项目配置已存在，请直接编辑 enabled 开关")
            write_json(
                path, dict(enabled=True, candidate_file=".teamkb/candidate.json")
            )
            out = {
                "status": "enabled",
                "project": str(root),
                "candidate_file": ".teamkb/candidate.json",
            }
        else:
            out = complete(c, a.project)
    else:
        if a.action == "remove":
            import re

            if not a.id or not re.fullmatch("[a-f0-9]{64}", a.id):
                raise ValueError("请提供 queue list 返回的完整 QUEUE_ID")
            path = queue_dir() / (a.id + ".json")
            existed = path.exists()
            path.unlink(missing_ok=True)
            print(json.dumps({"removed": existed, "id": a.id}))
            return
        out = []
        for path in sorted(queue_dir().glob("*.json")):
            entry = json.loads(path.read_text())
            if a.action == "list":
                out.append(
                    {
                        k: entry.get(k)
                        for k in [
                            "id",
                            "url",
                            "status",
                            "attempts",
                            "next_retry_at",
                            "last_error",
                        ]
                    }
                )
                continue
            if entry["url"] != c.url:
                continue
            if a.reset:
                entry.update(status="queued", attempts=0, next_retry_at=0)
                write_json(path, entry)
            if entry["status"] == "queued":
                out.append(deliver(c, entry["payload"]))
    print(json.dumps(out, ensure_ascii=False, indent=2))


def register(sub):
    for name in [
        "categories",
        "standards",
        "contributions",
        "propose",
        "agent",
        "queue",
    ]:
        p = sub.add_parser(name, help="团队知识库 " + name)
        p.set_defaults(func=cmd, needs_client=True)
        if name == "contributions":
            p.add_argument("id", nargs="?", default="")
        if name == "propose":
            p.add_argument("file")
            p.add_argument("--draft", action="store_true")
        if name == "agent":
            p.add_argument("action", choices=["init", "complete"])
            p.add_argument("--project", default=".")
        if name == "queue":
            p.add_argument("action", choices=["list", "retry", "remove"])
            p.add_argument("id", nargs="?", default="")
            p.add_argument(
                "--reset",
                action="store_true",
                help="处理鉴权或材料问题后手动重置失败条目",
            )
