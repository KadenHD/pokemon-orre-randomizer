# Changelog

## 1.2.16

- Fix an intermittent freeze after generating an XD preview. The shared preview
  now keeps the interface responsive while its background thread shuts down.
- Limit the extracted source archive's test run and report the last test output
  if it times out.
- Compare Colosseum and XD side by side in the README and slow down the
  motorcycle showcase.

## 1.2.15

- Show Duking’s requested Pokémon, Poké Spot, encounter frequency and reward
  together in XD’s preview and journal.
- Align Pokémon names and trade details across both columns of XD’s gift preview.
- Distinguish encounter frequency from wild shiny odds in the Simple settings.
- Mute the desktop diagnostics and isolated Dolphin validation runs.

## 1.2.14

- Add an optional, independent wild shiny rate for XD's three Poké Spots.
  Each new encounter keeps its result on the field, in battle and after capture.
  The presets and older profiles retain the original odds.
- Match the Phenac boy's impression of Justy to Justy's randomized team.
- Improve the placement of short starters in the Outskirt Stand sidecar.
  The prerecorded opening movie retains its original footage.

## 1.2.13

- Show the randomized encounter on the field at all three XD Poké Spots.
  The field and battle palettes use the same native shiny roll.
- Synchronize XD's Gateon Port Shadow encounter, Miror B.'s lighthouse dancers,
  and Wakin's companion and dialogue on the S.S. Libra and at Cipher Key Lair.
- Synchronize Colosseum's starters at the Outskirt Stand motorcycle arrival,
  Miror B.'s Pyrite dancers, Duking's gift scenes and Eagun's partner.
- Show the actual form and shiny palette of Colosseum's Mt. Battle reward.

## 1.2.12

- Fix XD's Gateon Port sailor dialogue so the stone and shard explanations
  refer to Eevee in general when the player starts with a different Pokémon.

## 1.2.11

- Update trainer dialogue and Shadow Pokémon reports to match randomized teams
  in Colosseum and XD, including Mt. Battle, rematches and the Phenac Gym.
- Adapt remarks about type themes, moves and abilities when the randomized
  battle changes them.
- Keep scripted references to XD's starter, tutorial Teddiursa and final Shadow
  Dragonite in sync with the chosen species.
- Shorten rewritten lines and use the names in the game's selected language.

## 1.2.10

- Fix shiny status for XD's Mt. Battle prizes and NPC trade rewards so the
  Pokémon received in-game matches the preview when shininess is tied to the seed.
- Preserve the trainer ID assigned by XD when generating these gifts.
- Keep Colosseum profiles and creation reports from 1.2.9 importable.

## 1.2.9

- Match the Pokémon model, cry and localized dialogue in Colosseum's Pyrite
  rescue and gift scenes to the Pokémon that replaces Plusle.
- Keep oversized species out of the Plusle gift pool so they fit the scripted
  scene more reliably. The rule also applies with family diversity enabled.
- Show the randomized species, cry and localized dialogue in the Mt. Battle
  presentation for Colosseum's Ho-Oh prize.
- Keep profiles and creation reports from previous versions importable.

## 1.2.8

- Restore missing accents in Pokémon names in previews and Pokémon sheets,
  including the names shown on evolution paths.
- Display readable, localized evolution item names with sentence casing in
  both games.
- Name XD's Sun Shard and Moon Shard in all six interface languages instead of
  showing numeric item labels.

## 1.2.7

- Show original ability and move descriptions in Pokémon sheets for both games
  in English, French, German, Spanish, Italian and Japanese.
- Give Shadow moves localized badges with white text in Colosseum and larger
  black text in XD. Center all move badges beside their name and description.
- Show Shadow Rush separately from the regular moves in Colosseum Shadow Pokémon sheets.
- Restore missing accents in move names when they match the localized spelling.

## 1.2.6

- Show original Colosseum and XD type badges on Pokémon sheets and next to
  moves, level-up moves, and compatible TMs in all six interface languages.
- Display move names with only the initial letter capitalized in scripts
  that use letter case.

## 1.2.5

- Remind players to use a copy of the game they are legally entitled to use on
  the ROM screen for Colosseum and XD.
- Add an author credit on Home that opens KadenHD's GitHub profile.
- Clarify the ROM policy near the README downloads and link to the notices for
  the bundled game logos, artwork, and music.

## 1.2.4

- Play the Pyrite Town theme on Home and each game's own title theme in its
  workspace. One saved Music toggle applies to all three tracks, independently
  of menu sounds. The bundled audio loops offline and is matched in level.
- Keep the game cards neutral when returning to Home from either game. Hover
  and keyboard focus still highlight the active card.
- Update the user guide, release notes and README capture for the new behavior.

## 1.2.3

- Replace enlarged 96 × 32 disc banners on Home with unchanged, transparent
  English game logos: 1280 × 543 for Colosseum and 1280 × 565 for XD.
  Bundle the verified originals and source metadata for offline use, preserve
  their proportions at normal and high display scaling, and keep the small
  disc banners for workspace headers and as fallbacks.
- Refresh the README's game selection screenshot with the 1.2.3 home screen.

## 1.2.2

- Keep creation details hidden after input-validation errors in both games.
  A shared creation-log component now controls initialization, collapsing,
  translation and visibility. It appears only on Create after a real generation
  starts, and keeps its log after completion, failure or cancellation.
- Reset the previous log for a new creation attempt and hide it on ROM/Settings.
  Both games expose details before the first worker progress update.
- Align the invalid-input message and restore the same ROM-page footer help
  when the Colosseum interface pack is available.
- Add regressions for both games, all six languages, preflight validation,
  creation progress, failure, cancellation and navigation.

## 1.2.1

Development tag; publication was held for the creation-details correction and
is superseded by v1.2.2. Its interface changes are included in v1.2.2.

- Unify shared Colosseum/XD wording, preset explanations, category help,
  starter labels, preview actions and applied-settings summaries in all six
  interface languages. Shared copy and metadata now have parity regressions.
- Show XD's native Shadow, gift and Poké Spot rosters before calculation, with
  unknown replacements where appropriate. Keep multilingual search available
  before calculation, and use the same loading animation, retry/cancel states,
  seeded shiny legend and single-click Pokémon sheets as Colosseum.
- Add XD's duplicate-family warning, original-ROM comparison after report
  import, creation-stage log and safe reuse of a verified preview patch plan.
  Both previews run through the same background worker and reject stale results.
- Preserve game-specific explanations for XD's protected Lugia, Poké Spots,
  tutorial and trade encounters, and Colosseum's starter pair and event gifts.
  These interface changes do not change the seeded randomization rules.

## 1.2.0

- Both XD desktop presets now replace Hordel's Shadow Togepi by default.
  Its purified replacement remains eligible for the trade, including after
  evolution. The advanced toggle and imported profile choices are preserved.
- Added an optional XD Shadow shiny unlock using the chosen rate and a stable
  seeded decision for each of the 83 Shadow IDs. Both randomizing presets
  enable it at 5%. The starter and ordinary gifts retain their existing draws;
  wild Poké Spot odds remain native.
- Use the player SID/TID for Shadow ownership before capture so capture and
  purification retain shiny status. Previously generated Shadow PIDs remain
  unchanged. Preview portraits and sheets use the seeded status.
- Added the option and scope explanations in all six interface languages.
  XD engines v3–v7 import without enabling the new unlock. The XD engine is
  now `xd-story-sha256-v8`.
- Enabled tutorial Teddiursa randomization in both XD desktop presets. The
  advanced toggle, unchanged-copy mode, legacy CLI defaults and imported
  profiles retain their existing behavior. Tutorial safety checks still apply.
- Both XD desktop presets draw regular Poké Spot encounters from the full
  supported Pokédex, respecting species filters and power matching. Slots keep
  their native levels and encounter rates. Duking's three rare-slot requests
  remain distinct and obtainable.
- Synchronize Duking's checks, dialogue and preview with those requests, even
  when gift rewards are preserved. Handle localized species-name swaps without
  accidentally rewriting names already replaced.
- Added a six-language advanced toggle for the full Pokédex pool. Older XD
  profiles retain their native three-species shuffle and saved choices. Existing
  draw domains remain unchanged when importing these profiles.
- Added authentic gameplay examples and advanced-setting screenshots to the
  README, with provenance and checked packaging allowlists.

Development builds 1.0.1 and 1.1.0 were not published as separate releases;
their changes are included in 1.2.0 above.

## 1.0.0

- First stable release for Colosseum and XD, with the shared three-step desktop
  workflow, six interface languages and the complete verified interface pack.
- Aligned the two randomizing presets: Pokémon-only now retains the same power,
  starter-pair and boss-diversity rules as Pokémon + moves. XD enables the same
  boss-diversity default. Moves, TMs and item randomization remain the distinction
  between modes; game-specific protections remain in place.
- Preserved existing CLI defaults and imported profile values. Added compatibility
  checks against profiles exported by the published RC2 source distribution,
  and retained RC1/RC2 import support.
- Reorganized the English README with the Orre logo and real application captures.
  Added user, compatibility and validation guides for both games; clarified the
  scope of historical reports and native testing.
- Included hash-verified documentation screenshots and compatibility fixtures in
  release archives. Stable releases provide the Windows setup EXE, portable ZIP,
  source ZIP and checksums. Earlier prerelease tags and assets are preserved.

## 0.21.0rc2

- Fixed XD battle EXP and purification hooks being placed inside the startup
  stack. Added native arena-floor checks for European, US and Japanese discs.
  The corrected engine still imports RC1 profiles without changing their settings.

- Public Windows and source distributions include the complete verified interface
  pack: game logos, background, cursor, menu sounds and music. Packaging rejects
  undeclared media and verifies every recorded asset hash.

- Home-screen audio controls and language selection use a silver and graphite palette.

- Added the approved metallic Orre logo to the home screen. Local and public
  builds include the original transparent logo and its provenance.

- The game selector uses a neutral black-to-gray background.

- The game pack uses the original English Pokémon XD banner on the home
  screen and XD workspace header.

- Reworked the home screen with two game choices using their own menu colors,
  a shared layout and whole-panel activation. Choices stack in compact windows
  and support keyboard navigation and all six interface languages.

- Renamed the Python package to `orre_randomizer` and the shared Rust codec to
  `orre_lzss`. Source launch commands, build scripts and release checks use the
  new package. Existing installed `colosseum-randomizer` commands remain aliases.
- Application preferences now use the Orre name and import existing Colosseum
  preferences once, preserving newer choices.

## 0.21.0rc1

- Added a dedicated Pokémon XD wizard for European, North American, and Japanese revision-0 discs.
- Added seeded XD options for the starter, trainers, Shadow Pokémon, gifts, Poké Spots, trades,
  moves, items, and progression. XD keeps its own story requirements and Shadow shiny rules.
- Added XD encounter previews, profiles, creation reports, and ISO or RVZ output.

## 0.20.0

- Pokémon Orre Randomizer opens on the choice of the game. Choose Colosseum to open the wizard. XD is marked as planned.
- Windows distributions use `OrreRandomizer.exe` and the repository name `pokemon-orre-randomizer`.
  GitHub Actions builds and verifies the release archives for version tags.

## 0.19.0

- The Duplicates tab lists starters, Shadow Pokémon, and gifts that share an evolution family.
- The Profiles menu allows you to resume the seed and settings from a creation report and compare
  the selected ROM to that of the report.

## 0.18.4

- Center the clear button in search fields.

## 0.18.3

- ROM creation can reuse a preview plan when the ROM hash, seed, and settings match. The generated ROM is always fully verified.

## 0.18.2

- The Poké Ball selection marker is aligned with the steps and preset wordings, with an additional space
  before text.

## 0.18.1

- The arrow in the Profiles menu is aligned with its wording.

## 0.18.0

- Randomized presets seek different families of evolution between starters, Shadow Pokémon and gifts.
  Exclusions, manual choices and strict constraints remain the priority. The creation report
  indicates the remaining duplicates.
- The old profiles retain their draw. The new preference is deactivated at their import.

## 0.17.4

- The overview of starters, Shadow Pokémon and gifts displays the names with an initial capitalization. A
  small red star in superscript indicates the Shiny Pokémon.

## 0.17.3

- The names of the Pokémon begin with a capital in the sheets. The Shiny star appears as an
  superscript.

## 0.17.2

- A red star after the name indicates the Shiny Pokémon in their sheet.

## 0.17.1

- The Evolutions tab shows the portraits and conditions of each stage, including for families with
  several branches. The portraits come from the ROM and resume the Shiny status when it is known.

## 0.17.0

- The two randomized presets activate the Shiny at 5% per encounter, with a result set by the seed.
  Their descriptions are displayed directly under the chosen mode.
- The preview shows the original encounters and marks a "?" the species that remain to be drawn. The
  portraits and names scroll during the calculation, then the list displays the final drawing.
  Search by name or number remains available.
- The cards adopt the frames of the game, with a portrait, stats bars and tabs for summary,
  abilities and evolutions.
- The Profiles menu joins the language and audio commands. The Create step consolidates the summary
  under Applied Settings and displays a DolphinTool field for an RVZ output. The path is shared with
  the ROM step.
- The 0.16.0 and 0.16.1 profiles retain their import settings and drawings.

## 0.16.1

- Clicking on a line of the Shadow Pokémon or Gifts tabs opens the Pokémon details obtained. On the keyboard,
  the Enter key opens the selected line.
- The filter distinguishes "All Pokémon", "Shiny only" and "Nonchromatic only". It appears when the
  preview knows the Shiny status.
- The preview recalls the original rates for starters and Shadow Pokémon captured. The profiles v0.16.0
  remain importable.

## 0.16.0

- Search for settings in Advanced mode in translated terms, aids, categories and choices, with
  normalization of usual accents and synonyms. A result joins the field without changing its value.
- Resetting the current category to preset values **Pokémon + moves** without changing the seed,
  paths or other categories.
- Summary of the actual rules in the step Create, with manual choices, rates and active factors,
  without revealing random draws. The detailed part scrolls at the opening to make its first lines
  visible.
- Shortened cancellation message. Updated contribution documentation for the 82 parameters and six
  languages.
- Strict import of profiles v0.15: even 82 fields and same values, without drawing migration. The
  engine `details-and-progression-v15` and profile diagram 1 remain unchanged.

The [notes v0.16](docs/DESKTOP_V16.md) record 449 tests, binary regression v0.15 in the three
regions and 336 diagnostic states of the two executables. The 15 successful Dolphin steps on Europe,
USA and Japan cover the step with floor at zero, single reserve release, final purification, normal
EXP ×2 with level rise and EXP ×2 set aside. The three sessions close normally. The fingerprint
checks confirm the integrity of the original ROMs and personal backups.

## 0.15.0

- Pokémon sheets in the overview: final properties of the ROM, known abilities, learnings, TM and
  chain of evolution, in the six languages. The talents displayed are the possibilities of the
  species. Individual talent remains attributed by the game.
- Manual choice of the first and second starter, by national name or number. Only one can also be
  fixed. The choice replaces the filters of stage, three-stage family and individual power, while
  preserving the exclusions, generations, legendary and duo rules.
- Optional progressive difficulty: three multipliers for the original levels 1–35, 36–50 and 51–100,
  applied before the boss bonuses and control of the final forms.
- EXP combat adjustable from ×0.25 to ×5 and decrease of the Heart Gauge from ×1 to ×10. ×1 by
  default. Qualified native and compound patches on all three regions. Final purification with Relic
  remains necessary.
- Local HTML log created next to the ROM, with folded sections for spoilers. Interface language, or
  `--journal-language` in CLI. No source/destination path or external resource in this log.
- Checking settings before creation via the preview engine, with recoverable errors without
  publishing ROMs.
- Reuse of a temporary RVZ decompression per window for successive previews, with revalidated hashes
  and cleaning when closing, changing source/tool or after error.
- Co-operative cancellation during recompression LZSS Rust and Python. Identical output without
  cancellation. Former ABI of the codec retained.
- 82 parameters, including 57 booleans, in the fifteen categories. Strict import of profiles v0.14
  with new neutral settings. Complete comparison of patches with the engine v0.14 archived
  successfully in the three regions.
- Corrected documentation: Randomized presets offer basic starters at three stages by default.
  Cancellation no longer waits for the end of a LZSS member.

Engine: `details-and-progression-v15`. The real data checks cover 18 configurations and 36 repeated
constructions. In Dolphin Europe, EXP ×2 produces a real gain of 1,346 instead of 673 in the reserve
of an obscure. The native refusal of another obscure still too closed is preserved. Jauge ×3
confirms 6,650 → 6,500 and 800 → 575 on two reductions of combat. Originals and personal Dolphin
profile remain unchanged after normal closing. These new QOL routes were not played on USA/Japan.
Level rise, final purification, step and gauge floor at zero remain unobserved here. These controls
do not certify a complete game.

[Operation, validation and limitations v0.15](docs/DESKTOP_V15.md).

## 0.14.0

- Support for ROM Europe `GC6P01`, USA `GC6E01` and Japan `GC6J01`, revision 0, in ISO or RVZ
  format. Strict header identification and complete SHA-256. Sources remain intact.
- Tables of trainers, dark, Pokémon, objects, shops and TM adapted to each region. Native names
  English USA and Japanese preserved. The names of the preview remain available in the six languages
  of the tool.
- Starter native patches, gift capabilities, levels and Shiny Pokémon adapted to the three
  executables, with their own addresses and memory allocations.
- Gifts fromEagun available in all three versions, with native Japanese dialogues in addition to PAL
  and USA texts. The script and reception conditions are kept.
- Imported profiles v0.13 without changing settings, including gifts and Shiny Pokémon related to
  the seed. New profiles usable on all three versions. The creation report identifies the exact ROM.
- PAL regression: ISO of the previous test v0.13 is reproduced identically. Technical matrix of 54
  configurations on the three regions, with 108 repeated constructions and nine previews compared to
  the final bytes.
- Validation Dolphin of gifts USA and Japan: two native gifts according to the preview, five
  readable dialogues, backup by the game, reloading without instant status and refusal of a second
  gift. original ROM and profile Dolphin personal unchanged.

Engine: `regional-purification-gifts-v14`. These technical checks do not certify three complete
parts of the scenario.

[Regional validation and limitations](docs/REGIONAL_COMPATIBILITY_2026-11-03.md). [Follow-up of
gifts USA and Japan](docs/REGIONAL_GIFTS_DOLPHIN_2026-11-03.md).

## 0.13.0

- Event gifts accessible from [Eagun] near Relic Stone: Pikachu gift after 10 purifications at level
  30, Celebi gift after 25 purifications at level 45. Configurable thresholds and levels separately.
  Each gift is limited to a backup reception.
- Access activated in both randomized and deactivated presets in identical copy. It becomes
  available after all the scenes of introduction to purification, including follow-up in the house
  after Skrub, even with a threshold of zero. The appearance ofEagun remains exclusive between his
  home and the sanctuary.
- Species and Shiny status of the two gifts follow the settings and the seed. The preview indicates
  the localized donor and the number of purifications required. The four numerical values are
  deactivated when access to it is.
- Dialogues added in the five languages of the European ROM, depending on the language of the game.
  Settings, aids and previews in the six languages of the interface, regardless of this selection.
- Profiles 0.5 to 0.12 imported with access disabled to keep their previous hashes and conditions.
  Profiles 0.11 and 0.12 retain the choice of Shiny status related to the seed.
- 74 parameters, including 56 booleans, in the 15 existing categories. Engine:
  `purification-gifts-v13`.

Validation and test limits:
[`docs/PURIFICATION_GIFTS_VALIDATION_2026-11-02.md`](docs/PURIFICATION_GIFTS_VALIDATION_2026-11-02.md).

## 0.12.0

- Separate settings in Configuration and Overview of Pokémon, with common seed and always accessible
  Profiles menu.
- Overview organized in three tabs: two starters, 48 Shadow Pokémon and four gifts. Search by name or
  number, Shiny filter when status is known and counter visible lines.
- Expanded lists on all available heights. End of the scrolling zones embedded in the step Settings.
  Wider and contrasting scrolling bars.
- Categories advanced in a sidebar when space allows, or in a compact selector. Reading width
  limited to 1,200 px and default folded mode details.
- Molette on a digital field or a focusless list transmitted to the form to avoid unintentional
  changes.
- Six languages retained, with navigation between views without loss of seed, rules or valid
  preview. Profiles 0.11 imported without changing the hashes. Engine `seeded-shiny-status-v12`
  unchanged.
- Qt references of categories and scroll bar explicitly stored to make the successive window reopens
  reliable.

## 0.11.0

- Option "Link the Shiny to the seed", checked by default when customization of the shinsies is
  enabled. The seed sets the status of each starter, gift, obscure and blocker location. The rate
  remains a probability without quota imposed.
- Accurate overview of the statutes for a new part, even below 100%, with authentic normal/Shiny
  portraits and textual mentions in the six languages. Two encounters of the same species may have
  different statutes.
- Announcement of the view-related mode before calculation. Box and rates dependent on
  customization. Change the invalid link the previous preview.
- Nature, genre, complete PID, IV and other game draws remain native. The already generated Pokémon
  retain their status. The old dark PIDs remain reused.
- Unchecking the link keeps the draw in play. Profiles 0.5 to 0.10.1 are migrated with this disabled
  option. Binary v11 mode compatibility verified at 0, 25 and 100%, with and without gift capability
  patch.
- 69 parameters, including 55 booleans, in the 15 existing categories. Composition C and path of the
  preserved interface.

Engine: `seeded-shiny-status-v12`. Automated verifications do not constitute Dolphin validation or a
complete part of the scenario. The CPU validation controlled under Dolphin is described in
[`docs/SEEDED_SHINIES_VALIDATION_2026-11-02.md`](docs/SEEDED_SHINIES_VALIDATION_2026-11-02.md).

## 0.10.1

- Expandable overview of the 48 Shadow Pokémon and four gifts identified, with their portraits,
  original species and names in all six languages.
- At 100% with the customization enabled, the interface announces the guaranteed Shiny starters
  before the calculation. Intermediate rates remain in play.
- The preview uses the final results of the engine, without creating a ROM. Event gifts are reported
  and are not unlocked by this preview.
- The 0.10.0 profiles and engine runs remain compatible.
- Buttons of selectors of exclusions explicitly retained to avoid an anomaly of Qt wrappers during
  successive openings. Entering in the search does not validate the window.

## 0.10.0

- Shiny category: box "Customize shinies" and rate from 0 to 100%, with four decimal places.
  Disabled by default: original behavior. 0%: none. 100%: all new Pokémon involved.
- Generation-real draw for trainers, dark, two starters and four gifts/events identified. The native
  generator retains its nature and gender constraints and the third generation shiny test.
- Aligning the owner of the Shadow Pokémon to keep status with capture and purification. Already registered
  PIDs are reused. No new draw on an old encounter.
- At 100%, the overview shows the Shiny portraits present in the ROM. At intermediate rates, he
  specifies that the status will be drawn in play, regardless of the randomizer's seed.
- Settings, explanations and previews in the six languages. Profiles 0.5 to 0.9 imported with the
  option disabled, without changing their game bytes.

Engine: `native-shiny-generation-v11`.

## 0.9.0

- Exclusions by species and by type of origin: lists with search, national numbers and names in all
  six languages. Checked means excluded. All replacements apply these filters, including starters,
  gifts and 48 obscure ones.
- Themes of non-obscurous teams: a common type at random, or a type of origin shared when possible.
  Teams sharing recordings are treated together. The dark ones keep their species and their
  reappearances.
- Final forms of non-obscured opponents from a chosen level. The level after bonus of bosses is
  used. Without randomization of species, evolution in the original family. Otherwise, draw among
  the authorized final forms.
- Combination of themes, exclusions, final forms and diversity of bosses without releasing
  exclusions. Capacity adjustment only when activated, with conservation of special markers.
- New settings disabled by default. Import of profiles 0.5 to 0.8 with verification of their
  footprint and preservation of hashes. Save exclusions in profiles. Corresponding CLI arguments.

Engine: `trainer-policies-and-exclusions-v10`. Presets 0.8 remain the same.

## 0.8.0

- Starters: choice of stage (all, base, first evolution, final) and independent filter for
  three-stage families. Both randomized configurations use by default the basic forms of these
  families.
- The number of stadiums comes from the chain of evolution of Colosseum, with consideration of
  babies and branchings. A preserved Pokémon is not constrained by these filters.
- With the three-stage filter and balancing, a base is compared to Eevee rather than Umbreon or
  Espeon statistics. The power constraints between the two starters, types and families remain
  applied.
- Import of the profiles 0.5 to 0.7 after checking their footprint. Old choice of converted basic
  shapes, new filter disabled, hashes retained. The old argument CLI `--starter-base-forms` remains
  accepted.
- Parameters, aids and messages available in all six languages. The identical Copy mode remains
  unchanged.

Engine: `starter-evolution-stages-v9`. New default settings change starters. Old profiles keep the
same game bytes.

## 0.7.0

- Starter preview: animated loading, visible cancellation and "Update Preview" status instead of the
  button after calculation. Update after changing the seed, ROM or settings. No recalculation for a
  configuration already displayed. States translated into the six languages.

- Interface available in the six original languages of Colosseum: French, English, German, Spanish,
  Italian and Japanese, regardless of the loaded ROM. System detection, manual selection stored and
  translations of descriptions, errors and dialogues.
- Overview of the starters named in the six languages. Names of the stones in the language chosen in
  the game, regardless of the tool.

- Eclipse application icon (choice B), integrated into the executable and Qt windows, available in
  both editions without ROM.

- Header title shortened in RANDOMIZE next to the Pokémon Colosseum logo.

- Three-step assistant, Simple and Advanced modes, French and English interface.
- Complete Japanese interface, system detection, stored choice and fonts adapted to Japanese
  characters.
- Coherent pictograms for the fourteen categories of settings, without portraits of Pokémon used as
  arbitrary symbols.
- Local standalone pack: images, portraits, cursor, three sounds and title theme.
- Independent musical reading of menu sounds, compatible with long paths.
- Music enabled by default like sounds, with preservation of the choice to disable it.
- Simple mode choice renowned and explained in the six languages: Pokémon + moves, Pokémon
  alone, identical copy. Common aids and custom settings explained, without changing the applied
  options.
- Overview of starters for the seed and current options, via the creation engine: names
  FR/EN/DE/ES/IT/JA, portraits read in the ROM and levels. ISO/RVZ, cancelable calculation,
  rejection of outdated results and no published ROMs.
- Spacing of eleven stone names while retaining the five native languages.
- Import old profiles with accurate retention of their hashes.
- Preserved start in the absence of the pack or valid metadata.
- Conversion field displayed only for an RVZ source. Request from DolphinTool to create an RVZ
  output from an ISO if necessary.
- The proposed output format is identical to that of the input ROM, with manual change retained
  during step-by-step returns.
- Separate public distribution, without images or sounds of the game. Local pack preserved.
- Offline diagnostic of the executable and after extraction control with a minimum PATH.
- Seeds matrix and settings, PCM measurements and archive verification.

The engine remains `native-text-and-boss-rules-v8`. The distribution and start corrections do not
change the data produced for the same configuration.
