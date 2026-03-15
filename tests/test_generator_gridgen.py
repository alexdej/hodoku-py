"""Tests for full grid generation and symmetric clue removal."""

import random

import pytest

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


def _is_180_symmetric(puzzle: str) -> bool:
    """Check that the given pattern has 180-degree rotational symmetry."""
    for i in range(81):
        symm = 9 * (8 - i // 9) + (8 - i % 9)
        has_i = puzzle[i] != "0"
        has_symm = puzzle[symm] != "0"
        if has_i != has_symm:
            return False
    return True


def _count_clues(puzzle: str) -> int:
    return sum(1 for ch in puzzle if ch != "0")


# ---------------------------------------------------------------------------
# Tests: Full grid generation
# ---------------------------------------------------------------------------

class TestGenerateFullGrid:

    def test_full_grid_valid(self):
        """Generated full grid should be a valid solved sudoku."""
        gen = SudokuGenerator()
        gen._generate_full_grid()
        assert _is_valid_sudoku(gen._new_full_sudoku)

    def test_full_grid_complete(self):
        """Full grid should have no empty cells."""
        gen = SudokuGenerator()
        gen._generate_full_grid()
        assert 0 not in gen._new_full_sudoku

    def test_full_grid_different_each_time(self):
        """Two generations should (almost certainly) produce different grids."""
        gen = SudokuGenerator()
        gen._generate_full_grid()
        grid1 = list(gen._new_full_sudoku)
        gen._generate_full_grid()
        grid2 = list(gen._new_full_sudoku)
        assert grid1 != grid2

    def test_full_grid_seeded_deterministic(self):
        """Seeded RNG should produce the same grid each time."""
        gen1 = SudokuGenerator(rng=random.Random(42))
        gen1._generate_full_grid()
        grid1 = list(gen1._new_full_sudoku)

        gen2 = SudokuGenerator(rng=random.Random(42))
        gen2._generate_full_grid()
        grid2 = list(gen2._new_full_sudoku)

        assert grid1 == grid2


# ---------------------------------------------------------------------------
# Tests: generate_sudoku (symmetric)
# ---------------------------------------------------------------------------

class TestGenerateSudoku:

    def test_symmetric_puzzle_valid(self):
        """Generated symmetric puzzle should have a unique solution."""
        gen = SudokuGenerator()
        puzzle = gen.generate_sudoku(symmetric=True)
        assert puzzle is not None
        assert len(puzzle) == 81

        # Verify uniqueness
        gen2 = SudokuGenerator()
        gen2.solve_string(puzzle)
        assert gen2.get_solution_count() == 1

    def test_symmetric_puzzle_is_symmetric(self):
        """Generated symmetric puzzle should have 180-degree symmetry."""
        gen = SudokuGenerator()
        puzzle = gen.generate_sudoku(symmetric=True)
        assert _is_180_symmetric(puzzle)

    def test_symmetric_puzzle_min_clues(self):
        """Generated puzzle should have at least 17 clues."""
        gen = SudokuGenerator()
        puzzle = gen.generate_sudoku(symmetric=True)
        assert _count_clues(puzzle) >= 17

    def test_asymmetric_puzzle_valid(self):
        """Generated asymmetric puzzle should have a unique solution."""
        gen = SudokuGenerator()
        puzzle = gen.generate_sudoku(symmetric=False)
        assert puzzle is not None

        gen2 = SudokuGenerator()
        gen2.solve_string(puzzle)
        assert gen2.get_solution_count() == 1

    def test_asymmetric_puzzle_min_clues(self):
        """Generated asymmetric puzzle should have at least 17 clues."""
        gen = SudokuGenerator()
        puzzle = gen.generate_sudoku(symmetric=False)
        assert _count_clues(puzzle) >= 17

    def test_seeded_deterministic(self):
        """Seeded RNG should produce the same puzzle."""
        gen1 = SudokuGenerator(rng=random.Random(123))
        puzzle1 = gen1.generate_sudoku(symmetric=True)

        gen2 = SudokuGenerator(rng=random.Random(123))
        puzzle2 = gen2.generate_sudoku(symmetric=True)

        assert puzzle1 == puzzle2

    def test_solution_matches_clues(self):
        """Solution should contain all clues from the generated puzzle."""
        gen = SudokuGenerator()
        puzzle = gen.generate_sudoku(symmetric=True)

        gen2 = SudokuGenerator()
        gen2.solve_string(puzzle)
        sol = gen2.get_solution()

        for i, ch in enumerate(puzzle):
            if ch != "0":
                assert sol[i] == int(ch), f"Mismatch at cell {i}"

    def test_multiple_generations(self):
        """Generate 5 puzzles and verify all are valid and unique."""
        gen = SudokuGenerator()
        puzzles = set()
        for _ in range(5):
            puzzle = gen.generate_sudoku(symmetric=True)
            assert puzzle is not None
            assert _count_clues(puzzle) >= 17

            gen2 = SudokuGenerator()
            gen2.solve_string(puzzle)
            assert gen2.get_solution_count() == 1

            puzzles.add(puzzle)

        # All 5 should be different
        assert len(puzzles) == 5
