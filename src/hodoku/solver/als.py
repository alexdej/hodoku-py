"""ALS solver: ALS-XZ, ALS-XY-Wing, ALS-XY-Chain, Death Blossom.

Mirrors Java's AlsSolver, Als, RestrictedCommon, and the ALS/RC collection
methods in SudokuStepFinder.
"""

from __future__ import annotations

from functools import cmp_to_key

from hodoku.core.grid import ALL_UNITS, BUDDIES, Grid
from hodoku.core.solution_step import SolutionStep
from hodoku.core.types import SolutionType

_MAX_RC = 50  # maximum RCs in an ALS-Chain (matches Java MAX_RC)

# Ordinal map used by AlsComparator for tiebreaking on type
_SOL_TYPE_ORDINALS = {t: i for i, t in enumerate(SolutionType)}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_buddies_of_set(cell_set: int) -> int:
    """Intersection of BUDDIES[c] for every cell c in cell_set.

    Returns the set of all cells that see every cell in cell_set.
    Returns 0 if cell_set is empty.
    """
    if not cell_set:
        return 0
    result = (1 << 81) - 1
    tmp = cell_set
    while tmp:
        lsb = tmp & -tmp
        result &= BUDDIES[lsb.bit_length() - 1]
        tmp ^= lsb
    return result


# ---------------------------------------------------------------------------
# ALS data structure
# ---------------------------------------------------------------------------

class Als:
    """Almost Locked Set: N cells in one house with exactly N+1 candidates."""

    __slots__ = (
        'indices', 'candidates',
        'indices_per_cand', 'buddies_per_cand', 'buddies_als_per_cand',
        'buddies',
    )

    def __init__(self, indices: int, candidates: int) -> None:
        self.indices = indices
        self.candidates = candidates
        self.indices_per_cand: list[int] = [0] * 10
        self.buddies_per_cand: list[int] = [0] * 10
        self.buddies_als_per_cand: list[int] = [0] * 10
        self.buddies: int = 0

    def compute_fields(self, grid: Grid) -> None:
        """Compute derived sets after collection."""
        cands = self.candidates
        tmp = cands
        while tmp:
            lsb = tmp & -tmp
            d = lsb.bit_length()  # digit (1-9)
            tmp ^= lsb
            ipc = self.indices & grid.candidate_sets[d]
            self.indices_per_cand[d] = ipc
            bpc = _get_buddies_of_set(ipc) & ~self.indices & grid.candidate_sets[d]
            self.buddies_per_cand[d] = bpc
            self.buddies_als_per_cand[d] = bpc | ipc
            self.buddies |= bpc

    def get_chain_penalty(self) -> int:
        """Chain distance penalty for using this ALS in a tabling chain.

        Mirrors Als.getChainPenalty() in Java.
        """
        cand_size = self.candidates.bit_count()
        if cand_size <= 1:
            return 0
        if cand_size == 2:
            return 1
        return (cand_size - 1) * 2

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Als) and self.indices == other.indices

    def __hash__(self) -> int:
        return hash(self.indices)


# ---------------------------------------------------------------------------
# Restricted Common data structure
# ---------------------------------------------------------------------------

class RestrictedCommon:
    """A Restricted Common between two ALSes.

    actual_rc encoding: 0=none, 1=cand1 only, 2=cand2 only, 3=both.
    """

    __slots__ = ('als1', 'als2', 'cand1', 'cand2', 'actual_rc')

    def __init__(self, als1: int, als2: int, cand1: int,
                 cand2: int = 0, actual_rc: int = 0) -> None:
        self.als1 = als1
        self.als2 = als2
        self.cand1 = cand1
        self.cand2 = cand2
        self.actual_rc = actual_rc

    def check_rc(self, prev: RestrictedCommon | None, first_try: bool) -> bool:
        """Update actual_rc based on the previous RC; return True if valid."""
        self.actual_rc = 1 if self.cand2 == 0 else 3
        if prev is None:
            if self.cand2 != 0:
                self.actual_rc = 1 if first_try else 2
            return self.actual_rc != 0
        if prev.actual_rc == 1:
            self.actual_rc = _check_rc_int(prev.cand1, 0, self.cand1, self.cand2)
        elif prev.actual_rc == 2:
            self.actual_rc = _check_rc_int(prev.cand2, 0, self.cand1, self.cand2)
        elif prev.actual_rc == 3:
            # Java passes cand1 twice here (case 3) — replicated faithfully.
            self.actual_rc = _check_rc_int(prev.cand1, prev.cand1, self.cand1, self.cand2)
        return self.actual_rc != 0


def _check_rc_int(c11: int, c12: int, c21: int, c22: int) -> int:
    """Remove ARC candidates {c11, c12} from PRC candidates {c21, c22}.

    Returns 0 (none left), 1 (c21), 2 (c22), or 3 (both).
    """
    if c12 == 0:
        # one ARC
        if c22 == 0:
            return 0 if c11 == c21 else 1
        else:
            if c11 == c22:
                return 1
            elif c11 == c21:
                return 2
            else:
                return 3
    else:
        # two ARCs
        if c22 == 0:
            return 0 if (c11 == c21 or c12 == c21) else 1
        else:
            if (c11 == c21 and c12 == c22) or (c11 == c22 and c12 == c21):
                return 0
            elif c11 == c22 or c12 == c22:
                return 1
            elif c11 == c21 or c12 == c21:
                return 2
            else:
                return 3


# ---------------------------------------------------------------------------
# ALS collection
# ---------------------------------------------------------------------------

def _collect_alses(grid: Grid) -> list[Als]:
    """Enumerate all ALSes in the grid (including single bivalue cells).

    Mirrors SudokuStepFinder.doGetAlses(onlyLargerThanOne=false).
    Iteration: 27 units x 9 start positions each, recursive subset search.
    """
    alses: list[Als] = []
    seen: set[int] = set()

    for unit in ALL_UNITS:
        n = len(unit)
        for start_j in range(n):
            _check_als_recursive(0, start_j, unit, n, grid, alses, seen, 0, 0)

    for als in alses:
        als.compute_fields(grid)

    return alses


def _check_als_recursive(
    anzahl: int,
    start_idx: int,
    unit: tuple[int, ...],
    n: int,
    grid: Grid,
    alses: list[Als],
    seen: set[int],
    index_set: int,
    cand_acc: int,
) -> None:
    """Recursive ALS search over one house.

    anzahl: number of cells already in the current set (0-based on entry).
    """
    anzahl += 1
    if anzahl > n - 1:
        return
    for i in range(start_idx, n):
        cell = unit[i]
        if grid.values[cell] != 0:
            continue
        new_index_set = index_set | (1 << cell)
        new_cands = cand_acc | grid.candidates[cell]
        if new_cands.bit_count() - anzahl == 1:
            if new_index_set not in seen:
                seen.add(new_index_set)
                alses.append(Als(new_index_set, new_cands))
        _check_als_recursive(anzahl, i + 1, unit, n, grid, alses, seen,
                             new_index_set, new_cands)


# ---------------------------------------------------------------------------
# RC collection (forward-only, no overlap)
# ---------------------------------------------------------------------------

def _collect_rcs(
    alses: list[Als],
    allow_overlap: bool = False,
) -> tuple[list[RestrictedCommon], list[int], list[int]]:
    """Find all Restricted Commons between ALS pairs.

    Forward-only (als2 index > als1 index).
    When allow_overlap is False (default), overlapping ALS pairs are skipped.
    When allow_overlap is True, overlapping pairs are allowed provided the RC
    candidate does not appear in the overlap region (mirrors Java withOverlap).

    Returns (rcs, start_indices, end_indices) where start_indices[i]..end_indices[i]
    is the slice of rcs whose als1 == i.
    """
    rcs: list[RestrictedCommon] = []
    n = len(alses)
    start_indices = [0] * n
    end_indices = [0] * n

    for i in range(n):
        als1 = alses[i]
        start_indices[i] = len(rcs)
        for j in range(i + 1, n):
            als2 = alses[j]
            overlap = als1.indices & als2.indices
            if overlap and not allow_overlap:
                continue
            # Must share at least one candidate
            common = als1.candidates & als2.candidates
            if not common:
                continue
            rc_count = 0
            new_rc: RestrictedCommon | None = None
            tmp = common
            while tmp:
                lsb = tmp & -tmp
                cand = lsb.bit_length()  # digit
                tmp ^= lsb
                all_cand_cells = als1.indices_per_cand[cand] | als2.indices_per_cand[cand]
                # RC candidate must not appear in the overlap region
                if overlap and all_cand_cells & overlap:
                    continue
                # RC check: all instances of cand in both ALSes must see each other.
                common_buddies = (als1.buddies_als_per_cand[cand]
                                  & als2.buddies_als_per_cand[cand])
                if all_cand_cells & ~common_buddies:
                    continue  # some cell doesn't see all others
                if rc_count == 0:
                    new_rc = RestrictedCommon(i, j, cand)
                    rcs.append(new_rc)
                else:
                    assert new_rc is not None
                    new_rc.cand2 = cand
                rc_count += 1
                if rc_count == 2:
                    break  # max 2 RCs per pair
        end_indices[i] = len(rcs)

    return rcs, start_indices, end_indices


# ---------------------------------------------------------------------------
# Shared elimination helper
# ---------------------------------------------------------------------------

def _check_candidates_to_delete(
    als1: Als, als2: Als,
    r1: int = 0, r2: int = 0, r3: int = 0, r4: int = 0,
) -> list[tuple[int, int]]:
    """Find (cell, digit) eliminations common to als1 and als2, minus RC digits.

    r1..r4 are RC candidates to exclude (0 means unused).
    Returns list of (cell_index, digit) in ascending cell order.
    """
    elim_mask = als1.candidates & als2.candidates
    for r in (r1, r2, r3, r4):
        if r:
            elim_mask &= ~(1 << (r - 1))
    if not elim_mask:
        return []
    # Quick pre-check: common buddies must exist
    if not (als1.buddies & als2.buddies):
        return []
    result: list[tuple[int, int]] = []
    tmp = elim_mask
    while tmp:
        lsb = tmp & -tmp
        cand = lsb.bit_length()
        tmp ^= lsb
        elim_cells = als1.buddies_per_cand[cand] & als2.buddies_per_cand[cand]
        c = elim_cells
        while c:
            cl = c & -c
            result.append((cl.bit_length() - 1, cand))
            c ^= cl
    return result


def _check_doubly_linked_als(
    als1: Als, als2: Als, rc1: int, rc2: int,
) -> list[tuple[int, int]]:
    """Locked-set eliminations when als1 and als2 share two RCs.

    als1 minus {rc1, rc2} forms a locked set; eliminate its remaining
    candidates from cells outside als2 that see all corresponding als1 cells.
    """
    remaining = als1.candidates & ~(1 << (rc1 - 1)) & ~(1 << (rc2 - 1))
    if not remaining:
        return []
    result: list[tuple[int, int]] = []
    tmp = remaining
    while tmp:
        lsb = tmp & -tmp
        cand = lsb.bit_length()
        tmp ^= lsb
        elim_cells = als1.buddies_per_cand[cand] & ~als2.indices
        c = elim_cells
        while c:
            cl = c & -c
            result.append((cl.bit_length() - 1, cand))
            c ^= cl
    return result


# ---------------------------------------------------------------------------
# AlsComparator sort key (mirrors Java's AlsComparator)
# ---------------------------------------------------------------------------

def _als_index_count(step: SolutionStep) -> int:
    return sum(bin(a[0]).count('1') for a in step.alses)


def _als_cmp(s1: SolutionStep, s2: SolutionStep) -> int:
    # 1. Most eliminations (descending)
    d = len(s2.candidates_to_delete) - len(s1.candidates_to_delete)
    if d:
        return d
    # 2. Equivalence check: same elimination set?
    k1 = tuple(sorted((c.index, c.value) for c in s1.candidates_to_delete))
    k2 = tuple(sorted((c.index, c.value) for c in s2.candidates_to_delete))
    if k1 != k2:
        # Not equivalent: sort by sum of deletion cell indices (ascending)
        return (sum(c.index for c in s1.candidates_to_delete)
                - sum(c.index for c in s2.candidates_to_delete))
    # Equivalent: 3. Fewer ALSes
    d = len(s1.alses) - len(s2.alses)
    if d:
        return d
    # 4. Fewer total cells across all ALSes
    d = _als_index_count(s1) - _als_index_count(s2)
    if d:
        return d
    # 5. Type ordinal (ascending)
    return _SOL_TYPE_ORDINALS[s1.type] - _SOL_TYPE_ORDINALS[s2.type]


def _best_step(deletes_map: dict) -> SolutionStep | None:
    steps = [step for _, step in deletes_map.values()]
    if not steps:
        return None
    steps.sort(key=cmp_to_key(_als_cmp))
    return steps[0]


def _record_step(
    step: SolutionStep,
    als_count: int,
    deletes_map: dict,
) -> None:
    """Store step if it's shortest (fewest ALS cells) for its elimination set."""
    key = tuple(sorted((c.index, c.value) for c in step.candidates_to_delete))
    old = deletes_map.get(key)
    if old is None or old[0] > als_count:
        deletes_map[key] = (als_count, step)


# ---------------------------------------------------------------------------
# Death Blossom RC-per-cell index
# ---------------------------------------------------------------------------

class _RCForDeathBlossom:
    """Per-stem-cell index of which ALSes cover each candidate."""

    __slots__ = ('cand_mask', 'als_per_candidate')

    def __init__(self) -> None:
        self.cand_mask: int = 0
        self.als_per_candidate: list[list[int]] = [[] for _ in range(10)]

    def add_als_for_candidate(self, als_idx: int, cand: int) -> None:
        self.als_per_candidate[cand].append(als_idx)
        self.cand_mask |= 1 << (cand - 1)


# ---------------------------------------------------------------------------
# Solver
# ---------------------------------------------------------------------------

class AlsSolver:
    """ALS-XZ, ALS-XY-Wing, ALS-XY-Chain, Death Blossom."""

    def __init__(self, grid: Grid) -> None:
        self.grid = grid

    def get_step(
        self, sol_type: SolutionType, allow_overlap: bool = False
    ) -> SolutionStep | None:
        if sol_type == SolutionType.ALS_XZ:
            return self._find_als_xz()
        if sol_type == SolutionType.ALS_XY_WING:
            return self._find_als_xy_wing(allow_overlap=allow_overlap)
        if sol_type == SolutionType.ALS_XY_CHAIN:
            return self._find_als_xy_chain(allow_overlap=allow_overlap)
        if sol_type == SolutionType.DEATH_BLOSSOM:
            return self._find_death_blossom(allow_overlap=allow_overlap)
        return None

    def find_all(
        self, sol_type: SolutionType, allow_overlap: bool = False
    ) -> list[SolutionStep]:
        if sol_type == SolutionType.ALS_XZ:
            return self._find_als_xz_all()
        if sol_type == SolutionType.ALS_XY_WING:
            return self._find_als_xy_wing_all(allow_overlap=allow_overlap)
        if sol_type == SolutionType.ALS_XY_CHAIN:
            return self._find_als_xy_chain_all(allow_overlap=allow_overlap)
        if sol_type == SolutionType.DEATH_BLOSSOM:
            return self._find_death_blossom_all(allow_overlap=allow_overlap)
        return []

    # ------------------------------------------------------------------
    # ALS-XZ
    # ------------------------------------------------------------------

    def _find_als_xz(self) -> SolutionStep | None:
        """Return the FIRST ALS-XZ step found (mirrors Java's onlyOne=true mode)."""
        grid = self.grid
        alses = _collect_alses(grid)
        rcs, _, _ = _collect_rcs(alses)

        for rc in rcs:
            if rc.als1 >= rc.als2:
                continue  # forward only (always true in forward-only mode)
            als1 = alses[rc.als1]
            als2 = alses[rc.als2]

            elims: list[tuple[int, int]] = []

            # Singly-linked elimination: exclude rc.cand1
            elims.extend(_check_candidates_to_delete(als1, als2, rc.cand1))

            # Doubly-linked: also exclude rc.cand2, plus locked-set elims
            if rc.cand2:
                elims.extend(_check_candidates_to_delete(als1, als2, rc.cand2))
                elims.extend(_check_doubly_linked_als(als1, als2, rc.cand1, rc.cand2))
                elims.extend(_check_doubly_linked_als(als2, als1, rc.cand1, rc.cand2))

            if not elims:
                continue

            step = SolutionStep(SolutionType.ALS_XZ)
            step.add_als(als1.indices, als1.candidates)
            step.add_als(als2.indices, als2.candidates)
            for cell, cand in elims:
                step.add_candidate_to_delete(cell, cand)
            return step

        return None

    def _find_als_xz_all(self) -> list[SolutionStep]:
        """Return ALL ALS-XZ steps (collect all, deduplicate by elimination set)."""
        grid = self.grid
        alses = _collect_alses(grid)
        rcs, _, _ = _collect_rcs(alses)
        deletes_map: dict = {}

        for rc in rcs:
            if rc.als1 >= rc.als2:
                continue
            als1 = alses[rc.als1]
            als2 = alses[rc.als2]

            elims: list[tuple[int, int]] = []
            elims.extend(_check_candidates_to_delete(als1, als2, rc.cand1))
            if rc.cand2:
                elims.extend(_check_candidates_to_delete(als1, als2, rc.cand2))
                elims.extend(_check_doubly_linked_als(als1, als2, rc.cand1, rc.cand2))
                elims.extend(_check_doubly_linked_als(als2, als1, rc.cand1, rc.cand2))
            if not elims:
                continue

            step = SolutionStep(SolutionType.ALS_XZ)
            step.add_als(als1.indices, als1.candidates)
            step.add_als(als2.indices, als2.candidates)
            for cell, cand in elims:
                step.add_candidate_to_delete(cell, cand)
            _record_step(step, _als_index_count(step), deletes_map)

        return [step for _, step in deletes_map.values()]

    # ------------------------------------------------------------------
    # ALS-XY-Wing
    # ------------------------------------------------------------------

    def _find_als_xy_wing(self, allow_overlap: bool = False) -> SolutionStep | None:
        """Return the FIRST ALS-XY-Wing step found (mirrors Java's onlyOne=true mode)."""
        grid = self.grid
        alses = _collect_alses(grid)
        rcs, _, _ = _collect_rcs(alses, allow_overlap=allow_overlap)
        n_rcs = len(rcs)

        for i in range(n_rcs):
            rc1 = rcs[i]
            for j in range(i + 1, n_rcs):
                rc2 = rcs[j]

                # Both singly-linked with the same candidate → skip
                if rc1.cand2 == 0 and rc2.cand2 == 0 and rc1.cand1 == rc2.cand1:
                    continue

                # Find pivot C: the ALS shared by both RCs
                c_idx, a_idx, b_idx = _identify_pivot(rc1, rc2)
                if c_idx is None:
                    continue

                als_a = alses[a_idx]
                als_b = alses[b_idx]

                # A and B must not overlap (skip when allow_overlap=True)
                if not allow_overlap and (als_a.indices & als_b.indices):
                    continue
                # A must not be subset/superset of B
                union_ab = als_a.indices | als_b.indices
                if union_ab == als_a.indices or union_ab == als_b.indices:
                    continue

                elims = _check_candidates_to_delete(
                    als_a, als_b,
                    rc1.cand1, rc1.cand2, rc2.cand1, rc2.cand2,
                )
                if not elims:
                    continue

                step = SolutionStep(SolutionType.ALS_XY_WING)
                step.add_als(als_a.indices, als_a.candidates)
                step.add_als(als_b.indices, als_b.candidates)
                step.add_als(alses[c_idx].indices, alses[c_idx].candidates)
                for cell, cand in elims:
                    step.add_candidate_to_delete(cell, cand)
                return step

        return None

    def _find_als_xy_wing_all(self, allow_overlap: bool = False) -> list[SolutionStep]:
        """Return ALL ALS-XY-Wing steps (collect all, deduplicate by elimination set)."""
        grid = self.grid
        alses = _collect_alses(grid)
        rcs, _, _ = _collect_rcs(alses, allow_overlap=allow_overlap)
        n_rcs = len(rcs)
        deletes_map: dict = {}

        for i in range(n_rcs):
            rc1 = rcs[i]
            for j in range(i + 1, n_rcs):
                rc2 = rcs[j]
                if rc1.cand2 == 0 and rc2.cand2 == 0 and rc1.cand1 == rc2.cand1:
                    continue
                c_idx, a_idx, b_idx = _identify_pivot(rc1, rc2)
                if c_idx is None:
                    continue
                als_a = alses[a_idx]
                als_b = alses[b_idx]
                if not allow_overlap and (als_a.indices & als_b.indices):
                    continue
                union_ab = als_a.indices | als_b.indices
                if union_ab == als_a.indices or union_ab == als_b.indices:
                    continue
                elims = _check_candidates_to_delete(
                    als_a, als_b,
                    rc1.cand1, rc1.cand2, rc2.cand1, rc2.cand2,
                )
                if not elims:
                    continue
                step = SolutionStep(SolutionType.ALS_XY_WING)
                step.add_als(als_a.indices, als_a.candidates)
                step.add_als(als_b.indices, als_b.candidates)
                step.add_als(alses[c_idx].indices, alses[c_idx].candidates)
                for cell, cand in elims:
                    step.add_candidate_to_delete(cell, cand)
                _record_step(step, _als_index_count(step), deletes_map)

        return [step for _, step in deletes_map.values()]

    # ------------------------------------------------------------------
    # ALS-XY-Chain
    # ------------------------------------------------------------------

    def _find_als_xy_chain(self, allow_overlap: bool = False) -> SolutionStep | None:
        grid = self.grid
        alses = _collect_alses(grid)
        rcs, start_indices, end_indices = _collect_rcs(alses, allow_overlap=allow_overlap)
        deletes_map: dict = {}

        n_als = len(alses)
        als_in_chain = [False] * n_als
        chain: list[RestrictedCommon] = []

        for i in range(n_als):
            start_als = alses[i]
            als_in_chain[i] = True
            self._chain_recursive(
                i, None, True,
                alses, rcs, start_indices, end_indices,
                als_in_chain, chain,
                start_als, deletes_map,
            )
            als_in_chain[i] = False

        return _best_step(deletes_map)

    def _find_als_xy_chain_all(self, allow_overlap: bool = False) -> list[SolutionStep]:
        """Return ALL ALS-XY-Chain steps (all entries from the deduplication map)."""
        grid = self.grid
        alses = _collect_alses(grid)
        rcs, start_indices, end_indices = _collect_rcs(alses, allow_overlap=allow_overlap)
        deletes_map: dict = {}

        n_als = len(alses)
        als_in_chain = [False] * n_als
        chain: list[RestrictedCommon] = []

        for i in range(n_als):
            start_als = alses[i]
            als_in_chain[i] = True
            self._chain_recursive(
                i, None, True,
                alses, rcs, start_indices, end_indices,
                als_in_chain, chain,
                start_als, deletes_map,
            )
            als_in_chain[i] = False

        return [step for _, step in deletes_map.values()]

    def _chain_recursive(
        self,
        als_idx: int,
        last_rc: RestrictedCommon | None,
        first_try: bool,
        alses: list[Als],
        rcs: list[RestrictedCommon],
        start_indices: list[int],
        end_indices: list[int],
        als_in_chain: list[bool],
        chain: list[RestrictedCommon],
        start_als: Als,
        deletes_map: dict,
    ) -> None:
        if len(chain) >= _MAX_RC:
            return

        first_try_local = True
        i = start_indices[als_idx]
        while i < end_indices[als_idx]:
            rc = rcs[i]

            if len(chain) >= _MAX_RC or not rc.check_rc(last_rc, first_try_local):
                i += 1
                first_try_local = True
                continue

            if als_in_chain[rc.als2]:
                i += 1
                first_try_local = True
                continue

            chain.append(rc)
            als_in_chain[rc.als2] = True

            if len(chain) >= 3:
                # Extract active RC candidates at each end
                first_rc = chain[0]
                c1 = first_rc.cand1 if first_rc.actual_rc in (1, 3) else 0
                c2 = first_rc.cand2 if first_rc.actual_rc in (2, 3) else 0
                # For case 3 on first_rc (both cands active), c2 set via actual_rc==3
                # but actual_rc==3 path: c1=cand1, c2=cand2
                if first_rc.actual_rc == 3:
                    c1 = first_rc.cand1
                    c2 = first_rc.cand2
                elif first_rc.actual_rc == 1:
                    c1 = first_rc.cand1
                    c2 = 0
                elif first_rc.actual_rc == 2:
                    c1 = 0
                    c2 = first_rc.cand2
                else:
                    c1 = c2 = 0

                c3 = c4 = 0
                if rc.actual_rc == 1:
                    c3 = rc.cand1
                elif rc.actual_rc == 2:
                    c3 = rc.cand2
                elif rc.actual_rc == 3:
                    c3 = rc.cand1
                    c4 = rc.cand2

                end_als = alses[rc.als2]
                elims = _check_candidates_to_delete(start_als, end_als, c1, c2, c3, c4)
                if elims:
                    step = SolutionStep(SolutionType.ALS_XY_CHAIN)
                    step.add_als(start_als.indices, start_als.candidates)
                    for link in chain:
                        step.add_als(alses[link.als2].indices,
                                     alses[link.als2].candidates)
                    for cell, cand in elims:
                        step.add_candidate_to_delete(cell, cand)
                    _record_step(step, _als_index_count(step), deletes_map)

            self._chain_recursive(
                rc.als2, rc, True,
                alses, rcs, start_indices, end_indices,
                als_in_chain, chain,
                start_als, deletes_map,
            )

            als_in_chain[rc.als2] = False
            chain.pop()

            # Doubly-linked first RC: retry with the alternate candidate
            if last_rc is None and rc.cand2 != 0 and first_try_local:
                first_try_local = False
                # Don't advance i — retry same RC with first_try=False
            else:
                i += 1
                first_try_local = True

    # ------------------------------------------------------------------
    # Death Blossom
    # ------------------------------------------------------------------

    def _find_death_blossom_all(self, allow_overlap: bool = False) -> list[SolutionStep]:
        """Return ALL Death Blossom steps."""
        grid = self.grid
        alses = _collect_alses(grid)
        rcdb = self._collect_rcs_for_death_blossom(alses)
        result: list[SolutionStep] = []

        for stem in range(81):
            if grid.values[stem] != 0:
                continue
            if rcdb[stem] is None:
                continue
            if rcdb[stem].cand_mask != grid.candidates[stem]:
                continue

            max_cand = 0
            tmp = grid.candidates[stem]
            while tmp:
                lsb = tmp & -tmp
                max_cand = lsb.bit_length()
                tmp ^= lsb

            state = _DBState(stem)
            self._db_recursive(
                1, max_cand, stem, rcdb[stem], alses, grid, state, result,
                allow_overlap=allow_overlap, find_all=True,
            )

        return result

    def _find_death_blossom(self, allow_overlap: bool = False) -> SolutionStep | None:
        """Return the FIRST Death Blossom step found (mirrors Java's onlyOne=true mode)."""
        grid = self.grid
        alses = _collect_alses(grid)
        rcdb = self._collect_rcs_for_death_blossom(alses)
        # Use a list so the recursive call can signal early exit
        result: list[SolutionStep] = []

        for stem in range(81):
            if grid.values[stem] != 0:
                continue
            if rcdb[stem] is None:
                continue
            if rcdb[stem].cand_mask != grid.candidates[stem]:
                continue

            max_cand = 0
            tmp = grid.candidates[stem]
            while tmp:
                lsb = tmp & -tmp
                max_cand = lsb.bit_length()
                tmp ^= lsb

            state = _DBState(stem)
            self._db_recursive(
                1, max_cand, stem, rcdb[stem], alses, grid, state, result,
                allow_overlap=allow_overlap, find_all=False,
            )
            if result:
                return result[0]

        return None

    def _collect_rcs_for_death_blossom(
        self, alses: list[Als],
    ) -> list[_RCForDeathBlossom | None]:
        """Build per-cell index of which ALSes cover each candidate."""
        rcdb: list[_RCForDeathBlossom | None] = [None] * 81

        for i, als in enumerate(alses):
            tmp = als.candidates
            while tmp:
                lsb = tmp & -tmp
                cand = lsb.bit_length()
                tmp ^= lsb
                cells = als.buddies_per_cand[cand]
                c = cells
                while c:
                    cl = c & -c
                    cell = cl.bit_length() - 1
                    c ^= cl
                    if rcdb[cell] is None:
                        rcdb[cell] = _RCForDeathBlossom()
                    rcdb[cell].add_als_for_candidate(i, cand)

        return rcdb

    def _db_recursive(
        self,
        cand: int,
        max_cand: int,
        stem: int,
        rcdb_entry: _RCForDeathBlossom,
        alses: list[Als],
        grid: Grid,
        state: _DBState,
        result: list,
        allow_overlap: bool = False,
        find_all: bool = False,
    ) -> None:
        if cand > max_cand:
            return

        if rcdb_entry.als_per_candidate[cand]:
            for als_idx in rcdb_entry.als_per_candidate[cand]:
                if not find_all and result:
                    return  # early exit
                als = alses[als_idx]

                # ALS must never contain the stem cell itself
                if als.indices & (1 << stem):
                    continue
                # No petal-petal overlap unless allow_overlap=True
                petal_indices = state.db_indices & ~(1 << stem)
                if not allow_overlap and (als.indices & petal_indices):
                    continue

                # Must share at least one common candidate
                if not (state.db_candidates & als.candidates):
                    continue

                state.akt_db_als[cand] = als_idx
                inc = state.db_candidates & ~als.candidates
                state.inc_db_cand[cand] = inc
                state.db_candidates &= als.candidates
                state.db_indices |= als.indices

                if cand < max_cand:
                    self._db_recursive(
                        cand + 1, max_cand, stem, rcdb_entry,
                        alses, grid, state, result,
                        allow_overlap=allow_overlap, find_all=find_all,
                    )
                else:
                    self._db_check_eliminations(stem, alses, grid, state, result)

                # Backtrack
                state.db_candidates |= inc
                state.db_indices &= ~als.indices
                state.akt_db_als[cand] = -1

                if not find_all and result:
                    return  # early exit after finding one
        else:
            state.akt_db_als[cand] = -1
            self._db_recursive(
                cand + 1, max_cand, stem, rcdb_entry,
                alses, grid, state, result,
                allow_overlap=allow_overlap, find_all=find_all,
            )

    def _db_check_eliminations(
        self,
        stem: int,
        alses: list[Als],
        grid: Grid,
        state: _DBState,
        result: list,
    ) -> None:
        """Check for eliminations; append first valid step to result."""
        elims: list[tuple[int, int]] = []

        tmp = state.db_candidates
        while tmp:
            lsb = tmp & -tmp
            check_cand = lsb.bit_length()
            tmp ^= lsb

            if state.akt_db_als[check_cand] != -1:
                continue  # stem candidate — locked, can't eliminate externally

            union_cells = 0
            for k in range(1, 10):
                if state.akt_db_als[k] == -1:
                    continue
                union_cells |= alses[state.akt_db_als[k]].indices_per_cand[check_cand]

            if not union_cells:
                continue

            buddies = _get_buddies_of_set(union_cells)
            buddies &= ~state.db_indices
            buddies &= ~(1 << stem)
            buddies &= grid.candidate_sets[check_cand]

            c = buddies
            while c:
                cl = c & -c
                elims.append((cl.bit_length() - 1, check_cand))
                c ^= cl

        if not elims:
            return

        step = SolutionStep(SolutionType.DEATH_BLOSSOM)
        step.add_index(stem)
        for k in range(1, 10):
            if state.akt_db_als[k] == -1:
                continue
            als = alses[state.akt_db_als[k]]
            step.add_als(als.indices, als.candidates)
        for cell, cand in elims:
            step.add_candidate_to_delete(cell, cand)

        result.append(step)


class _DBState:
    """Mutable state for the Death Blossom recursive search."""

    __slots__ = ('db_indices', 'db_candidates', 'akt_db_als', 'inc_db_cand')

    def __init__(self, stem: int) -> None:
        self.db_indices: int = 1 << stem   # start with stem cell excluded
        self.db_candidates: int = 0x1ff    # all 9 candidates (MAX_MASK)
        self.akt_db_als: list[int] = [-1] * 10
        self.inc_db_cand: list[int] = [0] * 10


# ---------------------------------------------------------------------------
# Pivot identification for ALS-XY-Wing
# ---------------------------------------------------------------------------

def _identify_pivot(
    rc1: RestrictedCommon, rc2: RestrictedCommon,
) -> tuple[int | None, int | None, int | None]:
    """Find the pivot ALS (C) shared by rc1 and rc2; return (c_idx, a_idx, b_idx).

    Returns (None, None, None) if no valid pivot exists (not exactly 3 distinct ALSes).
    """
    # Four possible shared-ALS configurations (mirrors Java's if-chain exactly)
    c_idx = a_idx = b_idx = None

    if rc1.als1 == rc2.als1 and rc1.als2 != rc2.als2:
        c_idx, a_idx, b_idx = rc1.als1, rc1.als2, rc2.als2
    elif rc1.als1 == rc2.als2 and rc1.als2 != rc2.als1:
        c_idx, a_idx, b_idx = rc1.als1, rc1.als2, rc2.als1
    elif rc1.als2 == rc2.als1 and rc1.als1 != rc2.als2:
        c_idx, a_idx, b_idx = rc1.als2, rc1.als1, rc2.als2
    elif rc1.als2 == rc2.als2 and rc1.als1 != rc2.als1:
        c_idx, a_idx, b_idx = rc1.als2, rc1.als1, rc2.als1

    return c_idx, a_idx, b_idx
