"""Guard that the UI snippet and the documented snippet are one source."""

from __future__ import annotations

from pathlib import Path

from bilicrawl.credentials import CONSOLE_SNIPPET

SNIPPET_JS = (
    Path(__file__).resolve().parent.parent
    / "skills"
    / "bilibili"
    / "scripts"
    / "sessdata_snippet.js"
)


def test_console_snippet_is_loaded_from_the_js_file():
    js = SNIPPET_JS.read_text(encoding="utf-8")
    body = "\n".join(line for line in js.splitlines() if not line.strip().startswith("//")).strip()
    assert CONSOLE_SNIPPET == body


def test_console_snippet_targets_sessdata():
    assert "SESSDATA" in CONSOLE_SNIPPET
    assert "copy(" in CONSOLE_SNIPPET
