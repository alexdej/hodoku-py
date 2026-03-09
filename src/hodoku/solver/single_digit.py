"""Single-digit pattern solver: Skyscraper, 2-String Kite, Empty Rectangle.

Mirrors Java's SingleDigitPatternSolver.
"""

from __future__ import annotations

from hodoku.core.grid import (
    Grid,
    ALL_UNITS,
    BLOCKS,
    BLOCK_MASKS,
    BUDDIES,
    COL_MASKS,
    CONSTRAINTS,
    COLS,
    LINE_MASKS,
    LINES,
)
from hodoku.core.solution_step import Candidate, SolutionStep
from hodoku.core.types import SolutionType

# ---------------------------------------------------------------------------
# Empty Rectangle static lookup tables (computed once at import time)
# ---------------------------------------------------------------------------

# Relative grid-index offsets within a block for the "empty" cells of each ER pattern.
# Offsets are from the top-left cell of the block (index 0 of the block).
_ER_OFFSETS: list[list[int]] = [
    [0, 1, 9, 10],
    [0, 2, 9, 11],
    [1, 2, 10, 11],
    [0, 1, 18, 19],
    [0, 2, 18, 20],
    [1, 2, 19, 20],
    [9, 10, 18, 19],
    [9, 11, 18, 20],
    [10, 11, 19, 20],
]

# Row / col offsets for the ER line/col, relative to the block's first row/col.
_ER_LINE_OFFSETS: list[int] = [2, 2, 2, 1, 1, 1, 0, 0, 0]
_ER_COL_OFFSETS:  list[int] = [2, 1, 0, 2, 1, 0, 2, 1, 0]


def _build_er_tables() -> tuple[
    list[list[int]], list[list[int]], list[list[int]]
]:
    """Precompute ER_SETS, ER_LINES, ER_COLS for all 9 blocks × 9 patterns."""
    er_sets:  list[list[int]] = [[0] * 9 for _ in range(9)]
    er_lines: list[list[int]] = [[0] * 9 for _ in range(9)]
    er_cols:  list[list[int]] = [[0] * 9 for _ in range(9)]
    for b in range(9):
        b0 = BLOCKS[b][0]          # index of the top-left cell of block b
        r0, c0, _ = CONSTRAINTS[b0]
        for p in range(9):
            er_sets[b][p]  = sum(1 << (b0 + off) for off in _ER_OFFSETS[p])
            er_lines[b][p] = _ER_LINE_OFFSETS[p] + r0
            er_cols[b][p]  = _ER_COL_OFFSETS[p]  + c0
    return er_sets, er_lines, er_cols


ER_SETS, ER_LINES, ER_COLS = _build_er_tables()

_BLOCK_ENTITY = 2  # Entity type for BLOCK (matches Java's Sudoku2.BLOCK)


# ---------------------------------------------------------------------------
# Solver
# ---------------------------------------------------------------------------

class SingleDigitSolver:
    """Skyscraper, 2-String Kite, Empty Rectangle."""

    def __init__(self, grid: Grid) -> None:
        self.grid = grid

    def get_step(self, sol_type: SolutionType) -> SolutionStep | None:
        if sol_type == SolutionType.SKYSCRAPER:
            return self._find_skyscraper()
        if sol_type == SolutionType.TWO_STRING_KITE:
            return self._find_two_string_kite()
        if sol_type == SolutionType.EMPTY_RECTANGLE:
            return self._find_empty_rectangle()
        if sol_type == SolutionType.DUAL_TWO_STRING_KITE:
            steps = self._find_dual_two_string_kites()
            return steps[0] if steps else None
        if sol_type == SolutionType.DUAL_EMPTY_RECTANGLE:
            steps = self._find_dual_empty_rectangles()
            return steps[0] if steps else None
        return None

    def find_all(self, sol_type: SolutionType) -> list[SolutionStep]:
        if sol_type == SolutionType.SKYSCRAPER:
            return self._find_skyscraper_all()
        if sol_type == SolutionType.TWO_STRING_KITE:
            return self._find_two_string_kite_all()
        if sol_type == SolutionType.EMPTY_RECTANGLE:
            return self._find_empty_rectangle_all()
        if sol_type == SolutionType.DUAL_TWO_STRING_KITE:
            return self._find_dual_two_string_kites()
        if sol_type == SolutionType.DUAL_EMPTY_RECTANGLE:
            return self._find_dual_empty_rectangles()
        return []

    def _find_skyscraper_all(self) -> list[SolutionStep]:
        """Return ALL Skyscraper steps."""
        grid = self.grid
        results: list[SolutionStep] = []
        seen_elims: set[tuple] = set()
        for cand in range(1, 10):
            for lines in (True, False):
                c_start, c_end = (0, 9) if lines else (9, 18)
                pairs = self._collect_pairs(c_start, c_end, cand)
                n = len(pairs)
                for i in range(n):
                    a0, a1 = pairs[i]
                    for j in range(i + 1, n):
                        b0, b1 = pairs[j]
                        if lines:
                            if CONSTRAINTS[a0][1] == CONSTRAINTS[b0][1]:
                                other = 1
                            elif CONSTRAINTS[a1][1] == CONSTRAINTS[b1][1]:
                                other = 0
                            else:
                                continue
                        else:
                            if CONSTRAINTS[a0][0] == CONSTRAINTS[b0][0]:
                                other = 1
                            elif CONSTRAINTS[a1][0] == CONSTRAINTS[b1][0]:
                                other = 0
                            else:
                                continue

                        free_i = pairs[i][other]
                        free_j = pairs[j][other]

                        if lines:
                            if CONSTRAINTS[free_i][1] == CONSTRAINTS[free_j][1]:
                                continue
                        else:
                            if CONSTRAINTS[free_i][0] == CONSTRAINTS[free_j][0]:
                                continue

                        elim = (
                            grid.candidate_sets[cand]
                            & BUDDIES[free_i]
                            & BUDDIES[free_j]
                        )
                        if elim:
                            linked_i = pairs[i][1 - other]
                            linked_j = pairs[j][1 - other]
                            key = (cand, elim)
                            if key not in seen_elims:
                                seen_elims.add(key)
                                step = SolutionStep(SolutionType.SKYSCRAPER)
                                step.add_value(cand)
                                step.add_index(free_i)
                                step.add_index(free_j)
                                step.add_index(linked_i)
                                step.add_index(linked_j)
                                tmp = elim
                                while tmp:
                                    lsb = tmp & -tmp
                                    step.add_candidate_to_delete(
                                        lsb.bit_length() - 1, cand
                                    )
                                    tmp ^= lsb
                                results.append(step)
        return results

    def _find_two_string_kite_all(self) -> list[SolutionStep]:
        """Return ALL 2-String Kite steps."""
        grid = self.grid
        results: list[SolutionStep] = []
        seen_elims: set[tuple] = set()
        for cand in range(1, 10):
            line_pairs = self._collect_pairs(0, 9, cand)
            col_pairs  = self._collect_pairs(9, 18, cand)
            for lp in line_pairs:
                for cp in col_pairs:
                    la, lb = lp
                    ca, cb = cp

                    la_b = CONSTRAINTS[la][2]
                    lb_b = CONSTRAINTS[lb][2]
                    ca_b = CONSTRAINTS[ca][2]
                    cb_b = CONSTRAINTS[cb][2]
                    if la_b == ca_b:
                        pass
                    elif la_b == cb_b:
                        ca, cb = cb, ca
                    elif lb_b == ca_b:
                        la, lb = lb, la
                    elif lb_b == cb_b:
                        la, lb = lb, la
                        ca, cb = cb, ca
                    else:
                        continue

                    if la == ca or la == cb or lb == ca or lb == cb:
                        continue

                    cross = CONSTRAINTS[cb][0] * 9 + CONSTRAINTS[lb][1]
                    if grid.candidate_sets[cand] >> cross & 1:
                        key = (cand, cross)
                        if key not in seen_elims:
                            seen_elims.add(key)
                            step = SolutionStep(SolutionType.TWO_STRING_KITE)
                            step.add_value(cand)
                            step.add_index(lb)
                            step.add_index(cb)
                            step.add_index(la)
                            step.add_index(ca)
                            step.add_candidate_to_delete(cross, cand)
                            step.fins.append(Candidate(la, cand))
                            step.fins.append(Candidate(ca, cand))
                            results.append(step)
        return results

    def _find_empty_rectangle_all(self) -> list[SolutionStep]:
        """Return ALL Empty Rectangle steps."""
        grid = self.grid
        results: list[SolutionStep] = []
        seen_elims: set[tuple] = set()
        for cand in range(1, 10):
            for b in range(9):
                count = grid.free[18 + b][cand]
                if count < 2 or count > 5:
                    continue
                block_cands = grid.candidate_sets[cand] & BLOCK_MASKS[b]
                for p in range(9):
                    if block_cands & ER_SETS[b][p]:
                        continue

                    er_line = ER_LINES[b][p]
                    er_col  = ER_COLS[b][p]

                    line_full = block_cands & LINE_MASKS[er_line]
                    line_part = line_full & ~COL_MASKS[er_col]
                    if not line_part:
                        continue

                    col_full = block_cands & COL_MASKS[er_col]
                    col_part = col_full & ~LINE_MASKS[er_line]
                    if not col_part:
                        continue

                    for cells, col_mode, constr in (
                        (LINES[er_line], False, er_col),
                        (COLS[er_col], True, er_line),
                    ):
                        step = self._check_er(cand, b, block_cands, cells, col_mode, constr)
                        if step:
                            key = tuple(sorted(
                                (c.index, c.value) for c in step.candidates_to_delete
                            ))
                            if key not in seen_elims:
                                seen_elims.add(key)
                                results.append(step)
        return results

    # ------------------------------------------------------------------
    # Dual patterns
    # ------------------------------------------------------------------

    def _find_dual_two_string_kites(self) -> list[SolutionStep]:
        """Find Dual 2-String Kites.

        A dual 2SK combines two 2SKs that share the same block connection
        (indices[2] and indices[3]) but produce different eliminations.
        """
        kites = self._find_two_string_kite_all()
        duals: list[SolutionStep] = []
        n = len(kites)
        for i in range(n - 1):
            s1 = kites[i]
            b11 = s1.indices[2]
            b12 = s1.indices[3]
            for j in range(i + 1, n):
                s2 = kites[j]
                b21 = s2.indices[2]
                b22 = s2.indices[3]
                if not ((b11 == b21 and b12 == b22) or (b12 == b21 and b11 == b22)):
                    continue
                if s1.candidates_to_delete[0] == s2.candidates_to_delete[0]:
                    continue  # same elimination
                dual = SolutionStep(SolutionType.DUAL_TWO_STRING_KITE)
                dual.values = list(s1.values)
                for idx in s1.indices:
                    dual.add_index(idx)
                for idx in s2.indices:
                    dual.add_index(idx)
                dual.fins = list(s1.fins)
                dual.candidates_to_delete = list(s1.candidates_to_delete)
                dual.add_candidate_to_delete(
                    s2.candidates_to_delete[0].index,
                    s2.candidates_to_delete[0].value,
                )
                duals.append(dual)
        return duals

    def _find_dual_empty_rectangles(self) -> list[SolutionStep]:
        """Find Dual Empty Rectangles.

        A dual ER combines two ERs from the same box with the same ER
        candidates (fins) but different eliminations.
        """
        ers = self._find_empty_rectangle_all()
        duals: list[SolutionStep] = []
        n = len(ers)
        for i in range(n - 1):
            s1 = ers[i]
            for j in range(i + 1, n):
                s2 = ers[j]
                # Same box (entity/entityNumber)
                if s1.entity != s2.entity or s1.entity_number != s2.entity_number:
                    continue
                # Same fins (box candidates)
                if len(s1.fins) != len(s2.fins):
                    continue
                if s1.fins != s2.fins:
                    continue
                # Different elimination
                if s1.candidates_to_delete[0] == s2.candidates_to_delete[0]:
                    continue
                dual = SolutionStep(SolutionType.DUAL_EMPTY_RECTANGLE)
                dual.values = list(s1.values)
                dual.entity = s1.entity
                dual.entity_number = s1.entity_number
                for idx in s1.indices:
                    dual.add_index(idx)
                for idx in s2.indices:
                    dual.add_index(idx)
                dual.fins = list(s1.fins)
                dual.candidates_to_delete = list(s1.candidates_to_delete)
                dual.add_candidate_to_delete(
                    s2.candidates_to_delete[0].index,
                    s2.candidates_to_delete[0].value,
                )
                duals.append(dual)
        return duals

    # ------------------------------------------------------------------
    # Shared helper
    # ------------------------------------------------------------------

    def _collect_pairs(
        self, c_start: int, c_end: int, cand: int
    ) -> list[tuple[int, int]]:
        """Return (cell_a, cell_b) for each unit in [c_start, c_end) with
        exactly 2 candidates for digit cand."""
        grid = self.grid
        pairs: list[tuple[int, int]] = []
        for constr in range(c_start, c_end):
            if grid.free[constr][cand] == 2:
                found: list[int] = []
                for cell in ALL_UNITS[constr]:
                    if grid.candidate_sets[cand] >> cell & 1:
                        found.append(cell)
                        if len(found) == 2:
                            break
                if len(found) == 2:
                    pairs.append((found[0], found[1]))
        return pairs

    # ------------------------------------------------------------------
    # Skyscraper
    # ------------------------------------------------------------------

    def _find_skyscraper(self) -> SolutionStep | None:
        """Find the first Skyscraper elimination.

        Row-mode: scan rows; linked ends share the same column.
        Col-mode: scan cols; linked ends share the same row.
        """
        grid = self.grid
        for cand in range(1, 10):
            for lines in (True, False):
                c_start, c_end = (0, 9) if lines else (9, 18)
                pairs = self._collect_pairs(c_start, c_end, cand)
                n = len(pairs)
                for i in range(n):
                    a0, a1 = pairs[i]
                    for j in range(i + 1, n):
                        b0, b1 = pairs[j]
                        # Find which pair of ends share a row/col (the "linked" ends).
                        # other = index into each pair for the FREE (non-linked) end.
                        if lines:
                            if CONSTRAINTS[a0][1] == CONSTRAINTS[b0][1]:
                                other = 1  # a0,b0 linked (same col); a1,b1 free
                            elif CONSTRAINTS[a1][1] == CONSTRAINTS[b1][1]:
                                other = 0  # a1,b1 linked; a0,b0 free
                            else:
                                continue
                        else:
                            if CONSTRAINTS[a0][0] == CONSTRAINTS[b0][0]:
                                other = 1  # a0,b0 linked (same row); a1,b1 free
                            elif CONSTRAINTS[a1][0] == CONSTRAINTS[b1][0]:
                                other = 0
                            else:
                                continue

                        free_i = pairs[i][other]
                        free_j = pairs[j][other]

                        # If free ends also share the relevant unit → X-Wing, skip
                        if lines:
                            if CONSTRAINTS[free_i][1] == CONSTRAINTS[free_j][1]:
                                continue
                        else:
                            if CONSTRAINTS[free_i][0] == CONSTRAINTS[free_j][0]:
                                continue

                        elim = (
                            grid.candidate_sets[cand]
                            & BUDDIES[free_i]
                            & BUDDIES[free_j]
                        )
                        if elim:
                            linked_i = pairs[i][1 - other]
                            linked_j = pairs[j][1 - other]
                            step = SolutionStep(SolutionType.SKYSCRAPER)
                            step.add_value(cand)
                            step.add_index(free_i)
                            step.add_index(free_j)
                            step.add_index(linked_i)
                            step.add_index(linked_j)
                            tmp = elim
                            while tmp:
                                lsb = tmp & -tmp
                                step.add_candidate_to_delete(
                                    lsb.bit_length() - 1, cand
                                )
                                tmp ^= lsb
                            return step
        return None

    # ------------------------------------------------------------------
    # 2-String Kite
    # ------------------------------------------------------------------

    def _find_two_string_kite(self) -> SolutionStep | None:
        """Find the first 2-String Kite elimination.

        One strong link in a row, one in a col, connected through a shared block.
        The "free ends" see a common candidate to eliminate.
        """
        grid = self.grid
        for cand in range(1, 10):
            line_pairs = self._collect_pairs(0, 9, cand)
            col_pairs  = self._collect_pairs(9, 18, cand)
            for lp in line_pairs:
                for cp in col_pairs:
                    # Local mutable copies so we can reorder without corrupting lists
                    la, lb = lp   # la=index 0, lb=index 1 (mutable labels)
                    ca, cb = cp

                    # Reorder so that la and ca are the block-connected ends.
                    # 4 possible alignments:
                    la_b = CONSTRAINTS[la][2]
                    lb_b = CONSTRAINTS[lb][2]
                    ca_b = CONSTRAINTS[ca][2]
                    cb_b = CONSTRAINTS[cb][2]
                    if la_b == ca_b:
                        pass                    # la,ca share block → free: lb,cb
                    elif la_b == cb_b:
                        ca, cb = cb, ca         # swap col pair
                    elif lb_b == ca_b:
                        la, lb = lb, la         # swap line pair
                    elif lb_b == cb_b:
                        la, lb = lb, la
                        ca, cb = cb, ca         # swap both
                    else:
                        continue               # no shared block

                    # All 4 cells must be distinct
                    if la == ca or la == cb or lb == ca or lb == cb:
                        continue

                    # cross_index = cell at (row of cb, col of lb)
                    cross = CONSTRAINTS[cb][0] * 9 + CONSTRAINTS[lb][1]
                    if grid.candidate_sets[cand] >> cross & 1:
                        step = SolutionStep(SolutionType.TWO_STRING_KITE)
                        step.add_value(cand)
                        step.add_index(lb)    # row free end
                        step.add_index(cb)    # col free end
                        step.add_index(la)    # row block end
                        step.add_index(ca)    # col block end
                        step.add_candidate_to_delete(cross, cand)
                        step.fins.append(Candidate(la, cand))
                        step.fins.append(Candidate(ca, cand))
                        return step
        return None

    # ------------------------------------------------------------------
    # Empty Rectangle
    # ------------------------------------------------------------------

    def _find_empty_rectangle(self) -> SolutionStep | None:
        """Find the first Empty Rectangle elimination."""
        grid = self.grid
        for cand in range(1, 10):
            for b in range(9):
                count = grid.free[18 + b][cand]
                if count < 2 or count > 5:
                    continue
                block_cands = grid.candidate_sets[cand] & BLOCK_MASKS[b]
                for p in range(9):
                    # Cells at these positions must be empty (no candidate)
                    if block_cands & ER_SETS[b][p]:
                        continue

                    er_line = ER_LINES[b][p]
                    er_col  = ER_COLS[b][p]

                    # Line part: block candidates in ER row, excluding ER col intersection
                    line_full = block_cands & LINE_MASKS[er_line]
                    not_enough = True
                    if line_full.bit_count() >= 2:
                        not_enough = False
                    line_part = line_full & ~COL_MASKS[er_col]
                    if not line_part:
                        continue

                    # Col part: block candidates in ER col, excluding ER row intersection
                    col_full = block_cands & COL_MASKS[er_col]
                    col_part = col_full & ~LINE_MASKS[er_line]
                    if not col_part:
                        continue

                    # Direction 1: iterate ER row cells, conjugate search in cols
                    step = self._check_er(
                        cand, b, block_cands,
                        LINES[er_line], False, er_col,
                    )
                    if step:
                        return step

                    # Direction 2: iterate ER col cells, conjugate search in rows
                    step = self._check_er(
                        cand, b, block_cands,
                        COLS[er_col], True, er_line,
                    )
                    if step:
                        return step

        return None

    def _check_er(
        self,
        cand: int,
        block: int,
        block_cands: int,
        cells: tuple[int, ...],
        reversed_: bool,
        er_unit_idx: int,
    ) -> SolutionStep | None:
        """Check ER eliminations in one scan direction.

        reversed_=False: iterate ER row; conjugate search in columns.
            er_unit_idx = er_col (0-8)
        reversed_=True:  iterate ER col; conjugate search in rows.
            er_unit_idx = er_line (0-8)
        """
        grid = self.grid
        conj_masks = LINE_MASKS if reversed_ else COL_MASKS
        other_masks = COL_MASKS if reversed_ else LINE_MASKS

        for index in cells:
            if grid.values[index] != 0:
                continue
            r, c, b = CONSTRAINTS[index]
            if b == block:
                continue
            if not (grid.candidate_sets[cand] >> index & 1):
                continue

            # Perpendicular dimension unit for conjugate-pair search
            unit = r if reversed_ else c
            conj_set = grid.candidate_sets[cand] & conj_masks[unit]
            if conj_set.bit_count() != 2:
                continue

            index2 = (conj_set ^ (1 << index)).bit_length() - 1
            r2, c2, _ = CONSTRAINTS[index2]

            # index2's other-dimension unit
            other_unit = c2 if reversed_ else r2
            line_cands = grid.candidate_sets[cand] & other_masks[other_unit]

            tmp = line_cands
            while tmp:
                lsb = tmp & -tmp
                index_del = lsb.bit_length() - 1
                tmp ^= lsb
                _, _, b_del = CONSTRAINTS[index_del]
                if b_del == block:
                    continue
                r_del, c_del, _ = CONSTRAINTS[index_del]
                unit_del = r_del if reversed_ else c_del
                if unit_del == er_unit_idx:
                    step = SolutionStep(SolutionType.EMPTY_RECTANGLE)
                    step.entity = _BLOCK_ENTITY
                    step.entity_number = block + 1
                    step.add_value(cand)
                    step.add_index(index)
                    step.add_index(index2)
                    bc = block_cands
                    while bc:
                        lsb2 = bc & -bc
                        step.fins.append(
                            Candidate(lsb2.bit_length() - 1, cand)
                        )
                        bc ^= lsb2
                    step.add_candidate_to_delete(index_del, cand)
                    return step

        return None
