"""Coloring solver: Simple Colors (Trap/Wrap), Multi-Colors.

Mirrors Java's ColoringSolver.
"""

from __future__ import annotations

from hodoku.core.grid import ALL_UNITS, BUDDIES, CONSTRAINTS, Grid
from hodoku.core.solution_step import SolutionStep
from hodoku.core.types import SolutionType


class ColoringSolver:
    """Simple Colors and Multi-Colors."""

    def __init__(self, grid: Grid) -> None:
        self.grid = grid

    def get_step(self, sol_type: SolutionType) -> SolutionStep | None:
        if sol_type in (SolutionType.SIMPLE_COLORS_TRAP, SolutionType.SIMPLE_COLORS_WRAP):
            return self._find_simple_colors()
        if sol_type in (SolutionType.MULTI_COLORS_1, SolutionType.MULTI_COLORS_2):
            return self._find_multi_colors()
        return None

    # ------------------------------------------------------------------
    # Coloring graph builder
    # ------------------------------------------------------------------

    def _do_coloring(self, cand: int) -> list[tuple[frozenset[int], frozenset[int]]]:
        """Partition cells with cand into color pairs via conjugate links.

        Returns a list of (C1, C2) frozensets.  Each pair is one connected
        component of the conjugate-pair graph; C1 and C2 alternate along links.
        Single-cell components (no conjugate link) are discarded.
        """
        grid = self.grid
        # Cells that carry cand and belong to at least one conjugate pair
        start: set[int] = set()
        all_cells_with_cand: int = grid.candidate_sets[cand]
        tmp = all_cells_with_cand
        while tmp:
            lsb = tmp & -tmp
            cell = lsb.bit_length() - 1
            r, c, b = CONSTRAINTS[cell]
            if (
                grid.free[r][cand] == 2
                or grid.free[9 + c][cand] == 2
                or grid.free[18 + b][cand] == 2
            ):
                start.add(cell)
            tmp ^= lsb

        color_pairs: list[tuple[frozenset[int], frozenset[int]]] = []

        while start:
            c1: set[int] = set()
            c2: set[int] = set()
            seed = min(start)  # match Java: always pick lowest-index cell first
            self._color_dfs(seed, cand, True, start, c1, c2)
            if c1 and c2:
                color_pairs.append((frozenset(c1), frozenset(c2)))
        return color_pairs

    def _color_dfs(
        self,
        cell: int,
        cand: int,
        on: bool,
        remaining: set[int],
        c1: set[int],
        c2: set[int],
    ) -> None:
        """DFS coloring: assign cell to c1 (on=True) or c2, then recurse."""
        if cell not in remaining:
            return
        remaining.discard(cell)
        (c1 if on else c2).add(cell)
        r, c, b = CONSTRAINTS[cell]
        for unit_idx in (r, 9 + c, 18 + b):
            partner = self._conjugate(cell, cand, unit_idx)
            if partner != -1:
                self._color_dfs(partner, cand, not on, remaining, c1, c2)

    def _conjugate(self, cell: int, cand: int, unit_idx: int) -> int:
        """Return the other cell in a conjugate pair in unit_idx, or -1."""
        grid = self.grid
        if grid.free[unit_idx][cand] != 2:
            return -1
        pair = grid.candidate_sets[cand] & self._unit_mask(unit_idx)
        other = pair & ~(1 << cell)
        if not other:
            return -1
        return other.bit_length() - 1

    def _unit_mask(self, unit_idx: int) -> int:
        """Return 81-bit mask for all cells in unit unit_idx (0-26)."""
        mask = 0
        for cell in ALL_UNITS[unit_idx]:
            mask |= 1 << cell
        return mask

    # ------------------------------------------------------------------
    # Simple Colors
    # ------------------------------------------------------------------

    def _find_simple_colors(self) -> SolutionStep | None:
        """Return the first Simple Colors step (Wrap preferred over Trap)."""
        best: SolutionStep | None = None
        for cand in range(1, 10):
            pairs = self._do_coloring(cand)
            for c1, c2 in pairs:
                # Wrap: two same-color cells see each other → eliminate that color
                step = self._check_wrap(cand, c1, c2)
                if step:
                    return step  # wrap is strong; return immediately

                # Trap: any cell that sees both a c1 and a c2 cell
                step = self._check_trap(cand, c1, c2)
                if step and best is None:
                    best = step
        return best

    def _check_wrap(
        self, cand: int, c1: frozenset[int], c2: frozenset[int]
    ) -> SolutionStep | None:
        grid = self.grid
        elim_mask = 0
        for color, other in ((c1, c2), (c2, c1)):
            color_list = list(color)
            for i in range(len(color_list) - 1):
                for j in range(i + 1, len(color_list)):
                    if BUDDIES[color_list[i]] >> color_list[j] & 1:
                        # This color is wrong — eliminate all of it
                        for cell in color:
                            if grid.candidate_sets[cand] >> cell & 1:
                                elim_mask |= 1 << cell
                        break
                else:
                    continue
                break
        if not elim_mask:
            return None
        step = SolutionStep(SolutionType.SIMPLE_COLORS_WRAP)
        step.add_value(cand)
        self._add_color_candidates(step, c1, cand, 0)
        self._add_color_candidates(step, c2, cand, 1)
        tmp = elim_mask
        while tmp:
            lsb = tmp & -tmp
            step.add_candidate_to_delete(lsb.bit_length() - 1, cand)
            tmp ^= lsb
        return step

    def _check_trap(
        self, cand: int, c1: frozenset[int], c2: frozenset[int]
    ) -> SolutionStep | None:
        grid = self.grid
        # Build union of buddies for each color
        buddies_c1 = 0
        for cell in c1:
            buddies_c1 |= BUDDIES[cell]
        buddies_c2 = 0
        for cell in c2:
            buddies_c2 |= BUDDIES[cell]

        elim_mask = (
            grid.candidate_sets[cand]
            & buddies_c1
            & buddies_c2
        )
        # Remove the coloring cells themselves
        for cell in c1 | c2:
            elim_mask &= ~(1 << cell)

        if not elim_mask:
            return None
        step = SolutionStep(SolutionType.SIMPLE_COLORS_TRAP)
        step.add_value(cand)
        self._add_color_candidates(step, c1, cand, 0)
        self._add_color_candidates(step, c2, cand, 1)
        tmp = elim_mask
        while tmp:
            lsb = tmp & -tmp
            step.add_candidate_to_delete(lsb.bit_length() - 1, cand)
            tmp ^= lsb
        return step

    # ------------------------------------------------------------------
    # Multi-Colors
    # ------------------------------------------------------------------

    def _find_multi_colors(self) -> SolutionStep | None:
        """Return the first Multi-Colors step.

        Mirrors Java: for each (i,j) pair, first try MC2 (accumulating
        eliminations from both a1 and a2), then MC1 (accumulating from
        all 4 pair combinations).  Return on the first non-empty result.
        """
        grid = self.grid
        for cand in range(1, 10):
            pairs = self._do_coloring(cand)
            n = len(pairs)
            for i in range(n):
                for j in range(n):
                    if i == j:
                        continue
                    a1, a2 = pairs[i]
                    b1, b2 = pairs[j]

                    # MC type 2: accumulate eliminations from a1 and a2 that each
                    # see both colors of B.
                    elim_mask = 0
                    if self._set_sees_both(a1, b1, b2):
                        for cell in a1:
                            if grid.candidate_sets[cand] >> cell & 1:
                                elim_mask |= 1 << cell
                    if self._set_sees_both(a2, b1, b2):
                        for cell in a2:
                            if grid.candidate_sets[cand] >> cell & 1:
                                elim_mask |= 1 << cell
                    if elim_mask:
                        elim: set[int] = set()
                        tmp = elim_mask
                        while tmp:
                            lsb = tmp & -tmp
                            elim.add(lsb.bit_length() - 1)
                            tmp ^= lsb
                        return self._make_mc_step(SolutionType.MULTI_COLORS_2, cand, a1, a2, b1, b2, elim)

                    # MC type 1: accumulate eliminations from all 4 pair combinations.
                    elim_mc1: set[int] = set()
                    if self._sets_intersect_buddies(a1, b1):
                        elim_mc1 |= self._trap_elim(cand, a2, b2)
                    if self._sets_intersect_buddies(a1, b2):
                        elim_mc1 |= self._trap_elim(cand, a2, b1)
                    if self._sets_intersect_buddies(a2, b1):
                        elim_mc1 |= self._trap_elim(cand, a1, b2)
                    if self._sets_intersect_buddies(a2, b2):
                        elim_mc1 |= self._trap_elim(cand, a1, b1)
                    if elim_mc1:
                        return self._make_mc_step(SolutionType.MULTI_COLORS_1, cand, a1, a2, b1, b2, elim_mc1)
        return None

    def _set_sees_both(
        self, color: frozenset[int], b1: frozenset[int], b2: frozenset[int]
    ) -> bool:
        """True if the cells in color collectively see at least one cell in b1
        AND at least one cell in b2."""
        sees_b1 = sees_b2 = False
        for cell in color:
            for b in b1:
                if BUDDIES[cell] >> b & 1:
                    sees_b1 = True
                    break
            for b in b2:
                if BUDDIES[cell] >> b & 1:
                    sees_b2 = True
                    break
            if sees_b1 and sees_b2:
                return True
        return False

    def _sets_intersect_buddies(
        self, s1: frozenset[int], s2: frozenset[int]
    ) -> bool:
        """True if any cell in s1 sees any cell in s2."""
        for a in s1:
            for b in s2:
                if BUDDIES[a] >> b & 1:
                    return True
        return False

    def _trap_elim(
        self, cand: int, color_a: frozenset[int], color_b: frozenset[int]
    ) -> set[int]:
        """Cells that see both color_a and color_b (for MC type-1 elim)."""
        grid = self.grid
        buddies_a = 0
        for cell in color_a:
            buddies_a |= BUDDIES[cell]
        buddies_b = 0
        for cell in color_b:
            buddies_b |= BUDDIES[cell]
        elim_mask = grid.candidate_sets[cand] & buddies_a & buddies_b
        for cell in color_a | color_b:
            elim_mask &= ~(1 << cell)
        result: set[int] = set()
        tmp = elim_mask
        while tmp:
            lsb = tmp & -tmp
            result.add(lsb.bit_length() - 1)
            tmp ^= lsb
        return result

    def _cells_with_cand(self, cand: int) -> set[int]:
        result: set[int] = set()
        tmp = self.grid.candidate_sets[cand]
        while tmp:
            lsb = tmp & -tmp
            result.add(lsb.bit_length() - 1)
            tmp ^= lsb
        return result

    def _make_mc_step(
        self,
        sol_type: SolutionType,
        cand: int,
        a1: frozenset[int],
        a2: frozenset[int],
        b1: frozenset[int],
        b2: frozenset[int],
        elim: set[int],
    ) -> SolutionStep:
        step = SolutionStep(sol_type)
        step.add_value(cand)
        self._add_color_candidates(step, a1, cand, 0)
        self._add_color_candidates(step, a2, cand, 1)
        self._add_color_candidates(step, b1, cand, 2)
        self._add_color_candidates(step, b2, cand, 3)
        for cell in sorted(elim):
            step.add_candidate_to_delete(cell, cand)
        return step

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def _add_color_candidates(
        self, step: SolutionStep, color: frozenset[int], cand: int, color_idx: int
    ) -> None:
        """Add all cells in color to step's color_candidates dict."""
        for cell in sorted(color):
            step.color_candidates[cell] = color_idx
