# Validation scope

This index records the v1.0.0 foundation and subsequent validation follow-ups.
Dated reports in `docs/` describe their named versions and scenarios; they are
historical evidence rather than the current feature specification.

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
