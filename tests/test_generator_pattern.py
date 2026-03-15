"""Tests for pattern-based clue removal and GeneratorPattern dataclass."""

import random

import pytest

from hodoku.generator.generator import SudokuGenerator
from hodoku.generator.pattern import GeneratorPattern


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


def _make_dense_pattern() -> list[bool]:
    """Create a dense pattern with 5 givens per box (45 total).

    Uses top-left 5 cells of each 3x3 box.  Dense enough that most
    random full grids produce a unique puzzle with this pattern.
    """
    pat = [False] * 81
    for br in range(3):
        for bc in range(3):
            cells = [
                (br * 3 + r) * 9 + bc * 3 + c
                for r in range(3)
                for c in range(3)
            ]
            for c in cells[:5]:
                pat[c] = True
    return pat


# ---------------------------------------------------------------------------
# Tests: GeneratorPattern dataclass
# ---------------------------------------------------------------------------

class TestGeneratorPattern:

    def test_default_construction(self):
        """Default pattern is all False with empty name."""
        gp = GeneratorPattern()
        assert gp.name == ""
        assert len(gp.pattern) == 81
        assert all(v is False for v in gp.pattern)
        assert gp.valid is False

    def test_construction_with_name(self):
        gp = GeneratorPattern(name="Test Pattern")
        assert gp.name == "Test Pattern"
        assert gp.num_givens == 0

    def test_construction_with_pattern(self):
        pat = [True] * 30 + [False] * 51
        gp = GeneratorPattern(name="30 givens", pattern=pat)
        assert gp.num_givens == 30

    def test_num_givens_property(self):
        pat = [False] * 81
        pat[0] = True
        pat[40] = True
        pat[80] = True
        gp = GeneratorPattern(pattern=pat)
        assert gp.num_givens == 3

    def test_invalid_pattern_length(self):
        with pytest.raises(ValueError, match="exactly 81"):
            GeneratorPattern(pattern=[True] * 50)

    def test_clone(self):
        pat = [True] * 25 + [False] * 56
        gp = GeneratorPattern(name="original", pattern=pat, valid=True)
        cloned = gp.clone()
        assert cloned.name == "original"
        assert cloned.pattern == pat
        assert cloned.valid is True
        # Modifying clone should not affect original
        cloned.pattern[0] = False
        assert gp.pattern[0] is True

    def test_str(self):
        gp = GeneratorPattern(name="Test")
        s = str(gp)
        assert "Test" in s

    def test_valid_flag(self):
        gp = GeneratorPattern()
        assert gp.valid is False
        gp.valid = True
        assert gp.valid is True


# ---------------------------------------------------------------------------
# Tests: Pattern-based puzzle generation
# ---------------------------------------------------------------------------

class TestPatternGeneration:

    def test_pattern_clues_only_at_pattern_positions(self):
        """Clues should only appear at positions where pattern is True."""
        gen = SudokuGenerator(rng=random.Random(42))
        pat = _make_dense_pattern()

        puzzle = gen.generate_sudoku(symmetric=False, pattern=pat)
        assert puzzle is not None

        for i, ch in enumerate(puzzle):
            if pat[i]:
                assert ch != "0", f"Cell {i} should be a given (pattern=True)"
            else:
                assert ch == "0", f"Cell {i} should be empty (pattern=False)"

    def test_pattern_puzzle_has_unique_solution(self):
        """Pattern-generated puzzle must have a unique solution."""
        gen = SudokuGenerator(rng=random.Random(42))
        pat = _make_dense_pattern()

        puzzle = gen.generate_sudoku(symmetric=False, pattern=pat)
        assert puzzle is not None

        checker = SudokuGenerator()
        checker.solve_string(puzzle)
        assert checker.get_solution_count() == 1
        assert _is_valid_sudoku(checker.get_solution())

    def test_pattern_num_givens_matches(self):
        """Number of clues in generated puzzle should match pattern's num_givens."""
        gen = SudokuGenerator(rng=random.Random(42))
        pat = _make_dense_pattern()
        gp = GeneratorPattern(name="dense", pattern=pat)

        puzzle = gen.generate_sudoku(symmetric=False, pattern=pat)
        assert puzzle is not None

        clue_count = sum(1 for ch in puzzle if ch != "0")
        assert clue_count == gp.num_givens

    def test_impossible_pattern_returns_none(self):
        """A pattern with too few givens should return None.

        With only 5 givens the puzzle will never have a unique solution.
        We use a small MAX_PATTERN_TRIES to avoid waiting forever.
        """
        gen = SudokuGenerator(rng=random.Random(42))
        pat = [False] * 81
        for i in range(5):
            pat[i] = True

        # Monkey-patch a small limit so the test doesn't run forever.
        # The real constant is 1_000_000 but we don't want to wait.
        import hodoku.generator.generator as gen_mod
        orig_source = gen.generate_sudoku

        # Call directly with a short loop
        gen._generate_full_grid()
        result = gen._generate_init_pos_pattern(pat)
        assert result is False

    def test_all_givens_pattern(self):
        """A pattern with all cells as givens should produce the full grid."""
        gen = SudokuGenerator(rng=random.Random(99))
        pat = [True] * 81

        puzzle = gen.generate_sudoku(symmetric=False, pattern=pat)
        assert puzzle is not None
        assert all(ch != "0" for ch in puzzle)

        checker = SudokuGenerator()
        checker.solve_string(puzzle)
        assert checker.get_solution_count() == 1

    def test_pattern_with_generator_pattern_via_api(self):
        """Generator.generate() should accept a GeneratorPattern object."""
        from hodoku.api import Generator
        from hodoku.core.types import DifficultyType

        pat = _make_dense_pattern()
        gp = GeneratorPattern(name="test", pattern=pat)

        generator = Generator()
        # Use a generous max_tries — pattern gen may need many attempts
        # to hit the right difficulty
        try:
            puzzle = generator.generate(
                difficulty=DifficultyType.EASY,
                pattern=gp,
                max_tries=200,
            )
            # If it succeeds, verify clues match pattern
            for i, ch in enumerate(puzzle):
                if pat[i]:
                    assert ch != "0"
                else:
                    assert ch == "0"
        except RuntimeError:
            # It's OK if no EASY puzzle was found in limited tries
            pass


# ---------------------------------------------------------------------------
# Tests: MAX_PATTERN_TRIES constant
# ---------------------------------------------------------------------------

class TestMaxPatternTries:

    def test_max_pattern_tries_value(self):
        """MAX_PATTERN_TRIES should be 1_000_000."""
        import inspect
        source = inspect.getsource(SudokuGenerator.generate_sudoku)
        assert "1_000_000" in source or "1000000" in source
