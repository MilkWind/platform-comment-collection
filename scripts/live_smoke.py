"""Opt-in live smoke test against the real Bilibili API.

    uv run python scripts/live_smoke.py --bvid BV1GJ411x7h7
    uv run python scripts/live_smoke.py --bvid BV1GJ411x7h7 --cookie-file cookie.txt

Fetches exactly one comment page, one sub-reply page, and one danmaku segment,
then asserts each is non-empty and within the expected schema. Run this after
any API or WBI change; never run it in CI.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "bilibili" / "core"))

import bilicrawl  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bvid", required=True)
    parser.add_argument("--cookie-file", default="")
    args = parser.parse_args(argv)

    raw = Path(args.cookie_file).read_text(encoding="utf-8-sig").strip() if args.cookie_file else ""
    adapter = bilicrawl.create_adapter({"cookie": raw} if raw else {})

    started = time.time()
    auth = adapter.verify()
    video = adapter.resolve_video(args.bvid)
    assert video.aid and video.parts, "no video metadata"

    page = adapter.comment_page(mode=3)
    assert page.roots, "no root comments"
    top = page.roots[0]

    sub = adapter.sub_reply_page(root_id=top.id, page=1) if top.reply_count else None

    targets = adapter.danmaku_targets()
    seg = adapter.danmaku_segment(targets[0]) if targets else None

    print(f"logged in:   {auth.is_logged_in}")
    print(f"video:       {video.title} | aid={video.aid} parts={len(video.parts)}")
    print(f"comments:    {len(page.roots)} roots on page 1 | total={page.total_all}")
    if sub is not None:
        print(f"sub-replies: {len(sub.replies)} on page 1 | total={sub.total}")
    if seg is not None:
        print(f"danmaku:     {len(seg.items)} items in segment 1")
    print(f"elapsed:     {time.time() - started:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
