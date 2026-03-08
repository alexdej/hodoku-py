"""pytest configuration and fixtures for hodoku-py tests."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from tests.hodoku_harness import HodokuResult, run_hodoku

PROJECT_ROOT = Path(__file__).parent.parent
HODOKU_JAR = PROJECT_ROOT / "hodoku" / "hodoku.jar"

# Roadmap order: simpler/more fundamental techniques come first so a
# regression in a low-level rule surfaces in the earliest possible suite.
_FILE_ORDER = [
    "test_cell_set.py",
    "test_grid.py",
    "test_brute_force.py",
    "test_validate_singles.py",
    "test_validate_subsets.py",
    "test_validate_single_digit.py",
    "test_validate_wings.py",
    "test_validate_coloring.py",
    "test_validate_uniqueness.py",
    "test_validate_fish.py",
    "test_validate_finned_fish.py",
    "test_validate_xchain.py",
    "test_validate_xychain.py",
    "test_validate_aic.py",
    "test_validate_als.py",
]
_FILE_RANK = {name: i for i, name in enumerate(_FILE_ORDER)}


def pytest_collection_modifyitems(items: list) -> None:
    """Re-order collected tests so files run in roadmap order."""
    items.sort(key=lambda item: _FILE_RANK.get(Path(item.fspath).name, len(_FILE_ORDER)))


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


def hodoku_solve(puzzle: str) -> HodokuResult:
    """Run HoDoKu on *puzzle* and return the parsed result.

    Raises RuntimeError if HoDoKu is not available or returns no result.
    """
    if not _hodoku_available():
        raise RuntimeError("HoDoKu is not available")
    result = run_hodoku(puzzle)
    if result is None:
        raise RuntimeError(f"HoDoKu returned no result for puzzle: {puzzle}")
    return result


@pytest.fixture
def solve_with_hodoku(hodoku_available):  # noqa: F811
    """Fixture that exposes hodoku_solve(), skipping if HoDoKu is unavailable."""
    return hodoku_solve
