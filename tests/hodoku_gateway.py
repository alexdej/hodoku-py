"""Py4J gateway to HoDoKu's Java solver.

Keeps a single JVM alive across the session and solves puzzles one at a time
via direct Java method calls — no temp files, no CLI output parsing.

Usage:
    gw = HodokuGateway()
    result = gw.solve("530070000...")   # returns HodokuResult
    gw.shutdown()

Or as a context manager:
    with HodokuGateway() as gw:
        result = gw.solve("530070000...")
"""

from __future__ import annotations

from pathlib import Path

from py4j.java_gateway import GatewayParameters, JavaGateway, launch_gateway

from hodoku.core.types import DifficultyType, SolutionType
from tests.hodoku_harness import HodokuResult, HodokuStep

PROJECT_ROOT = Path(__file__).parent.parent
HODOKU_JAR = PROJECT_ROOT / "hodoku" / "hodoku.jar"

# Map Java DifficultyLevel ordinals to our DifficultyType.
_LEVEL_MAP: dict[int, DifficultyType] = {
    0: DifficultyType.INCOMPLETE,
    1: DifficultyType.EASY,
    2: DifficultyType.MEDIUM,
    3: DifficultyType.HARD,
    4: DifficultyType.UNFAIR,
    5: DifficultyType.EXTREME,
}

# Map Java SolutionType.name() to our Python SolutionType.
# Most map 1:1 by name. The generic parent types need special handling.
_GENERIC_TYPE_MAP: dict[str, SolutionType] = {
    "FORCING_CHAIN": SolutionType.FORCING_CHAIN_CONTRADICTION,
    "FORCING_NET": SolutionType.FORCING_NET_CONTRADICTION,
    "SIMPLE_COLORS": SolutionType.SIMPLE_COLORS_TRAP,
    "MULTI_COLORS": SolutionType.MULTI_COLORS_1,
    "NICE_LOOP": SolutionType.CONTINUOUS_NICE_LOOP,
    "GROUPED_NICE_LOOP": SolutionType.GROUPED_CONTINUOUS_NICE_LOOP,
    "LOCKED_CANDIDATES": SolutionType.LOCKED_CANDIDATES_1,
    "KRAKEN_FISH": SolutionType.KRAKEN_FISH_TYPE_1,
}

# Build full name→enum map once.
_PY_TYPE_BY_NAME: dict[str, SolutionType] = {t.name: t for t in SolutionType}
_PY_TYPE_BY_NAME.update(_GENERIC_TYPE_MAP)


def _map_solution_type(java_type) -> SolutionType | None:
    """Map a Java SolutionType enum value to our Python SolutionType."""
    return _PY_TYPE_BY_NAME.get(java_type.name())


class HodokuGateway:
    """Py4J bridge to HoDoKu's Java solver."""

    def __init__(self, jar_path: Path = HODOKU_JAR) -> None:
        if not jar_path.exists():
            raise FileNotFoundError(f"hodoku.jar not found at {jar_path}")
        self._port = launch_gateway(
            classpath=str(jar_path),
            die_on_exit=True,
        )
        self._gateway = JavaGateway(
            gateway_parameters=GatewayParameters(
                port=self._port, auto_convert=True,
            )
        )
        self._jvm = self._gateway.jvm

    def __enter__(self) -> HodokuGateway:
        return self

    def __exit__(self, *exc) -> None:
        self.shutdown()

    def shutdown(self) -> None:
        try:
            self._gateway.shutdown()
        except Exception:
            pass

    def solve(self, puzzle: str) -> HodokuResult:
        """Solve a single puzzle and return a HodokuResult."""
        jvm = self._jvm

        sudoku = jvm.sudoku.Sudoku2()
        sudoku.setSudoku(puzzle)

        solver = jvm.solver.SudokuSolver()
        solver.setSudoku(sudoku)
        solver.solve()

        java_steps = solver.getSteps()
        java_level = solver.getLevel()
        score = int(solver.getScore())

        level = _LEVEL_MAP.get(java_level.getOrdinal(), DifficultyType.INCOMPLETE)
        solved = sudoku.isSolved()

        steps: list[HodokuStep] = []
        for i in range(java_steps.size()):
            java_step = java_steps.get(i)
            java_type = java_step.getType()

            technique = java_type.getStepName()
            solution_type = _map_solution_type(java_type)

            # Placements / context cells
            indices = list(java_step.getIndices())
            values = list(java_step.getValues())

            # Eliminations
            java_cands = java_step.getCandidatesToDelete()
            eliminations: list[tuple[int, int]] = []
            for j in range(java_cands.size()):
                c = java_cands.get(j)
                eliminations.append((int(c.getIndex()), int(c.getValue())))

            steps.append(HodokuStep(
                technique=technique,
                solution_type=solution_type,
                indices=indices,
                values=values,
                eliminations=eliminations,
            ))

        return HodokuResult(
            puzzle=puzzle,
            level=level,
            score=score,
            steps=steps,
            solved=solved,
        )
