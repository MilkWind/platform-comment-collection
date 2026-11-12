"""HTTP transport with injectable backends.

The core performs exactly one network request per public call. Retry loops,
delays, and backoff live in the outer engine, not here (see
docs/adapter-contract.md). ``transport`` is injectable so unit tests can run
fully offline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import requests

from .errors import NotFound, ProtocolError, RiskControl, TransientError

BASE_HEADERS = {
    "Referer": "https://www.bilibili.com",
    "Origin": "https://www.bilibili.com",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
DEFAULT_TIMEOUT = 20.0


@dataclass
class TransportResponse:
    status: int
    content: bytes
    url: str
    headers: dict[str, str]


class Transport(Protocol):
    def request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = ...,
    ) -> TransportResponse: ...


class RequestsTransport:
    """Default transport backed by a single ``requests.Session``."""

    def __init__(self, user_agent: str | None = None) -> None:
        self.session = requests.Session()
        self.user_agent = user_agent or DEFAULT_USER_AGENT

    def set_cookie(self, cookie: str | None) -> None:
        self.session.headers.pop("Cookie", None)
        if cookie:
            self.session.headers["Cookie"] = cookie

    def request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> TransportResponse:
        merged = {**BASE_HEADERS, "User-Agent": self.user_agent, **(headers or {})}
        resp = self.session.request(method, url, params=params, headers=merged, timeout=timeout)
        if resp.status_code == 412:
            raise RiskControl("HTTP 412 risk control", http_status=412, url=url)
        if resp.status_code == 429:
            raise TransientError("HTTP 429 too many requests", http_status=429, url=url)
        if resp.status_code in (404, 403):
            raise NotFound(f"HTTP {resp.status_code}", http_status=resp.status_code, url=url)
        if resp.status_code >= 500:
            raise TransientError(f"HTTP {resp.status_code}", http_status=resp.status_code, url=url)
        if resp.status_code != 200:
            raise ProtocolError(
                f"unexpected HTTP {resp.status_code}", http_status=resp.status_code, url=url
            )
        return TransportResponse(
            status=resp.status_code,
            content=resp.content,
            url=resp.url,
            headers=dict(resp.headers),
        )


def get_json(
    transport: Transport,
    url: str,
    params: dict[str, object] | None = None,
    *,
    allow_codes: tuple[int, ...] = (),
) -> dict:
    """GET a JSON endpoint and return the decoded ``data`` payload.

    ``allow_codes`` lets a caller accept specific non-zero API codes as normal
    (e.g. nav's -101 for anonymous sessions). Any other API-level failure raises
    a classified :class:`BiliApiError`; decode errors raise
    :class:`ProtocolError` so bugs surface loudly instead of returning an empty
    result.
    """
    from .errors import classify_api_code

    resp = transport.request("GET", url, params=params)
    try:
        import json

        payload = json.loads(resp.content)
    except (ValueError, UnicodeDecodeError) as exc:  # pragma: no cover - defensive
        raise ProtocolError(f"invalid JSON from {url}: {exc}", url=url) from exc
    code = int(payload.get("code", 0))
    if code != 0 and code not in allow_codes:
        raise classify_api_code(code, payload.get("message", ""), url=url)
    return payload.get("data") or {}


def get_bytes(transport: Transport, url: str, params: dict[str, object] | None = None) -> bytes:
    """GET a binary endpoint (protobuf danmaku) without JSON decoding."""
    return transport.request("GET", url, params=params).content
