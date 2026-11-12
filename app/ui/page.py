"""Page layout: sidebar, tabs, and the job panel (outside the tabs)."""

from pathlib import Path

import streamlit as st

from app.ui import jobs
from app.ui.i18n import DEFAULT_LOCALE, t
from app.ui.platform_tab import render_platform_tab
from app.ui.registry import discover


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

    final = st.session_state.get("pcc_events")
    last = job.latest_progress()

    st.subheader(t(locale, "job_running_banner") if job.is_running() else t(locale, "done"))
    if last is not None:
        total = last.total or 0
        ratio = min(1.0, last.done / total) if total else 0.0
        st.progress(ratio, text=f"{t(locale, 'phase_' + last.phase)} · {last.done}/{total or '?'}")
    else:
        st.progress(0.0)

    running = job.is_running()
    col1, col2 = st.columns([1, 4])
    if running:
        if col1.button(t(locale, "cancel"), type="secondary"):
            job.cancel()

    logs = st.session_state.get("pcc_logs", [])
    with st.expander(t(locale, "logs"), expanded=True):
        st.code("\n".join(logs[-60:]) or "…", language="text")

    if final is not None and not running:
        if final.kind == "done":
            payload = final.payload or {}
            counts = payload.get("counts", {})
            st.success(f"{t(locale, 'done')}: {counts}")
            archive = payload.get("archive")
            if archive and Path(archive).exists():
                st.download_button(
                    t(locale, "download"),
                    data=Path(archive).read_bytes(),
                    file_name=Path(archive).name,
                    mime="application/zip",
                )
            st.caption(f"{t(locale, 'open_dir')}: {payload.get('out_dir')}")
            if st.button("✕ Reset", key="pcc_reset"):
                jobs.clear()
                st.rerun()
        elif final.kind == "cancelled":
            st.warning(t(locale, "cancelled"))
        elif final.kind == "error":
            st.error(f"{t(locale, 'error')}: {final.message}")
            tb = (final.payload or {}).get("traceback")
            if tb:
                with st.expander("Traceback"):
                    st.code(tb, language="text")
