"""pytest configuration for the parity test suite.

Provides:
  --puzzle-file PATH       path to a puzzle file (required to run any tests)
  --puzzle-count N         limit to N randomly sampled puzzles (default: all)
  --puzzle-seed N          RNG seed for random sampling (default: 42)
  --hodoku-backend MODE    "py4j" (default) or "batch"

Session fixtures:
  hodoku_parity_results   lazy solver that returns HodokuResult per puzzle
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
class PuzzleEntry:
    puzzle: str
    section: str | None  # most recent # comment, or None if before any comment
    test_id: str


def _resolve_puzzle_path(puzzle_file: str) -> Path:
    """Resolve --puzzle-file to an actual path.

    Accepts:
      - absolute path
      - path relative to project root
      - bare stem like "top1465" (looked up in tests/testdata/)
      - name with dots like "exemplars-1.0" (tried as-is + with suffixes)
    """
    path = Path(puzzle_file)
    if path.is_absolute():
        return path
    candidate = PROJECT_ROOT / path
    if candidate.exists():
        return candidate
    # Try as-is in testdata (handles "exemplars-1.0.txt" etc.)
    candidate = TESTDATA_DIR / puzzle_file
    if candidate.exists():
        return candidate
    # Try appending common suffixes to the full input string
    for suffix in (".sdm", ".txt"):
        candidate = TESTDATA_DIR / (puzzle_file + suffix)
        if candidate.exists():
            return candidate
    return PROJECT_ROOT / path


def _load_puzzle_file(path: Path, count: int | None, seed: int, *, file_stem: str | None = None) -> list[PuzzleEntry]:
    """Parse a puzzle file into PuzzleEntry objects.

    Lines starting with # are section titles unless the content after # is
    itself a valid puzzle string (i.e. a commented-out puzzle), in which case
    the line is silently skipped.
    """
    entries: list[PuzzleEntry] = []
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
        # Handle lines with trailing comments: "puzzle # annotation"
        puzzle_part = stripped.split("#")[0].strip()
        if _PUZZLE_RE.match(puzzle_part):
            puzzle = puzzle_part
            idx = section_counts.get(section, 0)
            section_counts[section] = idx + 1
            slug = re.sub(r'\s+', '_', section) if section else None
            local_id = f"{slug}/p{idx}" if slug else f"p{idx}"
            test_id = f"{file_stem}::{local_id}" if file_stem else local_id
            entries.append(PuzzleEntry(puzzle=puzzle, section=section, test_id=test_id))

    if count is not None and len(entries) > count:
        rng = random.Random(seed)
        entries = rng.sample(entries, count)

    return entries


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--puzzle-file",
        default=None,
        help="Path to puzzle file to test (required for tests/parity/).",
    )
    parser.addoption(
        "--puzzle-count",
        type=int,
        default=None,
        help="Limit to N randomly sampled puzzles (default: all).",
    )
    parser.addoption(
        "--puzzle-seed",
        type=int,
        default=42,
        help="RNG seed for random sampling (default: 42).",
    )
    parser.addoption(
        "--hodoku-backend",
        default="py4j",
        choices=["py4j", "batch"],
        help="HoDoKu backend: 'py4j' (default, persistent JVM) or 'batch' (CLI subprocess).",
    )


# ---------------------------------------------------------------------------
# Batch backend (original) — solves puzzles via CLI in chunks
# ---------------------------------------------------------------------------

BATCH_SIZE = 100


class _BatchHodokuResults:
    """Solves puzzles via HoDoKu CLI in batches, on demand."""

    def __init__(self, puzzles: list[str]) -> None:
        self._puzzles = puzzles
        self._cache: dict[str, HodokuResult] = {}
        self._chunk_of: dict[str, int] = {}
        for i, p in enumerate(puzzles):
            self._chunk_of[p] = i // BATCH_SIZE
        self._solved_chunks: set[int] = set()
        self._total_chunks = (len(puzzles) + BATCH_SIZE - 1) // BATCH_SIZE

    def get(self, puzzle: str) -> HodokuResult | None:
        if puzzle in self._cache:
            return self._cache.get(puzzle)
        chunk_idx = self._chunk_of.get(puzzle)
        if chunk_idx is None:
            return None
        self._solve_chunk(chunk_idx)
        return self._cache.get(puzzle)

    def _solve_chunk(self, chunk_idx: int) -> None:
        if chunk_idx in self._solved_chunks:
            return
        start = chunk_idx * BATCH_SIZE
        end = min(start + BATCH_SIZE, len(self._puzzles))
        print(
            f"\n[hodoku:batch] Solving puzzles {start+1}-{end} of {len(self._puzzles)} "
            f"(chunk {chunk_idx+1}/{self._total_chunks})..."
        )
        chunk = self._puzzles[start:end]
        self._cache.update(run_hodoku_batch(chunk))
        self._solved_chunks.add(chunk_idx)

    def shutdown(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Py4J backend — persistent JVM, solves one puzzle at a time
# ---------------------------------------------------------------------------

class _Py4jHodokuResults:
    """Solves puzzles via Py4J gateway, one at a time on demand."""

    def __init__(self) -> None:
        from tests.hodoku_gateway import HodokuGateway
        print("\n[hodoku:py4j] Starting JVM gateway...")
        self._gateway = HodokuGateway()
        self._cache: dict[str, HodokuResult] = {}

    def get(self, puzzle: str) -> HodokuResult | None:
        if puzzle not in self._cache:
            self._cache[puzzle] = self._gateway.solve(puzzle)
        return self._cache[puzzle]

    def shutdown(self) -> None:
        self._gateway.shutdown()


# ---------------------------------------------------------------------------
# Protocol type for the test to depend on
# ---------------------------------------------------------------------------

class HodokuResults:
    """Protocol-like base for both backends."""
    def get(self, puzzle: str) -> HodokuResult | None: ...
    def shutdown(self) -> None: ...


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def hodoku_parity_results(
    request: pytest.FixtureRequest,
    hodoku_available: bool,
) -> HodokuResults:
    """Provide lazy access to HoDoKu results via the selected backend."""
    puzzle_file = request.config.getoption("--puzzle-file")
    if puzzle_file is None:
        pytest.skip("--puzzle-file not provided")
    backend = request.config.getoption("--hodoku-backend")

    count = request.config.getoption("--puzzle-count")
    seed = request.config.getoption("--puzzle-seed")
    path = _resolve_puzzle_path(puzzle_file)
    if not path.exists():
        pytest.fail(f"--puzzle-file not found: {path}")
    entries = _load_puzzle_file(path, count, seed, file_stem=path.stem)
    puzzles = [e.puzzle for e in entries]

    if backend == "py4j":
        results = _Py4jHodokuResults()
    else:
        results = _BatchHodokuResults(puzzles)

    request.addfinalizer(results.shutdown)
    return results
