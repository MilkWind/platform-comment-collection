"""Copy-the-core demonstration: resolve a video and fetch one page of each kind.

    uv run python skills/bilibili/examples/quickstart.py BV1GJ411x7h7

Uses only ``core/bilicrawl`` — no engine, no UI.
"""

from __future__ import annotations

import sys
from pathlib import Path

CORE = Path(__file__).resolve().parent.parent / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

import bilicrawl  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: quickstart.py <BV id or URL> [cookie]", file=sys.stderr)
        return 2
    adapter = bilicrawl.create_adapter({"cookie": argv[2]} if len(argv) > 2 else {})

    auth = adapter.verify()
    print("logged in:", auth.is_logged_in)

    video = adapter.resolve_video(argv[1])
    print(f"title: {video.title}")
    print(f"aid: {video.aid} | parts: {len(video.parts)}")

    page = adapter.comment_page(mode=3)
    print(f"first page: {len(page.roots)} roots, total {page.total_all}")
    for comment in page.roots[:3]:
        row = adapter.to_row(comment, "comments", ["id", "user_name", "like_count", "content"])
        print("  ", row["user_name"], row["like_count"], row["content"][:30])

    targets = adapter.danmaku_targets()
    if targets:
        seg = adapter.danmaku_segment(targets[0])
        print(f"danmaku segment 1: {len(seg.items)} items")
        if seg.items:
            print("   first:", seg.items[0].content[:30])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
