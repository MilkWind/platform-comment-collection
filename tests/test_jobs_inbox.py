"""Pure-unit tests for the event -> session-state mapping used by the job panel."""

from __future__ import annotations

from app.engine.progress import Event
from app.ui.jobs import ingest


def test_item_events_replace_rows_instead_of_appending():
    items: dict[int, dict] = {}
    logs: list[str] = []
    events = [
        Event.item({"index": 0, "state": "running", "video_id": "BV1"}),
        Event.item({"index": 0, "state": "done", "video_id": "BV1"}),
        Event.item({"index": 1, "state": "running", "video_id": "BV2"}),
    ]
    logs, items, terminal = ingest(events, logs, items)

    assert terminal is None
    assert sorted(items) == [0, 1]
    assert items[0]["state"] == "done"


def test_logs_are_bounded_and_prefixed():
    logs = [f"line {i}" for i in range(398)]
    events = [
        Event.log("warned", level="warn"),
        Event.log("broke", level="error"),
        Event.log("ok"),
    ]
    logs, _, _ = ingest(events, logs, {})

    assert len(logs) == 400
    assert logs[-3:] == ["⚠ warned", "✖ broke", "• ok"]


def test_terminal_event_is_returned_and_logged():
    logs, items, terminal = ingest(
        [Event(kind="done", message="Batch complete.")], [], {}
    )
    assert terminal is not None and terminal.kind == "done"
    assert logs[-1].startswith("■ done")
