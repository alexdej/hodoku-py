"""Simple solver — Full House, Naked/Hidden Singles, Locked Candidates,
Naked/Hidden Subsets (Pair, Triple, Quad), Locked Pair/Triple.

Mirrors Java's SimpleSolver for all techniques in that class.
Iteration order matches HoDoKu exactly.
"""

from __future__ import annotations

from hodoku.core.grid import (
    ALL_UNITS, BLOCKS, CELL_CONSTRAINTS, COLS, DIGIT_MASKS, LINES, Grid,
)
from hodoku.core.solution_step import SolutionStep
from hodoku.core.types import SolutionType


class SimpleSolver:
    """Finds all techniques handled by HoDoKu's SimpleSolver."""

    def __init__(self, grid: Grid) -> None:
        self.grid = grid

    def get_step(self, sol_type: SolutionType) -> SolutionStep | None:
        if sol_type == SolutionType.FULL_HOUSE:
            return self.find_full_house()
        if sol_type == SolutionType.NAKED_SINGLE:
            return self.find_naked_single()
        if sol_type == SolutionType.HIDDEN_SINGLE:
            return self.find_hidden_single()
        if sol_type in (SolutionType.LOCKED_CANDIDATES_1, SolutionType.LOCKED_CANDIDATES_2):
            return self._find_locked_candidates(sol_type)
        if sol_type == SolutionType.LOCKED_PAIR:
            return self._find_naked_xle(2, locked_only=True)
        if sol_type == SolutionType.NAKED_PAIR:
            return self._find_naked_xle(2, locked_only=False)
        if sol_type == SolutionType.LOCKED_TRIPLE:
            return self._find_naked_xle(3, locked_only=True)
        if sol_type == SolutionType.NAKED_TRIPLE:
            return self._find_naked_xle(3, locked_only=False)
        if sol_type == SolutionType.NAKED_QUADRUPLE:
            return self._find_naked_xle(4, locked_only=False)
        if sol_type == SolutionType.HIDDEN_PAIR:
            return self._find_hidden_xle(2)
        if sol_type == SolutionType.HIDDEN_TRIPLE:
            return self._find_hidden_xle(3)
        if sol_type == SolutionType.HIDDEN_QUADRUPLE:
            return self._find_hidden_xle(4)
        return None

    # ------------------------------------------------------------------
    # Full House
    # ------------------------------------------------------------------

    def find_full_house(self) -> SolutionStep | None:
        """Non-consumingly scan ns_queue for a cell that is the last in any unit."""
        g = self.grid
        for cell, digit in g.ns_queue:
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
        """Consume hs_queue; stop at first unsolved cell regardless of outcome."""
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
                return None  # valid cell but stale entry
        return None

    # ------------------------------------------------------------------
    # Locked Candidates
    # ------------------------------------------------------------------

    def find_all(self, sol_type: SolutionType) -> list[SolutionStep]:
        """Return ALL steps of the given type (used by reglib harness and /bsa mode)."""
        if sol_type == SolutionType.LOCKED_CANDIDATES_1:
            return self._lc_in_units_all(18, BLOCKS)
        if sol_type == SolutionType.LOCKED_CANDIDATES_2:
            return self._lc_in_units_all(0, LINES) + self._lc_in_units_all(9, COLS)
        if sol_type in (SolutionType.LOCKED_PAIR,):
            return self._find_naked_xle_all(2, locked_only=True)
        if sol_type == SolutionType.NAKED_PAIR:
            return self._find_naked_xle_all(2, locked_only=False)
        if sol_type in (SolutionType.LOCKED_TRIPLE,):
            return self._find_naked_xle_all(3, locked_only=True)
        if sol_type == SolutionType.NAKED_TRIPLE:
            return self._find_naked_xle_all(3, locked_only=False)
        if sol_type == SolutionType.NAKED_QUADRUPLE:
            return self._find_naked_xle_all(4, locked_only=False)
        if sol_type == SolutionType.HIDDEN_PAIR:
            return self._find_hidden_xle_all(2)
        if sol_type == SolutionType.HIDDEN_TRIPLE:
            return self._find_hidden_xle_all(3)
        if sol_type == SolutionType.HIDDEN_QUADRUPLE:
            return self._find_hidden_xle_all(4)
        # For all other types, fall back to get_step (yields 0 or 1 result).
        step = self.get_step(sol_type)
        return [step] if step is not None else []

    def _find_locked_candidates(self, sol_type: SolutionType) -> SolutionStep | None:
        """Dispatch LC1 (blocks→row/col) and LC2 (row/col→block)."""
        if sol_type == SolutionType.LOCKED_CANDIDATES_1:
            return self._lc_in_units(18, BLOCKS)
        # LOCKED_CANDIDATES_2
        step = self._lc_in_units(0, LINES)
        if step is not None:
            return step
        return self._lc_in_units(9, COLS)

    def _lc_in_units(
        self,
        constraint_base: int,
        units: tuple[tuple[int, ...], ...],
    ) -> SolutionStep | None:
        """Search one group of 9 units for a Locked Candidates step.

        constraint_base:
          18 → blocks  (LC1: pointing)
           0 → rows    (LC2: claiming)
           9 → cols    (LC2: claiming)
        """
        g = self.grid
        for unit_idx in range(9):
            for cand in range(1, 10):
                unit_free = g.free[unit_idx + constraint_base][cand]
                if unit_free not in (2, 3):
                    continue
                # Check whether all cells with cand share a secondary constraint
                first = True
                same = [True, True, True]
                constraint = [0, 0, 0]
                for cell in units[unit_idx]:
                    if not (g.candidates[cell] & DIGIT_MASKS[cand]):
                        continue
                    cc = CELL_CONSTRAINTS[cell]
                    if first:
                        constraint[0], constraint[1], constraint[2] = cc
                        first = False
                    else:
                        for j in range(3):
                            if same[j] and constraint[j] != cc[j]:
                                same[j] = False

                skip_constraint = unit_idx + constraint_base
                if constraint_base == 18:
                    # LC1: block cells all in same row → eliminate from that row
                    if same[0] and g.free[constraint[0]][cand] > unit_free:
                        return self._create_lc_step(
                            SolutionType.LOCKED_CANDIDATES_1, cand,
                            skip_constraint, ALL_UNITS[constraint[0]],
                        )
                    if same[1] and g.free[constraint[1]][cand] > unit_free:
                        return self._create_lc_step(
                            SolutionType.LOCKED_CANDIDATES_1, cand,
                            skip_constraint, ALL_UNITS[constraint[1]],
                        )
                else:
                    # LC2: row/col cells all in same block → eliminate from that block
                    if same[2] and g.free[constraint[2]][cand] > unit_free:
                        return self._create_lc_step(
                            SolutionType.LOCKED_CANDIDATES_2, cand,
                            skip_constraint, ALL_UNITS[constraint[2]],
                        )
        return None

    def _lc_in_units_all(
        self,
        constraint_base: int,
        units: tuple[tuple[int, ...], ...],
    ) -> list[SolutionStep]:
        """Like _lc_in_units but collects all matching steps instead of returning first."""
        g = self.grid
        results = []
        for unit_idx in range(9):
            for cand in range(1, 10):
                unit_free = g.free[unit_idx + constraint_base][cand]
                if unit_free not in (2, 3):
                    continue
                first = True
                same = [True, True, True]
                constraint = [0, 0, 0]
                for cell in units[unit_idx]:
                    if not (g.candidates[cell] & DIGIT_MASKS[cand]):
                        continue
                    cc = CELL_CONSTRAINTS[cell]
                    if first:
                        constraint[0], constraint[1], constraint[2] = cc
                        first = False
                    else:
                        for j in range(3):
                            if same[j] and constraint[j] != cc[j]:
                                same[j] = False

                skip_constraint = unit_idx + constraint_base
                if constraint_base == 18:
                    if same[0] and g.free[constraint[0]][cand] > unit_free:
                        results.append(self._create_lc_step(
                            SolutionType.LOCKED_CANDIDATES_1, cand,
                            skip_constraint, ALL_UNITS[constraint[0]],
                        ))
                    if same[1] and g.free[constraint[1]][cand] > unit_free:
                        results.append(self._create_lc_step(
                            SolutionType.LOCKED_CANDIDATES_1, cand,
                            skip_constraint, ALL_UNITS[constraint[1]],
                        ))
                else:
                    if same[2] and g.free[constraint[2]][cand] > unit_free:
                        results.append(self._create_lc_step(
                            SolutionType.LOCKED_CANDIDATES_2, cand,
                            skip_constraint, ALL_UNITS[constraint[2]],
                        ))
        return results

    def _create_lc_step(
        self,
        sol_type: SolutionType,
        cand: int,
        skip_constraint: int,
        unit_cells: tuple[int, ...],
    ) -> SolutionStep:
        """Build an LC step: cells in unit_cells that hold cand and are NOT in
        skip_constraint are eliminations; those inside skip_constraint are the
        pattern cells (stored in indices)."""
        g = self.grid
        step = SolutionStep(sol_type)
        step.add_value(cand)
        for cell in unit_cells:
            if g.candidates[cell] & DIGIT_MASKS[cand]:
                if skip_constraint in CELL_CONSTRAINTS[cell]:
                    step.add_index(cell)
                else:
                    step.add_candidate_to_delete(cell, cand)
        return step

    # ------------------------------------------------------------------
    # Naked Subsets (Pair / Triple / Quad + Locked variants)
    # ------------------------------------------------------------------

    def _find_naked_xle(self, anz: int, locked_only: bool) -> SolutionStep | None:
        """Find Naked/Locked Subset of size anz.

        Mirrors findNakedXle: BLOCKS first (only place locked subsets arise),
        then LINES, then COLS.
        """
        naked_only = not locked_only
        step = self._naked_in_units(BLOCKS, anz, locked_only, naked_only)
        if step is not None or locked_only:
            return step
        step = self._naked_in_units(LINES, anz, False, True)
        if step is not None:
            return step
        return self._naked_in_units(COLS, anz, False, True)

    def _find_naked_xle_all(self, anz: int, locked_only: bool) -> list[SolutionStep]:
        """Collect ALL Naked/Locked Subset steps of size anz."""
        naked_only = not locked_only
        results: list[SolutionStep] = []
        self._naked_in_units(BLOCKS, anz, locked_only, naked_only, _results=results)
        if not locked_only:
            self._naked_in_units(LINES, anz, False, True, _results=results)
            self._naked_in_units(COLS, anz, False, True, _results=results)
        return results

    def _naked_in_units(
        self,
        units: tuple[tuple[int, ...], ...],
        anz: int,
        locked_only: bool,
        naked_only: bool,
        _results: list[SolutionStep] | None = None,
    ) -> SolutionStep | None:
        g = self.grid
        for entity in range(9):
            # Collect unsolved cells with 1..anz candidates
            eligible: list[int] = []
            for cell in units[entity]:
                cnt = g.candidates[cell].bit_count()
                if 0 < cnt <= anz:
                    eligible.append(cell)
            n = len(eligible)
            if n < anz:
                continue

            # Enumerate combinations using mirrored Java nested loops with
            # early-exit when union already exceeds anz digits.
            for i1 in range(n - anz + 1):
                m1 = g.candidates[eligible[i1]]
                for i2 in range(i1 + 1, n - anz + 2):
                    m2 = m1 | g.candidates[eligible[i2]]
                    if m2.bit_count() > anz:
                        continue
                    if anz == 2:
                        if m2.bit_count() == anz:
                            step = self._create_subset_step(
                                [eligible[i1], eligible[i2]], m2,
                                anz, locked_only, naked_only,
                            )
                            if step is not None:
                                if _results is None:
                                    return step
                                _results.append(step)
                    else:
                        for i3 in range(i2 + 1, n - anz + 3):
                            m3 = m2 | g.candidates[eligible[i3]]
                            if m3.bit_count() > anz:
                                continue
                            if anz == 3:
                                if m3.bit_count() == anz:
                                    step = self._create_subset_step(
                                        [eligible[i1], eligible[i2], eligible[i3]], m3,
                                        anz, locked_only, naked_only,
                                    )
                                    if step is not None:
                                        if _results is None:
                                            return step
                                        _results.append(step)
                            else:
                                for i4 in range(i3 + 1, n):
                                    m4 = m3 | g.candidates[eligible[i4]]
                                    if m4.bit_count() > anz:
                                        continue
                                    if m4.bit_count() == anz:
                                        step = self._create_subset_step(
                                            [eligible[i1], eligible[i2],
                                             eligible[i3], eligible[i4]], m4,
                                            anz, locked_only, naked_only,
                                        )
                                        if step is not None:
                                            if _results is None:
                                                return step
                                            _results.append(step)
        return None

    def _create_subset_step(
        self,
        cells: list[int],
        cands_mask: int,
        anz: int,
        locked_only: bool,
        naked_only: bool,
    ) -> SolutionStep | None:
        """Build and classify a Naked Subset step (Naked/Locked Pair/Triple/Quad).

        Mirrors createSubsetStep for the Naked branch:
        - Eliminates cands_mask from all cells in shared constraints outside subset.
        - Detects Locked if eliminations occur in both the shared row/col AND the
          shared box, and cells share box + row or box + col.
        """
        g = self.grid
        cells_set = set(cells)
        cc0 = CELL_CONSTRAINTS[cells[0]]

        # Which of the 3 constraint types are shared by ALL subset cells?
        same = [True, True, True]
        for cell in cells[1:]:
            cc = CELL_CONSTRAINTS[cell]
            for j in range(3):
                if same[j] and cc0[j] != cc[j]:
                    same[j] = False

        # Collect eliminations; track whether they occur outside the box
        to_delete: list[tuple[int, int]] = []
        seen_elims: set[tuple[int, int]] = set()
        found_constraint = [False, False, False]
        anz_found = 0

        for i in range(3):
            if not same[i]:
                continue
            for cell in ALL_UNITS[cc0[i]]:
                if cell in cells_set:
                    continue
                del_mask = g.candidates[cell] & cands_mask
                if not del_mask:
                    continue
                for d in range(1, 10):
                    if del_mask & DIGIT_MASKS[d]:
                        key = (cell, d)
                        if key not in seen_elims:
                            seen_elims.add(key)
                            to_delete.append(key)
                if not found_constraint[i]:
                    # Count this constraint if: it's the box (i==2)
                    # OR the cell is outside the block (not sharing block with subset)
                    if i == 2 or CELL_CONSTRAINTS[cell][2] != cc0[2]:
                        found_constraint[i] = True
                        anz_found += 1

        if not to_delete:
            return None

        # Locked: pair/triple sharing box+row or box+col, with deletions in both
        is_locked = (
            anz < 4
            and anz_found > 1
            and same[2] and (same[0] or same[1])
        )

        if locked_only and not is_locked:
            return None
        if naked_only and is_locked:
            return None

        if is_locked:
            sol_type = SolutionType.LOCKED_PAIR if anz == 2 else SolutionType.LOCKED_TRIPLE
        else:
            sol_type = (
                SolutionType.NAKED_PAIR,
                SolutionType.NAKED_TRIPLE,
                SolutionType.NAKED_QUADRUPLE,
            )[anz - 2]

        step = SolutionStep(sol_type)
        for cell in cells:
            step.add_index(cell)
        for d in range(1, 10):
            if cands_mask & DIGIT_MASKS[d]:
                step.add_value(d)
        for cell, d in to_delete:
            step.add_candidate_to_delete(cell, d)
        return step

    # ------------------------------------------------------------------
    # Hidden Subsets (Pair / Triple / Quad)
    # ------------------------------------------------------------------

    def _find_hidden_xle(self, anz: int) -> SolutionStep | None:
        """Find Hidden Subset of size anz.

        Mirrors findHiddenXle: BLOCKS (constraintBase=18) first, then LINES
        (constraintBase=0), then COLS (constraintBase=9).
        """
        step = self._hidden_in_units(18, BLOCKS, anz)
        if step is not None:
            return step
        step = self._hidden_in_units(0, LINES, anz)
        if step is not None:
            return step
        return self._hidden_in_units(9, COLS, anz)

    def _find_hidden_xle_all(self, anz: int) -> list[SolutionStep]:
        """Collect ALL Hidden Subset steps of size anz."""
        results: list[SolutionStep] = []
        self._hidden_in_units(18, BLOCKS, anz, _results=results)
        self._hidden_in_units(0, LINES, anz, _results=results)
        self._hidden_in_units(9, COLS, anz, _results=results)
        return results

    def _hidden_in_units(
        self,
        constraint_base: int,
        units: tuple[tuple[int, ...], ...],
        anz: int,
        _results: list[SolutionStep] | None = None,
    ) -> SolutionStep | None:
        g = self.grid
        for entity in range(9):
            # Need more than anz unsolved cells for a hidden subset to exist
            unsolved = sum(1 for cell in units[entity] if g.candidates[cell])
            if unsolved <= anz:
                continue

            constraint_idx = constraint_base + entity

            # Collect digits whose free count is 1..anz and build per-digit
            # bitmask of positions within this unit (bit j set → position j has digit)
            ipc: list[int] = [0] * 10  # ipc[d] = position bitmask for digit d
            eligible: list[int] = []
            for d in range(1, 10):
                f = g.free[constraint_idx][d]
                if 0 < f <= anz:
                    eligible.append(d)
                    for j, cell in enumerate(units[entity]):
                        if g.candidates[cell] & DIGIT_MASKS[d]:
                            ipc[d] |= 1 << j

            if len(eligible) < anz:
                continue

            ne = len(eligible)

            # Enumerate digit combinations; union of ipc masks must cover exactly anz cells
            for i1 in range(ne - anz + 1):
                d1 = eligible[i1]
                cm1 = ipc[d1]
                for i2 in range(i1 + 1, ne - anz + 2):
                    d2 = eligible[i2]
                    cm2 = cm1 | ipc[d2]
                    if anz == 2:
                        if cm2.bit_count() == 2:
                            step = self._create_hidden_step(
                                units[entity], [d1, d2], cm2,
                            )
                            if step is not None:
                                if _results is None:
                                    return step
                                _results.append(step)
                    else:
                        for i3 in range(i2 + 1, ne - anz + 3):
                            d3 = eligible[i3]
                            cm3 = cm2 | ipc[d3]
                            if anz == 3:
                                if cm3.bit_count() == 3:
                                    step = self._create_hidden_step(
                                        units[entity], [d1, d2, d3], cm3,
                                    )
                                    if step is not None:
                                        if _results is None:
                                            return step
                                        _results.append(step)
                            else:
                                for i4 in range(i3 + 1, ne):
                                    d4 = eligible[i4]
                                    cm4 = cm3 | ipc[d4]
                                    if cm4.bit_count() == 4:
                                        step = self._create_hidden_step(
                                            units[entity], [d1, d2, d3, d4], cm4,
                                        )
                                        if step is not None:
                                            if _results is None:
                                                return step
                                            _results.append(step)
        return None

    def _create_hidden_step(
        self,
        unit_cells: tuple[int, ...],
        digits: list[int],
        cell_pos_mask: int,
    ) -> SolutionStep | None:
        """Build a Hidden Subset step: delete all non-subset candidates from subset cells."""
        g = self.grid
        cands_mask = 0
        for d in digits:
            cands_mask |= DIGIT_MASKS[d]

        cells = [unit_cells[j] for j in range(9) if cell_pos_mask & (1 << j)]

        to_delete: list[tuple[int, int]] = []
        for cell in cells:
            del_mask = g.candidates[cell] & ~cands_mask
            for d in range(1, 10):
                if del_mask & DIGIT_MASKS[d]:
                    to_delete.append((cell, d))

        if not to_delete:
            return None

        anz = len(digits)
        sol_type = (
            SolutionType.HIDDEN_PAIR,
            SolutionType.HIDDEN_TRIPLE,
            SolutionType.HIDDEN_QUADRUPLE,
        )[anz - 2]

        step = SolutionStep(sol_type)
        for cell in cells:
            step.add_index(cell)
        for d in digits:
            step.add_value(d)
        for cell, d in to_delete:
            step.add_candidate_to_delete(cell, d)
        return step
