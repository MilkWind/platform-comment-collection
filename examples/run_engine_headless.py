"""Headless batch run without the UI.

    uv run python examples/run_engine_headless.py BV1GJ411x7h7 --max-roots 40
    uv run python examples/run_engine_headless.py <url> --cookie "$(cat cookie.txt)"

Demonstrates the engine applying the skill's strategies to a platform core.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.engine.job import CrawlJob, CrawlOptions, CrawlRequest  # noqa: E402
from app.ui import registry  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Headless comment/danmaku collection")
    parser.add_argument("input", help="BV id, av id, or a video URL")
    parser.add_argument("--platform", default="bilibili")
    parser.add_argument("--cookie", default="", help="cookie header, SESSDATA value, or cURL")
    parser.add_argument("--comments-only", action="store_true")
    parser.add_argument("--danmaku-only", action="store_true")
    parser.add_argument("--no-sub-replies", action="store_true")
    parser.add_argument("--mode", type=int, default=3, choices=[2, 3], help="2=time 3=hot")
    parser.add_argument("--max-roots", type=int, default=None)
    parser.add_argument("--preset", default="balanced", choices=["safe", "balanced", "fast"])
    parser.add_argument("--out", default="output")
    args = parser.parse_args(argv)

    entry = registry.get_platform(args.platform)
    if entry is None:
        print(f"unknown platform: {args.platform}", file=sys.stderr)
        return 2
    module = entry.module

    options = CrawlOptions(
        collect_comments=not args.danmaku_only,
        collect_sub_replies=not args.no_sub_replies,
        collect_danmaku=not args.comments_only,
        mode=args.mode,
        comment_fields=module.default_fields("comments"),
        danmaku_fields=module.default_fields("danmaku"),
        policies=__import__("app.engine.policy", fromlist=["Policies"]).Policies.for_preset(
            args.preset
        ),
        output_root=Path(args.out),
        max_roots=args.max_roots,
    )
    request = CrawlRequest(
        platform=entry.id,
        raw_input=args.input,
        credentials={"cookie": args.cookie} if args.cookie else {},
        options=options,
        adapter_factory=module.create_adapter,
    )
    job = CrawlJob(request)
    job.start()

    while job.is_running() or not job.events.empty():
        for event in job.drain():
            if event.kind == "log":
                print(f"[{event.level}] {event.message}")
            elif event.kind == "progress":
                total = event.total or 0
                pct = f"{event.done / total * 100:5.1f}%" if total else "  ?  "
                print(f"  {event.phase:9} {pct} {event.done}/{total or '?'} {event.message}")
            elif event.kind == "done":
                print("\nDONE", event.payload.get("counts"))
                print("output:", event.payload.get("out_dir"))
            elif event.kind in ("error", "cancelled"):
                print(f"\n{event.kind.upper()}: {event.message}", file=sys.stderr)
        if job.is_running():
            import time

            time.sleep(0.2)

    return 0 if job.result else 1


if __name__ == "__main__":
    raise SystemExit(main())
