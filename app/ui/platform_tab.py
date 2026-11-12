"""Generic platform tab: renders any platform from its manifest + module APIs.

No platform branching lives here. The form is built from ``credential_fields()``
and ``field_catalog()``; the crawl is driven by ``CrawlRequest``.

This is intentionally *not* wrapped in ``st.form``: a form does not rerun while
the user types, so a submit button whose enabled state depends on the input
would never become clickable. Plain widgets rerun per interaction, which keeps
validation live and the controls testable.
"""

from pathlib import Path

import streamlit as st

from app.engine.job import CrawlJob, CrawlOptions, CrawlRequest
from app.engine.policy import Policies
from app.ui import jobs
from app.ui.i18n import label, t
from app.ui.registry import PlatformEntry

MAX_ROOTS_DEFAULT = 2000
_PRESETS = {"safe": "preset_safe", "balanced": "preset_balanced", "fast": "preset_fast"}


def _state_key(entry: PlatformEntry, name: str) -> str:
    return f"pcc_form_{entry.id}_{name}"


def render_platform_tab(entry: PlatformEntry, locale: str, output_root: Path) -> None:
    module = entry.module
    active = jobs.is_active()  # only while a job is actually running

    raw_input = st.text_input(
        t(locale, "input_label"),
        key=_state_key(entry, "input"),
        placeholder=t(locale, "input_placeholder"),
        disabled=active,
    )
    parsed = module.parse_input(raw_input) if raw_input else None
    if raw_input and parsed is not None and not parsed.ok:
        st.warning(t(locale, "input_invalid"))

    for field in module.credential_fields():
        with st.expander(label(locale, field.label_en, field.label_zh), expanded=False):
            st.text_area(
                label(locale, field.label_en, field.label_zh),
                key=_state_key(entry, f"cred_{field.key}"),
                disabled=active,
                help=label(locale, field.help_en, field.help_zh),
            )
            st.caption(label(locale, "Console snippet:", "控制台片段："))
            st.code(field.console_snippet, language="javascript")
            st.caption(
                label(
                    locale,
                    "If SESSDATA is HttpOnly, use DevTools → Network → Copy as cURL "
                    "and paste above.",
                    "如果 SESSDATA 为 HttpOnly，请用开发者工具 → 网络 → 复制为 cURL，"
                    "然后粘贴到上方。",
                )
            )

    st.divider()
    st.subheader(t(locale, "scope"))
    c1, c2, c3 = st.columns(3)
    collect_comments = c1.checkbox(
        t(locale, "collect_comments"), value=True, disabled=active, key=_state_key(entry, "c")
    )
    collect_sub = c2.checkbox(
        t(locale, "collect_sub"),
        value=True,
        disabled=active or not collect_comments,
        key=_state_key(entry, "s"),
    )
    collect_danmaku = c3.checkbox(
        t(locale, "collect_danmaku"), value=True, disabled=active, key=_state_key(entry, "d")
    )

    sort_option = st.radio(
        t(locale, "sort"),
        options=["hot", "time"],
        format_func=lambda v: t(locale, "sort_hot" if v == "hot" else "sort_time"),
        horizontal=True,
        disabled=active,
        key=_state_key(entry, "sort"),
    )
    mode = 3 if sort_option == "hot" else 2

    st.divider()
    st.subheader(t(locale, "fields_comments"))
    comment_fields = _field_checkboxes(entry, module, "comments", locale, active)
    st.subheader(t(locale, "fields_danmaku"))
    danmaku_fields = _field_checkboxes(entry, module, "danmaku", locale, active)

    with st.expander(t(locale, "advanced")):
        preset = st.radio(
            t(locale, "preset"),
            options=["safe", "balanced", "fast"],
            format_func=lambda v: t(locale, _PRESETS[v]),
            index=1,
            horizontal=True,
            disabled=active,
            key=_state_key(entry, "preset"),
        )
        max_roots = st.number_input(
            t(locale, "max_roots"),
            min_value=0,
            value=MAX_ROOTS_DEFAULT,
            step=100,
            disabled=active,
            key=_state_key(entry, "max_roots"),
        )

    disabled = active or not (collect_comments or collect_danmaku) or not raw_input
    if st.button(
        t(locale, "start"),
        type="primary",
        disabled=disabled,
        key=_state_key(entry, "start"),
        use_container_width=True,
    ):
        _start(
            entry,
            module,
            locale,
            raw_input,
            collect_comments,
            collect_sub,
            collect_danmaku,
            mode,
            comment_fields,
            danmaku_fields,
            preset,
            int(max_roots),
            output_root,
        )


def _start(
    entry,
    module,
    locale,
    raw_input,
    collect_comments,
    collect_sub,
    collect_danmaku,
    mode,
    comment_fields,
    danmaku_fields,
    preset,
    max_roots,
    output_root,
) -> None:
    credentials = {
        field.key: st.session_state.get(_state_key(entry, f"cred_{field.key}"), "") or ""
        for field in module.credential_fields()
    }
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
    request = CrawlRequest(
        platform=entry.id,
        raw_input=raw_input.strip(),
        credentials=credentials,
        options=options,
        adapter_factory=module.create_adapter,
    )
    jobs.start_job(CrawlJob(request))
    st.rerun()


def _field_checkboxes(entry, module, kind: str, locale: str, active: bool) -> list[str]:
    specs = module.field_catalog(kind)
    selected: list[str] = []
    columns = st.columns(3)
    for i, spec in enumerate(specs):
        text = label(locale, spec.label_en, spec.label_zh)
        if spec.requires_auth:
            text += " 🔒"
        if columns[i % 3].checkbox(
            text,
            value=spec.default,
            key=_state_key(entry, f"field_{kind}_{spec.key}"),
            disabled=active,
        ):
            selected.append(spec.key)
    return selected
