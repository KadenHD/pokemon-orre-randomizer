# Version 0.15: files, selected starters and progress

The v0.15 adds Pokémon plugs, an HTML log, the manual choice of starters, a level curve and two game
rhythm settings. RVZ previews reuse their decompression and the recompression becomes cancelable in
the Rust and Python codecs. The three ROM revision 0 Europe, USA and Japan remain identified by
their full footprint.

Engine: `details-and-progression-v15`. **82 parameters, including 57 booleans**, remain in the
fifteen categories. The new game rules are neutral by default: starters drawn by the seed, curve
deactivated, EXP and purification to ×1.

## Choose starters

In **Advanced → Starters and gifts**, **First starter** and **Second starter** propose a searchable
list by name or national number of the Pokédex. **Draw with the seed** keeps the usual draw. It is
possible to fix the two starters or to fix one and draw its partner.

The manual choice takes precedence over the stage, the three-stage family filter and the power
comparison with the replaced Pokémon. It does not bypass the exclusions by species/type, the
generations, the legendary filter or the constraints of the duo: different families, lack of common
type and near power between the two Pokémon. If these rules do not allow the choice, the tool
indicates what needs to be corrected. It does not disable them alone. Shedinja remains excluded from
the selection to retain the existing protection.

Unchecking **Replace Umbreon** or **Replace Espeon** retains the original starter. Its manual
selector then has no effect. The starting levels remain 26 and 25, with the initial experience
adapted to the chosen species.

In the two randomized presets, the starters drawn by the seed remain by default the basic forms of
three-stage families. These two filters are independent and can be modified.

## Data sheets and verification of settings

The **Details** buttons of starters and preview encounters open a sheet in the language of the tool.
It contains.

- possible types, talents and final basic statistics;
- the abilities known for the meeting when their list is determined;
- Level learning and compatible TM;
- the complete evolution chain, with the conditions entered in this ROM.

These data come from the final bytes, after randomization and correction of evolution. They are not
deduced from a modern Pokédex. For example, Haunter indicates a level rise from 40 when the
adaptation of simple exchanges is activated. An evolution preserved by exchange is reported as
unavailable directly in Colosseum. An obscure must be purified before evolving. The talents
displayed are the possibilities of the species. The game still determines individual talent.

The names remain available in French, English, German, Spanish, Italian and Japanese. Readers use
the available native banks and withdrawal names for the languages missing from a monolingual ROM.
The source of these catalogues appears in the [notices tierces](../THIRD_PARTY_NOTICES.md).

**Check settings** launches the engine used by preview and creation, without publishing ROM.
Incompatibilities of filters, stages or torque are presented with possible corrections. A successful
check corresponds to the ROM, the seed and the current options. Any invalid change.

## Progressive difficulty

In **Levels and capture**, the optional curve replaces the global multiplier by three values, each
from ×0.5 to ×2.

| Plage | Level of the encounter in the original game |
| --- | --- |
| Start | 1-35 |
| Milieu | 36-50 |
| Fin | 51-100 |

The range is chosen before any level change. Therefore, it is not recalculated when a Pokémon rises
from 35 to 39, for example. These categories do not represent chapters or cities. The result is
rounded to the nearest integer and bounded between 1 and 100.

The order is **curve → boss bonus → choice of final stage**. Dark people receive the general level
change, but remain excluded from the boss bonus and the final stage filter. Starters and gifts keep
their level settings clean. Disabling the curve restores the global multiplier. Its three values can
remain stored without being applied.

## EXP and Heart Gauge

**Battle EXP gained ×** ranges from ×0.25 to ×5, with a step of 0.25 in the interface. The fight win
is changed after the native bonuses, with rounding to the nearest integer and a minimum of 1 for a
positive gain. The setting also concerns the EXP set aside for a dark one when the game allows. It
is not multiplied upon its release. The initial LEEXP and the Super Bonbons retain their original
treatment.

**Purification speed ×** ranges from ×1 to ×10. It multiplies the gauge decreases calculated by the
game, with its floor to zero. Increases remain normal. Nature and objects keep their native effects
before this factor. Final purification at the Relic and scenario conditions remain necessary.

Both values are **×1 by default**. To ×1, no additional QOL code is added. Functions and
instructions are qualified separately in the three executables. An unknown DOL or unexpected
instruction are refused. The added code shares the protected reservation of gift and Shiny
capability patches.

The [native contracts and PowerPC controls](QOL_NATIVE_2026-11-03.md) describe qualification,
records and limits. **Dolphin Europe confirms a 673 win with EXP ×2 became 1,346**, actually added
to the reserve of Blastoise (12,313 → 13,659). Lanturn receives the same calculated gain, then the
game normally refuses to reserve it as long as its gauge is too high. With gauge ×3, native
decreases -0.5 and -0.75 become -1.5 and -2.25, respectively: the gauges increase from 6,650 to
6,500 and from 800 to 575.

These cookies come from a real fight on a separate test card. The captures do not write EXP, gauge,
or combat result. The synthetic progression of the fixture, its consistency correction, and the
navigation shortcuts kept are reported in the native notes. The originals and the personal Dolphin
profile remain unchanged after normal closure of the two tests. **The new QOL USA/Japan routes
remain qualified by the contracts and the matrix, without any observation in this essay.** No level
rise, final purification, decrease by step or branch of the floor to zero has been observed here.
The matrix below remains a check of the data.

## Journal HTML

Each creation produces three separate files.

| File | Contenu |
| --- | --- |
| `partie.iso` ou `partie.rvz` | New Game Image |
| `partie.iso.json` ou `partie.rvz.json` | Technical report and reproduction |
| `partie.iso.html` ou `partie.rvz.html` | Journal readable, offline |

The journal consists of starters, Shadow Pokémon, gifts, trainers' teams, evolutions and TM. The sections
are initially folded to avoid spoilers. **Open journal** is available after creation. Its content
describes a new part with this configuration. It does not read an existing backup.

The application chooses the current language of the interface. The CLI offers `--journal-language
fr|en|de|es|it|ja`, with `fr` by default. This choice does not change the language of the game. HTML
is autonomous, without script, image or external resource. The source and destination paths of the
technical report are not included. Texts are escaped and a content policy limits active resources.

The creation refuses a name of ISO/RVZ, JSON or HTML already used. The files are published without
overwriting and a failure of publication removes the intermediate outputs from this creation.

## RVZ overviews and cancellation

A window keeps as much as possible an RVZ decompression in a private temporary folder, with its
isolated DolphinTool profile. Change the set or options re-use this ISO. The hashes of the source,
tool and ISO are re-validated. Horoding alone never prove the identity of the files. L的ISO is also
re-read after calculation to reject a change that occurred during the preview.

Change the source or tool, encounter an error, or close the window releases the cache. An active
calculation keeps its reading until it stops, then the cleaning takes place. No persistent game
cache is installed. Provide about 1.5 Gio on the temporary volume of the system for an RVZ preview.

The Rust codec checks the block cancellation of about 16 Kio. The Python reference also has its
breakpoints. An interrupted compression does not return a partial result. The context is specific to
the task, the old ABI is kept and an old DLL can use the cancelable Python fold. DolphinTool
conversions already monitored remain stopped by their owner in case of cancellation.

The real test of an RVZ USA is 4,328 s for the first preparation and 2,250 s for the next reading,
with only one conversion, the same ISO bytes and removal of the cache at the closing. These times do
not cover the complete calculation of the preview. A cancellation sent during the native compression
of 8 Mio returns in 0.094 s since the beginning of the call. The following recompression remains
identical to Python. These are local measures, without duration engagement on another PC.

## Profiles and validation of actual data

The profiles v0.14 are imported with the eight new neutral settings. Their footprint is checked
before migration. An old profile containing fields v0.15 or unknown is refused, even if it has been
re-embedded. No field is silently ignored. The re-export uses the full current format.

The private matrix covers six configurations per region, i.e. **18 cases and 36 repeated
constructions** recommended settings, two manual starters, a manual starter, a curve with boss,
EXP/jauge alone and a combination of additions with randomized types, talents, statistics and Shiny
Pokémon.

The controls reread the final bytes and verify, in each region.

- 386 cards, 184 edges of evolution and 3,947 apprenticeships;
- 3,355 records of trainers, 48 dark groups and their 108 variants;
- the 398 first-tier meetings, 2 185 second, 772 third and 145 boss bonuses in the combined case;
- the two manual starters, their derogation from the stage filter, and the refusal of an explicitly
  excluded manual species;
- the composition of the new EXP/jauge blocks with the other patches, and the identity of the entire
  REL when only the two QOL settings are added;
- the six languages of the newspapers, their closed sections and the absence of source/destination
  paths or external active resources.

Three combined ISOs have been created and verified in full. With the new neutral settings, the
comparison of the offsets, sizes and bytes of each patch with the v0.14 engine is identical in all
three regions. The copy mode produces zero patch. An additional check checks 2,508 non-obscured
final shapes per region, including five locations that cross the threshold only after the boss
bonus.

Migration tests include a profile actually exported by archived v0.14 sources. Cross-tests of the
codec, native/Python cancellation, content changes despite an identical size/date, cache corruption,
errors and competing players are also controlled.

These tests do not constitute a complete part or a validation of balancing, a physical console or a
second PC. The previous regional tests and gifts remain described in [validation
v0.14](REGIONAL_COMPATIBILITY_2026-11-03.md).

Evidence containing game data remains private in `build/v15-validation/`: `matrix-result.json`,
`extra-checks.json`, three ISOs, reports and newspapers. The cache/codec control is in
`build/v15-pipeline-validation/real-cache-and-codec-validation.json`. Europe native cookies, their
prior/after CK3s, test cards, conservation monitors and the explicit scope aggregate remain in
`build/v15-runtime/`. The balance sheet is `result.json`. USA/Japan maps prepared with the only PVs
observed after native Europe healing are offline test data, without claiming a cure played on these
two regions. The fingerprints of the six ISO/RVZ sources and the 46 files of the personal Dolphin
profile remain identical. These evidence files are not distributed.

## Validation of Windows executables

The two frozen editions pass **A total of 312 Qt states**: 156 by edition, in the six languages and
sizes 1040×800 and 680×540. These diagnostics cover the route, settings, exclusions and presentation
previews. The controlled binary and codec correspond to the distribution files.

The local executable was then used in its normal window with the US ROM, the seed `a0b4009878a88547`
and the manual starters Gengar/Steelix. The diagnosis first pointed to an impossible couple.
Choosing this eligible duo allowed to calculate the preview, to open the French file and then to
create a separate ISO with its JSON and HTML journal. An independent rereading compares the entire
ISO with the seven recalculated patches, as well as the records to the REL and DOL actually
extracted from this ISO. The obtained species and levels are Gengar 26 and Steelix 25. The French
newspaper corresponds to the report. Its rendering in all six languages keeps the sections closed
and does not take up any personal path. The source ROM and the original RVZ USA remain unchanged.

The two private temporary folders are empty after closing the application, without an orphaned
preview cache or intermediate output. Window captures and binary control are kept in
`build/v15-runtime/ui/`, with the balance sheet `frozen-creation-validation.json`. The 312 states
are recorded in `build/v15-frozen/staging-validation.json`. This creation uses EXP and purification
at ×1 and the curve is disabled: it completes the separate tests of these settings without
constituting a complete part or a test on another PC.

## CLI

```powershell
python -m colosseum_randomizer.cli original.iso duo.iso --seed ma-seed --starter-umbreon-species 94 --starter-espeon-species 208 --journal-language en
python -m colosseum_randomizer.cli original.iso rythme.iso --seed ma-seed --progressive-levels --early-level-multiplier 0.9 --mid-level-multiplier 1.1 --late-level-multiplier 1.25 --experience-multiplier 2 --purification-multiplier 3
```

The numbers of the starters are those of the national Pokédex, not the internal clues of the game.
Both examples create separate files and do not affect backups.
