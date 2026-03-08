"""pytest configuration for the SDM broad-variety test suite.

Provides:
  --sdm-file PATH    path to an .sdm file (required to run any tests)
  --sdm-count N      limit to N randomly sampled puzzles (default: all)
  --sdm-seed N       RNG seed for random sampling (default: 42)

Session fixtures:
  sdm_entries          the sampled SdmEntry objects
  hodoku_sdm_results   dict[puzzle, HodokuResult] — one JVM invocation
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.hodoku_harness import HodokuResult, run_hodoku_batch

PROJECT_ROOT = Path(__file__).parent.parent.parent
TESTDATA_DIR = PROJECT_ROOT / "tests" / "testdata"

# Matches a valid puzzle line: exactly 81 digits/dots (ignoring surrounding whitespace)
_PUZZLE_RE = re.compile(r'^[0-9.]{81}$')


@dataclass
class SdmEntry:
    puzzle: str
    section: str | None  # most recent # comment, or None if before any comment
    test_id: str


def _resolve_sdm_path(sdm_file: str) -> Path:
    """Resolve --sdm-file to an actual path.

    Accepts:
      - absolute path
      - path relative to project root
      - bare stem like "top1465" (looked up in tests/testdata/)
    """
    path = Path(sdm_file)
    if path.is_absolute():
        return path
    candidate = PROJECT_ROOT / path
    if candidate.exists():
        return candidate
    stem = path.stem if path.suffix else sdm_file
    for suffix in (".sdm", ".txt"):
        candidate = TESTDATA_DIR / (stem + suffix)
        if candidate.exists():
            return candidate
    return PROJECT_ROOT / path


def _load_sdm(path: Path, count: int | None, seed: int, *, file_stem: str | None = None) -> list[SdmEntry]:
    """Parse an .sdm file into SdmEntry objects.

    Lines starting with # are section titles unless the content after # is
    itself a valid puzzle string (i.e. a commented-out puzzle), in which case
    the line is silently skipped.
    """
    entries: list[SdmEntry] = []
    section: str | None = None
    section_counts: dict[str | None, int] = {}

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            content = stripped[1:].strip()
            if not _PUZZLE_RE.match(content):
                # It's a section title, not a commented-out puzzle
                section = content or None
            continue
        if _PUZZLE_RE.match(stripped):
            puzzle = stripped
            idx = section_counts.get(section, 0)
            section_counts[section] = idx + 1
            slug = re.sub(r'\s+', '_', section) if section else None
            local_id = f"{slug}/p{idx}" if slug else f"p{idx}"
            test_id = f"{file_stem}::{local_id}" if file_stem else local_id
            entries.append(SdmEntry(puzzle=puzzle, section=section, test_id=test_id))

    if count is not None and len(entries) > count:
        rng = random.Random(seed)
        entries = rng.sample(entries, count)

    return entries


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--sdm-file",
        default=None,
        help="Path to .sdm puzzle file to test (required for tests/sdm/).",
    )
    parser.addoption(
        "--sdm-count",
        type=int,
        default=None,
        help="Limit to N randomly sampled puzzles (default: all).",
    )
    parser.addoption(
        "--sdm-seed",
        type=int,
        default=42,
        help="RNG seed for random sampling (default: 42).",
    )


@pytest.fixture(scope="session")
def sdm_entries(request: pytest.FixtureRequest) -> list[SdmEntry]:
    sdm_file = request.config.getoption("--sdm-file")
    if sdm_file is None:
        pytest.skip("--sdm-file not provided")
    count = request.config.getoption("--sdm-count")
    seed = request.config.getoption("--sdm-seed")
    path = _resolve_sdm_path(sdm_file)
    if not path.exists():
        pytest.fail(f"--sdm-file not found: {path}")
    return _load_sdm(path, count, seed, file_stem=path.stem)


@pytest.fixture(scope="session")
def hodoku_sdm_results(
    sdm_entries: list[SdmEntry],
    hodoku_available: bool,  # from parent conftest — skips if HoDoKu absent
) -> dict[str, HodokuResult]:
    """Run HoDoKu on all selected puzzles in one JVM invocation."""
    return run_hodoku_batch([e.puzzle for e in sdm_entries])
