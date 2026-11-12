"""Prove the second-platform seam: enabling a manifest adds a tab with no app edits."""

from __future__ import annotations

import shutil
from pathlib import Path

from app.ui import registry

SKILLS = Path(__file__).resolve().parent.parent / "skills"


def test_enabling_template_adds_a_platform(tmp_path, monkeypatch):
    # Build a throwaway skills root with the template enabled under a real name.
    fake_skills = tmp_path / "skills"
    shutil.copytree(SKILLS / "_template", fake_skills / "acme")
    (fake_skills / "acme" / "core" / "examplecrawl").rename(
        fake_skills / "acme" / "core" / "acme_same_shapes"
    )
    manifest = fake_skills / "acme" / "skill.toml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8")
        .replace('id = "example"', 'id = "acme"')
        .replace('module = "examplecrawl"', 'module = "acme_same_shapes"')
        .replace("enabled = false", "enabled = true"),
        encoding="utf-8",
    )

    monkeypatch.setattr(registry, "SKILLS_DIR", fake_skills)
    registry.discover.cache_clear()
    try:
        entries = registry.discover()
        assert [e.id for e in entries] == ["acme"]
        assert entries[0].display_name("en") == "Example Platform"
        # Importing the module (with its model re-exports) must not need app code.
        assert entries[0].module.PLATFORM_ID == "example"
    finally:
        registry.discover.cache_clear()
