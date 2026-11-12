"""WBI request signing.

Bilibili's Web-Base Interface adds ``wts`` (unix seconds) and ``w_rid``
(an md5 signature) to protected endpoints. The mixin key is derived from the
``img_key`` and ``sub_key`` published by ``/x/web-interface/nav``, permuted
through a fixed 64-entry table.

``sign_query()`` is pure and deterministic given its inputs, which is what
makes the golden-vector test possible.
"""

from __future__ import annotations

import hashlib
import time
import urllib.parse

from .http import Transport, get_json

NAV_URL = "https://api.bilibili.com/x/web-interface/nav"

# fmt: off
MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
    22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52,
]
# fmt: on

# Characters Bilibili strips from parameter values before signing.
_STRIP_TABLE = str.maketrans("", "", "!'()*")


def mixin_key(img_key: str, sub_key: str) -> str:
    """Derive the 32-char mixin key from the two nav keys."""
    orig = img_key + sub_key
    return "".join(orig[i] for i in MIXIN_KEY_ENC_TAB)[:32]


def sign_query(
    params: dict[str, object],
    img_key: str,
    sub_key: str,
    wts: int | None = None,
) -> str:
    """Return the fully signed query string (``...&wts=...&w_rid=...``).

    Values are signed with the disallowed characters stripped, keys are sorted,
    and the exact ``urlencode`` output that is hashed is what the caller must
    send. Appending this string to a URL (instead of passing ``params=``) keeps
    the wire bytes identical to the signed bytes.
    """
    key = mixin_key(img_key, sub_key)
    signed = {str(k): str(v) for k, v in params.items()}
    signed["wts"] = str(int(wts if wts is not None else time.time()))
    cleaned = {k: v.translate(_STRIP_TABLE) for k, v in signed.items()}
    query = urllib.parse.urlencode(sorted(cleaned.items()))
    w_rid = hashlib.md5((query + key).encode("utf-8")).hexdigest()
    return f"{query}&w_rid={w_rid}"


class WbiKeyCache:
    """Fetches and caches the nav keys; cleared when a signature is rejected."""

    def __init__(self, transport: Transport) -> None:
        self._transport = transport
        self._keys: tuple[str, str] | None = None

    def clear(self) -> None:
        self._keys = None

    def get(self, *, force: bool = False) -> tuple[str, str]:
        if self._keys is None or force:
            # Anonymous sessions get code -101 but still receive wbi_img keys.
            data = get_json(self._transport, NAV_URL, allow_codes=(-101,))
            wbi = data.get("wbi_img") or {}
            img = _basename(wbi.get("img_url", ""))
            sub = _basename(wbi.get("sub_url", ""))
            if not img or not sub:
                from .errors import ProtocolError

                raise ProtocolError("nav response missing wbi_img keys")
            self._keys = (img, sub)
        return self._keys


def _basename(url: str) -> str:
    return url.rsplit("/", 1)[-1].split(".")[0] if url else ""
