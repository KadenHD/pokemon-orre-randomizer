# Story gift scenes

This audit covers the Pokémon gifts and scripted encounters the randomizer
already supports in the revision-0 releases of Colosseum and XD. The archive
inventory establishes which models are packaged with each room. It does not
identify every resource a shared engine routine can load at runtime.

## Colosseum

### Doking's gift in Pyrite

The final gift constructor supplies the species for the rescue and handover.
`M2_cave_1F_2.fsys` and `M2_guild_1F_1.fsys` each store the Plusle actor as
resource `0x06F90400`. The patch resolves the replacement's battle model using
the regional DOL resource table and `GSfsys.toc`, then adapts its HSD data for
the field actor. The scene keeps its original actor, camera and movement cues.
The twelve field animation slots use the replacement's idle pose. The field actor
shows the normal palette and uses form A for Unown. The gift itself gets the
game's normal form and the shiny result specified by the randomizer settings.

Five Pyrite archives contain the literal story references. The patch updates
35 language banks across the three discs, including the written cries, and
seven cry operands per disc. It retains the gift call and the original story
flags. Static checks converted the model of every supported species on the
European disc and repacked both actor rooms from the original US and Japanese
discs.
[Model format and animation slots](https://github.com/StarsMmd/Blender-Addon-Gamecube-Models/blob/main/technical-docs/exporter_setup.md#animation-slots)

In Dolphin 2609a, an isolated French PAL replay for seed `pyrite-scene-7`
displayed Snorlax in Duking's office, named it in the dialogue and cry caption,
and confirmed its transfer to the PC with a full party. The model can extend
beyond the fixed camera frame for large species such as Snorlax. The replay
used a copy of a QA memory card with the native room and relevant story flags
set to the start of the handover.

A separate replay started after the cave battle. It showed the updated
dialogue and cry caption in the cave and followed the native transition into
Duking's office, where Snorlax appeared. The post-battle save reload hides the
cave actor on the original disc too. Its replacement in the cave was checked
in the archive data. The PAL test ISO's SHA-256 was
`dce9e63acd20389c0930904bd4374b3c41dde42822beebca8642146fe08964c8`.

Three further French PAL replays verified the model inside the holding area
before the rescue and at Duking's office for Gengar (`pyrite-scene-17`),
Growlithe (`pyrite-scene-51`) and Chikorita (`pyrite-scene-117`). For the
cave recordings, the copied ROM starts the player at the inner door. The
handover runs with the original scene trigger on a separate copied save.

The replacement pool for this gift excludes species listed at 3.5 m or
taller in the [Pokédex data](https://github.com/PokeAPI/pokeapi/blob/master/data/v2/csv/pokemon.csv)
and Snorlax, whose width clips in the handover. This applies to both selection
paths. Wailord could obscure most of Duking's office in Dolphin before this
restriction. These species remain eligible for other encounters according to
the selected settings.

### Ho-Oh at Mt. Battle

The Battle Mode prize has its own presentation in `D2_present_room.fsys`. The
archive contains only `present_map`. In `main.dol`, `d2presentPlayGiftScene`
resolves the model and cry through two hardcoded species operands. Messages
`0x44B9–0x44BC` cover a full party and PC, the arrival, the transfer to the PC,
and receipt in the party. The original messages name Ho-Oh, with a generic
full-storage message in Spanish. The function is identified in the
[matching US decompilation](https://github.com/dougchansan/pkmn-colosseum/blob/ad02df4900c623d16d02b9a8ddd9c53ea0cd3db2/src/game/gs_range_80265EC4.c#L99).

| Disc | Model operand in `main.dol` | Cry operand in `main.dol` |
| --- | ---: | ---: |
| `GC6P01` | `0x267B7C` | `0x267C4C` |
| `GC6E01` | `0x262F9C` | `0x26306C` |
| `GC6J01` | `0x25E6C0` | `0x25E790` |

The [reward patch](../../orre_randomizer/engine/hooh_reward.py) reads the final
species from the gift constructor and uses its native name in the four reward
messages. It preserves the message window and fanfare controls. The new text
fits within the original allocation in each `main.dol` bank and the matching
European and US `common.rel` copies. The Japanese messages live in `main.dol`.
The ending at Realgam Tower has its own Ho-Oh actor and animation tracks in
`D4_casino_colo.fsys` and is a separate story event.

Static checks on all three original discs confirmed that the patch handles
different internal species IDs and fits the longest native name in each bank.
The reward model still uses the native presentation's normal palette and its
default form. The scene reads the species, while palette and form would require
the individual Pokémon's data.

A French PAL comparison in Dolphin 2609a showed Ho-Oh in the original
presentation and Luvdisc in the randomized one. Both messages named the
displayed species. A test-only shortcut opened the presentation directly.

A separate French PAL run entered Battle Mode with a copy of a story save
and registered a prepared team through the game menu. The fixture supplied
the first 99 wins and story and purification requirements. The fight against
the 100th opponent was played with a strengthened test team. The victory
handler opened the native prize event. With seed `mt-battle-qa` and a 100%
shiny rate, the presentation named and displayed Yanma. The full party sent
the level 70 shiny Yanma to the PC. The prize flag changed from 0 to 1 and the
same Pokémon identity was verified on the written memory card after saving
through the game's reward prompt.

### Pikachu and Celebi from Eagun

The added rewards at the Relic Stone reuse Eagun's actor and deliver the
selected Pokémon directly to the party or PC. The dialogue describes the gift
without naming a species and there is no Pokémon model in the handover. These
paths were previously exercised in Dolphin. Celebi's appearance when summoned
with the Time Flute and the Bonus Disc's `ex_shrine.fsys` actor `cerebi_dat`
belong to different events. [Regional gift validation](../REGIONAL_GIFTS_DOLPHIN_2026-11-03.md)

## XD

| Encounter | What the existing patch synchronizes |
| --- | --- |
| Hordel's Shadow Togepi | The gift, the eligible forms for the later exchange, and offer messages `0xA42F`, `0xA433`, `0xA435`, and `0xA436` in `S1_shop_1F.fsys`. |
| Hordel's Elekid reward | The received species and its name in messages `0xA438`, `0xA43B`, `0xA43C`, `0xA43E`, and `0xA443` in the same archive. |
| Duking's three trades | The requested and received species names in `M2_guild_1F_2.fsys`, with the received names at script offsets `0xD30`, `0xD74`, and `0xDB8`. |
| Three Mt. Battle prizes | The reward constructor and the name shown in menu and confirmation messages `0x7A49–0x7A4B` in `D2_crater_colo.fsys`. |
| Eevee and tutorial Teddiursa | Eevee's lab dialogue at `M5_labo_2F:0x9C42`. Teddiursa's battle entry and name in the tutorial, rematch, and fight banks. |

The three gift room archives contain no dedicated model for any of the vanilla
gift species. Previous Dolphin tests exercised Hordel's gift and exchange and
Duking's trades.

French PAL replays in Dolphin 2609a started from copies of an in-game test
save prepared just before the 100th match. The final battle against the Mt.
Battle master was played with a strengthened test team. A control with the
team-change flag set awarded Poké Coupons and skipped the Pokémon prize, as
the original rules require.

The first eligible replays showed the expected names and moves but awarded
non-shiny Pokémon at a configured 100% shiny rate. The gift argument block
begins at `sp+0x0C`. The old patch wrote the policy into the trainer ID word
at `sp+0x1C`. The corrected hook writes it into the upper half of the
catch-floor word at `sp+0x28` and runs the native trainer ID update.

With the corrected ISO and seed `mt-battle-qa`, three separate final victories
and saves verified every option. The menu and confirmation named Totodile,
Larvitar, and Bulbasaur, matching the preview. Totodile and Bulbasaur joined
the party. Larvitar went to the PC when the party was full. Each save contained
the selected prize at level 5 with the expected moves, trainer ID, and shiny
status. Patch assembly was also checked on the US and Japanese DOLs.

The same correction was tested in French PAL with the `trade-check-49` seed
and a 5% shiny rate. Two prepared copies of a native save supplied a purified
Togepi for Hordel and Trapinch, Surskit, and Wooper for Duking. The four trades
ran through the game's dialogue and party selection. After saving in-game,
the memory cards matched the preview for species, level, moves, and shiny
status. Hordel's Beautifly and Duking's Miltank were shiny. Duking's Nidoran♂
and Aron were standard. The cards also retained the trainer IDs assigned by
the native trade routines.

Shadow Lugia is a separate case with a dedicated model and purification path.
Bonsly and Munchlax are scripted field Pokémon outside the randomizable gift
pool. [XD investigation and runtime checks](XD.md)
