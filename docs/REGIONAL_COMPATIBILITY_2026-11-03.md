# Compatibility Europe, USA and Japan — version 0.14.0

Version 0.14 accepts the three Colosseum revision 0 ROMs identified in
[README](../README.md#compatibility). It retains the same options in all three regions, with data
provisions and native addresses specific to each executable. Original files remain read-only. Each
creation produces a separate image and report.

## Identification and adaptation

The header selects a candidate region. The entire ISO SHA-256, after decompression of an RVZ, must
then correspond exactly to this region. Changing an ID in a header is not enough to allow a patch.
DOL executables, `common.rel` data and gift and shop archives also have their own fingerprints and
content checks. A mixture of components from different regions is refused.

| Version | Identifier | Size of the original DOL | Languages of the game |
| --- | --- | ---: | --- |
| Europe | `GC6P01` | 4,096,576 bytes | English, French, German, Italian, Spanish |
| USA | `GC6E01` | 3,779,808 bytes | English |
| Japan | `GC6J01` | 3,699,680 bytes | Japanese |

The tables share the same diagrams and accounts: 820 trainers, 5,510 records of Pokémon of trainer,
413 lines of species including the 386 real species, 358 capacities and 97 lines of obscure
metadata. Their positions and banks of names differ. USA banks bear the native tag `US`. Japanese
banks use their native headers and UTF-16BE chains.

The six starter and gift routines, the constructors, the starting capabilities, the object and TM
tables, the PID generators and the player/memory variables have been identified in each executable.
The expected connection instructions and targets are checked before modification. The Japanese SDK
`arenaLo` variable uses a different displacement, among other things. The allocations of the new
patches follow each version.

The USA and Japan regions have only one store archive, compared to five for PAL. The patches no
longer seek to create missing language variants. The Japanese names of the stones remain native. The
patch of spacing concerns eleven PAL labels and a USA wording, without any necessary change in
Japan.

## GiftsEagun and Languages

The original script of the Relic is identical in all three regions. The few differences in the
Japanese home script are outside the modified areas. The script conditions, native identifiers of
gifts and persistent indicators are retained. The non-target members of the archives remain
identical.

The five new dialogues follow the native language of the game: five translations in Europe, English
in the USA, Japanese in Japan. Japanese uses real UTF-16BE channels, native controls and full
hunting typography. The interface of the tool keeps its six languages, regardless of the ROM. The
missing names in a monolingual ROM come from the translated catalogue already provided with the tool
for preview. The names written in the game remain those of its own bank.

The detailed validations of PAL gifts, including backup and reloading, remain described in [previous
follow-up](PURIFICATION_GIFTS_FOLLOWUP_2026-11-02.md). USA and Japanese trials then validated the
two native acquisitions, rendering of the five dialogs, a backup in the game and reloading in a new
process, followed by refusal of a second gift. The preparation of QA cards and the limits of the
two text checks are detailed in [follow-up Dolphin of regional
gifts](REGIONAL_GIFTS_DOLPHIN_2026-11-03.md).

## Engine and image checks

The source suite executes 386 tests: 384 succeeds and two are ignored. Regional tests control among
other things the PowerPC instructions of patches, the return of native calls and the preservation of
registers, Japanese names, shops, exclusions, TM, bosses and profile migrations. The three tests of
the Rust codec also succeed.

The actual data matrix covers 18 configurations per region, 54 cases and 108 repeated patch
constructions. It rereads the final bytes and checks.

- the 3,355 sites of qualified and filled trainers;
- the 48 distinct dark families when this rule is active;
- starter stages, generation filters, boss rules and advanced modes;
- objects, shops, six stones and names in each native bank;
- 25 % and 100 % seed Shiny decisions, their final tables of 5,510 erector locations and 97 obscure
  lines;
- personalized gift thresholds 0/48 and their levels 17/88;
- nine real calls from the preview, each with 54 portraits and results of the two starters, four
  gifts and 48 Shadow Pokémon compared to the final data.

The three RVZs provided then followed the complete creation chain to ISO and then RVZ. The
recompression of each RVZ output is exactly the expected ISO. The copy mode on the three ISOs
returns their original SHA-256. Each source is recompressed after processing and remains unchanged.

The PAL regression reproduced in the same ISO l v0.13, seed `purification-rewards-1`, 25 per cent
Shiny rate, SHA-256 `da8e0d6883231b9d1cb5578895ca469db600de4894a86c0d97c2c960a22121a7`Eighteen DOL
compositions also have bytes and reports identical to the sources v0.13 archived.

## Starts in Dolphin

The three images were started separately with new memory profiles and cards, without importing
backup or personal SRAM. The native menu, the name entry, confirmation of new part and the beginning
of the introduction were searched in each region.

Seed: `regional-validation-1`. Team data were read after the owner's native generation and
allocation, without substitution of Pokémon, PID, script or savestate.

| Region | Rate tested | First starter | Second starter | Status observed in the team |
| --- | --- | --- | --- | --- |
| Europe | 25 %, linked to the seed | Mareep, level 26 | Totodile, level 25 | Two non-Shiny Pokémon, in accordance with the overview |
| USA | 25 %, linked to the seed | Mareep, level 26 | Totodile, level 25 | Two non-Shiny Pokémon, in accordance with the overview |
| Japan | 100 %, linked to the seed | Mareep, level 26 | Totodile, level 25 | Two Shiny, in accordance with the overview |

The species, levels, experience and four capacities correspond to the six records. The Shiny
statuses are calculated from their PIDs and final owner IDs. The temporary records observed before
transfer are not enough for this last control: the game still assigns their owner to them after the
generation routine.

In Japan, the introduction was also continued until the character was checked in front of the train.
The Pokémon menu displays the two starters, their Japanese names, levels and Shiny portraits. The
three sessions selected normally close with a zero return code. The fingerprints of the three
original RVZs and all files of the Dolphin Personal Profile, including the memory card and SRAM,
remain the same before and after the tests.

The harness uses the private copy Dolphin 2609a already used in previous trials, with its host input
patch and isolated profiles. This copy is not part of the distribution. Two first attempts to launch
PAL have blocked before the debugger initialization. They have been stopped and their retention of
the originals and personal profile has been verified. The following profiles activate logging.
USA/Japan trials disable the SDL DirectInput backend of the joysticks to avoid a documented blocking
of the host, while maintaining the keyboard and Dolphin test controller.

These tests validate start-ups and teams of new games. They do not constitute three complete parts,
nor a repeat of each evolution, purchase, capture and late combat in each region. The test on
another Windows PC remains a separate distribution check.

## Application and reproduction

Local and public Windows executables use the same engine. Each pass 156 Qt diagnostic states in the
six languages, two window sizes, settings, previews and exclusion dialogs. The archives are
extracted in a new path with spaces and accents for the start test. The Rust codec and editing
resources are checked. The public edition does not contain ROM, backup, Dolphin, or the game's image
and sound pack. Archives of previous versions are kept.

The profiles v0.13 keep all their options, including gifts and Shiny Pokémon. The new profiles are
configurations that can be used on all three regions. The report of a creation retains the regional
identifier and the exact fingerprints: a binary reproduction requires the same ROM, seed,
configuration and version of the engine.

Evidence containing game data remains private in `build/region-compat-2026-11-02/`: inventories,
REL/DOL qualifications, `matrix/`, `creation-validation.json`, captures and observations `runtime/`.
They are not embedded in the distributed sources or executables.
