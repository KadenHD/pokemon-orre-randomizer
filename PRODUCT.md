# Pokémon Orre Randomizer

<!-- impeccable:product-schema 1 -->

## Platform

Desktop. Python/Qt native application, Windows first. The engine does not depend on Windows. The
platform catalog of the skill doesn't cover Qt desktop: system conventions and Qt controls govern
this surface, without transposing a web page into a window.

## Users

Players who have an unmodified image of Pokémon Colosseum or XD and want to create their own randomized game,
without extracting the game or using commands.

## Product Purpose

Choose a game on the home screen, then an ISO or RVZ, a seed, rules and a destination. Produce a new image
verified with its reproduction report. Colosseum and XD are available, with shared navigation and game-specific rules.

## Capabilities and Constraints

- ROM GC6P01 Europe, GC6E01 USA and GC6J01 Japan, revision 0, each identified by full hash. ISO and
  RVZ formats.
- Supported trainer Pokémon, starters, and gifts. Families distinct between starters,
  Shadow Pokémon and gifts when the rules allow, and accessible evolutions.
- 83 parameters, including 58 booleans, in fifteen categories. Three starting points: Pokémon +
  capabilities, Pokémon only, Unchanged copy.
- By default, starters are base forms from three-stage families. Advanced choice of evolution stage and
  independent filter. Profiles 0.5 to 0.8 migrated without changing their hashes.
- Manual choice of zero, one or two starters by name or national number of the Pokédex, from a
  searchable list. The manual choice takes precedence over the stadium, the three-stage family and
  the individual power, but respects the exclusions, generations, legendary and constraints of the
  duo. A disabled replacement retains the original starter and ignores this choice.
- Explicit exclusions by species and type of origin, with searchable selection and names in all six
  languages. Apply to all replacements.
- Themes of non-obscured teams and final forms from a chosen level. Options disabled by default,
  hidden preserved. The bonus level of the bosses is used and the teams sharing recordings are
  processed together.
- Step Settings divided into Pokémon Configuration and Overview, with common seed and Profiles menu
  in the header. Simple and Advanced keep the same options. Advanced categories move from a column
  to a selector when space is missing. Only one area of content scrolls through the active view,
  with persistent navigation and protection against unintentional value changes to the wheel.
- Search for Advanced settings on labels, aids, categories and choices in the current language,
  without accents and with usual synonyms. The choice of a result joins the field and its focus
  without changing the options.
- Resetting the current category to zero only, to the reference named **Pokémon + moves** (office
  preset). Seed, paths, other categories and imported profiles remain distinct from this reference.
- Creation summary based on actual rules: manual choices, constraints, rates and factors actually
  active. Values stored but deactivated are not announced as applied. No random drawing is revealed
  in this summary.
- An preview of both starters, the 48 Shadow Pokémon and the four gifts by the creation engine:
  the FR/EN/DE/ES/IT/JA names, the available levels and the portraits of the ROM, without publishing
  the ISO. The explicit calculation, the animated and cancelable loading, the result shared between
  three tabs, the "Update Preview" status, the update after changing the ROM, the seed or the
  options. The lists compare the original names to the replacements, with search and counter. A " ?"
  precedes the calculation of the unknown species and a visual roulette accompanies the calculation.
  Event gifts remain subject to their conditions of obtaining.
- Sheets accessible from the starters and meetings of the preview: types, possible talents,
  statistics, known abilities, learnings, TM and complete evolution chain after the final bytes of
  the ROM. Text and names in the six languages, without changing the language of the game or
  announcing the individual talent as determined.
- Session cache for the RVZ preview: a single ISO temporarily decompressed per window, reused after
  source/ISO/tool fingerprint control. Invalidation of source/tool change, after error and closure.
  No persistent game cache.
- HTML log produced next to each ROM, folded sections for spoilers: starters, Shadow Pokémon, gifts,
  trainers, evolutions and TM. Language of the interface or choice CLI among the six languages,
  default French in CLI. Offline playback without script or external resource. Source/destination
  paths of the technical report are not included. None of the three existing output files is
  replaced.
- JSON profiles can be shared without ROMs or personal paths, imported with version and print
  validation. v0.13.0 imports previous profiles with access to disabled event gifts to preserve
  their data. Profiles 0.11 and 0.12 also retain the link of Shiny Pokémon to the seed.
- Event gifts available from [Eagun] to Relic Stone: default thresholds of 10 and 25 purified Shadow Pokémon,
  levels 30 and 45, all adjustable. Option activated in both randomized modes. The scenes of
  introduction to purification must be completely completed. Its presence becomes exclusive between
  home and sanctuary, with only one gift and backup discount. The five dialogues follow the language
  of the PAL, USA or Japanese game. The interface retains its six languages.
- Custom shiny rate from 0 to 100%, to 5% by default in the two randomized presets of the office.
  The option "Link the Shiny Pokémon to the seed", checked by default and dependent on this
  customization, sets the status by starter, gift, dark ID or trainer location. The preview shows
  the exact status for a new part, even at intermediate rates, with authentic portraits and a red
  star for the Shiny Pokémon. The same species may have different status according to the encounter.
  The rate expresses a probability, without quota on the results.
- Unchecking the link keeps the draw in play at the chosen rate. The profiles 0.5 to 0.10.1 are
  migrated with this link disabled to preserve their outputs. Nature, genre, complete PID and IV
  remain native. The old dark PIDs are reused and the already generated Pokémon are not removed by
  lot. The previewed result assumes a new part.
- Duo de starters forced by families, types, power and basic forms. Rules independent of the dark
  bosses, with overall attribution of the 48 families.
- Optional progressive difficulty by levels of origin 1–35, 36–50 and 51–100, from ×0.5 to ×2 for
  each range. It replaces the global multiplier, precedes boss bonuses and final stage control. It
  does not correspond to chapters and does not change starters/gift levels.
- EXP of combats ×0.25 to ×5, by step of 0.25. Decrease of the Heart Gauge ×1 to ×10. Both remain at
  ×1 by default. The native treatment keeps the initial EXPP and the final purification to the
  Relic. The contracts and the validation status to the execution are distinct in the notes v0.15.
- Attacks and learnings, talents, statistics, types, objects held, species filters, levels and
  capture configurable separately, with special data protections.
- TM and compatibilitys, chests, six ordinary stocks and teams of seven identified leaders.
  Conservation of HM, keys and stones. Non-obscured boss rules preserve the dark draw.
- Codec LZSS accelerated in Rust in executable. Same output as the Python reference. Cooperative
  cancellation during recompression in both paths, task specific context and previous ABI retained.
- Processing is local and requires no account. ROMs stay on the user’s computer.
- Interface in French, English, German, Spanish, Italian or Japanese depending on the language of
  the system, with manual choice stored and immediate change without changing the configured part.
- ISO processed directly. External DolphinTool is required to convert RVZs. The field appears at
  input or output depending on the format and shares the path.
- No ROM or Dolphin installation enters local distributions.
- The user has explicitly chosen the desktop application and wants an open source project.
- The interface and the report distinguish technical validation and complete part played.

- Direction chosen: original Colosseum menus, composition C (compact assistant).
- The local edition features a pack of images, icons and exported sounds from the ROM. The interface
  starts without ROM or cache.
- Track music and menu sounds have independent commands, activated at the first launch if available.
  Choices remain stored and do not change profiles.
- The compact names of eleven stones can be spaced, with the five native translations retained. The
  old profiles keep the correction disabled.

## Operating Context

Occasional session, on computer: a resizeable window, native file selectors, readable progress,
cancellation and recoverable errors. The source must never become a destination. An existing output
must not be replaced.

## Evidence on Hand

The v0.16 is a batch of navigation, documentation and validation. It keeps the engine
`details-and-progression-v15`, the 82 fields and profile diagram 1. The profiles v0.15 are
recognized separately and imported without changing their values. An archived export v0.15,
including the eight recent non-neutral settings, is used to control this compatibility. The six
compared configurations in three regions and the three combined images remain identical to the
v0.15. 449 tests and 336 diagnostic states of the two executables are checked. The 15 Dolphin steps
on Europe, USA and Japan confirm the step with zero floor, the single reserve release, the final
purification, the normal x2 exp with level rise and the dark x2 exp are stored. The three sessions
normally close. Original ROMs and personal backups pass the fingerprint control. The prepared maps,
inherited statistics and the door shortcut delimit this target path. [Validation details
v0.16](docs/DESKTOP_V16.md)

La v0.15 uses the engine `details-and-progression-v15`. The matrix on the three real ROMs covers 18
configurations and 36 repeated constructions. It checks manual starters, filters, levels, boss
bonuses, EXP/jauge composition, 386 plugs, 108 obscure variants and six log languages per region.
Copy mode does not add any patch. The new neutral settings exactly reproduce the engine patches
v0.14 A real RVZ decompression is reused and then removed. A native cancellation during compression
is observed in 0.094 s. Originals and Personal Dolphin profile remain unchanged. Dolphin Europe
confirms EXP ×2: native gain 673 became 1,346, actually added to the reserve of Blastoise, and
retained refusal for Lanturn still too obscure. Jauge ×3 confirms decreases 6,650 → 6,500 and 800 →
575 in combat. Both tests close normally, without changing the originals or personal profile. These
new courses QOL USA/Japan remain qualified by the contracts and matrix, without any observation in
this trial. No level rise, final purification, decrease by the step or branch of the floor to zero
n-y was observed. The preparation of the test cards and the limits are shown in
`docs/DESKTOP_V15.md` . The technical matrix is not a complete part.

V3 engine and local tests. ISO reconstruction tested under Dolphin, purchase of a Moon Stone The
evolutions and the entire scenario were not all played individually. v0.3 There are 111 Python tests
and three Rust tests passed. Its executable creates an ISO identical to that of the sources. A cold
start in a new Dolphin part confirms the two starters, their level and their capabilities. The fight
and the late gifts of this version remain to be controlled manually. v0.4 add the TM, chests,
inventory and boss: 147 Python tests and three Rust tests passed, ISO reproducible identical between
sources and executable, RVZ verified after recompression. Dolphin confirms the names and
descriptions of the TM on a backup copy. Buys, chests and boss fights remain to be covered in this
version. v0.5 adds profiles, the duo of starters and the rules of boss Shadow Pokémon: 187 Python tests and
three Rusts pass. The import in the executable reproduces exactly the ISO of the sources. Dolphin
starts the images and loads a copy of the memory card. The new combat and acquisition routes remain
open. The preservation and closing details Dolphin are shown in `docs/DESKTOP_V05.md`.

The v0.11.0 uses the engine `seeded-shiny-status-v12`. Automated tests control the decisions by
seed, native tables, mixed previews and translations. Six comparisons of the unlinked mode, at 0, 25
and 100%, with and without gift capability fixes, keep the bytes of the v11 engine. These controls
do not constitute Dolphin validation of this evolution nor a complete part of the scenario.

## Product Principles

- A seed and the same rules reproduce the same data.
- The actions name their effect and the file concerned.
- Errors explain how to resume.
- Game data and backups remain with the user.
- The native path of selection, configuration and creation takes precedence over decoration.

