"""Rate limiting, retry, and error classification — the strategy layer.

This is where the abstract strategies documented in
``skills/bilibili/references/strategies.md`` become executable. Cores stay pure;
all waiting and retrying happens here.

Classification is duck-typed: it reads ``kind``/``retryable`` off any exception,
so a second platform's error types work without a shared base class.
"""

from __future__ import annotations

import random
import threading
from dataclasses import dataclass, field

from .control import Cancelled

# Per-request-kind pacing (seconds, min..max before jitter). Balanced preset.
_BASE_INTERVALS: dict[str, tuple[float, float]] = {
    "comment_page": (0.8, 1.6),
    "sub_reply_page": (0.25, 0.6),
    "danmaku_segment": (0.15, 0.45),
    "resolve_video": (0.0, 0.0),
    "verify": (0.0, 0.0),
}

# Multipliers applied to the base intervals by each preset.
_SCALE = {"safe": 2.0, "balanced": 1.0, "fast": 0.45}


@dataclass(frozen=True)
class Decision:
    fatal: bool
    refresh_keys: bool = False
    delay_hint: float | None = None


@dataclass
class Policies:
    preset: str = "balanced"
    max_attempts: int = 4
    backoff_base: float = 1.2
    backoff_cap: float = 20.0
    intervals: dict[str, tuple[float, float]] = field(default_factory=dict)

    @classmethod
    def for_preset(cls, preset: str) -> Policies:
        scale = _SCALE.get(preset, 1.0)
        intervals = {k: (lo * scale, hi * scale) for k, (lo, hi) in _BASE_INTERVALS.items()}
        return cls(preset=preset, intervals=intervals)

    def interval(self, kind: str) -> tuple[float, float]:
        return self.intervals.get(kind, (0.0, 0.0))


def classify(exc: Exception) -> Decision:
    """Map an exception to retry behaviour using only duck-typed attributes."""
    kind = getattr(exc, "kind", "")
    retryable = bool(getattr(exc, "retryable", False))
    http_status = getattr(exc, "http_status", None)
    code = getattr(exc, "code", None)

    if kind == "auth_expired" or code == -101:
        return Decision(fatal=True)
    if kind == "not_found":
        return Decision(fatal=True)
    if http_status == 412 or kind == "risk_control":
        return Decision(fatal=False, delay_hint=12.0)
    if kind == "wbi_stale" or code == -412:
        return Decision(fatal=False, refresh_keys=True, delay_hint=1.0)
    if retryable or http_status in (429, 500, 502, 503, 504):
        return Decision(fatal=False)
    # Unknown exception types are treated as fatal after one attempt: fail
    # loudly on bugs rather than looping forever.
    return Decision(fatal=True)


class Policy:
    def __init__(self, policies: Policies, cancel_event: threading.Event) -> None:
        self.policies = policies
        self.cancel_event = cancel_event

    def _wait(self, delay: float) -> None:
        if delay > 0:
            # Interruptible sleep so cancellation is immediate even mid-backoff.
            self.cancel_event.wait(delay)

    def gate(self, kind: str) -> None:
        lo, hi = self.policies.interval(kind)
        if hi <= 0:
            return
        self._wait(random.uniform(lo, hi))

    def call(self, kind: str, fn, *args, **kwargs):
        """Run ``fn`` with pacing, classification, recovery, and retry."""
        owner = getattr(fn, "__self__", None)  # the adapter for a bound method
        attempt = 0
        while True:
            if self.cancel_event.is_set():
                raise Cancelled()
            if attempt > 0:
                delay = min(
                    self.policies.backoff_cap, self.policies.backoff_base * 2 ** (attempt - 1)
                )
                self._wait(delay * random.uniform(0.8, 1.2))
            self.gate(kind)
            try:
                return fn(*args, **kwargs)
            except Cancelled:
                raise
            except Exception as exc:  # noqa: BLE001 - deliberately classify everything
                decision = classify(exc)
                attempt += 1
                if decision.fatal or attempt >= self.policies.max_attempts:
                    raise
                if decision.refresh_keys and owner is not None and hasattr(owner, "recover"):
                    try:
                        owner.recover(exc)
                    except Exception:  # noqa: BLE001 - recovery must never mask the retry
                        pass
                if decision.delay_hint:
                    self._wait(decision.delay_hint)
