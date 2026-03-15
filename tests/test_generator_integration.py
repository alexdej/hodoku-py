"""Generator Task 5: Integration testing + solver integration.

Comprehensive test suite covering:
1. Property tests at each difficulty level (EASY/MEDIUM/HARD/UNFAIR)
2. Symmetric puzzle tests (180-degree rotational symmetry)
3. Pattern puzzle tests (clues only at pattern positions)
4. Edge cases (empty pattern, too-few-givens, max_tries=0)
5. End-to-end: generate → solve → verify solution correctness
6. Benchmark: time generation for each difficulty level
7. BruteForceSolver uses grid.solution from generator
"""

import random
import time

import pytest

from hodoku.api import Generator, Solver
from hodoku.core.grid import Grid
from hodoku.core.scoring import DIFFICULTY_MAX_SCORE
from hodoku.core.types import DifficultyType, SolutionType
from hodoku.generator.generator import SudokuGenerator
from hodoku.solver.brute_force import BruteForceSolver


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
    """Check that clue positions have 180-degree rotational symmetry."""
    for i in range(81):
        mirror = 80 - i
        has_i = puzzle[i] != "0"
        has_mirror = puzzle[mirror] != "0"
        if has_i != has_mirror:
            return False
    return True


def _count_clues(puzzle: str) -> int:
    return sum(1 for ch in puzzle if ch != "0")


def _solution_string(values: list[int]) -> str:
    return "".join(str(v) for v in values)


# ---------------------------------------------------------------------------
# 1. Property tests at each difficulty level
# ---------------------------------------------------------------------------

class TestDifficultyProperty:
    """Generate N puzzles per difficulty, verify properties."""

    @pytest.fixture(scope="class")
    def generator(self):
        return Generator()

    @pytest.fixture(scope="class")
    def solver(self):
        return Solver()

    @pytest.mark.parametrize("n", range(3))
    def test_easy_properties(self, generator, solver, n):
        puzzle = generator.generate(difficulty=DifficultyType.EASY)
        assert len(puzzle) == 81
        assert _count_clues(puzzle) >= 17
        assert generator.validate(puzzle) == "valid"
        result = solver.solve(puzzle)
        assert result.solved
        assert result.level == DifficultyType.EASY

    @pytest.mark.parametrize("n", range(3))
    def test_medium_properties(self, generator, solver, n):
        puzzle = generator.generate(difficulty=DifficultyType.MEDIUM)
        assert len(puzzle) == 81
        assert _count_clues(puzzle) >= 17
        assert generator.validate(puzzle) == "valid"
        result = solver.solve(puzzle)
        assert result.solved
        assert result.level == DifficultyType.MEDIUM
        # Score should be above EASY max
        assert result.score >= DIFFICULTY_MAX_SCORE[DifficultyType.EASY]

    @pytest.mark.parametrize("n", range(2))
    def test_hard_properties(self, generator, solver, n):
        puzzle = generator.generate(
            difficulty=DifficultyType.HARD, max_tries=50_000,
        )
        assert len(puzzle) == 81
        assert _count_clues(puzzle) >= 17
        assert generator.validate(puzzle) == "valid"
        result = solver.solve(puzzle)
        assert result.solved
        assert result.level == DifficultyType.HARD
        assert result.score >= DIFFICULTY_MAX_SCORE[DifficultyType.MEDIUM]

    def test_unfair_properties(self, generator, solver):
        puzzle = generator.generate(
            difficulty=DifficultyType.UNFAIR, max_tries=100_000,
        )
        assert len(puzzle) == 81
        assert _count_clues(puzzle) >= 17
        assert generator.validate(puzzle) == "valid"
        result = solver.solve(puzzle)
        assert result.solved
        assert result.level == DifficultyType.UNFAIR
        assert result.score >= DIFFICULTY_MAX_SCORE[DifficultyType.HARD]


# ---------------------------------------------------------------------------
# 2. Symmetric puzzle tests
# ---------------------------------------------------------------------------

class TestSymmetricPuzzles:

    @pytest.fixture(scope="class")
    def generator(self):
        return Generator()

    def test_symmetric_generation_has_symmetry(self, generator):
        """Symmetric puzzles must have 180-degree rotational symmetry."""
        for _ in range(5):
            puzzle = generator.generate(
                difficulty=DifficultyType.EASY, symmetric=True,
            )
            assert _is_180_symmetric(puzzle), (
                f"Puzzle lacks 180° symmetry: {puzzle}"
            )

    def test_asymmetric_generation_is_valid(self, generator):
        """Asymmetric puzzles need not be symmetric but must still be valid."""
        puzzle = generator.generate(
            difficulty=DifficultyType.EASY, symmetric=False,
        )
        assert len(puzzle) == 81
        assert generator.validate(puzzle) == "valid"


# ---------------------------------------------------------------------------
# 3. Pattern puzzle tests
# ---------------------------------------------------------------------------

class TestPatternPuzzles:

    @pytest.fixture(scope="class")
    def generator(self):
        return Generator()

    def test_pattern_clues_only_at_pattern_positions(self):
        """Clues must appear only where the pattern says True (1)."""
        # Use a dense pattern (~50 cells) to increase likelihood of uniqueness.
        # Pattern generation inherently requires many retries since a random
        # full grid must happen to be uniquely determined by the pattern cells.
        rng = random.Random(12345)
        pattern_indices = set(rng.sample(range(81), 50))
        bool_pattern = [i in pattern_indices for i in range(81)]

        puzzle = None
        for _ in range(200):
            gen = SudokuGenerator()
            puzzle = gen.generate_sudoku(symmetric=False, pattern=bool_pattern)
            if puzzle is not None:
                break

        assert puzzle is not None, (
            "Pattern generation should succeed with a 50-cell pattern"
        )
        assert len(puzzle) == 81

        for i in range(81):
            if not bool_pattern[i]:
                assert puzzle[i] == "0", (
                    f"Cell {i} has clue '{puzzle[i]}' but pattern is False"
                )
            else:
                assert puzzle[i] != "0", (
                    f"Cell {i} should have a clue but is empty"
                )

    def test_pattern_puzzle_valid(self):
        """Pattern-based puzzle must have a unique solution."""
        rng = random.Random(67890)
        pattern_indices = set(rng.sample(range(81), 50))
        bool_pattern = [i in pattern_indices for i in range(81)]

        puzzle = None
        for _ in range(200):
            gen = SudokuGenerator()
            puzzle = gen.generate_sudoku(symmetric=False, pattern=bool_pattern)
            if puzzle is not None:
                break

        assert puzzle is not None

        gen2 = SudokuGenerator()
        gen2.solve_string(puzzle)
        assert gen2.get_solution_count() == 1


# ---------------------------------------------------------------------------
# 4. Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_max_tries_zero_raises(self):
        """max_tries=0 should raise RuntimeError immediately."""
        gen = Generator()
        with pytest.raises(RuntimeError):
            gen.generate(difficulty=DifficultyType.EASY, max_tries=0)

    def test_too_few_givens_pattern_returns_none(self):
        """A pattern with only 2 cells can't produce a unique puzzle."""
        gen = SudokuGenerator()
        pattern = [False] * 81
        pattern[0] = True
        pattern[80] = True
        # Low-level API returns None on failure (avoids 100K inner retries
        # multiplied by the API's max_tries loop)
        result = gen.generate_sudoku(symmetric=False, pattern=pattern)
        assert result is None

    def test_empty_pattern_produces_empty_grid(self):
        """A pattern of all zeros produces an empty grid (no clues).

        The solver considers 0-solution grids as ≤1, so generate_sudoku
        returns the empty grid. However, it's not a valid puzzle.
        """
        gen = SudokuGenerator()
        pattern = [False] * 81
        result = gen.generate_sudoku(symmetric=False, pattern=pattern)
        # Returns an all-zeros string (empty grid)
        assert result == "0" * 81
        # Verify it's not a valid puzzle (has 0 solutions, not 1)
        gen2 = SudokuGenerator()
        gen2.solve_string(result)
        assert gen2.get_solution_count() == 0


# ---------------------------------------------------------------------------
# 5. End-to-end: generate → solve → verify
# ---------------------------------------------------------------------------

class TestEndToEnd:

    def test_generate_solve_verify(self):
        """Full pipeline: generate puzzle, solve it, verify solution."""
        gen = Generator()
        solver = Solver()

        puzzle = gen.generate(difficulty=DifficultyType.MEDIUM)
        result = solver.solve(puzzle)

        assert result.solved
        assert len(result.solution) == 81

        # Solution must be a valid sudoku
        sol_values = [int(ch) for ch in result.solution]
        assert _is_valid_sudoku(sol_values)

        # Solution must contain all clues from the puzzle
        for i, ch in enumerate(puzzle):
            if ch != "0":
                assert result.solution[i] == ch, (
                    f"Clue mismatch at cell {i}: "
                    f"puzzle={ch}, solution={result.solution[i]}"
                )

    def test_generate_solve_steps_produce_correct_solution(self):
        """Replaying solution steps on the grid produces the solved grid."""
        gen = Generator()
        solver = Solver()

        puzzle = gen.generate(difficulty=DifficultyType.EASY)
        result = solver.solve(puzzle)
        assert result.solved

        # Replay: apply each step's placements to the grid
        grid = Grid()
        grid.set_sudoku(puzzle)
        for step in result.steps:
            for idx, val in zip(step.indices, step.values):
                grid.set_cell(idx, val)
            for cand in step.candidates_to_delete:
                if grid.candidates[cand.index] & (1 << (cand.value - 1)):
                    grid.del_candidate(cand.index, cand.value)

        assert grid.is_solved()
        assert grid.get_sudoku_string() == result.solution


# ---------------------------------------------------------------------------
# 6. Benchmark: time generation for each difficulty
# ---------------------------------------------------------------------------

class TestBenchmark:

    @pytest.mark.parametrize("difficulty,max_tries", [
        (DifficultyType.EASY, 20_000),
        (DifficultyType.MEDIUM, 20_000),
        (DifficultyType.HARD, 50_000),
    ])
    def test_generation_timing(self, difficulty, max_tries):
        """Benchmark: generate one puzzle and report timing."""
        gen = Generator()
        start = time.perf_counter()
        puzzle = gen.generate(difficulty=difficulty, max_tries=max_tries)
        elapsed = time.perf_counter() - start

        assert puzzle is not None
        assert len(puzzle) == 81

        # Report timing (visible in pytest -v output)
        print(f"\n  {difficulty.name}: generated in {elapsed:.2f}s")


# ---------------------------------------------------------------------------
# 7. BruteForceSolver uses grid.solution from generator
# ---------------------------------------------------------------------------

class TestBruteForceSolverIntegration:

    def test_brute_force_uses_generator_solution(self):
        """BruteForceSolver should use grid.solution set by the generator."""
        gen = SudokuGenerator()
        puzzle = gen.generate_sudoku(symmetric=True)
        assert puzzle is not None

        # Get the known solution from the generator
        gen2 = SudokuGenerator()
        grid = Grid()
        grid.set_sudoku(puzzle)
        assert gen2.valid_solution(grid) is True
        assert grid.is_solution_set()

        # BruteForceSolver should pick up grid.solution
        bf = BruteForceSolver(grid)

        # Get a step — should use grid.solution, not recompute
        step = bf.get_step(SolutionType.BRUTE_FORCE)
        assert step is not None
        assert step.type == SolutionType.BRUTE_FORCE
        assert len(step.indices) == 1
        assert len(step.values) == 1

        idx = step.indices[0]
        val = step.values[0]
        # The value must match what grid.solution says
        assert val == grid.solution[idx]
        # The cell must be currently unsolved
        assert grid.values[idx] == 0

    def test_brute_force_without_generator_solution(self):
        """BruteForceSolver should fall back to backtracking when no solution."""
        # Use a nearly-solved puzzle so the pure-Python backtracker is fast.
        # Known solution: 731526984546918732892374615683145279957283461124769853279851346365497128418632597
        # Remove just 3 cells to keep backtracking trivial.
        solved = "731526984546918732892374615683145279957283461124769853279851346365497128418632597"
        puzzle = list(solved)
        puzzle[0] = "0"   # was 7
        puzzle[40] = "0"  # was 3
        puzzle[80] = "0"  # was 7
        puzzle = "".join(puzzle)

        grid = Grid()
        grid.set_sudoku(puzzle)
        # Solution is NOT set (no generator call)
        assert not grid.is_solution_set()

        bf = BruteForceSolver(grid)
        step = bf.get_step(SolutionType.BRUTE_FORCE)
        assert step is not None
        assert step.type == SolutionType.BRUTE_FORCE

        # Value placed must be correct for the cell
        idx = step.indices[0]
        val = step.values[0]
        assert val == int(solved[idx])

    def test_brute_force_selects_middle_unsolved(self):
        """BruteForceSolver should pick the middle unsolved cell (Java compat)."""
        # Use same nearly-solved puzzle for speed.
        solved = "731526984546918732892374615683145279957283461124769853279851346365497128418632597"
        puzzle = list(solved)
        puzzle[0] = "0"
        puzzle[40] = "0"
        puzzle[80] = "0"
        puzzle = "".join(puzzle)

        grid = Grid()
        grid.set_sudoku(puzzle)

        bf = BruteForceSolver(grid)
        step = bf.get_step(SolutionType.BRUTE_FORCE)

        unsolved = [i for i in range(81) if grid.values[i] == 0]
        expected_idx = unsolved[len(unsolved) // 2]
        assert step.indices[0] == expected_idx

    def test_brute_force_wrong_type_returns_none(self):
        """BruteForceSolver only handles BRUTE_FORCE type."""
        grid = Grid()
        grid.set_sudoku("0" * 81)
        bf = BruteForceSolver(grid)
        assert bf.get_step(SolutionType.FULL_HOUSE) is None
