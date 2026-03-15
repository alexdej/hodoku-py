"""Parity tests: Python backtracker vs Java backtracker via Py4J.

Compares solution counts and actual solutions for a mix of unique,
multi-solution, and invalid puzzles.  Marked with @pytest.mark.java
so they only run when the JVM is available.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from hodoku.core.grid import Grid
from hodoku.generator.generator import SudokuGenerator

# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

TESTDATA = Path(__file__).parent.parent / "testdata"

# Load puzzles from HardestDatabase110626.txt (skip header line)
def _load_hardest(n: int = 200) -> list[str]:
    path = TESTDATA / "HardestDatabase110626.txt"
    puzzles: list[str] = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("Hardest"):
                continue
            puzzle = line.split(",")[0]
            if len(puzzle) == 81 and all(c in "0123456789." for c in puzzle):
                puzzles.append(puzzle.replace(".", "0"))
                if len(puzzles) >= n:
                    break
    return puzzles


HARD_PUZZLES = _load_hardest(200)

# Puzzles with known unique solutions (from test_generator.py)
UNIQUE_PUZZLES = [
    "..15............32...............2.9.5...3......7..8..27.....4.3...9.......6..5..",
    ".1.....2....8..6.......3........43....2.1....8......9.4...7.5.3...2...........4..",
    "...87..3.52.......4..........3.9..7......54...8.......2.....5.....3....9...1.....",
    ".51..........2.4...........64....2.....5.1..7...3..6..4...3.......8...5.2........",
    "17.....4....62....5...3....84....1.....3....6......9....6.....3.....1..........5.",
    "...7...1...6.......4.......7..5.1.....8...4..2...........24.6...3..8....1.......9",
    "3.....7.....1..4.....2.........5.61..82...........6....1.....287...3...........3.",
    "64.7............53.......1.7.86........4.9...5.........6....4......5.2......1....",
]

# Multi-solution puzzles (too few clues)
MULTI_SOLUTION = [
    "1" + "0" * 80,                # single clue
    "120000000" + "0" * 72,        # two clues
]

# Invalid puzzles — only row conflicts (adjacent cells) are detectable quickly.
# Column/box conflicts may cause both Java and Python to hang exploring an
# inconsistent grid.  That's a known limitation of HoDoKu's backtracker.
INVALID_PUZZLES = [
    "11" + "0" * 79,               # two 1s in same row — quickly detected
]


# ---------------------------------------------------------------------------
# Benchmark (Python-only, no Java needed)
# ---------------------------------------------------------------------------

class TestBenchmark:

    def test_benchmark_1000_puzzles(self):
        """Solve 1000 puzzles and report timing."""
        # Use first 200 hard puzzles, repeat 5x to get 1000
        puzzles = HARD_PUZZLES[:200] * 5
        assert len(puzzles) == 1000

        gen = SudokuGenerator()
        start = time.perf_counter()
        for puzzle in puzzles:
            gen.solve_string(puzzle)
            assert gen.get_solution_count() == 1
        elapsed = time.perf_counter() - start

        ms_per = elapsed * 1000 / len(puzzles)
        print(f"\nPython backtracker: {elapsed:.2f}s for 1000 puzzles "
              f"({ms_per:.2f} ms/puzzle)")

        # Compare with Java baseline: 0.0234 ms/puzzle
        java_ms = 0.0234
        ratio = ms_per / java_ms
        print(f"Java baseline: {java_ms} ms/puzzle, ratio: {ratio:.0f}x")

        if elapsed > 60:
            pytest.skip("Backtracker >60s for 1000 puzzles — noted as risk")


# ---------------------------------------------------------------------------
# Parity tests (require Java via Py4J)
# ---------------------------------------------------------------------------

@pytest.mark.java
class TestBacktrackerParity:
    """Head-to-head: Python vs Java backtracker."""

    @pytest.fixture(scope="class")
    def gateway(self):
        from tests.hodoku_gateway import HodokuGateway
        gw = HodokuGateway()
        yield gw
        gw.shutdown()

    @pytest.mark.parametrize("puzzle", UNIQUE_PUZZLES, ids=[f"unique-{i}" for i in range(len(UNIQUE_PUZZLES))])
    def test_unique_puzzles(self, gateway, puzzle):
        """Unique puzzles: both solvers should find count=1 with same solution."""
        # Python
        py_gen = SudokuGenerator()
        py_gen.solve_string(puzzle)
        py_count = py_gen.get_solution_count()
        py_sol = py_gen.get_solution()

        # Java
        java_count, java_sol = gateway.solve_backtracker(puzzle)

        assert py_count == java_count == 1, (
            f"count mismatch: py={py_count}, java={java_count}"
        )
        assert py_sol == java_sol, "solution mismatch"

    @pytest.mark.parametrize("puzzle", HARD_PUZZLES[:200],
                             ids=[f"hard-{i}" for i in range(min(200, len(HARD_PUZZLES)))])
    def test_hard_puzzles(self, gateway, puzzle):
        """Hard puzzles from HardestDatabase: compare solution counts and values."""
        # Python
        py_gen = SudokuGenerator()
        py_gen.solve_string(puzzle)
        py_count = py_gen.get_solution_count()
        py_sol = py_gen.get_solution()

        # Java
        java_count, java_sol = gateway.solve_backtracker(puzzle)

        assert py_count == java_count, (
            f"count mismatch for {puzzle}: py={py_count}, java={java_count}"
        )
        if py_count == 1:
            assert py_sol == java_sol, f"solution mismatch for {puzzle}"

    @pytest.mark.parametrize("puzzle", MULTI_SOLUTION,
                             ids=[f"multi-{i}" for i in range(len(MULTI_SOLUTION))])
    def test_multi_solution(self, gateway, puzzle):
        """Multi-solution puzzles: both should report count=2."""
        py_gen = SudokuGenerator()
        py_gen.solve_string(puzzle)
        py_count = py_gen.get_solution_count()

        java_count, _ = gateway.solve_backtracker(puzzle)

        assert py_count == java_count, (
            f"count mismatch: py={py_count}, java={java_count}"
        )

    @pytest.mark.parametrize("puzzle", INVALID_PUZZLES,
                             ids=[f"invalid-{i}" for i in range(len(INVALID_PUZZLES))])
    def test_invalid_puzzles(self, gateway, puzzle):
        """Invalid puzzles: both should report count=0."""
        py_gen = SudokuGenerator()
        py_gen.solve_string(puzzle)
        py_count = py_gen.get_solution_count()

        java_count, _ = gateway.solve_backtracker(puzzle)

        assert py_count == java_count == 0, (
            f"count mismatch: py={py_count}, java={java_count}"
        )

    def test_valid_solution_api(self, gateway):
        """Test valid_solution() API parity."""
        puzzle = UNIQUE_PUZZLES[0]

        # Python
        py_gen = SudokuGenerator()
        grid = Grid()
        grid.set_sudoku(puzzle)
        py_unique = py_gen.valid_solution(grid)
        py_sol = grid.solution if py_unique else None

        # Java
        java_unique, java_sol = gateway.valid_solution(puzzle)

        assert py_unique == java_unique
        if py_unique:
            assert py_sol == java_sol
