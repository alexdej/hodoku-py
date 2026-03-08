"""Fish solver: basic (X-Wing, Swordfish, Jellyfish) and finned/sashimi variants.

Mirrors the basic-fish and finned-fish portions of Java's FishSolver.
Franken and Mutant variants are not implemented.
"""

from __future__ import annotations

from itertools import combinations

from hodoku.core.grid import (
    BUDDIES,
    COL_MASKS,
    COLS,
    Grid,
    LINE_MASKS,
    LINES,
)

# All 81 cells mask
_ALL_CELLS = (1 << 81) - 1


def _fin_buddies(fin_mask: int) -> int:
    """Return the intersection of buddies of all fin cells.

    A cell is in the result iff it can see every fin cell simultaneously.
    """
    common = _ALL_CELLS
    tmp = fin_mask
    while tmp:
        lsb = tmp & -tmp
        common &= BUDDIES[lsb.bit_length() - 1]
        tmp ^= lsb
    return common
from hodoku.core.solution_step import Entity, SolutionStep
from hodoku.core.types import SolutionType

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


def _apply_siamese(steps: list[SolutionStep]) -> None:
    """Append siamese combinations to *steps* (modifies in place).

    Two finned/sashimi fish are siamese when they share the same base
    entities (same candidate, same rows/cols) but differ in their fin
    configuration and eliminations.  HoDoKu merges them into a single
    step with the combined cover + fin + elimination sets.
    """
    n = len(steps)
    for i in range(n - 1):
        s1 = steps[i]
        if not s1.base_entities:
            continue
        # Entity is a frozen dataclass with fields .type and .number
        base_key1 = tuple((e.type, e.number) for e in s1.base_entities)
        cand1 = s1.values[0] if s1.values else None
        elim1 = frozenset((c.index, c.value) for c in s1.candidates_to_delete)
        for j in range(i + 1, n):
            s2 = steps[j]
            if not s2.base_entities:
                continue
            if (s2.values[0] if s2.values else None) != cand1:
                continue
            base_key2 = tuple((e.type, e.number) for e in s2.base_entities)
            if base_key1 != base_key2:
                continue
            elim2 = frozenset((c.index, c.value) for c in s2.candidates_to_delete)
            if elim1 == elim2:
                continue
            # Build siamese step: clone s1, add s2's covers/fins/elims
            # Entity and Candidate are frozen dataclasses — safe to share refs
            siam = SolutionStep(s1.type)
            siam.add_value(cand1)
            for idx in s1.indices:
                siam.add_index(idx)
            siam.base_entities.extend(s1.base_entities)
            siam.cover_entities.extend(s1.cover_entities)
            siam.fins.extend(s1.fins)
            for c in s1.candidates_to_delete:
                siam.add_candidate_to_delete(c.index, c.value)
            # Add s2's additional covers, fins, elims
            siam.cover_entities.extend(s2.cover_entities)
            siam.fins.extend(s2.fins)
            for c in s2.candidates_to_delete:
                if (c.index, c.value) not in elim1:
                    siam.add_candidate_to_delete(c.index, c.value)
            steps.append(siam)


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

    def find_all(self, sol_type: SolutionType) -> list[SolutionStep]:
        if sol_type in _FISH_SIZE:
            return self._find_basic_fish_all(sol_type)
        if sol_type in _FINNED_SIZE:
            n = _FINNED_SIZE[sol_type]
            steps = self._find_finned_fish_all(sol_type, sashimi=False)
            if n >= 3:
                # HoDoKu finds finned+sashimi together for siamese combinations
                sashimi_type = _FINNED_TO_SASHIMI[sol_type]
                steps = steps + self._find_finned_fish_all(sashimi_type, sashimi=True)
                _apply_siamese(steps)
            return steps
        if sol_type in _SASHIMI_SIZE:
            n = _SASHIMI_SIZE[sol_type]
            sashimi_steps = self._find_finned_fish_all(sol_type, sashimi=True)
            if n >= 3:
                finned_type = {v: k for k, v in _FINNED_TO_SASHIMI.items()}[sol_type]
                steps = self._find_finned_fish_all(finned_type, sashimi=False) + sashimi_steps
                _apply_siamese(steps)
                return steps
            return sashimi_steps
        return []

    def _find_basic_fish_all(self, sol_type: SolutionType) -> list[SolutionStep]:
        """Return ALL basic fish of the given size."""
        n = _FISH_SIZE[sol_type]
        grid = self.grid
        results: list[SolutionStep] = []
        seen_elims: set[tuple] = set()

        for cand in range(1, 10):
            cand_set = grid.candidate_sets[cand]
            if not cand_set:
                continue

            for row_mode in (True, False):
                unit_masks  = LINE_MASKS if row_mode else COL_MASKS
                cover_masks = COL_MASKS  if row_mode else LINE_MASKS

                eligible: list[int] = []
                for u in range(9):
                    cnt = bin(cand_set & unit_masks[u]).count("1")
                    if 2 <= cnt <= n:
                        eligible.append(u)

                if len(eligible) < n:
                    continue

                for combo in combinations(eligible, n):
                    base_mask = 0
                    for u in combo:
                        base_mask |= cand_set & unit_masks[u]

                    cover_indices: list[int] = []
                    for ci in range(9):
                        if base_mask & cover_masks[ci]:
                            cover_indices.append(ci)

                    if len(cover_indices) != n:
                        continue

                    cover_mask = 0
                    for ci in cover_indices:
                        cover_mask |= cover_masks[ci]

                    elim_mask = cand_set & cover_mask & ~base_mask
                    if not elim_mask:
                        continue

                    elim_key = (cand, elim_mask)
                    if elim_key in seen_elims:
                        continue
                    seen_elims.add(elim_key)

                    results.append(self._make_step(
                        sol_type, cand, combo, cover_indices,
                        base_mask, elim_mask, row_mode
                    ))

        return results

    def _find_finned_fish_all(
        self, sol_type: SolutionType, sashimi: bool
    ) -> list[SolutionStep]:
        """Return ALL finned/sashimi fish of the given size."""
        n = _SASHIMI_SIZE[sol_type] if sashimi else _FINNED_SIZE[sol_type]
        finned_type = sol_type if not sashimi else {
            v: k for k, v in _FINNED_TO_SASHIMI.items()
        }[sol_type]
        grid = self.grid
        results: list[SolutionStep] = []
        seen_elims: set[tuple] = set()

        for cand in range(1, 10):
            cand_set = grid.candidate_sets[cand]
            if not cand_set:
                continue

            for row_mode in (True, False):
                unit_masks  = LINE_MASKS if row_mode else COL_MASKS
                cover_masks = COL_MASKS  if row_mode else LINE_MASKS

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

                    cover_indices: list[int] = []
                    for ci in range(9):
                        if base_mask & cover_masks[ci]:
                            cover_indices.append(ci)

                    if len(cover_indices) < n or len(cover_indices) > n + 3:
                        continue

                    for cover_combo in combinations(cover_indices, n):
                        cover_mask = 0
                        for ci in cover_combo:
                            cover_mask |= cover_masks[ci]

                        fin_mask = base_mask & ~cover_mask
                        if not fin_mask:
                            continue
                        if bin(fin_mask).count('1') > 5:
                            continue

                        fin_common = _fin_buddies(fin_mask)
                        elim_mask = cand_set & cover_mask & fin_common & ~base_mask
                        if not elim_mask:
                            continue

                        is_sashimi = False
                        for u in combo:
                            body = cand_set & unit_masks[u] & cover_mask
                            if bin(body).count('1') <= 1:
                                is_sashimi = True
                                break

                        if is_sashimi != sashimi:
                            continue

                        actual_type = (
                            _FINNED_TO_SASHIMI[finned_type]
                            if is_sashimi else finned_type
                        )

                        elim_key = (cand, row_mode, elim_mask, fin_mask)
                        if elim_key in seen_elims:
                            continue
                        seen_elims.add(elim_key)

                        results.append(self._make_step(
                            actual_type, cand, combo, list(cover_combo),
                            base_mask, elim_mask, row_mode,
                            fin_mask=fin_mask,
                        ))

        return results

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
                        if bin(fin_mask).count('1') > 5:
                            continue

                        # Eliminations: cover candidates that see ALL fin cells
                        fin_common = _fin_buddies(fin_mask)
                        elim_mask = cand_set & cover_mask & fin_common & ~base_mask
                        if not elim_mask:
                            continue

                        # Sashimi: any base unit has ≤1 body cell (HoDoKu definition)
                        is_sashimi = False
                        for u in combo:
                            body = cand_set & unit_masks[u] & cover_mask
                            if bin(body).count('1') <= 1:
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
        from hodoku.core.solution_step import Candidate
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
