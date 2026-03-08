"""TablingSolver — Forcing Chain / Forcing Net solver.

Mirrors Java's TablingSolver. Builds implication tables for every premise
("candidate N is set/deleted in cell X"), expands them transitively, then
checks for contradictions and verities.

Phase 1: Forcing Chains only (chainsOnly=True, withGroupNodes=True).
Phase 2 (future): Forcing Nets.
Phase 3 (future): ALS nodes in tabling.
"""

from __future__ import annotations

import copy

from hodoku.core.grid import (
    ALL_UNIT_MASKS,
    BLOCK_MASKS,
    BUDDIES,
    CELL_CONSTRAINTS,
    COL_MASKS,
    DIGIT_MASKS,
    LINE_MASKS,
    Grid,
)
from hodoku.core.solution_step import Candidate, SolutionStep
from hodoku.core.types import SolutionType
from hodoku.solver.chain_utils import (
    GROUP_NODE,
    NORMAL_NODE,
    get_candidate,
    get_cell_index,
    get_cell_index2,
    get_cell_index3,
    get_node_type,
    is_strong,
    make_entry,
    make_entry_simple,
)
from hodoku.solver.chains import _collect_group_nodes, _GroupNode
from hodoku.solver.table_entry import MAX_TABLE_ENTRY_LENGTH, TableEntry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ALL_CELLS: int = (1 << 81) - 1


def _iter_bits(mask: int):
    """Yield set bit positions in ascending order."""
    while mask:
        lsb = mask & -mask
        yield lsb.bit_length() - 1
        mask ^= lsb


def _bit_count(mask: int) -> int:
    return mask.bit_count()


def _get_all_candidates(grid: Grid, cell: int) -> list[int]:
    """Return list of candidate digits for a cell (ascending)."""
    mask = grid.candidates[cell]
    result: list[int] = []
    for d in range(1, 10):
        if mask & DIGIT_MASKS[d]:
            result.append(d)
    return result


# ---------------------------------------------------------------------------
# TablingSolver
# ---------------------------------------------------------------------------

class TablingSolver:
    """Forcing Chain / Forcing Net solver using Trebor's Tables."""

    def __init__(self, grid: Grid) -> None:
        self.grid = grid

        # Main tables: index = cell*10 + cand (cands 1-indexed, so 810 entries)
        self.on_table: list[TableEntry] = [TableEntry() for _ in range(810)]
        self.off_table: list[TableEntry] = [TableEntry() for _ in range(810)]

        # Extended table for group nodes (and later ALS nodes)
        self.extended_table: list[TableEntry] = []
        self.extended_table_map: dict[int, int] = {}
        self.extended_table_index: int = 0

        # Group nodes cache
        self.group_nodes: list[_GroupNode] = []

        # Steps found in current run
        self.steps: list[SolutionStep] = []
        self.deletes_map: dict[str, int] = {}

        # Chain reconstruction workspace
        self._chain: list[int] = [0] * MAX_TABLE_ENTRY_LENGTH
        self._chain_index: int = 0
        self._tmp_chain: list[int] = [0] * MAX_TABLE_ENTRY_LENGTH
        self._mins: list[list[int]] = [[0] * MAX_TABLE_ENTRY_LENGTH for _ in range(200)]
        self._min_indexes: list[int] = [0] * 200
        self._act_min: int = 0
        self._lasso_set: int = 0  # bitmask
        self._tmp_chains: list[list[int]] = [[] for _ in range(9)]
        self._tmp_chains_index: int = 0

        # Temporary sets for checks
        self._global_step = SolutionStep(SolutionType.HIDDEN_SINGLE)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_step(self, sol_type: SolutionType) -> SolutionStep | None:
        """Find the best forcing chain/net step, if any."""
        if sol_type in (
            SolutionType.FORCING_CHAIN_CONTRADICTION,
            SolutionType.FORCING_CHAIN_VERITY,
        ):
            self.steps.clear()
            self._get_forcing_chains()
            if self.steps:
                self.steps.sort(key=_tabling_sort_key)
                return self.steps[0]
            return None
        if sol_type in (
            SolutionType.FORCING_NET_CONTRADICTION,
            SolutionType.FORCING_NET_VERITY,
        ):
            # Phase 2: not yet implemented
            return None
        return None

    def do_step(self, step: SolutionStep) -> None:
        """Apply a forcing chain/net step to the grid."""
        grid = self.grid
        if step.values:
            for i, value in enumerate(step.values):
                grid.set_cell(step.indices[i], value)
        else:
            for cand in step.candidates_to_delete:
                grid.del_candidate(cand.index, cand.value)

    # ------------------------------------------------------------------
    # Core algorithm
    # ------------------------------------------------------------------

    def _get_forcing_chains(self) -> None:
        """Build tables, expand, and check for forcing chains."""
        self.deletes_map.clear()

        # Step 1: Fill tables (chains only — direct implications)
        self._fill_tables()

        # Step 2: Add group nodes
        self._fill_tables_with_group_nodes()

        # Step 3: Expand tables (transitive closure)
        self._expand_tables(self.on_table)
        self._expand_tables(self.off_table)

        # Step 4: Check for contradictions and verities
        self._check_forcing_chains()

    # ------------------------------------------------------------------
    # Step 1: Fill tables — chains only (direct implications)
    # ------------------------------------------------------------------

    def _fill_tables(self) -> None:
        """Populate on_table and off_table with direct implications.

        Chains-only path: record only immediate consequences of each premise.
        """
        grid = self.grid

        # Reset all tables
        for i in range(810):
            self.on_table[i].reset()
            self.off_table[i].reset()
        self.extended_table_map.clear()
        self.extended_table_index = 0

        for i in range(81):
            if grid.values[i] != 0:
                continue
            for cand in range(1, 10):
                if not (grid.candidates[i] & DIGIT_MASKS[cand]):
                    continue

                ti = i * 10 + cand
                on_entry = self.on_table[ti]
                off_entry = self.off_table[ti]

                # Record the premise itself
                on_entry.add_entry_simple(i, cand, True)
                off_entry.add_entry_simple(i, cand, False)

                # ON premise: all other candidates in the cell → OFF
                # OFF premise (bivalue): the other candidate → ON
                cands = _get_all_candidates(grid, i)
                for other_cand in cands:
                    if other_cand == cand:
                        continue
                    on_entry.add_entry_simple(i, other_cand, False)
                    if len(cands) == 2:
                        off_entry.add_entry_simple(i, other_cand, True)

                # ON premise: for each house, other cells with cand → OFF
                # Strong link (free==2): also add ON entry (matches Java exactly)
                peers_with_cand = grid.candidate_sets[cand] & ~(1 << i)
                for constr in CELL_CONSTRAINTS[i]:
                    anz_cands = grid.free[constr][cand]
                    if anz_cands < 2:
                        continue
                    peers_in_house = peers_with_cand & ALL_UNIT_MASKS[constr]
                    if not peers_in_house:
                        continue

                    # Weak links: all peers lose cand
                    for cell in _iter_bits(peers_in_house):
                        on_entry.add_entry_simple(cell, cand, False)

                    if anz_cands == 2:
                        # Strong link: the single remaining peer
                        # Java adds this to onTable (see TablingSolver.java:1858)
                        peer = (peers_in_house & -peers_in_house).bit_length() - 1
                        on_entry.add_entry_simple(peer, cand, True)

    # ------------------------------------------------------------------
    # Step 2: Fill tables with group nodes
    # ------------------------------------------------------------------

    def _get_next_extended_table_entry(self, index: int) -> TableEntry:
        """Ensure extended_table has an entry at ``index``, reset and return it."""
        while index >= len(self.extended_table):
            self.extended_table.append(TableEntry())
        entry = self.extended_table[index]
        entry.reset()
        return entry

    def _fill_tables_with_group_nodes(self) -> None:
        """Add group node implications to the extended table and cross-link
        them into on_table / off_table.

        Mirrors TablingSolver.fillTablesWithGroupNodes() in Java.
        """
        grid = self.grid
        self.group_nodes = _collect_group_nodes(grid)
        gns = self.group_nodes

        for i, gn in enumerate(gns):
            # Create ON entry in extended table
            on_entry = self._get_next_extended_table_entry(self.extended_table_index)
            on_entry.add_entry(
                gn.index1, gn.digit, True,
                cell_index2=gn.index2, cell_index3=gn.index3,
                node_type=GROUP_NODE,
            )
            self.extended_table_map[on_entry.entries[0]] = self.extended_table_index
            self.extended_table_index += 1

            # Create OFF entry in extended table
            off_entry = self._get_next_extended_table_entry(self.extended_table_index)
            off_entry.add_entry(
                gn.index1, gn.digit, False,
                cell_index2=gn.index2, cell_index3=gn.index3,
                node_type=GROUP_NODE,
            )
            self.extended_table_map[off_entry.entries[0]] = self.extended_table_index
            self.extended_table_index += 1

            # Candidates that can see the group node (same digit, in buddies)
            visible = grid.candidate_sets[gn.digit] & gn.buddies
            if visible:
                # GN ON → every visible candidate is OFF
                # Each visible candidate's onTable gets a GN OFF entry
                for cell in _iter_bits(visible):
                    on_entry.add_entry_simple(cell, gn.digit, False)
                    tmp = self.on_table[cell * 10 + gn.digit]
                    tmp.add_entry(
                        gn.index1, gn.digit, False,
                        cell_index2=gn.index2, cell_index3=gn.index3,
                        node_type=GROUP_NODE,
                    )

                # GN OFF → if only one candidate remains in a house,
                # that candidate is ON
                # Check block
                block_visible = visible & BLOCK_MASKS[gn.block]
                if block_visible and _bit_count(block_visible) == 1:
                    cell = (block_visible & -block_visible).bit_length() - 1
                    off_entry.add_entry_simple(cell, gn.digit, True)
                    tmp = self.off_table[cell * 10 + gn.digit]
                    tmp.add_entry(
                        gn.index1, gn.digit, True,
                        cell_index2=gn.index2, cell_index3=gn.index3,
                        node_type=GROUP_NODE,
                    )

                # Check line or col
                if gn.line != -1:
                    line_visible = visible & LINE_MASKS[gn.line]
                else:
                    line_visible = visible & COL_MASKS[gn.col]
                if line_visible and _bit_count(line_visible) == 1:
                    cell = (line_visible & -line_visible).bit_length() - 1
                    off_entry.add_entry_simple(cell, gn.digit, True)
                    tmp = self.off_table[cell * 10 + gn.digit]
                    tmp.add_entry(
                        gn.index1, gn.digit, True,
                        cell_index2=gn.index2, cell_index3=gn.index3,
                        node_type=GROUP_NODE,
                    )

            # Group-node-to-group-node connections
            line_count = 0
            line1_index = -1
            col_count = 0
            col1_index = -1
            block_count = 0
            block1_index = -1

            for j, gn2 in enumerate(gns):
                if j == i:
                    continue
                if gn.digit != gn2.digit:
                    continue
                # Check for overlap
                if gn.cells & gn2.cells:
                    continue

                # Same line → GN ON turns other GN OFF
                if gn.line != -1 and gn.line == gn2.line:
                    line_count += 1
                    if line_count == 1:
                        line1_index = j
                    on_entry.add_entry(
                        gn2.index1, gn.digit, False,
                        cell_index2=gn2.index2, cell_index3=gn2.index3,
                        node_type=GROUP_NODE,
                    )

                # Same col
                if gn.col != -1 and gn.col == gn2.col:
                    col_count += 1
                    if col_count == 1:
                        col1_index = j
                    on_entry.add_entry(
                        gn2.index1, gn.digit, False,
                        cell_index2=gn2.index2, cell_index3=gn2.index3,
                        node_type=GROUP_NODE,
                    )

                # Same block
                if gn.block == gn2.block:
                    block_count += 1
                    if block_count == 1:
                        block1_index = j
                    on_entry.add_entry(
                        gn2.index1, gn.digit, False,
                        cell_index2=gn2.index2, cell_index3=gn2.index3,
                        node_type=GROUP_NODE,
                    )

            # If only one other GN in a house and no additional single
            # candidates → GN OFF turns other GN ON
            if line_count == 1:
                gn2 = gns[line1_index]
                house_cands = LINE_MASKS[gn.line] & grid.candidate_sets[gn.digit]
                house_cands &= ~gn.cells
                house_cands &= ~gn2.cells
                if not house_cands:
                    off_entry.add_entry(
                        gn2.index1, gn.digit, True,
                        cell_index2=gn2.index2, cell_index3=gn2.index3,
                        node_type=GROUP_NODE,
                    )

            if col_count == 1:
                gn2 = gns[col1_index]
                house_cands = COL_MASKS[gn.col] & grid.candidate_sets[gn.digit]
                house_cands &= ~gn.cells
                house_cands &= ~gn2.cells
                if not house_cands:
                    off_entry.add_entry(
                        gn2.index1, gn.digit, True,
                        cell_index2=gn2.index2, cell_index3=gn2.index3,
                        node_type=GROUP_NODE,
                    )

            if block_count == 1:
                gn2 = gns[block1_index]
                house_cands = BLOCK_MASKS[gn.block] & grid.candidate_sets[gn.digit]
                house_cands &= ~gn.cells
                house_cands &= ~gn2.cells
                if not house_cands:
                    off_entry.add_entry(
                        gn2.index1, gn.digit, True,
                        cell_index2=gn2.index2, cell_index3=gn2.index3,
                        node_type=GROUP_NODE,
                    )

    # ------------------------------------------------------------------
    # Step 3: Expand tables (transitive closure)
    # ------------------------------------------------------------------

    def _expand_tables(self, table: list[TableEntry]) -> None:
        """Expand every entry in *table* by merging implications from source
        tables.

        Mirrors TablingSolver.expandTables() in Java.
        """
        on_table = self.on_table
        off_table = self.off_table
        ext_table = self.extended_table
        ext_map = self.extended_table_map

        for i in range(len(table)):
            dest = table[i]
            if dest.index == 0:
                continue

            # Walk entries (excluding premise at 0)
            j = 1
            while j < len(dest.entries):
                entry_val = dest.entries[j]
                if entry_val == 0:
                    break
                if dest.is_full():
                    break

                # Find the source table for this entry
                is_from_extended = False
                is_from_on = False

                if get_node_type(entry_val) != NORMAL_NODE:
                    # Group/ALS node → look up in extended table
                    src_idx = ext_map.get(entry_val)
                    if src_idx is None:
                        j += 1
                        continue
                    src = ext_table[src_idx]
                    src_table_index = src_idx
                    is_from_extended = True
                else:
                    src_table_index = dest.get_cell_index(j) * 10 + dest.get_candidate(j)
                    if dest.is_strong(j):
                        src = on_table[src_table_index]
                        is_from_on = True
                    else:
                        src = off_table[src_table_index]

                if src.index == 0:
                    j += 1
                    continue

                # Expand: merge non-expanded entries from src into dest
                src_base_distance = dest.get_distance(j)

                for k in range(1, src.index):
                    if src.is_expanded(k):
                        continue

                    src_distance = src.get_distance(k)
                    src_entry = src.entries[k]

                    if src_entry in dest.indices:
                        # Entry already exists in dest — check if shorter path
                        org_index = dest.indices[src_entry]
                        if dest.is_expanded(org_index):
                            new_dist = src_base_distance + src_distance
                            old_dist = dest.get_distance(org_index)
                            if (old_dist > new_dist or
                                    (old_dist == new_dist and
                                     dest.get_node_type(org_index) > src.get_node_type(k))):
                                # Shorter or simpler path → rewrite
                                dest.ret_indices[org_index] = _make_ret_index_single(src_table_index)
                                dest.set_expanded(org_index)
                                if is_from_extended:
                                    dest.set_extended_table(org_index)
                                elif is_from_on:
                                    dest.set_on_table(org_index)
                                dest._set_distance(org_index, new_dist)
                    else:
                        # New entry — add it
                        if get_node_type(src_entry) == NORMAL_NODE:
                            dest.add_entry_with_ri(
                                src.get_cell_index(k),
                                src.get_candidate(k),
                                src.is_strong(k),
                                src_table_index,
                            )
                        else:
                            dest.add_entry(
                                get_cell_index(src_entry),
                                get_candidate(src_entry),
                                is_strong(src_entry),
                                cell_index2=get_cell_index2(src_entry),
                                cell_index3=get_cell_index3(src_entry),
                                node_type=get_node_type(src_entry),
                                ri1=src_table_index,
                            )

                        new_idx = dest.index - 1
                        dest.set_expanded(new_idx)
                        if is_from_extended:
                            dest.set_extended_table(new_idx)
                        elif is_from_on:
                            dest.set_on_table(new_idx)
                        dest._set_distance(new_idx, src_base_distance + src_distance)

                j += 1

    # ------------------------------------------------------------------
    # Step 4: Check for contradictions and verities (Stage 4)
    # ------------------------------------------------------------------

    def _check_forcing_chains(self) -> None:
        """Run all forcing chain/net checks after tables are built."""
        # Contradiction from single chain
        for i in range(810):
            self._check_one_chain(self.on_table[i])
            self._check_one_chain(self.off_table[i])

        # Verity from two chains (same cell+cand, ON vs OFF)
        for i in range(810):
            self._check_two_chains(self.on_table[i], self.off_table[i])

        # Verity from all candidates in a cell / house
        self._check_all_chains_for_house(None)
        self._check_all_chains_for_house(LINE_MASKS)
        self._check_all_chains_for_house(COL_MASKS)
        self._check_all_chains_for_house(BLOCK_MASKS)

    def _check_one_chain(self, entry: TableEntry) -> None:
        """Check a single table entry for contradictions.

        Six checks mirroring TablingSolver.checkOneChain():
        1. Inverse of premise in same table
        2. Same candidate set AND deleted in same cell
        3. Two different values set in same cell
        4. Same value set twice in one house
        5. Cell emptied (all candidates deleted)
        6. All instances of candidate deleted from house
        """
        if entry.index == 0:
            return

        grid = self.grid
        premise_cell = entry.get_cell_index(0)
        premise_cand = entry.get_candidate(0)
        premise_strong = entry.is_strong(0)

        # --- Check 1: chain contains inverse of premise ---
        if premise_strong:
            # ON premise but OFF for same cand in same cell → contradiction
            if entry.off_sets[premise_cand] & (1 << premise_cell):
                self._global_step.reset()
                self._global_step.type = SolutionType.FORCING_CHAIN_CONTRADICTION
                self._global_step.add_candidate_to_delete(premise_cell, premise_cand)
                self._global_step.entity = 0  # CELL
                self._reset_tmp_chains()
                self._add_chain(entry, premise_cell, premise_cand, False)
                self._replace_or_copy_step()
        else:
            # OFF premise but ON for same cand in same cell → contradiction
            if entry.on_sets[premise_cand] & (1 << premise_cell):
                self._global_step.reset()
                self._global_step.type = SolutionType.FORCING_CHAIN_CONTRADICTION
                self._global_step.add_index(premise_cell)
                self._global_step.add_value(premise_cand)
                self._global_step.entity = 0
                self._reset_tmp_chains()
                self._add_chain(entry, premise_cell, premise_cand, True)
                self._replace_or_copy_step()

        # --- Check 2: same candidate set AND deleted in same cell ---
        for i in range(len(entry.on_sets)):
            tmp = entry.on_sets[i] & entry.off_sets[i]
            if tmp:
                self._global_step.reset()
                self._global_step.type = SolutionType.FORCING_CHAIN_CONTRADICTION
                if premise_strong:
                    self._global_step.add_candidate_to_delete(premise_cell, premise_cand)
                else:
                    self._global_step.add_index(premise_cell)
                    self._global_step.add_value(premise_cand)
                self._global_step.entity = 0
                first_cell = (tmp & -tmp).bit_length() - 1
                self._global_step.entity_number = first_cell
                self._reset_tmp_chains()
                self._add_chain(entry, first_cell, i, False)
                self._add_chain(entry, first_cell, i, True)
                self._replace_or_copy_step()

        # --- Check 3: two different values set in same cell ---
        for i in range(1, 10):
            for j in range(i + 1, 10):
                tmp = entry.on_sets[i] & entry.on_sets[j]
                if tmp:
                    self._global_step.reset()
                    self._global_step.type = SolutionType.FORCING_CHAIN_CONTRADICTION
                    if premise_strong:
                        self._global_step.add_candidate_to_delete(premise_cell, premise_cand)
                    else:
                        self._global_step.add_index(premise_cell)
                        self._global_step.add_value(premise_cand)
                    self._global_step.entity = 0
                    first_cell = (tmp & -tmp).bit_length() - 1
                    self._global_step.entity_number = first_cell
                    self._reset_tmp_chains()
                    self._add_chain(entry, first_cell, i, True)
                    self._add_chain(entry, first_cell, j, True)
                    self._replace_or_copy_step()

        # --- Check 4: same value set twice in one house ---
        self._check_house_set(entry, LINE_MASKS, 1)   # LINE
        self._check_house_set(entry, COL_MASKS, 2)     # COL
        self._check_house_set(entry, BLOCK_MASKS, 3)   # BLOCK

        # --- Check 5: cell emptied (all candidates deleted) ---
        # For each cell: if all its candidates are in off_sets (and not
        # counteracted by on_sets or already-set values), it's emptied.
        # Mirrors Java: AND(offSets[i] | ~candidateSets[i]) for i=1..9,
        # then remove cells with ON values and already-solved cells.
        tmp_all = _ALL_CELLS
        for i in range(1, 10):
            or_not = entry.off_sets[i] | (_ALL_CELLS & ~grid.candidate_sets[i])
            tmp_all &= or_not
        for i in range(10):
            tmp_all &= ~entry.on_sets[i]
        # Remove already-solved cells
        solved_mask = 0
        for cell in range(81):
            if grid.values[cell] != 0:
                solved_mask |= 1 << cell
        tmp_all &= ~solved_mask

        if tmp_all:
            for cell in _iter_bits(tmp_all):
                self._global_step.reset()
                self._global_step.type = SolutionType.FORCING_CHAIN_CONTRADICTION
                if premise_strong:
                    self._global_step.add_candidate_to_delete(premise_cell, premise_cand)
                else:
                    self._global_step.add_index(premise_cell)
                    self._global_step.add_value(premise_cand)
                self._global_step.entity = 0
                self._global_step.entity_number = cell
                self._reset_tmp_chains()
                cands = _get_all_candidates(grid, cell)
                for c in cands:
                    self._add_chain(entry, cell, c, False)
                self._replace_or_copy_step()

        # --- Check 6: all instances of candidate deleted from house ---
        self._check_house_del(entry, LINE_MASKS, 1)
        self._check_house_del(entry, COL_MASKS, 2)
        self._check_house_del(entry, BLOCK_MASKS, 3)

    def _check_house_set(
        self, entry: TableEntry, house_masks: tuple[int, ...], entity_type: int,
    ) -> None:
        """Check if an assumption leads to same value set twice in one house."""
        premise_cell = entry.get_cell_index(0)
        premise_cand = entry.get_candidate(0)
        premise_strong = entry.is_strong(0)

        for i in range(1, 10):
            for j, h_mask in enumerate(house_masks):
                tmp = h_mask & entry.on_sets[i]
                if _bit_count(tmp) > 1:
                    self._global_step.reset()
                    self._global_step.type = SolutionType.FORCING_CHAIN_CONTRADICTION
                    if premise_strong:
                        self._global_step.add_candidate_to_delete(premise_cell, premise_cand)
                    else:
                        self._global_step.add_index(premise_cell)
                        self._global_step.add_value(premise_cand)
                    self._global_step.entity = entity_type
                    self._global_step.entity_number = j
                    self._reset_tmp_chains()
                    for cell in _iter_bits(tmp):
                        self._add_chain(entry, cell, i, True)
                    self._replace_or_copy_step()

    def _check_house_del(
        self, entry: TableEntry, house_masks: tuple[int, ...], entity_type: int,
    ) -> None:
        """Check if all instances of a candidate are deleted from a house."""
        grid = self.grid
        premise_cell = entry.get_cell_index(0)
        premise_cand = entry.get_candidate(0)
        premise_strong = entry.is_strong(0)

        for i in range(1, 10):
            for j, h_mask in enumerate(house_masks):
                tmp = h_mask & grid.candidate_sets[i]
                if tmp and (tmp & entry.off_sets[i]) == tmp:
                    self._global_step.reset()
                    self._global_step.type = SolutionType.FORCING_CHAIN_CONTRADICTION
                    if premise_strong:
                        self._global_step.add_candidate_to_delete(premise_cell, premise_cand)
                    else:
                        self._global_step.add_index(premise_cell)
                        self._global_step.add_value(premise_cand)
                    self._global_step.entity = entity_type
                    self._global_step.entity_number = j
                    self._reset_tmp_chains()
                    for cell in _iter_bits(tmp):
                        self._add_chain(entry, cell, i, False)
                    self._replace_or_copy_step()

    def _check_two_chains(self, on: TableEntry, off: TableEntry) -> None:
        """Check ON/OFF pair for verities.

        If both ON and OFF premises for the same cell/candidate lead to the
        same conclusion, that conclusion must be true.
        """
        if on.index == 0 or off.index == 0:
            return

        premise_cell = on.get_cell_index(0)

        # Check onSets: both lead to same value SET in same cell
        for i in range(1, 10):
            tmp = on.on_sets[i] & off.on_sets[i] & ~(1 << premise_cell)
            if tmp:
                for cell in _iter_bits(tmp):
                    self._global_step.reset()
                    self._global_step.type = SolutionType.FORCING_CHAIN_VERITY
                    self._global_step.add_index(cell)
                    self._global_step.add_value(i)
                    self._reset_tmp_chains()
                    self._add_chain(on, cell, i, True)
                    self._add_chain(off, cell, i, True)
                    self._replace_or_copy_step()

        # Check offSets: both lead to same candidate DELETED from same cell
        for i in range(1, 10):
            tmp = on.off_sets[i] & off.off_sets[i] & ~(1 << premise_cell)
            if tmp:
                for cell in _iter_bits(tmp):
                    self._global_step.reset()
                    self._global_step.type = SolutionType.FORCING_CHAIN_VERITY
                    self._global_step.add_candidate_to_delete(cell, i)
                    self._reset_tmp_chains()
                    self._add_chain(on, cell, i, False)
                    self._add_chain(off, cell, i, False)
                    self._replace_or_copy_step()

    def _check_all_chains_for_house(
        self,
        house_masks: tuple[int, ...] | None,
    ) -> None:
        """Check all candidates in cells/houses for verities.

        If ALL candidates for a cell (or all instances of a digit in a house)
        lead to the same conclusion, that conclusion must be true.
        """
        grid = self.grid

        if house_masks is None:
            # Check per cell: all candidates in the cell
            for i in range(81):
                if grid.values[i] != 0:
                    continue
                entry_list: list[TableEntry] = []
                cands = _get_all_candidates(grid, i)
                for c in cands:
                    entry_list.append(self.on_table[i * 10 + c])
                self._check_entry_list(entry_list)
        else:
            # Check per house: all cells with candidate j in house i
            for i, h_mask in enumerate(house_masks):
                for j in range(1, 10):
                    tmp = h_mask & grid.candidate_sets[j]
                    if tmp:
                        entry_list = []
                        for cell in _iter_bits(tmp):
                            entry_list.append(self.on_table[cell * 10 + j])
                        self._check_entry_list(entry_list)

    def _check_entry_list(self, entry_list: list[TableEntry]) -> None:
        """AND all on_sets/off_sets across entry_list; anything remaining is a verity."""
        if not entry_list:
            return

        # AND all on_sets and off_sets
        tmp_on = [0] * 10
        tmp_off = [0] * 10
        for idx, entry in enumerate(entry_list):
            for j in range(1, 10):
                if idx == 0:
                    tmp_on[j] = entry.on_sets[j]
                    tmp_off[j] = entry.off_sets[j]
                else:
                    tmp_on[j] &= entry.on_sets[j]
                    tmp_off[j] &= entry.off_sets[j]

        for j in range(1, 10):
            if tmp_on[j]:
                for cell in _iter_bits(tmp_on[j]):
                    self._global_step.reset()
                    self._global_step.type = SolutionType.FORCING_CHAIN_VERITY
                    self._global_step.add_index(cell)
                    self._global_step.add_value(j)
                    self._reset_tmp_chains()
                    for entry in entry_list:
                        self._add_chain(entry, cell, j, True)
                    self._replace_or_copy_step()

            if tmp_off[j]:
                for cell in _iter_bits(tmp_off[j]):
                    self._global_step.reset()
                    self._global_step.type = SolutionType.FORCING_CHAIN_VERITY
                    self._global_step.add_candidate_to_delete(cell, j)
                    self._reset_tmp_chains()
                    for entry in entry_list:
                        self._add_chain(entry, cell, j, False)
                    self._replace_or_copy_step()

    # ------------------------------------------------------------------
    # Chain reconstruction
    # ------------------------------------------------------------------

    def _reset_tmp_chains(self) -> None:
        """Reset chain workspace before building chains for a step."""
        self._tmp_chains_index = 0

    def _build_chain(self, entry: TableEntry, cell_index: int, cand: int, is_set: bool) -> None:
        """Build a chain from the implication back to the premise.

        Populates self._chain / self._chain_index with entries in reverse
        order (from implication back to premise). Also populates self._mins
        for net branches.

        Mirrors TablingSolver.buildChain() in Java.
        """
        self._chain_index = 0
        chain_entry = make_entry_simple(cell_index, cand, is_set)

        # Find the entry in the table
        index = -1
        for i in range(entry.index):
            if entry.entries[i] == chain_entry:
                index = i
                break

        if index == -1:
            return

        # Reset net data structures
        self._act_min = 0
        for i in range(len(self._min_indexes)):
            self._min_indexes[i] = 0

        # Build the main chain
        self._chain_index = self._build_chain_inner(
            entry, index, self._chain, False
        )

        # Build net parts
        min_index = 0
        while min_index < self._act_min:
            entry_val = self._mins[min_index][0]
            try:
                ei = entry.get_entry_index_by_value(entry_val)
            except KeyError:
                min_index += 1
                continue
            self._min_indexes[min_index] = self._build_chain_inner(
                entry, ei, self._mins[min_index], True
            )
            min_index += 1

    def _build_chain_inner(
        self,
        entry: TableEntry,
        entry_index: int,
        act_chain: list[int],
        is_min: bool,
    ) -> int:
        """Walk retIndices backwards to construct a chain.

        Returns the number of entries written to act_chain.
        Mirrors the inner buildChain() in Java.
        """
        act_chain_index = 0
        act_chain[act_chain_index] = entry.entries[entry_index]
        act_chain_index += 1
        first_entry_index = entry_index
        expanded = False
        org_entry = entry

        while first_entry_index != 0 and act_chain_index < len(act_chain):
            if entry.is_expanded(first_entry_index):
                # Jump to the source table
                src_idx = org_entry.get_ret_index(first_entry_index, 0)
                if entry.is_extended_table(first_entry_index):
                    entry = self.extended_table[src_idx]
                elif entry.is_on_table(first_entry_index):
                    entry = self.on_table[src_idx]
                else:
                    entry = self.off_table[src_idx]
                expanded = True
                # Find this entry's value in the source table
                try:
                    first_entry_index = entry.get_entry_index_by_value(
                        org_entry.entries[first_entry_index]
                    )
                except KeyError:
                    break

            tmp_entry_index = first_entry_index
            for i in range(5):
                ret_idx = entry.get_ret_index(tmp_entry_index, i)
                if i == 0:
                    first_entry_index = ret_idx
                    if ret_idx < len(entry.entries):
                        act_chain[act_chain_index] = entry.entries[ret_idx]
                        act_chain_index += 1
                    else:
                        break
                else:
                    # Net branch (multiple inference)
                    if ret_idx != 0 and not is_min:
                        if self._act_min < len(self._mins):
                            self._mins[self._act_min][0] = entry.entries[ret_idx]
                            self._min_indexes[self._act_min] = 1
                            self._act_min += 1

            if expanded and first_entry_index == 0:
                # Jumped to another table and reached its start → jump back
                ret_entry = entry.entries[0]
                entry = org_entry
                try:
                    first_entry_index = entry.get_entry_index_by_value(ret_entry)
                except KeyError:
                    break
                expanded = False

        return act_chain_index

    def _add_chain(
        self, entry: TableEntry, cell_index: int, cand: int, is_set: bool,
    ) -> None:
        """Build and add a chain to the global step.

        Mirrors TablingSolver.addChain() — builds the chain backwards then
        reverses it, checking for lassos along the way.
        """
        if self._tmp_chains_index >= len(self._tmp_chains):
            return

        self._build_chain(entry, cell_index, cand, is_set)

        if self._chain_index == 0:
            return

        # Reverse the chain and interleave net branches (mins)
        j = 0
        for i in range(self._chain_index - 1, -1, -1):
            old_entry = self._chain[i]
            self._tmp_chain[j] = old_entry
            j += 1
            # Check for net branches (mins)
            for k in range(self._act_min):
                if self._mins[k][self._min_indexes[k] - 1] == old_entry:
                    # This min connects here — add it (reversed, negated)
                    for m in range(self._min_indexes[k] - 2, -1, -1):
                        self._tmp_chain[j] = -self._mins[k][m]
                        j += 1
                    # Sentinel for net branch end
                    self._tmp_chain[j] = -(1 << 31)  # Integer.MIN_VALUE equivalent
                    j += 1

        if j > 0:
            # Copy to the step's chain list
            chain_data = self._tmp_chain[:j]
            if self._tmp_chains_index < len(self._tmp_chains):
                self._tmp_chains[self._tmp_chains_index] = list(chain_data)
            self._global_step.chains.append(list(chain_data))
            self._tmp_chains_index += 1

    # ------------------------------------------------------------------
    # Dedup and step management
    # ------------------------------------------------------------------

    def _adjust_type(self, step: SolutionStep) -> None:
        """Upgrade FORCING_CHAIN to FORCING_NET if the step is a net."""
        if step.is_net():
            if step.type == SolutionType.FORCING_CHAIN_CONTRADICTION:
                step.type = SolutionType.FORCING_NET_CONTRADICTION
            elif step.type == SolutionType.FORCING_CHAIN_VERITY:
                step.type = SolutionType.FORCING_NET_VERITY

    def _replace_or_copy_step(self) -> None:
        """Add globalStep to steps list, deduplicating by candidate string.

        If a step with the same eliminations/placements already exists and has
        shorter chains, keep the old one. Otherwise replace or add.
        """
        step = self._global_step
        self._adjust_type(step)

        # Determine the dedup key
        if step.candidates_to_delete:
            del_key = step.get_candidate_string()
        elif step.indices:
            del_key = step.get_single_candidate_string()
        else:
            return  # no effect

        old_index = self.deletes_map.get(del_key)
        if old_index is not None:
            old_step = self.steps[old_index]
            if old_step.get_chain_length() > step.get_chain_length():
                # New chain is shorter → replace
                self.steps[old_index] = copy.deepcopy(step)
            return

        # New step
        self.deletes_map[del_key] = len(self.steps)
        self.steps.append(copy.deepcopy(step))


# ---------------------------------------------------------------------------
# Sorting key for tabling steps (TablingComparator)
# ---------------------------------------------------------------------------

def _tabling_sort_key(step: SolutionStep) -> tuple:
    """Sort key matching Java's TablingComparator.

    Steps with placements sort before eliminations.
    Within each group: more eliminations/placements first,
    then shorter chain length, then by cell/digit.
    """
    has_placement = len(step.indices) > 0
    if has_placement:
        return (
            0,                          # placements first
            -len(step.indices),         # more placements = better
            _chain_length(step),        # shorter chains = better
            step.indices[0] if step.indices else 0,
            step.values[0] if step.values else 0,
        )
    else:
        return (
            1,                          # eliminations second
            -len(step.candidates_to_delete),  # more elims = better
            _chain_length(step),
            step.candidates_to_delete[0].index if step.candidates_to_delete else 0,
            step.candidates_to_delete[0].value if step.candidates_to_delete else 0,
        )


def _chain_length(step: SolutionStep) -> int:
    """Total chain length across all chains in the step."""
    total = 0
    for chain in step.chains:
        total += len(chain)
    return total


# ---------------------------------------------------------------------------
# Helper for expand_tables — single-index retIndex
# ---------------------------------------------------------------------------

def _make_ret_index_single(index: int) -> int:
    """Create a retIndex with only index1 set (no other predecessors)."""
    if index > 4096:
        index = 0
    return index
