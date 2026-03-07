"""Chain solver: X-Chain, XY-Chain, Remote Pair, Discontinuous/Continuous Nice Loop.

Mirrors Java's ChainSolver.
"""

from __future__ import annotations

from hodoku_py.core.grid import ALL_UNITS, BUDDIES, CELL_CONSTRAINTS, CONSTRAINTS, Grid
from hodoku_py.core.solution_step import SolutionStep
from hodoku_py.core.types import SolutionType

_MAX_CHAIN = 20  # maximum chain length (number of nodes)
_MAX_NL_CHAIN = 20  # maximum chain length for Nice Loop / AIC


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


def _build_nl_links(grid: Grid) -> list[list[tuple[int, bool]]]:
    """Multi-candidate link graph for Nice Loop / AIC.

    Node index: cell * 9 + (cand - 1), cand is 1-indexed.
    Returns links[node] = [(end_node, is_strong), ...].

    Intra-cell links:
      - Bivalue cell: one strong link to the other candidate (same cell).
      - Multi-valued cell: weak links to every other candidate (same cell).
    Inter-cell links (mirrors _build_x_links but for ALL candidates):
      - Strong if the unit contains exactly 2 cells with that digit.
      - Block neighbors that share a row or col with the source are skipped
        (already covered by the row/col link — same dedup as _build_x_links).
    """
    links: list[list[tuple[int, bool]]] = [[] for _ in range(81 * 9)]

    for cell in range(81):
        if grid.values[cell] != 0:
            continue
        cand_list = [d for d in range(1, 10) if grid.candidates[cell] >> (d - 1) & 1]
        if not cand_list:
            continue
        is_bivalue = len(cand_list) == 2
        r_c, c_c, _ = CONSTRAINTS[cell]
        row_u, col_u, blk_u = CELL_CONSTRAINTS[cell]

        for cand in cand_list:
            node = cell * 9 + (cand - 1)

            # Intra-cell links
            if is_bivalue:
                other = cand_list[0] if cand == cand_list[1] else cand_list[1]
                links[node].append((cell * 9 + (other - 1), True))
            else:
                for other in cand_list:
                    if other != cand:
                        links[node].append((cell * 9 + (other - 1), False))

            # Inter-cell links
            for unit_idx in (row_u, col_u, blk_u):
                is_strong = grid.free[unit_idx][cand] == 2
                is_block = unit_idx >= 18
                for nb in ALL_UNITS[unit_idx]:
                    if nb == cell:
                        continue
                    if not (grid.candidate_sets[cand] >> nb & 1):
                        continue
                    if is_block:
                        r_nb, c_nb, _ = CONSTRAINTS[nb]
                        if r_nb == r_c or c_nb == c_c:
                            continue  # already covered by row/col link
                    links[node].append((nb * 9 + (cand - 1), is_strong))

    return links


# ---------------------------------------------------------------------------
# Sort key matching HoDoKu's SolutionStep.compareTo
# ---------------------------------------------------------------------------

def _elim_sort_key(step: SolutionStep) -> int:
    """Weighted index sum used by HoDoKu to order steps with equal elim count.

    Java formula — iterates candidatesToDelete in insertion order (NOT sorted):
        sum += cand.index * offset + cand.value;  offset starts at 1, +=80 each step
    """
    total = 0
    offset = 1
    for c in step.candidates_to_delete:
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
        if sol_type in (
            SolutionType.CONTINUOUS_NICE_LOOP,
            SolutionType.DISCONTINUOUS_NICE_LOOP,
            SolutionType.AIC,
        ):
            return self._find_nice_loop()
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
    # Nice Loop (Discontinuous / Continuous)
    # ------------------------------------------------------------------

    def _find_nice_loop(self) -> SolutionStep | None:
        """Search for DNL, CNL, and AIC steps in one DFS pass; return the global best."""
        grid = self.grid
        links = _build_nl_links(grid)
        deletes_dnl: dict[tuple, tuple[int, SolutionStep]] = {}
        deletes_cnl: dict[tuple, tuple[int, SolutionStep]] = {}
        deletes_aic: dict[tuple, tuple[int, SolutionStep]] = {}

        for start_cell in range(81):
            if grid.values[start_cell] != 0:
                continue
            for start_cand in range(1, 10):
                if not (grid.candidate_sets[start_cand] >> start_cell & 1):
                    continue

                start_node = start_cell * 9 + (start_cand - 1)

                # Try every first link (both strong and weak — unlike X-Chain).
                # The first link's strength is preserved as-is (no downgrade).
                for first_end_node, first_is_strong in links[start_node]:
                    first_end_cell = first_end_node // 9
                    first_end_cand = first_end_node % 9 + 1

                    # Self-link guard
                    if first_end_cell == start_cell and first_end_cand == start_cand:
                        continue

                    chain: list[tuple[int, int]] = [
                        (start_cell, start_cand),
                        (first_end_cell, first_end_cand),
                    ]
                    link_strong: list[bool] = [first_is_strong]
                    # chain_cells: cells already in the chain (for lasso detection).
                    # Starts with {start_cell}; first_end_cell is added when we
                    # recurse deeper from it (matching Java's chainSet.add timing).
                    chain_cells: set[int] = {start_cell}

                    self._dfs_nl(
                        links, chain, link_strong, chain_cells,
                        strong_only=not first_is_strong,
                        start_cell=start_cell,
                        start_cand=start_cand,
                        deletes_dnl=deletes_dnl,
                        deletes_cnl=deletes_cnl,
                        deletes_aic=deletes_aic,
                    )

        # DNL, CNL, and AIC all compete; return the best.
        # (CONTINUOUS_NICE_LOOP is the single SOLVER_STEPS trigger for all NL types.)
        all_steps = (
            [step for _, step in deletes_dnl.values()]
            + [step for _, step in deletes_cnl.values()]
            + [step for _, step in deletes_aic.values()]
        )
        if not all_steps:
            return None
        all_steps.sort(key=_step_sort_key)
        return all_steps[0]

    def _dfs_nl(
        self,
        links: list[list[tuple[int, bool]]],
        chain: list[tuple[int, int]],
        link_strong: list[bool],
        chain_cells: set[int],
        strong_only: bool,
        start_cell: int,
        start_cand: int,
        deletes_dnl: dict,
        deletes_cnl: dict,
        deletes_aic: dict,
    ) -> None:
        """DFS over the NL link graph.

        chain[k] = (cell, cand) node; link_strong[k] = strength of the link
        FROM chain[k] TO chain[k+1] (for k >= 0).

        chain_cells mirrors Java's chainSet: contains start_cell and all cells
        visited before the current tail.  A link back to any cell in chain_cells
        is a lasso (skip) unless that cell is start_cell (a loop — check it).
        """
        if len(chain) >= _MAX_NL_CHAIN:
            return

        current_cell, current_cand = chain[-1]
        current_node = current_cell * 9 + (current_cand - 1)

        for end_node, link_is_strong in links[current_node]:
            if strong_only and not link_is_strong:
                continue

            end_cell = end_node // 9
            end_cand = end_node % 9 + 1

            # Self-link guard
            if end_cell == current_cell and end_cand == current_cand:
                continue

            # Loop / lasso detection
            is_loop = False
            if end_cell in chain_cells:
                if end_cell != start_cell:
                    continue  # lasso: hits a middle cell
                is_loop = True

            # Downgrade: strong link in a weak position is recorded as weak.
            # Matches Java: if (!entry.strongOnly && newLinkIsStrong) downgrade.
            effective_strong = link_is_strong and strong_only

            # Add current cell to visited before going deeper (Java: chainSet.add).
            added = current_cell not in chain_cells
            chain_cells.add(current_cell)

            if is_loop:
                # Minimum 3 links: chain has start + >=2 intermediates.
                if len(chain) >= 3:
                    self._check_nice_loop(
                        chain, link_strong,
                        close_strong=effective_strong,
                        close_cand=end_cand,
                        start_cell=start_cell,
                        start_cand=start_cand,
                        deletes_dnl=deletes_dnl,
                        deletes_cnl=deletes_cnl,
                    )
                # Don't recurse past a loop (Java: entry.aktIndex = entry.endIndex).
            else:
                # AIC check: open chain ending with a strong link.
                # Mirrors TablingSolver.checkAics(offTable): the chain must start
                # with a strong first link (link_strong[0]=True = off-table, start OFF)
                # and the current link must be strong (end node is ON).
                # Minimum distance of 3 links: len(chain) >= 3 before appending.
                if effective_strong and len(chain) >= 3 and link_strong[0]:
                    self._check_aic(
                        start_cell, start_cand, end_cell, end_cand,
                        chain, deletes_aic,
                    )

                chain.append((end_cell, end_cand))
                link_strong.append(effective_strong)

                self._dfs_nl(
                    links, chain, link_strong, chain_cells,
                    strong_only=not effective_strong,
                    start_cell=start_cell,
                    start_cand=start_cand,
                    deletes_dnl=deletes_dnl,
                    deletes_cnl=deletes_cnl,
                    deletes_aic=deletes_aic,
                )

                link_strong.pop()
                chain.pop()

            if added:
                chain_cells.discard(current_cell)

    def _check_nice_loop(
        self,
        chain: list[tuple[int, int]],
        link_strong: list[bool],
        close_strong: bool,
        close_cand: int,
        start_cell: int,
        start_cand: int,
        deletes_dnl: dict,
        deletes_cnl: dict,
    ) -> None:
        """Classify and record a Nice Loop.

        chain[0] = (start_cell, start_cand); chain[1:] are intermediate nodes.
        link_strong[k] = strength of link from chain[k] to chain[k+1].
        close_strong / close_cand describe the loop-closing link back to start_cell.

        Mirrors Java's checkNiceLoop() in ChainSolver.java.
        """
        grid = self.grid
        first_strong = link_strong[0]   # strength of first link out of start
        last_strong = close_strong       # strength of loop-closing link
        sc = start_cand
        ec = close_cand

        step = SolutionStep(SolutionType.DISCONTINUOUS_NICE_LOOP)  # default; may change

        if not first_strong and not last_strong and sc == ec:
            # DNL case 1: both links weak, same candidate → delete sc from start
            step.add_candidate_to_delete(start_cell, sc)

        elif first_strong and last_strong and sc == ec:
            # DNL case 2: both links strong, same candidate → set sc (delete others)
            for d in range(1, 10):
                if d != sc and grid.candidate_sets[d] >> start_cell & 1:
                    step.add_candidate_to_delete(start_cell, d)

        elif first_strong != last_strong and sc != ec:
            # DNL case 3: one strong, one weak, different candidates →
            # delete the candidate carried by the weak link
            if not first_strong:
                step.add_candidate_to_delete(start_cell, sc)   # first link is weak
            else:
                step.add_candidate_to_delete(start_cell, ec)   # last link is weak

        elif (
            (not first_strong and not last_strong
             and grid.candidates[start_cell].bit_count() == 2
             and sc != ec)
            or (first_strong and last_strong and sc != ec)
            or (first_strong != last_strong and sc == ec)
        ):
            # CNL: two-pass elimination
            step = SolutionStep(SolutionType.CONTINUOUS_NICE_LOOP)

            # Build the full loop as parallel arrays for easy indexed access.
            # full_nodes[k] = chain[k] for k<len(chain), then (start_cell, ec).
            # full_strong[k] = strength of link from full_nodes[k] to full_nodes[k+1].
            full_nodes: list[tuple[int, int]] = chain + [(start_cell, ec)]
            full_strong: list[bool] = link_strong + [close_strong]
            n = len(full_nodes)

            # Mask of all cells in the loop (used to exclude them from buddy elims).
            chain_mask = 0
            for cell, _ in chain:
                chain_mask |= 1 << cell

            # Pass 1: cell entered AND exited via strong inter-cell links with a
            # weak intra-cell link in between → delete all OTHER candidates from it.
            # Added in chain-traversal order, ascending digit within each cell
            # (matches Java's SudokuSet.getAllCandidates() ascending output).
            for i in range(1, n - 2):  # need chain[i], [i+1], [i+2] all valid
                if (full_strong[i - 1]                           # strong arrival at [i]
                        and full_nodes[i - 1][0] != full_nodes[i][0]  # inter-cell
                        and not full_strong[i]                   # weak link [i]→[i+1]
                        and full_nodes[i][0] == full_nodes[i + 1][0]  # intra-cell
                        and full_strong[i + 1]                   # strong departure
                        and full_nodes[i + 1][0] != full_nodes[i + 2][0]):
                    c1 = full_nodes[i][1]
                    c2 = full_nodes[i + 2][1]
                    cell = full_nodes[i][0]
                    for d in range(1, 10):
                        if d != c1 and d != c2 and grid.candidate_sets[d] >> cell & 1:
                            step.add_candidate_to_delete(cell, d)

            # Pass 2: weak inter-cell link → eliminate that candidate from all
            # cells that see both endpoints (excluding chain cells).
            # Added in chain-traversal order, ascending cell-index within each link
            # (matches Java's SudokuSet iterator which yields ascending indices).
            for i in range(1, n):
                if (not full_strong[i - 1]                            # weak link
                        and full_nodes[i - 1][0] != full_nodes[i][0]):  # inter-cell
                    shared = (
                        BUDDIES[full_nodes[i - 1][0]]
                        & BUDDIES[full_nodes[i][0]]
                        & grid.candidate_sets[full_nodes[i][1]]
                        & ~chain_mask
                    )
                    tmp = shared
                    while tmp:
                        lsb = tmp & -tmp
                        step.add_candidate_to_delete(lsb.bit_length() - 1, full_nodes[i][1])
                        tmp ^= lsb
        else:
            return  # no valid loop type

        if not step.candidates_to_delete:
            return

        # Record chain cells as indices.
        for cell, _ in chain:
            step.add_index(cell)

        key = tuple(sorted((c.index, c.value) for c in step.candidates_to_delete))
        dmap = deletes_dnl if step.type == SolutionType.DISCONTINUOUS_NICE_LOOP else deletes_cnl
        old = dmap.get(key)
        if old is None or old[0] > len(chain):
            dmap[key] = (len(chain), step)

    def _check_aic(
        self,
        start_cell: int,
        start_cand: int,
        end_cell: int,
        end_cand: int,
        chain: list[tuple[int, int]],
        deletes_aic: dict,
    ) -> None:
        """Record an AIC step if eliminations exist.

        Mirrors TablingSolver.checkAic():
          Type 1 (start_cand == end_cand): eliminate start_cand from all cells
            that see both start_cell and end_cell (at least 2 such cells in Java's
            inclusive-buddy view; with our exclusive-buddy BUDDIES, any non-empty set).
          Type 2 (different candidates, end_cell sees start_cell): eliminate
            end_cand from start_cell and start_cand from end_cell.
        """
        grid = self.grid
        step = SolutionStep(SolutionType.AIC)

        if start_cand == end_cand:
            # Type 1: any cell seeing both endpoints can't have start_cand.
            elim = BUDDIES[start_cell] & BUDDIES[end_cell] & grid.candidate_sets[start_cand]
            if not elim:
                return
            tmp = elim
            while tmp:
                lsb = tmp & -tmp
                step.add_candidate_to_delete(lsb.bit_length() - 1, start_cand)
                tmp ^= lsb
        else:
            # Type 2: end_cell must see start_cell; eliminate cross-candidates.
            if not (BUDDIES[start_cell] >> end_cell & 1):
                return
            # Add in ascending cell-index order for HoDoKu compatibility.
            cells = sorted([
                (start_cell, end_cand) if grid.candidate_sets[end_cand] >> start_cell & 1 else None,
                (end_cell, start_cand) if grid.candidate_sets[start_cand] >> end_cell & 1 else None,
            ], key=lambda x: x[0] if x else 999)
            for item in cells:
                if item is not None:
                    step.add_candidate_to_delete(item[0], item[1])
            if not step.candidates_to_delete:
                return

        # Chain indices: all nodes in chain plus the AIC endpoint.
        for cell, _ in chain:
            step.add_index(cell)
        step.add_index(end_cell)

        key = tuple(sorted((c.index, c.value) for c in step.candidates_to_delete))
        old = deletes_aic.get(key)
        if old is None or old[0] > len(chain):
            deletes_aic[key] = (len(chain), step)

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
