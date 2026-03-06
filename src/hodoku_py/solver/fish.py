"""Basic fish solver: X-Wing (2), Swordfish (3), Jellyfish (4).

Mirrors the basic-fish portion of Java's FishSolver.
Finned, Sashimi, Franken, Mutant variants are row 14.
"""

from __future__ import annotations

from itertools import combinations

from hodoku_py.core.grid import (
    COL_MASKS,
    COLS,
    CONSTRAINTS,
    Grid,
    LINE_MASKS,
    LINES,
)
from hodoku_py.core.solution_step import Entity, SolutionStep
from hodoku_py.core.types import SolutionType

# Entity type constants (mirror Java's Sudoku2.LINE / COL / BLOCK)
_LINE  = 0
_COL   = 1

_BASIC_TYPES = (
    SolutionType.X_WING,
    SolutionType.SWORDFISH,
    SolutionType.JELLYFISH,
)

# Size for each basic fish type
_FISH_SIZE = {
    SolutionType.X_WING:    2,
    SolutionType.SWORDFISH: 3,
    SolutionType.JELLYFISH: 4,
}


class FishSolver:
    """X-Wing, Swordfish, Jellyfish (basic unfinned fish)."""

    def __init__(self, grid: Grid) -> None:
        self.grid = grid

    def get_step(self, sol_type: SolutionType) -> SolutionStep | None:
        if sol_type in _FISH_SIZE:
            return self._find_basic_fish(sol_type)
        return None

    # ------------------------------------------------------------------
    # Core algorithm
    # ------------------------------------------------------------------

    def _find_basic_fish(self, sol_type: SolutionType) -> SolutionStep | None:
        """Search for a basic fish of the given size.

        Row-mode: base = rows, cover = cols.
        Col-mode: base = cols, cover = rows.
        For each candidate digit, try all C(9, n) combinations of base units
        where the digit appears 2..n times.  If those n base units span exactly
        n cover units, any candidates in the cover units outside the base can
        be eliminated.
        """
        n = _FISH_SIZE[sol_type]
        grid = self.grid

        for cand in range(1, 10):
            cand_set = grid.candidate_sets[cand]
            if not cand_set:
                continue

            for row_mode in (True, False):
                unit_masks  = LINE_MASKS if row_mode else COL_MASKS
                cover_masks = COL_MASKS  if row_mode else LINE_MASKS
                units       = LINES      if row_mode else COLS

                # Collect candidate base units (those with 2..n occurrences)
                eligible: list[int] = []
                for u in range(9):
                    cnt = bin(cand_set & unit_masks[u]).count("1")
                    if 2 <= cnt <= n:
                        eligible.append(u)

                if len(eligible) < n:
                    continue

                for combo in combinations(eligible, n):
                    # Union of candidate cells across these n base units
                    base_mask = 0
                    for u in combo:
                        base_mask |= cand_set & unit_masks[u]

                    # Which perpendicular units do these cells span?
                    cover_indices: list[int] = []
                    for ci in range(9):
                        if base_mask & cover_masks[ci]:
                            cover_indices.append(ci)

                    if len(cover_indices) != n:
                        continue  # not a fish

                    # Elimination: candidates in cover units but not in base
                    cover_mask = 0
                    for ci in cover_indices:
                        cover_mask |= cover_masks[ci]

                    elim_mask = cand_set & cover_mask & ~base_mask
                    if not elim_mask:
                        continue

                    return self._make_step(
                        sol_type, cand, combo, cover_indices,
                        base_mask, elim_mask, row_mode
                    )

        return None

    # ------------------------------------------------------------------
    # Step construction
    # ------------------------------------------------------------------

    def _make_step(
        self,
        sol_type: SolutionType,
        cand: int,
        base_units: tuple[int, ...],
        cover_units: list[int],
        base_mask: int,
        elim_mask: int,
        row_mode: bool,
    ) -> SolutionStep:
        step = SolutionStep(sol_type)
        step.add_value(cand)

        # Indices: cells in the base units that carry the candidate
        tmp = base_mask
        while tmp:
            lsb = tmp & -tmp
            step.add_index(lsb.bit_length() - 1)
            tmp ^= lsb

        # Base entities (rows or cols)
        base_type  = _LINE if row_mode else _COL
        cover_type = _COL  if row_mode else _LINE
        for u in base_units:
            step.base_entities.append(Entity(base_type, u + 1))  # 1-based
        for ci in cover_units:
            step.cover_entities.append(Entity(cover_type, ci + 1))

        # Eliminations
        tmp = elim_mask
        while tmp:
            lsb = tmp & -tmp
            step.add_candidate_to_delete(lsb.bit_length() - 1, cand)
            tmp ^= lsb

        return step
