# Validation scope

This index records the v1.0.0 foundation and subsequent validation follow-ups.
Dated reports in `docs/` describe their named versions and scenarios; they are
historical evidence rather than the current feature specification.

## v2.1.7 gameplay and CI follow-up

- In both European games, copied saves passed a fresh Shadow Deoxys capture,
  Meteorite form change, native purification, native save and cold reload.
  The saved and loaded Pokémon records matched byte for byte.
- Fairy diagnostics covered 3,639 cases across the six regional executables.
  Muted European Dolphin runs reached the installed battle code for 602
  Colosseum cases and 611 XD cases. A separate XD play test checked the Purify
  Chamber types, tempo and flow.
- The European XD ONBS route covered the field menu, battle entry, command HUD,
  battle exit and elevator in both graphics modes, with cold 4:3 references.
  The 16:9 HD exit used a recorded victory state.
- A separate European XD test covered twelve PC cases for ordinary, Shadow and
  purified Lugia across both palettes and both values of the setting that keeps
  the Shadow appearance. The Purify Chamber test checked the uploaded texture
  key. The native animated sprite uses the original frame timing.
- The local eight-module benchmark ran 96 tests in each trial. Its median fell
  from 70.4 seconds with one worker to 47.4 seconds with two. The CI workflow
  records timings separately for its Windows and Linux jobs.

## v2.1.6 preset defaults and interface copy (2026-11-26)

Fairy rules are on in both randomized presets for both games. Copy mode and
imported profiles retain their saved settings. The targeted regression campaign
passed 406 tests across 36 isolated modules, covering preset selection, older
profiles, preserved encounters and the Fairy pipeline. The shared interface's
49 targeted tests passed again after the six-language preset copy changes.

The source interface diagnostic rendered 474 states at 1040 x 800 and
680 x 540, with 210 saved screenshots. The approved home screenshots remained
byte-identical. Both English Simple-mode screenshots were refreshed and all
58 documentation media files passed the manifest checks. Impeccable's project
check reported no findings. These interface checks use private muted settings
and open no ROM or personal save.

The release workflow separately tests the exact commit on Linux and Windows,
then rebuilds and audits the Windows app and installer before publication.
The in-game Fairy checks recorded below cover the mechanics introduced in
v2.1.5.

## v2.1.5 optional Fairy rules (2026-11-26)

The local source campaign covered all 208 isolated modules and 1,975 tests,
with no outstanding failures. Three Windows symbolic-link privilege checks
were skipped. Bounded reruns replaced earlier sandbox and file-lock failures;
these totals describe the final result per module, not a single uninterrupted
test command. All 127 Fairy checks passed without skips. Both randomized
presets passed complete production patch generation for all six regional
releases of the two games, using original source discs without writing output
ISOs or changing those discs.

Muted Dolphin trials on private European ROM and memory-card copies covered
all seven added moves in both games, their animations and PP consumption,
native TM purchases and teaching, evolution learning, replacement, refusal,
cancellation, saving and cold reload. Identity and shiny status were checked
separately from displayed models. Additional USA and Japanese checks covered
loading, localized names, descriptions and type badges in both games.
Colosseum Japan also passed a live Disarming Voice and Dragon Rage immunity
check. An XD comparison used the same ISO, saved state and internal resolution
with texture replacements enabled and disabled to verify its separate x4 Fairy
badge. Original opening videos were retained, and owned test emulators stopped.

The rebuilt development Windows application passed its complete frozen audit:
474 interface states and 210 saved screenshots, plus native libraries and
source-to-package integrity checks. Its source archive passed all 208 modules
with 1,940 tests and 176 expected skips where private retail files were absent.
Windows HD archive and automatic save-backup publication checks cover transient
file locks, existing destinations and bounded atomic publication.

These are bounded scenarios, not complete playthroughs or every animation in
every regional release. The added-move GBA transfer refusal has native table
and PowerPC tests; a connected GBA session has not been tested. Hosted release
jobs separately test the exact release commit and rebuild and audit its final
Windows executable, installer and archives. See [Fairy rules](FAIRY_TYPE.md).

## v2.1.4 Deoxys forms and Meteorite (2026-11-26)

The local source campaign covered all 194 isolated test modules, with 1,830
tests executed and no outstanding failures. Its whole-suite deadline required
two bounded runs. Both directory-junction modules passed their complete
filesystem-enabled reruns. After the final native fixes, all 117 Deoxys checks
and 164 shared regression checks passed again. Production plans passed for
both games, including their registered native/x4 assets and public packaging.

Muted European Dolphin trials used private ROM and memory-card copies.
Colosseum covered an initial seeded form, standard/shiny displays, the native
Meteorite menu, a real save and cold reload, and the current owned form in the
DNA hologram and keypad. XD covered all four menu choices, a native save and
cold reload, Shadow form changes, purification and PC transfer. PID, original
trainer, shiny status, HP and Shadow data were checked independently of the
displayed model. All owned test processes stopped, and protected source ROMs
and saves retained their hashes. Prerecorded opening videos stayed original.

This is not a complete playthrough or an exhaustive animation test. A fresh
Shadow Deoxys capture was not played through live, and the final XD
purification was not followed by a second cold reload. External GBA transfer
retention is unqualified. XD's Purify Chamber uses its native animated sprites;
this feature adds no x4 replacements for those animations, and their actual
HD upload path has not been qualified. Regional code contracts and resource
checks do not extend the European runtime trials to every regional screen.
See [Deoxys forms](DEOXYS_FORMS.md) for the supported behavior.

Hosted release jobs separately validate the exact commit and final Windows
executable, installer and downloadable archives.

## v2.1.3 launcher music and display checks (2026-11-25)

After the version update, 135 targeted checks passed across display patches,
game folders, launcher UI, interface parity, translations, Windows distribution,
public archives, installer checksums and the independent-main release gate.
The frozen-app audit now explicitly requires the regional display-data module.

The latest per-module results cover all 180 source test modules: 1,723 tests,
with 1,720 passing, three skipped, no failures and no errors. Results from
bounded isolated processes are consolidated by module; a rerun replaces its
earlier result rather than adding duplicate tests. The three skips concern
Windows privileges for file symbolic links in artwork, HD hosting and menu
sound caches. Both directory-junction modules passed their complete reruns
with fixture filesystem access (20 and 16 tests).

The initial full run reached its whole-suite deadline. The remaining modules
and earlier failures were completed separately with the declared Pillow 13
dependency. The global interpreter's Pillow 11.2.1 had caused missing image
APIs, rejection by the vector-renderer qualification and a pinned font-manifest
mismatch. The four affected HD modules pass with Pillow 13.0.0. The diagnostic
GUI module also passes with a complete module deadline. Test workers suppress
native menu audio; music unit tests supply explicit fake backends.

Music preference checks cover new game folders, an absent setting, explicit
opt-out, reopening and temporary renderer unavailability. An unsupported
region/revision, missing music bridge or unqualified renderer retains native
audio. These are preference and capability checks; they do not extend the
earlier soundtrack, device or long-session audio validation.

Twenty-six display checks independently execute the emitted PowerPC instructions
and compare the six revision-0 regional contracts with retail-word fixtures.
They cover camera and orthographic scaling, fullscreen pass compensation,
deferred recording/replay, full-width and overscan window geometry, bounded
sprites, XD's temporary FLASH geometry, Colosseum's resource-selected menu
cameras, FIFO destination, register/condition preservation and owned-only 4:3
restoration. The menu-camera lookup checks resource counts, table bounds and
complete MEM1 pointer ranges before reading camera data. Geometry adapters
change only their qualified X coordinates; UVs, Y coordinates and unrelated
sprite records remain native. The extra adapter space is bounded separately
from the exception-padding cave. Profile tests cover preservation of explicit
enabled and disabled cheat preferences in every game/region and display mode,
an absent preference, and the absence of a cheat-setting launch override.

An additional XD PDA trial exposed its anti-Action Replay routine clearing
the earlier adapter at `0x80002800`. The overwritten instructions could stall
the display even with Dolphin cheats disabled. The replacement placement uses
unused permanent executable padding at `0x80004D00`; it does not require a
cheat-setting restriction. A regression executes both adapters after the native
anti-Action Replay wipe, without reapplying the per-frame patch.

Final European revision-0 trials used the relocated adapters with original
textures. Colosseum's 184-byte adapter matched the source for 3,651 consecutive
samples spanning 11,797 video interrupts, about 236 seconds. Checks covered
the menu, loading, summary, return to the field, Miror B.'s story area, battle
entry and the command HUD. XD's adapter matched for 2,256 consecutive samples
spanning 7,749 video interrupts, about 155 seconds. Its summary, PDA Shadow
Monitor and return path worked through repeated anti-Action Replay clears.
XD room transitions and battle endings were not covered by these trials.
Both sessions stopped normally through Dolphin with `NoAudioOutput` enabled;
all owned processes were closed.

Earlier HD trials logged 55 custom-asset loading messages for Colosseum and
133 for XD while checking menu and summary geometry at the old adapter
placement. Those trials establish HD loading and the observed geometry, not
final HD runtime coverage at `0x80004D00`. Static checks of ten retained
HD-patched executables confirm the new cave is unused in those layouts.

Earlier native 4:3 trials restored the live perspective and orthographic
instructions to `FFA01090` and `4E800020`, with native screen proportions in
both games. The final source separately tests owned-only restoration of the
relocated adapters. SHA-256 comparisons kept the original and trial ROMs and
the source QA cards unchanged.

Static checks for Europe, USA and Japan do not certify all regional screens,
cameras, transitions or complete playthroughs. Display corrections live in
the run's isolated emulator profile; the ROM and original movie files remain
unchanged. The qualified original movie projection calls are preserved.

These are local source and gameplay results. Hosted release jobs separately
validate the exact commit and final Windows executable and installer.

## v2.1.2 release preflight (2026-11-25)

After the version update, 102 targeted checks passed for starter progression,
historical profiles, installer checksums and the independent-main release gate.
The source builder explicitly includes the genuine v2.1.1 profile fixture.
A newly built source ZIP passed its checksum and CRC checks; the historical
profile and distribution modules then passed all 18 checks from a temporary
extraction outside the checkout. Its archive contains the new progression and
checksum modules and no ROMs or saves. The extraction was removed afterward.

The gameplay evidence below was collected on the preceding application version
with the named engine revisions. The release version bump does not repeat or
extend those Dolphin scopes. Hosted release jobs separately validate the exact
commit and the final Windows downloads.

## Follow-up validation (2026-11-24)

The [European fresh-start trials](XD_FRESH_START_VALIDATION_2026-11-24.md)
separate native NEW GAME evidence from prepared checkpoints. A deliberate
first-Chobin defeat additionally exposed a retry gate that can trap a passive
starter. The [v19 progression safeguard](XD_FIRST_BATTLE_PROGRESSION_VALIDATION.md)
documents the narrow script correction, localized reply, regional contracts,
profile migration and independent native loss replay.

The source suite completed 1,693 tests across all 180 isolated modules. Two
Windows junction-fixture modules required a rerun with filesystem access;
both passed completely (31 tests). Three existing symbolic-link privilege
skips remain. The final localized reply and serialized plans passed the
16 relevant module, integration and migration checks again. These are local
source validations, not a new GitHub Actions or published-release result.

The installer build now records the standalone EXE alongside both ZIPs in
`SHA256SUMS.json`. A real build from the published v2.1.1 Windows payload
compiled successfully and reproduced the published setup byte for byte.
The complete three-asset manifest passed the release verifier, and both ZIP
records remained unchanged. The setup was inspected, not executed; the personal
installation and published release assets were not modified. The temporary
copies used for this build were removed after digest verification.

Forty-nine targeted checks cover checksum publication, release CI, Windows
distribution and updater selection. The publication cases exercise damaged
inputs, concurrent files, a changed manifest, interrupted publication and
rollback. The separate starter harness checks also pass.

The [USA/Japan starter campaign](REGIONAL_STARTER_VALIDATION.md) records its
native-data comparisons and complete production plans separately from emulator
trials. It completed 144 requests: 128 valid complete plans, 16 expected
Shedinja exclusions and no unexpected errors. All 96 natural starter rows
matched the regional original learnsets, including empty slots.

Four muted Dolphin trials then started native new games on separate fresh
profiles. USA Colosseum showed Ditto 26 and Smeargle 25; Japan Colosseum showed
Wobbuffet 26 and Metapod 25. USA XD showed Ditto 10, and Japan XD Wobbuffet 10,
after winning the original simulation. Their move sheets matched the expected
natural sets. These are regional startup/summary checks, not full playthroughs
or first-Snag claims. All original regional RVZs and movie files remained
unchanged. Verified generated images and decoded copies were removed; test
cards and evidence remain. No personal save or profile was used.

## v2.1.1 complete starter creation and private diagnostics (2026-11-23)

The expanded read-only matrix completed 885 attempts: 875 valid production
patch plans and ten checks of the existing Shedinja exclusion, with no
unexpected failure. Each game covered every one of its 385 admitted starter
species with natural moves. Colosseum checked both constructor slots. Actual
default presets, two seeds, automatic pairs and one-manual-partner cases were
checked separately. Full-image hashes of both original European discs remained
unchanged; this matrix wrote no output ROMs. See
[the exact matrix scopes and limits](STARTER_PIPELINE_VALIDATION.md).

XD's first capture is natively Snag-only and guaranteed for Shadow ID 1. Native
instruction checks cover four windows on Europe, USA and Japan layouts, both
before and after patching. A small instruction interpreter independently checks
the forced-capture branch. No attack, damaging-move requirement or extra
Master Ball patch is added for short starter learnsets.

A real Colosseum Pokémon-only seed previously drew Abra with Teleport and
Silcoon with Harden. Automatic natural-mode pairs now exclude combinations
limited to those verified harmless effects or Splash. Both species remain
eligible with another partner; two explicit manual choices stay unchanged.
This narrow safeguard does not promise every battle can be won. A further
advanced-case regression combines natural starters, randomized level-up moves
and story-family diversity: it checks final learnsets rather than native ones.
The complete production plan passes with an Abra/Silcoon-only candidate pool
after their learns are randomized, with the original disc hash unchanged.

The initial isolated source pass completed 1,653 tests across 175 modules in
933.063 seconds, with no failures and three Windows symbolic-link skips.
Follow-up tests cover the final-learnset projection and migration of genuine
v2.1.0 exports. Four historical checksum-verified profiles retain every setting and exact
seed; two historical creation reports retain their verified disc identity.
Their engine migration is reported; old challenge codes still require their
original engine. Existing ROMs, saves and caught Pokémon are not rewritten.

The diagnostic export is local and allowlisted. Tests cover typed option
validation, optional seed omission, sensitive-looking seeds, error
normalization, cancellation, exclusive publication and file-boundary
sanitization. Actual Qt checks cover both games, all six languages, pending
preview ownership and delayed-work suspension while the review dialog is open.
No personal paths, raw errors, logs, ROM or save bytes are exported.

A muted European XD trial used a prepared checkpoint on a copied card before
the native Snag Machine handoff. The game supplied the Snag Machine and five
ordinary Poké Balls normally. Level-10 Magikarp caught the first Shadow Pokémon,
a level-11 Phanpy with full HP, without selecting an attack; Naps was defeated
and the original story continued. The party then contained both Pokémon at
full HP; Magikarp's summary still showed Splash and three empty move slots.
This is a targeted capture-scene check, not
a new complete playthrough. The loaded starter-constructor windows in both
generated trial discs match the final source planners; game-folder bridges
separately relocate system data. The original opening movies are retained.

The muted European Colosseum trial started a fresh game on a copied card with
the formerly passive-pair seed. After the original opening, the native party
contained Sandslash at level 26 and Krabby at level 25. Their summaries showed
Defense Curl / Sand Attack / Poison Sting / Slash and Leer / Vice Grip /
Harden / Mud Shot respectively, matching the production plan. This is a native
startup and summary check; no full campaign or all-region Dolphin claim is made.

The release pipeline retains independent Windows/Linux main tests for the exact
commit, extracted-source tests, frozen-module/resource audits, the full UI
diagnostic matrix and clean installer installation/uninstallation. Packaging
waits for main CI in parallel and rechecks it immediately before publishing;
only duplicate tag-suite and native-build passes have been removed.

The fresh public source archive passed 1,627 tests across all 176 isolated
modules in 568.766 seconds. Its 130 declared skips reflect missing local data
or platform prerequisites in the extracted archive. The frozen Windows app
then passed its isolated diagnostic in 42.4 seconds, rendering all 474 UI
states and saving the prescribed 210 captures. Both diagnostic exports were
reviewed and saved. The archive audit verified 207 bundled application modules,
51 required runtime modules, resource integrity and absence of private source
paths. The separate Windows installer compiled without modifying the personal
installation; installation/uninstallation remains a clean-runner release gate.

## v2.1.0 run tools and encounter move policies (2026-11-23)

Tests use private preferences and temporary synthetic game folders/cards.
Native-data cases read the original European Colosseum REL/DOL and XD disc;
muted Dolphin trials use separate generated images and copied memory cards.
No personal ROM, card, save state or emulator profile was modified.

- Library checks cover registration, search, missing entries, reference removal
  and launcher metadata. Forgetting a run leaves its game data intact.
- Card checks cover deduplication, retention, identity/hash rejection, safe
  restoration, partial-publication rollback, linked paths, active-run locks and
  external emulator ownership. A launch test creates a real synthetic backup
  before releasing the command to the mocked launch slot.
- Storage checks cover hard links, protected data, referenced/recent views,
  changed candidates, installer locks and a library changed by another app
  instance. Cleanup deletes only explicitly selected eligible fixture views.
- Challenge checks cover both option types, exact seeds, Unicode, integrity,
  unknown engines, layout compatibility and bounded decompression. Invalid
  imports leave the current game/settings untouched.
- Native Qt checks cover all six interface languages, bounded dialogs, worker
  cleanup and the normal 1,040 x 800 Home viewport without scrolling. Screenshots
  in the run-management guide use demonstration data and muted preferences.
- Starter regressions select Beldum, Metang and Magikarp in each game with both
  non-random move modes. Native instructions accept them without requiring a
  random draw; species mode uses Take Down or Splash as appropriate, with empty
  unused slots. Colosseum's level-26 Magikarp also has Tackle.
- Native trainer checks verify that replacements in both games receive their
  own learned moves at their encounter level. Relearned moves follow native
  order, while Shadow/scripted slots remain protected. GUI/CLI/profile tests
  distinguish original, species and random policies and preserve old booleans.

The final isolated pass ran 1,607 tests across all 170 modules in 817.547 seconds
with no failures. Three existing symbolic-link tests were skipped because this
Windows account cannot create symbolic links. The new junction and linked-path
guards passed. CI also runs the suite on Linux and Windows.

Muted European Dolphin trials started a new Colosseum game with Beldum at
level 26 (Take Down only) and Magikarp at level 25 (Splash and Tackle). XD
completed the original opening simulator and entered the lab with Beldum at
level 10, with Take Down and three empty slots. The lab dialogue named Beldum.
The original opening movies were retained. These are targeted startup and
summary checks, not complete campaigns or every regional starter combination.

Both runs had a byte-verified card backup before Dolphin started. Attempting
restoration while the owned Colosseum process was active was refused. XD then
saved its new game to the copied card; after the test process closed, restoring
the earlier snapshot reproduced the original card digest and retained a backup
of the new save. Original image/card/executable hashes and generated-image hashes
remained unchanged. XD also booted with a newly created isolated profile.
An initial XD test process did not expose game memory before the startup
deadline; it was closed, and both the retry and fresh-profile check passed.
No cause or normal emulator exit is inferred from that abandoned trial.

The extracted Windows app diagnostic checks real SQLite operations, synthetic
card backup/restoration, both challenge formats and all four dialogs without
opening a personal run or starting an emulator. The installer is built locally;
the release workflow tests installation on its clean Windows runner before
publishing. This does not claim a second physical PC or controller playtest.

The engine identifiers are now `natural-encounter-moves-v27` and
`xd-natural-encounter-moves-v17`. Older JSON profiles retain their option values
and report a migration; exact historical reproduction requires the old app.
Challenge codes require an exact engine/layout match. Existing generated ROMs
and Pokémon already stored on a memory card are not rewritten by an app update.

## Automated and packaged checks

- The integrated converter is tested with a synthetic GameCube container across
  all nine ISO/GCM/RVZ input/output pairs, and through both games' publication
  pipelines. Tests cover Unicode paths, cancellation, malformed input,
  callback errors, existing-file protection, reports and temporary-file cleanup.
  Runtime conversion tests forbid launching any external executable.
- On 2026-11-16, the native reader decoded all six supported retail RVZ originals
  to their expected ISO SHA-256 hashes. For both European games, native RVZ
  output was also decoded independently by DolphinTool and compared byte for
  byte with the original raw disc. Source RVZ hashes were unchanged. DolphinTool
  was used only as an independent development check; it is not part of the app.
- Windows diagnostics require the bundled disc-conversion library and exercise
  a synthetic GCM → RVZ → ISO roundtrip without a developer PATH. This verifies
  container conversion and packaging; it does not certify a new gameplay run.
- Python tests cover guarded edits, disc identity, both games' options, allocation,
  previews, profiles, translations, reports and GUI state.
- Preset tests compare all shared fields across games and balance fields across
  modes. Exports from the actual published RC2 source archive verify that imports
  keep old values. RC1 version/engine compatibility is checked too.
- GitHub Actions runs Windows and Linux tests. Tests requiring local ROMs declare
  and skip those prerequisites on public runners.
- Rust/Python codec output is compared. Archive audits check CRCs, hashes, paths,
  notices and the allowlisted interface pack.
- Windows diagnostics cover six languages and two sizes, including
  both games and home. Isolated smoke tests remove developer tools from PATH and
  use fresh application data. The installer is installed, checked and uninstalled.
- Published asset sizes and SHA-256 digests are verified after release.

Counts evolve; the Actions run for a release tag records that build's results.

### Launcher upgrades and shiny resource audit (2026-11-23)

Version 2.0.6 adds an explicit launcher upgrade, with 18 targeted backend
and Qt checks covering protected run files, unchanged pack pins, cancellation,
active-run locks, concurrent settings changes, version rechecks under the lock,
rollback, interrupted publication, cache repair and unexpected worker errors.
All six translated update dialogs fit a fixed 760 x 400 window. Closing the
dialog or main window waits for the background worker.
An additional 32-test batch covers both update flows, compact Home layouts and
offline diagnostics. Home utility actions stack in compact windows, with no
horizontal overflow in the six-language app-update matrix.

Malformed Windows update-package checks run in a separate bounded module. Each
invalid path has its own fresh dummy application and test result; traversal,
case collisions, ROM payloads and NTFS streams keep their original rejection
assertions and 15-second helper deadlines. This avoids exhausting one module's
global budget on a busy runner without extending or removing safety checks.

Release CI checks the exported sources across all 167 isolated modules, with
explicit skips for prerequisite-dependent cases. The Windows ZIP passes integrity, asset, runtime
source and private-path audits. Its relocated executable renders 474 UI states
and retains 210 screenshots with developer tools removed from PATH and private
preferences. The separate frozen launcher-upgrade diagnostic also passes for
both games, verifying the actual runtime copy, backups and six protected files
per synthetic run without opening a personal ROM or save.

The [six-disc shiny audit](SHINY_MODEL_COVERAGE.md) checks 386 normal/shiny
field-model pairs per disc, all Unown letters, sampled Spinda PIDs, portraits
and Colosseum DNA bodies. No base-species model was missing. Current authored
Lugia and Castform native/x4 assets pass their production loaders and integrity
contracts; the targeted shiny/artwork suite passes 110 tests. This is exhaustive
resource coverage, not a live encounter with every species.

Five silent Dolphin 2609b runs add 40 native screenshots: field, party and
summary pages in USA/Japan editions of both games, plus a USA XD Quick Battle
through active move selection. Read-only sampling confirms the current regional
perspective and orthographic branches after loading. The 2D menus retain their
proportions inside the wide viewport. The test fixtures are existing v2.0.0 QA
images used to qualify the current display recipe, not a new randomizer-engine
playthrough. Native textures are used with 3x internal rendering. Some widened
views can expose the edge of a room or backdrop designed for 4:3.

Each run uses a copied memory card and an isolated profile with **No Audio
Output**, zero volume and mute overrides. No user Dolphin process is attached.
The source test images, source cards and Dolphin executable retain their
hashes, all owned processes close, and the original movies remain unchanged.

A second physical Windows PC is not available in this environment. Relocated
portable diagnostics on this PC do not replace that hardware check. On a second
PC, extract the complete Windows ZIP and run the following from its application
directory in PowerShell. Use a new report name for each attempt:

```powershell
$report = Join-Path $PWD 'second-pc-diagnostics.json'
Start-Process -FilePath '.\OrreRandomizer.exe' -WindowStyle Hidden -Wait -ArgumentList @(
  '--diagnostics', ('"' + $report + '"'), '--launcher-upgrade-check'
)
Get-Content -LiteralPath $report
```

The optional upgrade check uses two disposable synthetic runs and a temporary
shared runtime cache. It starts no emulator, downloads no packs and opens no
personal ROM or save. A successful report must include `successful: true`,
`frozen: true` and a successful `launcher_upgrade_check` for both games.

### Existing game-folder migration replay (2026-11-23)

Four existing test folders were copied for the follow-up: Colosseum and XD
folders created with 2.0.0, and two HD folders created with 2.0.4. Emulator and
shared-cache paths were isolated before testing. The upgrade APIs were loaded
from the authenticated published Windows executable; all 203 production
Python files matched its build record after line-ending normalization.

All four upgrades to 2.0.6 passed. Before starting Dolphin, hash comparisons
verified 2,542 protected existing files, including ROMs, cards, controls,
settings and texture references. Seeds and pack pins stayed unchanged, backup
receipts were created, and repeating each upgrade changed nothing. The native
launcher stubs also started the exact published cached runtime offscreen.

The 2.0.0 copies loaded existing validation cards through their upgraded run
profiles. Field, party, summary and move pages were checked in both games;
Colosseum also reached Miror B.'s scene and battle introduction. Its party
portraits were checked in both 4:3 and 16:9 after allowing texture loading to
finish. Captures taken immediately after opening the party can precede the
last portraits becoming visible.

The original cards in the two 2.0.4 test folders were initialized but contained
no Story Mode progress. Their unchanged copies produced the game's own
no-saved-data message. Intact backups were retained, and separate known-positive
validation cards were used for supplementary resumed-game checks. This does
not certify continuity of a personally played 2.0.4 campaign.

Both HD copies then loaded those validation cards with their pinned packs at
3x internal resolution. Party portraits, summary and move pages were checked;
XD's ability page and return to the field were also captured. Read-only RAM
samples confirmed the expected display hooks after initialization. Sampled
host-process peak working sets were about 1.0 GiB for Colosseum and 1.25 GiB
for XD; these short runs do not establish a memory-leak or VRAM budget.

The 21 targeted game-folder and display tests passed. Final hash comparisons
confirmed all four source folders and their source cards were unchanged, as
were the copied ROMs and manifests. No product-code change was needed for
these checks. The initial legacy DTM bootstrap failed before gameplay;
subsequent checks used normal boots and isolated controller input instead.
Large temporary ROM, runtime and texture-view copies were removed after
verification; validation cards, screenshots and reports were retained.

These are bounded compatibility checks on existing images, not a complete
campaign or a live encounter with every species. Native emulator screenshots
and private preservation reports retain the evidence. No personal Dolphin
window was controlled, and the opening movies stayed inside unchanged ROMs.

### Launcher speed and display follow-up (2026-11-20)

The v2.0.5 checkout exercises 1,548 tests across 164 isolated modules. The
development sandbox blocks one Windows junction fixture; its complete
15-test module passes with normal user permissions. Release CI also runs the
suite from the extracted source archive, without the local game dumps.

The targeted launcher suite passes 47 tests, with 29 additional HD-folder and
dependency integration tests. All 12 game/language launcher layouts fit the
fixed 1,100 x 800 window. Updated English launcher screenshots use the actual
Qt widgets and demonstration folder names.

Read-only audits match the perspective hook, orthographic return, empty stub
space, r2 and read-only 0.75 constant in all six supported revision-0 executable
layouts. Independent PPC tests check the emitted matrix correction, camera
aspect calculation, branch targets and reverse patches. Wide mode does not
use game variables or BSS space for new constants.

Silent Dolphin 2609b checks use private profiles and test-image hard links
that are removed afterward. In Europe Colosseum, the final 300% hold/toggle
produces about 150 VI/s, with about 50 VI/s after release and 25 VI/s while
slowing down. Europe XD checks the final 200% target at about 100 VI/s and
returns to about 50 VI/s. Both final widescreen hooks are observed in live
memory. Colosseum's native summary menu retains its proportions in 16:9;
the 4:3 check restores the native instructions and fills a 2,560 x 1,440
borderless window with side bars. These checks do not certify every camera
or menu in a full campaign, nor a native visual pass of every region.

A further XD 4:3 run confirms both native projection instructions, 200%
acceleration and release to 100%, with no source-image change.

The QA audio backend produces no output; volume and mute overrides are also
applied, without a music companion. Image hashes remain unchanged and owned
test processes are closed after the bounded checks. The launcher's stock
Dolphin speed changes remain stepped; hiding OSD does not make them atomic.

### Multi-seed and ancillary-menu follow-up (2026-11-20)

Before the launcher changes, the local suite passed 1,539 tests across
163 isolated modules. Three symlink checks are skipped because this Windows
account cannot create them.
Native audio FIFO compilation and execution pass with the localized compiler.

The offline matrix checks 44 production patch plans: 32 desktop-preset cases,
six unchanged controls and six advanced boundary cases. Both games use Europe,
USA and Japan originals. Each European preset is checked with four seeds,
including Unicode and the maximum accepted seed length. Shared seeds reproduce
their species, abilities and item draws across the supported regions.

Checks read the final DOL, REL and archive members. They cover the default
replacement-family rules, excluded legendary draws, retained species,
original shop Balls, varied randomized treasure contents and unchanged movies.
Reusing a source after a randomized plan restores all 74 native Colosseum
treasure records for the Pokemon-only preset. Script interpretation also checks
Adelbert's contact, gift and Master Ball gates and the bonus quest's eligibility
across purification counts. These are offline state checks, not 44 campaigns.

The final Bingo lookup fix is checked separately from that matrix. XD's fixed
rentals use their original species traits through both native lookup paths.
Final Europe, USA and Japan patch comparisons reproduce the
previous control plans exactly outside the DOL; all 116 compared archive
replacements, including the REL, remain byte-identical. The seed draw algorithm
is unchanged. Independent instruction execution covers the two hooks, complete
object-accessor prologue/epilogue, ordinary encounters, rental battles, Bingo
menus and invalid or uninitialized overlay stacks. The second selector shares
the original table rather than allocating another copy.

A muted European Dolphin replay uses a production-generated XD ISO with types,
abilities and statistics randomized. Battle Bingo retains Dragonair's Dragon
type, Shed Skin and 81 HP, and Charmander's 68 HP. The replay covers the card
menu, grid, one victory, EP consumption, a Master Ball capture, Treecko's Grass
type and Overgrow, voluntary exit and return to the field menu. A native save
made during the preceding test reloads normally before this replay. It does
not qualify completion of an entire Bingo card or its full-clear reward.

Further HD menu replays use existing regional QA images and newly prepared
texture caches. Japanese XD covers VS artwork, the Group Battle configuration
screen, Quick Battle team selection, battle HUD, surrender result and menu
return. Japanese Colosseum covers the main and Quick Battle menus, difficulty,
four-Pokemon selection, a double-battle HUD and move menu, surrender result
and menu return. Group Battle is an on-screen check; no physical GBA link or
multiplayer session is claimed. Original ROMs, donor cards and personal
emulator profiles remain unchanged. Startup movies retain their original files.

There is no second physical PC test or uninterrupted full-campaign playthrough
in this follow-up. Source, instruction, checkpoint and menu checks remain
separate from those qualifications. See [HD coverage](HD_COVERAGE.md) for native
artwork fallbacks and the separate, unchanged Genius Sonority startup movie.

### Encounter columns and XD portrait shapes (v1.2.25)

The complete local suite passed 944 tests across 110 isolated modules. Two
Windows symlink checks are skipped because this host cannot create those links.
All four Rust codec tests passed. Checks cover the displayed Shadow roster
numbers, unchanged engine IDs, three-column gift and Poké Spot tables,
six-language acquisition conditions, wrapped text, pixel scrolling and circular
XD placeholders and roulette portraits.

Nine English README captures use the actual application and read-only original
inputs. They include known-only encounters, both games' full starter, Shadow
and gift previews, and XD's location/rate column. Each image has its capture
version, settings, dimensions and hash recorded in the media manifest.

Separate muted Dolphin instances used European test ISOs built by the current
production pipeline and copied, deliberately staged checkpoints. Colosseum
checks covered normal and shiny Shadow Lugia in battle, Psychic and Shadow
Rush. XD checks covered the shiny XD001 presentation, both Shadow Lugia
palettes in battle, Protect and the shiny Lugia's Shadow Rush. These observations
confirm the exercised entry, idle and move animations; they do not cover every
move, all 17 animation slots or a complete playthrough. Original input, donor
card and emulator hashes remained unchanged. Personal profiles were not used.

### Known-only automatic previews and retained properties (2026-11-16)

The v1.2.24 full local suite passed 938 tests across 109 isolated modules.
Two Windows symlink checks are skipped because this host cannot create those
links. All four Rust codec tests passed. The rebuilt Windows EXE passed 204
interface states in six languages, using isolated preferences and muted audio.
The public archive and embedded-code audit found no local user-home paths.


Additional checks cover the known-only worker, queued full requests, cancellation,
seed/source invalidation, single-click sheets, strict option types and shared
six-language copy. Original Colosseum and XD inputs were read without creating
an ISO or touching a save. The known-only entry points reject any call to the
full builders in integration tests; XD also rejects species draws and whole-deck
processing in that path.

For the two desktop presets, retained/manual sheets, shiny status and portraits
were compared with the full production preview on the same original and seed.
Further cases cover native starters/gifts/Poké Spots and the advanced property
override with a manually selected starter. No compared field differed.
On this machine, the desktop-default known projection took about 2.2-2.7 seconds,
versus 8.0-14.3 seconds for the full preview. Both include original-file checking;
these are local measurements, not a timing guarantee for other hardware or RVZs.

Profiles exported by the actual v1.2.23 source were imported into the changed
engine. Every in-memory patch offset, size and SHA-256 matched that source for
both games and both randomized presets. Synthetic tests independently check
that preserved species retain the same learnable TM moves after a shared TM
permutation, while other species still follow the requested rules.

Twelve muted Qt captures cover known previews in all six languages, plus two
advanced-settings captures. These are desktop/read-only checks, not new Dolphin
playthroughs or validation of future wild encounter levels. Poké Spot sheets
continue to list learnsets and compatible TMs without predicting four active
moves for a future encounter of variable level.

### Added-model artwork formats (v1.2.23)

The targeted group passed 165 tests across 15 isolated modules without skips.
It covers species-independent square/circular formatting, both Shadow Lugia
variants in the actual Qt list and sheet, separate DNA body validation, native
texture hashes and existing model/field identity selectors in both games.
Eight muted Qt captures cover both games, both variants and preview/sheet
views using real bundled portraits and synthetic encounter details. No ROM,
save or network access was needed for these captures. Native integration tests
read local originals where available. No personal save, live installed update
or Dolphin session was opened for this app-format correction.

The native XD face encoder still matches the published normal and shiny
resource hashes. The resource contract in [CUSTOM_MODELS.md](CUSTOM_MODELS.md)
also requires separate whole-body artwork and explicit native model, field
animation and scene validation for future additions. This does not claim
automatic compatibility of an arbitrary new model or new native playthroughs.

### Centered update progress (v1.2.23)

The affected desktop regression group passed 100 tests across seven isolated
modules. It covers update entry points, blocked game/profile actions and file
drops, previous disabled-state restoration, Escape/cancellation, preparation
errors and the verified restart handoff. The existing Windows-helper tests use
disposable apps to exercise installation, rollback and user-file preservation.

Forty-eight real Qt captures cover download, preparation, restart and error
states in all six languages at 1040×800 and 680×540. The active panel stays
centered without changing the window size; game selection is hidden and the
header controls are disabled. Captures use registered Windows fonts, muted
audio, private preferences and simulated networking. This is not a live update
of the installed application, and no personal ROM or save is opened.

### Preset copy and wild shiny defaults (v1.2.22)

The targeted local checks passed 84 tests across eight modules without skips.
They cover the shared preset policy, six-language copy, applied settings,
retained older profiles, Poké Spot selection and the native appearance branch.
The actual Qt settings screens were checked in 72 states: both games, all three
presets, six languages and 1040×800 / 680×540 windows. Text fit, translation,
scrolling, shared terminology and hidden preset-only notes were checked with
isolated, muted preferences and no ROM selected.

The Impeccable design index was regenerated from the current DESIGN.md and
checked against the Qt theme: 33 color tokens, six typography roles, eleven
component samples and all surface source paths. The maintenance diagnostic
reports no findings. Current product, design and interface-writing documents
now distinguish seeded encounters from XD's per-encounter wild rolls; UTF-8,
token references and local documentation links were checked.

Original European data was used for production-plan checks in both games.
Random draws exclude Legendary and Mythical Pokémon; protected original
legendary Shadows remain. XD's two presets install the five native wild-PID
hooks at 5%. Wild preview rows do not claim a seeded shiny status at this rate.
The PowerPC wrapper test exercises fresh RNG results on both sides of the 5%
threshold, checks the generated PID, and verifies stack/return preservation.
The appearance-script test preserves the game's encounter-shiny check and
selects a distinct shiny field model. These are automated checks, not a new
Dolphin playthrough or visual field-to-capture recording.

The subsequent muted Dolphin check used one unchanged European XD ISO and the
seed `poke-spots-five-percent-20`. Twenty fresh ordinary Rock Poké Spot draws
through the ISO-loaded native generation routine produced twenty distinct PIDs,
with one shiny on draw 3. One native special encounter was recorded separately.
No RNG or PID was forced; debugger calls stopped after the native encounter
state was written, before the PDA notification. This was a native generation
test, not twenty played battles, and this small sample is not a statistical
measurement of the configured 5% rate.

Observed normal and shiny Walrein encounters were then staged in separate
copied memory cards, preserving their species, owner and generated PID. With
the same ISO in ordinary Dolphin, both showed the correct field model, battle
model and portrait. Both were caught through the game's capture flow. Their
party records retained the observed PIDs and normal/shiny status, and native
summary screens confirmed their appearance. Six unedited comparison captures
cover field arrival, battle and captured summaries. Originals, source cards
and the candidate ISO were not modified. This check covers the European Rock
Poké Spot and Walrein; it does not claim a new visual pass of every species,
spot or regional disc.

### Fixed previews, shop Balls and Eagun framing (v1.2.21)

The final v1.2.21 local suite passed 910 tests across 106 isolated modules,
with two Windows symlink skips. The 55-test scene and reward regression group
also passed, including repeat-visit and native worker-visibility checks.
These counts describe source validation; release archives and the frozen
Windows executable are checked separately by the packaging workflow.

Production previews from original European data in both games were checked at
0%, 5% and 100% shiny rates. Fixed encounters use the exact calculated row,
portrait and sheet; randomized replacements remain unknown until requested.
Six-language layout checks covered both games and two window sizes, with a
12-pixel portrait/text gap and 8 pixels before sheet buttons.

Shop data checks covered 48 cases across all six supported regional discs,
including retained original Balls, randomized other stock, opt-out behavior and
independent Ball treasures. Twelve older-profile cases retained the previous
shop scope; the preserved European fixture reproduced its shop bytes exactly.
Original source files retained their hashes.

Muted Dolphin comparisons found that Eagun and Nascour already loaded distinct,
correct native models. The misleading dialogue camera showed Nascour during
Eagun's lines. The correction frames Eagun separately and turns him toward the
player, without replacing or recreating either actor. Native checks use a private
profile, the No Audio Output backend and copied QA memory cards.
The corrected European run completed the battle and captured bonus Shadow ID96.
After Nascour's departure, the partner's line and both Eagun lines kept all three
characters inside the same group shot. Original capture and purification totals
remained at 48, with the bonus capture recorded separately.
On a separate, explicitly staged post-quest QA card, native flag 2678 correctly
hid the original entrance worker. The earlier checkpoint had left it clear;
the ROM retains that original story condition unchanged.
Eagun directly offered and delivered a randomized purification gift after the
quest, without the extra thank-you bubble. Leaving the shrine through the cave
and returning used the ordinary map transitions and retained that gift receipt.
The remaining gift was then offered directly, with no quest thanks in front of
it. The staged checkpoint still contained an unclaimed native EIN File dialogue;
that original handoff was completed normally before the subsequent interaction,
without a ROM change or a progression bypass.

### Default policies and bonus encounter (v1.2.20)

Local source validation covered 883 tests in 104 isolated modules, with two
Windows platform skips. Three historical test fixtures were updated for the
new settings and their exact tests rerun; no product code changed during that
validation. Exported-source and executable checks are repeated for the release
build. Public runners skip the tests which require original local game files.

Native Colosseum data checks cover both presets, the three protected beasts,
all of their trainer aliases, independent bonus-team and final-Shadow switches,
and the original 48-member completion roster. XD checks use real European decks
and their western language variants to verify the three protected birds and
family reservations. XD001 retains its existing story protection.

The bonus scene's dialogue was checked with all 386 species names in each
playable language, including the separate US English bank. Its mailbox text
reflows replacement names; scene captions stay within three measured lines.

A muted European Dolphin run used an isolated copied QA card after the 48
original captures and purifications. Replacing the bonus Lugia with a shiny
Wailord changed its shrine model and the dialogue, including the partner's
instruction and the saved player names. The scene launched the native battle
and advanced its introduction state normally. The copied inputs retained their
hashes. This was a scene and battle-launch check, not a new complete capture
and purification playthrough for that replacement.

Earlier muted runs in both games checked normal and shiny Shadow Lugia before
and after actual purification, with appearance retention on and off, as well
as ordinary Lugia negative controls. Colosseum's Snag List navigation and DNA
displays were checked separately. These observations do not claim full native
playthroughs of all three regions.

### Interface parity (v1.2.1)

The local suite completed 527 tests with no failures (two platform skips).
The frozen Windows executable passed 456 UI states with bundled images, sounds
and music, using isolated preferences. Eleven dedicated parity regressions check
shared labels, help, pending rosters, multilingual search, loading/cancellation,
stale results, single-click sheets, report comparison and verified-plan reuse.

Real read-only previews were computed from the European Colosseum and XD
originals. XD's pending roster and internal/National Pokédex mapping were checked
against all three regional data sets. For XD, recommended, Pokémon-only and copy
preview plans matched freshly computed creation patches; copy produced zero
patches. Originals remained unchanged. No new Dolphin gameplay check was needed
for this presentation update; prior native-validation limits still apply.

### Creation-details follow-up (v1.2.2)

Additional regressions exercise both games' actual Qt worker callbacks and the
shared creation log. They check that validation errors never reveal Details,
including in all six languages, while genuine generation exposes it before the
first progress event. Success, failure, cancellation, navigation, translation and
a new invalid attempt preserve the intended visibility and reset behavior.

### Pokémon sheets (v1.2.7)

Read-only previews from the European originals for both games were rendered
in Qt to check original descriptions, move badge alignment and Shadow moves.
The bundled catalogs were checked in all six interface languages. Each language
has 76 ability descriptions and 355 Colosseum or 372 XD move descriptions.
These checks cover application presentation and packaging.

## Native Dolphin checks

Colosseum reports cover selected battles, starters, shinies and regional gifts:

- [Disc round trip](reverse-engineering/ROUNDTRIP.md)
- [Dolphin validation](DOLPHIN_VALIDATION_2026-10-31.md)
- [Shiny validation](DOLPHIN_SHINIES_VALIDATION_2026-11-01.md)
- [Seeded preview](SEEDED_SHINIES_VALIDATION_2026-11-02.md)
- [Regional gifts](REGIONAL_GIFTS_DOLPHIN_2026-11-03.md)

XD's [research report](reverse-engineering/XD.md) records regional structures,
story protections and native follow-ups. The corrected v6 runtime hook was
checked with matched European QA saves and separate original/modified images:

| Measurement | Original | Modified |
| --- | --- | --- |
| Vivid Scent, Rhyhorn's Heart Gauge starting at 6000 | 5700 (−300) | 5100 (−900), purification ×3 |
| First measured EXP award in the same trainer battle | 165 | 248, EXP ×1.5 |
| Last measured EXP award | 91 | 137, EXP ×1.5 |
| Total EXP gained by each participant | 522 | 785, rounding per award |

Both battles and the purification flow returned normally. Original ROMs,
personal saves and personal Dolphin settings were preserved. The v1 preset
alignment changes which existing options are selected; it does not change these
native hooks.

## Full-Pokédex Poké Spots (v1.1.0)

The local suite ran 510 tests, with 508 passing and two Windows-specific skips.
The full encounter draw and Duking request synchronization were checked against
the European, US and Japanese originals, including all native text-bank patches.
The same seed produced the same nine species across regions. A separate European
ISO passed full output-byte verification and DolphinTool's disc verification;
its encounters matched the preview. Keeping gift rewards unchanged still updated
the requests. Both preview lists were checked in all six interface languages.

The published RC2 source archive supplied an independent v6 reference. Its two
exported XD presets produced identical ISO patch bytes under v6 and v7 when
imported with the native Poké Spot shuffle. New full-pool draws have separate
keys; the older draw domains remain unchanged.

These checks validate data, text, previews and disc construction. A newly played
Duking exchange and full campaign for each possible draw are not claimed here.

### Pending Poké Spot encounters (v1.2.15)

In muted French PAL Dolphin sessions, the Spot Monitor registered a new
Vulpix at Rock with a 0% wild shiny rate, and new shiny Taillow and Sentret
at Oasis and Cave with a 100% rate. The test cards started just before the
encounter timer. After saving, separate copies loaded the pending encounters
at their respective spots with the rate reversed. The on-field message and
model matched the battle species. All three captures were saved, and the
captured entries retained the exact pending personality and owner IDs.

### Phenac dialogue replays (v1.2.15)

Muted French PAL sessions used separate copies of a player save, prepared at
the two relevant story states. The boy outside the Pre Gym cheered for Chinchou
and then explained he was imitating Justy. The first battle against Folly used
Slakoth and Ekans. The game displayed both names in his defeat line, followed
by the native continuation. The output ISO’s `openingdemo.thp` matched the
original disc byte for byte.

## XD Shadow shiny unlock (v1.2.0)

The [dedicated report](XD_SHADOW_SHINIES_VALIDATION.md) records guarded patches
for all three regions at 0%, 5% and 100%, 83 preview decisions and portraits,
and controlled native Dolphin calls. Native PID generation, player ownership,
capture metadata and the purification state transition retained the expected
shiny status. This is function-level runtime evidence, not a newly played
capture-to-purification sequence. The current suite and relocated Windows app
passed 516 tests (two platform skips) and 204 UI states respectively.

## Shadow Lugia replay (v1.2.10)

The [French PAL replay](XD_SHADOW_SHINIES_VALIDATION.md#shadow-lugia-in-v1210)
covers the final scene, a native capture, both final battles, purification in
the chamber, and reloading the purified shiny Lugia from the PC after a full
emulator restart. It used the default preset at 5% and prepared test cards.

## Default preset campaign checkpoints (v1.2.10)

Fresh French PAL games used separate, blank cards and the desktop Pokémon +
moves preset. In XD, seed `xd-final-0` passed the opening simulator battle.
The first lab save contained the reported level 10 Larvitar and its four moves.
In Colosseum, seed `orre-campaign-preset` started with Dratini and Oddish and
passed the opening fights at Outskirt Stand and Phenac City. After the Phenac
fight, Gafar's French dialogue still named Whismur, although he used Nincada
and Seedot. The rescue scene continued and the game saved normally at the
Phenac Pokémon Center. These two checkpoints cover the opening of each game.

## Phenac victory dialogue

The post-battle message uses the final species from Folly's two team slots.
If they are different, it names both in team order. The first page uses the
ROM's localized species names and the following page is preserved byte for
byte. Verification covered all five European language banks on two seeds and
the American English and Japanese banks on one seed. Only the target message
pointer and its appended replacement changed in each bank. A European
no-change build matched the original ISO's SHA-256.

Three fresh French PAL runs in muted Dolphin played through the opening
battles to the victory message. Gafar named Nincada and Seedot on
`orre-campaign-preset`, Ekans and Zigzagoon on `phenac-dialogue-2`, and
Whismur on the no-change build. The rescue sequence continued after the new
line on `phenac-dialogue-2`. A separate rebuild using the earlier campaign's
exact options and seed reloaded its test card and reached the Phenac Colosseum
reception.

The XD campaign test card reloaded at the simulator with seed `xd-final-0`.
The next lab cutscene completed, the player reached the regional map and
returned, and the game saved outside the lab on the copied card.

## Dialogue that follows a randomized species

The audit extracted 494,940 native message entries from the European,
American and Japanese retail discs of both games. The count includes menu
text, language variants and duplicate banks. Native trainer tables and
field scripts were used to review references to battle teams, including
references expressed through types, moves or abilities.

Colosseum updates the Johto starter rematches, related PDA mail and other
Shadow reports, plus Gafar's first battle, the Phenac Gym opponents and the
Snagem Hideout rematches. XD covers both lab outcomes, Mt. Battle and
Colosseum opponents, Eagun's battle and the final Shadow Dragonite. The
Gateon Port sailor can offer an evolution item to a player who started
with another species, so that branch no longer assumes they released Eevee.
Atill's Teddiursa remark reads Atill's team. Naps's tutorial has its own patch. The
Mt. Battle remark about Castform and Wailord reads both final team slots.
Remarks about type themes, abilities and move combinations are adapted when
the randomized battle changes their premise.

The direct trainer message IDs were cross-checked against the native party
tables in all three regions of each game. Four Colosseum battle messages
named species absent from their original parties. Rows 190 and 362, linked to
battles 192 and 364, use the same placeholder party at slot 238. Their revised
introductions avoid naming a species or move. Both of Reman's chants now use
the first two Pokémon in trainer row 655. Function 32 of `D2_cloud_3` selects
one of these chants for the first opponent. The patch updates the fight bank
and its Mt. Battle copies. Fixed scene actors remain separate from trainer
dialogue patches.

The follow-up audit included field dialogue and remarks that imply a team
without naming its Pokémon. Candidates were checked against the speaker's
native party, moves, types and abilities, plus the script branch that displays
the message. Checking those links distinguishes a real team strategy from a
trainer's personal preference, a fixed story actor or an unused message.
The party used for dialogue is the final one after team policies. For example,
Colosseum updates Folly's line when the fully evolved opponents setting alone
turns his Whismur into Exploud.

Toti's introduction and defeat at Pyrite keep their dance theme when her
two parties still have dance moves. In XD, the Mt. Battle field lines account
for real team details, such as Gratin's trapping strategy, Ebilo's flower and
butterfly pair, and Tulon's Rain Dance. The Orre Colosseum lines distinguish
changes to party composition from changes to the moves or abilities a tactic
requires.

The follow-up used seed `orre-dialogue-context` on all six verified retail
discs. Both randomization presets, a moves-only configuration and the
unchanged preset were checked for each game. Colosseum also ran with only
fully evolved opponents enabled, and XD ran with only types and abilities
randomized. The emitted language banks preserved page counts for the new
edits and added no explicit line breaks. The unchanged preset emitted no
patches. Width estimates also covered the longest pairs of species names in
the new XD field lines.

Muted PAL Dolphin runs replayed Lola's introduction and defeat in Pyrite on
a copy of the personal Colosseum card. In XD, copies of the Mt. Battle QA card
rendered the new zone 13, 66 and 67 lines. Zone 66 named Machoke and Graveler,
which both appeared in the battle. The test images placed the player near the
targets and invoked the native booth scripts for the XD encounters. The
protected source cards and personal profile matched their original hashes
afterward.

### XD Battle Simulator

All 12 lessons use fixed rental teams. The advanced species settings used to
change their types, abilities and base stats through the shared species table.
Virtual battles now use the retail table for those rentals. Normal battles
continue to use the randomized table. The opening simulator battle and Battle
CDs use the same virtual battle modes.

Generated builds of the European, American and Japanese editions preserved the
12 rental teams and their original lesson text in the six playable languages,
with types, abilities and base stats randomized outside the simulator. A test
runs the regional PowerPC hook before, during and after the virtual encounters.

In muted Dolphin, the French PAL lesson on matching Pokémon and move types
completed with Rattata using Quick Attack to defeat Makuhita. The same build
uses Electric-type Rattata in the adventure, while the virtual lesson used
its original Normal-type data.

Checks on all six discs with seed `dialogue-audit-1`, and on both European
discs with `dialogue-audit-2`, found no added line breaks in the changed text.
Where a longer name could crowd the lab or Phenac dialogue, the patch
shortens the sentence within the native layout. Two European no-change
builds matched their respective original SHA-256 hashes.

In muted Dolphin, the French PAL Colosseum build loaded an isolated copy of
the personal card and opened its PDA inbox. The original card was verified
unchanged. In a new game with seed `orre-campaign-preset`, Gafar's defeat
line read “GAFAR: NINGALE et GRAINIPIOT K.O. !” on one line, matching his
two Pokémon in battle. The French PAL XD build completed the opening simulator
fight with seed `xd-final-0`. Both lab dialogue pages named Larvitar
(`EMBRYLEX`) in the native box. In a separate muted PAL replay with seed
`dialogue-audit-1`, the player fought Rodolphe in Mt. Battle zone 82 on a
prepared copy of the XD test card. His post-battle dialogue read
“Mon duo, CHARMINA et GROLEM !”, the two team slots that originally held
Castform and Wailord. The line fit the original box on one line. The four
Colosseum battle message rewrites were checked in the regional ROM data,
including each copy in the Mt. Battle archives.

For v1.2.12, a muted French PAL replay used a copy of a test save with
Larvitar as the starter. The sailor's Water Stone and Moon Shard
explanations both referred to an Eevee. The game confirmed receipt of
the Moon Shard. The item dialogue was also checked in the other language
banks on the European, American and Japanese discs.

## Limits

Selected scenes and synthetic fixtures do not prove a complete playthrough or
balance across all seeds. No full campaign or second physical Windows PC is
claimed for v1.2.0. These are additional coverage opportunities, not completed
checks. Distinguish observed game failures from limitations of prepared QA scenes.
