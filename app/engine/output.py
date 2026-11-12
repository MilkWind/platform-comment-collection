"""Output writers: crash-safe JSONL, utf-8-sig CSV, meta.json, zip.

Platform-blind: rows come from ``adapter.to_row`` and column order from the
selected field keys. JSONL is the canonical dataset; CSV is a convenience
export for Excel.
"""

from __future__ import annotations

import csv
import json
import zipfile
from dataclasses import asdict
from pathlib import Path


class JsonlSink:
    """Append-only, flushed-per-row JSONL writer."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = path.open("a", encoding="utf-8", newline="\n")
        self._ids: set[str] = set()
        for line in self._existing_lines():
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if "id" in record:
                self._ids.add(str(record["id"]))

    def _existing_lines(self):
        if not self.path.exists():
            return []
        # Read before opening in append mode to seed dedup state.
        return self.path.read_text(encoding="utf-8").splitlines()

    def seen(self, item_id: str) -> bool:
        return item_id in self._ids

    def append(self, row: dict) -> bool:
        """Write a row unless its id was already written. Returns True if written."""
        item_id = str(row.get("id", ""))
        if item_id and item_id in self._ids:
            return False
        self._fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        self._fh.flush()
        if item_id:
            self._ids.add(item_id)
        return True

    def close(self) -> None:
        self._fh.close()

    def __enter__(self) -> JsonlSink:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def __len__(self) -> int:
        return len(self._ids)


def jsonl_to_csv(jsonl_path: Path, csv_path: Path, fields: list[str]) -> Path:
    """Stream JSONL into CSV with utf-8-sig so Excel opens Chinese correctly."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with (
        jsonl_path.open("r", encoding="utf-8") as src,
        csv_path.open("w", encoding="utf-8-sig", newline="") as dst,
    ):
        writer = csv.DictWriter(dst, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for line in src:
            line = line.strip()
            if not line:
                continue
            writer.writerow(json.loads(line))
    return csv_path


def write_meta(path: Path, meta: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def zip_dir(path: Path, *, files: list[Path] | None = None) -> Path:
    """Zip the run's files next to the output folder; returns the archive path."""
    archive = path.parent / f"{path.name}.zip"
    targets = files if files is not None else sorted(p for p in path.rglob("*") if p.is_file())
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in targets:
            zf.write(file, arcname=file.relative_to(path))
    return archive


def dataclass_meta(obj) -> dict:
    return asdict(obj)
