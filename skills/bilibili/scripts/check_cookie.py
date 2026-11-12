"""Validate a Bilibili cookie and print login status.

    uv run python skills/bilibili/scripts/check_cookie.py --cookie "$(cat cookie.txt)"
    uv run python skills/bilibili/scripts/check_cookie.py --cookie-file cookie.txt

Accepts a full cookie header, SESSDATA=..., a bare SESSDATA value, or a cURL.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

CORE = Path(__file__).resolve().parent.parent / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

import bilicrawl  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check a Bilibili cookie")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--cookie", default="")
    group.add_argument("--cookie-file", default="")
    args = parser.parse_args(argv)

    raw = args.cookie
    if args.cookie_file:
        raw = Path(args.cookie_file).read_text(encoding="utf-8-sig").strip()

    adapter = bilicrawl.create_adapter({"cookie": raw} if raw else {})
    auth = adapter.verify()
    print("logged in:", auth.is_logged_in)
    if auth.user_name:
        print("user:", auth.user_name)
    for warning in auth.warnings:
        print("warning:", warning)
    if not raw:
        print("note: no cookie supplied; anonymous mode works for read-only access.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
