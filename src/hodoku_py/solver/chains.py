"""Chain solver: X-Chain, XY-Chain, Remote Pair.

Mirrors Java's ChainSolver (simple chains only).
Nice Loop / AIC are handled by TablingSolver (not yet implemented).
"""

from __future__ import annotations

from hodoku_py.core.grid import ALL_UNITS, BUDDIES, CELL_CONSTRAINTS, CONSTRAINTS, Grid
from hodoku_py.core.solution_step import SolutionStep
from hodoku_py.core.types import SolutionType

_MAX_CHAIN = 20  # maximum chain length (number of nodes)


# ---------------------------------------------------------------------------
# Link building
# ---------------------------------------------------------------------------

def _build_x_links(grid: Grid, digit: int) -> list[list[tuple[int, bool]]]:
    """Return links[cell] = [(neighbor, is_strong), ...] for one digit.

    Strong link: the unit has exactly 2 candidates for this digit.
    Block neighbors that also share a row or col with the source cell are
    skipped — the row/col link already covers them (mirrors Java's constr==2
    deduplication in getAllLinks).
    """
    cand_set = grid.candidate_sets[digit]
    links: list[list[tuple[int, bool]]] = [[] for _ in range(81)]

    for cell in range(81):
        if not (cand_set >> cell & 1):
            continue
        r_c, c_c, _ = CONSTRAINTS[cell]
        row_u, col_u, blk_u = CELL_CONSTRAINTS[cell]

        for unit_idx in (row_u, col_u, blk_u):
            is_strong = grid.free[unit_idx][digit] == 2
            is_block = unit_idx >= 18
            for nb in ALL_UNITS[unit_idx]:
                if nb == cell:
                    continue
                if not (cand_set >> nb & 1):
                    continue
                if is_block:
                    r_nb, c_nb, _ = CONSTRAINTS[nb]
                    if r_nb == r_c or c_nb == c_c:
                        continue  # already covered by row/col link
                links[cell].append((nb, is_strong))

    return links


# ---------------------------------------------------------------------------
# Sort key matching HoDoKu's SolutionStep.compareTo
# ---------------------------------------------------------------------------

def _elim_sort_key(step: SolutionStep) -> int:
    """Weighted index sum used by HoDoKu to order steps with equal elim count.

    Java formula (candidatesToDelete sorted by index):
        sum += cand.index * offset + cand.value;  offset starts at 1, +=80 each step
    """
    total = 0
    offset = 1
    for c in sorted(step.candidates_to_delete, key=lambda x: (x.index, x.value)):
        total += c.index * offset + c.value
        offset += 80
    return total


def _step_sort_key(step: SolutionStep) -> tuple:
    return (-len(step.candidates_to_delete), _elim_sort_key(step))


# ---------------------------------------------------------------------------
# Solver
# ---------------------------------------------------------------------------

class ChainSolver:
    """X-Chain, XY-Chain, Remote Pair."""

    def __init__(self, grid: Grid) -> None:
        self.grid = grid

    def get_step(self, sol_type: SolutionType) -> SolutionStep | None:
        if sol_type == SolutionType.TURBOT_FISH:
            return self._find_turbot_fish()
        if sol_type == SolutionType.X_CHAIN:
            return self._find_x_chain()
        if sol_type == SolutionType.XY_CHAIN:
            return self._find_xy_chain()
        if sol_type == SolutionType.REMOTE_PAIR:
            return self._find_remote_pair()
        return None

    # ------------------------------------------------------------------
    # Turbot Fish (X-Chain restricted to 3 links / 4 nodes)
    # ------------------------------------------------------------------

    def _find_turbot_fish(self) -> SolutionStep | None:
        """Find the best Turbot Fish (X-Chain with at most 3 links)."""
        return self._find_x_chain_impl(SolutionType.TURBOT_FISH, max_nodes=4)

    # ------------------------------------------------------------------
    # X-Chain
    # ------------------------------------------------------------------

    def _find_x_chain(self) -> SolutionStep | None:
        """Find the best X-Chain elimination.

        Collects all valid chains, deduplicates by elimination set (keeping
        shortest per set), then returns the one ranked first by HoDoKu's
        comparator (most eliminations, then lowest weighted index sum).
        """
        return self._find_x_chain_impl(SolutionType.X_CHAIN, max_nodes=_MAX_CHAIN)

    def _find_x_chain_impl(self, sol_type: SolutionType, max_nodes: int) -> SolutionStep | None:
        grid = self.grid
        # elim_key → (chain_length, step): shortest chain per elimination set
        deletes_map: dict[tuple, tuple[int, SolutionStep]] = {}

        for digit in range(1, 10):
            cand_set = grid.candidate_sets[digit]
            if not cand_set:
                continue

            links = _build_x_links(grid, digit)

            tmp = cand_set
            while tmp:
                lsb = tmp & -tmp
                start = lsb.bit_length() - 1
                tmp ^= lsb

                start_buddies = grid.candidate_sets[digit] & BUDDIES[start]
                if not start_buddies:
                    continue

                for nb, is_strong in links[start]:
                    if not is_strong:
                        continue  # X-Chain must start with a strong link

                    chain: list[int] = [start, nb]
                    chain_set: set[int] = {nb}  # tracks chain[1:] for lasso check

                    self._dfs_x(
                        digit, links, chain, chain_set,
                        strong_only=False,  # just placed a strong link; next: weak
                        start=start,
                        start_buddies=start_buddies,
                        deletes_map=deletes_map,
                        sol_type=sol_type,
                        max_nodes=max_nodes,
                    )

        if not deletes_map:
            return None

        steps = [step for _, step in deletes_map.values()]
        steps.sort(key=_step_sort_key)
        return steps[0]

    def _dfs_x(
        self,
        digit: int,
        links: list[list[tuple[int, bool]]],
        chain: list[int],
        chain_set: set[int],
        strong_only: bool,
        start: int,
        start_buddies: int,
        deletes_map: dict,
        sol_type: SolutionType = SolutionType.X_CHAIN,
        max_nodes: int = _MAX_CHAIN,
    ) -> None:
        if len(chain) >= max_nodes:
            return

        current = chain[-1]

        for nb, link_is_strong in links[current]:
            if strong_only and not link_is_strong:
                continue  # must use strong link here

            if nb == start:
                continue  # nice loop — not an X-Chain
            if nb in chain_set:
                continue  # lasso: revisiting a middle cell

            # When !strong_only: a strong link is treated as weak (no chain check).
            effective_strong = link_is_strong and strong_only

            chain.append(nb)
            chain_set.add(nb)

            # Valid chain end: ended on a strong link, at least 3 nodes total.
            if effective_strong and len(chain) > 2:
                elim = start_buddies & BUDDIES[nb]
                if elim:
                    self._record(digit, sol_type, chain, elim, deletes_map)

            self._dfs_x(
                digit, links, chain, chain_set,
                strong_only=not strong_only,
                start=start,
                start_buddies=start_buddies,
                deletes_map=deletes_map,
                sol_type=sol_type,
                max_nodes=max_nodes,
            )

            chain.pop()
            chain_set.discard(nb)

    # ------------------------------------------------------------------
    # XY-Chain
    # ------------------------------------------------------------------

    def _find_xy_chain(self) -> SolutionStep | None:
        return self._find_xy_type(SolutionType.XY_CHAIN)

    # ------------------------------------------------------------------
    # Remote Pair
    # ------------------------------------------------------------------

    def _find_remote_pair(self) -> SolutionStep | None:
        return self._find_xy_type(SolutionType.REMOTE_PAIR)

    # ------------------------------------------------------------------
    # Shared XY/RP search
    # ------------------------------------------------------------------

    def _find_xy_type(self, sol_type: SolutionType) -> SolutionStep | None:
        """Find the best XY-Chain or Remote Pair.

        XY-Chain: all cells bivalue; strong link = within-cell, weak = inter-cell.
        Remote Pair: like XY-Chain but all cells must share identical candidate pair;
                     minimum 4 cells (8 chain nodes).
        """
        grid = self.grid
        is_rp = sol_type == SolutionType.REMOTE_PAIR
        deletes_map: dict[tuple, tuple[int, SolutionStep]] = {}

        for start in range(81):
            if grid.values[start] != 0:
                continue
            # Both XY-Chain and RP require bivalue start cell
            cands = [d for d in range(1, 10) if grid.candidate_sets[d] >> start & 1]
            if len(cands) != 2:
                continue
            start_mask = grid.candidates[start]  # 9-bit candidate mask for RP matching

            d1, d2 = cands[0], cands[1]

            for start_cand, other_cand in ((d1, d2), (d2, d1)):
                start_buddies = grid.candidate_sets[start_cand] & BUDDIES[start]
                if not start_buddies:
                    continue
                if is_rp:
                    start_buddies2 = grid.candidate_sets[other_cand] & BUDDIES[start]

                # chain stores (cell, candidate) pairs
                chain: list[tuple[int, int]] = [(start, start_cand), (start, other_cand)]
                visited: set[int] = {start}

                self._dfs_xy(
                    grid, chain, visited,
                    strong_only=False,  # just used within-cell strong; next: inter-cell
                    start=start,
                    start_cand=start_cand,
                    start_buddies=start_buddies,
                    start_buddies2=start_buddies2 if is_rp else 0,
                    start_mask=start_mask,
                    sol_type=sol_type,
                    deletes_map=deletes_map,
                )

        if not deletes_map:
            return None

        steps = [step for _, step in deletes_map.values()]
        steps.sort(key=_step_sort_key)
        return steps[0]

    def _dfs_xy(
        self,
        grid: Grid,
        chain: list[tuple[int, int]],
        visited: set[int],
        strong_only: bool,
        start: int,
        start_cand: int,
        start_buddies: int,
        start_buddies2: int,
        start_mask: int,
        sol_type: SolutionType,
        deletes_map: dict,
    ) -> None:
        if len(chain) >= _MAX_CHAIN:
            return

        current_cell, current_cand = chain[-1]
        is_rp = sol_type == SolutionType.REMOTE_PAIR

        if strong_only:
            # Within-cell strong link: move to the other candidate in current_cell.
            # (bivalue cell guaranteed — current_cell is always bivalue for XY/RP)
            other_cand = next(
                d for d in range(1, 10)
                if d != current_cand and grid.candidate_sets[d] >> current_cell & 1
            )

            chain.append((current_cell, other_cand))

            # Check: valid chain end when other_cand == start_cand and len > 2
            # (mirrors: stackLevel > 1 && newLinkIsStrong && newLinkCandidate == startCandidate)
            if other_cand == start_cand and len(chain) > 2:
                if is_rp and len(chain) >= 8:
                    self._check_rp(chain, start_cand, start_buddies, start_buddies2, deletes_map)
                elif not is_rp:
                    elim = start_buddies & BUDDIES[current_cell]
                    if elim:
                        self._record_xy(start_cand, chain, elim, deletes_map)

            self._dfs_xy(
                grid, chain, visited, strong_only=False,
                start=start, start_cand=start_cand,
                start_buddies=start_buddies, start_buddies2=start_buddies2,
                start_mask=start_mask, sol_type=sol_type, deletes_map=deletes_map,
            )
            chain.pop()

        else:
            # Inter-cell weak link: move to another bivalue cell with current_cand.
            r_c, c_c, _ = CONSTRAINTS[current_cell]
            row_u, col_u, blk_u = CELL_CONSTRAINTS[current_cell]
            cand_set = grid.candidate_sets[current_cand]

            for unit_idx in (row_u, col_u, blk_u):
                is_block = unit_idx >= 18
                for nb in ALL_UNITS[unit_idx]:
                    if nb == current_cell:
                        continue
                    if not (cand_set >> nb & 1):
                        continue
                    # Must be bivalue
                    if grid.candidates[nb].bit_count() != 2:
                        continue
                    # Remote Pair: must have same two candidates
                    if is_rp and grid.candidates[nb] != start_mask:
                        continue
                    # Block dedup: skip if also connected via row/col
                    if is_block:
                        r_nb, c_nb, _ = CONSTRAINTS[nb]
                        if r_nb == r_c or c_nb == c_c:
                            continue
                    if nb == start:
                        continue  # nice loop
                    if nb in visited:
                        continue  # lasso

                    chain.append((nb, current_cand))
                    visited.add(nb)

                    self._dfs_xy(
                        grid, chain, visited, strong_only=True,
                        start=start, start_cand=start_cand,
                        start_buddies=start_buddies, start_buddies2=start_buddies2,
                        start_mask=start_mask, sol_type=sol_type, deletes_map=deletes_map,
                    )

                    chain.pop()
                    visited.discard(nb)

    def _check_rp(
        self,
        chain: list[tuple[int, int]],
        start_cand: int,
        start_buddies: int,
        start_buddies2: int,
        deletes_map: dict,
    ) -> None:
        """Record a Remote Pair step. Eliminates both candidates from shared buddies."""
        # For a 4-cell chain (len=8): check start cell vs end cell only.
        # For longer chains: also check all pairs of cells with opposite polarity.
        # Positions in chain: 0,1 = cell0; 2,3 = cell1; 4,5 = cell2; ...
        # Even node-pair indices (0,2,4,...) are the "entry" candidates.
        # Pairs with opposite polarity: i and j where (j-i) ≡ 2 (mod 4) and j-i >= 6.
        step = SolutionStep(SolutionType.REMOTE_PAIR)
        start_cell = chain[0][0]
        other_cand = chain[1][1]  # the other start candidate

        step.add_value(start_cand)
        step.add_value(other_cand)

        n = len(chain)
        elim1_mask = 0
        elim2_mask = 0
        cand_set1 = self.grid.candidate_sets[start_cand]
        cand_set2 = self.grid.candidate_sets[other_cand]
        for i in range(0, n, 2):
            cell_i = chain[i][0]
            for j in range(i + 6, n, 4):
                cell_j = chain[j][0]
                shared = BUDDIES[cell_i] & BUDDIES[cell_j]
                elim1_mask |= shared & cand_set1
                elim2_mask |= shared & cand_set2

        if not elim1_mask and not elim2_mask:
            return

        tmp = elim1_mask
        while tmp:
            lsb = tmp & -tmp
            step.add_candidate_to_delete(lsb.bit_length() - 1, start_cand)
            tmp ^= lsb
        tmp = elim2_mask
        while tmp:
            lsb = tmp & -tmp
            step.add_candidate_to_delete(lsb.bit_length() - 1, other_cand)
            tmp ^= lsb

        for cell, _ in chain:
            step.add_index(cell)

        key = tuple(sorted((c.index, c.value) for c in step.candidates_to_delete))
        old = deletes_map.get(key)
        if old is None or old[0] > len(chain):
            deletes_map[key] = (len(chain), step)

    def _record_xy(
        self,
        digit: int,
        chain: list[tuple[int, int]],
        elim_mask: int,
        deletes_map: dict,
    ) -> None:
        """Build an XY-Chain step and store if shortest for its elimination set."""
        step = SolutionStep(SolutionType.XY_CHAIN)
        step.add_value(digit)
        tmp = elim_mask
        while tmp:
            lsb = tmp & -tmp
            step.add_candidate_to_delete(lsb.bit_length() - 1, digit)
            tmp ^= lsb
        for cell, _ in chain:
            step.add_index(cell)

        key = tuple(sorted((c.index, c.value) for c in step.candidates_to_delete))
        old = deletes_map.get(key)
        if old is None or old[0] > len(chain):
            deletes_map[key] = (len(chain), step)

    # ------------------------------------------------------------------
    # Shared helper
    # ------------------------------------------------------------------

    def _record(
        self,
        digit: int,
        sol_type: SolutionType,
        chain: list[int],
        elim_mask: int,
        deletes_map: dict,
    ) -> None:
        """Build a step and store it if it's the shortest for its elimination set."""
        step = SolutionStep(sol_type)
        step.add_value(digit)
        tmp = elim_mask
        while tmp:
            lsb = tmp & -tmp
            step.add_candidate_to_delete(lsb.bit_length() - 1, digit)
            tmp ^= lsb
        for cell in chain:
            step.add_index(cell)

        key = tuple(sorted((c.index, c.value) for c in step.candidates_to_delete))
        old = deletes_map.get(key)
        if old is None or old[0] > len(chain):
            deletes_map[key] = (len(chain), step)
