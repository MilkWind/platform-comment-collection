"""Bridge between the generic engine and Streamlit.

The worker thread never touches Streamlit; this module drains job queues on the
script thread and keeps the current job in ``st.session_state``.
"""

import streamlit as st

from app.engine.job import CrawlJob
from app.engine.progress import Event

JOB_KEY = "pcc_job"
LOG_KEY = "pcc_logs"
EVENT_KEY = "pcc_events"


def current_job() -> CrawlJob | None:
    return st.session_state.get(JOB_KEY)


def start_job(job: CrawlJob) -> None:
    st.session_state[JOB_KEY] = job
    st.session_state[LOG_KEY] = []
    st.session_state[EVENT_KEY] = None
    job.start()


def drain() -> list[Event]:
    """Drain queued events into session state, keeping a bounded log."""
    job = current_job()
    if job is None:
        return []
    events = job.drain()
    logs: list[str] = st.session_state.get(LOG_KEY, [])
    for event in events:
        if event.kind == "log":
            prefix = {"warn": "⚠ ", "error": "✖ "}.get(event.level, "• ")
            logs.append(f"{prefix}{event.message}")
        elif event.kind == "progress":
            logs.append(f"… [{event.phase}] {event.done}/{event.total or '?'} {event.message}")
        elif event.kind in ("done", "error", "cancelled"):
            st.session_state[EVENT_KEY] = event
            logs.append(f"■ {event.kind}: {event.message}")
    if len(logs) > 400:
        logs = logs[-400:]
    st.session_state[LOG_KEY] = logs
    return events


def is_active() -> bool:
    job = current_job()
    return bool(job and job.is_running())


def clear() -> None:
    for key in (JOB_KEY, LOG_KEY, EVENT_KEY):
        st.session_state.pop(key, None)
