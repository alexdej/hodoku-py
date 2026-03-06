"""Uniqueness solver: Uniqueness Tests 1-6, Hidden Rectangle, BUG+1.

Mirrors Java's UniquenessSolver.
Avoidable Rectangles (AR1/AR2) require tracking solved-but-not-given cells,
which our current Grid does not do — skipped for now.
"""

from __future__ import annotations

from hodoku_py.core.grid import ALL_UNITS, BLOCKS, BUDDIES, COLS, CONSTRAINTS, Grid, LINES
from hodoku_py.core.solution_step import Candidate, SolutionStep
from hodoku_py.core.types import SolutionType

_UT_TYPES = frozenset({
    SolutionType.UNIQUENESS_1,
    SolutionType.UNIQUENESS_2,
    SolutionType.UNIQUENESS_3,
    SolutionType.UNIQUENESS_4,
    SolutionType.UNIQUENESS_5,
    SolutionType.UNIQUENESS_6,
    SolutionType.HIDDEN_RECTANGLE,
})

# Bitmask for all 9 digits (bits 0-8 → digits 1-9)
_ALL_DIGITS = (1 << 9) - 1


class UniquenessSolver:
    """Uniqueness Tests 1–6, Hidden Rectangle, BUG+1."""

    def __init__(self, grid: Grid) -> None:
        self.grid = grid

    def get_step(self, sol_type: SolutionType) -> SolutionStep | None:
        if sol_type in _UT_TYPES:
            return self._find_ur(sol_type)
        if sol_type == SolutionType.BUG_PLUS_1:
            return self._find_bug_plus_1()
        return None

    # ------------------------------------------------------------------
    # BUG+1
    # ------------------------------------------------------------------

    def _find_bug_plus_1(self) -> SolutionStep | None:
        """Bivalue Universal Grave + 1.

        Exactly one unsolved cell has 3 candidates; all other unsolved cells
        have exactly 2. Every unit has at most 2 occurrences of each candidate
        except one (cand3) which appears exactly 3 times in one row, one col,
        and one box — and that cell is the trivalue cell.
        """
        grid = self.grid
        index3 = -1
        for i in range(81):
            if grid.values[i] != 0:
                continue
            n = bin(grid.candidates[i]).count("1")
            if n > 3:
                return None
            if n == 3:
                if index3 != -1:
                    return None  # two trivalue cells → not BUG+1
                index3 = i
        if index3 == -1:
            return None

        cand3 = -1
        bug_row = bug_col = bug_box = -1
        for unit in range(27):
            for d in range(1, 10):
                cnt = grid.free[unit][d]
                if cnt > 3:
                    return None
                if cnt == 3:
                    unit_type = unit // 9  # 0=row, 1=col, 2=box
                    if unit_type == 0:
                        if bug_row != -1 or (cand3 != -1 and cand3 != d):
                            return None
                        cand3 = d
                        bug_row = unit
                    elif unit_type == 1:
                        if bug_col != -1 or (cand3 != -1 and cand3 != d):
                            return None
                        cand3 = d
                        bug_col = unit
                    else:
                        if bug_box != -1 or (cand3 != -1 and cand3 != d):
                            return None
                        cand3 = d
                        bug_box = unit

        if cand3 == -1:
            return None
        r3, c3, b3 = CONSTRAINTS[index3]
        if r3 != bug_row or (9 + c3) != bug_col or (18 + b3) != bug_box:
            return None
        if not (grid.candidate_sets[cand3] >> index3 & 1):
            return None

        step = SolutionStep(SolutionType.BUG_PLUS_1)
        mask = grid.candidates[index3]
        for d in range(1, 10):
            if mask >> (d - 1) & 1 and d != cand3:
                step.add_candidate_to_delete(index3, d)
        return step if step.candidates_to_delete else None

    # ------------------------------------------------------------------
    # Unique Rectangle search
    # ------------------------------------------------------------------

    def _find_ur(self, target_type: SolutionType) -> SolutionStep | None:
        """Find the first UR step of the given type (or any UR type if caching)."""
        grid = self.grid
        seen_rects: set[tuple[int, int, int, int]] = set()
        cached: list[SolutionStep] = []

        for i11 in range(81):
            if grid.values[i11] != 0:
                continue
            n = bin(grid.candidates[i11]).count("1")
            if n < 2:
                continue
            cands = [d for d in range(1, 10) if grid.candidates[i11] >> (d - 1) & 1]
            # Try all pairs from the candidates of this starting cell
            for ci in range(len(cands)):
                for cj in range(ci + 1, len(cands)):
                    cand1, cand2 = cands[ci], cands[cj]
                    step = self._find_ur_for_pair(
                        i11, cand1, cand2, seen_rects, cached, target_type
                    )
                    if step is not None:
                        return step

        # Return cached step of the requested type
        for step in cached:
            if step.type == target_type:
                return step
        return None

    def _find_ur_for_pair(
        self,
        i11: int,
        cand1: int,
        cand2: int,
        seen_rects: set[tuple[int, int, int, int]],
        cached: list[SolutionStep],
        target_type: SolutionType,
    ) -> SolutionStep | None:
        """Search for URs starting at i11 with the given candidate pair."""
        grid = self.grid
        r11, c11, b11 = CONSTRAINTS[i11]

        # Find second cell in the same block sharing both candidates,
        # in the same row OR same col
        for i12 in BLOCKS[b11]:
            if i12 == i11:
                continue
            r12, c12, b12 = CONSTRAINTS[i12]
            if r12 != r11 and c12 != c11:
                continue  # not aligned in row or col
            if grid.values[i12] != 0:
                continue
            if not (grid.candidates[i12] >> (cand1 - 1) & 1 and
                    grid.candidates[i12] >> (cand2 - 1) & 1):
                continue

            is_lines = (r11 == r12)
            # The opposite side of the rectangle
            unit11 = COLS[c11] if is_lines else LINES[r11]
            unit12 = COLS[c12] if is_lines else LINES[r12]

            for idx in range(9):
                i21 = unit11[idx]
                i22 = unit12[idx]
                if CONSTRAINTS[i21][2] == b11:
                    continue  # must be a different block
                if grid.values[i21] != 0 or grid.values[i22] != 0:
                    continue
                if not (grid.candidates[i21] >> (cand1 - 1) & 1 and
                        grid.candidates[i21] >> (cand2 - 1) & 1):
                    continue
                if not (grid.candidates[i22] >> (cand1 - 1) & 1 and
                        grid.candidates[i22] >> (cand2 - 1) & 1):
                    continue

                # Deduplicate rectangles
                key = tuple(sorted((i11, i12, i21, i22)))
                if key in seen_rects:
                    continue
                seen_rects.add(key)

                step = self._check_ur(
                    i11, i12, i21, i22, cand1, cand2, cached, target_type
                )
                if step is not None:
                    return step
        return None

    def _check_ur(
        self,
        i11: int, i12: int, i21: int, i22: int,
        cand1: int, cand2: int,
        cached: list[SolutionStep],
        target_type: SolutionType,
    ) -> SolutionStep | None:
        """Evaluate all UR types for this rectangle."""
        grid = self.grid
        indexe = (i11, i12, i21, i22)
        ur_mask = (1 << (cand1 - 1)) | (1 << (cand2 - 1))

        # Partition cells: two_cands = cells with only cand1/cand2; additional = rest
        two_cands: list[int] = []
        additional: list[int] = []
        for cell in indexe:
            extra = grid.candidates[cell] & ~ur_mask & _ALL_DIGITS
            if extra == 0:
                two_cands.append(cell)
            else:
                additional.append(cell)

        twoSize = len(two_cands)

        def emit(step: SolutionStep) -> SolutionStep | None:
            if step.type == target_type:
                return step
            cached.append(step)
            return None

        def make_step(sol_type: SolutionType) -> SolutionStep:
            s = SolutionStep(sol_type)
            s.add_value(cand1)
            s.add_value(cand2)
            for c in indexe:
                s.add_index(c)
            return s

        # UT1: 3 cells are pure bivalue → eliminate both from the 4th
        if twoSize == 3:
            del_cell = additional[0]
            s = make_step(SolutionType.UNIQUENESS_1)
            for d in (cand1, cand2):
                if grid.candidates[del_cell] >> (d - 1) & 1:
                    s.add_candidate_to_delete(del_cell, d)
            if s.candidates_to_delete:
                result = emit(s)
                if result:
                    return result

        # UT2 / UT5: 1 or 2 additional-candidate cells all share exactly 1 extra candidate
        if twoSize in (1, 2):
            add_mask = 0
            buddies_all = (1 << 81) - 1
            for cell in additional:
                add_mask |= grid.candidates[cell] & ~ur_mask & _ALL_DIGITS
                if bin(add_mask).count("1") > 1:
                    break
                buddies_all &= BUDDIES[cell]
            if bin(add_mask).count("1") == 1:
                add_cand = add_mask.bit_length()  # digit (1-9)
                elim = grid.candidate_sets[add_cand] & buddies_all
                for cell in additional + two_cands:
                    elim &= ~(1 << cell)
                if elim:
                    i1, i2 = additional[0], (additional[1] if len(additional) > 1 else two_cands[0])
                    r1, c1 = CONSTRAINTS[i1][:2]
                    r2, c2 = CONSTRAINTS[i2][:2]
                    same_line_or_col = (r1 == r2 or c1 == c2)
                    sol_type = (
                        SolutionType.UNIQUENESS_2
                        if (len(additional) <= 2 and same_line_or_col)
                        else SolutionType.UNIQUENESS_5
                    )
                    s = make_step(sol_type)
                    tmp = elim
                    while tmp:
                        lsb = tmp & -tmp
                        s.add_candidate_to_delete(lsb.bit_length() - 1, add_cand)
                        tmp ^= lsb
                    result = emit(s)
                    if result:
                        return result

        # UT3: 2 additional-candidate cells; find k-1 more cells in a shared house
        # to form a Naked Subset on the additional candidates
        if twoSize == 2:
            u3_cands = 0
            for cell in additional:
                u3_cands |= grid.candidates[cell] & ~ur_mask & _ALL_DIGITS
            i1, i2 = additional
            r1, c1, b1 = CONSTRAINTS[i1]
            r2, c2, b2 = CONSTRAINTS[i2]
            ur_all = set(indexe)
            for unit_cells, unit_type in [
                (LINES[r1] if r1 == r2 else None, 0),
                (COLS[c1] if c1 == c2 else None, 1),
                (BLOCKS[b1] if b1 == b2 else None, 2),
            ]:
                if unit_cells is None:
                    continue
                # Candidates to add: cells in unit not in UR and not holding cand1/cand2
                u3_pool = [
                    c for c in unit_cells
                    if c not in ur_all
                    and grid.values[c] == 0
                    and not (grid.candidates[c] >> (cand1 - 1) & 1)
                    and not (grid.candidates[c] >> (cand2 - 1) & 1)
                    and grid.candidates[c] & _ALL_DIGITS
                ]
                step = self._check_ut3_recursive(
                    unit_type, unit_cells, u3_pool, u3_cands, list(additional),
                    ur_mask, ur_all, 0, indexe, cand1, cand2, cached, target_type
                )
                if step:
                    return step

        # UT4: 2 additional-candidate cells in same row/col; one UR candidate is absent
        # from all cells seen by both → eliminate the other from the 2 extra cells
        if twoSize == 2:
            i1, i2 = additional
            r1, c1 = CONSTRAINTS[i1][:2]
            r2, c2 = CONSTRAINTS[i2][:2]
            if r1 == r2 or c1 == c2:
                shared_buddies = BUDDIES[i1] & BUDDIES[i2]
                del_cand = -1
                if not (grid.candidate_sets[cand1] & shared_buddies):
                    del_cand = cand2
                elif not (grid.candidate_sets[cand2] & shared_buddies):
                    del_cand = cand1
                if del_cand != -1:
                    s = make_step(SolutionType.UNIQUENESS_4)
                    for cell in additional:
                        if grid.candidates[cell] >> (del_cand - 1) & 1:
                            s.add_candidate_to_delete(cell, del_cand)
                    if s.candidates_to_delete:
                        result = emit(s)
                        if result:
                            return result

        # UT6: 2 diagonal additional-candidate cells; one UR candidate appears ONLY
        # in the UR cells in both its rows and cols → delete that candidate from the 2 extra cells
        if twoSize == 2:
            i1, i2 = additional
            r1, c1 = CONSTRAINTS[i1][:2]
            r2, c2 = CONSTRAINTS[i2][:2]
            if r1 != r2 and c1 != c2:
                # union of lines and cols through the extra cells, minus the UR itself
                lines_cols_mask = 0
                for row in (r1, r2):
                    for cell in LINES[row]:
                        lines_cols_mask |= 1 << cell
                for col in (c1, c2):
                    for cell in COLS[col]:
                        lines_cols_mask |= 1 << cell
                for cell in indexe:
                    lines_cols_mask &= ~(1 << cell)
                del_cand = -1
                if not (grid.candidate_sets[cand1] & lines_cols_mask):
                    del_cand = cand1
                elif not (grid.candidate_sets[cand2] & lines_cols_mask):
                    del_cand = cand2
                if del_cand != -1:
                    s = make_step(SolutionType.UNIQUENESS_6)
                    for cell in additional:
                        if grid.candidates[cell] >> (del_cand - 1) & 1:
                            s.add_candidate_to_delete(cell, del_cand)
                    if s.candidates_to_delete:
                        result = emit(s)
                        if result:
                            return result

        # Hidden Rectangle: 1 or 2 bivalue cells (diagonally placed if 2);
        # the row AND col through the non-bivalue side have no other occurrences
        # of one UR candidate → eliminate the other from the intersection cell
        if twoSize in (1, 2):
            if twoSize == 2:
                i1t, i2t = two_cands
                r1t, c1t = CONSTRAINTS[i1t][:2]
                r2t, c2t = CONSTRAINTS[i2t][:2]
                if r1t == r2t or c1t == c2t:
                    pass  # must be diagonal
                else:
                    for corner in two_cands:
                        step = self._check_hidden_rect(
                            corner, additional, two_cands, cand1, cand2,
                            indexe, cached, target_type
                        )
                        if step:
                            return step
            else:
                corner = two_cands[0]
                step = self._check_hidden_rect(
                    corner, additional, two_cands, cand1, cand2,
                    indexe, cached, target_type
                )
                if step:
                    return step

        return None

    def _check_ut3_recursive(
        self,
        unit_type: int,
        unit_cells: tuple[int, ...],
        pool: list[int],
        cands_included: int,
        indices_included: list[int],
        ur_mask: int,
        ur_all: set[int],
        start: int,
        indexe: tuple[int, int, int, int],
        cand1: int, cand2: int,
        cached: list[SolutionStep],
        target_type: SolutionType,
    ) -> SolutionStep | None:
        grid = self.grid
        for i in range(start, len(pool)):
            new_cands = cands_included | (grid.candidates[pool[i]] & _ALL_DIGITS)
            new_indices = indices_included + [pool[i]]

            # For blocks: skip if all in same row/col (already checked by line/col pass)
            if unit_type == 2 and _same_line_or_col(new_indices):
                pass
            else:
                n_cands = bin(new_cands).count("1")
                n_cells = len(new_indices)
                if n_cands == n_cells - 1:
                    # Naked Subset found — find eliminations in the unit
                    s = SolutionStep(SolutionType.UNIQUENESS_3)
                    s.add_value(cand1)
                    s.add_value(cand2)
                    for c in indexe:
                        s.add_index(c)
                    new_idx_set = set(new_indices)
                    for cell in unit_cells:
                        if grid.values[cell] != 0 or cell in new_idx_set:
                            continue
                        del_mask = grid.candidates[cell] & new_cands
                        for d in range(1, 10):
                            if del_mask >> (d - 1) & 1:
                                s.add_candidate_to_delete(cell, d)
                    # Also eliminate from shared block if applicable
                    if unit_type in (0, 1):
                        block = _same_block(new_indices)
                        if block != -1:
                            for cell in BLOCKS[block]:
                                if grid.values[cell] != 0 or cell in new_idx_set:
                                    continue
                                del_mask = grid.candidates[cell] & new_cands
                                for d in range(1, 10):
                                    if del_mask >> (d - 1) & 1:
                                        s.add_candidate_to_delete(cell, d)
                    # Add fins (the subset cells and their shared candidates)
                    for d in range(1, 10):
                        if new_cands >> (d - 1) & 1:
                            for cell in new_indices:
                                if grid.candidates[cell] >> (d - 1) & 1:
                                    s.fins.append(Candidate(cell, d))
                    if s.candidates_to_delete:
                        if s.type == target_type:
                            return s
                        cached.append(s)

            step = self._check_ut3_recursive(
                unit_type, unit_cells, pool, new_cands, new_indices,
                ur_mask, ur_all, i + 1, indexe, cand1, cand2, cached, target_type
            )
            if step:
                return step
        return None

    def _check_hidden_rect(
        self,
        corner: int,
        additional: list[int],
        two_cands: list[int],
        cand1: int, cand2: int,
        indexe: tuple[int, int, int, int],
        cached: list[SolutionStep],
        target_type: SolutionType,
    ) -> SolutionStep | None:
        """Check Hidden Rectangle from one corner cell."""
        grid = self.grid
        r_c, c_c = CONSTRAINTS[corner][:2]
        i1, i2 = additional[0], additional[1]
        r1, c1 = CONSTRAINTS[i1][:2]
        r2, c2 = CONSTRAINTS[i2][:2]
        # The "other" line and col (not through corner)
        line1 = r1 if r1 != r_c else r2
        col1  = c1 if c1 != c_c else c2

        all_ur: int = 0
        for cell in indexe:
            all_ur |= 1 << cell

        for (check_cand, del_cand) in ((cand1, cand2), (cand2, cand1)):
            # check_cand must appear only within the UR in line1 AND col1
            line_others = grid.candidate_sets[check_cand] & self._line_mask(line1) & ~all_ur
            col_others  = grid.candidate_sets[check_cand] & self._col_mask(col1)  & ~all_ur
            if line_others or col_others:
                continue
            # del_cand can be removed from the cell at (line1, col1)
            del_idx = line1 * 9 + col1
            if grid.candidate_sets[del_cand] >> del_idx & 1:
                s = SolutionStep(SolutionType.HIDDEN_RECTANGLE)
                s.add_value(cand1)
                s.add_value(cand2)
                for c in indexe:
                    s.add_index(c)
                s.add_candidate_to_delete(del_idx, del_cand)
                if s.type == target_type:
                    return s
                cached.append(s)
        return None

    def _line_mask(self, row: int) -> int:
        mask = 0
        for c in range(9):
            mask |= 1 << (row * 9 + c)
        return mask

    def _col_mask(self, col: int) -> int:
        mask = 0
        for r in range(9):
            mask |= 1 << (r * 9 + col)
        return mask


def _same_line_or_col(indices: list[int]) -> bool:
    if not indices:
        return False
    r0, c0 = CONSTRAINTS[indices[0]][:2]
    return (all(CONSTRAINTS[i][0] == r0 for i in indices) or
            all(CONSTRAINTS[i][1] == c0 for i in indices))


def _same_block(indices: list[int]) -> int:
    """Return block index if all cells share one block, else -1."""
    if not indices:
        return -1
    b0 = CONSTRAINTS[indices[0]][2]
    if all(CONSTRAINTS[i][2] == b0 for i in indices):
        return b0
    return -1
