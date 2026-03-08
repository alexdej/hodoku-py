"""TableEntry — one row in the tabling implication table.

Mirrors Java's TableEntry class. Each TableEntry holds all transitive
implications of a single premise ("candidate N is set/deleted in cell X").

The parallel arrays ``entries[]`` and ``ret_indices[]`` are synchronised:
``entries[k]`` is a 32-bit packed chain entry (see chain_utils.py) and
``ret_indices[k]`` is a 64-bit backpointer used for chain reconstruction.

``on_sets[d]`` / ``off_sets[d]`` (d 1-9) are 81-bit bitmasks summarising
which cells can be set to / deleted from digit d as a result of the premise.
"""

from __future__ import annotations

from hodoku.solver.chain_utils import (
    NORMAL_NODE,
    get_candidate,
    get_cell_index,
    get_node_type,
    is_strong,
    make_entry,
)

# ---------------------------------------------------------------------------
# retIndex flag bits (64-bit)
# ---------------------------------------------------------------------------

_EXPANDED: int = 1 << 61
_ON_TABLE: int = 1 << 62
_EXTENDED_TABLE: int = 1 << 63

# Mask that preserves the three flag bits (63, 62, 61) and the lower 52 bits,
# clearing only the 9 distance bits (52-60).
_DIST_CLEAR_MASK: int = 0xE00FFFFFFFFFFFFF

MAX_TABLE_ENTRY_LENGTH: int = 500


class TableEntry:
    """One premise's implication table row."""

    __slots__ = (
        "index",
        "entries",
        "ret_indices",
        "on_sets",
        "off_sets",
        "indices",
    )

    def __init__(self) -> None:
        self.index: int = 0
        self.entries: list[int] = [0] * MAX_TABLE_ENTRY_LENGTH
        self.ret_indices: list[int] = [0] * MAX_TABLE_ENTRY_LENGTH
        # on_sets[d] = bitmask of cells that can be SET to d; index 0 unused
        self.on_sets: list[int] = [0] * 10
        # off_sets[d] = bitmask of cells from which d can be DELETED
        self.off_sets: list[int] = [0] * 10
        # Reverse lookup: entry value -> index in entries[]
        self.indices: dict[int, int] = {}

    def reset(self) -> None:
        """Clear the table for reuse."""
        self.index = 0
        self.indices.clear()
        for i in range(10):
            self.on_sets[i] = 0
            self.off_sets[i] = 0
        entries = self.entries
        ret_indices = self.ret_indices
        for i in range(len(entries)):
            entries[i] = 0
            ret_indices[i] = 0

    # ------------------------------------------------------------------
    # Adding entries
    # ------------------------------------------------------------------

    def add_entry(
        self,
        cell_index1: int,
        cand: int,
        is_set: bool,
        cell_index2: int = -1,
        cell_index3: int = -1,
        node_type: int = NORMAL_NODE,
        ri1: int = 0,
        ri2: int = 0,
        ri3: int = 0,
        ri4: int = 0,
        ri5: int = 0,
        penalty: int = 0,
    ) -> None:
        """Add an implication to this table.

        Convenience wrapper that mirrors all Java addEntry overloads via
        keyword arguments.
        """
        idx = self.index
        if idx >= len(self.entries):
            return

        # Dedup: for normal nodes, skip if already recorded in on/off sets
        if node_type == NORMAL_NODE:
            if is_set:
                if self.on_sets[cand] & (1 << cell_index1):
                    return
            else:
                if self.off_sets[cand] & (1 << cell_index1):
                    return

        # Construct the 32-bit packed entry
        entry = make_entry(cell_index1, cell_index2, cell_index3,
                           cand, is_set, node_type)
        self.entries[idx] = entry
        self.ret_indices[idx] = _make_ret_index(ri1, ri2, ri3, ri4, ri5)

        # Set distance — for initial entries ri1 is the predecessor index
        # in THIS table. For expanded entries the caller overrides immediately.
        if ri1 < len(self.ret_indices):
            self._set_distance(idx, self.get_distance(ri1) + 1)

        # Update summary bitmasks (only for normal nodes)
        if node_type == NORMAL_NODE:
            if is_set:
                self.on_sets[cand] |= 1 << cell_index1
            else:
                self.off_sets[cand] |= 1 << cell_index1

        # ALS penalty
        if penalty:
            self._set_distance(idx, self.get_distance(idx) + penalty)

        self.indices[entry] = idx
        self.index = idx + 1

    # ------------------------------------------------------------------
    # Convenience wrappers matching Java's overload patterns
    # ------------------------------------------------------------------

    def add_entry_simple(self, cell_index: int, cand: int, is_set: bool) -> None:
        """Simple node, no reverse index. Used for initial table filling."""
        self.add_entry(cell_index, cand, is_set)

    def add_entry_with_ri(self, cell_index: int, cand: int, is_set: bool,
                          reverse_index: int) -> None:
        """Simple node with one reverse index. Used during expansion."""
        self.add_entry(cell_index, cand, is_set, ri1=reverse_index)

    # ------------------------------------------------------------------
    # Entry accessors (delegate to chain_utils on entries[idx])
    # ------------------------------------------------------------------

    def get_cell_index(self, idx: int) -> int:
        return get_cell_index(self.entries[idx])

    def is_strong(self, idx: int) -> bool:
        return is_strong(self.entries[idx])

    def get_candidate(self, idx: int) -> int:
        return get_candidate(self.entries[idx])

    def get_node_type(self, idx: int) -> int:
        return get_node_type(self.entries[idx])

    def is_full(self) -> bool:
        return self.index >= len(self.entries)

    # ------------------------------------------------------------------
    # Entry lookup
    # ------------------------------------------------------------------

    def get_entry_index_by_value(self, entry: int) -> int:
        """Find the slot index for a given 32-bit entry value.

        Returns the index, or raises KeyError if not found.
        """
        return self.indices[entry]

    def get_entry_index(self, cell_index: int, is_set: bool, cand: int) -> int:
        """Find the slot index for cell/cand/set combination.

        Returns 0 if not found (matching Java behaviour).
        """
        from hodoku.solver.chain_utils import make_entry_simple
        entry = make_entry_simple(cell_index, cand, is_set)
        return self.indices.get(entry, 0)

    # ------------------------------------------------------------------
    # retIndex bit manipulation
    # ------------------------------------------------------------------

    def get_distance(self, idx: int) -> int:
        """Distance from root (bits 52-60, 9 bits)."""
        return _get_ret_index(self.ret_indices[idx], 5) & 0x1FF

    def _set_distance(self, idx: int, distance: int) -> None:
        """Set distance in ret_indices[idx]."""
        d = distance & 0x1FF
        self.ret_indices[idx] &= _DIST_CLEAR_MASK
        self.ret_indices[idx] |= d << 52

    def is_expanded(self, idx: int) -> bool:
        """Entry was merged from another table during expansion."""
        return (self.ret_indices[idx] & _EXPANDED) != 0

    def set_expanded(self, idx: int) -> None:
        self.ret_indices[idx] |= _EXPANDED

    def is_on_table(self, idx: int) -> bool:
        """Source was on_table (vs off_table)."""
        return (self.ret_indices[idx] & _ON_TABLE) != 0

    def set_on_table(self, idx: int) -> None:
        self.ret_indices[idx] |= _ON_TABLE

    def is_extended_table(self, idx: int) -> bool:
        """Source was extended_table."""
        return (self.ret_indices[idx] & _EXTENDED_TABLE) != 0

    def set_extended_table(self, idx: int) -> None:
        self.ret_indices[idx] |= _EXTENDED_TABLE

    def set_extended_table_last(self) -> None:
        """Mark the most recently added entry as from extended_table."""
        self.ret_indices[self.index - 1] |= _EXTENDED_TABLE

    def get_ret_index(self, idx: int, which: int) -> int:
        """Get reverse index ``which`` (0-4) or distance (5) from slot ``idx``."""
        return _get_ret_index(self.ret_indices[idx], which)

    def get_ret_index_count(self, idx: int) -> int:
        """Number of reverse indices in slot ``idx`` (1-5)."""
        return _get_ret_index_count(self.ret_indices[idx])


# ---------------------------------------------------------------------------
# Module-level helpers (matching Java's static methods)
# ---------------------------------------------------------------------------

def _make_ret_index(i1: int, i2: int, i3: int, i4: int, i5: int) -> int:
    """Pack up to 5 reverse indices into a 64-bit retIndex value.

    The largest value is placed in the first (12-bit) slot.
    Matches TableEntry.makeSRetIndex in Java.
    """
    # Clamp to field widths
    if i1 > 4096:
        i1 = 0
    if i2 > 1023:
        i2 = 0
    if i3 > 1023:
        i3 = 0
    if i4 > 1023:
        i4 = 0
    if i5 > 1023:
        i5 = 0

    # Ensure the largest value is first
    if i2 > i1:
        i1, i2 = i2, i1
    if i3 > i1:
        i1, i3 = i3, i1
    if i4 > i1:
        i1, i4 = i4, i1
    if i5 > i1:
        i1, i5 = i5, i1

    return (i5 << 42) + (i4 << 32) + (i3 << 22) + (i2 << 12) + i1


def _get_ret_index(ret_index: int, which: int) -> int:
    """Extract reverse index ``which`` (0-4) or distance (5) from a retIndex.

    Matches TableEntry.getSRetIndex in Java.
    """
    if which == 0:
        return ret_index & 0xFFF
    ret = (ret_index >> (which * 10 + 2)) & 0x3FF
    if which == 5:
        ret &= 0x1FF
    return ret


def _get_ret_index_count(ret_index: int) -> int:
    """Count how many reverse indices are present (1-5).

    The first is always present (even if 0).
    Matches TableEntry.getSRetIndexAnz in Java.
    """
    count = 1
    ri = ret_index >> 12
    for _ in range(4):
        if ri & 0x3FF:
            count += 1
        ri >>= 10
    return count
