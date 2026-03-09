"""Parser for HoDoKu's reglib-1.3.txt regression test library.

Format per data line:
    :<technique_code[-variant|x]>:<candidates>:<givens_with_plus>:<deleted_cands>:<eliminations>:<placements>:<extra>:

Where:
  - givens_with_plus: 81-char puzzle where '+' before a digit marks it as placed
    (not an original given) — all digits (with or without '+') are set cells.
  - deleted_cands: candidates manually removed beyond standard Sudoku rules,
    space-separated as <digit><row><col> (1-indexed).
  - eliminations: expected eliminations, same format as deleted_cands.
  - placements: expected cell placements (mutually exclusive with eliminations).
  - variant '-x': fail case — technique must NOT find anything.
  - variant '-N': numeric variant (affects solver options).

5-digit codes: some entries use 'XXXXY' (5 digits, no dash) where XXXX is the
base code and Y is the variant digit.  This matches Java's getTypeFromLibraryType
fallback: if a 5-char code ending in '1' is unrecognised, strip the trailing '1'
and look up the 4-char base code.  We generalise this to any trailing digit.

Note: reglib codes differ from exemplars codes for coloring techniques:
  reglib 0500 = Simple Colors Trap   (exemplars 0500 = Trap+Wrap together)
  reglib 0501 = Simple Colors Wrap   (exemplars 0501 = Multi-Colors 1+2)
  reglib 0502 = Multi-Colors 1
  reglib 0503 = Multi-Colors 2
Similarly, reglib distinguishes 0607 (AR1) from 0608 (AR2).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from hodoku.core.types import SolutionType

# reglib-1.3.txt lives alongside this file
REGLIB_FILE = Path(__file__).parent / "reglib-1.3.txt"

# ---------------------------------------------------------------------------
# Technique code → human-readable name (used in test IDs)
# ---------------------------------------------------------------------------

CODE_NAMES: dict[str, str] = {
    "0000": "Full_House",
    "0002": "Hidden_Single",
    "0003": "Naked_Single",
    "0100": "Locked_Candidates_1",
    "0101": "Locked_Candidates_2",
    "0110": "Locked_Pair",
    "0111": "Locked_Triple",
    "0200": "Naked_Pair",
    "0201": "Naked_Triple",
    "0202": "Naked_Quadruple",
    "0210": "Hidden_Pair",
    "0211": "Hidden_Triple",
    "0212": "Hidden_Quadruple",
    "0300": "X-Wing",
    "0301": "Swordfish",
    "0302": "Jellyfish",
    "0310": "Finned_X-Wing",
    "0311": "Finned_Swordfish",
    "0312": "Finned_Jellyfish",
    "0320": "Sashimi_X-Wing",
    "0321": "Sashimi_Swordfish",
    "0322": "Sashimi_Jellyfish",
    "0330": "Franken_X-Wing",
    "0331": "Franken_Swordfish",
    "0332": "Franken_Jellyfish",
    "0340": "Finned_Franken_X-Wing",
    "0341": "Finned_Franken_Swordfish",
    "0342": "Finned_Franken_Jellyfish",
    "0350": "Mutant_X-Wing",
    "0351": "Mutant_Swordfish",
    "0352": "Mutant_Jellyfish",
    "0360": "Finned_Mutant_X-Wing",
    "0361": "Finned_Mutant_Swordfish",
    "0362": "Finned_Mutant_Jellyfish",
    "0363": "Finned_Mutant_Squirmbag",
    "0364": "Finned_Mutant_Whale",
    "0400": "Skyscraper",
    "0401": "Two-String_Kite",
    "0402": "Empty_Rectangle",
    "0403": "Turbot_Fish",
    "0404": "Dual_Two-String_Kite",
    "0405": "Dual_Empty_Rectangle",
    "0500": "Simple_Colors_Trap",
    "0501": "Simple_Colors_Wrap",
    "0502": "Multi-Colors_1",
    "0503": "Multi-Colors_2",
    "0600": "Uniqueness_1",
    "0601": "Uniqueness_2",
    "0602": "Uniqueness_3",
    "0603": "Uniqueness_4",
    "0604": "Uniqueness_5",
    "0605": "Uniqueness_6",
    "0606": "Hidden_Rectangle",
    "0607": "Avoidable_Rectangle_1",
    "0608": "Avoidable_Rectangle_2",
    "0610": "BUG+1",
    "0701": "X-Chain",
    "0702": "XY-Chain",
    "0703": "Remote_Pair",
    "0706": "Continuous_Nice_Loop",
    "0707": "Discontinuous_Nice_Loop",
    "0708": "AIC",
    "0709": "Grouped_CNL",
    "0710": "Grouped_DNL",
    "0711": "Grouped_AIC",
    "0800": "XY-Wing",
    "0801": "XYZ-Wing",
    "0803": "W-Wing",
    "0901": "ALS-XZ",
    "0902": "ALS-XY-Wing",
    "0903": "ALS-XY-Chain",
    "0904": "Death_Blossom",
    "1101": "Sue_de_Coq",
    "1201": "Template_Set",
    "1202": "Template_Delete",
    "1301": "Forcing_Chain_Contradiction",
    "1302": "Forcing_Chain_Verity",
    "1303": "Forcing_Net_Contradiction",
    "1304": "Forcing_Net_Verity",
}

# ---------------------------------------------------------------------------
# Technique code → frozenset[SolutionType]
# Codes absent from this map are skipped (not yet implemented or out-of-scope).
# ---------------------------------------------------------------------------

TECHNIQUE_TYPES: dict[str, frozenset[SolutionType]] = {
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
    "0363": frozenset({SolutionType.FINNED_MUTANT_SQUIRMBAG}),
    "0364": frozenset({SolutionType.FINNED_MUTANT_WHALE}),
    "0400": frozenset({SolutionType.SKYSCRAPER}),
    "0401": frozenset({SolutionType.TWO_STRING_KITE}),
    "0402": frozenset({SolutionType.EMPTY_RECTANGLE}),
    "0403": frozenset({SolutionType.TURBOT_FISH}),
    "0404": frozenset({SolutionType.DUAL_TWO_STRING_KITE}),
    "0405": frozenset({SolutionType.DUAL_EMPTY_RECTANGLE}),
    # reglib splits Simple Colors into Trap (0500) and Wrap (0501)
    "0500": frozenset({SolutionType.SIMPLE_COLORS_TRAP}),
    "0501": frozenset({SolutionType.SIMPLE_COLORS_WRAP}),
    # reglib splits Multi-Colors into type 1 (0502) and type 2 (0503)
    "0502": frozenset({SolutionType.MULTI_COLORS_1}),
    "0503": frozenset({SolutionType.MULTI_COLORS_2}),
    "0600": frozenset({SolutionType.UNIQUENESS_1}),
    "0601": frozenset({SolutionType.UNIQUENESS_2}),
    "0602": frozenset({SolutionType.UNIQUENESS_3}),
    "0603": frozenset({SolutionType.UNIQUENESS_4}),
    "0604": frozenset({SolutionType.UNIQUENESS_5}),
    "0605": frozenset({SolutionType.UNIQUENESS_6}),
    "0606": frozenset({SolutionType.HIDDEN_RECTANGLE}),
    # reglib distinguishes AR1 (0607) from AR2 (0608)
    "0607": frozenset({SolutionType.AVOIDABLE_RECTANGLE_1}),
    "0608": frozenset({SolutionType.AVOIDABLE_RECTANGLE_2}),
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
    "1201": frozenset(),  # Template Set — not yet implemented
    "1202": frozenset(),  # Template Delete — not yet implemented
    "1301": frozenset(),  # Forcing Chain Contradiction — not yet implemented
    "1302": frozenset(),  # Forcing Chain Verity — not yet implemented
    "1303": frozenset(),  # Forcing Net Contradiction — not yet implemented
    "1304": frozenset(),  # Forcing Net Verity — not yet implemented
}


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ReglibEntry:
    line_num: int
    technique_code: str                                    # normalised 4-char code, e.g. "0901"
    variant: int | None                                    # 1, 2, … or None
    fail_case: bool                                        # True if variant == 'x'
    candidates_field: str                                  # "3" or "34" (targeted digits)
    givens_placed: str                                     # 81-char string, ready for set_sudoku
    deleted_candidates: tuple[tuple[int, int, int], ...]  # (digit, row, col) 1-indexed
    eliminations: tuple[tuple[int, int, int], ...]         # (digit, row, col) 1-indexed
    placements: tuple[tuple[int, int, int], ...]           # (digit, row, col) 1-indexed
    extra: str                                             # chain length or other info
    solution_types: frozenset[SolutionType]                # empty → unrecognised code

    @property
    def test_id(self) -> str:
        name = CODE_NAMES.get(self.technique_code, self.technique_code)
        if self.fail_case:
            suffix = "-x"
        elif self.variant is not None:
            suffix = f"-{self.variant}"
        else:
            suffix = ""
        return f"{self.technique_code}_{name}{suffix}_{self.line_num}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_givens_plus(s: str) -> str:
    """Return a string suitable for Grid.set_sudoku, preserving '+' markers.

    '+' before a digit marks it as placed (not a given). Grid.set_sudoku
    uses this to populate the ``givens`` bitmask.
    """
    return s


def _parse_cell_list(s: str) -> tuple[tuple[int, int, int], ...]:
    """Parse a space-separated list of '<digit><row><col>' tokens (1-indexed)."""
    result: list[tuple[int, int, int]] = []
    for token in s.split():
        token = token.strip()
        if len(token) == 3 and token.isdigit():
            result.append((int(token[0]), int(token[1]), int(token[2])))
    return tuple(result)


def _resolve_code(raw: str) -> tuple[str, int | None, bool]:
    """Return (normalised_4char_code, variant, fail_case) from the raw technique field.

    Handles three formats:
      "0311"    → code="0311", variant=None, fail_case=False
      "0311-1"  → code="0311", variant=1,    fail_case=False
      "0311-x"  → code="0311", variant=None, fail_case=True
      "03111"   → code="0311", variant=1,    fail_case=False  (5-digit, no dash)
    """
    variant: int | None = None
    fail_case = False

    if "-" in raw:
        dash = raw.index("-")
        code = raw[:dash]
        suffix = raw[dash + 1:]
        if suffix == "x":
            fail_case = True
        else:
            try:
                variant = int(suffix)
            except ValueError:
                return raw, None, False  # malformed; caller will skip
    elif len(raw) == 5 and raw.isdigit():
        # 5-digit code: last digit is variant (mirrors Java getTypeFromLibraryType fallback)
        code = raw[:4]
        variant = int(raw[4])
    else:
        code = raw

    return code, variant, fail_case


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def parse_reglib(path: Path = REGLIB_FILE) -> list[ReglibEntry]:
    """Parse reglib-1.3.txt and return all test entries."""
    entries: list[ReglibEntry] = []

    with open(path, encoding="utf-8") as f:
        lines = f.readlines()

    for line_num, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if not line.startswith(":"):
            continue

        # Split on ':'; pad to 9 fields
        parts = line.split(":")
        while len(parts) < 9:
            parts.append("")

        raw_code = parts[1].strip()
        candidates_field = parts[2].strip()
        givens_raw = parts[3].strip()
        deleted_raw = parts[4].strip()
        elims_raw = parts[5].strip()
        placements_raw = parts[6].strip()
        extra = parts[7].strip()

        code, variant, fail_case = _resolve_code(raw_code)

        givens_placed = _parse_givens_plus(givens_raw)
        if sum(1 for c in givens_placed if c.isdigit() or c == '.') != 81:
            continue  # malformed — skip

        solution_types = TECHNIQUE_TYPES.get(code, frozenset())

        entries.append(ReglibEntry(
            line_num=line_num,
            technique_code=code,
            variant=variant,
            fail_case=fail_case,
            candidates_field=candidates_field,
            givens_placed=givens_placed,
            deleted_candidates=_parse_cell_list(deleted_raw),
            eliminations=_parse_cell_list(elims_raw),
            placements=_parse_cell_list(placements_raw),
            extra=extra,
            solution_types=solution_types,
        ))

    return entries
