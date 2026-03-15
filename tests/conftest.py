"""pytest configuration and fixtures for hodoku-py tests."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
HODOKU_JAR = PROJECT_ROOT / "hodoku" / "hodoku.jar"


def pytest_collection_modifyitems(items: list) -> None:
    """Re-order collected tests: unit tests first, then reglib, then parity."""
    def _sort_key(item):
        markers = {m.name for m in item.iter_markers()}
        if "unit" in markers:
            return 0
        parent = Path(item.fspath).parent.name
        if parent == "reglib":
            return 1
        if parent == "parity":
            return 3
        return 2  # other top-level test files
    items.sort(key=_sort_key)


def _hodoku_available() -> bool:
    """Return True if hodoku.jar and Java are available."""
    if not HODOKU_JAR.exists():
        return False
    if shutil.which("java") is None:
        return False
    try:
        result = subprocess.run(
            ["java", "-jar", str(HODOKU_JAR), "/lt"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(PROJECT_ROOT),
        )
        return "List of Techniques" in result.stdout
    except Exception:
        return False


@pytest.fixture(scope="session")
def hodoku_available() -> bool:
    """Session-scoped fixture: skip the test if HoDoKu is not available."""
    available = _hodoku_available()
    if not available:
        pytest.skip("HoDoKu JAR or Java not available")
    return available
