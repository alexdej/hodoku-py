"""Wing pattern solver: W-Wing, XY-Wing, XYZ-Wing.

Mirrors Java's WingSolver.
"""

from __future__ import annotations

from hodoku_py.core.grid import BUDDIES, CONSTRAINTS, Grid
from hodoku_py.core.solution_step import Candidate, SolutionStep
from hodoku_py.core.types import SolutionType


class WingSolver:
    """W-Wing, XY-Wing, XYZ-Wing."""

    def __init__(self, grid: Grid) -> None:
        self.grid = grid

    def get_step(self, sol_type: SolutionType) -> SolutionStep | None:
        if sol_type == SolutionType.W_WING:
            return self._find_w_wing()
        if sol_type == SolutionType.XY_WING:
            return self._find_xy_wing()
        if sol_type == SolutionType.XYZ_WING:
            return self._find_xyz_wing()
        return None

    # ------------------------------------------------------------------
    # XY-Wing / XYZ-Wing shared logic
    # ------------------------------------------------------------------

    def _find_xy_wing(self) -> SolutionStep | None:
        return self._find_wing(xyz=False)

    def _find_xyz_wing(self) -> SolutionStep | None:
        return self._find_wing(xyz=True)

    def _find_wing(self, xyz: bool) -> SolutionStep | None:
        """Search for XY-Wing (xyz=False) or XYZ-Wing (xyz=True).

        Logic mirrors WingSolver.getWing():
        - Collect bivalue cells (candidate count == 2) and optionally trivalue.
        - For XY-Wing:  try each bivalue cell as pivot, two others as pincers.
        - For XYZ-Wing: try each trivalue cell as pivot, two bivalue pincers.
        - All three cells together must span exactly 3 distinct candidates.
        - Pivot must see both pincers.
        - Pincers share exactly one candidate z.
        - Eliminate z from cells that see both pincers (and pivot for XYZ).
        """
        grid = self.grid
        bi_cells: list[int] = []
        tri_cells: list[int] = []
        for i in range(81):
            if grid.values[i] != 0:
                continue
            n = bin(grid.candidates[i]).count("1")
            if n == 2:
                bi_cells.append(i)
            elif xyz and n == 3:
                tri_cells.append(i)

        pivot_list = tri_cells if xyz else bi_cells

        for pi, pivot in enumerate(pivot_list):
            pivot_mask = grid.candidates[pivot]
            for ji, j_cell in enumerate(bi_cells):
                if xyz and j_cell == pivot:
                    continue
                if not xyz and ji <= pi:
                    continue  # avoid duplicate (pivot, j) pairs for XY
                j_mask = grid.candidates[j_cell]
                if bin(pivot_mask | j_mask).count("1") != 3:
                    continue  # can't form a 3-candidate wing
                k_start = ji + 1
                for k_cell in bi_cells[k_start:]:
                    if k_cell == pivot:
                        continue
                    k_mask = grid.candidates[k_cell]
                    if bin(pivot_mask | j_mask | k_mask).count("1") != 3:
                        continue
                    # No two cells may have identical candidate sets
                    if pivot_mask == j_mask or j_mask == k_mask or k_mask == pivot_mask:
                        continue

                    # For XY-Wing, try all 3 rotations (each cell as pivot)
                    candidates_for_pivot = [(pivot, j_cell, k_cell)]
                    if not xyz:
                        candidates_for_pivot += [
                            (j_cell, pivot, k_cell),
                            (k_cell, j_cell, pivot),
                        ]

                    for idx1, idx2, idx3 in candidates_for_pivot:
                        step = self._check_wing(idx1, idx2, idx3, xyz)
                        if step:
                            return step
        return None

    def _check_wing(
        self, pivot: int, pincer1: int, pincer2: int, xyz: bool
    ) -> SolutionStep | None:
        """Check if (pivot, pincer1, pincer2) form a valid wing and return step."""
        grid = self.grid
        # Pivot must see both pincers
        if not (BUDDIES[pivot] >> pincer1 & 1) or not (BUDDIES[pivot] >> pincer2 & 1):
            return None

        p1_mask = grid.candidates[pincer1]
        p2_mask = grid.candidates[pincer2]
        shared = p1_mask & p2_mask
        if bin(shared).count("1") != 1:
            return None  # pincers must share exactly one candidate z

        cand_z = shared.bit_length()  # digit (1-9)

        # Cells to eliminate from: see both pincers (and pivot for XYZ)
        elim_set = grid.candidate_sets[cand_z] & BUDDIES[pincer1] & BUDDIES[pincer2]
        if xyz:
            elim_set &= BUDDIES[pivot]
        # Remove the wing cells themselves
        elim_set &= ~((1 << pivot) | (1 << pincer1) | (1 << pincer2))
        if not elim_set:
            return None

        sol_type = SolutionType.XYZ_WING if xyz else SolutionType.XY_WING
        step = SolutionStep(sol_type)

        pivot_mask = grid.candidates[pivot]
        # Values stored: the three candidates of the pivot cell
        for bit in range(1, 10):
            if pivot_mask >> (bit - 1) & 1:
                step.add_value(bit)
        if not xyz:
            # XY-Wing stores only z as third value (HoDoKu convention)
            # Rewrite: values = [x, y, z] where pivot={x,y}, pincer1={x,z}, pincer2={y,z}
            # The third value recorded is cand_z (already last if pivot={x,y})
            pass  # pivot_mask has 2 bits; cand_z is implicitly recorded via fins

        step.add_index(pivot)
        step.add_index(pincer1)
        step.add_index(pincer2)

        # Fins: pincers carry z; pivot also carries z for XYZ
        if xyz:
            step.fins.append(Candidate(pivot, cand_z))
        step.fins.append(Candidate(pincer1, cand_z))
        step.fins.append(Candidate(pincer2, cand_z))

        tmp = elim_set
        while tmp:
            lsb = tmp & -tmp
            step.add_candidate_to_delete(lsb.bit_length() - 1, cand_z)
            tmp ^= lsb
        return step

    # ------------------------------------------------------------------
    # W-Wing
    # ------------------------------------------------------------------

    def _find_w_wing(self) -> SolutionStep | None:
        """Find the first W-Wing elimination.

        Two bivalue cells with identical candidates {a, b}.
        A strong link on b connects them (one end sees cell1, the other sees cell2).
        Eliminate a from all cells that see both bivalue cells.
        """
        grid = self.grid
        bi_cells: list[int] = []
        for i in range(81):
            if grid.values[i] == 0 and bin(grid.candidates[i]).count("1") == 2:
                bi_cells.append(i)

        for ii, i in enumerate(bi_cells):
            cell_i = grid.candidates[i]
            # Extract the two digits from the bitmask
            bits = [b + 1 for b in range(9) if cell_i >> b & 1]
            cand_a, cand_b = bits[0], bits[1]

            # Pre-compute peers of i that carry cand_a / cand_b
            peers_a = grid.candidate_sets[cand_a] & BUDDIES[i]
            peers_b = grid.candidate_sets[cand_b] & BUDDIES[i]

            for j in bi_cells[ii + 1:]:
                if grid.candidates[j] != cell_i:
                    continue  # must have identical candidate sets

                # Potential eliminations of cand_a: cells seeing both i and j
                elim_a = peers_a & BUDDIES[j]
                if elim_a:
                    step = self._check_w_link(cand_a, cand_b, i, j, elim_a)
                    if step:
                        return step

                # Potential eliminations of cand_b: cells seeing both i and j
                elim_b = peers_b & BUDDIES[j]
                if elim_b:
                    step = self._check_w_link(cand_b, cand_a, i, j, elim_b)
                    if step:
                        return step

        return None

    def _check_w_link(
        self,
        cand_elim: int,
        cand_link: int,
        idx1: int,
        idx2: int,
        elim_set: int,
    ) -> SolutionStep | None:
        """Find a strong link on cand_link that bridges idx1 and idx2.

        The strong link must have one end seeing idx1 and the other seeing idx2.
        A single end cannot see BOTH idx1 and idx2 (forbidden by HoDoKu).
        """
        grid = self.grid
        # Scan all 27 constraints for a strong link on cand_link
        for constr in range(27):
            if grid.free[constr][cand_link] != 2:
                continue
            # Find the two cells in this unit with cand_link
            link_cells: list[int] = []
            for cell in self._unit_cells(constr):
                if cell != idx1 and cell != idx2 and grid.candidate_sets[cand_link] >> cell & 1:
                    link_cells.append(cell)
                    if len(link_cells) == 2:
                        break
            if len(link_cells) != 2:
                continue

            w1, w2 = link_cells
            # One must see idx1, the other idx2; neither may see BOTH
            w1_sees1 = bool(BUDDIES[w1] >> idx1 & 1)
            w1_sees2 = bool(BUDDIES[w1] >> idx2 & 1)
            w2_sees1 = bool(BUDDIES[w2] >> idx1 & 1)
            w2_sees2 = bool(BUDDIES[w2] >> idx2 & 1)

            if w1_sees1 and w1_sees2:
                continue  # forbidden
            if w2_sees1 and w2_sees2:
                continue  # forbidden

            if w1_sees1 and w2_sees2:
                pass  # w1→idx1, w2→idx2
            elif w1_sees2 and w2_sees1:
                w1, w2 = w2, w1  # swap so w1→idx1
            else:
                continue  # no valid bridge

            # Valid W-Wing!
            step = SolutionStep(SolutionType.W_WING)
            step.add_value(cand_elim)
            step.add_value(cand_link)
            step.add_index(idx1)
            step.add_index(idx2)
            step.fins.append(Candidate(idx1, cand_link))
            step.fins.append(Candidate(idx2, cand_link))
            step.fins.append(Candidate(w1, cand_link))
            step.fins.append(Candidate(w2, cand_link))

            tmp = elim_set
            while tmp:
                lsb = tmp & -tmp
                step.add_candidate_to_delete(lsb.bit_length() - 1, cand_elim)
                tmp ^= lsb
            return step

        return None

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _unit_cells(self, constr: int) -> list[int]:
        """Return all cell indices in constraint unit constr (0-26)."""
        from hodoku_py.core.grid import ALL_UNITS  # avoid circular at module level
        return list(ALL_UNITS[constr])
