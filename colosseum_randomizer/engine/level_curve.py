"""Difficulty tiers use immutable encounter levels, before native boss bonuses."""
import math


def encounter_level(original_level, options):
    if getattr(options, "progressive_levels", False):
        tier = "early" if original_level <= 35 else "mid" if original_level <= 50 else "late"
        multiplier = getattr(options, tier + "_level_multiplier")
    else:
        multiplier = options.trainer_level_multiplier
    return max(1, min(100, math.floor(original_level * multiplier + 0.5)))
