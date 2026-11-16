"""Bridge between the generic engine and Streamlit.

The worker thread never touches Streamlit; this module drains job queues on the
script thread and keeps the current job in ``st.session_state``.

Batch jobs additionally keep one row per video. Rows are updated by *replacing*
a dict entry, never by appending, so the job panel stays bounded no matter how
many events a batch produces.
"""

from __future__ import annotations

import streamlit as st

from app.engine.job import EventJob
from app.engine.progress import Event

JOB_KEY = "pcc_job"
LOG_KEY = "pcc_logs"
EVENT_KEY = "pcc_events"
BATCH_ITEMS_KEY = "pcc_batch_items"
BATCH_PREVIEW_KEY = "pcc_batch_preview"
CONSUMED_KEY = "pcc_terminal_consumed"

MAX_LOG_LINES = 400
TERMINAL = ("done", "error", "cancelled")


def current_job() -> EventJob | None:
    return st.session_state.get(JOB_KEY)


def start_job(job: EventJob) -> None:
    st.session_state[JOB_KEY] = job
    st.session_state[LOG_KEY] = []
    st.session_state[EVENT_KEY] = None
    st.session_state[BATCH_ITEMS_KEY] = {}
    st.session_state.pop(CONSUMED_KEY, None)
    job.start()


def batch_items() -> dict[int, dict]:
    return st.session_state.get(BATCH_ITEMS_KEY, {})


def batch_preview() -> dict[str, dict]:
    return st.session_state.get(BATCH_PREVIEW_KEY, {})


def ingest(
    events: list[Event], logs: list[str], items: dict[int, dict]
) -> tuple[list[str], dict[int, dict], Event | None]:
    """Pure event -> state mapping (no Streamlit), so it is testable directly."""
    terminal: Event | None = None
    for event in events:
        if event.kind == "log":
            prefix = {"warn": "⚠ ", "error": "✖ "}.get(event.level, "• ")
            logs.append(f"{prefix}{event.message}")
        elif event.kind == "item":
            payload = event.payload or {}
            index = payload.get("index")
            if index is not None:
                items[index] = payload
        elif event.kind in TERMINAL:
            terminal = event
            logs.append(f"■ {event.kind}: {event.message}")
    return logs[-MAX_LOG_LINES:], items, terminal


def drain() -> list[Event]:
    """Drain queued events into session state, keeping a bounded log."""
    job = current_job()
    if job is None:
        return []
    events = job.drain()
    logs, items, terminal = ingest(
        events,
        st.session_state.get(LOG_KEY, []),
        dict(st.session_state.get(BATCH_ITEMS_KEY, {})),
    )
    st.session_state[LOG_KEY] = logs
    st.session_state[BATCH_ITEMS_KEY] = items
    if terminal is not None:
        st.session_state[EVENT_KEY] = terminal
    return events


def consume_terminal(event: Event) -> bool:
    """True the first time a given terminal event is seen.

    Resolve terminals merge their preview into session state so the next full
    rerun can fill the (disabled) table columns with titles and part counts.
    """
    if st.session_state.get(CONSUMED_KEY) == event.ts:
        return False
    st.session_state[CONSUMED_KEY] = event.ts
    payload = event.payload or {}
    if event.kind == "done" and payload.get("mode") == "resolve":
        preview = dict(st.session_state.get(BATCH_PREVIEW_KEY, {}))
        for item in payload.get("items", []):
            key = item.get("resolve_input") or item.get("raw")
            if key:
                preview[key] = item
        st.session_state[BATCH_PREVIEW_KEY] = preview
        return True
    return False


def is_active() -> bool:
    job = current_job()
    return bool(job and job.is_running())


def clear() -> None:
    for key in (JOB_KEY, LOG_KEY, EVENT_KEY, BATCH_ITEMS_KEY, BATCH_PREVIEW_KEY, CONSUMED_KEY):
        st.session_state.pop(key, None)
