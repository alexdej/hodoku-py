# Implementation Spec: Single-Digit Patterns, Wings, Coloring

Rows 9–11 from ROADMAP.md. Produced by reading Java source:
`SingleDigitPatternSolver.java`, `WingSolver.java`, `ColoringSolver.java`.

---

## Group A — Single-Digit Patterns (`solver/single_digit.py`)

### Key data structures
- `grid.candidate_sets[d]` — 81-bit int, cells containing digit d
- `grid.free[c][d]` — count of unsolved cells in constraint c with digit d
- `BUDDIES[cell]` — 81-bit int of all 20 peers
- `ALL_UNITS[c]`, `LINES`, `COLS`, `BLOCKS`

---

### Skyscraper

**Entry:** `get_step(SKYSCRAPER)` → `find_skyscraper()`

**Algorithm:**
1. For each digit 1-9:
2. Scan rows (constraints 0-8), then cols (constraints 9-17):
   - Collect units with **exactly 2 candidates** → record both cell indices
3. Try all pairs (i, j) where i < j from the same pass (rows or cols):
   - **Row mode**: check if one end shares the **same column** as a corresponding end in the other row
   - **Col mode**: check if one end shares the **same row**
   - If the two "linked" ends are in the same row/col but NOT the same box it would be X-Wing → skip
   - Free ends: `elim_set = BUDDIES[free_end_i] & BUDDIES[free_end_j] & candidate_sets[d]`
   - If non-empty → Skyscraper found

**SolutionStep:**
- `type`: `SKYSCRAPER`
- `values`: `[digit]`
- `indices`: `[end1_line, end2_line, end1_col, end2_col]`
- `candidates_to_delete`: cells in `elim_set` with `digit`

**Iteration order:** digits 1-9, rows first then cols, pairs in natural order (i < j).

---

### 2-String Kite

**Entry:** `get_step(TWO_STRING_KITE)` → `find_two_string_kite()`

**Algorithm:**
1. For each digit 1-9:
2. Collect units with exactly 2 candidates:
   - Lines (rows 0-8) → `line_pairs`
   - Cols (cols 9-17) → `col_pairs`
3. Try all pairs (one from lines, one from cols):
   - **Alignment**: reorder so the two "linked" cells share a block (4 possible alignments)
   - Free ends must differ from each other
   - `cross_index = cell at (row_of_col_free_end, col_of_row_free_end)`
   - If `cross_index` has the candidate → found

**SolutionStep:**
- `type`: `TWO_STRING_KITE`
- `values`: `[digit]`
- `indices`: `[row_free, col_free, row_block_end, col_block_end]`
- `fins`: `[row_block_end, col_block_end]` (the block-connected cells)
- `candidates_to_delete`: `[(cross_index, digit)]`

**Dual 2-String Kite:** two 2SK steps sharing the same fins (indices[2] and [3]) but different eliminations → merge into `DUAL_TWO_STRING_KITE`.

---

### Turbot Fish

Not in `SingleDigitPatternSolver.java` — likely subsumed by Skyscraper/2SK or absent.

---

### Empty Rectangle

**Entry:** `get_step(EMPTY_RECTANGLE)` → `find_empty_rectangle()`

**Static lookup tables (precomputed at import time):**
- `ER_OFFSETS[9]` — relative positions within a block for each ER pattern
- `ER_LINE_OFFSETS[9]`, `ER_COL_OFFSETS[9]` — row/col offsets for each pattern
- `ER_SETS[block][pattern]` — cells that must be empty for valid ER (as 81-bit mask)
- `ER_LINES[block][pattern]`, `ER_COLS[block][pattern]` — ER row/col for each block+pattern

**Algorithm:**
1. For each digit 1-9:
2. For each of 9 blocks:
   - Skip if block has fewer than 2 candidates
   - `block_cands = candidate_sets[d] & BLOCK_MASKS[b]`
   - For each ER pattern (0-8):
     - `ER_SETS[b][p] & block_cands` must be **empty**
     - Line part of block: `block_cands & LINE_MASKS[er_line] & ~COL_MASKS[er_col]` must be ≥1
     - Col part of block: `block_cands & COL_MASKS[er_col] & ~LINE_MASKS[er_line]` must be ≥1
     - Call `check_er(digit, er_line, er_col, block, block_cands)` for row and col

**check_er(d, er_line, er_col, block, block_cands):**
- For each cell in `er_line` not in block that has `d`:
  - Conjugate in `er_col`: `conj_set = candidate_sets[d] & COL_MASKS[er_col]`
  - If `conj_set` has exactly 2 cells, find the other one (`index2`)
  - For each candidate of `d` in the row of `index2`:
    - If in `er_col` but outside block → eliminate

**SolutionStep:**
- `type`: `EMPTY_RECTANGLE`
- `entity`: `BLOCK`, `entity_number`: `block + 1`
- `values`: `[digit]`
- `indices`: `[index, index2]` (the conjugate pair)
- `fins`: all cells in `block_cands`
- `candidates_to_delete`: `[(elim_cell, digit)]`

**Dual Empty Rectangle:** two ER steps on the same block with same fins but different eliminations → `DUAL_EMPTY_RECTANGLE`.

---

## Group B — Wings (`solver/wings.py`)

### Shared setup
Both XY-Wing and XYZ-Wing precompute:
- `bi_cells` — all cells with exactly 2 candidates
- `tri_cells` — all cells with exactly 3 candidates (XYZ only)

---

### XY-Wing

**Entry:** `get_step(XY_WING)` → `get_xy_wing()` → `get_wing(xyz=False)`

**Algorithm:**
1. Try all triples (i, j, k) from `bi_cells`, i < j < k:
   - Union of all three cell masks must have exactly 3 bits set (3 distinct candidates)
   - Try all 3 rotations as pivot: (i, j, k), (j, i, k), (k, j, i)
   - For each rotation: pivot must see **both** pincers
   - Shared candidate Z between pincers: `cell2 & cell3` must have exactly 1 bit
   - `elim_set = BUDDIES[p2] & BUDDIES[p3] & candidate_sets[Z]`
   - If non-empty → found

**SolutionStep:**
- `type`: `XY_WING`
- `values`: `[cand1, cand2, candZ]` (pivot's candidates + Z)
- `indices`: `[pivot, pincer1, pincer2]`
- `fins`: `[(pincer1, Z), (pincer2, Z)]`
- `candidates_to_delete`: cells in `elim_set` with Z

---

### XYZ-Wing

**Entry:** `get_step(XYZ_WING)` → `get_xyz_wing()` → `get_wing(xyz=True)`

**Algorithm:**
1. Try: pivot from `tri_cells`, both pincers from `bi_cells` (j < k):
   - Union of all three masks must have exactly 3 bits set
   - Pivot sees both pincers
   - Shared Z between pincers: `cell2 & cell3` has exactly 1 bit
   - `elim_set = BUDDIES[pivot] & BUDDIES[p2] & BUDDIES[p3] & candidate_sets[Z]`
   - Note: **includes pivot's buddies** (unlike XY-Wing)

**SolutionStep:**
- `type`: `XYZ_WING`
- `values`: `[cand1, cand2, cand3]` (all pivot candidates)
- `indices`: `[pivot, pincer1, pincer2]`
- `fins`: `[(pivot, Z), (pincer1, Z), (pincer2, Z)]`
- `candidates_to_delete`: cells in `elim_set` with Z

---

### W-Wing

**Entry:** `get_step(W_WING)` → `get_w_wing()`

**Algorithm:**
1. For each bivalue cell i:
   - Extract `cand1, cand2`
   - `pre1 = BUDDIES[i] & candidate_sets[cand1]`
   - `pre2 = BUDDIES[i] & candidate_sets[cand2]`
2. For each bivalue cell j > i with the **same candidate mask**:
   - Check `cand1`: `elim_set = pre1 & BUDDIES[j]`
   - If non-empty → call `check_link(cand1, cand2, i, j, elim_set)`
   - Check `cand2`: `elim_set = pre2 & BUDDIES[j]`
   - If non-empty → call `check_link(cand2, cand1, i, j, elim_set)`

**check_link(elim_cand, link_cand, i, j, elim_set):**
- For each of 27 constraints with `free[c][link_cand] == 2`:
  - The two cells in the conjugate pair for `link_cand` in constraint c:
    - `w_index1` = the one that sees i
    - `w_index2` = the one that sees j
    - If both found → W-Wing!

**SolutionStep:**
- `type`: `W_WING`
- `values`: `[cand1, cand2]`
- `indices`: `[i, j]`
- `fins`: `[(i, cand2), (j, cand2), (w_index1, cand2), (w_index2, cand2)]`
- `candidates_to_delete`: cells in `elim_set` with `elim_cand`

---

## Group C — Coloring (`solver/coloring.py`)

### Shared: `do_coloring(digit)`

Assigns colors (0/1) to all cells that can be reached through conjugate pairs for `digit`.

**Data structures:**
- `color_sets[d][pair_idx][color]` — 81-bit int of colored cells
- `color_pair_count[d]` — number of color groups for digit d
- `step_number[d]` — cached puzzle state (invalidate when step_number changes)

**Algorithm:**
1. Cache check: return if puzzle state unchanged
2. Reset color data for digit
3. Filter: `start_set = candidate_sets[d]`; remove cells not in any conjugate pair
   - A cell is in a conjugate pair if `free[c][d] == 2` for at least one of its 3 constraints
4. While `start_set` not empty:
   - Pop a cell, assign color 0, recurse
5. `color_recursive(cell, digit, color)`:
   - Add cell to `color_sets[d][pair_idx][color]`, remove from `start_set`
   - For each of cell's 3 constraints:
     - If `free[c][d] == 2`: find conjugate partner
     - Recurse with opposite color

**get_conjugate(cell, digit, constraint_idx):**
- `free[constraint_idx][digit]` must == 2
- `conj_set = candidate_sets[digit] & ALL_UNIT_MASKS[constraint_idx]`
- Return the cell in `conj_set` that is not `cell`

---

### Simple Colors Wrap (`SIMPLE_COLORS_WRAP`)

**Algorithm:**
1. `do_coloring(d)` for each digit
2. For each color pair:
   - For each color (0 and 1):
     - Check if any two cells in the same color see each other
     - If yes: eliminate ALL cells of that color

**SolutionStep:**
- `type`: `SIMPLE_COLORS_WRAP`
- `values`: `[digit]`
- `color_candidates`: `{cell: 0 or 1}` for all colored cells
- `candidates_to_delete`: all cells of the contradicting color with digit

---

### Simple Colors Trap (`SIMPLE_COLORS_TRAP`)

**Algorithm:**
1. `do_coloring(d)` for each digit
2. For each color pair (set0, set1):
   - For each (c0 ∈ set0, c1 ∈ set1):
     - `delete_set |= BUDDIES[c0] & BUDDIES[c1] & candidate_sets[d]`
   - Cells in `delete_set` see both colors → eliminate

**SolutionStep:**
- `type`: `SIMPLE_COLORS_TRAP`
- `values`: `[digit]`
- `color_candidates`: all colored cells mapped to color index
- `candidates_to_delete`: cells in `delete_set` with digit

---

### Multi-Colors 1 (`MULTI_COLORS_1`)

**Algorithm:**
1. `do_coloring(d)` for each digit
2. For each ordered pair of different color groups (i, j):
   - Check 4 sub-cases: (set_i0 vs set_j0), (set_i0 vs set_j1), (set_i1 vs set_j0), (set_i1 vs set_j1)
   - `check_multicolor2(setA, setB)`: any cell in setA sees any cell in setB?
   - If yes: the **opposite colors** (setA's complement, setB's complement) can be eliminated via trap logic:
     - `check_candidate_to_delete(opposite_of_A, opposite_of_B, d)` — cells that see both

**SolutionStep:**
- `type`: `MULTI_COLORS_1`
- `color_candidates`: set_i0 (0), set_i1 (1), set_j0 (2), set_j1 (3)

---

### Multi-Colors 2 (`MULTI_COLORS_2`)

**Algorithm:**
1. `do_coloring(d)` for each digit
2. For each ordered pair of color groups (i, j):
   - For each color (set_i0, set_i1):
     - `check_multicolor1(setA, set_j0, set_j1)`:
       - For each cell in setA: does it see **both** set_j0 AND set_j1?
       - If yes: eliminate ALL of setA

**SolutionStep:**
- `type`: `MULTI_COLORS_2`
- `color_candidates`: set_i0 (0), set_i1 (1), set_j0 (2), set_j1 (3)
- `candidates_to_delete`: all cells of the contradicting color (setA)
