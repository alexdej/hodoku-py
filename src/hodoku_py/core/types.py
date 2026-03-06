from enum import Enum


class DifficultyType(Enum):
    INCOMPLETE = 0
    EASY = 1
    MEDIUM = 2
    HARD = 3
    UNFAIR = 4
    EXTREME = 5


class SolutionCategory(Enum):
    SINGLES = "Singles"
    INTERSECTIONS = "Intersections"
    SUBSETS = "Subsets"
    BASIC_FISH = "Basic Fish"
    FINNED_BASIC_FISH = "(Sashimi) Finned Fish"
    FRANKEN_FISH = "Franken Fish"
    FINNED_FRANKEN_FISH = "Finned Franken Fish"
    MUTANT_FISH = "Mutant Fish"
    FINNED_MUTANT_FISH = "Finned Mutant Fish"
    SINGLE_DIGIT_PATTERNS = "Single Digit Patterns"
    COLORING = "Coloring"
    UNIQUENESS = "Uniqueness"
    CHAINS_AND_LOOPS = "Chains and Loops"
    WINGS = "Wings"
    ALMOST_LOCKED_SETS = "Almost Locked Sets"
    ENUMERATIONS = "Enumerations"
    MISCELLANEOUS = "Miscellaneous"
    LAST_RESORT = "Last Resort"


class SolutionType(Enum):
    # Singles
    FULL_HOUSE = "Full House"
    HIDDEN_SINGLE = "Hidden Single"
    NAKED_SINGLE = "Naked Single"
    # Intersections
    LOCKED_CANDIDATES_1 = "Locked Candidates Type 1 (Pointing)"
    LOCKED_CANDIDATES_2 = "Locked Candidates Type 2 (Claiming)"
    LOCKED_PAIR = "Locked Pair"
    LOCKED_TRIPLE = "Locked Triple"
    # Subsets
    NAKED_PAIR = "Naked Pair"
    NAKED_TRIPLE = "Naked Triple"
    NAKED_QUADRUPLE = "Naked Quadruple"
    HIDDEN_PAIR = "Hidden Pair"
    HIDDEN_TRIPLE = "Hidden Triple"
    HIDDEN_QUADRUPLE = "Hidden Quadruple"
    # Basic fish
    X_WING = "X-Wing"
    SWORDFISH = "Swordfish"
    JELLYFISH = "Jellyfish"
    SQUIRMBAG = "Squirmbag"
    WHALE = "Whale"
    LEVIATHAN = "Leviathan"
    # Finned basic fish
    FINNED_X_WING = "Finned X-Wing"
    FINNED_SWORDFISH = "Finned Swordfish"
    FINNED_JELLYFISH = "Finned Jellyfish"
    FINNED_SQUIRMBAG = "Finned Squirmbag"
    FINNED_WHALE = "Finned Whale"
    FINNED_LEVIATHAN = "Finned Leviathan"
    SASHIMI_X_WING = "Sashimi X-Wing"
    SASHIMI_SWORDFISH = "Sashimi Swordfish"
    SASHIMI_JELLYFISH = "Sashimi Jellyfish"
    SASHIMI_SQUIRMBAG = "Sashimi Squirmbag"
    SASHIMI_WHALE = "Sashimi Whale"
    SASHIMI_LEVIATHAN = "Sashimi Leviathan"
    # Franken fish
    FRANKEN_X_WING = "Franken X-Wing"
    FRANKEN_SWORDFISH = "Franken Swordfish"
    FRANKEN_JELLYFISH = "Franken Jellyfish"
    FRANKEN_SQUIRMBAG = "Franken Squirmbag"
    FRANKEN_WHALE = "Franken Whale"
    FRANKEN_LEVIATHAN = "Franken Leviathan"
    FINNED_FRANKEN_X_WING = "Finned Franken X-Wing"
    FINNED_FRANKEN_SWORDFISH = "Finned Franken Swordfish"
    FINNED_FRANKEN_JELLYFISH = "Finned Franken Jellyfish"
    FINNED_FRANKEN_SQUIRMBAG = "Finned Franken Squirmbag"
    FINNED_FRANKEN_WHALE = "Finned Franken Whale"
    FINNED_FRANKEN_LEVIATHAN = "Finned Franken Leviathan"
    # Mutant fish
    MUTANT_X_WING = "Mutant X-Wing"
    MUTANT_SWORDFISH = "Mutant Swordfish"
    MUTANT_JELLYFISH = "Mutant Jellyfish"
    MUTANT_SQUIRMBAG = "Mutant Squirmbag"
    MUTANT_WHALE = "Mutant Whale"
    MUTANT_LEVIATHAN = "Mutant Leviathan"
    FINNED_MUTANT_X_WING = "Finned Mutant X-Wing"
    FINNED_MUTANT_SWORDFISH = "Finned Mutant Swordfish"
    FINNED_MUTANT_JELLYFISH = "Finned Mutant Jellyfish"
    FINNED_MUTANT_SQUIRMBAG = "Finned Mutant Squirmbag"
    FINNED_MUTANT_WHALE = "Finned Mutant Whale"
    FINNED_MUTANT_LEVIATHAN = "Finned Mutant Leviathan"
    # Kraken fish
    KRAKEN_FISH_TYPE_1 = "Kraken Fish Type 1"
    KRAKEN_FISH_TYPE_2 = "Kraken Fish Type 2"
    # Single digit patterns
    SKYSCRAPER = "Skyscraper"
    TWO_STRING_KITE = "2-String Kite"
    TURBOT_FISH = "Turbot Fish"
    EMPTY_RECTANGLE = "Empty Rectangle"
    DUAL_TWO_STRING_KITE = "Dual 2-String Kite"
    DUAL_EMPTY_RECTANGLE = "Dual Empty Rectangle"
    # Coloring
    SIMPLE_COLORS_TRAP = "Simple Colors Trap"
    SIMPLE_COLORS_WRAP = "Simple Colors Wrap"
    MULTI_COLORS_1 = "Multi-Colors 1"
    MULTI_COLORS_2 = "Multi-Colors 2"
    # Uniqueness
    UNIQUENESS_1 = "Uniqueness Test 1"
    UNIQUENESS_2 = "Uniqueness Test 2"
    UNIQUENESS_3 = "Uniqueness Test 3"
    UNIQUENESS_4 = "Uniqueness Test 4"
    UNIQUENESS_5 = "Uniqueness Test 5"
    UNIQUENESS_6 = "Uniqueness Test 6"
    BUG_PLUS_1 = "Bivalue Universal Grave + 1"
    HIDDEN_RECTANGLE = "Hidden Rectangle"
    AVOIDABLE_RECTANGLE_1 = "Avoidable Rectangle Type 1"
    AVOIDABLE_RECTANGLE_2 = "Avoidable Rectangle Type 2"
    # Wings
    XY_WING = "XY-Wing"
    XYZ_WING = "XYZ-Wing"
    W_WING = "W-Wing"
    # Chains and loops
    X_CHAIN = "X-Chain"
    XY_CHAIN = "XY-Chain"
    REMOTE_PAIR = "Remote Pair"
    CONTINUOUS_NICE_LOOP = "Continuous Nice Loop"
    DISCONTINUOUS_NICE_LOOP = "Discontinuous Nice Loop"
    AIC = "AIC"
    GROUPED_CONTINUOUS_NICE_LOOP = "Grouped Continuous Nice Loop"
    GROUPED_DISCONTINUOUS_NICE_LOOP = "Grouped Discontinuous Nice Loop"
    GROUPED_AIC = "Grouped AIC"
    # Almost locked sets
    ALS_XZ = "Almost Locked Set XZ-Rule"
    ALS_XY_WING = "Almost Locked Set XY-Wing"
    ALS_XY_CHAIN = "Almost Locked Set XY-Chain"
    DEATH_BLOSSOM = "Death Blossom"
    SUE_DE_COQ = "Sue de Coq"
    # Enumerations (forcing chains/nets)
    FORCING_CHAIN_CONTRADICTION = "Forcing Chain Contradiction"
    FORCING_CHAIN_VERITY = "Forcing Chain Verity"
    FORCING_NET_CONTRADICTION = "Forcing Net Contradiction"
    FORCING_NET_VERITY = "Forcing Net Verity"
    # Last resort
    TEMPLATE_SET = "Template Set"
    TEMPLATE_DEL = "Template Delete"
    BRUTE_FORCE = "Brute Force"
    # Sentinels
    INCOMPLETE = "Incomplete Solution"
    GIVE_UP = "Give Up"

    def is_single(self) -> bool:
        return self in (
            SolutionType.FULL_HOUSE,
            SolutionType.HIDDEN_SINGLE,
            SolutionType.NAKED_SINGLE,
        )
