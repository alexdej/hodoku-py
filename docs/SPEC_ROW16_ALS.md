# Implementation Spec: Almost Locked Sets (ALS)

Row 16 from ROADMAP.md. Produced by reading Java source:
`AlsSolver.java`, `Als.java`, `RestrictedCommon.java`, `SudokuStepFinder.java`.

---

## Overview

An **Almost Locked Set (ALS)** is a set of N cells within a single house that together
contain exactly N+1 distinct candidates. A single bivalue cell is the smallest ALS.

All four ALS techniques share two build phases:
1. **Collect ALSes** — enumerate all valid ALS in the grid
2. **Collect RCs** — find all Restricted Commons between pairs of ALSes

---

## Data Structures

### `Als`

```python
@dataclass
class Als:
    indices: int           # CellSet bitmask (which cells)
    candidates: int        # 9-bit mask (which digits appear)
    indices_per_cand: list[int]      # [0..9]: CellSet of ALS cells with digit d
    buddies_per_cand: list[int]      # [0..9]: cells outside ALS seeing ALL ALS cells with d, having d
    buddies_als_per_cand: list[int]  # [0..9]: buddies_per_cand[d] | indices_per_cand[d]
    buddies: int           # union of all buddies_per_cand[d]
```

**Computing fields** (after collection):
```
for d in 1..9 where bit d-1 set in candidates:
    indices_per_cand[d] = indices & candidate_sets[d]
    buddies_per_cand[d] = get_buddies_of_set(indices_per_cand[d])
                          & ~indices
                          & candidate_sets[d]
    buddies_als_per_cand[d] = buddies_per_cand[d] | indices_per_cand[d]
    buddies |= buddies_per_cand[d]
```

where `get_buddies_of_set(S)` = intersection of `BUDDIES[c]` for all cells `c` in S.

### `RestrictedCommon` (RC)

```python
@dataclass
class RestrictedCommon:
    als1: int      # index into alses list
    als2: int      # index into alses list (als2 > als1 in forward-only mode)
    cand1: int     # first RC digit
    cand2: int     # second RC digit (0 if only one RC)
    actual_rc: int # 0=none, 1=cand1 only, 2=cand2 only, 3=both (used in chain search)
```

---

## Phase 1: ALS Collection (`collect_alses`)

Mirrors `SudokuStepFinder.doGetAlses()` and `checkAlsRecursive()`.

```
alses = []
seen = set()   # CellSet bitmasks already recorded

for unit in ALL_UNITS:   # 27 units (9 rows, 9 cols, 9 boxes)
    for start_j in range(len(unit)):
        _check_als_recursive(anzahl=0, start_idx=start_j, unit, cand_acc=0)
```

**Recursive helper** `_check_als_recursive(anzahl, start_idx, unit, cand_acc, index_set)`:
```
anzahl += 1
if anzahl > len(unit) - 1:  # max 8 cells in an ALS
    return
for i in range(start_idx, len(unit)):
    cell = unit[i]
    if grid.values[cell] != 0:
        continue
    index_set |= 1 << cell
    new_cands = cand_acc | grid.candidates[cell]
    if new_cands.bit_count() - anzahl == 1:   # N+1 candidates in N cells
        if index_set not in seen:
            seen.add(index_set)
            alses.append(Als(index_set, new_cands))
    _check_als_recursive(anzahl, i+1, unit, new_cands, index_set)
    index_set ^= 1 << cell
```

After collection, call `compute_fields()` on each ALS.

The `onlyLargerThanOne=False` variant (used by solver) includes single bivalue cells as ALS.

---

## Phase 2: RC Collection (`collect_rcs`)

Mirrors `SudokuStepFinder.doGetRestrictedCommons()`.

Config: `rc_only_forward=True`, `allow_overlap=False` (HoDoKu defaults when solving).

```
rcs = []
start_indices = [0] * len(alses)
end_indices   = [0] * len(alses)

for i, als1 in enumerate(alses):
    start_indices[i] = len(rcs)
    for j in range(i+1, len(alses)):   # forward-only: j > i
        als2 = alses[j]
        # Overlap check (not allowed by default)
        if als1.indices & als2.indices:
            continue
        # Common candidates
        common = als1.candidates & als2.candidates
        if not common:
            continue
        rc_count = 0
        new_rc = None
        for cand in bits(common):
            # No RC cell may be in the overlap area (empty here since no overlap)
            # Check: all instances of cand in both ALSes see each other
            all_cand_cells = als1.indices_per_cand[cand] | als2.indices_per_cand[cand]
            common_buddies = als1.buddies_als_per_cand[cand] & als2.buddies_als_per_cand[cand]
            if all_cand_cells & ~common_buddies == 0:   # all cells are in common_buddies
                if rc_count == 0:
                    new_rc = RestrictedCommon(i, j, cand)
                    rcs.append(new_rc)
                else:
                    new_rc.cand2 = cand
                rc_count += 1
    end_indices[i] = len(rcs)
```

At most 2 RCs per ALS pair (HoDoKu only handles ALS, not AALS).

---

## Shared elimination helper: `check_candidates_to_delete`

Used by XZ, XY-Wing, and XY-Chain to find eliminations between two "flanking" ALSes.

```
check_candidates_to_delete(als1, als2, r1, r2, r3, r4):
    # Exclude RC candidates from elimination candidates
    elim_cands = als1.candidates & als2.candidates
    for r in [r1, r2, r3, r4]:
        if r > 0:
            elim_cands &= ~(1 << (r-1))   # clear bit for digit r
    if not elim_cands:
        return []
    # Quick pre-check: any shared buddies?
    if not (als1.buddies & als2.buddies):
        return []
    result = []
    for cand in bits(elim_cands):
        elim_cells = als1.buddies_per_cand[cand] & als2.buddies_per_cand[cand]
        for cell in bits(elim_cells):
            result.append((cell, cand))
    return result
```

Note: `buddies_per_cand` already excludes ALS cells, so no extra filtering needed.
Eliminations are added in ascending cell order (iterate bits low-to-high).

---

## Technique 1: ALS-XZ (`get_step(ALS_XZ)`)

Mirrors `AlsSolver.getAlsXZInt()`.

**Forward pass only** (als1 index < als2 index, enforced by `rc.als1 < rc.als2` check).

```
for rc in rcs:
    if rc.als1 >= rc.als2:
        continue   # only forward
    als1 = alses[rc.als1]
    als2 = alses[rc.als2]

    # Singly-linked: check with rc.cand1 excluded
    elims = check_candidates_to_delete(als1, als2, rc.cand1, -1, -1, -1)

    # Doubly-linked: rc.cand2 != 0
    if rc.cand2:
        elims += check_candidates_to_delete(als1, als2, rc.cand2, -1, -1, -1)
        # Locked-set eliminations from doubly-linked ALS
        d1 = check_doubly_linked_als(als1, als2, rc.cand1, rc.cand2)
        d2 = check_doubly_linked_als(als2, als1, rc.cand1, rc.cand2)
        if d1 or d2:
            # fins cleared (doubly-linked indicator) — handled at step-build time

    if elims:
        record step
```

**Doubly-linked locked-set check** (`check_doubly_linked_als(als1, als2, rc1, rc2)`):
```
remaining = als1.candidates & ~(1 << (rc1-1)) & ~(1 << (rc2-1))
result = []
for cand in bits(remaining):
    elim_cells = als1.buddies_per_cand[cand] & ~als2.indices
    for cell in bits(elim_cells):
        result.append((cell, cand))
return result
```

**SolutionStep:**
- `type`: `ALS_XZ`
- `alses`: `[(als1.indices, als1.candidates), (als2.indices, als2.candidates)]`
- `candidates_to_delete`: all elim (cell, cand) pairs

---

## Technique 2: ALS-XY-Wing (`get_step(ALS_XY_WING)`)

Mirrors `AlsSolver.getAlsXYWingInt()`.

Three ALSes: A, B (flanking), C (pivot). Two RCs connect C to A and C to B.

```
for i, rc1 in enumerate(rcs):
    for j in range(i+1, len(rcs)):
        rc2 = rcs[j]
        # Both single-cand check: if rc1.cand2==0 and rc2.cand2==0 and same cand → skip
        if rc1.cand2 == 0 and rc2.cand2 == 0 and rc1.cand1 == rc2.cand1:
            continue
        # Must connect exactly 3 distinct ALSes
        # Identify pivot C (the shared ALS) and flanking A, B
        c_idx, a_idx, b_idx = identify_pivot(rc1, rc2)
        if c_idx is None:
            continue
        als_a, als_b, als_c = alses[a_idx], alses[b_idx], alses[c_idx]
        # No overlap between A and B (C already checked via RC collection)
        if als_a.indices & als_b.indices:
            continue
        # A must not be a subset of B or vice versa
        if (als_a.indices | als_b.indices) in (als_a.indices, als_b.indices):
            continue
        # Eliminate candidates common to A and B, minus all 4 RC candidates
        elims = check_candidates_to_delete(als_a, als_b,
                    rc1.cand1, rc1.cand2, rc2.cand1, rc2.cand2)
        if elims:
            record step
```

**Identifying pivot** (`identify_pivot(rc1, rc2)`):
Four possible configurations: `rc1.als1==rc2.als1`, `rc1.als1==rc2.als2`,
`rc1.als2==rc2.als1`, `rc1.als2==rc2.als2`. The shared index is C; the other
two indices are A and B. All three must be distinct.

**SolutionStep:**
- `type`: `ALS_XY_WING`
- `alses`: `[A, B, C]` (flanking first, then pivot)
- `candidates_to_delete`: elim pairs from A and B

---

## Technique 3: ALS-XY-Chain (`get_step(ALS_XY_CHAIN)`)

Mirrors `AlsSolver.getAlsXYChainInt()` and `getAlsXYChainRecursive()`.

A chain of ALSes A0–A1–...–Ak connected by RCs. Minimum k+1 = 4 ALSes (3 RCs).
Eliminations come from candidates common to the first and last ALS, minus the "active"
RC digits at each end.

**RC adjacency rule** (`check_rc(this_rc, prev_rc, first_try)`):
Controls which candidates of an RC are "active" (`actual_rc` field), excluding any
candidate that was already used by the previous link. This ensures alternation of RCs.

```
check_rc(this_rc, prev_rc, first_try):
    # Default: all available candidates active
    this_rc.actual_rc = 1 if this_rc.cand2 == 0 else 3
    if prev_rc is None:
        # Start of chain: for doubly-linked first RC, try one at a time
        if this_rc.cand2 != 0:
            this_rc.actual_rc = 1 if first_try else 2
        return this_rc.actual_rc != 0
    # Remove candidates used by prev_rc
    match prev_rc.actual_rc:
        case 1: this_rc.actual_rc = check_rc_int(prev_rc.cand1, 0, ...)
        case 2: this_rc.actual_rc = check_rc_int(prev_rc.cand2, 0, ...)
        case 3: this_rc.actual_rc = check_rc_int(prev_rc.cand1, prev_rc.cand1, ...)
                # Note: Java passes cand1 twice here (cand1, cand1 not cand1, cand2)
                # Replicate faithfully for HoDoKu compatibility.
    return this_rc.actual_rc != 0
```

**`check_rc_int(c11, c12, c21, c22)`** — removes duplicate candidates:
Returns 0 (no valid RC), 1 (cand1 valid), 2 (cand2 valid), or 3 (both valid)
by eliminating any of {c21, c22} that appears in {c11, c12}.

**Main loop:**
```
for i, start_als in enumerate(alses):
    als_in_chain = {i}
    chain = []         # list of RestrictedCommon
    first_rc = None
    first_try = True
    _chain_recursive(i, last_rc=None)
```

**Recursive step** `_chain_recursive(als_idx, last_rc)`:
```
for rc in rcs[start_indices[als_idx] : end_indices[als_idx]]:
    if not rc.check_rc(last_rc, first_try):
        continue
    if rc.als2 in als_in_chain:
        continue   # no whips
    if chain is empty:
        first_rc = rc
    chain.append(rc)
    als_in_chain.add(rc.als2)
    if len(chain) >= 3:
        # Check eliminations between start_als and alses[rc.als2]
        c1, c2 = active_cands_of(first_rc)    # actual_rc determines which
        c3, c4 = active_cands_of(rc)
        elims = check_candidates_to_delete(start_als, alses[rc.als2], c1, c2, c3, c4)
        if elims:
            record step (deduplicate by elim set, keep shorter chain)
    _chain_recursive(rc.als2, last_rc=rc)
    als_in_chain.remove(rc.als2)
    chain.pop()
    # Doubly-linked first RC: try alternate candidate
    if last_rc is None and rc.cand2 != 0 and first_try:
        first_try = False
        retry same rc
    else:
        first_try = True
```

**Active cands of RC:**
```
c1, c2 = 0, 0
if rc.actual_rc in (1, 3): c1 = rc.cand1
if rc.actual_rc in (2, 3): c2 = rc.cand2  # but see case 3 note above
```

Wait — the first RC's `actual_rc` is set during `check_rc(None, first_try)`.
For chains: at elimination check time, `actual_rc` holds what was last set.

**Deduplication:** same elimination set → keep the version with fewer ALSes (shorter chain).
Uses `Options.isOnlyOneAlsPerStep()` which is `true` by default.

**SolutionStep:**
- `type`: `ALS_XY_CHAIN`
- `alses`: `[start_als, als[rc0.als2], ..., als[last_rc.als2]]`
- `candidates_to_delete`: elim pairs

---

## Technique 4: Death Blossom (`get_step(DEATH_BLOSSOM)`)

Mirrors `AlsSolver.getAlsDeathBlossomInt()` and `checkAlsDeathBlossomRecursive()`.

A **stem cell** S has candidates {c1, ..., ck}. For each ci, there is an ALS Ai such that:
- ci is an RC between S and Ai (i.e., all ci candidates in Ai see S)
- All Ai are non-overlapping
- The union of all Ai cells doesn't contain S

Any candidate Z that appears in ALL Ai and whose instances in all Ai see each other
(i.e., a common buddy exists outside all Ai and S) can be eliminated.

### Phase 2b: RC collection for Death Blossom (`collect_rcs_for_death_blossom`)

For each ALS, for each candidate d in the ALS: find all cells in `buddies_per_cand[d]`.
Those cells are potential stem cells for d. For each such cell, record that this ALS
can serve as the "petal" for candidate d.

```
rcdb = [None] * 81   # RCForDeathBlossom per cell

for i, als in enumerate(alses):
    for d in bits(als.candidates):
        for cell in bits(als.buddies_per_cand[d]):
            rcdb[cell] = rcdb[cell] or RCForDeathBlossom()
            rcdb[cell].add_als_for_candidate(i, d)
            rcdb[cell].cand_mask |= 1 << (d-1)
```

### Main search

```
for stem in range(81):
    if grid.values[stem] != 0:
        continue
    if rcdb[stem] is None:
        continue
    if rcdb[stem].cand_mask != grid.candidates[stem]:
        # Not all stem candidates have an ALS → impossible
        continue
    # Try all combinations of ALSes, one per candidate
    _db_recursive(cand=1, max_cand=max_candidate_in_stem)
```

**Recursive helper** `_db_recursive(cand)`:
```
if cand > max_cand:
    # All stem candidates covered — check eliminations
    for check_cand in bits(combined_als_candidates):
        # Union all ALS cells with check_cand
        union_cells = OR of als.indices_per_cand[check_cand] for each ALS in combo
        elim = get_buddies_of_set(union_cells)
             & ~combined_als_indices
             & ~{stem}
             & candidate_sets[check_cand]
        if elim:
            record eliminations
    return

if rcdb[stem].indices[cand] > 0:
    for als_i in rcdb[stem].als_per_candidate[cand]:
        als = alses[als_i]
        if als.indices & combined_indices:
            continue   # overlap not allowed
        add als to combo
        _db_recursive(cand + 1)
        remove als from combo
else:
    # No ALS for this candidate → skip to next
    _db_recursive(cand + 1)
```

**SolutionStep:**
- `type`: `DEATH_BLOSSOM`
- `indices`: `[stem_cell]`
- `alses`: one per candidate of stem
- `candidates_to_delete`: all elimination (cell, cand) pairs

---

## Sort order: `AlsComparator`

All ALS techniques share this comparator to pick the "best" step:

```python
def als_cmp(s1, s2) -> int:
    # 1. Most eliminations (descending)
    d = len(s2.candidates_to_delete) - len(s1.candidates_to_delete)
    if d != 0:
        return d
    # 2. If elim sets differ: lowest sum of deletion cell indices
    k1 = sorted((c.index, c.value) for c in s1.candidates_to_delete)
    k2 = sorted((c.index, c.value) for c in s2.candidates_to_delete)
    if k1 != k2:
        return sum(c.index for c in s1.candidates_to_delete) \
             - sum(c.index for c in s2.candidates_to_delete)
    # 3. Fewest ALSes
    d = len(s1.alses) - len(s2.alses)
    if d != 0:
        return d
    # 4. Fewest total cells across all ALSes
    d = als_index_count(s1) - als_index_count(s2)
    if d != 0:
        return d
    # 5. Type ordinal (ascending)
    return s1.type ordinal - s2.type ordinal
```

where `als_index_count(step) = sum(popcount(a[0]) for a in step.alses)`.

---

## Configuration (HoDoKu defaults when solving)

| Option | Default | Effect |
|--------|---------|--------|
| `rc_only_forward` | `True` | Only RCs where als2 > als1 are collected |
| `allow_als_overlap` | `False` | ALS pairs with overlapping cells are skipped |
| `only_one_als_per_step` | `True` | Dedup by elim set, keep shortest chain |
| `max_rc` (chain length) | 50 | Maximum RCs in an ALS-Chain |

---

## Wiring

Register in `step_finder.py`:
```python
_ALS_TYPES = frozenset({
    SolutionType.ALS_XZ,
    SolutionType.ALS_XY_WING,
    SolutionType.ALS_XY_CHAIN,
    SolutionType.DEATH_BLOSSOM,
})
```

`SolutionStep` needs `add_als(indices: int, candidates: int)` helper method.

---

## Validation

Use HoDoKu technique codes: `axz`, `axy`, `axc`, `db`.

```bash
# Find clean puzzles
cd hodoku && java -Xmx512m -jar hodoku.jar /s /sc axz
cd hodoku && java -Xmx512m -jar hodoku.jar /s /sc axy
cd hodoku && java -Xmx512m -jar hodoku.jar /s /sc axc
cd hodoku && java -Xmx512m -jar hodoku.jar /s /sc db
```

Cleanness `:1` (SSTS before and after) is realistic for ALS-XZ and ALS-XY-Wing.
ALS-Chain and Death Blossom may require `:0`.
