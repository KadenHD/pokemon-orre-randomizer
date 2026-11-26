# Changelog

## 2.1.5 - 2026-11-26

- Add an opt-in Fairy setting shared by Colosseum and XD, disabled in both
  presets. Update 18 existing species and three native moves while keeping
  generation III's other type matchups and the separate Shadow type.
- Add Disarming Voice, Draining Kiss, Play Rough, Fairy Wind, Moonblast,
  Dazzling Gleam and Baby-Doll Eyes with approved existing animations, native
  localized help, level-up additions and evolution-learning events.
- Add ordinary TM51-TM57 items, cash-shop stock and a single 57-TM shuffle with
  matching descriptions and compatibility. Keep the eight native HMs intact.
- Add six-language native and independently rendered x4 Fairy badges, including
  XD's small battle badges, and use the installed data in previews and sheets.
- Keep older profiles' Fairy setting disabled and isolate content preparation
  inside each generation or known-encounter preview worker.
- Use the singular TM label before numbered entries in sheets and journals.
- Use Colosseum Japan's native badge tables and message font field. Keep new
  move text and Meteorite text in the ROM's language on Japanese and USA discs;
  European discs retain their in-game language selection.
- Report a concurrently created HD hosting directory as an existing destination
  on Windows, while preserving it and keeping unrelated access errors visible.
  Retry brief Windows locks when publishing prepared HD archives.
- Leave headroom for the complete test suite on Windows runners, keeping the
  module watchdog and every test. Align source-audit and release-gate deadlines.
- Retry brief Windows file locks when publishing an automatic save backup.
  Keep publication atomic and stop after the existing bounded retry window.

## 2.1.4 - 2026-11-26

- Add Deoxys's Attack, Defense and Speed forms to Colosseum using XD's models
  and animations, with normal and shiny native/x4 artwork.
- Choose a newly randomized Deoxys's initial form from the seed in both games.
  Store its form separately from its personality so changing form preserves its
  shiny status and identity.
- Add a reusable Meteorite to both games. Use it outside battle on a party
  Deoxys, including a Shadow Deoxys, to choose any of its four forms.
- Show the encounter's form and its corresponding base stats in previews,
  Pokémon sheets and exported journals. Keep Colosseum's DNA displays tied to
  the specimen's current form.
- Follow the saved form in XD's Purify Chamber using its original animated
  sprites, including shiny variants. Keep native uppercase item/form labels
  and size the translated form menu to fit its choices.
- Keep the XD item-action contract test independent of private retail inputs,
  including positive and negative small-data pointer displacements.

## 2.1.3 - 2026-11-25

- Keep **Keep music at 100%** enabled for new supported game folders and when
  its saved setting is absent. Retain an explicit disabled choice on reopening
  and preserve the preference if the qualified renderer is temporarily missing.
  Use native audio whenever the region, revision or music bridge is unsupported.
- Improve selected native widescreen clears, fades and window backgrounds,
  including tiled and overscan panels. Preserve the proportions of bounded UI
  elements and handle Colosseum's 3D menu backdrops with their qualified menu
  cameras. Keep the ROM and original movies unchanged. Restore only owned
  display patches when switching to 4:3.
- Relocate the extra menu adapters from the low-memory area cleared by XD's
  anti-Action Replay routine. That routine could overwrite the earlier adapter
  and stall the display when opening the PDA. Preserve the profile's existing
  cheat preference in both games and display modes, without a launch override.
- Bundle the six-region retail display fixture in the source archive. Add
  instruction-level display checks, launcher preference regressions and
  profile-preference coverage. Keep targeted European runtime checks separate
  from static regional checks and complete-playthrough claims.

## 2.1.2 - 2026-11-25

- Prevent XD's first Chobin encounter from trapping a randomized run after a
  defeat. Keep the initial battle and victory path intact; talking to Chobin
  after losing resumes the native Jovi scene without another compulsory battle.
  Change only the qualified retry instruction, preserving natural moves,
  Pokémon, later battles and original movies. Leave copy and cosmetic-only
  configurations unchanged. Make the shared post-battle reply neutral about
  the winner in all six game languages, retaining native names and controls.
- Recognize the previous XD engine when importing v2.1.1 profiles and creation
  reports. Preserve their seed and settings, report the engine migration, and
  keep old challenge codes tied to their original engine. Include the historical
  profile fixture in the source archive so migration tests also run there.
- Include the standalone Windows setup EXE in `SHA256SUMS.json`, retaining both
  ZIP checksums. Publish the installer and manifest only after the requested
  build checks pass; reject existing assets and stale manifests. Audit the
  installer's checksum and Windows header without executing it.
- Add Smeargle to the developer starter matrix's representative species.
- Extend sensitive-starter validation to the USA and Japanese releases of both
  games: complete production plans, native learnset comparisons and separate
  muted Dolphin new-game/summary checks. Preserve the original movies and
  distinguish generation results from gameplay coverage.

## 2.1.1 - 2026-11-23

- Complete XD's natural-starter fix through the full creation pipeline. Retain
  the native Snag-only first encounter and its guaranteed Shadow-ID-1 capture;
  do not require an attack or add a random move to Magikarp, Abra or other
  short/conditional learnsets. Verify the original and final capture contracts
  for Europe, USA and Japan before publishing a ROM.
- Prevent automatic Colosseum natural-mode draws from pairing two starters
  limited to verified Teleport, Harden or Splash effects. Keep each species
  available with another partner, preserve explicit manual choices and record
  their narrow safety result. Other move modes retain their draw domain.
- Evaluate the final randomized learnsets for that safeguard when advanced
  settings combine natural starters with randomized level-up moves.
- Add complete native starter planning and real preview/plan consistency tests,
  plus a bounded developer matrix that records full-image identity, serialized
  patch digests, policy exclusions and original preservation without writing
  hundreds of ROMs. Keep generation checks separate from Dolphin playtests.
- Add **Profiles > Export diagnostic...** in both games. Review an allowlisted
  local JSON report for the last failure or current settings before saving;
  the seed is optional and sensitive-looking seeds are omitted. Exclude ROMs,
  saves, paths, logs and raw error text. Retain all six interface languages,
  background saving, cancellation and existing-file protection.
- Preserve automatic-known-preview ownership when recording diagnostic context;
  pause delayed previews and report comparisons while the export dialog is open.
- Remove the duplicate tag test matrix and native build. Keep independent
  exact-commit Windows/Linux main CI, extracted-source tests, frozen-app checks
  and clean installer installation/uninstallation. Wait for main CI in parallel
  with packaging for up to 35 minutes, covering the main jobs' 30-minute limit
  with startup slack, and recheck it immediately before publication.
- Update the user/developer guides, diagnostic screenshot and issue template.
  New engine identifiers report migrations for older profiles; existing ROMs,
  saves and game folders are not rewritten by an app update.
- Retain v2.1.0 profile and creation-report imports in both games, preserving
  every setting and seed while reporting the engine migration.

## 2.1.0 - 2026-11-23

- Remove XD's starter restriction that required random starting moves for
  species such as Beldum, Metang and Magikarp.
- Add original, species level-up and random encounter move choices to both
  games. The Pokémon-only preset now uses the replacement's level-up moves at
  its encounter level, with empty slots when it has learned fewer moves.
  Preserve Shadow moves, special slots and protected species. Pokémon + moves
  keeps random starting moves. Existing boolean profile settings retain their
  original meaning; the new engine versions report a migration on old profiles.
- Add **My games**, a local library of created and added game folders, with
  search, launcher versions, launch/folder actions and removable references.
- Back up a run's memory cards before launch by default. Add manual snapshots
  and verified restoration, retain up to five copies within 256 MiB, and protect
  active cards with run locks and emulator checks. Save states and ROMs are not
  part of these backups.
- Add background storage accounting with hard-link-aware totals and explicit
  cleanup of old, unreferenced texture views. Preserve ROMs, saves, installed
  packs, runtimes, music banks and downloads; recheck candidates before deletion.
- Share compact, checked challenge codes containing the seed, all randomizer
  rules and engine identity. Import selects the game and rejects incompatible
  engines, damaged data and oversized compressed payloads.
- Localize the four tools in all six interface languages and keep their main
  content and actions within fixed native desktop windows.
- Verify SQLite, synthetic card backup/restoration, challenge roundtrips and
  all four dialogs in the extracted Windows app, without opening a personal run.

## 2.0.6 - 2026-11-23

- Add an explicit **Update a launcher...** action on Home. Upgrade a run's
  launcher without regenerating its ROM or changing its saves, controls,
  settings or pinned HD packs. Back up the previous launcher files, reject an
  active run and incompatible pack pins, and roll back a failed publication.
- Keep launcher preparation cancellable and off the GUI thread. Closing the
  dialog or app waits for the worker; long folder names retain a readable
  shortened label and their complete accessible path.
- Stack Home's utility actions in compact windows and update their layout
  immediately, keeping both game choices and app-update states free of
  horizontal overflow in all six languages.
- Add an opt-in offline packaged diagnostic for launcher upgrades, using
  disposable synthetic runs rather than personal ROMs or saves.
- Run malformed Windows update-package checks in a separate bounded worker.
  Retain every path, rollback and preservation assertion and the original
  per-operation deadlines, without exhausting the updater module's time budget.
- Audit shiny resources across all six supported revision-0 discs and the
  registered native/x4 custom assets. Clarify that legacy Castform weather
  atlases retain their original colors while the modern shiny forms use
  separate registered resources. No missing base-species shiny model was found.

## 2.0.5 - 2026-11-20

- Start every launcher session at 100%. Use the selected 100/200/300% only as
  the Tab fast-forward target, retain Shift+Tab at 50%, and add Ctrl+Tab to
  toggle acceleration. Suppress Dolphin's OSD in the isolated profile to hide
  its intermediate 10% speed notices; stock transitions are still stepped.
- Add remembered 16:9 and original 4:3 display choices in both launchers.
  Start in borderless fullscreen, with guarded regional camera and 2D
  projection patches for widescreen; keep the ROM and original movies intact.
- Fit the revised launcher controls in the fixed window in all six languages.
- Keep XD's Battle Bingo rental species properties unchanged while selecting
  a card, preparing its Pokemon, displaying the grid and fighting. Retain the
  original traits for Battle CDs and training simulations. Ordinary teams and
  field menus continue to use the chosen randomization rules.
- Guard the Bingo menu selector against an uninitialized or empty native
  overlay stack, and preserve explicit settings when importing XD v15 profiles.
  Keep the seed draw algorithm unchanged.
- Add a source-qualified x4 vector reconstruction of the retail Genius
  Sonority wordmark shared by the six supported discs. Record its provenance,
  offline recipe and limits separately from the unchanged startup movies.
- Read native compiler diagnostics as bytes in the audio FIFO test harness,
  preserving errors from non-English Windows toolchains under UTF-8 Python.

## 2.0.4 - 2026-11-19

- Keep Forecast on Castform and exclude it from other species' randomized
  abilities in both games. Other Castform properties remain configurable.
- Update Castform's battle HUD portrait from its currently loaded model, using
  the native sun, rain, hail and normal artwork. Retain native shiny selection,
  asynchronous loading and the existing Shadow Lugia portrait hooks.
- Reduce the HD Sunny Form portrait's model size by 20% in both games. Reuse
  the original GPU capture with an identical crop for normal and shiny cells;
  preserve the native square/round frames and HUD orientation.
- Add distinct modern shiny colors for Castform's Sunny, Rainy and Snowy forms
  in both games, with color-only native models, genuine x4 materials and paired
  native/HD portraits. Keep each specimen's native shiny decision, ordinary
  resources, meshes, opacity and animations. Bind every added native texture
  to its exact reviewed HD artwork and include it in immutable cache identities.
- Refresh the linked stock-material catalogue atomically when portrait framing
  changes. Reject inconsistent material recipes before publishing any artwork.
- Version the new engines and warn when importing an older profile or creation
  report. Preserve all explicit settings, including the option to retain the
  original properties of Pokemon whose species is unchanged.
- Stabilize the source-archive timeout regression on busy systems. Start its
  unchanged two-second deadline after the hanging test is ready, and verify
  that the worker process is terminated.
- Prevent repeated row-size invalidations from keeping the encounter preview
  busy. Coalesce layout requests, preserve wrapped conditions on resize and
  keep horizontal scrolling disabled.
- Render measured HD menu geometry through premultiplied pixels and integer
  alpha conversion. Remove CPU-dependent reciprocal rounding and verify the
  complete output against the reviewed artwork.
- Keep packaged diagnostics offline. Preserve every UI check and render in
  the Windows smoke test while only encoding the screenshots it retains.
- Require successful independent main-branch tests for the exact release
  commit before publishing Windows downloads.
- Wait for updater-test executables to exit before removing their temporary
  folders, avoiding intermittent Windows file locks in source audits.

## 2.0.3 - 2026-11-19

- Withdrawn after a Windows check exposed CPU-dependent offline HD menu
  reproduction. Replaced by 2.0.4.

## 2.0.2 - 2026-11-19

- Enable the 512x512 Spinda lab face on Japanese Colosseum with a compact,
  fenced 512 KiB reservation. Validate two saved PIDs, shiny and ordinary,
  exact GPU texture output, native fallback and recovery in the same process.
- Fix a stale Spinda lab pattern when the game recycles a face texture's
  memory address. Retire the previous PID registration before publishing the
  new one; retain the wrapper contract for older European and USA folders.
- Install the 43 reviewed x4 weather and Deoxys material textures on the stock
  models as well as the additional portraits. Keep each regional native key,
  shiny palette, mesh and animation; keep Original mode unchanged.
- Include the form-material registry in immutable cache identities, reject
  altered or conflicting artwork and preserve installed source packs.
- Add seven x4 vector menu resources for Colosseum battle-menu frames and XD
  indicators, command-panel transparency, name entry and hologram shading.
  Bundle their offline authoring recipes and provenance checks.
- Recreate the five European XD health notices with their original wording
  and line layout, using vector lettering and a measured warning symbol.
- Fix European XD sheet headings sampling letters from the adjacent title
  and remove caption remnants from the shared HD background.
- Clean the Options background stripes in all seven Colosseum locale layouts.
  Retain the native rectangles and every HD donor pixel outside the stripe band.
- Extend six-region menu preparation to 328 checked PNGs. Document source
  coverage separately from the menus actually observed in Dolphin.
- Extend muted Dolphin checks to USA and Japanese party menus, and German,
  Spanish and Italian field menus in both games, using copied QA cards.
- Compare authored HD pixels exactly before publishing the authenticated PNG,
  so offline reproduction is independent of platform PNG compression.
- Require both Linux and Windows test jobs, as well as the packaged Windows
  checks, before the release workflow can publish any downloads.

## 2.0.1 - 2026-11-19

- Add localized HD type/status badges, battle controls, Pokémon sheets, P-AD
  and PC captions, with separate regional layouts and authenticated donors.
- Recreate XD's VS illustrations with game character meshes and authentic
  GameCube controller and GBA photographs, retaining their source credits.
- Use linear texture filtering in each game's isolated HD profile so localized
  x4 menu captions remain smooth. Restore native filtering in Original mode.
- Add localized XD title menus, Bingo type charts and eleven Bingo portraits
  rendered from the real Pokémon models and pinned x4 materials. Preserve
  original text cells and distinguish reconstructed artwork from upstream art.
- Include portable authoring tools and offline packaged checks for the new
  vector menus and registered scene artwork.
- Fix the HD manager's worker connection, which prevented downloads from
  starting and left closing the window stuck on cancellation. Show preparation
  and byte progress immediately, keep the interface responsive, and restore
  controls after completion, failure or cancellation.
- Use neutral charcoal backgrounds for Home and shared HD-manager tooltips,
  menus, text details and selection states. Theme dividers and shortcut keys
  through the active palette instead of inheriting Colosseum's green.
- Remove translation bindings when a dialog is destroyed, so changing the
  language after closing the HD manager does not access deleted Qt widgets.
- Keep the HD manager usable when optional game logos are unavailable, including
  its resize and language-change paths.
- Fail packaged diagnostics on Python exceptions raised in Qt callbacks,
  including errors that do not propagate out of the event loop.
- Include valid small native font banks in HD text capture, covering their
  Pokédollar and punctuation variants without changing the approved letter
  proportions or native advances. Distinguish advance-only spaces from native
  fallback quads with nonzero geometry in runtime diagnostics.
- Fill missing HD texture identities from already-required companion packs,
  while preserving the game pack's art and custom overrides. Track both pack
  generations so repairing a dependency prepares a new immutable view.
- Add localized HD HP/level atlases for the five European XD languages, using
  the genuine XD donor and mikeyX's vector typography. Validate these files
  with the custom overlay cache; retain Original mode without HD packs.
- Add native glyph-page capture for new game folders and vector HD lettering
  from a pinned Noto Sans JP donor. Preserve native text advances, dialogue
  layout and visible Original-mode samples. Keep native guides independent of artistic
  recipes so later HD text corrections can rebuild the cache without the ROM.
- Check custom texture and auxiliary-file hashes before reusing an HD cache,
  and reject missing or altered native guides before rendering replacements.
- Add reviewed x4 portraits for Castform's three weather forms in both games
  and Deoxys's Attack, Defense and Speed forms in XD. Keep native square/round
  framing and paired normal/shiny crops. Include reproducible material and
  composition tools; leave the upstream stock 3D coverage unchanged.
- Add a PID-aware x4 Spinda face companion for qualified Colosseum profiles,
  with fenced texture banks and native fallback. Wait for an observed native
  acknowledgement before reusing buffers after startup or a save-state rewind.
  Do not inject its hooks or reserve its memory on unqualified profiles.
- Use XD's actual horizontal text scale when positioning padded glyphs;
  preserve Colosseum's separate layout and restore the task origin after drawing.
- Retry temporary Windows locks when publishing a completed HD cache, using
  the same cancellable, atomic publication as game folders.
- Update Colosseum Japan's verified apploader budget when runtime additions
  exceed its original 4 MiB executable allowance. Set a finite budget from the
  actual rounded sections and retain the independent memory-boundary checks.
- Keep the controls dialog closed while launch preparation is running. Preserve
  the native-rendering warning if the optional Spinda face companion cannot
  start, while allowing the game to continue.
- Document remaining HD coverage gaps across regions, languages, extra forms
  and dynamically generated text instead of implying complete HUD coverage.

## 2.0.0 - 2026-11-18

- Align custom DNA body artwork at native and x4 resolution using one frozen
  pose and common framing. Restore the keypad's black contour for new body
  renders while preserving retail outlines, material colors and head portraits.
  Use a fuller front view and larger custom placement without clipping the
  body, bevel or duplicate numbers.
- Keep Spinda's DNA body colors and spot diagram in sync with the saved
  specimen in Original and HD modes, including older saves with another PID.
  Reserve the runtime writers after the generated code so runs with several
  Spinda samples cannot overlap their instruction blocks.
- Require both pinned HD packs for XD: its own textures and Colosseum's
  portraits. Install missing dependencies together, retain completed packs
  on retry and check both packs before HD creation or launch. Keep Original
  mode available without packs.
- Reuse the Colosseum pack's x4 portraits for XD's 386 base species and Unown
  forms, with verified texture mappings and circular framing. Keep unsupported
  extra forms native. Use separate native/HD Shadow Lugia head renders with
  its actual red eye and model materials, plus violet square/circular frames
  shared by the app and generated native faces. Keep DNA whole-body art separate.
- Retry brief Windows directory locks when publishing an immutable HD texture
  view, preserving the installed pack and custom overlays.
- Recover an already completed HD download after an interrupted publication.
  Retain a truncated response for continuation instead of discarding its bytes.
- Support fixed GitHub release assets below 2 GiB, with automatic reassembly
  of the original XD archive. Verify each fragment and the full archive, and
  resume interrupted transfers without downloading verified fragments again.
- Complete Shadow Lugia's x4 materials in battle and its three field models,
  including the shiny belly and separate cinematic eye layers. Keep native
  geometry and animations; recapture bodies/portraits with full HD coverage
  and rebuild older prepared caches automatically.

- Pin the original community HD archives by Sephie and mikeyX, including
  PNG/DDS donors and deterministic duplicate selection. Retrieve verified packs
  from a release-configured HTTPS origin or distribution folder. Prepare both
  archives for private storage or download them from the separate, frozen
  GitHub pack release. Credit both authors in the manager, README and downloads.

- Create a game folder with a small Rust launcher, generated ISO/GCM/RVZ,
  reports, custom textures and a separate Dolphin profile. Keep ROM-only output
  available. Detect Dolphin or let the player select it; never import saves
  implicitly or replace an existing game folder.
- Add a neutral shared HD manager with pinned upstream versions and SHA-256
  verification, resumable downloads, cancellation and repair. Reuse textures
  across runs without copying gigabytes into each folder. Keep custom native
  models and add matching x4 texture overlays, including shiny variants.
- Derive custom HD materials and portraits from the pinned HD packs instead
  of filtering native bitmaps. Register separate pack-textured whole-body art,
  preserve native assets, record donor provenance and block incomplete custom
  HD preparation. Resolve cross-game pack dependencies for imported models.
- Reopen each run independently of the randomizer. Keep its graphics, speed,
  keyboard/XInput controls, memory card and save states together. Provide
  100%/200% base speed and hold shortcuts for 200%/50% while the game has focus.
- Enable the optional native-speed music companion for verified Europe
  revision-0 images on Windows with the checked renderer recipe. Gameplay music
  follows the host clock; effects, cries and prerecorded movie sound remain
  native. Fall back to native audio when the helper cannot follow. Leave the
  option disabled for unvalidated regions, revisions and renderer builds.
- Match the GameCube's actual audio clock in the experimental companion and
  preserve its resampling phase during same-session music reconstruction.
- Share the same creation and launcher layouts across both game themes, with
  all six interface languages and English generated filenames. Preserve the
  source opening videos, original ROMs and personal Dolphin profiles.

## 1.2.26 - 2026-11-16

- Integrate lossless RVZ conversion through a bundled Rust library. Remove
  DolphinTool path fields and the external converter requirement from both games.
- Accept GCM input and output. Every ISO, GCM or RVZ input offers all three output
  formats, with the input format selected by default. Preserve cancellation,
  source checks, exclusive output creation and full RVZ roundtrip verification.
- Include the locked converter sources and dependency notices in distributions;
  verify native conversion in the relocated Windows application smoke test.
- Remove local account and workspace paths from native library diagnostics.
- Disable horizontal panning in both games' encounter tables, including
  trackpad gestures, Shift+wheel and input over the header. Keep vertical
  scrolling and ignore the horizontal part of diagonal gestures.

## 1.2.25 - 2026-11-16

- Display Colosseum's final four native Shadow entries as 45-48, keeping their
  internal IDs unchanged. Use the same roster numbers in duplicate-family
  labels and the offline journal; the optional bonus encounter is entry 49.
- Give gifts and XD Poké Spots a middle column for acquisition conditions,
  locations and encounter rates. Add Plusle and Ho-Oh's original requirements in all six
  languages. Wrap long conditions and allow pixel scrolling through tall rows.
- Use circular XD placeholders and clip every XD preview portrait to the same
  silhouette, including starter roulette frames. Keep Colosseum portraits square.
- Keep long acquisition text inside its column and refresh nine English README
  previews, including XD's Poké Spot locations and encounter rates.

## 1.2.24 - 2026-11-16

- Load only retained and manually selected encounters automatically, including
  their actual sheets and known shiny appearance. Calculate randomized
  replacements and the complete ROM patch plan only when the user requests
  the full preview. Queue that request safely after a pending known-data read.
- Preserve native abilities, moves, learnsets, compatible TM moves, types,
  base stats and held items for retained encounters. Protect their evolution
  families in shared species tables; shiny and accessible-evolution rules still
  apply. Add the shared advanced opt-in for property randomization, unchecked
  in both games' randomized presets. Import older profiles with their original
  property rules so saved runs remain reproducible.

## 1.2.23 - 2026-11-15

- Use XD's circular portrait for added Shadow Lugia appearances in previews
  and Pokémon sheets, including the shiny variant. Keep Colosseum's square
  format and existing native textures. Share the added-portrait formatter and
  whole-body validation, and document the required battle, field, animation
  and DNA resources for every future added model.
- Center update progress in a dedicated home view instead of adding it below
  the game cards. Lock game navigation, profiles, language, audio controls,
  file drops and manual closing while updating. Allow cancellation during
  download, restore previous controls on cancellation or error, and let the
  verified helper close the app when it is ready to restart.

## 1.2.22 - 2026-11-15

- Stop the test runner at the global deadline when Windows reports a slightly
  early process timeout. Do not start another worker with the remaining fraction
  of time; retain the failure and the explicit untested-modules diagnostic.
- Refresh the Impeccable design reference, surface brief and generated index.
  Align current guides on seeded shinies, per-encounter Poké Spot rolls, fixed
  previews and shared preset protections.
- Clarify both presets in all six interface languages: retained shop Balls,
  protected legendary encounters, unchanged moves and items in Pokémon-only
  mode, event rewards and the bonus quest. Update Plusle's help for scaled
  story models and remove repeated evolution-stage wording.
- Enable XD's separate 5% wild shiny rate in both randomizing presets. Roll
  again for every new Poké Spot encounter; its field model, battle and captured
  Pokémon share the same result. Imported profiles retain their saved wild rate.

- Exclude Legendary and Mythical Pokémon from random draws in both randomizing
  presets and both games, including starters, Shadows, gifts and XD's Poké Spots.
  They can be enabled under Advanced > Allowed Pokémon. Keep fixed story
  encounters, original legendary Shadow species and the bonus Lugia unchanged.

## 1.2.21 - 2026-11-15

- Frame Eagun during his own lines in Colosseum's bonus quest and turn him
  toward the player. Keep Nascour in his own shots and retain both original
  character models. Keep all three characters in the final group shot after
  Nascour leaves, throughout the partner's and Eagun's remaining lines.
- After the quest, let Eagun resume purification rewards directly instead of
  repeating his quest thanks on every interaction or area visit. With event
  rewards disabled, he gives purification advice instead.
- Add space between Pokémon portraits, names and sheet buttons in previews.
  Automatically load portraits and sheets for fixed encounters from the
  selected ROM, with their seeded shiny appearance, while leaving randomized
  replacements hidden until the preview is requested.
- Keep all original shop Poké Balls in both randomizing presets and both games.
  Add an independent advanced switch for shops, without protecting Ball
  treasures. Include Colosseum's nine ordinary cash shop inventories and
  preserve the previous scope when importing an older profile.

## 1.2.20 - 2026-11-15

- Enable Colosseum's bonus quest in both randomizing presets, keeping its
  intended team and Shadow Lugia by default. Add independent advanced switches
  for the first five team members and the final Shadow Pokémon, with matching
  scene models, dialogue, mail and previews.
- Preserve original legendary Shadow species by default in both games. Add an
  advanced switch to randomize them; XD001 remains protected for XD's story.
  Show these protections and the bonus battle's fixed choices in the applied
  settings summary, including when their randomization switches are off.
- Use XD's dark model and matching normal or custom shiny portraits for every
  Shadow Lugia in both games, including randomized encounters, Snag Lists and
  supported field scenes. Match Colosseum's DNA hologram and keypad to the same
  saved identity and purification state.
- Keep the DNA analyzer's original blue hologram effect. Use native whole-body
  artwork on its door keypad, including shiny and Unown variants. Render the
  two extra Shadow Lugia icons from their actual 3D models, with complete
  transparent silhouettes; retain the native puzzle answers.
- Add an advanced option in both games to retain Shadow Lugia's appearance
  after purification. It is disabled by default, changes appearance only and
  never affects a Lugia that was not a Shadow Pokémon. Older profiles keep it off.
- Isolate test modules in bounded processes to avoid accumulated Qt thread
  cleanup hangs, and close the complete private test process group on archive
  verification timeout. Extract the Windows installer compiler without elevation.

- Stage the optional Colosseum Lugia confrontation with camera shots, both
  heroes, a matching field model and localized dialogue. Use saved hero/partner
  names. After capture, Nascour walks to the exit before the final exchange.
  Keep retries available and protect original story and Master Ball handoffs.
  Remember the introduction independently of other battle results, and send
  Eagun's warning only after a motorcycle trip to another area. Keep the last purification
  uninterrupted. Use the native Cipher Admin battle theme.

- Always link custom shiny rates to the seed in Colosseum, matching XD. Retire
  the unlink switch and normalize older unlinked profiles after verification,
  retaining their rate. Eagun's gift, battle partner and field appearance now
  share the same determined status at intermediate custom rates as well.

- List purification gifts by their configured thresholds in previews and the
  offline journal, preserving other gifts and stable ordering for equal counts.

- Offer a localized one-click Windows update on home for newer stable GitHub
  releases. Download and check the package's size and SHA-256, update installed
  and portable editions in place, then restart. Show cancellable download
  progress and recoverable errors; preserve ROMs, saves and preferences.
  Check once in the background without blocking offline use or window closing.

- Preserve Eagun's original home actor and story dialogue, including the P★DA
  contact exchange and Master Ball handoff. Delay added shrine events until
  the contact exchange, and while a native Master Ball handoff is pending.
- Match Eagun's companion to his first purification gift, including determined
  shiny colors, Unown's form and Spinda's spots. Remove the companion from his
  home after the gift without hiding Eagun or replacing his story interactions.
- Randomize abilities in both presets, allow every starter evolution stage,
  and remove default species-power matching and starter-pair type constraints.
- Draw moves without type or power matching in Pokémon + moves. Keep the
  offensive-move and duplicate protections available separately in Advanced.
- Randomize already-held opponent items and ordinary Ball treasures in the
  full preset. Disabling similar-value matching now opens both item categories
  and prices, consistently in Colosseum and XD.
- Use saved Shadow identities for the Snag List's models, including shiny
  colors and Spinda's spots, without changing saved Pokémon.
- Keep Colosseum's unchanged teammates consistent after a Shadow Pokémon is
  captured, including moves, held items and seeded shiny/Spinda identities.
  Preserve genuine progression teams and the captured slot's native handling.
- Check that XD's starter can hit the first Shadow opponent even when tutorial
  Teddiursa is kept unchanged. Reject unsupported matchups before creating the
  output, and do not count Focus Punch as a reliable standalone attack.
- Resolve the actual PKX Idle animation for field models and preserve native
  Plusle scene motions when using its original field model.
- Include the bonus trainer and battle in previews and the journal without
  changing the original completion requirements or totals. Reuse Nascour's
  original localized name. The event's own advanced switches control its team
  independently of general trainer and Shadow randomization.
- Give shiny Shadow Lugia a custom white-body, dark-belly appearance in both
  games, with matching preview portraits and the original pink shiny appearance
  after purification.
- Use black backgrounds inside normal and shiny Shadow Lugia portrait frames,
  including the edge of the original violet disc. Keep XD's round mask and fit
  the complete head inside it; retain Colosseum's square tile.
- Match XD001's real-time presentation to its shiny identity. Restore
  Colosseum's bonus battle portrait and keep its dark appearance in targeting
  and capture views. Match the portraits' black eye mask and white neck to
  the 3D model, with black backgrounds in the application.

## 1.2.19

- Match more trainer dialogue to the final teams and battle tactics in both
  games, including field conversations and remarks about moves or abilities.
- Keep XD's Battle Simulator lessons and Battle CDs playable with randomized
  types, abilities and base stats by using original data for virtual rentals.
- Keep the saved Spinda's pattern and shiny palette in XD's Gateon Port scene.

## 1.2.18

- Match Colosseum's DNA analyzer and door keypad to the randomized Shadow
  encounters, including known shiny colors and matching Spinda spot patterns.
- Draw Unown's letter or punctuation form from the seed and use it in battles,
  supported scenes, the DNA lab and the desktop preview.
- Match Spinda's spots to the Pokémon's in-game personality value in supported
  scenes. Show its exact spot pattern in the Pokémon sheet when available.

## 1.2.17

- Keep the interface responsive while ROM creation and report checks finish.
- Retry the Windows installer compiler download and use the GitHub asset API
  as a fallback, with the same SHA-256 check.
- Run the release test suite from the extracted source archive and print a
  thread traceback if it hangs.

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
