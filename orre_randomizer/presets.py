"""Desktop presets share balance rules; Pokémon-only changes their scope."""
from dataclasses import replace
from typing import TypeVar

from .options import Options


Preset = TypeVar("Preset")


def without_moves_and_items(options: Preset) -> Preset:
    """Keep every balance choice while retaining native moves, TMs and items."""
    return replace(options, randomize_trainer_moves=False, randomize_starter_moves=False,
                   randomize_gift_moves=False, randomize_learnsets=False,
                   randomize_tm_moves=False, tm_compatibility_mode="original",
                   randomize_field_items=False, randomize_shop_items=False)


def recommended_preset() -> Options:
    return replace(Options.recommended(), custom_shinies=True,
                   shiny_chance_percent=5.0, diverse_story_families=True)


def species_preset() -> Options:
    return without_moves_and_items(recommended_preset())
