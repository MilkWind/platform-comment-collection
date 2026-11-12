"""Minimal paging loop using ONLY core primitives (no engine, no UI).

    uv run python skills/bilibili/examples/comments_to_jsonl.py BV1GJ411x7h7 comments.jsonl

Demonstrates how small the "copy-the-core" integration can be: the core does
one request per call, and you own pacing/retries here.
"""

from __future__ import annotations

import dataclasses
import json
import sys
import time
from pathlib import Path

CORE = Path(__file__).resolve().parent.parent / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

import bilicrawl  # noqa: E402

DELAY = 1.0  # seconds between requests; keep it polite


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: comments_to_jsonl.py <BV id or URL> [out.jsonl]", file=sys.stderr)
        return 2
    out = Path(argv[2]) if len(argv) > 2 else Path("comments.jsonl")

    adapter = bilicrawl.create_adapter({})
    adapter.resolve_video(argv[1])

    seen: set[str] = set()
    cursor = None
    written = 0
    with out.open("w", encoding="utf-8") as fh:
        while True:
            page = adapter.comment_page(cursor=cursor, mode=3)
            new = [c for c in [*page.pinned, *page.roots] if c.id not in seen]
            for comment in new:
                seen.add(comment.id)
                fh.write(json.dumps(dataclasses.asdict(comment), ensure_ascii=False) + "\n")
            written += len(new)
            print(f"\r{written} comments", end="", flush=True)
            if page.is_end or not page.next_cursor:
                break
            cursor = page.next_cursor
            time.sleep(DELAY)
    print(f"\nsaved {written} roots to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
