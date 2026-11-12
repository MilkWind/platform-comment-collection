"""Discover platform skills by their ``skill.toml`` manifest.

Each ``skills/<name>/skill.toml`` declares the import module inside
``skills/<name>/core``. Directories starting with ``_`` (such as
``_template``) are skipped. Adding a platform is a new manifest, not a UI edit.
"""

from __future__ import annotations

import importlib
import sys
import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SKILLS_DIR = ROOT / "skills"


@dataclass(frozen=True)
class PlatformEntry:
    id: str
    module_name: str
    name_en: str
    name_zh: str
    order: int
    enabled: bool
    skill_dir: Path
    core_dir: Path

    @property
    def module(self):
        return importlib.import_module(self.module_name)

    def display_name(self, locale: str) -> str:
        return self.name_zh if locale.startswith("zh") else self.name_en


def _register_core_paths() -> None:
    for core in SKILLS_DIR.glob("*/core"):
        path = str(core)
        if path not in sys.path:
            sys.path.insert(0, path)


@lru_cache(maxsize=1)
def discover() -> list[PlatformEntry]:
    _register_core_paths()
    entries: list[PlatformEntry] = []
    for manifest in sorted(SKILLS_DIR.glob("*/skill.toml")):
        if manifest.parent.name.startswith("_"):
            continue
        data = tomllib.loads(manifest.read_text(encoding="utf-8")).get("platform", {})
        if not data.get("enabled", True):
            continue
        entries.append(
            PlatformEntry(
                id=data["id"],
                module_name=data["module"],
                name_en=data.get("name_en", data["id"]),
                name_zh=data.get("name_zh", data["id"]),
                order=int(data.get("order", 100)),
                enabled=bool(data.get("enabled", True)),
                skill_dir=manifest.parent,
                core_dir=manifest.parent / "core",
            )
        )
    return sorted(entries, key=lambda e: e.order)


def get_platform(platform_id: str) -> PlatformEntry | None:
    return next((e for e in discover() if e.id == platform_id), None)
