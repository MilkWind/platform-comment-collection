from __future__ import annotations

from bilicrawl.errors import (
    AuthExpired,
    NotFound,
    ProtocolError,
    RiskControl,
    TransientError,
    WbiStale,
)


def test_error_taxonomy_attributes():
    assert AuthExpired("x").retryable is False
    assert NotFound("x").retryable is False
    assert ProtocolError("x").retryable is False
    assert RiskControl("x").retryable is True
    assert TransientError("x").retryable is True
    assert WbiStale("x").retryable is True
    assert RiskControl("x").kind == "risk_control"
    assert WbiStale("x").kind == "wbi_stale"


def test_error_str_includes_fingerprint():
    err = ProtocolError("boom", code=-400, url="https://example/api")
    text = str(err)
    assert "code=-400" in text
    assert "url=" in text
