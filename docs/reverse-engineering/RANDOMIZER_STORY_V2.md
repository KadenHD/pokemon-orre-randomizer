# Story randomizer v2: trainers, starters and gifts identified

This version of the **30 octobre 2026** extends the randomizer to the six starter and gift routines
identified in the PAL program **GC6P01, revision 0**. At the same time, it reproduces the drawings
of trainers of the v1.

To play this version, use **`jouer-randomizer-histoire.ps1`** at the root of the project. This
launcher explicitly opens the new ISO with its isolated profile, without using the usual memory
card.

- ISO : `build/randomizer-story-v2/colosseum-pal-randomizer-story.iso`
- Taille : **1 459 978 240 octets**.
- SHA-256 : `1e1dea04cb1bac4e4c82abf4301843934d11430782927d97342e92bfb86d0686`
- Script : `scripts/randomize_story.py`
- Journals: `randomizer-manifest.json` for trainers, `specials-manifest.json` for
  starters/gifts, in the construction directory.
- Verification: `build/randomizer-story-v2/story-verification.json`
- Captures : `build/randomizer-story-v2/evidence/`
- Sustainable Summary of Controls: [story-v2-validation.json](story-v2-validation.json)

## Result of the seed

| Original location | Replacement | Level retained | Routine status |
|---|---|---:|---|
| Umbreon | **Smeargle** | **26** | Starter |
| Espeon | **Slowbro** | **25** | Starter |
| Plusle | Arbok | 13 | Gift of scenario |
| Ho-Oh | Articuno | 70 | Rewards |
| Celebi | Seadra | 10 | Event Routine present in PAL, access not shown |
| Pikachu | Qwilfish | 10 | Event Routine present in PAL, access not shown |

The **3,355 Pokémon of trainers in 817 trainers**, including **48 dark groups**, remain identical to
those produced by the same seed in v1. The REL and the entire archive `common.fsys` have the same
bytes as the v1. The rules of dark levels, abilities, talents and aliases are described in [the v1
ratio](RANDOMIZER_V1.md).

## Programme changes

The script rejects any DOL different from the original SHA-256
`a788176a45eb88dbd227246a7205ab9856bc79f3cca7e4a0f5376cf466664df5`. It checks the PowerPC
instructions `li r4, espèce`, `li r5, niveau` and the call to the local constructor `0x80128238`,
then replaces only the immediate species and the two immediate starter EXPs.

| Routine | Base in main.dol | Species field u16 |
|---|---:|---:|
| Umbreon | `0x131E1C` | `0x131E1E` |
| Espeon | `0x131CF4` | `0x131CF6` |
| Plusle | `0x131BF4` | `0x131BF6` |
| Ho-Oh | `0x131B10` | `0x131B12` |
| Celebi | `0x1318E0` | `0x1318E2` |
| Pikachu | `0x1319F0` | `0x1319F2` |

The starters rewrite their EXP after creation. At `base + 0x92`, this EXP is recalculated at
**threshold of the retained level**, depending on the growth group of the new species: Smeargle
receives **14 060 EXP** at level 26. Slowbro **15 625 EXP** at level 25. The partial progression to
the next level is reset to zero. The other four routines allow the manufacturer to calculate the
EXP.

The manufacturer initializes the name from the new species. The calls and instructions for
abilities/objects/nature remain unchanged. The capabilities imposed by routines can therefore remain
those of the replaced species, as for the Pokémon of trainers.

For this seed, **11 octets de main.dol** change. Its SHA-256 becomes
`6330e041a5f13fb63a65d308a3a8d45e47c99b462d4e396be8eba3869b93b485`. The original DOL is never opened
in writing. Its modified version is also kept in the construction directory.

The ISO check allows only the actually different DOL bytes, the eight FST bytes of `common.fsys` and
the new archive. **1 459 018 413 other bytes** remain identical to the ISO source. The entire DOL
must also be equal to the result recalculated since the seed. No mask can hide other code changes.

## Reproducibility and controls

The overall version is **`trainers-and-gifts-v2`**. It reuses the SHA-256 v1 draw with the separate
keys `special:umbreon`, `special:espeon`, `special:plusle`, `special:ho-oh`, `special:celebi-event`,
`special:pikachu-event`. The pool remains that of the 386 real species, excluding the original
species of each routine. The seed does not fix AI, PID or damage during the parts.

**30 tests** pass, including the six growth groups, thresholds 25/26, repeatability, rejection of
bad DOL or unexpected instructions, rejection of a change in levels/capacity/code and creation of a
profile without importing backup.

`DolphinTool verify` ends with code **0**, `Problems Found: No`, CRC32 `c5c5e4ac`, SHA-1
`c5a194b99377b36f9b82ecef565058b7b47a1a44`. It also issues `Error creating key`, as in previous
checks.

## Real test of a new part

ISO was launched with **Dolphin 2609a, JIT64 SC, Direct3D 12, DSP HLE**, cheats disabled, in
`build/randomizer-story-v2/dolphin-user`. This profile was created with `--empty-card`, without
importing the usual memory card or SRAM. The game confirmed the absence of a file, created its file
on the new card, and then started a new part named **MICHAEL**.

After the introduction, the Pokémon menu of the scenario actually shows the two replacements. The
cards display their animated models and the following information.

| Starter obtenu | Level | PV | Type | Talent | EXP | EXP jusqu'au level suivant |
|---|---:|---:|---|---|---:|---:|
| Smeargle | 26 | 71/71 | Normal | Tempo Perso | **14 060** | **1 686** |
| Slowbro | 25 | 86/86 | Eau / Psy | Tempo Perso | **15 625** | **1 951** |

These values confirm that the levels and curves of EXP remain consistent after replacement. The
emulator was closed properly with the output code **0**. No fight of this new part nor actual
obtaining of a late gift was used as evidence.

| Preuve | Capture in evidence/ |
|---|---|
| Empty test card, no imported file | `01-fresh-memory-card.png` |
| Two starters received in the scenario team | `02-new-story-starter-team.png` |
| Model, Statistics and EXP Smeargle | `03-queulorior-summary-exp.png` |
| Model, Statistics and EXP Slowbro | `04-flagadoss-summary-exp.png` |

The usual profile was inventoried before this session. An attempt to check with the v1 historical
manifest reported four already different configuration/SRAM files during the preparation of v2. The
retention control of this extension relates to the v2 manifest. The old manifests remain retained. A
compatibility check on ISO v1 with the current profile reference is passed in
`build/regression-v1-current-baseline/`.

After Dolphin's closure, the complete verification confirms that **the ISO source, the 2,011 files
of `game/` and the 20 existing files of the usual profile inventoried before this test are
unchanged**. The REL, the FSYS archive and the DOL have been reproduced since the season and
compared to the final ISO bytes. The previous three ISOs retain their respective SHA-256. The
durable summary contains the detailed results and hashs of the four catches.

## Perimeter and limits

Celebi/Pikachu routines exist in the DOL PAL. Modify them **n'active pas** these events. Their
access conditions are not changed. Late gifts and events still require specific testing.

The external distributions Jirachi/Bonus Disc and e-Reader are not processed by these six routines.
Jirachi remains a possible species in the draw pool. The 33 unreferenced populated locations of the
trainer table remain preserved. One of them is zero-level and without capacity. A constant
constructor of [Treecko level 1, with an unestablished role, is also retained.

The old backups are not converted: the already created Pokémon remain the backup ones. Pre-recorded
kinematics, fixed images and dialogues are not rewritten. This version does not constitute a
validation of a complete path, captures/purifications or all rewards.

## Build and launch

From the root of the project.

```powershell
.\jouer-randomizer-histoire.ps1
```

For another seed, choose an existing output directory.

```powershell
python scripts/randomize_story.py --source-iso 'Pokemon Colosseum (Europe) (En,Fr,De,Es,It).iso' --seed 'ma-seed' --output-dir build/histoire-ma-seed
python scripts/prepare_dolphin_test.py --output build/histoire-ma-seed/dolphin-user --empty-card
.\scripts\start_dolphin_test.ps1 -Iso build/histoire-ma-seed/colosseum-pal-randomizer-story.iso -UserDirectory build/histoire-ma-seed/dolphin-user
python scripts/randomize_story.py --verify-only --output-dir build/histoire-ma-seed
```

`--empty-card` creates a new profile without importing old cards or SRAM. Originals are inventoried
for final control. The copy mode used by previous tests remains the default behavior without this
option.

## Primary sources

- [XGDemoStarterPokemon.swift, commit
  f2d6c4a](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/enumerable/XGDemoStarterPokemon.swift):
  Colosseum and starter EXP routines.
- [CMGiftPokemon.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/enumerable/CMGiftPokemon.swift)
  and
  [CMGiftPokemonManager.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/managers/CMGiftPokemonManager.swift):
  four gifts and all six routines.
- [XGExpRate.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/enums/XGExpRate.swift)
  and
  [CMPokemonStats.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/enumerable/CMPokemonStats.swift):
  growth and group byte at `species + 0x00`.
- [Dispatching of the six gifts in NTSC-U
  decompilation](https://github.com/dougchansan/pkmn-colosseum/blob/ad02df4900c623d16d02b9a8ddd9c53ea0cd3db2/src/game/field_range_801CA7EC.c#L349):
  substantiation of the roles. The offsets used come from the verified DOL PAL.
