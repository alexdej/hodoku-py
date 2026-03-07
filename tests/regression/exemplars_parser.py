"""Parser for exemplars-1.0.txt (UTF-16 LE, one puzzle per line).

Format per data line:
    <81-char puzzle> # <annotation>   (annotation is informational only)

Section headers:
    #NNNN: Technique Name             (code + human name)

Puzzles inherit the technique from the most recent section header.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from hodoku_py.core.types import SolutionType

EXEMPLARS_FILE = (
    Path(__file__).parent.parent.parent / "hodoku" / "HoDoKu" / "exemplars-1.0.txt"
)

# ---------------------------------------------------------------------------
# Section code → SolutionType set
#
# Some sections cover multiple variants (e.g. Simple Colors covers both
# Trap and Wrap); we store a frozenset so tests can check for any of them.
# ---------------------------------------------------------------------------

SECTION_TYPES: dict[str, frozenset[SolutionType]] = {
    "0000": frozenset({SolutionType.FULL_HOUSE}),
    "0002": frozenset({SolutionType.HIDDEN_SINGLE}),
    "0003": frozenset({SolutionType.NAKED_SINGLE}),
    "0100": frozenset({SolutionType.LOCKED_CANDIDATES_1}),
    "0101": frozenset({SolutionType.LOCKED_CANDIDATES_2}),
    "0110": frozenset({SolutionType.LOCKED_PAIR}),
    "0111": frozenset({SolutionType.LOCKED_TRIPLE}),
    "0200": frozenset({SolutionType.NAKED_PAIR}),
    "0201": frozenset({SolutionType.NAKED_TRIPLE}),
    "0202": frozenset({SolutionType.NAKED_QUADRUPLE}),
    "0210": frozenset({SolutionType.HIDDEN_PAIR}),
    "0211": frozenset({SolutionType.HIDDEN_TRIPLE}),
    "0212": frozenset({SolutionType.HIDDEN_QUADRUPLE}),
    "0300": frozenset({SolutionType.X_WING}),
    "0301": frozenset({SolutionType.SWORDFISH}),
    "0302": frozenset({SolutionType.JELLYFISH}),
    "0310": frozenset({SolutionType.FINNED_X_WING}),
    "0311": frozenset({SolutionType.FINNED_SWORDFISH}),
    "0312": frozenset({SolutionType.FINNED_JELLYFISH}),
    "0320": frozenset({SolutionType.SASHIMI_X_WING}),
    "0321": frozenset({SolutionType.SASHIMI_SWORDFISH}),
    "0322": frozenset({SolutionType.SASHIMI_JELLYFISH}),
    "0330": frozenset({SolutionType.FRANKEN_X_WING}),
    "0331": frozenset({SolutionType.FRANKEN_SWORDFISH}),
    "0332": frozenset({SolutionType.FRANKEN_JELLYFISH}),
    "0340": frozenset({SolutionType.FINNED_FRANKEN_X_WING}),
    "0341": frozenset({SolutionType.FINNED_FRANKEN_SWORDFISH}),
    "0342": frozenset({SolutionType.FINNED_FRANKEN_JELLYFISH}),
    "0350": frozenset({SolutionType.MUTANT_X_WING}),
    "0351": frozenset({SolutionType.MUTANT_SWORDFISH}),
    "0352": frozenset({SolutionType.MUTANT_JELLYFISH}),
    "0360": frozenset({SolutionType.FINNED_MUTANT_X_WING}),
    "0361": frozenset({SolutionType.FINNED_MUTANT_SWORDFISH}),
    "0362": frozenset({SolutionType.FINNED_MUTANT_JELLYFISH}),
    "0400": frozenset({SolutionType.SKYSCRAPER}),
    "0401": frozenset({SolutionType.TWO_STRING_KITE}),
    "0402": frozenset({SolutionType.EMPTY_RECTANGLE}),
    "0403": frozenset({SolutionType.TURBOT_FISH}),
    # 0500: Simple Colors covers both Trap and Wrap variants
    "0500": frozenset({SolutionType.SIMPLE_COLORS_TRAP, SolutionType.SIMPLE_COLORS_WRAP}),
    # 0501: Multi-Colors covers both type 1 and type 2
    "0501": frozenset({SolutionType.MULTI_COLORS_1, SolutionType.MULTI_COLORS_2}),
    "0600": frozenset({SolutionType.UNIQUENESS_1}),
    "0601": frozenset({SolutionType.UNIQUENESS_2}),
    "0602": frozenset({SolutionType.UNIQUENESS_3}),
    "0603": frozenset({SolutionType.UNIQUENESS_4}),
    "0604": frozenset({SolutionType.UNIQUENESS_5}),
    "0605": frozenset({SolutionType.UNIQUENESS_6}),
    "0606": frozenset({SolutionType.HIDDEN_RECTANGLE}),
    # 0607 used for both AR1 and AR2 in the file — resolved by section name
    "0607:ar1": frozenset({SolutionType.AVOIDABLE_RECTANGLE_1}),
    "0607:ar2": frozenset({SolutionType.AVOIDABLE_RECTANGLE_2}),
    "0610": frozenset({SolutionType.BUG_PLUS_1}),
    "0701": frozenset({SolutionType.X_CHAIN}),
    "0702": frozenset({SolutionType.XY_CHAIN}),
    "0703": frozenset({SolutionType.REMOTE_PAIR}),
    "0706": frozenset({SolutionType.CONTINUOUS_NICE_LOOP}),
    "0707": frozenset({SolutionType.DISCONTINUOUS_NICE_LOOP}),
    "0708": frozenset({SolutionType.AIC}),
    "0709": frozenset({SolutionType.GROUPED_CONTINUOUS_NICE_LOOP}),
    "0710": frozenset({SolutionType.GROUPED_DISCONTINUOUS_NICE_LOOP}),
    "0711": frozenset({SolutionType.GROUPED_AIC}),
    "0800": frozenset({SolutionType.XY_WING}),
    "0801": frozenset({SolutionType.XYZ_WING}),
    "0803": frozenset({SolutionType.W_WING}),
    "0901": frozenset({SolutionType.ALS_XZ}),
    "0902": frozenset({SolutionType.ALS_XY_WING}),
    "0903": frozenset({SolutionType.ALS_XY_CHAIN}),
    "0904": frozenset({SolutionType.DEATH_BLOSSOM}),
    "1101": frozenset({SolutionType.SUE_DE_COQ}),
    "1202": frozenset({SolutionType.FORCING_CHAIN_VERITY}),
    "1301": frozenset({SolutionType.FORCING_CHAIN_CONTRADICTION}),
    "1302": frozenset({SolutionType.FORCING_CHAIN_VERITY}),
    "1303": frozenset({SolutionType.FORCING_NET_CONTRADICTION}),
    "1304": frozenset({SolutionType.FORCING_NET_VERITY}),
}

# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ExemplarEntry:
    line_num: int
    section_code: str               # e.g. "0100"
    section_name: str               # e.g. "Locked Candidate Type 1"
    puzzle: str                     # 81-char string (digits + '.')
    expected_types: frozenset[SolutionType]  # what technique(s) this tests

    @property
    def test_id(self) -> str:
        return f"{self.section_code}_{self.line_num}"


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

_SECTION_RE = re.compile(r"^#(\d{4,5}):\s*(.+)$")
_PUZZLE_RE = re.compile(r"^[0-9.]{81}$")


def parse_exemplars(path: Path = EXEMPLARS_FILE) -> list[ExemplarEntry]:
    """Parse exemplars-1.0.txt and return all puzzle entries."""
    with open(path, encoding="utf-16") as f:
        lines = f.readlines()

    entries: list[ExemplarEntry] = []
    current_code = ""
    current_name = ""
    # Track how many times we've seen code 0607 (it's reused for AR1 and AR2)
    _0607_count = 0

    for line_num, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue

        if line.startswith("#"):
            m = _SECTION_RE.match(line)
            if m:
                current_code = m.group(1)[:4]   # trim 5-digit variants to 4
                current_name = m.group(2).strip()
                if current_code == "0607":
                    _0607_count += 1
            continue

        # Puzzle line: everything before the optional '#' annotation
        puzzle_part = line.split("#")[0].strip()
        if not _PUZZLE_RE.match(puzzle_part):
            continue

        # Resolve section → SolutionType set
        lookup_key = current_code
        if current_code == "0607":
            lookup_key = "0607:ar2" if _0607_count >= 2 else "0607:ar1"
        expected = SECTION_TYPES.get(lookup_key, frozenset())

        entries.append(
            ExemplarEntry(
                line_num=line_num,
                section_code=current_code,
                section_name=current_name,
                puzzle=puzzle_part,
                expected_types=expected,
            )
        )

    return entries
