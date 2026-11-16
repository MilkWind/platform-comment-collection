"""Headless run without the UI — one video or a whole list.

    uv run python examples/run_engine_headless.py BV1GJ411x7h7 --max-roots 40
    uv run python examples/run_engine_headless.py BV1… BV2… --cookie "$(cat cookie.txt)"
    uv run python examples/run_engine_headless.py --file videos.txt

Demonstrates the engine applying the skill's strategies to a platform core.
Several inputs run sequentially with the same pacing, one video at a time.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.engine.batch import BatchJob, items_from_plan, plan_batch  # noqa: E402
from app.engine.job import CrawlOptions, CrawlRequest  # noqa: E402
from app.engine.policy import Policies  # noqa: E402
from app.ui import registry  # noqa: E402


def _read_file(path: str | None) -> list[str]:
    if not path:
        return []
    return Path(path).read_text(encoding="utf-8").splitlines()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Headless comment/danmaku collection")
    parser.add_argument("input", nargs="*", help="one or more BV ids, av ids, or video URLs")
    parser.add_argument("--file", help="text file with one input per line ('#' comments allowed)")
    parser.add_argument("--platform", default="bilibili")
    parser.add_argument("--cookie", default="", help="cookie header, SESSDATA value, or cURL")
    parser.add_argument("--comments-only", action="store_true")
    parser.add_argument("--danmaku-only", action="store_true")
    parser.add_argument("--no-sub-replies", action="store_true")
    parser.add_argument("--mode", type=int, default=3, choices=[2, 3], help="2=time 3=hot")
    parser.add_argument("--max-roots", type=int, default=None)
    parser.add_argument("--preset", default="balanced", choices=["safe", "balanced", "fast"])
    parser.add_argument("--out", default="output")
    parser.add_argument(
        "--no-skip-completed", action="store_true", help="recollect videos already marked complete"
    )
    args = parser.parse_args(argv)

    entry = registry.get_platform(args.platform)
    if entry is None:
        print(f"unknown platform: {args.platform}", file=sys.stderr)
        return 2
    module = entry.module

    text = "\n".join([*args.input, *_read_file(args.file)])
    plan = plan_batch(module, text)
    if plan.invalid:
        print("ignored lines: " + ", ".join(str(line.line_no) for line in plan.invalid))
    if plan.duplicates:
        print("duplicate lines: " + ", ".join(f"{a}->{b}" for a, b in plan.duplicates))
    if not plan.items:
        print("nothing to collect", file=sys.stderr)
        return 2

    options = CrawlOptions(
        collect_comments=not args.danmaku_only,
        collect_sub_replies=not args.no_sub_replies,
        collect_danmaku=not args.comments_only,
        mode=args.mode,
        comment_fields=module.default_fields("comments"),
        danmaku_fields=module.default_fields("danmaku"),
        policies=Policies.for_preset(args.preset),
        output_root=Path(args.out),
        max_roots=args.max_roots,
    )
    template = CrawlRequest(
        platform=entry.id,
        raw_input="",
        credentials={"cookie": args.cookie} if args.cookie else {},
        options=options,
        adapter_factory=module.create_adapter,
    )
    items = items_from_plan(plan, [item.index for item in plan.items])
    job = BatchJob(template, items, skip_completed=not args.no_skip_completed)
    job.start()

    marks = {"done": "ok", "error": "err", "skipped": "skip"}
    while job.is_running() or not job.events.empty():
        for event in job.drain():
            if event.kind == "log":
                print(f"[{event.level}] {event.message}")
            elif event.kind == "progress":
                total = event.total or 0
                pct = f"{event.done / total * 100:5.1f}%" if total else "  ?  "
                print(f"  {event.phase:9} {pct} {event.done}/{total or '?'}")
            elif event.kind == "item":
                payload = event.payload or {}
                if payload.get("state") in marks:
                    counts = payload.get("counts") or {}
                    extra = f" error={payload['error']}" if payload.get("error") else ""
                    print(
                        f"  [{marks[payload['state']]}] "
                        f"{payload.get('video_id') or payload.get('resolve_input')} "
                        f"{payload.get('title') or ''} "
                        f"comments={counts.get('comments', 0)} "
                        f"danmaku={counts.get('danmaku', 0)}{extra}"
                    )
            elif event.kind in ("error", "cancelled"):
                print(f"\n{event.kind.upper()}: {event.message}", file=sys.stderr)
        if job.is_running():
            time.sleep(0.2)

    summary = job.summary or {}
    print(
        f"summary: ok={summary.get('done', 0)} failed={summary.get('failed', 0)} "
        f"skipped={summary.get('skipped', 0)}"
    )
    if summary.get("archive"):
        print("archive:", summary["archive"])
    elif summary.get("manifest"):
        print("manifest:", summary["manifest"])
    return 0 if summary.get("done") else 1


if __name__ == "__main__":
    raise SystemExit(main())
