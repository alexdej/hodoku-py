"""Chain entry bit-packing utilities.

Mirrors Java's Chain class static methods for 32-bit packed chain entries.

Entry format (32-bit integer):
    bits  0- 3: candidate (digit 1-9)
    bit      4: strong link (1) or weak link (0)
    bits  5-11: cell index 1 (0-80)
    bits 12-18: cell index 2 (group node 2nd cell, or lower 7 bits of ALS index)
    bits 19-25: cell index 3 (group node 3rd cell, or upper 7 bits of ALS index)
    bits 26-29: node type (0=NORMAL, 1=GROUP, 2=ALS)
    bits 30-31: reserved

Entries can be negative in chain arrays to mark net branch starting points.
All accessor functions take the absolute value before extracting fields.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Node type constants
# ---------------------------------------------------------------------------

NORMAL_NODE: int = 0
GROUP_NODE: int = 1
ALS_NODE: int = 2

# ---------------------------------------------------------------------------
# Internal masks and offsets (matching Chain.java exactly)
# ---------------------------------------------------------------------------

_CAND_MASK: int = 0xF             # bits 0-3
_STRONG_MASK: int = 0x10          # bit 4
_INDEX_MASK: int = 0x7F           # 7-bit index mask
_INDEX1_OFFSET: int = 5
_INDEX2_OFFSET: int = 12
_INDEX3_OFFSET: int = 19
_NO_INDEX: int = 0x7F             # all bits set = "not used"
_MODE_MASK: int = 0x3C000000      # bits 26-29
_MODE_OFFSET: int = 26
_GROUP_NODE_MASK: int = 0x4000000  # 1 << 26
_ALS_NODE_MASK: int = 0x8000000    # 2 << 26
_ALS_INDEX_MASK: int = 0x3FFF000   # bits 12-25 (14 bits total)
_ALS_INDEX_OFFSET: int = 12


# ---------------------------------------------------------------------------
# Entry construction
# ---------------------------------------------------------------------------

def make_entry(
    cell_index1: int,
    cell_index2: int,
    cell_index3: int,
    candidate: int,
    is_strong: bool,
    node_type: int,
) -> int:
    """Create a 32-bit packed chain entry.

    Parameters match Chain.makeSEntry(cellIndex1, cellIndex2, cellIndex3,
    candidate, isStrong, nodeType) in Java.
    """
    entry = (cell_index1 << _INDEX1_OFFSET) | candidate
    if is_strong:
        entry |= _STRONG_MASK
    if node_type == GROUP_NODE:
        entry |= _GROUP_NODE_MASK
    elif node_type == ALS_NODE:
        entry |= _ALS_NODE_MASK

    if cell_index2 == -1:
        cell_index2 = 0 if node_type == NORMAL_NODE else _NO_INDEX
    if cell_index3 == -1:
        cell_index3 = 0 if node_type == NORMAL_NODE else _NO_INDEX

    entry |= (cell_index2 << _INDEX2_OFFSET)
    entry |= (cell_index3 << _INDEX3_OFFSET)
    return entry


def make_entry_simple(cell_index: int, candidate: int, is_strong: bool) -> int:
    """Shorthand: normal node, no second/third cell."""
    return make_entry(cell_index, -1, -1, candidate, is_strong, NORMAL_NODE)


# ---------------------------------------------------------------------------
# Entry accessors — all handle negative entries (net branch markers)
# ---------------------------------------------------------------------------

def get_cell_index(entry: int) -> int:
    """First cell index (bits 5-11)."""
    if entry < 0:
        entry = -entry
    return (entry >> _INDEX1_OFFSET) & _INDEX_MASK


def get_cell_index2(entry: int) -> int:
    """Second cell index; returns -1 if not present."""
    if entry < 0:
        entry = -entry
    result = (entry >> _INDEX2_OFFSET) & _INDEX_MASK
    return -1 if result == _INDEX_MASK else result


def get_cell_index3(entry: int) -> int:
    """Third cell index; returns -1 if not present."""
    if entry < 0:
        entry = -entry
    result = (entry >> _INDEX3_OFFSET) & _INDEX_MASK
    return -1 if result == _INDEX_MASK else result


def get_candidate(entry: int) -> int:
    """Candidate digit (bits 0-3)."""
    if entry < 0:
        entry = -entry
    return entry & _CAND_MASK


def is_strong(entry: int) -> bool:
    """True if the entry represents a strong link (candidate SET)."""
    if entry < 0:
        entry = -entry
    return (entry & _STRONG_MASK) != 0


def get_node_type(entry: int) -> int:
    """Node type: NORMAL_NODE, GROUP_NODE, or ALS_NODE."""
    if entry < 0:
        entry = -entry
    return (entry & _MODE_MASK) >> _MODE_OFFSET


def get_als_index(entry: int) -> int:
    """ALS index (14-bit value stored across cell_index2 + cell_index3 fields)."""
    if entry < 0:
        entry = -entry
    return (entry & _ALS_INDEX_MASK) >> _ALS_INDEX_OFFSET


def get_lower_als_index(als_index: int) -> int:
    """Lower 7 bits of an ALS index (stored in cell_index2 position)."""
    return als_index & _INDEX_MASK


def get_higher_als_index(als_index: int) -> int:
    """Upper 7 bits of an ALS index (stored in cell_index3 position)."""
    return (als_index >> 7) & _INDEX_MASK


def make_entry_als(
    cell_index: int,
    als_index: int,
    candidate: int,
    is_strong: bool,
    node_type: int,
) -> int:
    """Create an ALS/group node entry by splitting als_index into two 7-bit halves."""
    return make_entry(
        cell_index,
        get_lower_als_index(als_index),
        get_higher_als_index(als_index),
        candidate,
        is_strong,
        node_type,
    )


def replace_als_index(entry: int, new_als_index: int) -> int:
    """Return a copy of *entry* with the ALS index replaced."""
    entry &= ~_ALS_INDEX_MASK
    entry |= (new_als_index << _ALS_INDEX_OFFSET) & _ALS_INDEX_MASK
    return entry


def set_strong(entry: int, strong: bool) -> int:
    """Return a copy of *entry* with the strong flag set or cleared."""
    if strong:
        return entry | _STRONG_MASK
    return entry & ~_STRONG_MASK
