#!/usr/bin/env python3
"""把已有的 seeyon-v8-kk 语料导入工作台。

你们本地的 seeyon-v8-kk skill 里已经打包了 232 篇语雀文档和完整索引，
这是冷启动的最佳种子。导入后即可离线检索，不必等语雀同步跑完。

用法：
  python3 ingest/load_corpus.py \
      --skill-dir "/Users/ljc/work/项目文档/大区IA/V8人天评估智能体/v8-human-day-estimator/skills/seeyon-v8-kk"

之后可以再跑 `wb sync` 用在线语雀做增量更新。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server.core.container import get_container  # noqa: E402
from server.core.docs import DocInput  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill-dir", required=True, help="seeyon-v8-kk 目录")
    ap.add_argument("--rebuild", action="store_true", help="导入后重建索引")
    args = ap.parse_args()

    skill = Path(args.skill_dir)
    index_file = skill / "references" / "v8-doc-index.json"
    docs_dir = skill / "resources" / "docs"
    if not index_file.exists():
        print(f"找不到索引文件：{index_file}", file=sys.stderr)
        return 1
    if not docs_dir.exists():
        print(f"找不到正文目录：{docs_dir}", file=sys.stderr)
        return 1

    entries = json.loads(index_file.read_text(encoding="utf-8"))
    docs = [e for e in entries if e.get("type") == "DOC" and e.get("file")]
    print(f"索引共 {len(entries)} 条，其中 DOC {len(docs)} 篇")

    c = get_container()
    ok = skipped = missing = 0
    failed: list[tuple[str, str]] = []

    for e in docs:
        f = docs_dir / e["file"]
        if not f.exists():
            missing += 1
            continue
        body = f.read_text(encoding="utf-8", errors="replace")
        if not body.strip():
            skipped += 1
            continue
        try:
            c.repo.upsert(
                DocInput(
                    id=f"yuque:{e['doc_id']}" if e.get("doc_id") else None,
                    title=e.get("title") or f.stem,
                    body=body,
                    source="yuque",
                    path_text=e.get("path_text") or "",
                    url=f"https://www.yuque.com/seeyonkk/v8/{e.get('url', '')}",
                    meta={
                        "yuque_doc_id": e.get("doc_id"),
                        "yuque_updated_at": e.get("updated_at", ""),
                        "origin_skill": "seeyon-v8-kk",
                    },
                    # 不在这里传 version_hint：统一交给 DocRepo._infer_version 从正文推断。
                    # 这里若自己抽，会和正文推断逻辑分叉（比如丢掉"以下/以上"限定词）。
                    created_by="corpus-import",
                )
            )
            ok += 1
        except Exception as exc:  # noqa: BLE001
            failed.append((e.get("title", "?"), str(exc)[:120]))

    n = c.rebuild_index()
    print(f"\n导入成功 {ok}  跳过(空) {skipped}  缺文件 {missing}  失败 {len(failed)}")
    print(f"索引已重建，当前 {n} 篇可检索")
    for t, err in failed[:10]:
        print(f"  ✗ {t}: {err}")
    return 0


def _version_from(e: dict) -> str:
    """从 description 里抽适用版本，语雀文档开头常有『适用版本：3.18』。"""
    import re

    desc = e.get("description") or ""
    m = re.search(r"适用版本[：:]\s*(\d+\.\d+)", desc)
    return m.group(1) if m else ""


if __name__ == "__main__":
    sys.exit(main())
