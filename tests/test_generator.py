"""Tests for the backtracking solver in hodoku.generator."""

import pytest

from hodoku.core.grid import Grid
from hodoku.generator.generator import SudokuGenerator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_valid_sudoku(values: list[int]) -> bool:
    """Verify a solved sudoku has no duplicates in any row/col/box."""
    for r in range(9):
        row = values[r * 9 : r * 9 + 9]
        if sorted(row) != list(range(1, 10)):
            return False
    for c in range(9):
        col = [values[r * 9 + c] for r in range(9)]
        if sorted(col) != list(range(1, 10)):
            return False
    for br in range(3):
        for bc in range(3):
            box = [
                values[(br * 3 + dr) * 9 + bc * 3 + dc]
                for dr in range(3)
                for dc in range(3)
            ]
            if sorted(box) != list(range(1, 10)):
                return False
    return True


def _matches_clues(puzzle: str, solution: list[int]) -> bool:
    """Verify the solution contains all clues from the puzzle string."""
    for i, ch in enumerate(puzzle):
        if ch.isdigit() and ch != "0":
            if solution[i] != int(ch):
                return False
    return True


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

# Puzzles known to have exactly one solution (from Java SudokuGenerator.main)
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

# A fully solved grid
SOLVED_GRID = "731526984546918732892374615683145279957283461124769853279851346365497128418632597"


# ---------------------------------------------------------------------------
# Tests: solve_string
# ---------------------------------------------------------------------------

class TestSolveString:

    @pytest.mark.parametrize("puzzle", UNIQUE_PUZZLES)
    def test_unique_solution(self, puzzle: str):
        gen = SudokuGenerator()
        gen.solve_string(puzzle)
        assert gen.get_solution_count() == 1
        sol = gen.get_solution()
        assert _is_valid_sudoku(sol)
        assert _matches_clues(puzzle, sol)

    def test_solved_grid(self):
        gen = SudokuGenerator()
        gen.solve_string(SOLVED_GRID)
        assert gen.get_solution_count() == 1
        assert gen.get_solution_as_string() == SOLVED_GRID

    def test_empty_grid_multiple_solutions(self):
        gen = SudokuGenerator()
        gen.solve_string("0" * 81)
        assert gen.get_solution_count() == 2

    def test_invalid_puzzle(self):
        # Two 1s in the same row
        gen = SudokuGenerator()
        gen.solve_string("11" + "0" * 79)
        assert gen.get_solution_count() == 0


# ---------------------------------------------------------------------------
# Tests: solve_values
# ---------------------------------------------------------------------------

class TestSolveValues:

    @pytest.mark.parametrize("puzzle", UNIQUE_PUZZLES)
    def test_unique_via_values(self, puzzle: str):
        gen = SudokuGenerator()
        vals = [int(ch) if ch.isdigit() else 0 for ch in puzzle]
        gen.solve_values(vals)
        assert gen.get_solution_count() == 1
        sol = gen.get_solution()
        assert _is_valid_sudoku(sol)
        assert _matches_clues(puzzle, sol)


# ---------------------------------------------------------------------------
# Tests: valid_solution / get_number_of_solutions via Grid
# ---------------------------------------------------------------------------

class TestGridAPI:

    @pytest.mark.parametrize("puzzle", UNIQUE_PUZZLES)
    def test_valid_solution(self, puzzle: str):
        gen = SudokuGenerator()
        grid = Grid()
        grid.set_sudoku(puzzle)
        assert gen.valid_solution(grid) is True
        assert grid.is_solution_set()
        assert _is_valid_sudoku(grid.solution)

    @pytest.mark.parametrize("puzzle", UNIQUE_PUZZLES)
    def test_number_of_solutions_unique(self, puzzle: str):
        gen = SudokuGenerator()
        grid = Grid()
        grid.set_sudoku(puzzle)
        assert gen.get_number_of_solutions(grid) == 1

    def test_number_of_solutions_multiple(self):
        gen = SudokuGenerator()
        grid = Grid()
        grid.set_sudoku("0" * 81)
        assert gen.get_number_of_solutions(grid) == 2

    def test_solution_stored_on_grid(self):
        gen = SudokuGenerator()
        grid = Grid()
        grid.set_sudoku(UNIQUE_PUZZLES[0])
        gen.valid_solution(grid)
        # Solution should match solve_string result
        gen.solve_string(UNIQUE_PUZZLES[0])
        expected = gen.get_solution()
        assert grid.solution == expected


# ---------------------------------------------------------------------------
# Tests: consistency between entry points
# ---------------------------------------------------------------------------

class TestConsistency:

    @pytest.mark.parametrize("puzzle", UNIQUE_PUZZLES[:3])
    def test_string_vs_values_same_solution(self, puzzle: str):
        gen = SudokuGenerator()

        gen.solve_string(puzzle)
        sol_str = gen.get_solution()

        vals = [int(ch) if ch.isdigit() else 0 for ch in puzzle]
        gen.solve_values(vals)
        sol_vals = gen.get_solution()

        assert sol_str == sol_vals

    @pytest.mark.parametrize("puzzle", UNIQUE_PUZZLES[:3])
    def test_grid_vs_string_same_solution(self, puzzle: str):
        gen = SudokuGenerator()

        gen.solve_string(puzzle)
        sol_str = gen.get_solution()

        grid = Grid()
        grid.set_sudoku(puzzle)
        gen.valid_solution(grid)

        assert grid.solution == sol_str
