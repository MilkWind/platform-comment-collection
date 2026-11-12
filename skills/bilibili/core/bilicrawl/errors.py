"""Error taxonomy for the Bilibili core.

The outer engine never imports this module; it classifies failures by reading
the ``kind``/``retryable`` attributes off whatever exception a core raises
(see docs/adapter-contract.md). Keeping the taxonomy here means a change in
Bilibili's error codes is a one-file fix.
"""

from __future__ import annotations


class BiliApiError(Exception):
    """Base error for every failure the core surfaces to the caller."""

    kind: str = "unknown"
    retryable: bool = False

    def __init__(
        self,
        message: str,
        *,
        http_status: int | None = None,
        code: int | None = None,
        url: str | None = None,
    ) -> None:
        super().__init__(message)
        self.http_status = http_status
        self.code = code
        self.url = url

    def __str__(self) -> str:  # include the API fingerprint for debuggability
        parts = [super().__str__()]
        if self.code is not None:
            parts.append(f"code={self.code}")
        if self.http_status is not None:
            parts.append(f"http={self.http_status}")
        if self.url:
            parts.append(f"url={self.url}")
        return " | ".join(parts)


class RiskControl(BiliApiError):
    """HTTP 412: the request was rejected by risk control. Back off a lot."""

    kind = "risk_control"
    retryable = True


class TransientError(BiliApiError):
    """Captcha / rate-limit / server busy. Retry after a moderate backoff."""

    kind = "transient"
    retryable = True


class WbiStale(BiliApiError):
    """JSON code -412: cached WBI keys are stale. Drop them and retry once."""

    kind = "wbi_stale"
    retryable = True


class AuthExpired(BiliApiError):
    """JSON code -101: the cookie is expired or invalid. Fatal; ask to re-auth."""

    kind = "auth_expired"
    retryable = False


class NotFound(BiliApiError):
    """The video/comment does not exist or is unavailable."""

    kind = "not_found"
    retryable = False


class ProtocolError(BiliApiError):
    """Unexpected response shape or an unhandled API code. Fatal; fail loudly."""

    kind = "protocol"
    retryable = False


# JSON API codes treated as transient (verified against blblcd/bilicmtcrawl).
_TRANSIENT_CODES = {-352, -509, -799}
# Codes that mean "the offset cursor ran past the available data".
_OFFSET_EXHAUSTED = {-400}


def classify_api_code(code: int, message: str = "", *, url: str | None = None) -> BiliApiError:
    """Map a decoded JSON ``code`` field to the right error subclass."""
    if code == -412:
        return WbiStale(message or "WBI signature rejected", code=code, url=url)
    if code == -101:
        return AuthExpired(message or "account not logged in", code=code, url=url)
    if code in _TRANSIENT_CODES:
        return TransientError(message or "rate limited", code=code, url=url)
    if code == -404 or code == 62002:
        return NotFound(message or "not found", code=code, url=url)
    if code in _OFFSET_EXHAUSTED:
        return ProtocolError(message or "offset exhausted", code=code, url=url)
    return ProtocolError(message or f"api error code {code}", code=code, url=url)
