#!/usr/bin/env python3
"""Find a "clean" test puzzle for a given HoDoKu technique.

A clean puzzle is one where HoDoKu's full solution uses only techniques that
our solver already implements (rows 1-9 of the roadmap).  Running with a
technique that our solver produces is a prerequisite for adding a validated
test case to tests/test_validate_*.py.

Usage:
    python scripts/find_clean_puzzle.py --tech SKYSCRAPER
    python scripts/find_clean_puzzle.py --tech EMPTY_RECTANGLE --seeds 0-2000
    python scripts/find_clean_puzzle.py --tech XY_WING --allowed "XY-Wing"

The --allowed flag ADDS extra technique names (as printed by HoDoKu /vp) to
the default allowed set.  Use it when you're testing a technique that depends
on other newly-implemented techniques.
"""

from __future__ import annotations

import argparse
import os
import random
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Inline minimal backtracking generator (no external deps)
# ---------------------------------------------------------------------------

def _backtrack(grid: list[int]) -> bool:
    for i in range(81):
        if grid[i] == 0:
            r, c = i // 9, i % 9
            box = (r // 3) * 3 + c // 3
            used: set[int] = set()
            for j in range(9):
                used.add(grid[r * 9 + j])
                used.add(grid[j * 9 + c])
                br, bc = (box // 3) * 3 + j // 3, (box % 3) * 3 + j % 3
                used.add(grid[br * 9 + bc])
            digits = list(set(range(1, 10)) - used)
            random.shuffle(digits)
            for d in digits:
                grid[i] = d
                if _backtrack(grid):
                    return True
                grid[i] = 0
            return False
    return True


def _count_solutions(grid: list[int], limit: int = 2) -> int:
    count = [0]

    def _solve(g: list[int]) -> None:
        if count[0] >= limit:
            return
        for i in range(81):
            if g[i] == 0:
                r, c = i // 9, i % 9
                box = (r // 3) * 3 + c // 3
                used: set[int] = set()
                for j in range(9):
                    used.add(g[r * 9 + j])
                    used.add(g[j * 9 + c])
                    br, bc = (box // 3) * 3 + j // 3, (box % 3) * 3 + j % 3
                    used.add(g[br * 9 + bc])
                for d in set(range(1, 10)) - used:
                    if count[0] >= limit:
                        return
                    g[i] = d
                    _solve(g)
                    g[i] = 0
                return
        count[0] += 1

    _solve(grid[:])
    return count[0]


def generate_puzzle(seed: int) -> str:
    random.seed(seed)
    grid: list[int] = [0] * 81
    _backtrack(grid)
    cells = list(range(81))
    random.shuffle(cells)
    for cell in cells:
        bak = grid[cell]
        grid[cell] = 0
        if _count_solutions(grid) != 1:
            grid[cell] = bak
    return "".join(map(str, grid))


# ---------------------------------------------------------------------------
# HoDoKu helpers
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[1]
_HODOKU_SH  = _REPO_ROOT / "hodoku" / "hodoku.sh"

_BASE_ALLOWED = {
    "Full House",
    "Naked Single",
    "Hidden Single",
    "Locked Candidates Type 1 (Pointing)",
    "Locked Candidates Type 2 (Claiming)",
    "Naked Pair",
    "Naked Triple",
    "Naked Quadruple",
    "Hidden Pair",
    "Hidden Triple",
    "Hidden Quadruple",
    "Locked Pair",
    "Locked Triple",
    "Skyscraper",
    "2-String Kite",
    "Empty Rectangle",
}


def hodoku_techniques(puzzle: str) -> set[str]:
    """Return the set of technique names HoDoKu uses to solve puzzle."""
    env = {**os.environ, "MSYS_NO_PATHCONV": "1"}
    proc = subprocess.run(
        ["bash", str(_HODOKU_SH), "/vp", "/o", "stdout", puzzle],
        capture_output=True, text=True, timeout=10, env=env,
        cwd=str(_REPO_ROOT),
    )
    techs: set[str] = set()
    for line in proc.stdout.splitlines():
        line = line.strip()
        if ":" in line:
            tech = line.split(":")[0].strip()
            if tech and tech[0].isalpha():
                techs.add(tech)
    return techs


def our_solver_uses(puzzle: str, technique_name: str) -> bool:
    """Return True if our solver applies the named SolutionType to this puzzle."""
    sys.path.insert(0, str(_REPO_ROOT / "src"))
    from hodoku.solver.solver import SudokuSolver  # noqa: PLC0415
    from hodoku.core.types import SolutionType      # noqa: PLC0415

    try:
        target = SolutionType[technique_name]
    except KeyError:
        raise SystemExit(f"Unknown technique: {technique_name}. "
                         f"Valid names: {[t.name for t in SolutionType]}")

    solver = SudokuSolver()
    result = solver.solve(puzzle)
    return any(s.type == target for s in result.steps)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tech", required=True,
                        help="SolutionType enum name, e.g. SKYSCRAPER, XY_WING")
    parser.add_argument("--seeds", default="0-500",
                        help="Seed range to search, e.g. 0-1000 (default: 0-500)")
    parser.add_argument("--allowed", nargs="*", default=[],
                        help="Extra HoDoKu technique names to allow (space-separated)")
    parser.add_argument("--limit", type=int, default=5,
                        help="Stop after finding this many clean puzzles (default: 5)")
    args = parser.parse_args()

    start_s, end_s = args.seeds.split("-")
    seed_range = range(int(start_s), int(end_s))
    allowed = _BASE_ALLOWED | set(args.allowed) | {args.tech.replace("_", "-").title()}
    # Also accept the raw HoDoKu display name the user might pass
    hodoku_name = args.tech.replace("_", " ").title()
    allowed.add(hodoku_name)

    print(f"Searching seeds {args.seeds} for clean {args.tech} puzzle...")
    print(f"Allowed techniques: {sorted(allowed)}\n")

    found = 0
    for seed in seed_range:
        puzzle = generate_puzzle(seed)

        # Quick pre-filter: does our solver even use the technique?
        if not our_solver_uses(puzzle, args.tech):
            continue

        # Slower check: does HoDoKu use it, and only allowed techniques?
        try:
            techs = hodoku_techniques(puzzle)
        except subprocess.TimeoutExpired:
            continue

        hodoku_name_check = next(
            (t for t in techs if t.lower() == args.tech.replace("_", " ").lower()),
            None,
        )
        if hodoku_name_check is None:
            continue  # HoDoKu didn't use it

        unknown = techs - allowed
        if unknown:
            print(f"  SEED={seed}: dirty ({unknown})")
            continue

        print(f"CLEAN SEED={seed}: {puzzle}")
        print(f"  techniques: {sorted(techs)}")
        found += 1
        if found >= args.limit:
            break

    if found == 0:
        print("No clean puzzles found in this seed range. Try a wider range.")


if __name__ == "__main__":
    main()
