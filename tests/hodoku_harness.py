"""HoDoKu validation harness.

Runs the HoDoKu JAR via hodoku.sh and parses the /vp (solution path) output
into structured Python objects for comparison against our solver.

Usage:
    python tests/hodoku_harness.py <81-char-puzzle>
"""

from __future__ import annotations

import re
import subprocess
import sys
import warnings
from dataclasses import dataclass, field
from pathlib import Path

from hodoku.core.types import DifficultyType, SolutionType

# ---------------------------------------------------------------------------
# Project root — hodoku.sh lives here
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class HodokuStep:
    technique: str                              # raw name from HoDoKu output
    solution_type: SolutionType | None          # mapped enum, or None if unknown
    indices: list[int] = field(default_factory=list)     # 0-based cells being SET
    values: list[int] = field(default_factory=list)      # digits being placed
    eliminations: list[tuple[int, int]] = field(default_factory=list)  # (cell, digit)


@dataclass
class HodokuResult:
    puzzle: str
    level: DifficultyType
    score: int
    steps: list[HodokuStep]
    solved: bool


# ---------------------------------------------------------------------------
# Technique name → SolutionType mapping
#
# HoDoKu step names come from SolutionType.properties. Most match our
# SolutionType enum values directly; exceptions are noted below.
# ---------------------------------------------------------------------------

def _build_name_map() -> dict[str, SolutionType]:
    # Start with a reverse map from each SolutionType's value string
    m: dict[str, SolutionType] = {t.value: t for t in SolutionType}

    # HoDoKu outputs generic names for grouped types; map to primary variant
    extras = {
        # HoDoKu properties key → our SolutionType
        "Almost Locked Set Chain":      SolutionType.ALS_XY_CHAIN,   # properties mismatch
        "Simple Colors":                SolutionType.SIMPLE_COLORS_TRAP,
        "Simple Colors Trap":           SolutionType.SIMPLE_COLORS_TRAP,
        "Simple Colors Wrap":           SolutionType.SIMPLE_COLORS_WRAP,
        "Multi Colors":                 SolutionType.MULTI_COLORS_1,
        "Multi Colors 1":               SolutionType.MULTI_COLORS_1,
        "Multi Colors 2":               SolutionType.MULTI_COLORS_2,
        "Nice Loop/AIC":                SolutionType.CONTINUOUS_NICE_LOOP,
        "Grouped Nice Loop/AIC":        SolutionType.GROUPED_CONTINUOUS_NICE_LOOP,
        "Forcing Chain":                SolutionType.FORCING_CHAIN_CONTRADICTION,
        "Forcing Net":                  SolutionType.FORCING_NET_CONTRADICTION,
        "Kraken Fish":                  SolutionType.KRAKEN_FISH_TYPE_1,
        "Incomplete Solution!":         SolutionType.INCOMPLETE,
        "Locked Candidates":            SolutionType.LOCKED_CANDIDATES_1,
    }
    m.update(extras)
    return m


_NAME_MAP: dict[str, SolutionType] = _build_name_map()

_LEVEL_MAP: dict[str, DifficultyType] = {
    "Incomplete": DifficultyType.INCOMPLETE,
    "Easy":       DifficultyType.EASY,
    "Medium":     DifficultyType.MEDIUM,
    "Hard":       DifficultyType.HARD,
    "Unfair":     DifficultyType.UNFAIR,
    "Extreme":    DifficultyType.EXTREME,
}


# ---------------------------------------------------------------------------
# Compact cell notation decoder
#
# HoDoKu compresses sets of cells sharing a row or column:
#   r1c5       → single cell: row 1, col 5
#   r1c45      → two cells in row 1: cols 4 and 5
#   r13c5      → two cells in col 5: rows 1 and 3
#   r1c45,r2c3 → three separate cells
#
# Each digit in the row/col part is one row/col number (1-9).
# ---------------------------------------------------------------------------

_COMPACT_RE = re.compile(r"r(\d+)c(\d+)")


def _parse_compact_cells(cell_str: str) -> list[int]:
    """Decode a compact cell string into a list of 0-based cell indices."""
    indices: list[int] = []
    for group in cell_str.split(","):
        group = group.strip()
        m = _COMPACT_RE.match(group)
        if not m:
            continue
        rows = [int(d) for d in m.group(1)]
        cols = [int(d) for d in m.group(2)]
        for r in rows:
            for c in cols:
                indices.append((r - 1) * 9 + (c - 1))
    return indices


# ---------------------------------------------------------------------------
# Step line parser
# ---------------------------------------------------------------------------

_PLACEMENT_RE = re.compile(r"r(\d)c(\d)=(\d)")
_ELIM_GROUP_RE = re.compile(r"([r\d,c]+)<>(\d)")


def _parse_step_line(line: str) -> HodokuStep | None:
    """Parse one indented step line. Returns None if the line is not a step."""
    line = line.strip()
    if not line:
        return None

    # Some techniques (e.g. BUG+1) use "Technique Name => elims" without a colon
    if ":" not in line:
        if "=>" not in line:
            return None
        arrow = line.index("=>")
        technique = line[:arrow].strip()
        rest = line[arrow:]  # keep "=>" so the elimination parser below works
    else:
        colon = line.index(":")
        technique = line[:colon].strip()
        rest = line[colon + 1:].strip()

    solution_type = _NAME_MAP.get(technique)
    if solution_type is None:
        warnings.warn(f"Unknown technique name: {technique!r}", stacklevel=2)

    step = HodokuStep(technique=technique, solution_type=solution_type)

    if "=>" in rest:
        # Elimination step: "<context> => <cells><>digit, ..."
        # Cell groups can contain commas (e.g. "r7c12,r9c5<>5") so we use
        # finditer rather than splitting on commas first.
        elim_part = rest.split("=>", 1)[1].strip()
        for m in _ELIM_GROUP_RE.finditer(elim_part):
            cells = _parse_compact_cells(m.group(1))
            digit = int(m.group(2))
            for cell in cells:
                step.eliminations.append((cell, digit))
    else:
        # Placement step: "r<r>c<c>=<digit>"
        m = _PLACEMENT_RE.search(rest)
        if m:
            row, col, digit = int(m.group(1)), int(m.group(2)), int(m.group(3))
            step.indices.append((row - 1) * 9 + (col - 1))
            step.values.append(digit)

    return step


# ---------------------------------------------------------------------------
# Output parser
# ---------------------------------------------------------------------------

_HEADER_RE = re.compile(
    r"^([0-9.]{81})\s+#\d+\s+(\w+)\s+\((\d+)\)"
)


def parse_hodoku_output(output: str) -> HodokuResult | None:
    """Parse the stdout from `hodoku.sh /vp /o stdout <puzzle>`.

    Returns None if no valid result line is found.
    """
    lines = output.splitlines()
    puzzle = ""
    level = DifficultyType.INCOMPLETE
    score = 0
    steps: list[HodokuStep] = []
    solved = True

    for line in lines:
        # "0 puzzles not solved logically" is the success case — only fail on non-zero
        if "Invalid solution:" in line or re.search(r"[1-9]\d* puzzles not solved", line):
            solved = False

        m = _HEADER_RE.match(line.strip())
        if m:
            puzzle = m.group(1)
            level = _LEVEL_MAP.get(m.group(2), DifficultyType.INCOMPLETE)
            score = int(m.group(3))
            continue

        # Step lines are indented with exactly 3 spaces and contain = or <> (not stats)
        if line.startswith("   ") and not line.startswith("    "):
            if "=" in line or "<>" in line:
                step = _parse_step_line(line)
                if step is not None and (step.indices or step.eliminations):
                    steps.append(step)

    if not puzzle:
        return None

    return HodokuResult(
        puzzle=puzzle,
        level=level,
        score=score,
        steps=steps,
        solved=solved,
    )


# ---------------------------------------------------------------------------
# Batch output parser
# ---------------------------------------------------------------------------

def parse_hodoku_batch_output(output: str) -> dict[str, HodokuResult]:
    """Parse the stdout from a batch HoDoKu run (`/vp /o stdout /bs <file>`).

    Returns a dict mapping puzzle string → HodokuResult.
    """
    results: dict[str, HodokuResult] = {}
    # Split on puzzle header lines; each starts with an 81-digit string
    sections = re.split(r"(?m)(?=^[0-9.]{81}\s+#\d+)", output)
    for section in sections:
        if not section.strip():
            continue
        result = parse_hodoku_output(section)
        if result and result.puzzle:
            results[result.puzzle] = result
    return results


# ---------------------------------------------------------------------------
# Subprocess runner
# ---------------------------------------------------------------------------

def run_hodoku(puzzle: str, timeout: int = 30) -> HodokuResult | None:
    """Run HoDoKu on *puzzle* and return a parsed HodokuResult, or None on error."""
    hodoku_sh = PROJECT_ROOT / "hodoku" / "hodoku.sh"
    if not hodoku_sh.exists():
        raise FileNotFoundError(f"hodoku.sh not found at {hodoku_sh}")

    hodoku_jar = PROJECT_ROOT / "hodoku" / "hodoku.jar"
    cmd = ["java", "-Xmx512m",
           "-Djava.util.logging.config.file=/dev/null",
           "-jar", str(hodoku_jar),
           "/vp", "/o", "stdout", puzzle]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(PROJECT_ROOT),
        )
        output = result.stdout
        if result.returncode != 0 and not output:
            warnings.warn(
                f"HoDoKu exited with code {result.returncode}: {result.stderr[:200]}",
                stacklevel=2,
            )
            return None
        return parse_hodoku_output(output)
    except subprocess.TimeoutExpired:
        warnings.warn(f"HoDoKu timed out after {timeout}s", stacklevel=2)
        return None
    except FileNotFoundError as e:
        raise RuntimeError(f"bash or hodoku.sh not found: {e}") from e


# ---------------------------------------------------------------------------
# Batch subprocess runner
# ---------------------------------------------------------------------------

def run_hodoku_batch(
    puzzles: list[str],
    timeout: int = 300,
) -> dict[str, HodokuResult]:
    """Run HoDoKu on *puzzles* in a single JVM invocation.

    Writes puzzles to a temp file, runs HoDoKu with ``/bs``, and returns
    a mapping of puzzle string → HodokuResult.  Unknown/invalid puzzles are
    silently omitted from the result dict.
    """
    import os
    import tempfile

    if not puzzles:
        return {}

    hodoku_jar = PROJECT_ROOT / "hodoku" / "hodoku.jar"
    if not hodoku_jar.exists():
        raise FileNotFoundError(f"hodoku.jar not found at {hodoku_jar}")

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as tmp:
        for p in puzzles:
            tmp.write(p + "\n")
        tmpfile = tmp.name

    cmd = [
        "java", "-Xmx512m",
        "-Djava.util.logging.config.file=/dev/null",
        "-jar", str(hodoku_jar),
        "/vp", "/o", "stdout", "/bs", tmpfile,
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(PROJECT_ROOT),
        )
        if result.returncode != 0 and not result.stdout:
            warnings.warn(
                f"HoDoKu batch exited {result.returncode}: {result.stderr[:200]}",
                stacklevel=2,
            )
            return {}
        return parse_hodoku_batch_output(result.stdout)
    except subprocess.TimeoutExpired:
        warnings.warn(f"HoDoKu batch timed out after {timeout}s", stacklevel=2)
        return {}
    finally:
        os.unlink(tmpfile)


# ---------------------------------------------------------------------------
# Manual test entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) != 2 or len(sys.argv[1]) != 81:
        print("Usage: python tests/hodoku_harness.py <81-char-puzzle>")
        sys.exit(1)

    puzzle_str = sys.argv[1]
    res = run_hodoku(puzzle_str)
    if res is None:
        print("No result returned (HoDoKu error or invalid puzzle).")
        sys.exit(1)

    print(f"Puzzle:  {res.puzzle}")
    print(f"Level:   {res.level.name}")
    print(f"Score:   {res.score}")
    print(f"Solved:  {res.solved}")
    print(f"Steps:   {len(res.steps)}")
    print()
    for i, step in enumerate(res.steps, 1):
        st = step.solution_type.name if step.solution_type else "UNKNOWN"
        if step.indices:
            cell = step.indices[0]
            r, c = cell // 9 + 1, cell % 9 + 1
            print(f"  {i:3}. {step.technique} -> r{r}c{c}={step.values[0]}  [{st}]")
        else:
            elim_summary = ", ".join(
                f"r{e[0]//9+1}c{e[0]%9+1}<>{e[1]}" for e in step.eliminations[:3]
            )
            if len(step.eliminations) > 3:
                elim_summary += f" (+{len(step.eliminations)-3} more)"
            print(f"  {i:3}. {step.technique} => {elim_summary}  [{st}]")
