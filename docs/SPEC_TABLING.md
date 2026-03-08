# Spec: Forcing Chains / Forcing Nets (Tabling)

`TablingSolver.java` — 3190 lines. Port to `src/hodoku/solver/tabling.py`.

---

## Overview

Tabling builds a complete implication table for every premise ("candidate N
set/deleted in cell X"), then checks those tables for contradictions and
verities. The result is a list of steps sorted by complexity; the solver
picks the first one.

**Dispatch** (from `TablingSolver.getStep()`):

| SolutionType | Config flag | Method |
|---|---|---|
| `FORCING_CHAIN_CONTRADICTION`, `FORCING_CHAIN_VERITY` | `chainsOnly=True`, `withGroupNodes=True` | `getForcingChains()` |
| `FORCING_NET_CONTRADICTION`, `FORCING_NET_VERITY` | `chainsOnly=False`, `withGroupNodes=True` | `getForcingNets()` |

Note: Nice Loop / AIC / GNL are **also** produced by TablingSolver in Java
(via `checkNiceLoops` / `checkAics`), but in our implementation those are
already handled by `chains.py`. The new file covers only Forcing
Chains/Nets.

---

## Data Structures

### `TableEntry`

One `TableEntry` per premise (cell × candidate × on/off). Holds all
transitive implications of that premise.

```python
@dataclass
class TableEntry:
    # index into entries[] / ret_indices[] — next free slot
    index: int = 0

    # entries[k]: 32-bit packed chain entry (same format as chains.py)
    entries: list[int]       # length MAX_TABLE_ENTRY_LENGTH (default 500)

    # ret_indices[k]: 64-bit backpointer for chain reconstruction
    ret_indices: list[int]   # same length

    # Summary bitmasks: onSets[d] = set of cells that can be set to d
    #                   offSets[d] = set of cells from which d can be deleted
    on_sets:  list[int]      # length 10 (index 0 unused), Python int bitmasks
    off_sets: list[int]      # same

    # Reverse lookup: entries[k] value → k (for deduplication in expandTables)
    indices: dict[int, int]
```

`entries[0]` is the premise itself (always the first element after reset).

#### retIndex bit format (64-bit int)

```
bits  0-11:  index of first predecessor in the table
bits 12-21:  index of second predecessor (nets only)
bits 22-31:  third predecessor
bits 32-41:  fourth predecessor
bits 42-51:  fifth predecessor
bits 52-60:  distance from root (chain length to this entry)
bit  61:     EXPANDED flag (entry came from another table during expandTables)
bit  62:     ON_TABLE flag (source was onTable, not offTable)
bit  63:     EXTENDED_TABLE flag (source was extendedTable)
```

Constants:
```python
_EXPANDED       = 1 << 61
_ON_TABLE       = 1 << 62
_EXTENDED_TABLE = 1 << 63

_IDX1_MASK  = 0xFFF          # bits 0-11
_IDX2_SHIFT = 12
_IDX3_SHIFT = 22
_IDX4_SHIFT = 32
_IDX5_SHIFT = 42
_DIST_SHIFT = 52
_DIST_MASK  = 0x1FF          # 9 bits
```

### Table arrays

```python
on_table:  list[TableEntry]   # length 810, index = cell*10 + cand
off_table: list[TableEntry]   # same
extended_table: list[TableEntry]   # for group nodes and ALS nodes
extended_table_map: dict[int, int] # entry value → index in extended_table
```

---

## Algorithm

### Step 1 — `fill_tables()`

For **chains** (`chainsOnly=True`): record only direct (single-step)
implications. For each empty cell and valid candidate `(cell, cand)`:

**onTable[cell*10+cand]** — premise: cand is SET in cell:
- Record premise as `entries[0]`
- Every other candidate in the cell → OFF
- Every other cell with `cand` in each shared house → OFF (weak link)
- If cand is the last remaining in a house (strong link, i.e. `free[house][cand] == 2`):
  → that other cell's cand → ON (no: only for offTable; onTable is one-way here)

**offTable[cell*10+cand]** — premise: cand is DELETED from cell:
- Record premise as `entries[0]`
- If cell has exactly 2 candidates → the other candidate → ON (naked single)
- For each house where `free[house][cand] == 2` → the only other cell's cand → ON (hidden single)

For **nets** (`chainsOnly=False`): deeper look-ahead using `get_table_entry()`.
Set/delete the candidate on a working copy of the grid, then run naked-single
and hidden-single detection iteratively (`anz_table_look_ahead` times, default 4)
and record all cascading implications with proper `ret_indices`.

### Step 2 — `fill_tables_with_group_nodes()`

Called after `fill_tables()` when `with_group_nodes=True`. Adds entries to
`extended_table` for each group node (GN), and cross-links those entries into
the main `on_table` / `off_table`.

The group nodes are the same ones computed in `chains.py`
(`_collect_group_nodes`). Re-use that function here.

For each GN (digit d, cells mask, buddies):

1. Create `onEntry` in `extended_table` (GN ON → every buddy cell's d → OFF;
   every same-house same-digit non-overlapping GN → OFF).
2. Create `offEntry` in `extended_table` (GN OFF → strong partner cells/GNs → ON;
   only when exactly one other d remains in the house).
3. Cross-link: every single cell with d that can see all GN cells gets
   a GN-OFF entry added to its `on_table` row (cell ON → GN OFF, via buddies).
4. Cross-link: every cell's `off_table` row that could trigger GN ON gets
   a GN-ON entry added.

### Step 3 — `fill_tables_with_als()` *(optional, controlled by `with_als_nodes`)*

Similar to group nodes but for ALS nodes. Re-uses the ALS list from `als.py`.
For each ALS and each entry candidate, create an `extended_table` entry and
wire it into the main tables. This is the most complex optional part; defer
to Phase 2 (see Implementation Phases below).

### Step 4 — `expand_tables(table)`

Compute the transitive closure: for each entry in `dest = table[i]`, look up
the source table for that entry (on/off/extended), and merge all of that
source's implications into `dest` (recursively, with distance tracking).

Key rules:
- Only non-expanded entries in the source are merged (skip if `src.is_expanded(k)`).
- If the entry already exists in `dest`:
  - Replace it if the new path is shorter (`srcBaseDistance + srcDistance < existing distance`)
  - Or if same distance but simpler node type (NORMAL < GROUP < ALS)
- Mark newly added entries as EXPANDED + record which source table they came from.

```python
def expand_tables(table, on_table, off_table, extended_table, extended_table_map):
    for dest in table:
        if dest.index == 0:
            continue
        j = 1
        while j < dest.index:
            entry_val = dest.entries[j]
            if entry_val == 0:
                break
            if dest.is_full():
                break
            # find source table
            node_type = chain_get_node_type(entry_val)
            if node_type != NORMAL_NODE:
                src_idx = extended_table_map[entry_val]
                src = extended_table[src_idx]
                is_extended = True; is_on = False
            else:
                src_table_idx = dest.get_cell_index(j) * 10 + dest.get_candidate(j)
                if dest.is_strong(j):
                    src = on_table[src_table_idx]
                    is_on = True
                else:
                    src = off_table[src_table_idx]
                    is_on = False
                is_extended = False
            base_dist = dest.get_distance(j)
            for k in range(1, src.index):
                if src.is_expanded(k):
                    continue
                # merge src.entries[k] into dest with distance tracking
                ...
            j += 1
```

### Step 5 — `check_forcing_chains()`

Run all four check types after tables are built and expanded:

```python
def check_forcing_chains():
    # 1. Contradiction from single chain
    for entry in (*on_table, *off_table):
        check_one_chain(entry)
    # 2. Verity from two chains (same premise cell, ON vs OFF)
    for i in range(810):
        check_two_chains(on_table[i], off_table[i])
    # 3. Verity across all candidates in a cell / house
    check_all_chains_for_house(None)                   # all cells
    check_all_chains_for_house(LINE_TEMPLATES)         # rows
    check_all_chains_for_house(COL_TEMPLATES)          # cols
    check_all_chains_for_house(BLOCK_TEMPLATES)        # boxes
```

---

## check_one_chain (Contradiction detection)

Given a single `TableEntry entry`, the premise is false if any of:

**A. Inverse of premise found**: Entry is strong (cand SET) and `offSets[cand]` contains the premise cell, OR entry is weak (cand DELETED) and `onSets[cand]` contains the premise cell.

**B. Same candidate SET and DELETED from same cell**: `onSets[d] & offSets[d] != 0` for any d.

**C. Two different values SET in same cell**: `onSets[d1] & onSets[d2] != 0` for d1 != d2.

**D. One value SET twice in a house**: For each house h and digit d, if `onSets[d] & house_mask` has more than 1 bit set → contradiction.

**E. Cell emptied**: For each non-set cell, if all candidates are either in `offSets` or not present, and the cell is not in any `onSets` → contradiction.

When a contradiction is found, the SolutionStep is:
- If premise is ON: `addCandidateToDelete(cell, cand)` (eliminate the premise)
- If premise is OFF: `addIndex(cell); addValue(cand)` (set the premise)

---

## check_two_chains (Verity from dual assumption)

Given `on = onTable[i]` and `off = offTable[i]` (same cell, same candidate):

- For each digit d: `result = on.onSets[d] & off.onSets[d]` → remove premise cell → if non-empty, those cells can be set to d (VERITY SET).
- For each digit d: `result = on.offSets[d] & off.offSets[d]` → remove premise cell → if non-empty, d can be deleted from those cells (VERITY DELETE).

---

## check_entry_list / check_all_chains_for_house (Verity from house/cell)

For a set of `TableEntry` objects (all candidates in a house for digit d, or all candidates in a cell):

- AND all `onSets[d]` together → if non-empty, those cells can be set to d
- AND all `offSets[d]` together → if non-empty, d can be deleted from those cells

---

## Deduplication / replace_or_copy_step

Every found step is keyed by its elimination/placement string. If a step with the same key already exists:
- Keep whichever has shorter total chain length.

This is `deletesMap` in Java → `deletes_map: dict[str, int]` in Python
(maps elimination key → index in `steps` list).

---

## Chain reconstruction (addChain / buildChain)

This is the most intricate part. Given a `TableEntry` and a target
(cell, cand, set/del), reconstruct the path from premise to target by
following `ret_indices` backwards.

Key considerations:
- Chains are built backwards then reversed.
- For nets: multiple predecessors exist (retIndex has 5 slots). Detect via
  `retIndex bits 12-51 != 0`. Each non-zero predecessor spawns a sub-chain.
- A "lasso" (cell appearing twice in the chain) terminates that path.
- The resulting `Chain` objects are stored in the `SolutionStep`.

**For Phase 1 (chains only), chain reconstruction is needed for output but
the chains are primarily used for HoDoKu compatibility. The eliminations
themselves can be validated without reconstructing the full chain path.**

---

## Sorting / TablingComparator

All found steps are sorted before picking the first. Sort key (ascending):
1. Number of candidates to delete + 1 if it's a placement (fewer = better)
2. Total chain length across all chains in the step (shorter = better)
3. Step type ordinal (CONTRADICTION before VERITY; CHAIN before NET)
4. First elimination cell index (lower = better)
5. First elimination digit (lower = better)

This order must be matched exactly for fidelity — the first step in
`steps` after sorting is what gets returned to the solve loop.

---

## Implementation Phases

### Phase 1 — Forcing Chains (no nets, no ALS nodes)

**Scope**: `chainsOnly=True`, `withGroupNodes=True`, `withAlsNodes=False`

This covers `FORCING_CHAIN_CONTRADICTION` and `FORCING_CHAIN_VERITY`.
These are the most common steps in hard puzzles and the ones HoDoKu uses
before resorting to Forcing Nets.

Steps:
1. `TableEntry` dataclass with `entries[]`, `ret_indices[]`, `on_sets[]`,
   `off_sets[]`, `indices` dict; helper methods for bit-packing.
2. `fill_tables()` (chains only path — direct implications only).
3. `fill_tables_with_group_nodes()` using `_collect_group_nodes()` from chains.py.
4. `expand_tables()`.
5. `check_one_chain()`, `check_two_chains()`, `check_entry_list()`,
   `check_all_chains_for_house()`.
6. Deduplication via `deletes_map`.
7. `TablingComparator` sort, return first step.
8. Chain reconstruction (simplified: walk ret_indices, produce Chain objects
   for the SolutionStep). Required for HoDoKu output format compatibility.

**Validation**: Find a puzzle where HoDoKu uses `Forcing Chain Contradiction`
or `Forcing Chain Verity`. Compare our step's elimination to HoDoKu's.
Use the brute-force test puzzles — they now run slowly due to missing tabling;
after Phase 1, they should solve with FC steps matching HoDoKu.

```bash
# Find clean FC puzzles (very common — most Extreme puzzles need it)
MSYS_NO_PATHCONV=1 java -jar hodoku/hodoku.jar /vp /o stdout <puzzle>
```

### Phase 2 — Forcing Nets

**Scope**: `chainsOnly=False`

Adds `get_table_entry()` — the deep look-ahead that sets/deletes a candidate
on a working copy of the grid and runs singles detection iteratively.
This requires a full clone of the Grid with candidate manipulation support.

`ret_indices` now carry multiple predecessor indices for proper net
reconstruction.

### Phase 3 — ALS Nodes in tabling

**Scope**: `withAlsNodes=True`

Adds `fill_tables_with_als()`. Re-uses `Als` objects from `als.py`.
Wires ALS nodes into the extended table with entry/exit candidates.

---

## Files to create/modify

| File | Change |
|------|--------|
| `src/hodoku/solver/tabling.py` | New file — `TablingSolver` class |
| `src/hodoku/solver/step_finder.py` | Add `TablingSolver` to dispatcher |
| `src/hodoku/core/scoring.py` | Verify FORCING_CHAIN_* entries in SOLVER_STEPS (they should already be present) |
| `tests/test_validate_tabling.py` | New validation test |

---

## Key Constants

```python
MAX_TABLE_ENTRY_LENGTH = 500  # Options.getInstance().getMaxTableEntryLength()
MAX_REC_DEPTH = 50            # for nets only
ANZ_TABLE_LOOK_AHEAD = 4      # Options.getInstance().getAnzTableLookAhead()
```

---

## Tricky Details

### Table index format
Java uses `cell * 10 + cand` (not `cell * 9 + (cand - 1)`). Candidates are
1-indexed. So `onTable[0]` is unused (cand 0 doesn't exist), `onTable[1]` is
cell 0 cand 1, `onTable[10]` is cell 1 cand 1, etc.

### `free[][]` array
`fillTables()` uses `sudoku.getFree()[constr][cand]` to determine how many
candidates remain in a house. Our `Grid` has `grid.free[house][cand]`. Check
that `constr` indices match `ALL_CONSTRAINTS_TEMPLATES` ordering.

### savedSudoku (nets only)
For nets, `fillTables` clones the grid at the start and restores it after
each candidate is processed. The `finder.getCandidates()` always uses the
**original** candidate sets (before any premise-induced eliminations).

### Extended table for group nodes
Group nodes do NOT live in the main `on_table`/`off_table` — they live in
`extended_table`, indexed by their packed chain entry value. The main tables
reference them, but they have their own `TableEntry` objects.

### Expand: do not expand expanded entries
When expanding, skip entries in `src` that are already expanded themselves
(they will be expanded transitively when we process `src`'s source). This
prevents exponential blowup.

### replaceOrCopyStep with `chainsOnly=False`
When `chainsOnly=False`, steps that come out as FORCING_CHAIN_* are upgraded
to FORCING_NET_* if `step.is_net()` (i.e., any chain has a branch — detected
from `ret_indices`).

### Ordering of eliminations in the step
As always: `sorted()` before calling `add_candidate_to_delete()`.

---

## Existing infrastructure to reuse

- `_collect_group_nodes()` from `chains.py` — identical group nodes needed
- `Als` / `alses` from `als.py` — for Phase 3
- Chain bit-packing constants from `chains.py` (NORMAL_NODE, GROUP_NODE, ALS_NODE)
- `BUDDIES`, `ALL_UNITS`, `CONSTRAINTS` from `core/grid.py`
- `LINE_TEMPLATES`, `COL_TEMPLATES`, `BLOCK_TEMPLATES` from `core/grid.py`
  (= `Sudoku2.LINE_TEMPLATES` etc.)
- `SolutionStep`, `Candidate` from `core/solution_step.py`
- `SolutionType.FORCING_CHAIN_CONTRADICTION` etc. from `core/types.py`
