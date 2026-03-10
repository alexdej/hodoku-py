"""Scoring configuration — mirrors Options.solverSteps[] and difficultyLevels[] in Java.

Each StepConfig records the solver priority (index), base score per application,
difficulty level, and enabled flags for a technique.

The Python enum splits some Java SolutionTypes into subtypes (e.g. SIMPLE_COLORS →
TRAP/WRAP, NICE_LOOP → Continuous/Discontinuous/AIC). Those subtypes share the same
StepConfig via the STEP_CONFIG alias table at the bottom.
"""

from __future__ import annotations

from dataclasses import dataclass

from hodoku.core.types import DifficultyType, SolutionCategory, SolutionType

_D = DifficultyType
_C = SolutionCategory
_S = SolutionType


@dataclass(frozen=True)
class StepConfig:
    index: int                   # solver priority (lower = tried first)
    solution_type: SolutionType
    level: DifficultyType        # difficulty this technique belongs to
    category: SolutionCategory
    base_score: int              # points added per application
    enabled: bool                # used in the solve loop?
    all_steps_enabled: bool      # searched in find-all-steps mode?


# ---------------------------------------------------------------------------
# Difficulty level score thresholds
# Puzzle difficulty = max level of all techniques used.
# These thresholds are used by the generator to filter puzzles by difficulty.
# ---------------------------------------------------------------------------

DIFFICULTY_MAX_SCORE: dict[DifficultyType, int] = {
    _D.INCOMPLETE: 0,
    _D.EASY:       800,
    _D.MEDIUM:     1000,
    _D.HARD:       1600,
    _D.UNFAIR:     1800,
    _D.EXTREME:    2**31 - 1,
}

# ---------------------------------------------------------------------------
# Full step table — transcribed from Options.solverSteps[] in Options.java.
# Rows appear in Java source order; SOLVER_STEPS below sorts by index.
# ---------------------------------------------------------------------------

DEFAULT_STEPS: tuple[StepConfig, ...] = (
    # Sentinels
    StepConfig(2**31 - 2, _S.INCOMPLETE, _D.INCOMPLETE, _C.LAST_RESORT,   0, False, False),
    StepConfig(2**31 - 1, _S.GIVE_UP,    _D.EXTREME,    _C.LAST_RESORT, 20000, True, False),
    # Singles
    StepConfig(100, _S.FULL_HOUSE,          _D.EASY,   _C.SINGLES,        4, True,  True),
    StepConfig(200, _S.NAKED_SINGLE,        _D.EASY,   _C.SINGLES,        4, True,  True),
    StepConfig(300, _S.HIDDEN_SINGLE,       _D.EASY,   _C.SINGLES,       14, True,  True),
    # Intersections
    StepConfig(1000, _S.LOCKED_PAIR,        _D.MEDIUM, _C.INTERSECTIONS,  40, True,  True),
    StepConfig(1100, _S.LOCKED_TRIPLE,      _D.MEDIUM, _C.INTERSECTIONS,  60, True,  True),
    StepConfig(1200, _S.LOCKED_CANDIDATES_1,_D.MEDIUM, _C.INTERSECTIONS,  50, True,  True),
    StepConfig(1210, _S.LOCKED_CANDIDATES_2,_D.MEDIUM, _C.INTERSECTIONS,  50, True,  True),
    # Subsets
    StepConfig(1300, _S.NAKED_PAIR,         _D.MEDIUM, _C.SUBSETS,        60, True,  True),
    StepConfig(1400, _S.NAKED_TRIPLE,       _D.MEDIUM, _C.SUBSETS,        80, True,  True),
    StepConfig(1500, _S.HIDDEN_PAIR,        _D.MEDIUM, _C.SUBSETS,        70, True,  True),
    StepConfig(1600, _S.HIDDEN_TRIPLE,      _D.MEDIUM, _C.SUBSETS,       100, True,  True),
    StepConfig(2000, _S.NAKED_QUADRUPLE,    _D.HARD,   _C.SUBSETS,       120, True,  True),
    StepConfig(2100, _S.HIDDEN_QUADRUPLE,   _D.HARD,   _C.SUBSETS,       150, True,  True),
    # Basic fish
    StepConfig(2200, _S.X_WING,             _D.HARD,   _C.BASIC_FISH,    140, True,  False),
    StepConfig(2300, _S.SWORDFISH,          _D.HARD,   _C.BASIC_FISH,    150, True,  False),
    StepConfig(2400, _S.JELLYFISH,          _D.HARD,   _C.BASIC_FISH,    160, True,  False),
    StepConfig(2500, _S.SQUIRMBAG,          _D.UNFAIR, _C.BASIC_FISH,    470, False, False),
    StepConfig(2600, _S.WHALE,              _D.UNFAIR, _C.BASIC_FISH,    470, False, False),
    StepConfig(2700, _S.LEVIATHAN,          _D.UNFAIR, _C.BASIC_FISH,    470, False, False),
    # Chains (basic)
    StepConfig(2800, _S.REMOTE_PAIR,        _D.HARD,   _C.CHAINS_AND_LOOPS, 110, True,  True),
    # Uniqueness
    StepConfig(2900, _S.BUG_PLUS_1,         _D.HARD,   _C.UNIQUENESS,    100, True,  True),
    # Single digit patterns
    StepConfig(3000, _S.SKYSCRAPER,         _D.HARD,   _C.SINGLE_DIGIT_PATTERNS, 130, True, True),
    StepConfig(3100, _S.TWO_STRING_KITE,    _D.HARD,   _C.SINGLE_DIGIT_PATTERNS, 150, True, True),
    StepConfig(3120, _S.TURBOT_FISH,        _D.HARD,   _C.SINGLE_DIGIT_PATTERNS, 120, True, True),
    StepConfig(3170, _S.EMPTY_RECTANGLE,    _D.HARD,   _C.SINGLE_DIGIT_PATTERNS, 120, True, True),
    # Wings
    StepConfig(3200, _S.W_WING,             _D.HARD,   _C.WINGS,         150, True,  True),
    StepConfig(3300, _S.XY_WING,            _D.HARD,   _C.WINGS,         160, True,  True),
    StepConfig(3400, _S.XYZ_WING,           _D.HARD,   _C.WINGS,         180, True,  True),
    # Uniqueness tests
    StepConfig(3500, _S.UNIQUENESS_1,       _D.HARD,   _C.UNIQUENESS,    100, True,  True),
    StepConfig(3600, _S.UNIQUENESS_2,       _D.HARD,   _C.UNIQUENESS,    100, True,  True),
    StepConfig(3700, _S.UNIQUENESS_3,       _D.HARD,   _C.UNIQUENESS,    100, True,  True),
    StepConfig(3800, _S.UNIQUENESS_4,       _D.HARD,   _C.UNIQUENESS,    100, True,  True),
    StepConfig(3900, _S.UNIQUENESS_5,       _D.HARD,   _C.UNIQUENESS,    100, True,  True),
    StepConfig(4000, _S.UNIQUENESS_6,       _D.HARD,   _C.UNIQUENESS,    100, True,  True),
    StepConfig(4010, _S.HIDDEN_RECTANGLE,       _D.HARD, _C.UNIQUENESS,  100, True,  True),
    StepConfig(4020, _S.AVOIDABLE_RECTANGLE_1,  _D.HARD, _C.UNIQUENESS,  100, True,  True),
    StepConfig(4030, _S.AVOIDABLE_RECTANGLE_2,  _D.HARD, _C.UNIQUENESS,  100, True,  True),
    # Finned basic fish
    StepConfig(4100, _S.FINNED_X_WING,      _D.HARD,   _C.FINNED_BASIC_FISH, 130, True,  False),
    StepConfig(4200, _S.SASHIMI_X_WING,     _D.HARD,   _C.FINNED_BASIC_FISH, 150, True,  False),
    StepConfig(4300, _S.FINNED_SWORDFISH,   _D.UNFAIR, _C.FINNED_BASIC_FISH, 200, True,  False),
    StepConfig(4400, _S.SASHIMI_SWORDFISH,  _D.UNFAIR, _C.FINNED_BASIC_FISH, 240, True,  False),
    StepConfig(4500, _S.FINNED_JELLYFISH,   _D.UNFAIR, _C.FINNED_BASIC_FISH, 250, True,  False),
    StepConfig(4600, _S.SASHIMI_JELLYFISH,  _D.UNFAIR, _C.FINNED_BASIC_FISH, 260, True,  False),
    StepConfig(4700, _S.FINNED_SQUIRMBAG,   _D.UNFAIR, _C.FINNED_BASIC_FISH, 470, False, False),
    StepConfig(4800, _S.SASHIMI_SQUIRMBAG,  _D.UNFAIR, _C.FINNED_BASIC_FISH, 470, False, False),
    StepConfig(4900, _S.FINNED_WHALE,       _D.UNFAIR, _C.FINNED_BASIC_FISH, 470, False, False),
    StepConfig(5000, _S.SASHIMI_WHALE,      _D.UNFAIR, _C.FINNED_BASIC_FISH, 470, False, False),
    StepConfig(5100, _S.FINNED_LEVIATHAN,   _D.UNFAIR, _C.FINNED_BASIC_FISH, 470, False, False),
    StepConfig(5200, _S.SASHIMI_LEVIATHAN,  _D.UNFAIR, _C.FINNED_BASIC_FISH, 470, False, False),
    # Miscellaneous
    StepConfig(5300, _S.SUE_DE_COQ,         _D.UNFAIR, _C.MISCELLANEOUS, 250, True,  True),
    # Coloring (Java SIMPLE_COLORS / MULTI_COLORS; Python splits into subtypes)
    StepConfig(5330, _S.SIMPLE_COLORS_TRAP, _D.HARD,   _C.COLORING,     150, True,  True),
    StepConfig(5360, _S.MULTI_COLORS_1,     _D.HARD,   _C.COLORING,     200, True,  True),
    # Chains and loops
    StepConfig(5400, _S.X_CHAIN,                    _D.UNFAIR, _C.CHAINS_AND_LOOPS, 260, True, True),
    StepConfig(5500, _S.XY_CHAIN,                   _D.UNFAIR, _C.CHAINS_AND_LOOPS, 260, True, True),
    StepConfig(5600, _S.CONTINUOUS_NICE_LOOP,        _D.UNFAIR, _C.CHAINS_AND_LOOPS, 280, True, True),
    StepConfig(5650, _S.GROUPED_CONTINUOUS_NICE_LOOP,_D.UNFAIR, _C.CHAINS_AND_LOOPS, 300, True, True),
    # Almost locked sets
    StepConfig(5700, _S.ALS_XZ,             _D.UNFAIR, _C.ALMOST_LOCKED_SETS, 300, True,  True),
    StepConfig(5800, _S.ALS_XY_WING,        _D.UNFAIR, _C.ALMOST_LOCKED_SETS, 320, True,  True),
    StepConfig(5900, _S.ALS_XY_CHAIN,       _D.UNFAIR, _C.ALMOST_LOCKED_SETS, 340, True,  True),
    StepConfig(6000, _S.DEATH_BLOSSOM,      _D.UNFAIR, _C.ALMOST_LOCKED_SETS, 360, False, True),
    # Franken fish
    StepConfig(6100, _S.FRANKEN_X_WING,          _D.UNFAIR,  _C.FRANKEN_FISH, 300, True,  False),
    StepConfig(6200, _S.FRANKEN_SWORDFISH,        _D.UNFAIR,  _C.FRANKEN_FISH, 350, True,  False),
    StepConfig(6300, _S.FRANKEN_JELLYFISH,        _D.UNFAIR,  _C.FRANKEN_FISH, 370, False, False),
    StepConfig(6400, _S.FRANKEN_SQUIRMBAG,        _D.EXTREME, _C.FRANKEN_FISH, 470, False, False),
    StepConfig(6500, _S.FRANKEN_WHALE,            _D.EXTREME, _C.FRANKEN_FISH, 470, False, False),
    StepConfig(6600, _S.FRANKEN_LEVIATHAN,        _D.EXTREME, _C.FRANKEN_FISH, 470, False, False),
    # Finned franken fish
    StepConfig(6700, _S.FINNED_FRANKEN_X_WING,      _D.UNFAIR,  _C.FINNED_FRANKEN_FISH, 390, True,  False),
    StepConfig(6800, _S.FINNED_FRANKEN_SWORDFISH,   _D.UNFAIR,  _C.FINNED_FRANKEN_FISH, 410, True,  False),
    StepConfig(6900, _S.FINNED_FRANKEN_JELLYFISH,   _D.UNFAIR,  _C.FINNED_FRANKEN_FISH, 430, False, False),
    StepConfig(7000, _S.FINNED_FRANKEN_SQUIRMBAG,   _D.EXTREME, _C.FINNED_FRANKEN_FISH, 470, False, False),
    StepConfig(7100, _S.FINNED_FRANKEN_WHALE,        _D.EXTREME, _C.FINNED_FRANKEN_FISH, 470, False, False),
    StepConfig(7200, _S.FINNED_FRANKEN_LEVIATHAN,   _D.EXTREME, _C.FINNED_FRANKEN_FISH, 470, False, False),
    # Mutant fish
    StepConfig(7300, _S.MUTANT_X_WING,       _D.EXTREME, _C.MUTANT_FISH, 450, False, False),
    StepConfig(7400, _S.MUTANT_SWORDFISH,    _D.EXTREME, _C.MUTANT_FISH, 450, False, False),
    StepConfig(7500, _S.MUTANT_JELLYFISH,    _D.EXTREME, _C.MUTANT_FISH, 450, False, False),
    StepConfig(7600, _S.MUTANT_SQUIRMBAG,    _D.EXTREME, _C.MUTANT_FISH, 470, False, False),
    StepConfig(7700, _S.MUTANT_WHALE,        _D.EXTREME, _C.MUTANT_FISH, 470, False, False),
    StepConfig(7800, _S.MUTANT_LEVIATHAN,    _D.EXTREME, _C.MUTANT_FISH, 470, False, False),
    # Finned mutant fish
    StepConfig(7900, _S.FINNED_MUTANT_X_WING,     _D.EXTREME, _C.FINNED_MUTANT_FISH, 470, False, False),
    StepConfig(8000, _S.FINNED_MUTANT_SWORDFISH,  _D.EXTREME, _C.FINNED_MUTANT_FISH, 470, False, False),
    StepConfig(8100, _S.FINNED_MUTANT_JELLYFISH,  _D.EXTREME, _C.FINNED_MUTANT_FISH, 470, False, False),
    StepConfig(8200, _S.FINNED_MUTANT_SQUIRMBAG,  _D.EXTREME, _C.FINNED_MUTANT_FISH, 470, False, False),
    StepConfig(8300, _S.FINNED_MUTANT_WHALE,      _D.EXTREME, _C.FINNED_MUTANT_FISH, 470, False, False),
    StepConfig(8400, _S.FINNED_MUTANT_LEVIATHAN,  _D.EXTREME, _C.FINNED_MUTANT_FISH, 470, False, False),
    # Last resort
    StepConfig(8450, _S.KRAKEN_FISH_TYPE_1,         _D.EXTREME, _C.LAST_RESORT, 500,   False, False),
    StepConfig(8500, _S.FORCING_CHAIN_CONTRADICTION, _D.EXTREME, _C.LAST_RESORT, 500,   True,  False),
    StepConfig(8600, _S.FORCING_NET_CONTRADICTION,   _D.EXTREME, _C.LAST_RESORT, 700,   True,  False),
    StepConfig(8700, _S.TEMPLATE_SET,                _D.EXTREME, _C.LAST_RESORT, 10000, False, False),
    StepConfig(8800, _S.TEMPLATE_DEL,                _D.EXTREME, _C.LAST_RESORT, 10000, False, False),
    StepConfig(8900, _S.BRUTE_FORCE,                 _D.EXTREME, _C.LAST_RESORT, 10000, True,  False),
)

# ---------------------------------------------------------------------------
# Derived tables
# ---------------------------------------------------------------------------

# Ordered sequence used by the solve loop — enabled steps only, sorted by index.
SOLVER_STEPS: tuple[StepConfig, ...] = tuple(
    sorted((s for s in DEFAULT_STEPS if s.enabled), key=lambda s: s.index)
)

# Fast lookup by SolutionType. Subtypes that Java maps to a single StepConfig
# are aliased below to their primary variant's config.
STEP_CONFIG: dict[SolutionType, StepConfig] = {
    s.solution_type: s for s in DEFAULT_STEPS
}

# Aliases: Python splits these Java types into named subtypes.
# All subtypes share the primary variant's score and level.
STEP_CONFIG.update({
    # SIMPLE_COLORS → TRAP (primary, index 5330) + WRAP
    _S.SIMPLE_COLORS_WRAP:              STEP_CONFIG[_S.SIMPLE_COLORS_TRAP],
    # MULTI_COLORS → 1 (primary, index 5360) + 2
    _S.MULTI_COLORS_2:                  STEP_CONFIG[_S.MULTI_COLORS_1],
    # NICE_LOOP → Continuous (primary, index 5600) + Discontinuous + AIC
    _S.DISCONTINUOUS_NICE_LOOP:         STEP_CONFIG[_S.CONTINUOUS_NICE_LOOP],
    _S.AIC:                             STEP_CONFIG[_S.CONTINUOUS_NICE_LOOP],
    # GROUPED_NICE_LOOP → Grouped Continuous (primary, index 5650) + others
    _S.GROUPED_DISCONTINUOUS_NICE_LOOP: STEP_CONFIG[_S.GROUPED_CONTINUOUS_NICE_LOOP],
    _S.GROUPED_AIC:                     STEP_CONFIG[_S.GROUPED_CONTINUOUS_NICE_LOOP],
    # FORCING_CHAIN → Contradiction (primary, index 8500) + Verity
    _S.FORCING_CHAIN_VERITY:            STEP_CONFIG[_S.FORCING_CHAIN_CONTRADICTION],
    # FORCING_NET → Contradiction (primary, index 8600) + Verity
    _S.FORCING_NET_VERITY:              STEP_CONFIG[_S.FORCING_NET_CONTRADICTION],
    # KRAKEN_FISH → Type 1 (primary, index 8450) + Type 2
    _S.KRAKEN_FISH_TYPE_2:              STEP_CONFIG[_S.KRAKEN_FISH_TYPE_1],
    # DUAL_* — not in Java StepConfig; treat as same score as their parent
    _S.DUAL_TWO_STRING_KITE:            STEP_CONFIG[_S.TWO_STRING_KITE],
    _S.DUAL_EMPTY_RECTANGLE:            STEP_CONFIG[_S.EMPTY_RECTANGLE],
})

# Score thresholds from Options.DEFAULT_DIFFICULTY_LEVELS in Java.
# If total score exceeds a level's max, the puzzle is bumped to the next level.
# Mirrors: while (score > level.getMaxScore()) level = nextLevel;
DIFFICULTY_MAX_SCORE: dict[DifficultyType, int] = {
    DifficultyType.EASY:    800,
    DifficultyType.MEDIUM:  1000,
    DifficultyType.HARD:    1600,
    DifficultyType.UNFAIR:  1800,
    DifficultyType.EXTREME: 2**31 - 1,  # Integer.MAX_VALUE
}
