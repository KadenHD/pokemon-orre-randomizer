# Story gift scenes

This audit covers the Pokémon gifts and scripted encounters the randomizer
already supports in the revision-0 releases of Colosseum and XD. The archive
inventory establishes which models are packaged with each room. It does not
identify every resource a shared engine routine can load at runtime.

## Colosseum

### Folly's first battle in Phenac

The entrance script in `M1_out.fsys` shows message `0x4E8D` after battle 14.
The replacement text reads the final species from trainer row 12, party rows
49 and 50. Both original slots hold Whismur. The patch updates the first page
with names from the original ROM's species banks. It leaves the second page,
script, later battles, and all other messages intact.

### Miror B.'s dancers in Pyrite Cave

The four Ludicolo field actors in `M2_cave_1F_2.fsys` now use the final species
from their corresponding battle slots. The retry after snagging Sudowoodo
uses the same four replacements. The original scene, actor positions and
camera cues are retained, but replacement Pokémon use their own idle pose.
The patch does not change Miror B. or his successor Mirakle B.
With seeded shinies, each actor uses its own battle slot's shiny decision,
which the retry also reuses. A French PAL Dolphin test put four Wailord around
Miror B. at 12% scale without obscuring him. With the seed
`wailord-mixed-763` and a 5% rate, one of the four was shiny on stage. The
first pair sent out in battle contained that shiny and a standard Wailord.

### Doking's gift in Pyrite

The final gift constructor supplies the species for the rescue and handover.
`M2_cave_1F_2.fsys` and `M2_guild_1F_1.fsys` each store the Plusle actor as
resource `0x06F90400`. The patch resolves the replacement's battle model using
the regional DOL resource table and `GSfsys.toc`, then adapts its HSD data for
the field actor. The scene keeps its original actor, camera and movement cues.
The twelve field animation slots use the replacement's idle pose. The actor
uses form A for Unown. It displays the gift's shiny color when the result is
known during ROM creation (a seeded draw or a guaranteed rate). If the game
draws the result at runtime, the actor displays the normal color.

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

Large species are eligible again. Both gift scenes use a reduced field
model for the species formerly excluded by size, including Snorlax. This
applies to both gift selection paths. The gift itself uses the normal
battle model. In the PAL test, a 6% Wailord fit in Duking's office and the
native scene confirmed its transfer to the PC. The shiny Wailord was visible
in the holding room and during the handover in a separate French PAL test.

The scene uses a retail shiny model when the disc has one. Otherwise the
converter applies the model's native PKX color recipe to the field copy's
textures and palettes without replacing battle textures.
[PKX color data reference](https://github.com/StarsMmd/Blender-Addon-Gamecube-Models/blob/main/technical-docs/shiny_variants.md)

### Colosseum opening

The Snagem Hideout escape is a prerecorded video at `movie/openingdemo.thp`.
The French PAL Dolphin frames match the decoded disc video, including the
shots of Umbreon running and both starters riding in the sidecar. The frames
retain those original models. The disc also contains Snagem Hideout models
and camera tracks in `S2_out_3.fsys`, but that room's script does not contain
the full movie sequence.

The initial arrival at Outskirt Stand is rendered in real time. The
[arrival patch](../../orre_randomizer/engine/starter_arrival.py) reads the
final starter species from the two constructors. It gives the scene its own
motorcycle resource, hides the replaced riders' geometry, and attaches the
selected models to the original joints. The script closes the new actors
before closing the motorcycle and keeps the native camera and animation.
The retail Pokédex height sets the scale cap and vertical offset for each
rider. The attachment updates the outer joint's transform every frame.
An unanimated child joint applies the scale and the seat offset without
altering the original skeleton or motion.
Shiny models use the seed's starter decisions or the guaranteed shiny rule.
When shininess is rolled during play, the arrival uses the regular palette.

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
The final handover hook captures the actual reward's personality value and
the result of the game's shiny check. The presentation passes both values to
the native model loader to select the form and palette, then clears them.
This also works with the original Ho-Oh when custom shiny rules are active.

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

After the appearance fix, a second muted French PAL run played the last
battle on a private copy of the prepared card. The native model loader
received Yanma's personality value and shiny flag, and the scene displayed
its blue palette. The game saved the reward to the copy, and the decrypted
memory-card slot contained the same level 70 Yanma with valid checksums.

### Pikachu and Celebi from Eagun

The added rewards at the Relic Stone reuse Eagun's actor and deliver the
selected Pokémon directly to the party or PC. The dialogue describes the gift
without naming a species and there is no Pokémon model in the handover. These
paths were previously exercised in Dolphin. Celebi's appearance when summoned
with the Time Flute and the Bonus Disc's `ex_shrine.fsys` actor `cerebi_dat`
belong to different events. [Regional gift validation](../REGIONAL_GIFTS_DOLPHIN_2026-11-03.md)

## XD

### Eagun's partner

The Pikachu actor at Eagun's house and the Relic Stone uses the final species
from his story battle. Its cries and written captions follow the new species.
Large models are reduced only for the field scenes. A French PAL test with
Wailord confirmed that the smaller model fits alongside Eagun after battle.

### Other scripted encounters

| Encounter | What the existing patch synchronizes |
| --- | --- |
| Hordel's Shadow Togepi | The gift, the eligible forms for the later exchange, and offer messages `0xA42F`, `0xA433`, `0xA435`, and `0xA436` in `S1_shop_1F.fsys`. |
| Hordel's Elekid reward | The received species and its name in messages `0xA438`, `0xA43B`, `0xA43C`, `0xA43E`, and `0xA443` in the same archive. |
| Duking's three trades | The requested and received species names in `M2_guild_1F_2.fsys`, with the received names at script offsets `0xD30`, `0xD74`, and `0xDB8`. |
| Three Mt. Battle prizes | The reward constructor and the name shown in menu and confirmation messages `0x7A49–0x7A4B` in `D2_crater_colo.fsys`. |
| Eevee and tutorial Teddiursa | The starter name in both simulator outcomes at `M5_labo_2F:0x9C42–0x9C43`. Teddiursa's battle entry and name in the tutorial and rematch. The separate Teddiursa message in the fight banks belongs to Atill's Mt. Battle team. |

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
The [v1.2.10 replay](../XD_SHADOW_SHINIES_VALIDATION.md#shadow-lugia-in-v1210)
checks its final scene, capture and purification with the default preset.
Bonsly and Munchlax are scripted field Pokémon outside the randomizable gift
pool. [XD investigation and runtime checks](XD.md)
