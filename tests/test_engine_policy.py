from __future__ import annotations

import threading

import pytest
from bilicrawl.errors import (
    AuthExpired,
    NotFound,
    ProtocolError,
    RiskControl,
    TransientError,
    WbiStale,
)

from app.engine.control import Cancelled
from app.engine.policy import Policies, Policy, classify


@pytest.mark.parametrize(
    "exc,fatal,refresh",
    [
        (AuthExpired("x"), True, False),
        (NotFound("x"), True, False),
        (ProtocolError("x"), True, False),
        (RiskControl("x"), False, False),
        (TransientError("x"), False, False),
        (WbiStale("x"), False, True),
        (RuntimeError("boom"), True, False),
    ],
)
def test_classify(exc, fatal, refresh):
    decision = classify(exc)
    assert decision.fatal is fatal
    assert decision.refresh_keys is refresh


def _policy(**overrides) -> Policy:
    policies = Policies.for_preset("fast")
    policies.intervals = {k: (0.0, 0.0) for k in policies.intervals}  # no pacing in tests
    for key, value in overrides.items():
        setattr(policies, key, value)
    return Policy(policies, threading.Event())


def test_policy_retries_transient_then_succeeds():
    policy = _policy()
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise TransientError("busy")
        return "ok"

    assert policy.call("danmaku_segment", flaky) == "ok"
    assert calls["n"] == 3


def test_policy_stops_on_fatal():
    policy = _policy()
    calls = {"n": 0}

    def boom():
        calls["n"] += 1
        raise AuthExpired("expired")

    with pytest.raises(AuthExpired):
        policy.call("comment_page", boom)
    assert calls["n"] == 1


def test_policy_exhausts_attempts():
    policy = _policy(max_attempts=3)
    calls = {"n": 0}

    def always():
        calls["n"] += 1
        raise TransientError("busy")

    with pytest.raises(TransientError):
        policy.call("comment_page", always)
    assert calls["n"] == 3


def test_policy_calls_recover_on_stale_key():
    class Owner:
        def __init__(self):
            self.recovered = False
            self.calls = 0

        def fetch(self):
            self.calls += 1
            if self.calls == 1:
                raise WbiStale("stale")
            return "ok"

        def recover(self, exc):
            self.recovered = True

    policy = _policy()
    owner = Owner()
    assert policy.call("comment_page", owner.fetch) == "ok"
    assert owner.recovered is True


def test_policy_cancellation_is_immediate():
    event = threading.Event()
    event.set()
    policy = Policy(Policies.for_preset("fast"), event)
    with pytest.raises(Cancelled):
        policy.call("comment_page", lambda: "never")
