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
    """X-Chain (more chain types to be added here)."""

    def __init__(self, grid: Grid) -> None:
        self.grid = grid

    def get_step(self, sol_type: SolutionType) -> SolutionStep | None:
        if sol_type == SolutionType.X_CHAIN:
            return self._find_x_chain()
        return None

    # ------------------------------------------------------------------
    # X-Chain
    # ------------------------------------------------------------------

    def _find_x_chain(self) -> SolutionStep | None:
        """Find the best X-Chain elimination.

        Collects all valid chains, deduplicates by elimination set (keeping
        shortest per set), then returns the one ranked first by HoDoKu's
        comparator (most eliminations, then lowest weighted index sum).
        """
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
    ) -> None:
        if len(chain) >= _MAX_CHAIN:
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
                    self._record(digit, SolutionType.X_CHAIN, chain, elim, deletes_map)

            self._dfs_x(
                digit, links, chain, chain_set,
                strong_only=not strong_only,
                start=start,
                start_buddies=start_buddies,
                deletes_map=deletes_map,
            )

            chain.pop()
            chain_set.discard(nb)

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
