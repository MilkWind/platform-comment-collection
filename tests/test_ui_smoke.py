"""Streamlit render and interaction smoke tests (no network)."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app" / "streamlit_app.py"

pytest.importorskip("streamlit")


def _run():
    from streamlit.testing.v1 import AppTest

    return AppTest.from_file(str(APP), default_timeout=60).run()


def test_app_renders_with_platform_tab():
    at = _run()
    assert not at.exception
    assert len(at.tabs) >= 1
    assert any("Bilibili" in t.label or "哔哩哔哩" in t.label for t in at.tabs)
    assert len(at.checkbox) > 0


def test_language_toggle_present():
    at = _run()
    radios = at.sidebar.radio
    assert radios
    assert len(radios[0].options) == 2  # Chinese + English options


def test_start_button_disables_without_input():
    at = _run()
    start = at.button(key="pcc_form_bilibili_start")
    assert start.disabled  # no video input yet


def test_start_button_enables_after_input():
    at = _run()
    at.text_area(key="pcc_form_bilibili_inputs").set_value("BV1GJ411x7h7")
    at.run()
    assert not at.button(key="pcc_form_bilibili_start").disabled


def test_batch_input_dedupes_and_skips_invalid_lines():
    at = _run()
    at.text_area(key="pcc_form_bilibili_inputs").set_value(
        "BV1GJ411x7h7\nhttps://www.bilibili.com/video/BV1GJ411x7h7/\nnot-a-link"
    )
    at.run()

    assert not at.exception
    assert len(at.data_editor) == 1
    table = at.data_editor[0].value
    assert len(table) == 1  # URL form deduped onto the bare BV id
    assert table.iloc[0]["video_id"] == "BV1GJ411x7h7"
    assert any("3" in str(c.value) for c in at.warning)  # invalid line number reported
    assert not at.button(key="pcc_form_bilibili_start").disabled
    assert not at.button(key="pcc_form_bilibili_resolve").disabled


def test_resolve_button_disabled_without_input():
    at = _run()
    assert at.button(key="pcc_form_bilibili_resolve").disabled


def test_field_groups_render():
    at = _run()
    keys = [cb.key for cb in at.checkbox if cb.key]
    assert any("field_comments_content" in k for k in keys)
    assert any("field_danmaku_progress_ms" in k for k in keys)
