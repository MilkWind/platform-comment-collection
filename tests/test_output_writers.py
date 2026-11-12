from __future__ import annotations

import json
from pathlib import Path

from app.engine.output import JsonlSink, jsonl_to_csv, write_meta


def test_jsonl_sink_dedups_by_id(tmp_path: Path):
    sink = JsonlSink(tmp_path / "comments.jsonl")
    assert sink.append({"id": "1", "content": "a"}) is True
    assert sink.append({"id": "1", "content": "a again"}) is False
    assert sink.append({"id": "2", "content": "b"}) is True
    sink.close()
    lines = (tmp_path / "comments.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2


def test_jsonl_sink_resumes_existing(tmp_path: Path):
    path = tmp_path / "comments.jsonl"
    path.write_text('{"id": "1", "content": "a"}\n', encoding="utf-8")
    sink = JsonlSink(path)
    assert sink.seen("1")
    assert sink.append({"id": "1", "content": "dup"}) is False
    sink.close()
    assert len(path.read_text(encoding="utf-8").splitlines()) == 1


def test_csv_is_utf8_sig_with_columns(tmp_path: Path):
    jsonl = tmp_path / "comments.jsonl"
    jsonl.write_text(
        json.dumps({"id": "1", "content": "中文内容"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    csv_path = jsonl_to_csv(jsonl, tmp_path / "comments.csv", ["id", "content"])
    raw = csv_path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")  # BOM
    text = csv_path.read_text(encoding="utf-8-sig")
    assert text.splitlines()[0] == "id,content"
    assert "中文内容" in text


def test_meta_written(tmp_path: Path):
    path = write_meta(tmp_path / "meta.json", {"counts": {"comments": 3}})
    assert json.loads(path.read_text(encoding="utf-8"))["counts"]["comments"] == 3
