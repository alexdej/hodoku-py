"""Tests for the C-accelerated backtracking solver (_gen_accel).

Comparison tests: every solve is run through both the pure-Python path and the
C path, and results are asserted identical.  This is the primary correctness
guarantee for the C extension.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from hodoku.core.grid import Grid

# ---------------------------------------------------------------------------
# Skip entire module if C extension is not compiled
# ---------------------------------------------------------------------------

try:
    from hodoku.generator import _gen_accel

    if _gen_accel is None:
        raise ImportError("_gen_accel imported as None")
except ImportError:
    pytest.skip(
        "C accelerator not compiled; run: python setup.py build_ext --inplace",
        allow_module_level=True,
    )

from hodoku.generator.generator import (
    SudokuGenerator,
    _POSSIBLE_VALUES,
    _copy_state,
    _rebuild_internal,
    _set_all_exposed_singles,
    _set_cell_valid,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TESTDATA_DIR = Path(__file__).parent / "testdata"


def _solve_python(puzzle: str) -> tuple[int, list[int]]:
    """Solve using the pure-Python path only."""
    gen = SudokuGenerator()
    # Directly call _solve_py to bypass C accel dispatch
    s0 = gen._stack[0]
    s0.grid.__init__()
    s0.candidates = ()
    s0.cand_index = 0

    for i, ch in enumerate(puzzle[:81]):
        value = ord(ch) - ord("0")
        if 1 <= value <= 9:
            s0.grid.set_cell(i, value)
            if not _set_all_exposed_singles(s0.grid):
                return (0, [0] * 81)

    gen._solve_py()
    return (gen.get_solution_count(), gen.get_solution())


def _solve_c_string(puzzle: str) -> tuple[int, list[int]]:
    """Solve using the C accelerator's solve_string."""
    return _gen_accel.solve_string(puzzle)


def _solve_c_values(puzzle: str) -> tuple[int, list[int]]:
    """Solve using the C accelerator's solve_values."""
    vals = [int(ch) if ch.isdigit() else 0 for ch in puzzle]
    return _gen_accel.solve_values(vals)


def _solve_c_grid(puzzle: str) -> tuple[int, list[int]]:
    """Solve using the C accelerator via Grid marshalling (_solve_c path)."""
    gen = SudokuGenerator()
    grid = Grid()
    grid.set_sudoku(puzzle)
    # This will use _solve_c internally since _gen_accel is loaded
    gen._solve_grid(grid)
    return (gen.get_solution_count(), gen.get_solution())


def _load_puzzles(filename: str, max_count: int = 0) -> list[str]:
    """Load puzzle strings from a test data file."""
    path = TESTDATA_DIR / filename
    puzzles = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Extract 81-char puzzle (lines may have trailing comments)
        candidate = line.split()[0] if line else ""
        if len(candidate) >= 81 and all(
            c in "0123456789." for c in candidate[:81]
        ):
            puzzles.append(candidate[:81].replace(".", "0"))
        if max_count and len(puzzles) >= max_count:
            break
    return puzzles


# ---------------------------------------------------------------------------
# Test corpus
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def exemplars() -> list[str]:
    """Load exemplar puzzles (202 puzzles, all difficulty levels)."""
    return _load_puzzles("exemplars-1.0.txt")


@pytest.fixture(scope="module")
def hard_puzzles() -> list[str]:
    """Load top1465 hard puzzles (first 200)."""
    return _load_puzzles("top1465.sdm", max_count=200)


# ---------------------------------------------------------------------------
# Comparison tests: C vs Python produce identical results
# ---------------------------------------------------------------------------

class TestCvsPythonComparison:
    """The critical correctness test: C and Python must produce identical
    solution_count and solution for every puzzle."""

    def test_exemplars_solve_string(self, exemplars: list[str]):
        """Compare C solve_string vs Python on all exemplar puzzles."""
        assert len(exemplars) >= 200, f"Expected 200+ exemplars, got {len(exemplars)}"
        mismatches = []
        for puzzle in exemplars:
            py_count, py_sol = _solve_python(puzzle)
            c_count, c_sol = _solve_c_string(puzzle)
            if py_count != c_count or py_sol != c_sol:
                mismatches.append(
                    f"puzzle={puzzle[:20]}... py=({py_count},{py_sol[:5]}...) "
                    f"c=({c_count},{c_sol[:5]}...)"
                )
        assert not mismatches, (
            f"{len(mismatches)} mismatches out of {len(exemplars)}:\n"
            + "\n".join(mismatches[:10])
        )

    def test_exemplars_solve_values(self, exemplars: list[str]):
        """Compare C solve_values vs Python on all exemplar puzzles."""
        mismatches = []
        for puzzle in exemplars:
            py_count, py_sol = _solve_python(puzzle)
            c_count, c_sol = _solve_c_values(puzzle)
            if py_count != c_count or py_sol != c_sol:
                mismatches.append(puzzle[:20])
        assert not mismatches, f"{len(mismatches)} mismatches"

    def test_exemplars_grid_path(self, exemplars: list[str]):
        """Compare C via Grid marshalling vs Python on exemplar puzzles."""
        mismatches = []
        for puzzle in exemplars:
            py_count, py_sol = _solve_python(puzzle)
            c_count, c_sol = _solve_c_grid(puzzle)
            if py_count != c_count or py_sol != c_sol:
                mismatches.append(puzzle[:20])
        assert not mismatches, f"{len(mismatches)} mismatches"

    def test_hard_puzzles(self, hard_puzzles: list[str]):
        """Compare C vs Python on hard puzzles (top1465)."""
        assert len(hard_puzzles) >= 200, f"Expected 200+ hard puzzles, got {len(hard_puzzles)}"
        mismatches = []
        for puzzle in hard_puzzles:
            py_count, py_sol = _solve_python(puzzle)
            c_count, c_sol = _solve_c_string(puzzle)
            if py_count != c_count or py_sol != c_sol:
                mismatches.append(puzzle[:20])
        assert not mismatches, f"{len(mismatches)} mismatches"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_empty_grid(self):
        """Empty grid: MRV threshold=9 means all cells skipped → count=0."""
        py_count, py_sol = _solve_python("0" * 81)
        c_count, c_sol = _solve_c_string("0" * 81)
        assert py_count == c_count == 0

    def test_solved_grid(self):
        """Fully solved grid should return count=1."""
        solved = "731526984546918732892374615683145279957283461124769853279851346365497128418632597"
        py_count, py_sol = _solve_python(solved)
        c_count, c_sol = _solve_c_string(solved)
        assert py_count == c_count == 1
        assert py_sol == c_sol
        assert c_sol == [int(ch) for ch in solved]

    def test_single_clue(self):
        """Single clue → multiple solutions (count=2)."""
        puzzle = "1" + "0" * 80
        py_count, _ = _solve_python(puzzle)
        c_count, _ = _solve_c_string(puzzle)
        assert py_count == c_count == 2

    def test_invalid_duplicate_row(self):
        """Two identical adjacent digits in the same row → count=0."""
        puzzle = "11" + "0" * 79
        py_count, _ = _solve_python(puzzle)
        c_count, _ = _solve_c_string(puzzle)
        assert py_count == c_count == 0

    def test_invalid_contradictory_clues(self):
        """Clues that force a contradiction during propagation → count=0."""
        # Place 1-8 in row 0's first 8 cells, then 9 in cell 9 (col 1).
        # Cell 8 in row 0 must be 9, but 9 is also forced into col 1
        # from cell 9 — creates a box conflict.
        puzzle = "123456780" + "9" + "0" * 71
        py_count, _ = _solve_python(puzzle)
        c_count, _ = _solve_c_string(puzzle)
        assert py_count == c_count

    def test_solve_values_matches_solve_string(self):
        """solve_values and solve_string must produce identical results."""
        puzzle = "4...3.......6..8..........1....5..9..8....6...7.2........1.27..5.3....4.9........"
        str_count, str_sol = _gen_accel.solve_string(puzzle)
        vals = [int(ch) if ch.isdigit() else 0 for ch in puzzle]
        val_count, val_sol = _gen_accel.solve_values(vals)
        assert str_count == val_count
        assert str_sol == val_sol


# ---------------------------------------------------------------------------
# Benchmark: C vs Python timing
# ---------------------------------------------------------------------------

class TestBenchmark:

    def test_benchmark_c_vs_python(self, exemplars: list[str]):
        """Print C vs Python timing on exemplar puzzles.

        Not a pass/fail test — just prints timing for comparison.
        """
        puzzles = exemplars[:200]

        # Python timing
        t0 = time.perf_counter()
        for p in puzzles:
            _solve_python(p)
        py_time = time.perf_counter() - t0

        # C timing (solve_string)
        t0 = time.perf_counter()
        for p in puzzles:
            _gen_accel.solve_string(p)
        c_time = time.perf_counter() - t0

        speedup = py_time / c_time if c_time > 0 else float("inf")
        print(
            f"\n--- Backtracker benchmark ({len(puzzles)} puzzles) ---\n"
            f"  Python: {py_time:.3f}s ({py_time/len(puzzles)*1000:.2f} ms/puzzle)\n"
            f"  C:      {c_time:.3f}s ({c_time/len(puzzles)*1000:.2f} ms/puzzle)\n"
            f"  Speedup: {speedup:.1f}x"
        )
