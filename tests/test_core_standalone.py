"""Guard the copy-the-core promise: importing the core must not pull in the UI."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "skills" / "bilibili" / "core"


def _run_in_core(body: str) -> subprocess.CompletedProcess:
    code = f"import sys; sys.path.insert(0, r'{CORE}'); import bilicrawl; {body}"
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)


def test_core_imports_without_ui_dependencies():
    result = _run_in_core(
        "heavy = [m for m in ('streamlit', 'pandas', 'app') if m in sys.modules]; "
        "print(','.join(heavy))"
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "", f"core pulled in UI modules: {result.stdout.strip()}"


def test_core_only_needs_stdlib_requests_protobuf():
    allowed_top = {
        "requests",
        "google",
        "urllib3",
        "certifi",
        "charset_normalizer",
        "idna",
        "bilicrawl",
        # Internal module of the protobuf C extension; not a real dependency.
        "cython_runtime",
    }
    result = _run_in_core(
        "tops = sorted({m.split('.')[0] for m in sys.modules}); print('\\n'.join(tops))"
    )
    assert result.returncode == 0, result.stderr
    third_party = {
        m
        for m in result.stdout.split()
        if m not in sys.stdlib_module_names and m not in allowed_top and not m.startswith("_")
    }
    assert third_party == set(), f"unexpected core dependencies: {third_party}"
