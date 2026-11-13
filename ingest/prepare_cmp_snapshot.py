"""Merge verified Markdown and browser captures into an importer recovery snapshot.

Install the optional conversion tool: pip install 'markdownify>=1.2,<2'
Usage: python ingest/prepare_cmp_snapshot.py --markdown direct.json --capture rendered.json --output recovered.json
"""
import argparse
import json
from pathlib import Path


def main():
    from bs4 import BeautifulSoup
    from markdownify import markdownify

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--markdown", type=Path, required=True)
    parser.add_argument("--capture", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    snapshot = json.loads(args.markdown.read_text())
    for file in args.capture:
        for route, item in json.loads(file.read_text()).items():
            soup = BeautifulSoup(item["html"], "html.parser")
            for node in soup(["script", "style", "noscript", "iframe"]):
                node.decompose()
            if len(soup.get_text(" ", strip=True)) < 60:
                continue
            snapshot[route] = {
                "body": markdownify(str(soup), heading_style="ATX").strip(),
                "url": item["url"],
                "sources": item["sources"],
            }
    for route, item in snapshot.items():
        if not item["body"].strip() or "未能获取 Markdown" in item["body"]:
            raise ValueError(f"Invalid recovered content: {route}")
    args.output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2))
    print(f"Verified snapshot: {len(snapshot)} documents")


if __name__ == "__main__":
    main()
