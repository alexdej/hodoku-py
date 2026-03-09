"""TemplateSolver — Template Set and Template Delete.

A *template* is one valid assignment of a single digit to the 81 cells:
exactly one cell per row, one per column, and one per box.  There are
46 656 such templates in total.

Template Set  — cells that appear in EVERY valid template for a digit must
                contain that digit.
Template Delete — cells that appear in NO valid template for a digit cannot
                  contain that digit (candidate can be eliminated).

The refinement pass (initLists=True in Java) iteratively removes templates
for digit j that overlap with the mandatory cells of another digit k, then
recomputes the mandatory/forbidden masks.  This is the variant always called
in HoDoKu's getAllTemplates() / getStep().

Port notes:
- Templates are generated once at import time via recursive backtracking.
- CellSets are plain Python ints (81-bit bitsets).
- Each Template-Set SolutionStep pairs add_index(cell) with add_value(digit)
  for EVERY cell so that zip(step.indices, step.values) is well-defined.
"""

from __future__ import annotations

from hodoku.core.grid import Grid
from hodoku.core.solution_step import SolutionStep
from hodoku.core.types import SolutionType

_ALL_CELLS: int = (1 << 81) - 1


# ---------------------------------------------------------------------------
# Template generation — runs once at module import
# ---------------------------------------------------------------------------

def _generate_templates() -> list[int]:
    """Return all 46 656 valid templates as 81-bit integers."""
    templates: list[int] = []

    def backtrack(row: int, used_cols: int, used_boxes: int, cellset: int) -> None:
        if row == 9:
            templates.append(cellset)
            return
        for col in range(9):
            if used_cols >> col & 1:
                continue
            box = (row // 3) * 3 + (col // 3)
            if used_boxes >> box & 1:
                continue
            backtrack(
                row + 1,
                used_cols | (1 << col),
                used_boxes | (1 << box),
                cellset | (1 << (row * 9 + col)),
            )

    backtrack(0, 0, 0, 0)
    return templates


_TEMPLATES: list[int] = _generate_templates()


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------

def _init_cand_templates(grid: Grid) -> tuple[list[int], list[int]]:
    """Compute setValueTemplates and delCandTemplates for all 9 digits.

    Returns (set_value[0..9], del_cand[0..9]), where index 0 is unused.
    After this call:
      - set_value[d] & ~positions[d]  → cells where d must be placed
      - del_cand[d] & candidate_sets[d] → candidates to eliminate
    """
    # positions[d]: cells where digit d is already placed
    positions = [0] * 10
    for cell in range(81):
        d = grid.values[cell]
        if d:
            positions[d] |= 1 << cell

    # allowed[d]: cells where d is still a candidate
    allowed = grid.candidate_sets  # list[int], index 0 unused

    # forbidden[d]: cells where d is neither placed nor a candidate
    forbidden = [0] * 10
    for d in range(1, 10):
        forbidden[d] = (~(positions[d] | allowed[d])) & _ALL_CELLS

    # --- Initial filtering pass ---
    # set_value[d] = AND of all valid templates (cells common to all)
    # del_cand[d]  = OR  of all valid templates (cells in at least one)
    set_value = [_ALL_CELLS] * 10
    del_cand = [0] * 10
    cand_lists: list[list[int]] = [[] for _ in range(10)]

    for t in _TEMPLATES:
        for d in range(1, 10):
            if (positions[d] & t) != positions[d]:
                continue  # template doesn't cover all already-placed cells
            if (forbidden[d] & t) != 0:
                continue  # template touches a forbidden cell
            set_value[d] &= t
            del_cand[d] |= t
            cand_lists[d].append(t)

    # --- Refinement pass (mirrors Java initLists=True) ---
    # Iteratively remove templates for digit j that overlap with the
    # mandatory positions (set_value) of any other digit k.
    removals = 1
    while removals:
        removals = 0
        for j in range(1, 10):
            set_value[j] = _ALL_CELLS
            del_cand[j] = 0
            new_list: list[int] = []
            for t in cand_lists[j]:
                removed = False
                for k in range(1, 10):
                    if k != j and (t & set_value[k]) != 0:
                        removed = True
                        removals += 1
                        break
                if not removed:
                    set_value[j] &= t
                    del_cand[j] |= t
                    new_list.append(t)
            cand_lists[j] = new_list

    # Complement: del_cand[d] now = cells in NO valid template
    for d in range(1, 10):
        del_cand[d] = (~del_cand[d]) & _ALL_CELLS

    return set_value, del_cand


# ---------------------------------------------------------------------------
# Solver class
# ---------------------------------------------------------------------------

class TemplateSolver:
    def __init__(self, grid: Grid) -> None:
        self.grid = grid

    # --- Public interface (mirrors other solvers) ---

    def get_step(self, sol_type: SolutionType) -> SolutionStep | None:
        steps = self.find_all(sol_type)
        return steps[0] if steps else None

    def find_all(self, sol_type: SolutionType) -> list[SolutionStep]:
        set_value, del_cand = _init_cand_templates(self.grid)
        positions = [0] * 10
        for cell in range(81):
            d = self.grid.values[cell]
            if d:
                positions[d] |= 1 << cell

        if sol_type is SolutionType.TEMPLATE_SET:
            return self._find_template_set(set_value, positions)
        if sol_type is SolutionType.TEMPLATE_DEL:
            return self._find_template_del(del_cand)
        return []

    # --- Internal helpers ---

    def _find_template_set(
        self, set_value: list[int], positions: list[int]
    ) -> list[SolutionStep]:
        steps: list[SolutionStep] = []
        for d in range(1, 10):
            cells_mask = set_value[d] & ~positions[d] & _ALL_CELLS
            if not cells_mask:
                continue
            step = SolutionStep(SolutionType.TEMPLATE_SET)
            mask = cells_mask
            while mask:
                lsb = mask & -mask
                cell = lsb.bit_length() - 1
                step.add_index(cell)
                step.add_value(d)
                mask ^= lsb
            steps.append(step)
        return steps

    def _find_template_del(self, del_cand: list[int]) -> list[SolutionStep]:
        steps: list[SolutionStep] = []
        for d in range(1, 10):
            elim_mask = del_cand[d] & self.grid.candidate_sets[d]
            if not elim_mask:
                continue
            step = SolutionStep(SolutionType.TEMPLATE_DEL)
            step.add_value(d)
            mask = elim_mask
            while mask:
                lsb = mask & -mask
                cell = lsb.bit_length() - 1
                step.add_candidate_to_delete(cell, d)
                mask ^= lsb
            steps.append(step)
        return steps
