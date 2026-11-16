"""Page layout: sidebar, tabs, and the job panel (outside the tabs)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from app.engine.batch import BatchJob, ResolveJob
from app.ui import jobs
from app.ui.i18n import DEFAULT_LOCALE, t
from app.ui.platform_tab import render_platform_tab
from app.ui.registry import discover

BATCH_COLUMNS = ["#", "line", "video_id", "title", "state", "phase", "comments", "danmaku", "error"]


def render() -> None:
    st.set_page_config(page_title="Platform Comment Collection", page_icon="💬", layout="wide")

    if "pcc_locale" not in st.session_state:
        st.session_state.pcc_locale = DEFAULT_LOCALE
    if "pcc_output_root" not in st.session_state:
        st.session_state.pcc_output_root = "output"

    with st.sidebar:
        st.session_state.pcc_locale = st.radio(
            "Language / 语言",
            options=["zh", "en"],
            format_func=lambda v: "中文" if v == "zh" else "English",
            index=0 if st.session_state.pcc_locale == "zh" else 1,
        )
        st.session_state.pcc_output_root = st.text_input(
            t(st.session_state.pcc_locale, "output_root"),
            value=st.session_state.pcc_output_root,
        )
        st.caption("v0.1.0")

    locale = st.session_state.pcc_locale
    output_root = Path(st.session_state.pcc_output_root)

    st.title(t(locale, "app_title"))
    st.caption(t(locale, "app_subtitle"))

    platforms = discover()
    if not platforms:
        st.error("No platform skills found under skills/*/skill.toml")
        return

    tabs = st.tabs([entry.display_name(locale) for entry in platforms])
    for tab, entry in zip(tabs, platforms, strict=True):
        with tab:
            render_platform_tab(entry, locale, output_root)

    render_job_panel(locale)


def render_job_panel(locale: str) -> None:
    job = jobs.current_job()
    if job is None:
        return
    st.divider()
    _job_fragment(locale)


@st.fragment(run_every=1.0)
def _job_fragment(locale: str) -> None:
    jobs.drain()
    job = jobs.current_job()
    if job is None:
        return

    final = st.session_state.get(jobs.EVENT_KEY)
    running = job.is_running()

    st.subheader(t(locale, "job_running_banner") if running else t(locale, "done"))
    if isinstance(job, (BatchJob, ResolveJob)):
        _render_batch_body(locale, job, final, running)
    else:
        _render_single_body(locale, job, final, running)

    if final is not None and not running and jobs.consume_terminal(final):
        st.rerun()


def _render_single_body(locale: str, job, final, running: bool) -> None:
    last = job.latest_progress()
    if last is not None:
        total = last.total or 0
        ratio = min(1.0, last.done / total) if total else 0.0
        st.progress(ratio, text=f"{t(locale, 'phase_' + last.phase)} · {last.done}/{total or '?'}")
    else:
        st.progress(0.0)

    col1, col2 = st.columns([1, 4])
    if running and col1.button(t(locale, "cancel"), type="secondary"):
        job.cancel()

    logs = st.session_state.get(jobs.LOG_KEY, [])
    with st.expander(t(locale, "logs"), expanded=True):
        st.code("\n".join(logs[-60:]) or "…", language="text")

    if final is not None and not running:
        _render_terminal(locale, final)


def _render_batch_body(locale: str, job, final, running: bool) -> None:
    items = jobs.batch_items()
    total = max(len(items), 1)
    finished = sum(
        1 for row in items.values() if row.get("state") in ("done", "error", "skipped", "cancelled")
    )
    st.progress(min(1.0, finished / total), text=f"{finished}/{total} · {t(locale, 'phase_batch')}")

    active = next(
        (row for row in items.values() if row.get("state") in ("resolving", "running")), None
    )
    if active is not None:
        st.caption(
            f"#{active.get('index', 0) + 1} "
            f"{active.get('video_id') or active.get('resolve_input') or ''} · "
            f"{active.get('phase') or ''} · {active.get('done')}/{active.get('total') or '?'}"
        )

    if items:
        st.dataframe(_items_frame(items, locale), hide_index=True, width="stretch")

    if running and st.button(t(locale, "cancel"), key="pcc_batch_cancel"):
        job.cancel()

    logs = st.session_state.get(jobs.LOG_KEY, [])
    with st.expander(t(locale, "logs"), expanded=not items):
        st.code("\n".join(logs[-60:]) or "…", language="text")

    if final is not None and not running:
        _render_terminal(locale, final, batch=True)


def _items_frame(items: dict[int, dict], locale: str = "zh") -> pd.DataFrame:
    renamed = {
        "#": "#",
        "line": t(locale, "col_line"),
        "video_id": t(locale, "col_video_id"),
        "title": t(locale, "col_title"),
        "state": t(locale, "col_state"),
        "phase": t(locale, "col_phase"),
        "comments": t(locale, "col_comments"),
        "danmaku": t(locale, "col_danmaku"),
        "error": t(locale, "col_error"),
    }
    rows = []
    for row in sorted(items.values(), key=lambda r: r.get("index", 0)):
        counts = row.get("counts") or {}
        rows.append(
            {
                "#": row.get("index", 0) + 1,
                "line": row.get("line_no"),
                "video_id": row.get("video_id") or "",
                "title": row.get("title") or "",
                "state": t(locale, f"state_{row.get('state', 'pending')}"),
                "phase": t(locale, "phase_" + row["phase"]) if row.get("phase") else "",
                "comments": counts.get("comments", 0),
                "danmaku": counts.get("danmaku", 0),
                "error": (row.get("error") or "")[:120],
            }
        )
    return pd.DataFrame(rows, columns=BATCH_COLUMNS).rename(columns=renamed)


@st.cache_data(show_spinner=False, max_entries=8)
def _file_bytes(path: str, mtime: float) -> bytes:
    """Read once per file version: the fragment re-runs every second."""
    return Path(path).read_bytes()


def _render_terminal(locale: str, final, batch: bool = False) -> None:
    if final.kind == "done":
        payload = final.payload or {}
        if payload.get("mode") == "resolve":
            done = sum(1 for item in payload.get("items", []) if item.get("state") == "done")
            st.success(t(locale, "resolved_n").format(n=done))
            return
        if batch:
            st.success(
                t(locale, "batch_summary").format(
                    done=payload.get("done", 0),
                    failed=payload.get("failed", 0),
                    skipped=payload.get("skipped", 0),
                )
            )
            if payload.get("aborted") == "auth_expired":
                st.warning(t(locale, "aborted_auth"))
            archive = payload.get("archive")
            if archive and Path(archive).exists():
                st.download_button(
                    t(locale, "download_all"),
                    data=_file_bytes(archive, Path(archive).stat().st_mtime),
                    file_name=Path(archive).name,
                    mime="application/zip",
                    key="pcc_batch_download",
                )
            with st.expander(t(locale, "per_video")):
                for item in payload.get("items", []):
                    archive = item.get("archive")
                    if item.get("state") != "done" or not archive or not Path(archive).exists():
                        continue
                    name = item.get("video_id") or f"#{item.get('index', 0) + 1}"
                    st.download_button(
                        name,
                        data=_file_bytes(archive, Path(archive).stat().st_mtime),
                        file_name=Path(archive).name,
                        mime="application/zip",
                        key=f"pcc_batch_dl_{item.get('index')}",
                    )
            st.caption(f"{t(locale, 'open_dir')}: {payload.get('manifest') or payload.get('out_dir')}")
        else:
            counts = payload.get("counts", {})
            st.success(f"{t(locale, 'done')}: {counts}")
            archive = payload.get("archive")
            if archive and Path(archive).exists():
                st.download_button(
                    t(locale, "download"),
                    data=_file_bytes(archive, Path(archive).stat().st_mtime),
                    file_name=Path(archive).name,
                    mime="application/zip",
                    key="pcc_download",
                )
            st.caption(f"{t(locale, 'open_dir')}: {payload.get('out_dir')}")
    elif final.kind == "cancelled":
        st.warning(t(locale, "cancelled"))
    elif final.kind == "error":
        st.error(f"{t(locale, 'error')}: {final.message}")
        tb = (final.payload or {}).get("traceback")
        if tb:
            with st.expander("Traceback"):
                st.code(tb, language="text")

    if st.button("✕ Reset", key="pcc_reset"):
        jobs.clear()
        st.rerun()
