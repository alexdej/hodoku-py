"""BruteForceSolver — last-resort backtracking solver.

When all logical techniques are exhausted, this solver guesses a digit for
the most-constrained empty cell and places it. The solve loop keeps calling
it (one placement per call) until the puzzle is solved.

The solution is computed once via backtracking on a plain int array, cached
on the grid object as `grid.solution` (which the generator already populates
for puzzles with known solutions). If `grid.solution` is not set, we run
backtracking here to fill it.
"""

from __future__ import annotations

from hodoku_py.core.grid import CONSTRAINTS
from hodoku_py.core.solution_step import SolutionStep
from hodoku_py.core.types import SolutionType


# ---------------------------------------------------------------------------
# Pure backtracking on a flat int[81] array — no Grid overhead.
# Returns True and fills `values` in-place on success.
# ---------------------------------------------------------------------------

# Precomputed peer-index sets for fast candidate checking
def _build_peers() -> tuple[frozenset[int], ...]:
    peers: list[frozenset[int]] = []
    for i in range(81):
        r, c, b = CONSTRAINTS[i]
        br, bc = (r // 3) * 3, (c // 3) * 3
        p: set[int] = set()
        for j in range(9):
            p.add(r * 9 + j)       # same row
            p.add(j * 9 + c)       # same col
            p.add((br + j // 3) * 9 + bc + j % 3)  # same box
        p.discard(i)
        peers.append(frozenset(p))
    return tuple(peers)


_PEERS: tuple[frozenset[int], ...] = _build_peers()


def _allowed(values: list[int], index: int, digit: int) -> bool:
    """Return True if digit can legally be placed at index."""
    for p in _PEERS[index]:
        if values[p] == digit:
            return False
    return True


def _solve_bt(values: list[int]) -> bool:
    """Backtracking solve in-place. Returns True if a solution was found."""
    # Find the first empty cell (simple MRV: just first empty)
    for i in range(81):
        if values[i] == 0:
            for d in range(1, 10):
                if _allowed(values, i, d):
                    values[i] = d
                    if _solve_bt(values):
                        return True
                    values[i] = 0
            return False
    return True  # no empty cell → solved


# ---------------------------------------------------------------------------
# Solver class
# ---------------------------------------------------------------------------

class BruteForceSolver:
    """Places one digit per call using the precomputed solution."""

    def __init__(self, grid) -> None:
        self.grid = grid
        self._solution: list[int] | None = None

    def _ensure_solution(self) -> bool:
        """Compute (or reuse) the solution. Returns False if unsolvable."""
        if self._solution is not None:
            return True
        # Prefer grid.solution if already filled by the generator
        if any(self.grid.solution):
            self._solution = list(self.grid.solution)
            return True
        # Fall back to backtracking from current grid state
        trial = list(self.grid.values)
        if _solve_bt(trial):
            self._solution = trial
            return True
        return False

    def get_step(self, sol_type: SolutionType) -> SolutionStep | None:
        if sol_type is not SolutionType.BRUTE_FORCE:
            return None
        if not self._ensure_solution():
            return None

        # Pick the first empty cell and return a placement step for it
        for i in range(81):
            if self.grid.values[i] == 0:
                digit = self._solution[i]
                step = SolutionStep(type=SolutionType.BRUTE_FORCE)
                step.indices.append(i)
                step.values.append(digit)
                return step

        return None  # grid is already solved
