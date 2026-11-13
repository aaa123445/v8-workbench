"""Import the V5 skill's bundled source pages, including CTP omitted by its index."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server.core.docs import DocInput

REPOSITORY = "https://github.com/aaa123445/seeyon-kk-skill"
SITES = {
    "v5devCTP": "CTP 技术平台",
    "seeyonapi": "REST 与 OpenAPI",
    "v5devCAP": "CAP 表单与应用",
    "v5devCIP": "CIP 集成平台",
    "v5devUIComp": "UI 组件库",
    "cmpdev": "CMP 移动开发",
    "v5devCMP": "移动平台与微协同",
    "v5doc": "部署运维",
    "v5doc2": "产品与文档中心",
}
SECTION = re.compile(
    r"^## (\d+)\. ([^\n]+)\n\n(> (?:原始路径|路由)：`([^`]+)`[^\n]*\n(?:>[^\n]*\n)*)",
    re.M,
)
LINK = re.compile(r"(!?\[[^\]\n]*\]\()([^\s)]+)(\))")
FETCH_FAILURE = re.compile(r"未能获取\s*Markdown", re.I)


def parse_corpus(root: Path, revision: str = "", cmp_snapshot: dict | None = None):
    documents = {}
    report = Counter()
    by_site = Counter()
    for site, name in SITES.items():
        path = root / "resources" / "docs" / f"{site}_文档汇总.md"
        text = path.read_text(encoding="utf-8")
        expected = re.search(r"提取文档数：\s*(\d+)", text)
        matches = list(SECTION.finditer(text))
        if not expected or len(matches) != int(expected[1]):
            raise ValueError(f"{site}: section count does not match declared count")
        for i, match in enumerate(matches):
            report["sections"] += 1
            title, route = match[2].strip(), match[4].strip()
            body = text[
                match.end() : matches[i + 1].start()
                if i + 1 < len(matches)
                else len(text)
            ].strip()
            if route.startswith("/quickStart/"):
                report["demo_skipped"] += 1
                continue
            snapshot = (cmp_snapshot or {}).get(route) if site == "cmpdev" else None
            if FETCH_FAILURE.search(body):
                if not snapshot or not snapshot.get("body", "").strip():
                    report["fetch_failed_skipped"] += 1
                    continue
                body = snapshot["body"]
                if FETCH_FAILURE.search(body):
                    raise ValueError(f"Recovered content still contains a fetch failure: {route}")
                report["fetch_recovered"] += 1
            if not re.sub(r"^\s*#+[^\n]*", "", body, flags=re.M).strip():
                report["empty_skipped"] += 1
                continue
            base = f"https://open.seeyoncloud.com/{site}/"
            if site == "cmpdev":
                url = snapshot["url"] if snapshot else base + "#/" + route.lstrip("/")
                # CMP embeds assets relative to its application root.
                link_base = base
            else:
                url = base + route.lstrip("/")
                link_base = url

            def absolute(m):
                value = m[2]
                if value.startswith(("#", "https://", "http://", "mailto:", "data:")):
                    return m[0]
                return m[1] + urljoin(link_base, value) + m[3]

            body = LINK.sub(absolute, body)
            did = (
                "seeyon-v5:"
                + hashlib.sha256((site + "\n" + route).encode()).hexdigest()[:24]
            )
            if did in documents:
                old = documents[did]
                if old.body != body:
                    raise ValueError(f"Conflicting duplicate route: {site} {route}")
                old.meta.setdefault("title_aliases", []).append(title)
                report["duplicates"] += 1
                continue
            documents[did] = DocInput(
                id=did,
                title=title,
                body=body,
                source="seeyon-v5",
                category_id="v5-" + site.lower(),
                path_text=f"技术平台 > 致远 V5 > {name} > {title}",
                url=url,
                tags=["致远 V5", site],
                created_by="v5-corpus-import",
                meta={
                    "origin_repository": REPOSITORY,
                    "origin_revision": revision,
                    "origin_file": str(path.relative_to(root)),
                    "origin_route": route,
                    "platform": "V5",
                    "site": site,
                    **({"recovered_from": snapshot["url"], "capture_sources": snapshot.get("sources", [])} if snapshot else {}),
                },
            )
            by_site[site] += 1
    report["documents"] = len(documents)
    return list(documents.values()), {**report, "by_site": dict(by_site)}


def import_corpus(container, documents):
    now = time.time()
    with container.db.write() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO categories(id,name,parent_id,sort_order,created_at) VALUES (?,?,?,?,?)",
            ("seeyon-v5", "致远 V5", "platforms", 20, now),
        )
        for i, (site, name) in enumerate(SITES.items()):
            conn.execute(
                "INSERT OR IGNORE INTO categories(id,name,parent_id,sort_order,created_at) VALUES (?,?,?,?,?)",
                ("v5-" + site.lower(), name, "seeyon-v5", 100 + i, now),
            )
    result = Counter()
    for doc in documents:
        result[container.repo.upsert(doc).action] += 1
    return dict(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill-dir", type=Path, required=True)
    parser.add_argument("--revision", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--cmp-snapshot", type=Path, help="Verified CMP recovery snapshot (JSON)")
    args = parser.parse_args()
    snapshot = json.loads(args.cmp_snapshot.read_text()) if args.cmp_snapshot else None
    documents, report = parse_corpus(args.skill_dir, args.revision, snapshot)
    if not args.dry_run:
        from server.core.container import get_container

        c = get_container()
        report["import"] = import_corpus(c, documents)
        report["indexed"] = c.rebuild_index()
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
