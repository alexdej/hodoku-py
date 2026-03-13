"""TablingSolver — Forcing Chain / Forcing Net solver.

Mirrors Java's TablingSolver. Builds implication tables for every premise
("candidate N is set/deleted in cell X"), expands them transitively, then
checks for contradictions and verities.

Also implements Nice Loop / AIC detection via the tabling framework,
including support for ALS nodes in grouped chains.
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
from hodoku.core.solution_step import SolutionStep
from hodoku.core.types import SolutionType
from hodoku.solver.als import Als, _collect_alses
from hodoku.solver.chain_utils import (
    ALS_NODE,
    GROUP_NODE,
    NORMAL_NODE,
    get_als_index,
    get_candidate,
    get_cell_index,
    get_cell_index2,
    get_cell_index3,
    get_lower_als_index,
    get_higher_als_index,
    get_node_type,
    is_strong,
    make_entry,
    make_entry_als,
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


def _first_bit(mask: int) -> int:
    """Return the index of the lowest set bit."""
    return (mask & -mask).bit_length() - 1


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

        # ALS cache (populated by _fill_tables_with_als)
        self._alses: list[Als] = []

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

        # Chain cell tracking (for nice loop lasso detection)
        self._chain_set: int = 0  # 81-bit bitmask of cells in current chain
        self._build_chain_set: int = 0  # cells in main chain (for min early termination)

        # Nice loop filter flag
        self._only_grouped_nice_loops: bool = False

        # Config: whether ALS nodes are allowed in tabling chains
        # (mirrors Java Options.isAllowAlsInTablingChains())
        self._config_allow_als_in_tabling: bool = False

        # Net mode flag: when True, forces all CHAIN types to NET types
        self._nets_mode: bool = False

        # Temporary sets for checks
        self._global_step = SolutionStep(SolutionType.HIDDEN_SINGLE)

        # candidatesAllowed: per-digit bitmask of cells where digit is allowed
        # based solely on placed values (ignoring technique eliminations).
        # Matches Java's SudokuStepFinder.getCandidatesAllowed().
        self._candidates_allowed: list[int] = [0] * 10

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_step(self, sol_type: SolutionType) -> SolutionStep | None:
        """Find the best step of the given type, or None.

        Handles Nice Loops, AICs, Forcing Chains, and Forcing Nets.
        Mirrors Java TablingSolver.getStep().
        """
        if sol_type in (
            SolutionType.CONTINUOUS_NICE_LOOP,
            SolutionType.DISCONTINUOUS_NICE_LOOP,
            SolutionType.AIC,
        ):
            return self._get_nice_loops(with_group_nodes=False, with_als_nodes=False)
        if sol_type in (
            SolutionType.GROUPED_CONTINUOUS_NICE_LOOP,
            SolutionType.GROUPED_DISCONTINUOUS_NICE_LOOP,
            SolutionType.GROUPED_AIC,
        ):
            return self._get_nice_loops(
                with_group_nodes=True,
                with_als_nodes=self._config_allow_als_in_tabling,
            )
        if sol_type in (
            SolutionType.FORCING_CHAIN_CONTRADICTION,
            SolutionType.FORCING_CHAIN_VERITY,
        ):
            self.steps.clear()
            self._get_forcing_chains()
            if self.steps:
                self.steps.sort(key=_fc_sort_key)
                return self.steps[0]
            return None
        if sol_type in (
            SolutionType.FORCING_NET_CONTRADICTION,
            SolutionType.FORCING_NET_VERITY,
        ):
            self.steps.clear()
            self._get_forcing_nets()
            if self.steps:
                self.steps.sort(key=_fc_sort_key)
                return self.steps[0]
            return None
        return None

    def find_all(self, sol_type: SolutionType) -> list[SolutionStep]:
        """Return all steps of the given type."""
        if sol_type in (
            SolutionType.CONTINUOUS_NICE_LOOP,
            SolutionType.DISCONTINUOUS_NICE_LOOP,
            SolutionType.AIC,
        ):
            return self.find_all_nice_loops(
                with_group_nodes=False, with_als_nodes=False,
                only_grouped=False, target_type=sol_type,
            )
        if sol_type in (
            SolutionType.GROUPED_CONTINUOUS_NICE_LOOP,
            SolutionType.GROUPED_DISCONTINUOUS_NICE_LOOP,
            SolutionType.GROUPED_AIC,
        ):
            return self.find_all_nice_loops(
                with_group_nodes=True,
                with_als_nodes=self._config_allow_als_in_tabling,
                only_grouped=True, target_type=sol_type,
            )
        if sol_type in (
            SolutionType.FORCING_CHAIN_CONTRADICTION,
            SolutionType.FORCING_CHAIN_VERITY,
        ):
            self.steps.clear()
            self._get_forcing_chains()
            return [s for s in self.steps if s.type == sol_type]
        if sol_type in (
            SolutionType.FORCING_NET_CONTRADICTION,
            SolutionType.FORCING_NET_VERITY,
        ):
            self.steps.clear()
            self._get_forcing_nets()
            return [s for s in self.steps if s.type == sol_type]
        return []

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

    def _get_nice_loops(
        self,
        with_group_nodes: bool,
        with_als_nodes: bool,
    ) -> SolutionStep | None:
        """Find the best nice loop / AIC step.

        Mirrors Java TablingSolver.getNiceLoops() → doGetNiceLoops().
        """
        self.steps.clear()
        self.deletes_map.clear()
        self._only_grouped_nice_loops = False

        self._fill_tables()
        if with_group_nodes:
            self._fill_tables_with_group_nodes()
        if with_als_nodes:
            self._fill_tables_with_als()

        self._expand_tables(self.on_table)
        self._expand_tables(self.off_table)

        self._check_nice_loops(self.on_table)
        self._check_nice_loops(self.off_table)
        self._check_aics(self.off_table)

        if self.steps:
            self.steps.sort(key=_tabling_sort_key)
            return self.steps[0]
        return None

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

    def _get_forcing_nets(self) -> None:
        """Build tables, expand, and check for forcing nets.

        Mirrors Java TablingSolver.doGetForcingChains() with chainsOnly=false.
        Net mode uses grid cloning + look-ahead singles detection to find
        more implications than chain-only mode.
        """
        self.deletes_map.clear()
        self._nets_mode = True

        try:
            self._fill_tables_nets()
            self._fill_tables_with_group_nodes()
            if self._config_allow_als_in_tabling:
                self._fill_tables_with_als()

            self._expand_tables(self.on_table)
            self._expand_tables(self.off_table)

            self._check_forcing_chains()
        finally:
            self._nets_mode = False

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
                        # Strong link: if cand is OFF, the other candidate
                        # has to be ON (Java: offTable line 1862, NOT onTable)
                        peer = (peers_in_house & -peers_in_house).bit_length() - 1
                        off_entry.add_entry_simple(peer, cand, True)

    # ------------------------------------------------------------------
    # Step 1b: Fill tables — nets (look-ahead)
    # ------------------------------------------------------------------

    _ANZ_TABLE_LOOK_AHEAD: int = 4

    def _fill_tables_nets(self) -> None:
        """Populate on_table/off_table using net-mode (look-ahead).

        Clones the grid, applies each premise, then runs naked/hidden single
        detection for ANZ_TABLE_LOOK_AHEAD rounds to find deeper implications.
        Mirrors Java fillTables() with chainsOnly=false.
        """
        grid = self.grid

        # Reset tables
        for i in range(810):
            self.on_table[i].reset()
            self.off_table[i].reset()
        self.extended_table_map.clear()
        self.extended_table_index = 0

        saved_grid = grid.clone()

        for i in range(81):
            if saved_grid.values[i] != 0:
                continue
            cands = _get_all_candidates(saved_grid, i)
            for cand in cands:
                # ON: set the cell
                grid.set(saved_grid)
                self._get_table_entry_net(self.on_table[i * 10 + cand],
                                          i, cand, True, saved_grid)
                # OFF: delete the candidate
                grid.set(saved_grid)
                self._get_table_entry_net(self.off_table[i * 10 + cand],
                                          i, cand, False, saved_grid)

        grid.set(saved_grid)

    def _get_table_entry_net(
        self, entry: TableEntry, cell_index: int, cand: int,
        is_set: bool, saved_grid: Grid,
    ) -> None:
        """Fill a single table entry using net-mode look-ahead.

        Mirrors Java getTableEntry(): applies premise, then looks ahead
        for naked/hidden singles.
        """
        grid = self.grid

        if is_set:
            self._set_cell_net(cell_index, cand, entry, saved_grid,
                               get_ret_indices=False, naked_single=False)
        else:
            grid.del_candidate(cell_index, cand)
            entry.add_entry_simple(cell_index, cand, False)
            # If cell becomes naked single, set it
            if grid.candidates[cell_index] and not (
                grid.candidates[cell_index] & (grid.candidates[cell_index] - 1)
            ):
                set_cand = grid.candidates[cell_index].bit_length()
                self._set_cell_net(cell_index, set_cand, entry, saved_grid,
                                   get_ret_indices=False, naked_single=True)

        # Look-ahead rounds: find naked/hidden singles
        for _ in range(self._ANZ_TABLE_LOOK_AHEAD):
            singles = self._find_all_singles_net(grid)
            if not singles:
                break
            for s_cell, s_cand, is_naked in singles:
                self._set_cell_net(s_cell, s_cand, entry, saved_grid,
                                   get_ret_indices=True, naked_single=is_naked)

    def _set_cell_net(
        self, cell_index: int, cand: int, entry: TableEntry,
        saved_grid: Grid, get_ret_indices: bool, naked_single: bool,
    ) -> None:
        """Set a cell during net-mode table filling and record implications.

        Mirrors Java setCell(). Records:
        - ON entry for the set cell
        - OFF entries for all buddy cells that have the candidate
        - OFF entries for all other candidates in the cell
        """
        grid = self.grid

        # Find all candidates that will be eliminated by setting this cell
        # Use original (saved) candidates for the buddy check
        peers_with_cand = saved_grid.candidate_sets[cand] & BUDDIES[cell_index]
        peers_with_cand &= ~(1 << cell_index)

        # Get other candidates in the cell (from current working grid, before set)
        other_cands = _get_all_candidates(grid, cell_index)

        # Find retIndices if needed (for look-ahead steps)
        ri = [0, 0, 0, 0, 0]
        if get_ret_indices:
            if naked_single:
                # Naked single: depends on elimination of all other candidates
                cell_cands = _get_all_candidates(saved_grid, cell_index)
                ri_idx = 0
                for c in cell_cands:
                    if c == cand and ri_idx < 5:
                        continue
                    idx = entry.get_entry_index(cell_index, False, c)
                    if ri_idx < 5:
                        ri[ri_idx] = idx
                        ri_idx += 1
            else:
                # Hidden single: depends on elimination of cand from house peers
                # Find house with smallest number of candidates in current grid
                # (Java uses sudoku.getFree(), not savedSudoku — must be done
                # before the cell is set)
                best_free = 999
                best_constr = CELL_CONSTRAINTS[cell_index][0]
                for constr in CELL_CONSTRAINTS[cell_index]:
                    f = grid.free[constr][cand]
                    if f < best_free:
                        best_free = f
                        best_constr = constr
                # Get all original candidates in that house (excluding self)
                house_peers = saved_grid.candidate_sets[cand] & ALL_UNIT_MASKS[best_constr]
                house_peers &= ~(1 << cell_index)
                ri_idx = 0
                for cell in _iter_bits(house_peers):
                    if ri_idx >= 5:
                        break
                    idx = entry.get_entry_index(cell, False, cand)
                    ri[ri_idx] = idx
                    ri_idx += 1

        # Now actually set the cell
        ret_index = entry.index
        grid.set_cell(cell_index, cand)

        # ON entry for the set operation
        if get_ret_indices:
            entry.add_entry(cell_index, cand, True,
                            ri1=ri[0], ri2=ri[1], ri3=ri[2],
                            ri4=ri[3], ri5=ri[4])
        else:
            entry.add_entry_simple(cell_index, cand, True)

        # OFF entries for all buddy cells that can see this cell (same candidate)
        for cell in _iter_bits(peers_with_cand):
            entry.add_entry_with_ri(cell, cand, False, ret_index)

        # OFF entries for all other candidates in the cell
        for c in other_cands:
            if c != cand:
                entry.add_entry_with_ri(cell_index, c, False, ret_index)

    @staticmethod
    def _find_all_singles_net(grid: Grid) -> list[tuple[int, int, bool]]:
        """Find all naked and hidden singles in the grid.

        Returns list of (cell, digit, is_naked_single).

        Uses the grid's ns_queue/hs_queue to match Java's queue-based
        discovery order (SimpleSolver.findAllNakedSingles / findAllHiddenSingles).
        The order matters because singles are applied sequentially and each
        setCell modifies the grid for subsequent singles.
        """
        results: list[tuple[int, int, bool]] = []

        # Naked singles — iterate nsQueue
        for cell, digit in grid.ns_queue:
            if grid.values[cell] == 0:
                results.append((cell, digit, True))

        # Hidden singles — iterate hsQueue
        # Java uses singleFound[] to avoid duplicate cells
        single_found: set[int] = set()
        for cell, digit in grid.hs_queue:
            if grid.values[cell] == 0 and cell not in single_found:
                # Verify the constraint still has free==1 for this digit
                for constr in CELL_CONSTRAINTS[cell]:
                    if grid.free[constr][digit] == 1:
                        results.append((cell, digit, False))
                        single_found.add(cell)
                        break

        return results

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
    # Step 2b: Fill tables with ALS nodes
    # ------------------------------------------------------------------

    def _get_als_table_entry(
        self, entry_cell: int, als_index: int, cand: int,
    ) -> TableEntry | None:
        """Look up an existing ALS table entry in the extended table."""
        entry = make_entry_als(entry_cell, als_index, cand, False, ALS_NODE)
        idx = self.extended_table_map.get(entry)
        if idx is not None:
            return self.extended_table[idx]
        return None

    def _fill_tables_with_als(self) -> None:
        """Add ALS node implications to the extended table and cross-link
        them into on_table / off_table.

        Mirrors TablingSolver.fillTablesWithAls() in Java.
        """
        grid = self.grid
        alses = _collect_alses(grid)
        # Skip single-cell ALSes (bivalue cells, handled as normal nodes)
        self._alses = [als for als in alses if als.indices.bit_count() >= 2]
        alses = self._alses

        gns = self.group_nodes

        for i, als in enumerate(alses):
            for j in range(1, 10):
                if not als.indices_per_cand[j]:
                    continue

                # Check if there are possible eliminations for any other digit k
                als_elims: list[int] = [0] * 10  # [k] = bitmask of eliminable cells
                eliminations_present = False
                for k in range(1, 10):
                    if k == j:
                        continue
                    if not als.indices_per_cand[k]:
                        continue
                    # Cells with candidate k that see ALL ALS cells with k
                    als_elims[k] = grid.candidate_sets[k] & als.buddies_per_cand[k]
                    if als_elims[k]:
                        eliminations_present = True

                if not eliminations_present:
                    continue

                # Create or find the ALS off-table entry
                entry_cell = _first_bit(als.indices_per_cand[j])
                off_entry = self._get_als_table_entry(entry_cell, i, j)
                if off_entry is None:
                    off_entry = self._get_next_extended_table_entry(
                        self.extended_table_index
                    )
                    off_entry.add_entry(
                        entry_cell, j, False,
                        cell_index2=get_lower_als_index(i),
                        cell_index3=get_higher_als_index(i),
                        node_type=ALS_NODE,
                    )
                    self.extended_table_map[off_entry.entries[0]] = (
                        self.extended_table_index
                    )
                    self.extended_table_index += 1

                # Put the ALS into onTables of all entry candidates:
                # find cells with candidate j that see all ALS cells with j
                trigger_cells = grid.candidate_sets[j] & als.buddies_per_cand[j]
                als_entry_val = make_entry_als(
                    entry_cell, i, j, False, ALS_NODE
                )

                for cell in _iter_bits(trigger_cells):
                    # Add ALS to cell's ON table
                    on_te = self.on_table[cell * 10 + j]
                    on_te.add_entry(
                        entry_cell, j, False,
                        cell_index2=get_lower_als_index(i),
                        cell_index3=get_higher_als_index(i),
                        node_type=ALS_NODE,
                    )

                    # Every group node containing this cell that doesn't
                    # overlap the ALS and sees all ALS cells with j
                    for gn in gns:
                        if gn.digit != j:
                            continue
                        if not (gn.cells & (1 << cell)):
                            continue
                        # Check overlap with ALS
                        if gn.cells & als.indices:
                            continue
                        # All ALS cells with j must be in group node's buddies
                        if (als.indices_per_cand[j] & gn.buddies) != als.indices_per_cand[j]:
                            continue
                        # Look up the group node ON entry in extended table
                        gn_on_val = make_entry(
                            gn.index1, gn.index2, gn.index3,
                            j, True, GROUP_NODE,
                        )
                        gn_ext_idx = self.extended_table_map.get(gn_on_val)
                        if gn_ext_idx is None:
                            continue
                        gn_te = self.extended_table[gn_ext_idx]
                        if als_entry_val in gn_te.indices:
                            continue
                        # Add ALS to group node's ON table
                        gn_te.add_entry(
                            entry_cell, j, False,
                            cell_index2=get_lower_als_index(i),
                            cell_index3=get_higher_als_index(i),
                            node_type=ALS_NODE,
                        )

                # Record elimination targets in the ALS off-table
                chain_penalty = als.get_chain_penalty()
                for k in range(1, 10):
                    if not als_elims[k]:
                        continue
                    for cell in _iter_bits(als_elims[k]):
                        off_entry.add_entry(cell, k, False, penalty=chain_penalty)
                    # If a group node is a subset of the eliminations
                    for gn in gns:
                        if gn.digit != k:
                            continue
                        if (gn.cells & als_elims[k]) != gn.cells:
                            continue
                        off_entry.add_entry(
                            gn.index1, k, False,
                            cell_index2=gn.index2, cell_index3=gn.index3,
                            node_type=GROUP_NODE,
                            penalty=chain_penalty,
                        )

                # Trigger other non-overlapping ALSes
                for k_idx, k_als in enumerate(alses):
                    if k_idx == i:
                        continue
                    if als.indices & k_als.indices:
                        continue  # overlapping
                    for l in range(1, 10):  # noqa: E741
                        if not als_elims[l]:
                            continue
                        if not k_als.indices_per_cand[l]:
                            continue
                        # alsEliminations must contain all k_als cells with l
                        if (k_als.indices_per_cand[l] & als_elims[l]) != k_als.indices_per_cand[l]:
                            continue
                        # Create table for triggered ALS if needed
                        k_entry_cell = _first_bit(k_als.indices_per_cand[l])
                        if self._get_als_table_entry(k_entry_cell, k_idx, l) is None:
                            new_entry = self._get_next_extended_table_entry(
                                self.extended_table_index
                            )
                            new_entry.add_entry(
                                k_entry_cell, l, False,
                                cell_index2=get_lower_als_index(k_idx),
                                cell_index3=get_higher_als_index(k_idx),
                                node_type=ALS_NODE,
                            )
                            self.extended_table_map[new_entry.entries[0]] = (
                                self.extended_table_index
                            )
                            self.extended_table_index += 1
                        # Link from current ALS to triggered ALS
                        off_entry.add_entry(
                            k_entry_cell, l, False,
                            cell_index2=get_lower_als_index(k_idx),
                            cell_index3=get_higher_als_index(k_idx),
                            node_type=ALS_NODE,
                            penalty=chain_penalty,
                        )

                # Forcings: if a buddy cell has only 1 candidate left
                for cell in _iter_bits(als.buddies):
                    if grid.values[cell] != 0:
                        continue
                    cand_count = grid.candidates[cell].bit_count()
                    if cand_count <= 2:
                        continue
                    remaining = grid.candidates[cell]
                    for l in range(1, 10):  # noqa: E741
                        if als_elims[l] and (als_elims[l] & (1 << cell)):
                            remaining &= ~DIGIT_MASKS[l]
                    if remaining.bit_count() == 1:
                        forced_digit = remaining.bit_length()
                        off_entry.add_entry(
                            cell, forced_digit, True,
                            penalty=chain_penalty + 1,
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

    def _init_candidates_allowed(self) -> None:
        """Compute candidatesAllowed — cells where each digit is allowed
        based solely on placed values (ignoring technique eliminations).

        Matches Java's SudokuStepFinder.initCandidatesAllowed().
        """
        grid = self.grid
        full = _ALL_CELLS
        empty_cells = full
        for d in range(1, 10):
            self._candidates_allowed[d] = full
        for i in range(81):
            if grid.values[i] != 0:
                self._candidates_allowed[grid.values[i]] &= ~BUDDIES[i]
                empty_cells &= ~(1 << i)
        for d in range(1, 10):
            self._candidates_allowed[d] &= empty_cells

    def _check_forcing_chains(self) -> None:
        """Run all forcing chain/net checks after tables are built."""
        self._init_candidates_allowed()

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
        premise_cell = entry.get_cell_index(0)
        premise_cand = entry.get_candidate(0)
        premise_strong = entry.is_strong(0)

        for i in range(1, 10):
            for j, h_mask in enumerate(house_masks):
                # Java uses candidatesAllowed (based on placed values only),
                # not candidates (which reflects technique eliminations).
                tmp = h_mask & self._candidates_allowed[i]
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

        # Build the main chain — collect cells in _build_chain_set for
        # early termination when building net parts (mirrors Java's tmpSetC)
        self._build_chain_set = 0
        self._chain_index = self._build_chain_inner(
            entry, index, self._chain, False
        )

        # Build net parts — reuse _build_chain_set so mins stop when
        # they reach a cell already in the main chain
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

        Uses self._build_chain_set (an 81-bit cell bitmask) to track cells
        in the main chain.  When *is_min* is True the walk stops early as
        soon as it reaches a cell that is already in the main chain AND the
        exact entry matches an entry in self._chain (mirrors Java's
        chainSet pre-selection + linear search).
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

                    if not is_min:
                        # Main chain: record cell in chain_set
                        cell_idx = get_cell_index(entry.entries[ret_idx])
                        self._build_chain_set |= 1 << cell_idx
                        node_type = get_node_type(entry.entries[ret_idx])
                        if node_type == GROUP_NODE:
                            ci2 = get_cell_index2(entry.entries[ret_idx])
                            if ci2 != -1:
                                self._build_chain_set |= 1 << ci2
                            ci3 = get_cell_index3(entry.entries[ret_idx])
                            if ci3 != -1:
                                self._build_chain_set |= 1 << ci3
                        elif node_type == ALS_NODE:
                            als_idx = get_als_index(entry.entries[ret_idx])
                            if als_idx < len(self._alses):
                                self._build_chain_set |= self._alses[als_idx].indices
                    else:
                        # Min chain: check if we've reached the main chain
                        cell_idx = get_cell_index(entry.entries[ret_idx])
                        if self._build_chain_set & (1 << cell_idx):
                            # Pre-selection hit — search main chain for exact match
                            entry_val = entry.entries[ret_idx]
                            for j in range(self._chain_index):
                                if self._chain[j] == entry_val:
                                    return act_chain_index
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
        is_nice_loop: bool = False, is_aic: bool = False,
    ) -> None:
        """Build and add a chain to the global step.

        Mirrors TablingSolver.addChain() — builds the chain backwards then
        reverses it, checking for lassos along the way.

        is_nice_loop: lasso detection allowing start cell at both ends.
        is_aic: stricter lasso detection (no return to start cell allowed).
        """
        if self._tmp_chains_index >= len(self._tmp_chains):
            return

        self._build_chain(entry, cell_index, cand, is_set)

        if self._chain_index == 0:
            return

        j = 0
        if is_nice_loop or is_aic:
            lasso_cells: int = 0  # 81-bit bitmask
            # For nice loops: first and second chain entries must differ in cell
            if is_nice_loop:
                c0 = get_cell_index(self._chain[0])
                c1 = get_cell_index(self._chain[1]) if self._chain_index > 1 else -1
                if c0 == c1:
                    return

        last_cell_index = -1
        last_cell_entry = -1
        first_cell_index = get_cell_index(self._chain[self._chain_index - 1])

        # Reverse the chain and check for lassos
        for i in range(self._chain_index - 1, -1, -1):
            old_entry = self._chain[i]
            new_cell_index = get_cell_index(old_entry)

            if is_nice_loop or is_aic:
                if lasso_cells & (1 << new_cell_index):
                    return  # lasso detected

                # Add last cell to lasso set (skip start cell for nice loops)
                if last_cell_index != -1 and (last_cell_index != first_cell_index or is_aic):
                    lasso_cells |= 1 << last_cell_index
                    # Group nodes: add all cells
                    if get_node_type(last_cell_entry) == GROUP_NODE:
                        ci2 = get_cell_index2(last_cell_entry)
                        if ci2 != -1:
                            lasso_cells |= 1 << ci2
                        ci3 = get_cell_index3(last_cell_entry)
                        if ci3 != -1:
                            lasso_cells |= 1 << ci3
                    elif get_node_type(last_cell_entry) == ALS_NODE:
                        als_idx = get_als_index(last_cell_entry)
                        if als_idx < len(self._alses):
                            lasso_cells |= self._alses[als_idx].indices

            last_cell_index = new_cell_index
            last_cell_entry = old_entry
            self._tmp_chain[j] = old_entry
            j += 1
            # Check for net branches (mins)
            for k in range(self._act_min):
                if self._mins[k][self._min_indexes[k] - 1] == old_entry:
                    for m in range(self._min_indexes[k] - 2, -1, -1):
                        self._tmp_chain[j] = -self._mins[k][m]
                        j += 1
                    self._tmp_chain[j] = -(1 << 31)
                    j += 1

        if j > 0:
            chain_data = self._tmp_chain[:j]
            if self._tmp_chains_index < len(self._tmp_chains):
                self._tmp_chains[self._tmp_chains_index] = list(chain_data)
            self._global_step.chains.append(list(chain_data))
            self._tmp_chains_index += 1

            # Collect chain cells for continuous nice loop elimination checking
            if is_nice_loop:
                self._chain_set = 0
                for ci in range(j):
                    ev = chain_data[ci]
                    if ev < 0:
                        continue  # net branch marker
                    self._chain_set |= 1 << get_cell_index(ev)
                    nt = get_node_type(ev)
                    if nt == GROUP_NODE:
                        ci2 = get_cell_index2(ev)
                        if ci2 != -1:
                            self._chain_set |= 1 << ci2
                        ci3 = get_cell_index3(ev)
                        if ci3 != -1:
                            self._chain_set |= 1 << ci3
                    elif nt == ALS_NODE:
                        aidx = get_als_index(ev)
                        if aidx < len(self._alses):
                            self._chain_set |= self._alses[aidx].indices

    # ------------------------------------------------------------------
    # Dedup and step management
    # ------------------------------------------------------------------

    def _adjust_type(self, step: SolutionStep) -> None:
        """Upgrade FORCING_CHAIN to FORCING_NET if the step is a net.

        Mirrors Java's adjustType() which checks step.isNet() — true when
        any chain entry is negative (net branch marker).
        """
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

        # In net mode, discard steps that are still CHAIN type (not promoted
        # to NET by adjustType). These were already found during chain mode.
        # Mirrors Java lines 1007-1011 in replaceOrCopyStep().
        if self._nets_mode and step.type in (
            SolutionType.FORCING_CHAIN_CONTRADICTION,
            SolutionType.FORCING_CHAIN_VERITY,
        ):
            return

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

    # ------------------------------------------------------------------
    # Nice Loop / AIC detection via tabling
    # ------------------------------------------------------------------

    def find_all_nice_loops(
        self,
        with_group_nodes: bool = True,
        with_als_nodes: bool = False,
        only_grouped: bool = True,
        target_type: SolutionType | None = None,
    ) -> list[SolutionStep]:
        """Find all nice loops / AICs using the tabling framework.

        Mirrors TablingSolver.getAllNiceLoops() and getAllGroupedNiceLoops()
        in Java.

        with_group_nodes: include group node entries in tables
        only_grouped: if True, only return grouped NL/AIC steps
        target_type: filter results to this specific type
        """
        self.steps.clear()
        self.deletes_map.clear()
        self._only_grouped_nice_loops = only_grouped

        # Fill tables
        self._fill_tables()
        if with_group_nodes:
            self._fill_tables_with_group_nodes()
        if with_als_nodes:
            self._fill_tables_with_als()

        # Expand tables
        self._expand_tables(self.on_table)
        self._expand_tables(self.off_table)

        # Check for nice loops and AICs
        self._check_nice_loops(self.on_table)
        self._check_nice_loops(self.off_table)
        self._check_aics(self.off_table)

        self._only_grouped_nice_loops = False

        # Filter to target type if specified
        if target_type is not None:
            return [s for s in self.steps if s.type == target_type]

        self.steps.sort(key=_tabling_sort_key)
        return list(self.steps)

    def _check_nice_loops(self, table: list[TableEntry]) -> None:
        """Check all table entries for nice loops.

        Mirrors TablingSolver.checkNiceLoops() in Java.
        """
        for i in range(len(table)):
            if table[i].index == 0:
                continue
            start_index = table[i].get_cell_index(0)
            for j in range(1, table[i].index):
                if table[i].entries[j] == 0:
                    break
                if (table[i].get_node_type(j) == NORMAL_NODE
                        and table[i].get_cell_index(j) == start_index):
                    self._check_nice_loop(table[i], j)

    def _check_nice_loop(self, entry: TableEntry, entry_index: int) -> None:
        """Check if a loop forms a valid nice loop and determine eliminations.

        Mirrors TablingSolver.checkNiceLoop() in Java.
        """
        if entry.get_distance(entry_index) <= 2:
            return

        grid = self.grid
        self._global_step.reset()
        self._global_step.type = SolutionType.DISCONTINUOUS_NICE_LOOP
        self._reset_tmp_chains()
        self._add_chain(
            entry, entry.get_cell_index(entry_index),
            entry.get_candidate(entry_index), entry.is_strong(entry_index),
            is_nice_loop=True,
        )
        if not self._global_step.chains:
            return

        nl_chain = self._global_step.chains[0]
        nl_chain_index = len(nl_chain) - 1
        nl_chain_length = len(nl_chain)

        if get_cell_index(nl_chain[0]) == get_cell_index(nl_chain[1]):
            return  # first link must leave start cell

        first_link_strong = entry.is_strong(1)
        last_link_strong = entry.is_strong(entry_index)
        start_candidate = entry.get_candidate(0)
        end_candidate = entry.get_candidate(entry_index)
        start_index = entry.get_cell_index(0)

        if not first_link_strong and not last_link_strong and start_candidate == end_candidate:
            # Discontinuous: eliminate startCandidate from startIndex
            self._global_step.add_candidate_to_delete(start_index, start_candidate)

        elif first_link_strong and last_link_strong and start_candidate == end_candidate:
            # Discontinuous: eliminate all except startCandidate
            for d in range(1, 10):
                if grid.candidates[start_index] & DIGIT_MASKS[d] and d != start_candidate:
                    self._global_step.add_candidate_to_delete(start_index, d)

        elif first_link_strong != last_link_strong and start_candidate != end_candidate:
            # Discontinuous: eliminate the weak-link candidate
            if not first_link_strong:
                self._global_step.add_candidate_to_delete(start_index, start_candidate)
            else:
                self._global_step.add_candidate_to_delete(start_index, end_candidate)

        elif ((not first_link_strong and not last_link_strong
                and grid.candidates[start_index].bit_count() == 2
                and start_candidate != end_candidate)
              or (first_link_strong and last_link_strong
                  and start_candidate != end_candidate)
              or (first_link_strong != last_link_strong
                  and start_candidate == end_candidate)):
            # Continuous nice loop
            self._global_step.type = SolutionType.CONTINUOUS_NICE_LOOP
            self._check_continuous_nl_eliminations(
                nl_chain, nl_chain_index, start_index,
                start_candidate, end_candidate,
                first_link_strong, last_link_strong,
            )
        else:
            return  # not a valid loop type

        if not self._global_step.candidates_to_delete:
            return

        # Check for grouped nodes
        grouped = any(
            get_node_type(nl_chain[i]) != NORMAL_NODE
            for i in range(len(nl_chain))
            if nl_chain[i] >= 0
        )
        if grouped:
            if self._global_step.type == SolutionType.DISCONTINUOUS_NICE_LOOP:
                self._global_step.type = SolutionType.GROUPED_DISCONTINUOUS_NICE_LOOP
            elif self._global_step.type == SolutionType.CONTINUOUS_NICE_LOOP:
                self._global_step.type = SolutionType.GROUPED_CONTINUOUS_NICE_LOOP

        if self._only_grouped_nice_loops and not grouped:
            return

        # Dedup by elimination set
        del_key = self._global_step.get_candidate_string()
        old_index = self.deletes_map.get(del_key)
        if old_index is not None:
            if self.steps[old_index].get_chain_length() <= nl_chain_length:
                return

        self.deletes_map[del_key] = len(self.steps)
        self.steps.append(copy.deepcopy(self._global_step))

    def _check_continuous_nl_eliminations(
        self,
        nl_chain: list[int],
        nl_chain_index: int,
        start_index: int,
        start_candidate: int,
        end_candidate: int,
        first_link_strong: bool,
        last_link_strong: bool,
    ) -> None:
        """Find eliminations for a continuous nice loop.

        Mirrors the CNL elimination logic in TablingSolver.checkNiceLoop().
        """
        grid = self.grid
        alses = self._alses

        for i in range(nl_chain_index + 1):
            ev = nl_chain[i]
            if ev < 0:
                continue  # net branch marker

            # Cell with two strong links → eliminate all except strong link cands
            if (i == 0 and first_link_strong and last_link_strong) or \
               (i > 0 and is_strong(nl_chain[i]) and i <= nl_chain_index - 2
                and get_cell_index(nl_chain[i - 1]) != get_cell_index(nl_chain[i])):  # noqa: E129

                if i == 0 or (
                    not is_strong(nl_chain[i + 1])
                    and get_cell_index(nl_chain[i]) == get_cell_index(nl_chain[i + 1])
                    and is_strong(nl_chain[i + 2])
                    and get_cell_index(nl_chain[i + 1]) != get_cell_index(nl_chain[i + 2])
                ):
                    if i == 0:
                        c1, c2 = start_candidate, end_candidate
                    else:
                        c1 = get_candidate(nl_chain[i])
                        c2 = get_candidate(nl_chain[i + 2])
                    cell = get_cell_index(nl_chain[i])
                    for d in range(1, 10):
                        if grid.candidates[cell] & DIGIT_MASKS[d] and d != c1 and d != c2:
                            self._global_step.add_candidate_to_delete(cell, d)

            # Weak link between cells
            if i > 0 and not is_strong(nl_chain[i]) \
               and get_cell_index(nl_chain[i - 1]) != get_cell_index(nl_chain[i]):
                act_cand = get_candidate(nl_chain[i])
                # Get buddies for both endpoints of the weak link
                buddies_prev = _get_node_buddies(nl_chain[i - 1], act_cand, alses)
                buddies_curr = _get_node_buddies(nl_chain[i], act_cand, alses)
                common = buddies_prev & buddies_curr
                common &= ~self._chain_set
                common &= ~(1 << start_index)
                common &= grid.candidate_sets[act_cand]
                for cell in _iter_bits(common):
                    self._global_step.add_candidate_to_delete(cell, act_cand)

                # ALS node: additional eliminations for non-RC candidates
                if get_node_type(nl_chain[i]) == ALS_NODE:
                    als_idx = get_als_index(nl_chain[i])
                    if als_idx < len(alses):
                        als = alses[als_idx]
                        # Check if the exit is forced (next link is strong)
                        is_force_exit = (
                            i < nl_chain_index and is_strong(nl_chain[i + 1])
                        )
                        next_cell_index = get_cell_index(nl_chain[i + 1]) if i < nl_chain_index else -1
                        exit_cands: int = 0  # bitmask of exit candidates
                        if is_force_exit:
                            force_cand = get_candidate(nl_chain[i + 1])
                            exit_cands = grid.candidates[next_cell_index] & ~DIGIT_MASKS[force_cand]
                        elif i < nl_chain_index:
                            exit_cands = DIGIT_MASKS[get_candidate(nl_chain[i + 1])]

                        # Eliminate non-RC, non-exit candidates
                        for d in range(1, 10):
                            if DIGIT_MASKS[d] & exit_cands:
                                continue
                            if d == act_cand:
                                continue
                            if not als.buddies_per_cand[d]:
                                continue
                            elim = als.buddies_per_cand[d] & grid.candidate_sets[d]
                            for cell in _iter_bits(elim):
                                self._global_step.add_candidate_to_delete(cell, d)

                        # Force exit: exit candidates eliminate via combined buddies
                        if is_force_exit:
                            next_buddies = BUDDIES[next_cell_index]
                            tmp_exit = exit_cands
                            while tmp_exit:
                                lsb = tmp_exit & -tmp_exit
                                d = lsb.bit_length()
                                tmp_exit ^= lsb
                                elim = als.buddies_per_cand[d] & next_buddies
                                elim &= grid.candidate_sets[d]
                                for cell in _iter_bits(elim):
                                    self._global_step.add_candidate_to_delete(cell, d)

    def _check_aics(self, table: list[TableEntry]) -> None:
        """Check off_table entries for AIC patterns.

        Mirrors TablingSolver.checkAics() in Java.
        AICs start with a strong link (off-table premise leads to ON entries).
        """
        grid = self.grid
        for i in range(len(table)):
            if table[i].index == 0:
                continue
            start_index = table[i].get_cell_index(0)
            start_candidate = table[i].get_candidate(0)
            start_buddies = BUDDIES[start_index]

            for j in range(1, table[i].index):
                if table[i].entries[j] == 0:
                    break
                if (table[i].get_node_type(j) != NORMAL_NODE
                        or not table[i].is_strong(j)
                        or table[i].get_cell_index(j) == start_index):
                    continue

                end_index = table[i].get_cell_index(j)
                end_candidate = table[i].get_candidate(j)

                if start_candidate == end_candidate:
                    # Type 1: same candidate at both ends
                    common = start_buddies & BUDDIES[end_index]
                    common &= grid.candidate_sets[start_candidate]
                    if common and _bit_count(common) >= 2:
                        self._check_aic(table[i], j)
                else:
                    # Type 2: different candidates, endpoints see each other
                    if not (start_buddies & (1 << end_index)):
                        continue
                    if (grid.candidates[end_index] & DIGIT_MASKS[start_candidate]
                            and grid.candidates[start_index] & DIGIT_MASKS[end_candidate]):
                        self._check_aic(table[i], j)

    def _check_aic(self, entry: TableEntry, entry_index: int) -> None:
        """Build an AIC step and add to results.

        Mirrors TablingSolver.checkAic() in Java.
        """
        if entry.get_distance(entry_index) <= 2:
            return

        grid = self.grid
        self._global_step.reset()
        self._global_step.type = SolutionType.AIC

        start_candidate = entry.get_candidate(0)
        end_candidate = entry.get_candidate(entry_index)
        start_index = entry.get_cell_index(0)
        end_index = entry.get_cell_index(entry_index)

        if start_candidate == end_candidate:
            # Type 1: eliminate from cells seeing both endpoints
            common = BUDDIES[start_index] & BUDDIES[end_index]
            common &= grid.candidate_sets[start_candidate]
            if _bit_count(common) > 1:
                for cell in _iter_bits(common):
                    if cell != start_index:
                        self._global_step.add_candidate_to_delete(cell, start_candidate)
        else:
            # Type 2: cross-elimination
            if grid.candidates[start_index] & DIGIT_MASKS[end_candidate]:
                self._global_step.add_candidate_to_delete(start_index, end_candidate)
            if grid.candidates[end_index] & DIGIT_MASKS[start_candidate]:
                self._global_step.add_candidate_to_delete(end_index, start_candidate)

        if not self._global_step.candidates_to_delete:
            return

        self._reset_tmp_chains()
        self._add_chain(
            entry, entry.get_cell_index(entry_index),
            entry.get_candidate(entry_index), entry.is_strong(entry_index),
            is_aic=True,
        )
        if not self._global_step.chains:
            return

        chain = self._global_step.chains[0]

        grouped = any(
            get_node_type(chain[ci]) != NORMAL_NODE
            for ci in range(len(chain))
            if chain[ci] >= 0
        )
        if grouped:
            if self._global_step.type == SolutionType.AIC:
                self._global_step.type = SolutionType.GROUPED_AIC

        if self._only_grouped_nice_loops and not grouped:
            return

        del_key = self._global_step.get_candidate_string()
        old_index = self.deletes_map.get(del_key)
        if old_index is not None:
            if self.steps[old_index].get_chain_length() <= len(chain):
                return

        self.deletes_map[del_key] = len(self.steps)
        self.steps.append(copy.deepcopy(self._global_step))


# ---------------------------------------------------------------------------
# Node buddies helper (matching Chain.getSNodeBuddies in Java)
# ---------------------------------------------------------------------------

def _get_node_buddies(entry: int, candidate: int, alses: list[Als]) -> int:
    """Get the buddy set for a chain node entry.

    For normal nodes: buddies of the cell.
    For group nodes: intersection of buddies of all cells.
    For ALS nodes: buddiesPerCandidat[candidate] for the ALS.
    """
    nt = get_node_type(entry)
    if nt == NORMAL_NODE:
        return BUDDIES[get_cell_index(entry)]
    elif nt == GROUP_NODE:
        result = BUDDIES[get_cell_index(entry)]
        ci2 = get_cell_index2(entry)
        if ci2 != -1:
            result &= BUDDIES[ci2]
        ci3 = get_cell_index3(entry)
        if ci3 != -1:
            result &= BUDDIES[ci3]
        return result
    elif nt == ALS_NODE:
        als_idx = get_als_index(entry)
        if als_idx < len(alses):
            return alses[als_idx].buddies_per_cand[candidate]
    return 0


# ---------------------------------------------------------------------------
# Sorting key for tabling steps (TablingComparator)
# ---------------------------------------------------------------------------

def _tabling_sort_cmp(o1: SolutionStep, o2: SolutionStep) -> int:
    """Comparator matching Java's SolutionStep.compareTo() exactly.

    This is used by Collections.sort(steps) in TablingSolver.getNiceLoops().

    Order:
      1. Singles (set-cell) before elimination steps
      2. More candidates to delete first (descending count)
      3. If not equivalent: compare by getIndexSumme (weighted sum of candidates)
      4. If equivalent: special fish handling, then chain length, values, indices
    """
    # Singles first
    single1 = _is_single(o1.type)
    single2 = _is_single(o2.type)
    if single1 and not single2:
        return -1
    if not single1 and single2:
        return 1

    # More candidates to delete first (descending)
    result = len(o2.candidates_to_delete) - len(o1.candidates_to_delete)
    if result != 0:
        return result

    # Equivalency check
    if not _is_equivalent(o1, o2):
        sum1 = _get_index_summe(o1.candidates_to_delete)
        sum2 = _get_index_summe(o2.candidates_to_delete)
        return sum1 - sum2

    # SPECIAL: fish steps
    if _is_fish(o1.type) and _is_fish(o2.type):
        # fish type/size comparison, cannibalism, endo fins, fins, values
        ret = _compare_fish_types(o1.type, o2.type)
        if ret != 0:
            return ret
        # Skip cannibalistic/fins/endo_fins comparisons for now (rarely relevant)
        if o1.values != o2.values:
            return sum(o1.values) - sum(o2.values)
        return 0

    # Chain length (ascending — shorter is better)
    chain_diff = o1.get_chain_length() - o2.get_chain_length()
    if chain_diff != 0:
        return chain_diff

    # Values comparison — Java uses isEqualInteger (set equality)
    if not _same_integers(o1.values, o2.values):
        return sum(o1.values) - sum(o2.values)

    # Indices comparison — Java uses isEqualInteger (set equality)
    if not _same_integers(o1.indices, o2.indices):
        # Java: indices.size() - o.indices.size() (ascending)
        if len(o1.indices) != len(o2.indices):
            return len(o1.indices) - len(o2.indices)
        # Java: sum2 - sum1 (descending)
        return sum(o2.indices) - sum(o1.indices)

    # Final tiebreaker: type comparison
    # Java: return type.compare(o.getType()) which uses step config index
    return _compare_types(o1.type, o2.type)


def _is_single(t: SolutionType) -> bool:
    """Check if a SolutionType is a single (placement) type."""
    name = t.name
    return name in ('FULL_HOUSE', 'HIDDEN_SINGLE', 'NAKED_SINGLE')


def _is_equivalent(o1: SolutionStep, o2: SolutionStep) -> bool:
    """Check if two steps are equivalent (same type and same effects).

    Mirrors Java SolutionStep.isEquivalent().
    """
    t1, t2 = o1.type, o2.type
    if _is_fish(t1) and _is_fish(t2):
        return True
    if _is_kraken_fish(t1) and _is_kraken_fish(t2):
        return True
    if t1 != t2:
        return False
    if o1.candidates_to_delete:
        return _same_candidates(o1.candidates_to_delete, o2.candidates_to_delete)
    # Java uses isEqualInteger which is set equality (order-independent)
    return _same_integers(o1.indices, o2.indices)


def _same_candidates(a: list, b: list) -> bool:
    """Check if two candidate lists have the same (index, value) pairs.

    Uses set-equality (order-independent) to match Java's isEqualCandidate().
    """
    if len(a) != len(b):
        return False
    # O(n^2) set comparison matching Java exactly
    for c1 in a:
        found = False
        for c2 in b:
            if c1.index == c2.index and c1.value == c2.value:
                found = True
                break
        if not found:
            return False
    return True


def _same_integers(a: list[int], b: list[int]) -> bool:
    """Set-equality check for integer lists, matching Java's isEqualInteger().

    Order-independent: [1, 2] == [2, 1].
    """
    if len(a) != len(b):
        return False
    for v in a:
        if v not in b:
            return False
    return True


def _compare_types(t1: SolutionType, t2: SolutionType) -> int:
    """Compare types by solver step config index.

    Mirrors Java SolutionType.compare() for non-fish types.
    """
    from hodoku.core.scoring import STEP_CONFIG
    c1 = STEP_CONFIG.get(t1)
    c2 = STEP_CONFIG.get(t2)
    idx1 = c1.index if c1 else 0
    idx2 = c2.index if c2 else 0
    return idx1 - idx2


def _compare_candidates_sorted(o1: SolutionStep, o2: SolutionStep) -> int:
    """Compare candidate-to-delete lists element-by-element, using sorted order.

    Both lists are sorted by (index, value) before comparison, making the
    result independent of the order in which candidates were discovered.
    """
    s1 = sorted(o1.candidates_to_delete, key=lambda c: (c.index, c.value))
    s2 = sorted(o2.candidates_to_delete, key=lambda c: (c.index, c.value))
    if len(s1) != len(s2):
        return len(s2) - len(s1)
    for c1, c2 in zip(s1, s2):
        result = (c1.index * 10 + c1.value) - (c2.index * 10 + c2.value)
        if result != 0:
            return result
    return 0


def _get_index_summe(candidates: list) -> int:
    """Weighted sum of candidate indices, matching Java's getIndexSumme().

    Java's getCandidateString() sorts candidatesToDelete by (value, index) via
    Collections.sort before compareTo/getIndexSumme is ever called.  So the
    weighted sum is computed over the *sorted* list, not insertion order.

    Uses increasing offset: first candidate weight=1, next=81, then=161, etc.
    """
    total = 0
    offset = 1
    for c in sorted(candidates, key=lambda c: (c.value, c.index)):
        total += c.index * offset + c.value
        offset += 80
    return total


def _is_fish(t: SolutionType) -> bool:
    """Check if a SolutionType is a fish type."""
    name = t.name
    return any(f in name for f in (
        'SWORDFISH', 'JELLYFISH', 'SQUIRMBAG', 'WHALE', 'LEVIATHAN',
        'X_WING',
    )) and 'KRAKEN' not in name


def _is_kraken_fish(t: SolutionType) -> bool:
    """Check if a SolutionType is a Kraken fish type."""
    return 'KRAKEN' in t.name


def _compare_fish_types(t1: SolutionType, t2: SolutionType) -> int:
    """Compare fish types by ordinal value."""
    # Use name-based ordering as a proxy for ordinal
    return 0  # Within equivalent fish, further comparison handled above


def _fc_sort_cmp(o1: SolutionStep, o2: SolutionStep) -> int:
    """Comparator matching Java's TablingComparator exactly.

    Used for forcing chains/nets (NOT nice loops).
    """
    has1 = len(o1.indices) > 0
    has2 = len(o2.indices) > 0

    if has1 and not has2:
        return -1
    if not has1 and has2:
        return 1

    if has1:
        # set cell — more cells first
        result = len(o2.indices) - len(o1.indices)
        if result != 0:
            return result
        if not _is_equivalent(o1, o2):
            sum1 = sum(o1.indices)
            sum2 = sum(o2.indices)
            return 1 if sum1 == sum2 else (sum1 - sum2)
        result = o1.get_chain_length() - o2.get_chain_length()
        if result != 0:
            return result
    else:
        result = len(o2.candidates_to_delete) - len(o1.candidates_to_delete)
        if result != 0:
            return result
        if not _is_equivalent(o1, o2):
            result = _compare_candidates_to_delete(o1, o2)
            if result != 0:
                return result
        result = o1.get_chain_length() - o2.get_chain_length()
        if result != 0:
            return result
    return 0


def _compare_candidates_to_delete(o1: SolutionStep, o2: SolutionStep) -> int:
    """Compare candidates element-by-element using index*10+value.

    Mirrors Java SolutionStep.compareCandidatesToDelete().  In Java, the
    candidatesToDelete lists are already sorted by (value, index) due to the
    getCandidateString() side effect, so we sort before comparing.
    """
    c1s = sorted(o1.candidates_to_delete, key=lambda c: (c.value, c.index))
    c2s = sorted(o2.candidates_to_delete, key=lambda c: (c.value, c.index))
    if len(c1s) != len(c2s):
        return len(c2s) - len(c1s)
    for c1, c2 in zip(c1s, c2s):
        result = (c1.index * 10 + c1.value) - (c2.index * 10 + c2.value)
        if result != 0:
            return result
    return 0


import functools  # noqa: E402
_tabling_sort_key = functools.cmp_to_key(_tabling_sort_cmp)
_fc_sort_key = functools.cmp_to_key(_fc_sort_cmp)


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
