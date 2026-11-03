# Pokémon Orre Randomizer

A free, open-source desktop randomizer for the Pokémon games set in Orre.
**Pokémon Colosseum** is supported today. **Pokémon XD** is planned.

Choose a clean Colosseum ISO or RVZ, a seed, and the rules you want to change.
The app processes the image locally and writes a separate output file.

## Download and run

On Windows 10 or 11 (64-bit), download the **Windows setup EXE** from
[GitHub Releases](https://github.com/KadenHD/pokemon-orre-randomizer/releases)
and run it. For portable use, download the Windows ZIP, extract the entire
archive, and open `OrreRandomizer.exe` beside its `_internal` folder.

Choose **Pokémon Colosseum** on the home screen. The Windows builds include
Python and the Rust codec.

## Using the app

1. In **ROM**, select or drop your clean ISO or RVZ.
2. In **Settings**, choose a preset and a seed, or import a profile from **Profiles**.
3. In **Create**, choose a new ISO or RVZ destination and check **Applied settings**.
4. Open the verified output in Dolphin and start a new game to see the new
   starters and encounters.

Select `DolphinTool.exe` from your [Dolphin installation](https://dolphin-emu.org/download/)
to read or write RVZ. The **ROM** step shows the field for RVZ inputs and **Create**
shows it for RVZ outputs. The fields share a path. The suggested output format
matches the source and can be changed. ISO-to-ISO creation needs no DolphinTool.
The app creates a disc image. Launching Dolphin and managing its saves are separate.

The app follows your system language, with English as the fallback. The selector
offers French, English, German, Spanish, Italian, and Japanese. Language changes
apply immediately, preserve the form, and are remembered. The game language
depends on your ROM. Evolution stone names and Eagun's dialogue follow the
languages available in the game.

**Music** and **Sounds** are independent preferences and start enabled when the
audio pack is present. The local build can use exported media. The public build
uses its own panels and controls. Both can start before you select a ROM.

### Presets and advanced settings

| Preset | What it changes |
| --- | --- |
| **Pokémon + moves** | Replaces Pokémon with others of similar strength and randomizes moves, level-up learnsets, TMs, and eligible chest and shop items. |
| **Pokémon only** | Replaces Pokémon without balancing their strength. It keeps moves, learnsets, TMs, and items, with the evolution stones available in shops. |
| **Unchanged copy** | Makes a verified copy and can convert between ISO and RVZ. |

Both randomized presets cover regular trainers, Shadow Pokémon, starters, and
gifts. They adapt evolutions for Colosseum, stock evolution stones in Phenac City
and Pyrite Town, and try to avoid repeated evolution families across starters,
Shadow Pokémon, and gifts. Fixed and manually chosen Pokémon, exclusions, and
strict rules take priority. Remaining duplicates appear in the preview and the
creation report. Older profiles import this cross-group rule disabled to preserve
their results.

**Advanced** provides 83 settings across fifteen categories. Switching between
Simple and Advanced preserves custom settings. In Advanced, use **Search settings…**
to find a label, help text, category, or choice in the current language. Selecting
a result focuses the corresponding field. **Recommended values** resets only that
category to the **Pokémon + moves** preset.

The main options include:

- **Trainers and Shadow Pokémon.** Randomize ordinary and Shadow Pokémon separately.
  The full trainer draw covers 3,355 Pokémon across 817 trainers. The 48 Shadow
  groups stay synchronized across encounters. You can require a different family
  for each Shadow Pokémon, give eligible non-Shadow teams a shared type, or require
  fully evolved non-Shadow opponents from a chosen level.
- **Starters.** By default, the randomized presets use base forms from families with
  three successive stages. Choose a different stage, disable the three-stage filter,
  or select either starter by name or National Pokédex number. A manual choice
  bypasses that starter's stage and individual power filters. Exclusions, permitted
  generations, and the rules for the pair still apply. Pair rules cover comparable
  strength, distinct families, and shared types. Starting levels are retained and
  experience is adapted to the replacement species.
- **Gifts.** Replace Plusle, Ho-Oh, and the event gifts for Pikachu and Celebi
  independently. With **Make event gifts obtainable** enabled, Eagun gives Pikachu's
  gift after 10 purifications at level 30 and Celebi's after 25 at level 45 by
  default. The four values can be changed separately. Eagun becomes available at
  the Relic Stone after the purification introduction, including the follow-up
  after Skrub. Each gift can be received once per save.
- **Moves and TMs.** Randomize trainer, starter, and gift moves and level-up learnsets
  separately. Options cover type matching, damaging moves, duplicates, and bans on
  self-destruct or one-hit knockout moves. Shadow Rush and special markers are
  protected. Shuffle 50 TMs with their descriptions and choose how compatibility
  is assigned. The eight HM records are preserved.
- **Bosses and eligible species.** Adjust seven bosses, protect family diversity,
  and set separate legendary and strength filters for their Shadow Pokémon.
  Exclude species or original types, restrict generations, and control legendary
  or mythical Pokémon and power matching. Shedinja is excluded from the normal
  replacement pool to avoid issues with Wonder Guard.
- **Species data and items.** Randomize types, abilities, stats, held items, eligible
  chest contents, and six shop inventories independently. Optional rules preserve
  family consistency, stat totals, item value, Poké Balls, or healing items.
  Key items, Time Flutes, stone availability, and scripted rewards are protected.
- **Levels, experience, and capture.** Adjust opponent levels from ×0.5 to ×2.
  Progressive difficulty offers separate multipliers for original levels 1–35,
  36–50, and 51–100. Shadow capture rate ranges from ×0.25 to ×5 with a configurable
  minimum. Battle EXP ranges from ×0.25 to ×5, and Heart Gauge reduction from ×1
  to ×10. Final purification still takes place at the Relic Stone.
- **Evolutions and shops.** Adapt trade, held-item trade, Clamperl, Eevee, and Feebas
  evolutions separately. Onix evolves into Steelix on leveling up from level 40 when
  held-item trades are adapted. Shadow Pokémon must be purified before evolving.
  The six evolution stones cost 2,100 each when their shops are enabled.
- **Shiny Pokémon.** Choose a 0–100% chance for supported encounters. Both randomized
  presets default to 5% linked to the seed. With the seed link enabled, Shiny status
  is decided per encounter for a new game, including when two encounters use the
  same species. Unlink it to roll in-game. Nature, gender, IVs, and the full PID are
  still generated by the game. Existing Pokémon keep their status.

See the [starter rules](docs/STARTER_STAGES.md), [trainer policies](docs/TRAINER_POLICIES.md),
[Shiny rules](docs/SHINIES.md), and [v0.15 progression notes](docs/DESKTOP_V15.md)
for the exact behavior and validation scope.

### Preview, profiles, and reports

In **Pokémon preview**, calculate the result for the selected ROM, seed, and settings.
The preview covers both starters, all 48 Shadow Pokémon, and four gifts. It compares
original and replacement encounters and displays decoded portraits from your ROM.
An unknown result is shown as `?` before calculation. A small red star marks a
known Shiny. If evolution families repeat, open **Duplicates** to see the encounters
involved. Click a starter's details button or an encounter row to view its stats,
moves, and evolutions.

You can cancel the preview or refresh it after changing settings. RVZ preview can
reuse one temporary decoded ISO per window. Creation can reuse the exact patch plan
from a matching preview and always verifies the complete output.

**Profiles** imports and exports a small JSON file with the seed and settings.
It carries no ROM data or local paths. **Restore from a report…** loads the seed
and settings from an existing creation report and compares the selected ROM with
the original used for that report.

Creation writes the verified image and two companion files:

- The `.iso.json` or `.rvz.json` report records the seed, settings, versions, and
  SHA-256 hashes. Keep it to reproduce the run. The same source, seed, settings,
  and engine version produce the same ISO. RVZ compression bytes can depend on
  DolphinTool's version.
- The `.iso.html` or `.rvz.html` journal is an offline guide with collapsible
  sections for starters, Shadow Pokémon, gifts, trainers, evolutions, and TMs.
  The GUI uses the current interface language. The CLI accepts
  `--journal-language fr|en|de|es|it|ja` and defaults to French.

See [Pokémon details and the journal](docs/POKEMON_DETAILS_AND_JOURNAL.md) for
what the preview and the final report contain.

## Compatibility

The app supports three original revision 0 discs. The decoded ISO must be
1,459,978,240 bytes and match the complete SHA-256 for its region.

| Region | Game ID | Original ISO SHA-256 |
| --- | --- | --- |
| Europe (five languages) | `GC6P01` | `1e3b4aa806ac3367cca13496f7701137e9437e7bac0101f75b9b137633a10aa9` |
| USA (English) | `GC6E01` | `78c4074429fa598b97bfac296bf8e0f7e93f5cb6d8679f8d2653ca902820f6c5` |
| Japan (Japanese) | `GC6J01` | `17c284ab2592083b91d33229ea03384ccdd397eab5db5d3a6ddf5b1f9685368f` |

Profiles can be used with all three regions. To reproduce the exact output, use
the same original image. The app rejects unknown revisions, already randomized
images, and incomplete dumps.

Allow about **1.5 GiB** free for ISO → ISO, **2.8 GiB** for RVZ → ISO, and
up to **5.6 GiB** for RVZ → RVZ. An RVZ preview can hold about **1.5 GiB** in
the system temporary directory until its window closes. Normal completion,
failure, or cancellation removes owned temporary files. After a forced stop,
check for leftover `.colosseum-*` directories.

See the [regional compatibility report](docs/REGIONAL_COMPATIBILITY_2026-11-03.md),
[regional gift tests](docs/REGIONAL_GIFTS_DOLPHIN_2026-11-03.md), and
[Dolphin validation report](docs/DOLPHIN_VALIDATION_2026-10-31.md) for what
was checked in-game. The reports document selected scenarios and their limits.

## Run from source

Use Python 3.12 or later.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m colosseum_randomizer
```

The GUI uses Qt. The Python LZSS codec works without Rust. To enable the Rust
codec from source, run `python scripts/build_native.py` with the Rust toolchain
installed. The Python and Rust encoders produce the same bytes.

The CLI uses the same engine as the GUI:

```powershell
python -m colosseum_randomizer.cli original.iso new-game.iso --seed my-seed
python -m colosseum_randomizer.cli original.rvz new-game.rvz --seed my-seed --dolphin-tool C:\Dolphin\DolphinTool.exe
python -m colosseum_randomizer.cli original.iso shared-game.iso --profile my-game.json
python -m colosseum_randomizer.cli original.iso duo.iso --seed my-seed --starter-umbreon-species 94 --starter-espeon-species 208 --journal-language en
```

Run `python -m colosseum_randomizer.cli --help` for all CLI flags. Rules can be
enabled or disabled individually, for example `--no-starter-umbreon`,
`--no-gift-hooh`, and `--no-evolve-beauty`. The CLI defaults preserve existing
usage. Use a profile to reproduce the exact GUI settings.

## Development and distribution

See [Contributing](CONTRIBUTING.md), [the release guide](docs/RELEASE.md),
[the changelog](CHANGELOG.md), and [reverse-engineering notes](RESEARCH.md).
The project code is [MIT licensed](LICENSE). See the [third-party notices](THIRD_PARTY_NOTICES.md)
for Qt, other dependencies, and media provenance.
