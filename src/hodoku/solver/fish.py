"""Fish solver: basic, finned/sashimi, Franken, and Mutant variants.

Mirrors Java's FishSolver.  Basic and finned/sashimi were already implemented;
Franken and Mutant extend the unit pool to include boxes as base/cover sets.

Fish category classification (mirrors Java's createFishStep logic):
  BASIC   — base = rows only,         cover = cols only (or vice versa)
  FRANKEN — base ⊆ {rows, blocks},   cover ⊆ {cols, blocks}  (or vice versa)
  MUTANT  — any other combination (rows and cols appear on the same side)

Unit pools for initForCandidat (fishType, lines=True):
  BASIC:   base = rows,              cover = cols
  FRANKEN: base = rows + blocks,     cover = cols + blocks
  MUTANT:  base = all 27 units,      cover = all 27 units  (one orientation)

Endo fins: cells that appear in two or more base units (possible when blocks
overlap rows/cols).  At most MAX_ENDO_FINS=2 endo fins are allowed.
Endo fins that are not covered appear in the regular fins mask and are
handled identically to external fins when computing eliminations.
"""

from __future__ import annotations

import ctypes
import ctypes.util
from itertools import combinations
from pathlib import Path

from hodoku.core.grid import (
    ALL_UNIT_MASKS,
    BLOCK_MASKS,
    BUDDIES,
    COL_MASKS,
    COLS,
    Grid,
    LINE_MASKS,
    LINES,
)

# All 81 cells mask
_ALL_CELLS = (1 << 81) - 1

# ---- C accelerator for cover search (optional, huge speedup) ----

_LO_MASK = (1 << 64) - 1
_HI_SHIFT = 64


class _FishResult(ctypes.Structure):
    _fields_ = [
        ("indices", ctypes.c_int32 * 7),
        ("cover_lo", ctypes.c_uint64), ("cover_hi", ctypes.c_uint64),
        ("cannibal_lo", ctypes.c_uint64), ("cannibal_hi", ctypes.c_uint64),
        ("fins_lo", ctypes.c_uint64), ("fins_hi", ctypes.c_uint64),
        ("elim_lo", ctypes.c_uint64), ("elim_hi", ctypes.c_uint64),
    ]


def _try_compile_accel(c_path: Path, so_path: Path) -> bool:
    """Try to compile the C accelerator.  Returns True on success."""
    import subprocess
    import sys
    # Determine shared library extension and compiler flags
    if sys.platform == "win32":
        # Windows: try gcc (MinGW) → produces .dll
        so_path = c_path.with_suffix(".dll")
        cmd = ["gcc", "-O2", "-shared", "-o", str(so_path), str(c_path)]
    elif sys.platform == "darwin":
        cmd = ["cc", "-O2", "-shared", "-fPIC", "-o", str(so_path), str(c_path)]
    else:
        cmd = ["gcc", "-O2", "-shared", "-fPIC", "-o", str(so_path), str(c_path)]
    try:
        subprocess.run(cmd, capture_output=True, timeout=30, check=True)
        return so_path.exists()
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def _load_accel():
    """Try to load the C accelerator; return (lib, find_covers) or (None, None).

    If the .so is missing but the .c source exists, attempts to compile it
    automatically.  Falls back to pure Python if compilation fails.
    """
    import sys
    c_path = Path(__file__).parent / "_fish_accel.c"
    suffix = ".dll" if sys.platform == "win32" else ".so"
    so_path = c_path.with_suffix(suffix)

    if not so_path.exists():
        if c_path.exists():
            _try_compile_accel(c_path, so_path)
        if not so_path.exists():
            return None, None

    try:
        lib = ctypes.CDLL(str(so_path))

        # Initialize BUDDIES table in C
        lib.fish_set_buddy.argtypes = [ctypes.c_int, ctypes.c_uint64, ctypes.c_uint64]
        lib.fish_set_buddy.restype = None
        for cell in range(81):
            b = BUDDIES[cell]
            lib.fish_set_buddy(cell, b & _LO_MASK, b >> _HI_SHIFT)

        # Set up find_covers signature
        lib.fish_find_covers.argtypes = [
            ctypes.POINTER(ctypes.c_uint64),  # ce_lo
            ctypes.POINTER(ctypes.c_uint64),  # ce_hi
            ctypes.c_int,                      # num_cover
            ctypes.c_int,                      # n
            ctypes.c_uint64, ctypes.c_uint64,  # base_lo, base_hi
            ctypes.c_uint64, ctypes.c_uint64,  # cand_lo, cand_hi
            ctypes.c_int,                      # with_fins
            ctypes.c_int,                      # max_fins
            ctypes.c_uint64, ctypes.c_uint64,  # endo_lo, endo_hi
            ctypes.POINTER(_FishResult),       # out
            ctypes.c_int,                      # max_out
        ]
        lib.fish_find_covers.restype = ctypes.c_int
        return lib, lib.fish_find_covers
    except OSError:
        return None, None


_accel_lib, _accel_find_covers = _load_accel()


def _fin_buddies(fin_mask: int) -> int:
    """Return the intersection of buddies of all fin cells.

    A cell is in the result iff it can see every fin cell simultaneously.
    """
    common = _ALL_CELLS
    tmp = fin_mask
    while tmp:
        lsb = tmp & -tmp
        common &= BUDDIES[lsb.bit_length() - 1]
        tmp ^= lsb
    return common
from hodoku.core.solution_step import Entity, SolutionStep
from hodoku.core.types import SolutionType

# Entity type constants (mirror Java's Sudoku2.LINE / COL / BLOCK)
_LINE  = 0
_COL   = 1

# Size for each basic fish type
_FISH_SIZE = {
    SolutionType.X_WING:    2,
    SolutionType.SWORDFISH: 3,
    SolutionType.JELLYFISH: 4,
}

# Finned and Sashimi types with their size
_FINNED_SIZE = {
    SolutionType.FINNED_X_WING:    2,
    SolutionType.FINNED_SWORDFISH: 3,
    SolutionType.FINNED_JELLYFISH: 4,
}

_SASHIMI_SIZE = {
    SolutionType.SASHIMI_X_WING:    2,
    SolutionType.SASHIMI_SWORDFISH: 3,
    SolutionType.SASHIMI_JELLYFISH: 4,
}

# Map finned → sashimi counterpart (same size, different classification)
_FINNED_TO_SASHIMI = {
    SolutionType.FINNED_X_WING:    SolutionType.SASHIMI_X_WING,
    SolutionType.FINNED_SWORDFISH: SolutionType.SASHIMI_SWORDFISH,
    SolutionType.FINNED_JELLYFISH: SolutionType.SASHIMI_JELLYFISH,
}

# ---------------------------------------------------------------------------
# Franken / Mutant fish
# ---------------------------------------------------------------------------

# Fish category constants (mirror Java FishSolver BASIC/FRANKEN/MUTANT)
_CAT_BASIC   = 0
_CAT_FRANKEN = 1
_CAT_MUTANT  = 2

# Unit type bit-flags (for category classification)
_BIT_LINE  = 1
_BIT_COL   = 2
_BIT_BLOCK = 4

# HoDoKu defaults for fin/endo-fin limits
_MAX_FINS      = 5
_MAX_ENDO_FINS = 2

# Entity type constants for boxes (Java's Sudoku2.BLOCK = 0)
_BLOCK = 2

# Entity type constants (reuse existing _LINE=0, _COL=1, new _BLOCK_ENT=2)
_BLOCK_ENT = 2

# SolutionType → (category, size, with_fins)
_GENERALIZED_INFO: dict[SolutionType, tuple[int, int, bool]] = {
    # Franken (basic / no fins)
    SolutionType.FRANKEN_X_WING:    (_CAT_FRANKEN, 2, False),
    SolutionType.FRANKEN_SWORDFISH: (_CAT_FRANKEN, 3, False),
    SolutionType.FRANKEN_JELLYFISH: (_CAT_FRANKEN, 4, False),
    # Franken (finned)
    SolutionType.FINNED_FRANKEN_X_WING:    (_CAT_FRANKEN, 2, True),
    SolutionType.FINNED_FRANKEN_SWORDFISH: (_CAT_FRANKEN, 3, True),
    SolutionType.FINNED_FRANKEN_JELLYFISH: (_CAT_FRANKEN, 4, True),
    # Mutant (basic / no fins)
    SolutionType.MUTANT_X_WING:    (_CAT_MUTANT, 2, False),
    SolutionType.MUTANT_SWORDFISH: (_CAT_MUTANT, 3, False),
    SolutionType.MUTANT_JELLYFISH: (_CAT_MUTANT, 4, False),
    # Mutant (finned)
    SolutionType.FINNED_MUTANT_X_WING:      (_CAT_MUTANT, 2, True),
    SolutionType.FINNED_MUTANT_SWORDFISH:   (_CAT_MUTANT, 3, True),
    SolutionType.FINNED_MUTANT_JELLYFISH:   (_CAT_MUTANT, 4, True),
    SolutionType.FINNED_MUTANT_SQUIRMBAG:   (_CAT_MUTANT, 5, True),
    SolutionType.FINNED_MUTANT_WHALE:       (_CAT_MUTANT, 6, True),
    SolutionType.FINNED_MUTANT_LEVIATHAN:   (_CAT_MUTANT, 7, True),
}

# (category, size, with_fins) → basic SolutionType (for step annotation when no fins)
_CAT_BASIC_TYPES: dict[tuple[int, int], SolutionType] = {
    (_CAT_FRANKEN, 2): SolutionType.FRANKEN_X_WING,
    (_CAT_FRANKEN, 3): SolutionType.FRANKEN_SWORDFISH,
    (_CAT_FRANKEN, 4): SolutionType.FRANKEN_JELLYFISH,
    (_CAT_MUTANT,  2): SolutionType.MUTANT_X_WING,
    (_CAT_MUTANT,  3): SolutionType.MUTANT_SWORDFISH,
    (_CAT_MUTANT,  4): SolutionType.MUTANT_JELLYFISH,
}

# (category, size) → finned SolutionType
_CAT_FINNED_TYPES: dict[tuple[int, int], SolutionType] = {
    (_CAT_FRANKEN, 2): SolutionType.FINNED_FRANKEN_X_WING,
    (_CAT_FRANKEN, 3): SolutionType.FINNED_FRANKEN_SWORDFISH,
    (_CAT_FRANKEN, 4): SolutionType.FINNED_FRANKEN_JELLYFISH,
    (_CAT_MUTANT,  2): SolutionType.FINNED_MUTANT_X_WING,
    (_CAT_MUTANT,  3): SolutionType.FINNED_MUTANT_SWORDFISH,
    (_CAT_MUTANT,  4): SolutionType.FINNED_MUTANT_JELLYFISH,
    (_CAT_MUTANT,  5): SolutionType.FINNED_MUTANT_SQUIRMBAG,
    (_CAT_MUTANT,  6): SolutionType.FINNED_MUTANT_WHALE,
    (_CAT_MUTANT,  7): SolutionType.FINNED_MUTANT_LEVIATHAN,
}


def _classify_fish(base_type_bits: int, cover_type_bits: int) -> int:
    """Classify a fish as BASIC/FRANKEN/MUTANT based on unit type bits.

    Mirrors Java FishSolver.createFishStep type-determination logic.
    LINE_MASK=1, COL_MASK=2, BLOCK_MASK=4 in Java.
    """
    if ((base_type_bits == _BIT_LINE and cover_type_bits == _BIT_COL) or
            (base_type_bits == _BIT_COL and cover_type_bits == _BIT_LINE)):
        return _CAT_BASIC
    # Franken: base ⊆ {LINE,BLOCK} and cover ⊆ {COL,BLOCK}, or vice versa
    if (((base_type_bits & ~(_BIT_LINE | _BIT_BLOCK)) == 0 and
             (cover_type_bits & ~(_BIT_COL | _BIT_BLOCK)) == 0) or
            ((base_type_bits & ~(_BIT_COL | _BIT_BLOCK)) == 0 and
             (cover_type_bits & ~(_BIT_LINE | _BIT_BLOCK)) == 0)):
        return _CAT_FRANKEN
    return _CAT_MUTANT


def _unit_type_bit(unit_idx: int) -> int:
    """Return the type bit for a unit index (0-8=row, 9-17=col, 18-26=block)."""
    if unit_idx < 9:
        return _BIT_LINE
    if unit_idx < 18:
        return _BIT_COL
    return _BIT_BLOCK


def _build_unit_pools(
    cand_set: int,
    fish_cat: int,
    lines: bool,
    n: int,
    with_fins: bool,
) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    """Build (base_pool, cover_pool) for a generalized fish search.

    Each pool entry is (unit_cands, unit_index) where unit_index is 0-26
    (0-8=rows, 9-17=cols, 18-26=blocks).

    Mirrors Java FishSolver.initForCandidat().
    """
    base_pool: list[tuple[int, int]] = []
    cover_pool: list[tuple[int, int]] = []

    for i in range(27):
        if fish_cat == _CAT_BASIC and i >= 18:
            continue
        unit_cands = cand_set & ALL_UNIT_MASKS[i]
        if not unit_cands:
            continue

        if i < 9:  # row
            if lines or fish_cat == _CAT_MUTANT:
                # row → base (with size filter), and cover if MUTANT
                if with_fins or unit_cands.bit_count() <= n:
                    base_pool.append((unit_cands, i))
                if fish_cat == _CAT_MUTANT:
                    cover_pool.append((unit_cands, i))
            else:
                # row → cover only (non-MUTANT, lines=False)
                cover_pool.append((unit_cands, i))
        elif i < 18:  # col
            if lines or fish_cat == _CAT_MUTANT:
                # col → cover, and base if MUTANT
                cover_pool.append((unit_cands, i))
                if fish_cat == _CAT_MUTANT:
                    if with_fins or unit_cands.bit_count() <= n:
                        base_pool.append((unit_cands, i))
            else:
                # col → base (with size filter), and cover if MUTANT
                if with_fins or unit_cands.bit_count() <= n:
                    base_pool.append((unit_cands, i))
                if fish_cat == _CAT_MUTANT:
                    cover_pool.append((unit_cands, i))
        else:  # block (i >= 18)
            if fish_cat != _CAT_BASIC:
                cover_pool.append((unit_cands, i))
                if with_fins or unit_cands.bit_count() <= n:
                    base_pool.append((unit_cands, i))

    return base_pool, cover_pool


def _apply_siamese(steps: list[SolutionStep]) -> None:
    """Append siamese combinations to *steps* (modifies in place).

    Two finned/sashimi fish are siamese when they share the same base
    entities (same candidate, same rows/cols) but differ in their fin
    configuration and eliminations.  HoDoKu merges them into a single
    step with the combined cover + fin + elimination sets.
    """
    n = len(steps)
    for i in range(n - 1):
        s1 = steps[i]
        if not s1.base_entities:
            continue
        # Entity is a frozen dataclass with fields .type and .number
        base_key1 = tuple((e.type, e.number) for e in s1.base_entities)
        cand1 = s1.values[0] if s1.values else None
        elim1 = frozenset((c.index, c.value) for c in s1.candidates_to_delete)
        for j in range(i + 1, n):
            s2 = steps[j]
            if not s2.base_entities:
                continue
            if (s2.values[0] if s2.values else None) != cand1:
                continue
            base_key2 = tuple((e.type, e.number) for e in s2.base_entities)
            if base_key1 != base_key2:
                continue
            elim2 = frozenset((c.index, c.value) for c in s2.candidates_to_delete)
            if elim1 == elim2:
                continue
            # Build siamese step: clone s1, add s2's covers/fins/elims
            # Entity and Candidate are frozen dataclasses — safe to share refs
            siam = SolutionStep(s1.type)
            siam.add_value(cand1)
            for idx in s1.indices:
                siam.add_index(idx)
            siam.base_entities.extend(s1.base_entities)
            siam.cover_entities.extend(s1.cover_entities)
            siam.fins.extend(s1.fins)
            for c in s1.candidates_to_delete:
                siam.add_candidate_to_delete(c.index, c.value)
            # Add s2's additional covers, fins, elims
            siam.cover_entities.extend(s2.cover_entities)
            siam.fins.extend(s2.fins)
            for c in s2.candidates_to_delete:
                if (c.index, c.value) not in elim1:
                    siam.add_candidate_to_delete(c.index, c.value)
            steps.append(siam)


class FishSolver:
    """X-Wing, Swordfish, Jellyfish — basic, finned/sashimi, Franken, Mutant."""

    def __init__(self, grid: Grid) -> None:
        self.grid = grid

    def get_step(self, sol_type: SolutionType) -> SolutionStep | None:
        if sol_type in _FISH_SIZE:
            return self._find_basic_fish(sol_type)
        if sol_type in _FINNED_SIZE:
            return self._find_finned_fish(sol_type, sashimi=False)
        if sol_type in _SASHIMI_SIZE:
            return self._find_finned_fish(sol_type, sashimi=True)
        if sol_type in _GENERALIZED_INFO:
            steps = self._find_generalized_fish_all(sol_type)
            return steps[0] if steps else None
        return None

    def find_all(self, sol_type: SolutionType, *, for_candidate: int = -1) -> list[SolutionStep]:
        if sol_type in _FISH_SIZE:
            return self._find_basic_fish_all(sol_type)
        if sol_type in _FINNED_SIZE:
            n = _FINNED_SIZE[sol_type]
            steps = self._find_finned_fish_all(sol_type, sashimi=False)
            if n >= 3:
                # HoDoKu finds finned+sashimi together for siamese combinations
                sashimi_type = _FINNED_TO_SASHIMI[sol_type]
                steps = steps + self._find_finned_fish_all(sashimi_type, sashimi=True)
                _apply_siamese(steps)
            return steps
        if sol_type in _SASHIMI_SIZE:
            n = _SASHIMI_SIZE[sol_type]
            sashimi_steps = self._find_finned_fish_all(sol_type, sashimi=True)
            if n >= 3:
                finned_type = {v: k for k, v in _FINNED_TO_SASHIMI.items()}[sol_type]
                steps = self._find_finned_fish_all(finned_type, sashimi=False) + sashimi_steps
                _apply_siamese(steps)
                return steps
            return sashimi_steps
        if sol_type in _GENERALIZED_INFO:
            steps = self._find_generalized_fish_all(sol_type, for_candidate=for_candidate)
            _apply_siamese(steps)
            return steps
        return []

    def _find_basic_fish_all(self, sol_type: SolutionType) -> list[SolutionStep]:
        """Return ALL basic fish of the given size."""
        n = _FISH_SIZE[sol_type]
        grid = self.grid
        results: list[SolutionStep] = []
        seen_elims: set[tuple] = set()

        for cand in range(1, 10):
            cand_set = grid.candidate_sets[cand]
            if not cand_set:
                continue

            for row_mode in (True, False):
                unit_masks  = LINE_MASKS if row_mode else COL_MASKS
                cover_masks = COL_MASKS  if row_mode else LINE_MASKS

                eligible: list[int] = []
                for u in range(9):
                    cnt = (cand_set & unit_masks[u]).bit_count()
                    if 2 <= cnt <= n:
                        eligible.append(u)

                if len(eligible) < n:
                    continue

                for combo in combinations(eligible, n):
                    base_mask = 0
                    for u in combo:
                        base_mask |= cand_set & unit_masks[u]

                    cover_indices: list[int] = []
                    for ci in range(9):
                        if base_mask & cover_masks[ci]:
                            cover_indices.append(ci)

                    if len(cover_indices) != n:
                        continue

                    cover_mask = 0
                    for ci in cover_indices:
                        cover_mask |= cover_masks[ci]

                    elim_mask = cand_set & cover_mask & ~base_mask
                    if not elim_mask:
                        continue

                    elim_key = (cand, elim_mask)
                    if elim_key in seen_elims:
                        continue
                    seen_elims.add(elim_key)

                    results.append(self._make_step(
                        sol_type, cand, combo, cover_indices,
                        base_mask, elim_mask, row_mode
                    ))

        return results

    def _find_finned_fish_all(
        self, sol_type: SolutionType, sashimi: bool
    ) -> list[SolutionStep]:
        """Return ALL finned/sashimi fish of the given size."""
        n = _SASHIMI_SIZE[sol_type] if sashimi else _FINNED_SIZE[sol_type]
        finned_type = sol_type if not sashimi else {
            v: k for k, v in _FINNED_TO_SASHIMI.items()
        }[sol_type]
        grid = self.grid
        results: list[SolutionStep] = []
        seen_elims: set[tuple] = set()

        for cand in range(1, 10):
            cand_set = grid.candidate_sets[cand]
            if not cand_set:
                continue

            for row_mode in (True, False):
                unit_masks  = LINE_MASKS if row_mode else COL_MASKS
                cover_masks = COL_MASKS  if row_mode else LINE_MASKS

                eligible: list[int] = []
                for u in range(9):
                    if cand_set & unit_masks[u]:
                        eligible.append(u)

                if len(eligible) < n:
                    continue

                for combo in combinations(eligible, n):
                    base_mask = 0
                    for u in combo:
                        base_mask |= cand_set & unit_masks[u]

                    cover_indices: list[int] = []
                    for ci in range(9):
                        if base_mask & cover_masks[ci]:
                            cover_indices.append(ci)

                    if len(cover_indices) < n or len(cover_indices) > n + 3:
                        continue

                    for cover_combo in combinations(cover_indices, n):
                        cover_mask = 0
                        for ci in cover_combo:
                            cover_mask |= cover_masks[ci]

                        fin_mask = base_mask & ~cover_mask
                        if not fin_mask:
                            continue
                        if fin_mask.bit_count() > 5:
                            continue

                        fin_common = _fin_buddies(fin_mask)
                        elim_mask = cand_set & cover_mask & fin_common & ~base_mask
                        if not elim_mask:
                            continue

                        is_sashimi = False
                        for u in combo:
                            body = cand_set & unit_masks[u] & cover_mask
                            if body.bit_count() <= 1:
                                is_sashimi = True
                                break

                        if is_sashimi != sashimi:
                            continue

                        actual_type = (
                            _FINNED_TO_SASHIMI[finned_type]
                            if is_sashimi else finned_type
                        )

                        elim_key = (cand, row_mode, elim_mask, fin_mask)
                        if elim_key in seen_elims:
                            continue
                        seen_elims.add(elim_key)

                        results.append(self._make_step(
                            actual_type, cand, combo, list(cover_combo),
                            base_mask, elim_mask, row_mode,
                            fin_mask=fin_mask,
                        ))

        return results

    # ------------------------------------------------------------------
    # Core algorithm
    # ------------------------------------------------------------------

    def _find_basic_fish(self, sol_type: SolutionType) -> SolutionStep | None:
        """Search for a basic fish of the given size.

        Row-mode: base = rows, cover = cols.
        Col-mode: base = cols, cover = rows.
        For each candidate digit, try all C(9, n) combinations of base units
        where the digit appears 2..n times.  If those n base units span exactly
        n cover units, any candidates in the cover units outside the base can
        be eliminated.
        """
        n = _FISH_SIZE[sol_type]
        grid = self.grid

        for cand in range(1, 10):
            cand_set = grid.candidate_sets[cand]
            if not cand_set:
                continue

            for row_mode in (True, False):
                unit_masks  = LINE_MASKS if row_mode else COL_MASKS
                cover_masks = COL_MASKS  if row_mode else LINE_MASKS
                units       = LINES      if row_mode else COLS

                # Collect candidate base units (those with 2..n occurrences)
                eligible: list[int] = []
                for u in range(9):
                    cnt = (cand_set & unit_masks[u]).bit_count()
                    if 2 <= cnt <= n:
                        eligible.append(u)

                if len(eligible) < n:
                    continue

                for combo in combinations(eligible, n):
                    # Union of candidate cells across these n base units
                    base_mask = 0
                    for u in combo:
                        base_mask |= cand_set & unit_masks[u]

                    # Which perpendicular units do these cells span?
                    cover_indices: list[int] = []
                    for ci in range(9):
                        if base_mask & cover_masks[ci]:
                            cover_indices.append(ci)

                    if len(cover_indices) != n:
                        continue  # not a fish

                    # Elimination: candidates in cover units but not in base
                    cover_mask = 0
                    for ci in cover_indices:
                        cover_mask |= cover_masks[ci]

                    elim_mask = cand_set & cover_mask & ~base_mask
                    if not elim_mask:
                        continue

                    return self._make_step(
                        sol_type, cand, combo, cover_indices,
                        base_mask, elim_mask, row_mode
                    )

        return None

    def _find_finned_fish(
        self, sol_type: SolutionType, sashimi: bool
    ) -> SolutionStep | None:
        """Search for a finned or sashimi fish of the given size.

        A finned fish is like a basic fish but some base cells fall outside
        the n cover units — these are 'fins'.  All fins must share one block.
        Eliminations: candidates in the cover units that are also in the fin
        block, but not in any base unit.

        Sashimi: same pattern, but at least one base unit has all its cells
        as fins (it contributes nothing to the body).
        """
        n = _SASHIMI_SIZE[sol_type] if sashimi else _FINNED_SIZE[sol_type]
        # The canonical type for step construction is the FINNED variant;
        # we decide finned vs sashimi per found fish.
        finned_type = sol_type if not sashimi else {
            v: k for k, v in _FINNED_TO_SASHIMI.items()
        }[sol_type]
        grid = self.grid

        for cand in range(1, 10):
            cand_set = grid.candidate_sets[cand]
            if not cand_set:
                continue

            for row_mode in (True, False):
                unit_masks  = LINE_MASKS if row_mode else COL_MASKS
                cover_masks = COL_MASKS  if row_mode else LINE_MASKS

                # Eligible base units: any unit with ≥1 occurrence
                # (fins can make a unit appear to have too many cells)
                eligible: list[int] = []
                for u in range(9):
                    if cand_set & unit_masks[u]:
                        eligible.append(u)

                if len(eligible) < n:
                    continue

                for combo in combinations(eligible, n):
                    base_mask = 0
                    for u in combo:
                        base_mask |= cand_set & unit_masks[u]

                    # All cover units hit by the base cells
                    cover_indices: list[int] = []
                    for ci in range(9):
                        if base_mask & cover_masks[ci]:
                            cover_indices.append(ci)

                    # Need at least n covers; skip if far too many (performance)
                    if len(cover_indices) < n or len(cover_indices) > n + 3:
                        continue

                    # Try every n-subset of cover_indices as the main covers
                    for cover_combo in combinations(cover_indices, n):
                        cover_mask = 0
                        for ci in cover_combo:
                            cover_mask |= cover_masks[ci]

                        fin_mask = base_mask & ~cover_mask
                        if not fin_mask:
                            continue  # basic fish, handled elsewhere
                        if fin_mask.bit_count() > 5:
                            continue

                        # Eliminations: cover candidates that see ALL fin cells
                        fin_common = _fin_buddies(fin_mask)
                        elim_mask = cand_set & cover_mask & fin_common & ~base_mask
                        if not elim_mask:
                            continue

                        # Sashimi: any base unit has ≤1 body cell (HoDoKu definition)
                        is_sashimi = False
                        for u in combo:
                            body = cand_set & unit_masks[u] & cover_mask
                            if body.bit_count() <= 1:
                                is_sashimi = True
                                break

                        if is_sashimi != sashimi:
                            continue

                        actual_type = (
                            _FINNED_TO_SASHIMI[finned_type]
                            if is_sashimi else finned_type
                        )
                        return self._make_step(
                            actual_type, cand, combo, list(cover_combo),
                            base_mask, elim_mask, row_mode,
                            fin_mask=fin_mask,
                        )

        return None

    # ------------------------------------------------------------------
    # Generalized fish (Franken / Mutant)
    # ------------------------------------------------------------------

    def _find_generalized_fish_all(
        self, sol_type: SolutionType, *, for_candidate: int = -1
    ) -> list[SolutionStep]:
        """Find all Franken or Mutant fish of the requested type.

        Mirrors Java FishSolver.getFishes() with FRANKEN or MUTANT fish_type.
        When for_candidate is 1-9, only that digit is searched (much faster).
        """
        fish_cat, n, with_fins = _GENERALIZED_INFO[sol_type]
        grid = self.grid
        results: list[SolutionStep] = []
        seen_elims: set[tuple] = set()

        # MUTANT: only one orientation (lines=True) since all units go to both
        # pools regardless of orientation.
        # FRANKEN: two orientations to cover both row-base and col-base setups.
        orientations = [True] if fish_cat == _CAT_MUTANT else [True, False]

        for cand in range(1, 10):
            if for_candidate != -1 and cand != for_candidate:
                continue
            cand_set = grid.candidate_sets[cand]
            if not cand_set:
                continue

            for lines in orientations:
                base_pool, cover_pool = _build_unit_pools(
                    cand_set, fish_cat, lines, n, with_fins
                )
                if len(base_pool) < n:
                    continue

                for base_combo in combinations(range(len(base_pool)), n):
                    # Accumulate base candidates and track endo fins
                    base_cand = 0
                    endo_fins = 0
                    skip = False
                    for bi in base_combo:
                        overlap = base_cand & base_pool[bi][0]
                        if overlap:
                            if not with_fins:
                                # Basic fish: no endo fins allowed
                                skip = True
                                break
                            if (endo_fins | overlap).bit_count() > _MAX_ENDO_FINS:
                                skip = True
                                break
                            endo_fins |= overlap
                        base_cand |= base_pool[bi][0]
                    if skip:
                        continue

                    # Unit indices used as base (to exclude from cover)
                    base_ids = frozenset(base_pool[bi][1] for bi in base_combo)

                    # Eligible cover units: not a base unit, intersects base_cand
                    cover_eligible = [
                        (mask, idx) for mask, idx in cover_pool
                        if idx not in base_ids and (mask & base_cand)
                    ]
                    if len(cover_eligible) < n:
                        continue

                    # Precompute base classification bits (same for all cover combos)
                    base_bits = 0
                    for bi in base_combo:
                        base_bits |= _unit_type_bit(base_pool[bi][1])

                    num_cover = len(cover_eligible)

                    if _accel_find_covers is not None:
                        # ---- C-accelerated cover search ----
                        _ce_lo = (ctypes.c_uint64 * num_cover)()
                        _ce_hi = (ctypes.c_uint64 * num_cover)()
                        for i in range(num_cover):
                            m = cover_eligible[i][0]
                            _ce_lo[i] = m & _LO_MASK
                            _ce_hi[i] = m >> _HI_SHIFT
                        _max_out = 10000
                        _out = (_FishResult * _max_out)()
                        nfound = _accel_find_covers(
                            _ce_lo, _ce_hi, num_cover, n,
                            base_cand & _LO_MASK, base_cand >> _HI_SHIFT,
                            cand_set & _LO_MASK, cand_set >> _HI_SHIFT,
                            1 if with_fins else 0, _MAX_FINS,
                            endo_fins & _LO_MASK, endo_fins >> _HI_SHIFT,
                            _out, _max_out,
                        )
                        for ri in range(min(nfound, _max_out)):
                            r = _out[ri]
                            cover_cand = r.cover_lo | (r.cover_hi << _HI_SHIFT)
                            fins = r.fins_lo | (r.fins_hi << _HI_SHIFT)
                            elim = r.elim_lo | (r.elim_hi << _HI_SHIFT)
                            # Classify
                            cover_bits = 0
                            for k in range(n):
                                cover_bits |= _unit_type_bit(cover_eligible[r.indices[k]][1])
                            actual_cat = _classify_fish(base_bits, cover_bits)
                            if actual_cat != fish_cat:
                                continue
                            elim_key = (cand, elim)
                            if elim_key in seen_elims:
                                continue
                            seen_elims.add(elim_key)
                            results.append(self._make_general_step(
                                sol_type, cand,
                                [base_pool[bi] for bi in base_combo],
                                [cover_eligible[r.indices[k]] for k in range(n)],
                                base_cand, elim, fins, endo_fins,
                            ))
                    else:
                        # ---- Pure Python fallback (DFS with pruning) ----
                        ce_masks = [cover_eligible[i][0] for i in range(num_cover)]
                        _cc = [0] * (n + 1)
                        _cn = [0] * (n + 1)
                        _ni = [0] * (n + 1)
                        _pi = [0] * (n + 1)
                        level = 1
                        _ni[1] = 0
                        while True:
                            while _ni[level] > num_cover - (n - level + 1):
                                level -= 1
                                if level == 0:
                                    break
                            if level == 0:
                                break
                            ci = _ni[level]
                            _ni[level] = ci + 1
                            _pi[level] = ci
                            mask = ce_masks[ci]
                            prev_cand = _cc[level - 1]
                            new_cand = prev_cand | mask
                            overlap = prev_cand & mask
                            new_cannibal = _cn[level - 1]
                            if overlap:
                                new_cannibal |= overlap
                            if level < n:
                                if with_fins and not (base_cand & ~new_cand):
                                    continue
                                _cc[level] = new_cand
                                _cn[level] = new_cannibal
                                level += 1
                                _ni[level] = ci + 1
                            else:
                                fins = base_cand & ~new_cand
                                # Java includes endo fins in the fin set for
                                # both the finnless/finned decision and the
                                # fin_buddies elimination check.
                                all_fins = fins | endo_fins
                                if not with_fins:
                                    if all_fins:
                                        continue
                                    elim = cand_set & new_cand & ~base_cand
                                    if new_cannibal:
                                        elim |= cand_set & new_cannibal
                                    if not elim:
                                        continue
                                else:
                                    fin_count = all_fins.bit_count()
                                    if fin_count == 0:
                                        continue
                                    if fin_count > _MAX_FINS:
                                        continue
                                    fin_buddies = _fin_buddies(all_fins)
                                    elim = cand_set & new_cand & fin_buddies & ~base_cand
                                    if new_cannibal:
                                        elim |= cand_set & new_cannibal & fin_buddies
                                    if not elim:
                                        continue
                                cover_bits = 0
                                for lv in range(1, n + 1):
                                    cover_bits |= _unit_type_bit(cover_eligible[_pi[lv]][1])
                                actual_cat = _classify_fish(base_bits, cover_bits)
                                if actual_cat != fish_cat:
                                    continue
                                elim_key = (cand, elim)
                                if elim_key in seen_elims:
                                    continue
                                seen_elims.add(elim_key)
                                results.append(self._make_general_step(
                                    sol_type, cand,
                                    [base_pool[bi] for bi in base_combo],
                                    [cover_eligible[_pi[lv]] for lv in range(1, n + 1)],
                                    base_cand, elim, fins, endo_fins,
                                ))

        return results

    def _make_general_step(
        self,
        sol_type: SolutionType,
        cand: int,
        base_units: list[tuple[int, int]],  # (unit_cands, unit_idx)
        cover_units: list[tuple[int, int]],
        base_cand: int,
        elim: int,
        fins: int,
        endo_fins: int,
    ) -> SolutionStep:
        """Build a SolutionStep for a Franken/Mutant fish."""
        step = SolutionStep(sol_type)
        step.add_value(cand)

        # Body cells: base candidates minus external fins
        body = base_cand & ~fins
        tmp = body
        while tmp:
            lsb = tmp & -tmp
            step.add_index(lsb.bit_length() - 1)
            tmp ^= lsb

        # External fins (fins excluding endo fins)
        from hodoku.core.solution_step import Candidate
        ext_fins = fins & ~endo_fins
        tmp = ext_fins
        while tmp:
            lsb = tmp & -tmp
            step.fins.append(Candidate(lsb.bit_length() - 1, cand))
            tmp ^= lsb

        # Endo fins
        tmp = endo_fins
        while tmp:
            lsb = tmp & -tmp
            step.endo_fins.append(Candidate(lsb.bit_length() - 1, cand))
            tmp ^= lsb

        # Base entities
        for _mask, uid in base_units:
            if uid < 9:
                step.base_entities.append(Entity(_LINE, uid + 1))
            elif uid < 18:
                step.base_entities.append(Entity(_COL, uid - 9 + 1))
            else:
                step.base_entities.append(Entity(_BLOCK_ENT, uid - 18 + 1))

        # Cover entities
        for _mask, uid in cover_units:
            if uid < 9:
                step.cover_entities.append(Entity(_LINE, uid + 1))
            elif uid < 18:
                step.cover_entities.append(Entity(_COL, uid - 9 + 1))
            else:
                step.cover_entities.append(Entity(_BLOCK_ENT, uid - 18 + 1))

        # Eliminations
        tmp = elim
        while tmp:
            lsb = tmp & -tmp
            step.add_candidate_to_delete(lsb.bit_length() - 1, cand)
            tmp ^= lsb

        return step

    # ------------------------------------------------------------------
    # Step construction
    # ------------------------------------------------------------------

    def _make_step(
        self,
        sol_type: SolutionType,
        cand: int,
        base_units: tuple[int, ...],
        cover_units: list[int],
        base_mask: int,
        elim_mask: int,
        row_mode: bool,
        fin_mask: int = 0,
    ) -> SolutionStep:
        step = SolutionStep(sol_type)
        step.add_value(cand)

        # Indices: body cells (base minus fins) carry the fish pattern;
        # fin cells are recorded in step.fins
        body_mask = base_mask & ~fin_mask
        tmp = body_mask
        while tmp:
            lsb = tmp & -tmp
            step.add_index(lsb.bit_length() - 1)
            tmp ^= lsb

        # Fin cells
        from hodoku.core.solution_step import Candidate
        tmp = fin_mask
        while tmp:
            lsb = tmp & -tmp
            step.fins.append(Candidate(lsb.bit_length() - 1, cand))
            tmp ^= lsb

        # Base entities (rows or cols)
        base_type  = _LINE if row_mode else _COL
        cover_type = _COL  if row_mode else _LINE
        for u in base_units:
            step.base_entities.append(Entity(base_type, u + 1))  # 1-based
        for ci in cover_units:
            step.cover_entities.append(Entity(cover_type, ci + 1))

        # Eliminations
        tmp = elim_mask
        while tmp:
            lsb = tmp & -tmp
            step.add_candidate_to_delete(lsb.bit_length() - 1, cand)
            tmp ^= lsb

        return step
