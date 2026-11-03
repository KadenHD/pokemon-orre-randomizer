# Application v0.5: boss profiles, starters and Shadow Pokémon

Version of October 31, 2026. Engine `starter-shadow-boss-rules-v7`. 59 parameters, including 51
booleans, in the fourteen native categories.

## Shareable profiles

Importing or exporting near the seed field works without selecting ROM. The JSON contains all the
rules, the exact Seed, the application and engine versions, the profile format and the public
identity of the compatible ROM. No path of ROM, output, Dolphin or backup is saved. The path of the
form does not change to import. The entire file is checked before changing the form. A limit of 64
KB, strict types and rejection of unknown, absent or repeated keys protect incorrect files.

The SHA-256 print of the content detects an accidental modification. This is not a signature of
authenticity. The profiles of another version are refused with an explanation. No silent migration
changes the hashes. An export refuses an existing file. The CLI accepts `--profile ma-partie.json`.
The options explicitly indicated and `--seed` may overload it.

## Duo de starters

Four boxes apply to randomized starting species.

- `starter_balance_pair`: difference in total statistics not more than `max(50, 20 % du plus
  faible)`, based on final statistics.
- `starter_distinct_families`: different families of evolution.
- `starter_complementary_types`: no type shared, from the final types. This is not a guarantee of
  coverage of all the opposing types.
- `starter_base_forms`: no preevolution in the native graph. Non-evolutionary species are eligible,
  including legendary authorized species.

The generation/legendar filters and the overall power preference remain respected. A partner whose
randomization is disabled does not change and serves as a constraint to the second. If no couple is
possible, the creation fails with an explanation and no output. Eligible couples are listed, then a
couple is chosen uniformly with the seed. No arbitrary limit of attempts can reject a couple yet
possible.

The 26/25 levels and instructions are retained. The two EXPs follow the final growth group. Attacks
are selected after the species. The other gifts keep their circulation independent. These four
new boxes remain disabled in the CLI base values, to preserve the old uses. The first three are
activated by "Recommended Rules".

## Shadow Pokémon bosses

The seven leaders already identified use seven distinct dark groups: 19, 21, 23, 34, 38, 43 and 44,
in 16 appearances of their variants.

- `boss_shadow_legendary_mode`: global filters, retain the legendary original status, or exclude the
  legendary/fabulous from these seven groups.
- `boss_shadow_power_mode`: follow the overall preference, impose a strict window of `±max(50, 20 %
  du total natif remplacé)`, or ignore this preference among bosses. The other filters remain
  applied in all three modes.
- `boss_shadow_min_bst`: minimum total **natif**, before any optional redistribution of statistics.
  Zero means no minimum.

The 48 families are assigned simultaneously by matching when singleness is activated. A family
useful to a boss can therefore not be consumed without the possibility of reassignment by a previous
ordinary draw. The strict constraints are never relaxed. A general preference withdrawal of power
required for singleness is recorded in the report.

Global filters remain a priority: keeping a legendary while prohibiting them produces an explicit
error. Levels, obscure identifiers, capture rates, number of Pokémon and scripts do not change.
Existing level/capture settings remain independent. All appearances of the same obscure receive the
same species. The two reinforcement/variety options of non-obscured companions then apply without
touching these hashes.

By default, these three specific settings are neutral: the operation of the Shadow Pokémon of v0.4 is
preserved. They gift't know if the Shadow Pokémon are randomized.

## Validation technique

196 Python tests and three Rust tests passed. The tests added cover the profiles and their
transactional import in the form, theEXP and attacks after selection of the duo, the final
properties, the strict filters, a match with reassignment, the seven boss groups and their aliases,
the uniqueness of the 48 families and the authorized bytes. Nine tests of the Dolphin monitor also
check the isolation of the paths, the tracking of personal files and the recording of the native
code of the process. The original sources remain read without writing.

The local test report records the validation seed.

| Test | Result |
| --- | --- |
| Preset recommended from ISO | 10,80 s. ISO `648cc8c0744c87fce40a7d4dbdd3f6f95f8df29bc48415ee33507cb5d1894b35` |
| Profile import and reconstruction | 11.56 s. Whether or not ISO |
| Import to Windows executable, then create 100% | 10.62 s. Whether or not ISO |
| All changes disabled | 7.97 s. ISO strictly identical to the original |
| RVZ → RVZ, boss legendary status preserved, near power, minimum 450 and basic starters | 24.12 s. ISO return verified `e3bf0206a25701bd17a04d8f51fb1b96b6560bbab373a82949a94566dad21adc` |

The expected recommended duo is Seadra level 26, TSB 440, EXP 17,576, and Electabuzz level 25, TSB
490, EXP 15 625. Types do not overlap. Deviation 50 is less than tolerance 88. These values are
derived from the final data.

QA reports and catches remain in `build/v05-qa/`] and `build/dolphin-validation/`, out of
distribution. Technical verification does not certify a fully played scenario. Dolphin observations
are recorded separately from expected values.

The publication procedure verifies the integrity of the archives and the absence of ROM, backup or
emulator. It launches tests from a source archive extracted without the dump of the game. Cases
requiring local data or a compiled codec are then ignored. The result specific to the reconstructed
archives is recorded after execution of `scripts/verify_release.py`.

## First Dolphin Pass and Conservation: Historical

During the first pass, two cold starts were made in profiles under `build/v05-qa/`: an empty card
for recommended ISO, then a copy of the personal card for `gameplay-check.iso`. The latter activates
the obscure rules of boss and removes the protection of the care sold, in order to prepare a shop
check. The loading of the copy and the movements from the PC, outside and towards the bridge were
observed. The catches are in `evidence/`. No RAM status of an old ISO was loaded.

At this initial stage, the new starters, purchases, safe collection, purification followed by a TM
and fights of the seven bosses had not yet been checked in the game. Their data had only been
checked automatically. The first Dolphin launcher ended with code 0. The second returned 1 after
closing, without a visible diagnosis and with an empty journal. The cause of this closure status is
not established. This control is not valid for a full session. The randomizer does not launch
Dolphin into the user's path.

After the tests, the ISO/RVZ sources, the 2,011 files of `game/` and the personal memory card
`MemoryCardA.EUR.raw` retained their fingerprints. A personal Dolphin instance was already opened
before the tests. Among its 20 files inventoried, `Config/Qt.ini` and `GC/SRAM.raw` changed during
the session. This pass did not establish the author of these two scripts. Their current condition
was not replaced to attempt a restoration. The personal game memory card remains the same as the
original copy. Detailed manifests remain local and are not distributed. These historical
observations are not replaced by the following tests and no restoration is claimed.

## Functional follow-up of 31 October 2026

The [Dolphin report dated](DOLPHIN_VALIDATION_2026-10-31.md) now distinguishes the expected values,
private preparations and observed native actions. A new part actually creates the starters Seadra 26
and Electabuzz 25. In a prepared copy, Onix 39 is purified, learns Tunnel by CT05 and then evolves
into Steelix at level 40 after a Super Bonbon. Learning, evolution and the four capacities retained
are checked in memory and on the screen.

The purchase of Accuracy+ at Pyrite Town debits exactly 950 and adds a copy. The tested chest gives
three Defense+ and activates its native flag. A true capture of Piloswine obscure level 35, group
19, adds a Pokémon in an empty PC box: occupation 14→15, Master Ball 1→0, capture flag 2144: 0→1.
The Pokémon already present in the PC remain identical. These results do not come from an injection
of rewards or captured Pokémon.

The dated report refers to the status of the seven boss teams, the Dolphin closures and the final
conservation control. It describes the test team at level 80, accelerated access to the scenes, the
pre-zeroing of a capture flag on a copy and the separation between the official emulator and his
private diagnostic copy. These tests do not certify a complete part, normal balancing or physical
console operation.

## Searching for formats

- [Fields and starters selection](reverse-engineering/V05_STARTERS_RESEARCH.md)
- [Inventory and rules of dark bosses](reverse-engineering/V05_SHADOW_BOSS_RESEARCH.md)
