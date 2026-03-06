"""Fish solver: basic (X-Wing, Swordfish, Jellyfish) and finned/sashimi variants.

Mirrors the basic-fish and finned-fish portions of Java's FishSolver.
Franken and Mutant variants are not implemented.
"""

from __future__ import annotations

from itertools import combinations

from hodoku_py.core.grid import (
    BLOCK_MASKS,
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

# Size for each basic fish type
_FISH_SIZE = {
    SolutionType.X_WING:    2,
    SolutionType.SWORDFISH: 3,
    SolutionType.JELLYFISH: 4,
}

# Finned and Sashimi types with their size
_FINNED_SIZE = {
    SolutionType.FINNED_X_WING:    2,
    SolutionType.FINNED_SWORDFISH: 3,
    SolutionType.FINNED_JELLYFISH: 4,
}

_SASHIMI_SIZE = {
    SolutionType.SASHIMI_X_WING:    2,
    SolutionType.SASHIMI_SWORDFISH: 3,
    SolutionType.SASHIMI_JELLYFISH: 4,
}

# Map finned → sashimi counterpart (same size, different classification)
_FINNED_TO_SASHIMI = {
    SolutionType.FINNED_X_WING:    SolutionType.SASHIMI_X_WING,
    SolutionType.FINNED_SWORDFISH: SolutionType.SASHIMI_SWORDFISH,
    SolutionType.FINNED_JELLYFISH: SolutionType.SASHIMI_JELLYFISH,
}


class FishSolver:
    """X-Wing, Swordfish, Jellyfish — basic and finned/sashimi variants."""

    def __init__(self, grid: Grid) -> None:
        self.grid = grid

    def get_step(self, sol_type: SolutionType) -> SolutionStep | None:
        if sol_type in _FISH_SIZE:
            return self._find_basic_fish(sol_type)
        if sol_type in _FINNED_SIZE:
            return self._find_finned_fish(sol_type, sashimi=False)
        if sol_type in _SASHIMI_SIZE:
            return self._find_finned_fish(sol_type, sashimi=True)
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

    def _find_finned_fish(
        self, sol_type: SolutionType, sashimi: bool
    ) -> SolutionStep | None:
        """Search for a finned or sashimi fish of the given size.

        A finned fish is like a basic fish but some base cells fall outside
        the n cover units — these are 'fins'.  All fins must share one block.
        Eliminations: candidates in the cover units that are also in the fin
        block, but not in any base unit.

        Sashimi: same pattern, but at least one base unit has all its cells
        as fins (it contributes nothing to the body).
        """
        n = _SASHIMI_SIZE[sol_type] if sashimi else _FINNED_SIZE[sol_type]
        # The canonical type for step construction is the FINNED variant;
        # we decide finned vs sashimi per found fish.
        finned_type = sol_type if not sashimi else {
            v: k for k, v in _FINNED_TO_SASHIMI.items()
        }[sol_type]
        grid = self.grid

        for cand in range(1, 10):
            cand_set = grid.candidate_sets[cand]
            if not cand_set:
                continue

            for row_mode in (True, False):
                unit_masks  = LINE_MASKS if row_mode else COL_MASKS
                cover_masks = COL_MASKS  if row_mode else LINE_MASKS

                # Eligible base units: any unit with ≥1 occurrence
                # (fins can make a unit appear to have too many cells)
                eligible: list[int] = []
                for u in range(9):
                    if cand_set & unit_masks[u]:
                        eligible.append(u)

                if len(eligible) < n:
                    continue

                for combo in combinations(eligible, n):
                    base_mask = 0
                    for u in combo:
                        base_mask |= cand_set & unit_masks[u]

                    # All cover units hit by the base cells
                    cover_indices: list[int] = []
                    for ci in range(9):
                        if base_mask & cover_masks[ci]:
                            cover_indices.append(ci)

                    # Need at least n covers; skip if far too many (performance)
                    if len(cover_indices) < n or len(cover_indices) > n + 3:
                        continue

                    # Try every n-subset of cover_indices as the main covers
                    for cover_combo in combinations(cover_indices, n):
                        cover_mask = 0
                        for ci in cover_combo:
                            cover_mask |= cover_masks[ci]

                        fin_mask = base_mask & ~cover_mask
                        if not fin_mask:
                            continue  # basic fish, handled elsewhere

                        # All fin cells must share one block
                        fin_block = CONSTRAINTS[fin_mask.bit_length() - 1][2]
                        tmp = fin_mask
                        all_same_block = True
                        while tmp:
                            lsb = tmp & -tmp
                            if CONSTRAINTS[lsb.bit_length() - 1][2] != fin_block:
                                all_same_block = False
                                break
                            tmp ^= lsb
                        if not all_same_block:
                            continue

                        # Eliminations: in cover units, in fin block, not in base
                        elim_mask = (
                            cand_set & cover_mask
                            & BLOCK_MASKS[fin_block]
                            & ~base_mask
                        )
                        if not elim_mask:
                            continue

                        # Sashimi: any base unit has zero body cells (all fins)?
                        is_sashimi = False
                        for u in combo:
                            if not (cand_set & unit_masks[u] & cover_mask):
                                is_sashimi = True
                                break

                        if is_sashimi != sashimi:
                            continue

                        actual_type = (
                            _FINNED_TO_SASHIMI[finned_type]
                            if is_sashimi else finned_type
                        )
                        return self._make_step(
                            actual_type, cand, combo, list(cover_combo),
                            base_mask, elim_mask, row_mode,
                            fin_mask=fin_mask,
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
        fin_mask: int = 0,
    ) -> SolutionStep:
        step = SolutionStep(sol_type)
        step.add_value(cand)

        # Indices: body cells (base minus fins) carry the fish pattern;
        # fin cells are recorded in step.fins
        body_mask = base_mask & ~fin_mask
        tmp = body_mask
        while tmp:
            lsb = tmp & -tmp
            step.add_index(lsb.bit_length() - 1)
            tmp ^= lsb

        # Fin cells
        from hodoku_py.core.solution_step import Candidate
        tmp = fin_mask
        while tmp:
            lsb = tmp & -tmp
            step.fins.append(Candidate(lsb.bit_length() - 1, cand))
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
