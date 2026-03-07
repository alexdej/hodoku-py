# Spec: Grouped Nice Loop / Grouped AIC (Row 17 — GNL)

## Why GNL is needed before ALS validation

HoDoKu's solve order places Grouped Nice Loop at score 5650 and ALS-XZ at 5700.
Any puzzle that requires ALS also tends to have GNL available first (HoDoKu will
apply GNL, not ALS). Without GNL, our solver takes a different code path and
the solve sequences diverge — making ALS validation impossible with clean puzzles.

---

## What is a Group Node?

A **group node** (GN) for digit `d` is a set of 2 or 3 cells satisfying:
- All cells are in the **same block** (`block`)
- All cells are in the **same row** (`line`) OR the **same column** (`col`)
- All cells have candidate `d`

The group node represents the inference: *"at least one of these cells holds d."*

Group nodes are collected from the intersection of (row × block) and (col × block).
This is identical to how HoDoKu's `GroupNode.getGroupNodes()` works:

```java
getGroupNodesForHouseType(groupNodes, finder, Sudoku2.LINE_TEMPLATES);
getGroupNodesForHouseType(groupNodes, finder, Sudoku2.COL_TEMPLATES);
```

Each GN stores:
- `digit`: the candidate
- `cells`: bitmask of cells in the group (2 or 3 bits)
- `buddies`: `BUDDIES[c1] & BUDDIES[c2] (& BUDDIES[c3])` — cells that see ALL group cells
- `block`, `line` (or -1), `col` (or -1)
- `cell_list`: sorted list of cell indices

---

## Link Semantics

GNL extends the Nice Loop link graph with group nodes as additional chain nodes.
Links are bidirectional and symmetric.

### GN ↔ Single-cell links

**Weak link (GN ↔ cell c):**
- Condition: `c` is in `GN.buddies` (c sees all cells in GN) and `c` has digit `d`
- Meaning: if GN is ON (some cell has d), then c is OFF; and vice versa

**Strong link (GN ↔ cell c):**
- Condition: `c` has digit `d`, and GN + c are the **only** positions for d in some
  shared house (block, row, or column)
- Meaning: if GN is OFF (no cell in GN has d), then c must be ON; and vice versa

### GN ↔ GN links

For two group nodes GN1 and GN2 with the same digit, no cell overlap, and sharing
a house (same line, col, or block):

**Weak link (GN1 ↔ GN2):** Always present when they share a house with same digit.

**Strong link (GN1 ↔ GN2):** Present when GN1 + GN2 are the **only** positions for d
in their shared house (no additional single cells, no third group node in that house).

### Java source reference

`TablingSolver.fillTablesWithGroupNodes()` (lines 1929–2070) builds exactly these
implications. Key logic:
- `onEntry` (GN ON): eliminates all buddies + other same-house GNs (weak)
- `offEntry` (GN OFF): forces the one remaining position in each house (strong)
- Symmetric: each cell's `onTable`/`offTable` also gets entries for the GN

---

## Output Types

| Type | Code | Condition |
|------|------|-----------|
| `GROUPED_DISCONTINUOUS_NICE_LOOP` | `gdnl` | Same as DNL but chain contains ≥1 group node |
| `GROUPED_CONTINUOUS_NICE_LOOP` | `gcnl` | Same as CNL but chain contains ≥1 group node |
| `GROUPED_AIC` | `gaic` | Same as AIC but chain contains ≥1 group node |

All three are already present in `SolutionType` and share `STEP_CONFIG` with
`GROUPED_CONTINUOUS_NICE_LOOP` (score 5650, difficulty UNFAIR).

There is also a `GROUPED_NICE_LOOP` generic trigger (like `NICE_LOOP` for NL) that
maps to `GROUPED_CONTINUOUS_NICE_LOOP`'s config.

---

## Node Numbering in the Extended Link Graph

In the DFS link graph:
- **Nodes 0–728**: regular cell-candidate nodes, `node_id = cell * 9 + (cand - 1)`
- **Nodes 729+i**: group node i in the `group_nodes` list

Helper functions needed:
```python
def _nid_is_group(nid):   return nid >= 729
def _nid_cell(nid):        return nid // 9               # only valid if nid < 729
def _nid_cand(nid, gns):   return (nid % 9 + 1) if nid < 729 else gns[nid-729].digit
def _nid_cells_mask(nid, gns): return (1 << (nid//9)) if nid < 729 else gns[nid-729].cells
def _nid_buddies(nid, gns):    return BUDDIES[nid//9] if nid < 729 else gns[nid-729].buddies
```

---

## Loop Closure Rules

**Critical:** Only NORMAL_NODEs (single cells) can close a Nice Loop back to the
start. Group nodes **cannot** close the loop. This matches Java's `checkNiceLoops()`:

```java
if (tables[i].getNodeType(j) == Chain.NORMAL_NODE
        && tables[i].getCellIndex(j) == startIndex) {
    checkNiceLoop(tables[i], j);
}
```

In DFS terms:
- Start is always a regular cell node
- A loop closes only when we reach `(start_cell, start_cand)` as a **regular** node
- A group node that overlaps any occupied chain cell is a lasso (skip)

---

## Chain Occupied Tracking

Replace `chain_cells: set[int]` with `chain_occupied: int` (bitmask):
- When visiting a regular node at `cell`: add `1 << cell`
- When visiting a group node GN: add all of `GN.cells`

Lasso check:
- For regular node `c`: `(1 << c) & chain_occupied != 0`
- For group node GN: `GN.cells & chain_occupied != 0`

Backtrack: restore `chain_occupied` to its value before the visit.

---

## DNL/CNL/AIC Classification with Group Nodes

The same four-case classification used for regular NL applies:

| First link | Last link | same cand? | Result |
|------------|-----------|-----------|--------|
| weak | weak | yes | DNL: eliminate start_cand from start_cell |
| strong | strong | yes | DNL: set start_cand (eliminate all others) |
| mixed | mixed | no | DNL: eliminate the weak-link cand from start_cell |
| (other) | | | CNL |

For **CNL pass 2** (weak inter-cell link → eliminate from buddies):
- If the link endpoint is a regular node at `cell`: use `BUDDIES[cell]`
- If the link endpoint is a group node GN: use `GN.buddies` instead of `BUDDIES[cell]`

This is what Java does:
```java
Chain.getSNodeBuddies(nlChain[i-1], actCand, alses, tmpSet);
Chain.getSNodeBuddies(nlChain[i],   actCand, alses, tmpSet1);
// Chain.getSNodeBuddies() returns BUDDIES[cell] for NORMAL_NODE
// or the precomputed GN.buddies for GROUP_NODE
```

**CNL pass 1** (cell entered and exited via strong inter-cell links with weak
intra-cell between) does NOT apply to group nodes — group nodes have no intra-cell
weak links, so they can't be the middle of this pattern. The Java comment confirms:
> "group nodes and ALS cannot provide weak links in the cells through which they are reached"

---

## Detection: Is the chain grouped?

After finding a valid NL/CNL/AIC, check if any node in the chain is a group node.
If yes, upgrade the type:
- `DISCONTINUOUS_NICE_LOOP` → `GROUPED_DISCONTINUOUS_NICE_LOOP`
- `CONTINUOUS_NICE_LOOP` → `GROUPED_CONTINUOUS_NICE_LOOP`
- `AIC` → `GROUPED_AIC`

---

## Implementation Plan

### Files to change

1. **`src/hodoku/core/types.py`** — no changes needed (GROUPED types already present)

2. **`src/hodoku/core/scoring.py`** — no changes needed (GROUPED_CONTINUOUS_NICE_LOOP
   and its aliases already in STEP_CONFIG)

3. **`src/hodoku/solver/chains.py`** — the main work:
   - Add `_GroupNode` dataclass
   - Add `_collect_group_nodes(grid)` (≈30 lines)
   - Add `_build_gnl_links(grid, group_nodes)` (≈80 lines): runs existing
     `_build_nl_links` logic for 0–728 then adds GN entries at 729+
   - Refactor `_dfs_nl` to use node IDs (integers) instead of `(cell, cand)` tuples;
     replace `chain_cells: set` with `chain_occupied: int` bitmask
   - Modify `_check_nice_loop` for group-node-aware CNL pass 2 and type upgrade
   - Modify `_check_aic` for group-node-aware type upgrade
   - Modify `_find_nice_loop(grouped=False)` to accept a `grouped` flag

4. **`src/hodoku/solver/step_finder.py`** — add GROUPED types to `_CHAIN_TYPES`

### Dispatch

In `step_finder.py`:
```python
_CHAIN_TYPES = frozenset({
    SolutionType.CONTINUOUS_NICE_LOOP,
    SolutionType.DISCONTINUOUS_NICE_LOOP,
    SolutionType.AIC,
    SolutionType.GROUPED_CONTINUOUS_NICE_LOOP,
    SolutionType.GROUPED_DISCONTINUOUS_NICE_LOOP,
    SolutionType.GROUPED_AIC,
    ...
})
```

In `ChainSolver.get_step()`:
```python
if sol_type in (CNL, DNL, AIC, TURBOT, X_CHAIN, XY_CHAIN, REMOTE_PAIR):
    ...  # existing dispatch
if sol_type in (GROUPED_CNL, GROUPED_DNL, GROUPED_AIC):
    return self._find_nice_loop(grouped=True)
```

---

## Duplicate Link Handling

When building strong links for GN, the same target cell might qualify via both the
block check AND the row/col check. Java adds to the table multiple times (harmless
for BFS). In the DFS link graph, duplicates are also harmless (just re-explores the
same path). Accept duplicates for simplicity and fidelity.

---

## Testing

Use HoDoKu `/vp` on a puzzle and look for `gdnl`/`gcnl`/`gaic` steps. Then compare
our elimination sets (not full path — just the grouped NL eliminations across the
whole solve, sorted) against HoDoKu's. Same approach as `test_validate_aic.py`.

To find puzzles:
```bash
MSYS_NO_PATHCONV=1 java -Xmx512m -jar hodoku/hodoku.jar /s /sc gnl 2>/dev/null
```
