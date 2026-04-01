"""Public API — the only import most users need."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from hodoku.core.grid import ALL_UNITS, Grid
from hodoku.core.solution_step import SolutionStep
from hodoku.core.types import DifficultyType, SolutionCategory, SolutionType
from hodoku.generator.generator import SudokuGenerator
from hodoku.generator.pattern import GeneratorPattern
from hodoku.solver.solver import SudokuSolver
from hodoku.solver.step_finder import SudokuStepFinder

if TYPE_CHECKING:
    from hodoku.config import SolverConfig

_VALID_CELL_CHARS = frozenset("0123456789.")

_FISH_CATEGORIES = frozenset({
    SolutionCategory.BASIC_FISH,
    SolutionCategory.FINNED_BASIC_FISH,
    SolutionCategory.FRANKEN_FISH,
    SolutionCategory.FINNED_FRANKEN_FISH,
    SolutionCategory.MUTANT_FISH,
    SolutionCategory.FINNED_MUTANT_FISH,
})

# Category → FishType level required
_FISH_CAT_LEVEL = {
    SolutionCategory.BASIC_FISH: 0,
    SolutionCategory.FINNED_BASIC_FISH: 0,
    SolutionCategory.FRANKEN_FISH: 1,
    SolutionCategory.FINNED_FRANKEN_FISH: 1,
    SolutionCategory.MUTANT_FISH: 2,
    SolutionCategory.FINNED_MUTANT_FISH: 2,
}

# Fish SolutionType → size (number of base sets).
_FISH_NAMES_BY_SIZE = [
    "X_WING", "SWORDFISH", "JELLYFISH", "SQUIRMBAG", "WHALE", "LEVIATHAN",
]
_FISH_PREFIXES = [
    "", "FINNED_", "SASHIMI_",
    "FRANKEN_", "FINNED_FRANKEN_",
    "MUTANT_", "FINNED_MUTANT_",
]
_FISH_TYPE_SIZE: dict[SolutionType, int] = {}
for _i, _name in enumerate(_FISH_NAMES_BY_SIZE):
    for _prefix in _FISH_PREFIXES:
        _st = getattr(SolutionType, _prefix + _name, None)
        if _st is not None:
            _FISH_TYPE_SIZE[_st] = _i + 2

# Primary type → alias subtypes that share the same StepConfig.
# find_all must dispatch these separately to find all variants.
_FIND_ALL_ALIASES: dict[SolutionType, list[SolutionType]] = {
    SolutionType.SIMPLE_COLORS_TRAP: [SolutionType.SIMPLE_COLORS_WRAP],
    SolutionType.MULTI_COLORS_1: [SolutionType.MULTI_COLORS_2],
    SolutionType.CONTINUOUS_NICE_LOOP: [
        SolutionType.DISCONTINUOUS_NICE_LOOP, SolutionType.AIC,
    ],
    SolutionType.GROUPED_CONTINUOUS_NICE_LOOP: [
        SolutionType.GROUPED_DISCONTINUOUS_NICE_LOOP, SolutionType.GROUPED_AIC,
    ],
    SolutionType.FORCING_CHAIN_CONTRADICTION: [SolutionType.FORCING_CHAIN_VERITY],
    SolutionType.FORCING_NET_CONTRADICTION: [SolutionType.FORCING_NET_VERITY],
    SolutionType.KRAKEN_FISH_TYPE_1: [SolutionType.KRAKEN_FISH_TYPE_2],
    SolutionType.TWO_STRING_KITE: [SolutionType.DUAL_TWO_STRING_KITE],
    SolutionType.EMPTY_RECTANGLE: [SolutionType.DUAL_EMPTY_RECTANGLE],
}


def _validate_puzzle(puzzle: str) -> None:
    """Raise ValueError for malformed puzzle strings.

    Accepts the same format as Grid.set_sudoku: 81 characters, each '0'-'9'
    or '.'.  Also accepts the '+D' placed-cell prefix notation.  Raises on
    invalid characters, wrong cell count, or duplicate digits in any house.
    """
    cells: list[str] = []
    i = 0
    while i < len(puzzle):
        ch = puzzle[i]
        if ch == "+":
            i += 1
            if i < len(puzzle):
                ch = puzzle[i]
                if ch not in _VALID_CELL_CHARS:
                    raise ValueError(f"Invalid character after '+': {ch!r}")
                cells.append(ch)
        elif ch in _VALID_CELL_CHARS:
            cells.append(ch)
        else:
            raise ValueError(f"Invalid character in puzzle string: {ch!r}")
        i += 1

    if len(cells) != 81:
        raise ValueError(f"Puzzle must have exactly 81 cells, got {len(cells)}")

    # Check for duplicate digits within each house (row, col, box)
    for unit in ALL_UNITS:
        seen: dict[str, int] = {}
        for idx in unit:
            d = cells[idx]
            if d in ("0", "."):
                continue
            if d in seen:
                raise ValueError(
                    f"Duplicate digit {d} in house (cells {seen[d]} and {idx})"
                )
            seen[d] = idx


@dataclass
class SolveResult:
    solved: bool
    steps: list[SolutionStep]
    level: DifficultyType
    score: int
    solution: str  # 81-char string


@dataclass
class RatingResult:
    level: DifficultyType
    score: int


class Solver:
    """Solves and analyses sudoku puzzles using human-style logic."""

    def __init__(self, config: SolverConfig | None = None) -> None:
        if config is None:
            from hodoku.config import DEFAULT_CONFIG
            config = DEFAULT_CONFIG
        self._config = config
        self._solver = SudokuSolver(config)

    def solve(self, puzzle: str) -> SolveResult:
        """Solve a puzzle string, returning the full solution path."""
        _validate_puzzle(puzzle)
        result = self._solver.solve(puzzle)
        return SolveResult(
            solved=result.solved,
            steps=result.steps,
            level=result.level,
            score=result.score,
            solution=result.solution,
        )

    def get_hint(self, puzzle: str) -> SolutionStep | None:
        """Return the next logical step, or None if already solved or stuck."""
        _validate_puzzle(puzzle)
        grid = Grid()
        grid.set_sudoku(puzzle)
        if grid.is_solved():
            return None
        finder = SudokuStepFinder(grid, self._config.solve_search)
        for cfg in self._config.solver_steps:
            step = finder.get_step(cfg.solution_type)
            if step is not None:
                return step
        return None

    def rate(self, puzzle: str) -> RatingResult:
        """Return difficulty level and score without recording solution steps."""
        _validate_puzzle(puzzle)
        result = self._solver.solve(puzzle)
        return RatingResult(level=result.level, score=result.score)

    def find_all_steps(self, puzzle: str) -> list[SolutionStep]:
        """Return every applicable technique at the current grid state."""
        _validate_puzzle(puzzle)
        grid = Grid()
        grid.set_sudoku(puzzle)
        return self._find_all_on_grid(grid)

    def _find_all_on_grid(self, grid: Grid) -> list[SolutionStep]:
        """Return every applicable technique on a pre-built grid."""
        find_cfg = self._config.find_all_search
        finder = SudokuStepFinder(grid, find_cfg)
        disabled = find_cfg.disabled_types
        fish_cfg = find_cfg.fish
        fish_type_level = fish_cfg.fish_type  # max fish category level
        steps: list[SolutionStep] = []
        for cfg in self._config.all_steps:
            sol_type = cfg.solution_type
            if sol_type in disabled:
                continue
            if cfg.category in _FISH_CATEGORIES:
                # Fish gated by search_fish + fish_type + max_size
                if not fish_cfg.search_fish:
                    continue
                if _FISH_CAT_LEVEL[cfg.category] > fish_type_level:
                    continue
                size = _FISH_TYPE_SIZE.get(sol_type, 99)
                if size < fish_cfg.min_size or size > fish_cfg.max_size:
                    continue
            elif not cfg.all_steps_enabled:
                continue
            steps.extend(finder.find_all(sol_type))
            for alias in _FIND_ALL_ALIASES.get(sol_type, ()):
                if alias not in disabled:
                    steps.extend(finder.find_all(alias))
        return steps


class Generator:
    """Generates valid sudoku puzzles at a requested difficulty level.

    Mirrors Java's ``BackgroundGenerator``: repeatedly generates random
    symmetric puzzles and rates them until one matches the target difficulty.
    """

    MAX_TRIES = 20_000

    def __init__(self, config: SolverConfig | None = None) -> None:
        if config is None:
            from hodoku.config import DEFAULT_CONFIG
            config = DEFAULT_CONFIG
        self._config = config
        self._generator = SudokuGenerator()
        self._solver = SudokuSolver(config)

    def generate(
        self,
        difficulty: DifficultyType = DifficultyType.MEDIUM,
        symmetric: bool = True,
        pattern: list[int] | GeneratorPattern | None = None,
        max_tries: int | None = None,
    ) -> str:
        """Generate an 81-character puzzle string at the requested difficulty.

        Raises ``RuntimeError`` if no puzzle matching the difficulty is found
        within *max_tries* attempts (default ``MAX_TRIES``).
        """
        if max_tries is None:
            max_tries = self.MAX_TRIES

        bool_pattern: list[bool] | None = None
        if isinstance(pattern, GeneratorPattern):
            bool_pattern = pattern.pattern
        elif pattern is not None:
            bool_pattern = [bool(p) for p in pattern]

        for _ in range(max_tries):
            puzzle = self._generator.generate_sudoku(
                symmetric=symmetric, pattern=bool_pattern,
            )
            if puzzle is None:
                # Pattern-based generation failed entirely
                raise RuntimeError(
                    "Could not generate a puzzle with the given pattern"
                )

            # Rate the puzzle
            result = self._solver.solve(puzzle)
            if not result.solved or result.level != difficulty:
                continue

            # Reject if score is below the previous level's max_score
            # (mirrors Java's rejectTooLowScore logic)
            if difficulty.value > DifficultyType.EASY.value:
                prev_level = DifficultyType(difficulty.value - 1)
                if result.score < self._config._difficulty_max_score[prev_level]:
                    continue

            return puzzle

        raise RuntimeError(
            f"Could not generate a {difficulty.name} puzzle in "
            f"{max_tries} attempts"
        )

    def validate(self, puzzle: str) -> Literal["valid", "invalid", "multiple"]:
        """Check whether a puzzle has exactly one solution.

        Returns ``"valid"`` (unique), ``"invalid"`` (no solution),
        or ``"multiple"`` (more than one solution).
        """
        _validate_puzzle(puzzle)
        grid = Grid()
        grid.set_sudoku(puzzle)
        count = self._generator.get_number_of_solutions(grid)
        if count == 0:
            return "invalid"
        elif count == 1:
            return "valid"
        else:
            return "multiple"
