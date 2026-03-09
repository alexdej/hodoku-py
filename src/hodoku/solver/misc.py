"""Miscellaneous solver — Sue de Coq.

Port of HoDoKu's MiscellaneousSolver.java.
"""

from __future__ import annotations

from hodoku.core.grid import (
    Grid, LINES, COLS, BLOCKS,
    LINE_MASKS, COL_MASKS, BLOCK_MASKS,
)
from hodoku.core.solution_step import Candidate, SolutionStep
from hodoku.core.types import SolutionType


def _popcount(v: int) -> int:
    return v.bit_count()


def _iter_bits(mask: int):
    """Yield individual bit positions from a bitmask."""
    while mask:
        lsb = mask & -mask
        yield lsb.bit_length() - 1
        mask ^= lsb


def _cand_mask_for_cells(grid: Grid, cell_mask: int) -> int:
    """OR together the candidate bitmasks for all cells in *cell_mask*."""
    result = 0
    for idx in _iter_bits(cell_mask):
        result |= grid.candidates[idx]
    return result


class MiscSolver:
    """Sue de Coq solver."""

    def __init__(self, grid: Grid) -> None:
        self.grid = grid

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def get_step(self, sol_type: SolutionType) -> SolutionStep | None:
        if sol_type is SolutionType.SUE_DE_COQ:
            return self._find_sdc(only_one=True)
        return None

    def find_all(self, sol_type: SolutionType) -> list[SolutionStep]:
        if sol_type is SolutionType.SUE_DE_COQ:
            results: list[SolutionStep] = []
            self._find_sdc(only_one=False, results=results)
            return results
        return []

    # ------------------------------------------------------------------
    # Sue de Coq core
    # ------------------------------------------------------------------

    def _find_sdc(
        self,
        only_one: bool = True,
        results: list[SolutionStep] | None = None,
    ) -> SolutionStep | None:
        grid = self.grid
        # Build bitmask of empty (unsolved) cells
        empty = 0
        for i in range(81):
            if grid.values[i] == 0:
                empty |= 1 << i

        # Try every (row_or_col, block) pair
        for line_masks, line_units in ((LINE_MASKS, LINES), (COL_MASKS, COLS)):
            for li in range(9):
                non_block_all = line_masks[li] & empty
                for bi in range(9):
                    block_all = BLOCK_MASKS[bi] & empty
                    intersection = non_block_all & block_all
                    if _popcount(intersection) < 2:
                        continue
                    step = self._check_intersection(
                        grid, intersection, non_block_all, block_all,
                        only_one, results,
                    )
                    if only_one and step is not None:
                        return step
        return None

    def _check_intersection(
        self,
        grid: Grid,
        intersection: int,
        non_block_all: int,
        block_all: int,
        only_one: bool,
        results: list[SolutionStep] | None,
    ) -> SolutionStep | None:
        """Try all 2-cell and 3-cell subsets of the intersection."""
        cells = list(_iter_bits(intersection))
        n = len(cells)

        for i1 in range(n - 1):
            c1 = cells[i1]
            cand1 = grid.candidates[c1]
            mask1 = 1 << c1

            for i2 in range(i1 + 1, n):
                c2 = cells[i2]
                cand2 = cand1 | grid.candidates[c2]
                mask2 = mask1 | (1 << c2)

                # 2-cell subset: need |V| >= |C| + 2, i.e. >= 4 candidates
                n_plus = _popcount(cand2) - 2
                if n_plus >= 2:
                    step = self._check_houses(
                        grid, mask2, cand2, n_plus,
                        non_block_all, block_all,
                        only_one, results,
                    )
                    if only_one and step is not None:
                        return step

                # 3-cell subsets
                for i3 in range(i2 + 1, n):
                    c3 = cells[i3]
                    cand3 = cand2 | grid.candidates[c3]
                    mask3 = mask2 | (1 << c3)
                    n_plus3 = _popcount(cand3) - 3
                    if n_plus3 >= 2:
                        step = self._check_houses(
                            grid, mask3, cand3, n_plus3,
                            non_block_all, block_all,
                            only_one, results,
                        )
                        if only_one and step is not None:
                            return step
        return None

    def _check_houses(
        self,
        grid: Grid,
        inter_cells: int,
        inter_cands: int,
        n_plus: int,
        non_block_all: int,
        block_all: int,
        only_one: bool,
        results: list[SolutionStep] | None,
    ) -> SolutionStep | None:
        """Search for matching cell sets in the row/col and block."""
        # Source cells: row/col cells NOT in the intersection
        nb_source = non_block_all & ~inter_cells
        # First pass: enumerate row/col subsets
        return self._search_non_block(
            grid, nb_source, inter_cells, inter_cands, n_plus,
            block_all, only_one, results,
        )

    def _search_non_block(
        self,
        grid: Grid,
        nb_source: int,
        inter_cells: int,
        inter_cands: int,
        n_plus: int,
        block_all: int,
        only_one: bool,
        results: list[SolutionStep] | None,
    ) -> SolutionStep | None:
        """Enumerate subsets of nb_source cells for the row/col part."""
        if not nb_source:
            return None
        source_list = list(_iter_bits(nb_source))
        max_cells = len(source_list)

        # Iterative subset enumeration (matching Java's stack approach)
        # We try all subsets of source_list, from size 1 upward.
        # For each subset, check if it qualifies, then hand off to block search.
        #
        # Use a simple recursive generator for clarity.
        return self._enum_nb_subsets(
            grid, source_list, 0, 0, 0, 0,
            inter_cells, inter_cands, n_plus,
            block_all, only_one, results,
        )

    def _enum_nb_subsets(
        self,
        grid: Grid,
        source: list[int],
        pos: int,
        level: int,
        sel_cells: int,
        sel_cands: int,
        inter_cells: int,
        inter_cands: int,
        n_plus: int,
        block_all: int,
        only_one: bool,
        results: list[SolutionStep] | None,
    ) -> SolutionStep | None:
        """Recursively enumerate non-block (row/col) subsets."""
        for i in range(pos, len(source)):
            idx = source[i]
            new_cands = sel_cands | grid.candidates[idx]

            # Prune: all candidates must be either from intersection or "extra"
            # No constraint on allowed cands for first pass (allowedCandSet = MAX_MASK)

            cands_from_inter = new_cands & inter_cands
            n_contained = _popcount(cands_from_inter)
            cands_extra = new_cands & ~inter_cands
            n_extra = _popcount(cands_extra)
            new_level = level + 1
            new_cells = sel_cells | (1 << idx)

            # The row/col set must:
            # 1. Contain at least one candidate from the intersection (n_contained > 0)
            # 2. Have more cells than extra candidates (new_level > n_extra)
            # 3. Leave some intersection candidates for the block (new_level - n_extra < n_plus)
            if n_contained > 0 and new_level > n_extra and new_level - n_extra < n_plus:
                # Viable: search block
                remaining_n_plus = n_plus - (new_level - n_extra)
                # Block source: block cells not in intersection and not in nb selection
                blk_source = block_all & ~inter_cells & ~new_cells
                # Block can't use candidates already claimed by row/col
                # (but extra candidates shared by both sets ARE allowed — handled in elimination)
                blk_disallowed = new_cands & ~cands_extra  # = intersection cands used by nb
                blk_allowed_mask = ~blk_disallowed & 0x1FF

                step = self._search_block(
                    grid, blk_source, blk_allowed_mask,
                    inter_cells, inter_cands, remaining_n_plus,
                    new_cells, new_cands,
                    block_all & ~inter_cells,  # full block minus intersection for elims
                    only_one, results,
                )
                if only_one and step is not None:
                    return step

            # Continue to larger subsets
            step = self._enum_nb_subsets(
                grid, source, i + 1, new_level, new_cells, new_cands,
                inter_cells, inter_cands, n_plus,
                block_all, only_one, results,
            )
            if only_one and step is not None:
                return step
        return None

    def _search_block(
        self,
        grid: Grid,
        blk_source: int,
        blk_allowed_mask: int,
        inter_cells: int,
        inter_cands: int,
        n_plus: int,
        nb_cells: int,
        nb_cands: int,
        blk_elim_region: int,
        only_one: bool,
        results: list[SolutionStep] | None,
    ) -> SolutionStep | None:
        """Enumerate block cell subsets for the second pass."""
        if not blk_source:
            return None
        source_list = list(_iter_bits(blk_source))
        return self._enum_blk_subsets(
            grid, source_list, 0, 0, 0, 0,
            blk_allowed_mask, inter_cells, inter_cands, n_plus,
            nb_cells, nb_cands, blk_elim_region,
            only_one, results,
        )

    def _enum_blk_subsets(
        self,
        grid: Grid,
        source: list[int],
        pos: int,
        level: int,
        sel_cells: int,
        sel_cands: int,
        allowed_mask: int,
        inter_cells: int,
        inter_cands: int,
        n_plus: int,
        nb_cells: int,
        nb_cands: int,
        blk_elim_region: int,
        only_one: bool,
        results: list[SolutionStep] | None,
    ) -> SolutionStep | None:
        for i in range(pos, len(source)):
            idx = source[i]
            cell_cands = grid.candidates[idx]

            # Cell must not contain disallowed candidates
            if cell_cands & ~allowed_mask:
                continue

            new_cands = sel_cands | cell_cands
            cands_from_inter = new_cands & inter_cands
            n_contained = _popcount(cands_from_inter)
            cands_extra = new_cands & ~inter_cands
            n_extra = _popcount(cands_extra)
            new_level = level + 1
            new_cells = sel_cells | (1 << idx)

            # For block (second pass): need exactly n_plus intersection-cands covered
            if n_contained > 0 and new_level - n_extra == n_plus:
                # It's a Sue de Coq! Check for eliminations.
                step = self._build_step(
                    grid, inter_cells, inter_cands,
                    nb_cells, nb_cands,
                    new_cells, new_cands,
                    blk_elim_region,
                )
                if step is not None:
                    if only_one:
                        return step
                    if results is not None:
                        results.append(step)

            # Try larger subsets: continue even at exact match because adding
            # a cell with extra candidates keeps coverage constant (Java always
            # goes deeper, pruning only via allowed_mask).
            if new_level - n_extra <= n_plus:
                step = self._enum_blk_subsets(
                    grid, source, i + 1, new_level, new_cells, new_cands,
                    allowed_mask, inter_cells, inter_cands, n_plus,
                    nb_cells, nb_cands, blk_elim_region,
                    only_one, results,
                )
                if only_one and step is not None:
                    return step
        return None

    def _build_step(
        self,
        grid: Grid,
        inter_cells: int,
        inter_cands: int,
        nb_cells: int,
        nb_cands: int,
        blk_cells: int,
        blk_cands: int,
        blk_elim_region: int,
    ) -> SolutionStep | None:
        """Build a SolutionStep if any eliminations exist.

        Elimination rules (matching Java):
        - In block cells (block - intersection - blockActSet):
          eliminate ((inter_cands | blk_cands) & ~nb_cands) | shared_extra
        - In row/col cells (row/col - intersection - nbActSet):
          eliminate ((inter_cands | nb_cands) & ~blk_cands) | shared_extra

        shared_extra = extra candidates appearing in BOTH nb and block sets.
        """
        # Extra candidates shared between both sets
        shared_extra = (nb_cands & blk_cands) & ~inter_cands

        elims: list[Candidate] = []

        # Block eliminations: cells in block not part of SDC
        blk_check = blk_elim_region & ~blk_cells
        if blk_check:
            blk_elim_cands = ((inter_cands | blk_cands) & ~nb_cands) | shared_extra
            if blk_elim_cands:
                for idx in _iter_bits(blk_check):
                    hit = grid.candidates[idx] & blk_elim_cands
                    for d in _iter_bits(hit):
                        elims.append(Candidate(idx, d + 1))

        # Row/col eliminations: cells in row/col not part of SDC
        # The non-block region for eliminations is all non-block cells minus
        # intersection minus nb selection.  We reconstruct it from the line.
        # Actually, we can get non_block_all from the caller... let me
        # use a trick: nb_cells are in the row/col, inter_cells are in both,
        # and blk_cells are in the block. The row/col elim region is:
        # (all row/col empty cells) - intersection - nb_cells
        # We don't have non_block_all here directly. But we can compute the
        # row/col from inter_cells and nb_cells: they share the same row/col.
        # Let me instead pass non_block_all through... Actually, let me
        # restructure: pass non_block_all to _build_step.
        #
        # For now, compute from the grid: find which row/col contains inter_cells.
        # All inter cells share a row and a col; check which is the line.
        first_inter = (inter_cells & -inter_cells).bit_length() - 1
        row = first_inter // 9
        col = first_inter % 9
        # Check if all inter cells are in the same row
        if inter_cells & LINE_MASKS[row] == inter_cells:
            nb_all = LINE_MASKS[row]
        else:
            nb_all = COL_MASKS[col]
        # Only empty cells
        nb_empty = 0
        for idx in _iter_bits(nb_all):
            if grid.values[idx] == 0:
                nb_empty |= 1 << idx
        nb_check = nb_empty & ~inter_cells & ~nb_cells
        if nb_check:
            nb_elim_cands = ((inter_cands | nb_cands) & ~blk_cands) | shared_extra
            if nb_elim_cands:
                for idx in _iter_bits(nb_check):
                    hit = grid.candidates[idx] & nb_elim_cands
                    for d in _iter_bits(hit):
                        elims.append(Candidate(idx, d + 1))

        if not elims:
            return None

        step = SolutionStep(SolutionType.SUE_DE_COQ)
        step.candidates_to_delete = elims
        # Store intersection cells and candidates in indices/values
        for idx in _iter_bits(inter_cells):
            step.add_index(idx)
        return step
