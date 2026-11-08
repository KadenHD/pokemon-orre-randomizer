# Male and female Pokémon models

Colosseum and XD use one base model per species for male and female Pokémon.
Nidoran♀ and Nidoran♂ have separate models because they are different species,
with National Pokédex numbers 29 and 32.

The European, USA and Japanese revision 0 discs were checked against their
registered ISO hashes. All six have 385 ordinary species with one model
resource each, plus Unown and its 28 forms. The asset census covered every
`pkx_*.fsys` archive on those discs. Every model member had one HSD geometry
root.

| Game | PKX model members per region | Base species with one model |
| --- | ---: | ---: |
| Colosseum | 527 | 385 |
| XD | 602 | 385 |

The native loader traces come from the two USA executables. Colosseum's
`pokemonCreateSequence` and `fightOutPokemonCreateSequence` resolve a species
model through the loader at `0x801DE190`. XD's corresponding functions resolve
the model through `Sequence_LoadPokemon` and `ModelSequence`. The selector paths
use the species model ID, with separate handling for Unown forms and shiny
resources. XD also handles Deoxys forms and Shadow Lugia. Spinda's spots are
derived from its personality value and can differ between individuals of either
sex.

Scripted field actors load an explicit resource ID. The randomizer builds its
replacement actors from the same base species model used by the battle loader.
Sex remains part of the Pokémon's data for the interface and battle mechanics.
[Supported story scenes](STORY_GIFT_SCENES.md)
