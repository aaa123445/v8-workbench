"""Stable V8 source taxonomy shared by migration and future Yuque imports."""

from __future__ import annotations

import json
import time

V8_CATEGORIES = [
    ("preparation", "开发准备"),
    ("standards", "开发规范"),
    ("development", "开发文档"),
    ("extensions", "扩展能力"),
    ("integration", "集成平台"),
    ("udc", "UDC平台"),
    ("bpm", "BPM平台"),
    ("portal", "门户平台"),
    ("components", "业务组件"),
    ("mobile", "移动端开发"),
    ("documents", "文会事"),
    ("migration", "数据迁移"),
    ("v5-integration", "V5V8融合"),
    ("debugging", "开发调试"),
    ("resources", "服务与资源查询"),
    ("cases", "真实案例库"),
    ("production", "线上问题总结"),
    ("utilities", "复用工具"),
    ("overview", "知识大纲"),
]
BY_PATH = {name: "v8-" + key for key, name in V8_CATEGORIES}
BY_PATH["V8知识大纲进度跟踪表"] = "v8-overview"


def category_for_path(path: str) -> str:
    return BY_PATH.get((path or "").split(" > ", 1)[0].strip(), "seeyon-v8")


def initialize_v8_categories(conn):
    now = time.time()
    for i, (key, name) in enumerate(V8_CATEGORIES):
        conn.execute(
            "INSERT OR IGNORE INTO categories(id,name,parent_id,sort_order,created_at) VALUES (?,?,?,?,?)",
            ("v8-" + key, name, "seeyon-v8", 100 + i, now),
        )
    # Only migrate uncategorized V8 roots; preserve deliberate manual assignments.
    rows = conn.execute(
        "SELECT id,path_text FROM docs WHERE category_id='seeyon-v8'"
    ).fetchall()
    moved = 0
    for row in rows:
        cid = category_for_path(row["path_text"])
        if cid == "seeyon-v8":
            continue
        conn.execute("UPDATE docs SET category_id=? WHERE id=?", (cid, row["id"]))
        conn.execute(
            "INSERT INTO knowledge_audit(actor,action,target,details,created_at) VALUES (?,?,?,?,?)",
            (
                "migration",
                "v8_classify",
                row["id"],
                json.dumps({"from": "seeyon-v8", "to": cid}),
                now,
            ),
        )
        moved += 1
    return moved
