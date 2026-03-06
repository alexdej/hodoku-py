"""Simple solver — Full House, Naked Single, Hidden Single.

Mirrors Java's SimpleSolver for the three queue-based single techniques.
Iteration order matches HoDoKu exactly: both consume the same FIFO queues
maintained by Grid._del_cand / Grid.set_cell.
"""

from __future__ import annotations

from hodoku_py.core.grid import CELL_CONSTRAINTS, Grid
from hodoku_py.core.solution_step import SolutionStep
from hodoku_py.core.types import SolutionType


class SimpleSolver:
    """Finds Full House, Naked Single, and Hidden Single steps."""

    def __init__(self, grid: Grid) -> None:
        self.grid = grid

    def get_step(self, sol_type: SolutionType) -> SolutionStep | None:
        if sol_type == SolutionType.FULL_HOUSE:
            return self.find_full_house()
        if sol_type == SolutionType.NAKED_SINGLE:
            return self.find_naked_single()
        if sol_type == SolutionType.HIDDEN_SINGLE:
            return self.find_hidden_single()
        return None

    # ------------------------------------------------------------------
    # Full House
    # ------------------------------------------------------------------

    def find_full_house(self) -> SolutionStep | None:
        """Non-consumingly scan ns_queue for a cell that is the last in any unit.

        A Full House is always also a Naked Single, so we inspect the naked-single
        queue.  For each queued cell/digit pair we check whether every other digit
        has free==0 in at least one of the cell's three constraints.
        """
        g = self.grid
        for cell, digit in g.ns_queue:          # non-consuming iteration
            if g.values[cell] != 0:
                continue
            for c in CELL_CONSTRAINTS[cell]:
                if all(g.free[c][d] == 0 for d in range(1, 10) if d != digit):
                    step = SolutionStep(SolutionType.FULL_HOUSE)
                    step.add_value(digit)
                    step.add_index(cell)
                    return step
        return None

    # ------------------------------------------------------------------
    # Naked Single
    # ------------------------------------------------------------------

    def find_naked_single(self) -> SolutionStep | None:
        """Consume ns_queue entries until a valid (unsolved) cell is found."""
        g = self.grid
        while g.ns_queue:
            cell, digit = g.ns_queue.popleft()
            if g.values[cell] == 0:
                step = SolutionStep(SolutionType.NAKED_SINGLE)
                step.add_value(digit)
                step.add_index(cell)
                return step
        return None

    # ------------------------------------------------------------------
    # Hidden Single
    # ------------------------------------------------------------------

    def find_hidden_single(self) -> SolutionStep | None:
        """Consume hs_queue entries.

        Mirrors Java exactly: after finding the first unsolved cell in the
        queue we check its constraints and return (or None), then stop —
        we do NOT continue to the next queue entry.
        """
        g = self.grid
        while g.hs_queue:
            cell, digit = g.hs_queue.popleft()
            if g.values[cell] == 0:
                for c in CELL_CONSTRAINTS[cell]:
                    if g.free[c][digit] == 1:
                        step = SolutionStep(SolutionType.HIDDEN_SINGLE)
                        step.add_value(digit)
                        step.add_index(cell)
                        return step
                # Stale entry: cell is valid but free has since changed.
                return None
        return None
