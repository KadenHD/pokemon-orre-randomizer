# First randomizer of Pokémon trainers

The **October 30, 2026** version for the dump **GC6P01 PAL, Revision 0**. The engine builds a new ISO
from the original data and the selected seed.

- ISO : `build/randomizer-v1/colosseum-pal-randomized.iso`
- Size is **1,459,978,240 bytes**.
- SHA-256 : `576e362ed037d8c1889683f6a72b5a83eee815d9346c07c3dad4e7a836ba0440`
- Script : `scripts/randomize_trainers.py`
- Full manifest: `build/randomizer-v1/randomizer-manifest.json`
- ISO verification: `build/randomizer-v1/randomizer-verification.json`
- Evidence of the test: `build/randomizer-v1/evidence/`
- Validation summary: [randomizer-validation.json](randomizer-validation.json)

## Rules of this version

The randomizer replaces the species of **3,355 populated sites referenced by the trainer table** in
**817 of the 820 trainers**. Each selected location receives a different species from its original
species, drawn evenly among **386 real species**. The valid internal indices are `1..251` and
`277..411`. Reserved entries, zero and egg are excluded.

The locations shared by several trainers are treated once. **108 Shadow Pokémon slots**
are grouped by their **48 Shadow IDs**: one single draw per ID, propagated to all battles and
to the species of the associated Shadow table. The identifiers, counters, trainer references and other
fields of this table are kept. Multiple Shadow IDs can receive the same species.

The displayed name is updated with the default name of the new species. The script rejects a custom
name or an unknown version of the REL. Levels, abilities, objects, nature, sex, EV and IV are
retained. The talent selector is retained, except **410 fallbacks `1 → 0`** when the new species does
not possess a second ability. The random ability marker `FF` remains intact.

The version retains the **2,122 empty slots**, **33 occupied slots not referenced by
trainers**, DOL starters and gifts, script texts and scripts. The replacement Pokémon inherit the original Pokémon’s moves, which may fall outside their usual learnset. The teams are not
balanced by power, type or stage of evolution.

## Reproducibility

The algorithm is identified by **`trainer-species-sha256-v1`**. It uses SHA-256 with surplus
rejection before modulo reduction, without depending on the random Python generator, the hour or the
iteration order of the dictionaries.

The hash input is the following concatenation: ASCII version ID, zero byte, two-byte big-endian
length, exact UTF-8 seed, zero byte, ASCII key, zero byte, four bytes big endian counter. The key is
`slot:INDEX` for an ordinary Pokémon or `shadow:ID` for an obscure group. The counter starts at zero.
The pool is sorted by internal index and the original species is excluded. Seeds contain 1 to 256
bytes UTF-8. Spaces, line breaks, and accents are part of the seed.

The same seed, the same dump and the same version reproduce the same data. The seed does not fix the
draw of opponents, the AI or the damage of the game during the games: it fixes the content of ISO.

The build calculates the REL twice from the original. The verifier then recalculates the REL and the
FSYS archive from the seed, and compares them byte by byte with the data reread in the final ISO.
All other ISO ranges are fully compared to the source image.

## Static checks

The output REL has SHA-256 `de232598f23440f9be97d71fce14e7cbe8998c1b26474eef2034d66ba3b13bcc`. **10,568 bytes** change, exclusively in the fields of species, name, the ability slot fallbacks and the
48 species fields in Shadow metadata. **27 other members** of `common.fsys` are identical after
decompression.

The reconstructed archive measures **959,808 bytes** and is placed at `0x418000`. The image differs
from the original only in its range `[4,292,608, 5,252,416)` and the eight FST bytes `[4,222,988, 4,222,996)`. The **1,459,018,424 other bytes** are identical.

`DolphinTool verify` ends with the code **0**, `Problems Found: No`, CRC32 `5b328d93` and SHA-1
`7bdc606df9a91aa8cfba2c39fa25362efe3a0017` and also emits `Error creating key`, as in previous
tests.

**25 tests** cover readers, encoder, control patch and randomizer: frozen seed vectors, even
seed/same result, different seeds, obscure aliases, shared locations, empty and unreferenced boxes,
talents and rejection of additional modifications.

The formats are based on [local analysis and its primary sources](community-formats.md), including
[CMTrainerPokemon.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/enumerable/CMTrainerPokemon.swift),
[CMPokemonStats.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/enumerable/CMPokemonStats.swift)
and [the Pokémon generator of the US
decompilation](https://github.com/wastelandgunner/pkmn-colosseum/blob/20fb9460b2259bf17631a5777fc080d918291d65/src/game/pokemon_range_8011F5FC.c).
The offsets used are checked on our PAL REL. The addresses of the US version are not transposed.

## Dolphin test

The new ISO has been explicitly launched with **Dolphin 2609a, JIT64 SC, Direct3D 12, DSP HLE**,
cheats deactivated, in the profile `build/randomizer-v1/dolphin-user`. The EUR memory card and SRAM
are copied to it. No condition from an old ISO has been loaded. Interactive inputs pass through
Dolphin's TAS controller, via Windows interface control.

The scenario is **Quick fight → Double → Very strong**, to the Colosseum of Phenac City. The game
attributed the team of **Simone (766)** to the player **MICHAEL**, facing **Basile (771)**. The
twelve species displayed correspond exactly to the manifest of this seed.

| Team | Species of origin, in sequence | Randomized species observed |
|---|---|---|
| Simone, loaned to the player | Meganium, Typhlosion, Feraligatr, Espeon, Umbreon, Ursaring | Nosepass, Oddish, Forretress, Hoothoot, Skarmory, Delcatty |
| Basile, computer-controlled | Suicune, Raikou, Entei, Aggron, Donphan, Salamence | Electrode, Seviper, Mankey, Kadabra, Tangela, Slowking |

Forretress, Nosepass, Oddish and Skarmory have been selected. The combat loads the models of
Forretress and Nosepass against Tangela and Electrode. The four Pokémon are level 50. Their initial
HP values displayed are respectively **135, 90, 125 and 120**. The menu of Forretress displays
AncientPower, Earthquake, Brick Break, and Return, inherited from Feraligatr’s record.

| Evidence | Screenshot in evidence/ |
|---|---|
| French title screen | `01-french-title.png` |
| Copied memory card loaded | `02-copied-memory-card-loaded.png` |
| Six species of Simone's team | `03-randomized-player-team.png` |
| Twelve species of both teams | `04-randomized-both-teams.png` |
| Four loaded models and initial HP | `05-randomized-battle-models.png` |
| Moves inherited by Forretress | `06-preserved-moves.png` |
| Return to next round menu and updated HP | `07-turn-resolution.png` |
| AncientPower went from 5 to 4 PP | `08-post-turn-pp-consumed.png` |

A turn was played by commanding **Forretress to use AncientPower on Tangela** and **Nosepass to use Body Slam on
Electrode**. The game returned to the attack menu, without blocking. The HP values observed after this
turn are Forretress **117/135**, Nosepass **51/90**, Tangela **104/125**, Electrode **30/120**.
AncientPower then displays **4/5 PP**. The HP changes are those of the complete round. They
are not assigned in isolation to a single move.

Dolphin was then closed properly with the output code **0**. The test covers this interactive tour,
without full combat or scenario path.

## Preservation after testing

The complete check performed after Dolphin's closure confirms that **the ISO source, the 2,011 files
of `game/` and the 20 existing files of the usual Dolphin profile controlled by the manifest are
unchanged**. Original memory cards remain in the usual profile. Session writings and caches belong
to the new profile under `build/`.

The REL and the FSYS archive recalculated since the seed are identical to those found in ISO. The
hashes of the two previous results, ISO without change and Pikachu control patch, have also been
rechecked and are unchanged. The details of these controls and the hashes of the eight screenshots are
recorded in the durable summary.

## Validation limits

The consistency of the 48 dark groups is statically controlled in ISO. Their capture, reappearance
after failure, purification and evolution are not validated by this rapid combat test. The old
captures are not migrated, the dialogs naming the original species are not rewritten and all
possible particular cases of scripts/DOL have not been excluded. A complete progression of the
scenario remains necessary before considering this version as validated for an entire part.

No physical console testing, backup writing in play, audio evaluation or performance measurement.

## Build another seed

From the root of the project, choose a non-existent output directory.

```powershell
python scripts/randomize_trainers.py --source-iso 'Pokemon Colosseum (Europe) (En,Fr,De,Es,It).iso' --seed 'ma-seed' --output-dir build/randomizer-ma-seed
python scripts/prepare_dolphin_test.py --output build/randomizer-ma-seed/dolphin-user
.\scripts\start_dolphin_test.ps1 -Iso build/randomizer-ma-seed/colosseum-pal-randomized.iso -UserDirectory build/randomizer-ma-seed/dolphin-user
python scripts/randomize_trainers.py --verify-only --output-dir build/randomizer-ma-seed
```

To launch the ISO already produced.

```powershell
.\scripts\start_dolphin_test.ps1 -Iso build/randomizer-v1/colosseum-pal-randomized.iso -UserDirectory build/randomizer-v1/dolphin-user
```

The preparation copies the memory card and the SRAM in the isolated profile. The captures already
present in an old backup are not converted: start a new part in this profile to play the randomized
scenario. Do not load a Dolphin state from another ISO, which could restore the old tables to
memory.
