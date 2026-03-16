"""Tests for the Generator public API (difficulty-filtered generation)."""

import pytest

from hodoku.api import Generator, Solver
from hodoku.core.types import DifficultyType


# ---------------------------------------------------------------------------
# Tests: generate() with difficulty filtering
# ---------------------------------------------------------------------------

class TestGenerateDifficulty:

    @pytest.fixture(scope="class")
    def generator(self):
        return Generator()

    @pytest.fixture(scope="class")
    def solver(self):
        return Solver()

    def test_generate_easy(self, generator, solver):
        """Generate an EASY puzzle and verify its rating."""
        puzzle = generator.generate(difficulty=DifficultyType.EASY)
        assert len(puzzle) == 81
        result = solver.solve(puzzle)
        assert result.solved
        assert result.level == DifficultyType.EASY

    def test_generate_medium(self, generator, solver):
        """Generate a MEDIUM puzzle and verify its rating."""
        puzzle = generator.generate(difficulty=DifficultyType.MEDIUM)
        result = solver.solve(puzzle)
        assert result.solved
        assert result.level == DifficultyType.MEDIUM

    def test_generate_hard(self, generator, solver):
        """Generate a HARD puzzle and verify its rating."""
        puzzle = generator.generate(
            difficulty=DifficultyType.HARD, max_tries=50_000,
        )
        result = solver.solve(puzzle)
        assert result.solved
        assert result.level == DifficultyType.HARD

    def test_generate_unique_solution(self, generator):
        """Generated puzzle must have exactly one solution."""
        puzzle = generator.generate(difficulty=DifficultyType.EASY)
        assert generator.validate(puzzle) == "valid"

    def test_generate_at_least_17_clues(self, generator):
        """Generated puzzle must have at least 17 clues."""
        puzzle = generator.generate(difficulty=DifficultyType.EASY)
        clues = sum(1 for ch in puzzle if ch != "0")
        assert clues >= 17


# ---------------------------------------------------------------------------
# Tests: validate()
# ---------------------------------------------------------------------------

class TestValidate:

    @pytest.fixture(scope="class")
    def generator(self):
        return Generator()

    def test_valid_puzzle(self, generator):
        """A well-formed unique puzzle returns 'valid'."""
        puzzle = (
            "..15............32...............2.9.5...3......"
            "7..8..27.....4.3...9.......6..5.."
        )
        assert generator.validate(puzzle) == "valid"

    def test_multiple_solutions(self, generator):
        """A puzzle with too few clues returns 'multiple'."""
        puzzle = "1" + "0" * 80
        assert generator.validate(puzzle) == "multiple"
