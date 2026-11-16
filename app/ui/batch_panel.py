"""Batch input panel: multi-line links -> plan preview -> table -> start.

Rendering is split in two: the text area, toggles and the editable table live in
the tab body (they hold user edits), while the live progress table lives in the
job fragment. Nothing here knows about Bilibili; everything comes from the
platform module's ``parse_input``.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from app.engine import checkpoint as ckpt
from app.engine.batch import BatchJob, items_from_plan, plan_batch
from app.engine.job import CrawlOptions, CrawlRequest
from app.engine.policy import Policies
from app.ui import jobs
from app.ui.i18n import t
from app.ui.registry import PlatformEntry


def _state_key(entry: PlatformEntry, name: str) -> str:
    return f"pcc_form_{entry.id}_{name}"


def _plan(entry: PlatformEntry, text: str):
    """Parse defensively: a broken platform parser must not take the tab down."""
    try:
        return plan_batch(entry.module, text)
    except Exception as exc:  # noqa: BLE001 - surface, never crash the page
        st.error(f"{type(exc).__name__}: {exc}")
        return None


def _row(
    planned, preview: dict, locale: str, skip_done: bool, output_root: Path, platform: str
) -> dict:
    seen = preview.get(planned.resolve_input, {})
    state = seen.get("state") or ""
    title = seen.get("title") or ""
    video_id = seen.get("video_id") or planned.video_id or ""
    # "Resolved" is preview state ("done" for a resolve job), not collection
    # state; only a finished checkpoint on disk means "skip this".
    complete_before = bool(video_id) and ckpt.is_video_complete(output_root, platform, video_id)
    if state == "done" and not complete_before:
        state = "ready"
    return {
        "collect": not (skip_done and complete_before),
        "line": planned.line_no,
        "input": planned.raw,
        "video_id": video_id,
        "title": title,
        "parts": seen.get("parts") or None,
        "state": t(locale, "state_skipped" if complete_before else f"state_{state}") if state else "",
    }


def render_batch_panel(
    entry: PlatformEntry,
    locale: str,
    active: bool,
    *,
    collect_comments: bool,
    collect_sub: bool,
    collect_danmaku: bool,
    mode: int,
    comment_fields: list[str],
    danmaku_fields: list[str],
    preset: str,
    max_roots: int,
    output_root: Path,
) -> None:
    text = st.text_area(
        t(locale, "input_label_batch"),
        key=_state_key(entry, "inputs"),
        placeholder=t(locale, "input_placeholder_batch"),
        height=150,
        disabled=active,
    )

    plan = _plan(entry, text) if text else None
    preview = jobs.batch_preview()
    skip_done = st.checkbox(
        t(locale, "skip_completed"),
        value=True,
        key=_state_key(entry, "skip_done"),
        disabled=active,
    )

    selected: list[str] = []
    if plan is not None and plan.items:
        st.caption(
            t(locale, "plan_summary").format(
                ok=len(plan.items) + len(plan.duplicates),
                unique=len(plan.items),
                invalid=len(plan.invalid),
                dup=len(plan.duplicates),
            )
        )
        if plan.invalid:
            st.warning(
                t(locale, "plan_invalid").format(
                    lines=", ".join(str(line.line_no) for line in plan.invalid)
                )
            )
        if plan.duplicates:
            st.warning(
                t(locale, "plan_duplicate").format(
                    lines=", ".join(f"{dup}→{first}" for dup, first in plan.duplicates)
                )
            )

        frame = pd.DataFrame(
            [
                _row(item, preview, locale, skip_done, output_root, entry.id)
                for item in plan.items
            ],
            columns=["collect", "line", "input", "video_id", "title", "parts", "state"],
        )
        edited = st.data_editor(
            frame,
            hide_index=True,
            num_rows="fixed",
            width="stretch",
            disabled=["line", "input", "video_id", "title", "parts", "state"],
            column_config={
                "collect": st.column_config.CheckboxColumn(t(locale, "col_collect")),
                "line": st.column_config.NumberColumn(t(locale, "col_line")),
                "input": st.column_config.TextColumn(t(locale, "col_input")),
                "video_id": st.column_config.TextColumn(t(locale, "col_video_id")),
                "title": st.column_config.TextColumn(t(locale, "col_title")),
                "parts": st.column_config.NumberColumn(t(locale, "col_parts")),
                "state": st.column_config.TextColumn(t(locale, "col_state")),
            },
            # The signature in the key means editing the text resets row toggles
            # instead of leaking stale checkboxes onto different videos.
            key=f"pcc_editor_{entry.id}_{plan.signature}",
        )
        selected = [
            item.resolve_input
            for item, keep in zip(plan.items, edited["collect"], strict=True)
            if bool(keep)
        ]

    scope_ok = collect_comments or collect_danmaku
    c1, c2 = st.columns([1, 2])
    resolve_clicked = c1.button(
        t(locale, "resolve"),
        disabled=active or plan is None or not plan.items,
        key=_state_key(entry, "resolve"),
        width="stretch",
    )
    start_clicked = c2.button(
        t(locale, "start"),
        type="primary",
        disabled=active or not selected or not scope_ok,
        key=_state_key(entry, "start"),
        width="stretch",
    )

    credentials = {
        field.key: st.session_state.get(_state_key(entry, f"cred_{field.key}"), "") or ""
        for field in entry.module.credential_fields()
    }

    if resolve_clicked and plan is not None:
        _start_resolve(entry, plan, credentials, preset, locale)

    if start_clicked and plan is not None:
        chosen = {item.resolve_input for item in plan.items} & set(selected)
        chosen_indices = [item.index for item in plan.items if item.resolve_input in chosen]
        options = CrawlOptions(
            collect_comments=collect_comments,
            collect_sub_replies=collect_sub,
            collect_danmaku=collect_danmaku,
            mode=mode,
            comment_fields=comment_fields,
            danmaku_fields=danmaku_fields,
            policies=Policies.for_preset(preset),
            output_root=output_root,
            max_roots=max_roots or None,
        )
        template = CrawlRequest(
            platform=entry.id,
            raw_input="",
            credentials=credentials,
            options=options,
            adapter_factory=entry.module.create_adapter,
        )
        items = items_from_plan(plan, chosen_indices, preview)
        jobs.start_job(BatchJob(template, items, skip_completed=skip_done))
        st.rerun()


def _start_resolve(entry: PlatformEntry, plan, credentials: dict, preset: str, locale: str) -> None:
    from app.engine.batch import ResolveJob

    items = items_from_plan(plan, [item.index for item in plan.items], jobs.batch_preview())
    job = ResolveJob(
        platform=entry.id,
        credentials=credentials,
        adapter_factory=entry.module.create_adapter,
        policies=Policies.for_preset(preset),
        items=items,
    )
    jobs.start_job(job)
    st.rerun()


__all__ = ["render_batch_panel"]
