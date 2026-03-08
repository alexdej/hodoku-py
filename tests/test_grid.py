import pytest

from hodoku.core.grid import Grid, CONSTRAINTS, BUDDIES, LINES, COLS, BLOCKS


# A simple easy puzzle (Wikipedia example)
EASY_PUZZLE = "530070000600195000098000060800060003400803001700020006060000280000419005000080079"
EASY_SOLUTION = "534678912672195348198342567859761423426853791713924856961537284287419635345286179"


def test_parse_and_string_roundtrip():
    g = Grid()
    g.set_sudoku(EASY_PUZZLE)
    assert g.get_sudoku_string() == EASY_PUZZLE


def test_parse_dots():
    puzzle = EASY_PUZZLE.replace("0", ".")
    g = Grid()
    g.set_sudoku(puzzle)
    assert "." not in g.get_sudoku_string()
    assert g.get_sudoku_string() == EASY_PUZZLE


def test_invalid_length_raises():
    g = Grid()
    with pytest.raises(ValueError):
        g.set_sudoku("123")


def test_set_cell_places_value():
    g = Grid()
    g.set_sudoku(EASY_PUZZLE)
    # r1c1 is already 5; check an empty cell
    # cell 1 (r1c2) is 3, cell 2 (r1c3) is 0 in EASY_PUZZLE — wait:
    # EASY_PUZZLE[0]='5', [1]='3', [2]='0' -> cell 2 is empty
    assert g.get_value(2) == 0
    g.set_cell(2, 4)
    assert g.get_value(2) == 4


def test_set_cell_removes_candidates_from_buddies():
    g = Grid()
    g.set_sudoku("." * 81)  # blank grid
    # place 5 in cell 0 (r1c1, box 0)
    g.set_cell(0, 5)
    # all buddies of cell 0 must not have 5 as candidate
    buddy_mask = BUDDIES[0]
    bits = buddy_mask
    while bits:
        lsb = bits & -bits
        j = lsb.bit_length() - 1
        bits ^= lsb
        assert not (g.candidates[j] & (1 << (5 - 1))), f"cell {j} still has digit 5"
    # digit 5 candidate_set must have no bits set in row 0, col 0, or box 0
    # (beyond cell 0 itself which is now set)
    for j in LINES[0]:
        if j != 0:
            assert not (g.candidate_sets[5] >> j & 1)
    for j in COLS[0]:
        if j != 0:
            assert not (g.candidate_sets[5] >> j & 1)
    for j in BLOCKS[0]:
        if j != 0:
            assert not (g.candidate_sets[5] >> j & 1)


def test_del_candidate():
    g = Grid()
    g.set_sudoku("." * 81)
    g.del_candidate(40, 5)
    assert not (g.candidates[40] & (1 << 4))
    assert not (g.candidate_sets[5] >> 40 & 1)


def test_constraints_structure():
    # spot-check: cell 0 is row 0, col 0, box 0
    assert CONSTRAINTS[0] == (0, 0, 0)
    # cell 80 is row 8, col 8, box 8
    assert CONSTRAINTS[80] == (8, 8, 8)
    # cell 10 is row 1, col 1, box 0
    assert CONSTRAINTS[10] == (1, 1, 0)


def test_buddies_count():
    # every cell has exactly 20 buddies
    for i in range(81):
        assert bin(BUDDIES[i]).count("1") == 20, f"cell {i} has wrong buddy count"


def test_clone_is_independent():
    g = Grid()
    g.set_sudoku(EASY_PUZZLE)
    h = g.clone()
    h.set_cell(2, 4)
    assert g.get_value(2) == 0


def test_is_solved():
    g = Grid()
    g.set_sudoku(EASY_SOLUTION)
    assert g.is_solved()


def test_unsolved_count():
    g = Grid()
    g.set_sudoku(EASY_PUZZLE)
    zeros = EASY_PUZZLE.count("0")
    assert g.unsolved_count() == zeros
