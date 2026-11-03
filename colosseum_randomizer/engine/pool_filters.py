"""Replacement exclusions use National Dex IDs and original Gen III types."""
from functools import lru_cache

VALID_TYPES = frozenset(range(18)) - {9}


@lru_cache(maxsize=128)
def _sets(species, types):
    if (any(type(i) is not int or not 1 <= i <= 386 for i in species)
            or any(type(i) is not int or i not in VALID_TYPES for i in types)):
        raise ValueError("invalid replacement exclusions")
    return frozenset(species), frozenset(types)


def exclusion_sets(options):
    return _sets(tuple(getattr(options, "excluded_species", ())),
                 tuple(getattr(options, "excluded_types", ())))


def has_exclusions(options) -> bool:
    species, types = exclusion_sets(options)
    return bool(species or types)


def species_excluded(original_row: dict, options) -> bool:
    species, types = exclusion_sets(options)
    return original_row["national_dex"] in species or bool(set(original_row["types"]) & types)


def allowed_replacement(original_row: dict, options) -> bool:
    national = original_row["national_dex"]
    generation = 1 if national <= 151 else 2 if national <= 251 else 3
    # Local import avoids a cycle with the existing species-pool helper.
    from .species_rules import LEGENDARY_NATIONAL
    return (national != 292 and getattr(options, f"allow_gen{generation}", True)
            and (getattr(options, "allow_legendaries", True) or national not in LEGENDARY_NATIONAL)
            and not species_excluded(original_row, options))
