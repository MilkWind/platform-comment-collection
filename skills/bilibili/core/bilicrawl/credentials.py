"""Credential handling: normalize pasted cookies / cURL into a Cookie header.

Bilibili's ``SESSDATA`` is often HttpOnly, so a ``document.cookie`` console
snippet cannot always read it. The normalizer therefore accepts several
forms so the UI's "paste" box works no matter what the user managed to copy:

    - a full cookie header:  ``SESSDATA=abc; buvid3=def; ...``
    - a single ``SESSDATA=abc`` pair, or a bare ``abc`` value
    - a pasted ``curl`` command (extracting the ``cookie`` and ``user-agent``)
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

_SNIPPET_FILE = Path(__file__).resolve().parent.parent.parent / "scripts" / "sessdata_snippet.js"
_FALLBACK_SNIPPET = (
    "(() => { const m = document.cookie.match(/(?:^|;\\s*)SESSDATA=([^;]+)/);\n"
    "  m ? copy('SESSDATA=' + m[1])\n"
    "    : console.warn('SESSDATA is HttpOnly here. Use Network -> any api.bilibili.com "
    "request -> Copy as cURL, then paste that into the app.'); })()"
)


def _load_snippet() -> str:
    """Read the canonical snippet by stripping ``//`` comment lines.

    Keeping a single source (the .js file) means the UI and the skill docs can
    never show a different snippet from the tested one.
    """
    try:
        lines = _SNIPPET_FILE.read_text(encoding="utf-8").splitlines()
    except OSError:
        return _FALLBACK_SNIPPET
    body = [line for line in lines if not line.strip().startswith("//")]
    return "\n".join(body).strip()


CONSOLE_SNIPPET = _load_snippet()

_CURL_COOKIE_RE = re.compile(
    r"(?:-H|--header)\s+(['\"])cookie:\s*(.*?)\1", re.IGNORECASE | re.DOTALL
)
_CURL_UA_RE = re.compile(
    r"(?:-H|--header)\s+(['\"])user-agent:\s*(.*?)\1", re.IGNORECASE | re.DOTALL
)


def normalize(raw: str | None) -> tuple[str | None, str | None]:
    """Return ``(cookie_header, user_agent)``; either may be ``None``.

    Accepts a cookie string, a bare SESSDATA value, or a pasted cURL command.
    """
    if not raw:
        return None, None
    text = raw.strip()
    if not text:
        return None, None

    if text.lower().startswith("curl"):
        cookie_m = _CURL_COOKIE_RE.search(text)
        ua_m = _CURL_UA_RE.search(text)
        cookie = cookie_m.group(2).strip() if cookie_m else None
        ua = ua_m.group(2).strip() if ua_m else None
        return _clean_cookie(cookie), ua

    return _clean_cookie(text), None


def _clean_cookie(text: str | None) -> str | None:
    if not text:
        return None
    value = text.strip().strip("'\"").strip()
    lower = value.lower()
    if lower.startswith("cookie:"):
        value = value[len("cookie:") :].strip()
    # A bare SESSDATA value (no '=' and no ';') is wrapped into a cookie pair.
    if "=" not in value and ";" not in value and " " not in value:
        return f"SESSDATA={value}"
    # Collapse whitespace/newlines that copy-paste often introduces.
    return re.sub(r"\s+", " ", value).strip()


def has_sessdata(cookie: str | None) -> bool:
    return bool(cookie) and "SESSDATA=" in (cookie or "")


def shell_split_lenient(text: str) -> list[str]:
    """shlex.split that never raises (used by the cURL normalizer in tests)."""
    try:
        return shlex.split(text)
    except ValueError:
        return text.split()
