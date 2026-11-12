from __future__ import annotations

from app.ui import registry


def test_discovers_bilibili():
    entries = registry.discover()
    ids = [e.id for e in entries]
    assert "bilibili" in ids


def test_skips_underscore_template():
    # _template exists on disk but must never be discovered.
    assert all(not e.skill_dir.name.startswith("_") for e in registry.discover())


def test_platform_module_exposes_contract_surface():
    entry = registry.get_platform("bilibili")
    assert entry is not None
    module = entry.module
    for name in ("parse_input", "credential_fields", "field_catalog", "create_adapter"):
        assert callable(getattr(module, name))
    assert module.PLATFORM_NAME_ZH


def test_display_name_by_locale():
    entry = registry.get_platform("bilibili")
    assert entry.display_name("zh") == entry.name_zh
    assert entry.display_name("en") == entry.name_en
