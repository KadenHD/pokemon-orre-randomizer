# Colosseum's optional postgame Shadow Lugia

Nascour returns near the Relic Stone after all **48 original
Shadow Pokémon have been captured and purified**, once Eagun's original story
scenes have finished. His six-member endgame team has five Pokémon at levels 65-69 and a fixed
Shadow Lugia at level 70. With trainer randomization disabled, he keeps his
original Gardevoir, Xatu, Dusclops, Walrein and Blaziken. With it enabled, the
five ordinary members are seeded, fully evolved replacements. The new trainer,
actor and battle do not replace an existing story encounter.

The bonus uses **XD's actual Shadow Lugia geometry and animation tracks** through
conditional display resources. Its base form retains the original dark texture
colours. Its shiny form uses the requested custom white body, dark belly and red
eyes, selected from the Pokémon's actual saved shiny identity. The Pokémon remains Colosseum species 249 with
its native saved personality and Shadow ID 96. Normal Colosseum purification
restores the ordinary Lugia model, or shiny Lugia when its saved identity is
shiny, unless the optional appearance-retention setting is enabled. XD's special Purify Chamber requirement does not apply. See
[`postgame_lugia_model.py`](../../orre_randomizer/engine/postgame_lugia_model.py)
for the model conversion, guarded display hooks and asset provenance. Five guarded model hooks cover battle/menu creation, resource selection and
the compact asynchronous Snag List requests. Twelve portrait hooks cover
native request, callback, sprite, draw and battle paths. All regional call
sites are checked against their original instructions before patching.

The PKX metadata must also follow Colosseum's scheduler. XD stores clip timing
as floating-point seconds, while Colosseum expects integer 60 Hz ticks; leaving
float bit patterns in place caused an indefinite entry animation during QA.
The converter rounds seconds x 60, maps XD track kinds 1/2 to native kind 0
and missing kind 0 to the native wait kind 1, and supplies Colosseum's scheduling
flags at `+0x08`. XD bone IDs, mesh, textures and animation DAT tracks are
preserved. Native PAL evidence includes loader `0x801E1E5C`, scheduler
`0x801E2F0C` and idle handler `0x801E39D4`. Corrected entry and damage animations
have passed the native battle test.

The battle model call also receives a minimal stack record without the Shadow
ID. Its wrapper retrieves the full combat record through the native `0xD6`
context and `0xCC` Pokémon getters. Target-selection and capture views can pass
another reduced record, so the common resource loader additionally matches
the exact native generated PID of a Lugia Shadow ID present in the final ROM.
The generic display layer covers randomized Shadow slots as well as ID96.
Purification normally selects ordinary Lugia; the shared advanced option can
retain the Shadow model instead. Full records without Shadow provenance get an
explicit ordinary-model marker, including when a PID matches a saved Shadow.
Substitute and unrelated personalities stay on their original path. No display
hook rewrites a saved PID or owner ID. See [the general appearance policy](SHADOW_LUGIA_APPEARANCE.md).

Portrait keys `0x7FF1` and `0x7FF2` select the ordinary/shiny frame in the
appended `0x7DF61200` face atlas. The original face-key calculations are guarded
at every regional native request, callback, sprite, draw and battle call site.
Purified Lugia returns to the original species face path.

## Progression and persistence

| Field | Value |
| --- | --- |
| Reserved native Shadow ID | 96 |
| Native capture flag | 2221 |
| Native purification flag | 1357 |
| Appended trainer ID | 820 |
| Appended party slots | 5510-5515 |
| Appended battle ID | 566 |
| Lugia level | 70 |
| Shadow-table counter at `+0x08` | 200 |
| Observed native initial heart gauge | 5000 |
| Shadow catch-rate override | 45 |
| Appended shrine actors | 4 (Nascour), 5 (Shadow Lugia) |
| Nascour field model | 35, native Nascour appearance |
| Nascour interaction | CMS function 13 |
| Explicit battle music | 1100, native Cipher Admin theme |

Eligibility checks seven existing Eagun story flags, including the native
P★DA-number exchange, and the exact original
48 capture and purification flags separately. The bonus cannot substitute for
a missing original Pokémon. Its scripts never set capture or purification flags.
Custom interactions also pause while Eagun's native Master Ball handoff is
pending. His home actor and original dialogue always remain unchanged. The
native conditions and the legacy obstruction are documented in
[`EVENT_STORY_SAFETY.md`](EVENT_STORY_SAFETY.md).

Winning without snagging Lugia produces a reminder and allows another attempt.
Losing also leaves the encounter available. After a native capture, Nascour
acknowledges Cipher's failure and walks to the shrine exit before being removed;
the partner and Eagun respond afterwards. The capture flag drives permanent
disappearance when the map loads again.
During the confrontation, Eagun turns toward the player during his lines and has
a separate camera shot; Nascour's lines return to the confrontation view. After
Nascour leaves, all three remaining lines retain the aftermath group camera;
switching back to the arrival camera cuts the heroes off at the right edge.
Both actors retain their native
models. A misleading shot of Nascour during Eagun's dialogue initially suggested
a model swap, but the live actor resources, model descriptors and joint pointers
were distinct and matched the original assets.
While Nascour is present, Eagun asks the player to snag Lugia instead of
repeating the original purification requirement. The optional event-gift handler
remains available before the threat and after the capture; its original body
is retained and reached through a wrapper.
After capture the wrapper now goes straight to that gift handler, with no extra
quest thank-you bubble on repeated interactions or room reloads. If accessible
event gifts are disabled, Eagun gives the localized purification advice instead.
The gratitude remains in the final scene.

The original worker at the entrance uses the native disappearance flag 2678.
Its visibility branch at shrine CMS `0x32D..0x37C` is unchanged in all three
regions. An incompletely staged QA card left that flag clear and made him
visible with his old Mt. Battle dialogue; this was a test-checkpoint issue,
not a new actor or a quest visibility override. Regression checks retain both
outcomes of the original condition without rewriting story flags in the ROM.

The native Ho-Oh checker still reads its fixed original 48-ID list. In the
European executable its routine is at `0x801F2C0C`, the list at `0x803C26C8`, and
each Shadow record supplies its purification flag at `+0x14`. The loop ends at
48. The bonus does not alter this list or extend the save format. The two global caught/purified counters otherwise scan all 96 reserved IDs.
Counter-local guards exclude bonus ID 96 from those original totals, leaving
individual flags, party Shadow counts and normal purification unchanged. The
Snag List includes the bonus as a separate 49th possible entry.

## Appended native data

### P★DA notification

The optional patch also appends mail ID32 to the separate `mail` REL in
`common.fsys`, increasing its record count from 32 to 33. All 32 original records,
their IDs, attachments and read effects remain intact. The new record uses the
retail Eagun sender ID `0x3ED3`, with new subject/body IDs `0xF0030` and `0xF0031`
in the localized `pda_menu*.fsys` message banks. Text follows the six playable
languages; original opaque strings and other PDA resources are retained.

Version 5 hooks the terminal `floorLink` call inside native `worldMapMain`.
The map resets its ride marker on entry; only the motorcycle animation sets it.
The wrapper requires that marker, the seven story flags and all 48 original
capture and purification flags. A pending Master Ball handoff takes priority.
An eligible completed ride sets a transient word in the appended DOL reservation.
All paths preserve the destination and entry arguments and tail-call original
`floorLink` exactly once. The first unconditional call in field `_floorUpdate`
then runs its original callee before checking the pending trip. Once any retail
mail notification has finished, it clears the word, rechecks eligibility, sends
ID32 and confirms receipt before advancing mission phase 0 to 1. Existing receipt
is reused without a duplicate; phases 1 and 2 are never reset. The pending word
starts at zero and is never stored in the save.

Sending before the floor change, as version 4 did, inserts the mail correctly
but loses its notification: the native close callback terminates that alert.
Deferring the entire send to field update preserves the native envelope and
sound without replaying an alert or inserting the same mail twice.

The automatic predicate always rejects ID32; all original IDs tail-call the
original predicate with unchanged arguments. The row also disables the native
send-all scan. Reading the message has no story effects. Walking callbacks and
hero initialization remain byte-identical to the original executable.

The native mailbox and read bitmap support 512 IDs. The PDA allocates its list
from the actual mailbox count and computes pages dynamically; 33 is not a new
save format. The travel call sites are PAL `0x80027574`, USA `0x8002598C` and Japan
`0x80025B74`. The automatic-mail guard sites are PAL `0x801D7098`, USA
`0x801D2A18` and Japan `0x801CE3DC`. Arrival hooks are PAL `0x801172C8`, USA
`0x80113A24` and Japan `0x801112F4`. Complete native world-map, ride, destination,
field-update, state-access and sender code fingerprints are checked before installation.
Static checks cover all three originals and seven localized banks; PPC execution
tests cover eligibility, volatile-register clobbers and destination preservation.
The native mailbox and six localized text banks have separate validation;
runtime findings are recorded below.

The earlier walking-based implementation (versions 2 and 3, superseded by
version 5) exposed an initialization dependency:
`mailMainInit` registers `cbStep` only through `mailInitMailbox`. Loading a save
did not register that callback. In the private PAL test, hero callbacks at
`0x80474190` contained poison, friendship and purification, but no mail callback
`0x801D7058`, even after more than 100 world units of movement. Calling mailbox
initialization would erase saved mail, so the patch never does that.

Version 2 registered a bonus-only callback at the end of `heroMoveAllInit`, after
its unchanged native poison and friendship registrations. Its guarded epilogue
sites are PAL `0x80134870`, USA `0x80130644` and Japan `0x8012DD80`. The relocated
load and original epilogue retain the caller's LR and r29-r31. The extra callback
checks the same eligibility predicate, then calls native `mailMainSendByScrpt`
with ID32 only. Its saved receipt prevents repeats across steps and save loads.
It does not register the native mail scanner or enable additional retail mails.

A muted PAL replay on a new production ISO confirmed that registration on save
load. Walking delivered ID32 once, displayed its unread envelope, and opening
the mail set the native read bit without changing story progression. Additional
walking retained exactly one copy. The French sender and body displayed in the
native P★DA; the subject was then shortened to `SOS Relique` after the longer
version clipped in the inbox. All six translations now use short subjects.
The shortened French subject was also rechecked in the native inbox and fits
its column. The text-body and native sending behavior remain unchanged.
Full original hero-init, callback-registration and sender function hashes are
checked in all three regions. PPC tests execute registration through the native
epilogue, test ABI clobbers, and cover eligible, already received, missing phone,
captured Lugia and pending Master Ball cases. The callback address is included in
the production report for native runtime verification.

Versions 4 and 5 remove that registration and its walking callback entirely.
The shrine's idle loop rechecks actors 4 and 5 after its existing yield, then
returns to original offset `0x2056`. The dedicated mission phase keeps them
hidden after an in-place final purification. Receipt on a completed motorcycle
trip activates them for the next visit.

### Staged shrine encounter

The warning is sent only after a completed motorcycle trip to another area.
Completing purification48 in place leaves mission state0 and both added actors
hidden. The travel wrapper confirms that native mail 32 was inserted before
setting state1. It also recognizes an existing mail 32 on an older save during
an eligible trip, without duplicating it or changing an introduced mission.
Reading the message itself has no story effects. Ordinary room changes,
whiteouts, cancelling the map and same-area choices do not activate the mission.

The first eligible visit uses native camera, movement and dialogue commands.
Both heroes approach the confrontation; the partner identifies Lugia's aura,
Nascour explains Cipher's attack on the Relic Stone, and Eagun defends the
shrine. The first battle follows that conversation. After a victory without a
snag, the commander remains available through his ordinary interaction.

The native actor initializer runs while the map is still fading from black.
The added scene therefore starts only after the original idle yield, not from
the initializer or the conditional original purification scene. Room-local
global 3 marks that first pass even when the event is ineligible; reaching the
last purification while already standing there never teleports the player into
an arrival sequence. Globals 0 and 1 retain their original storage and values.

Room-local global 2 protects staged visibility. It is reasserted immediately
after the native battle returns, along with the arrival marker, so an idle
refresh cannot hide Nascour midway through his departure or start a second
arrival after an unsuccessful snag. The CMS never writes these temporary
markers to the save. The saved capture flag remains authoritative on reload.

Native defeat reconstructs the room before the old encounter thread can
restore its temporary markers. A dedicated two-bit native save field now
tracks the mission independently of other battles: 0 before activation,
1 after mail receipt on a completed motorcycle trip, and 2 after the introduction. The
introduction writes state 2 only after its final dialogue and before battle152.
A defeat in that battle therefore leaves a manual retry available without
replaying the introduction. Losing another battle cannot suppress a first visit.

The appended descriptor is flag 3593, group 3, bits 6414/6415. All 3593 original
descriptors and their bit positions remain byte-identical. The new field shares
the last used word with the final retail flag: 201 used words before and after,
inside the original 384-word allocation. No saved-data offsets, serializer sizes,
original story flags or Shadow completion counters change.

Native command 61 starts a path segment and enables the model's automatic
walking animation. Command 69 sets its speed afterwards; command 62 waits for
movement and turning to finish. After capture, native command 59 restores both
heroes to the scene's approach positions before the first camera yield. This
keeps a manual retry's arbitrary player position out of Nascour's exit path.
Departure follows five points, first passing west of the lectern and then
along the centre of the walkable path, ending at Z125 outside the camera view
before hiding the actor. Earlier routes crossed the outer collision boundary
or passed too close to the lectern and the heroes. Both could trigger the
native 60-frame stuck-movement snap. Command 179 restores the original
room camera and hero following before command 33 returns control.

Lugia uses a separate room-local DAT under character model 69/resource
`0x009B0400`. It is converted from the same verified XD Shadow Lugia asset as
the battle model, with its actual Idle motion repeated in the field motion
slots. The production plan supplies its determined shiny status; the ordinary
and custom shiny variants share geometry, scale and staging. Lugia stands at
(-32,0,0), separated from Nascour's torso. Its initial heading is derived from
Eagun's installed position, so room reconstruction after a loss does not turn
it away from him. Native command 165 also turns it towards Eagun during his two
introductory speeches. After Nascour leaves, a separate over-the-shoulder shot
aims at the remaining group's centre from the original unobstructed camera
position. The hero, partner and Eagun turn towards one another before the last
three messages. Eagun's original
Pikachu/first-gift companion and its resources remain separate.

All six playable languages have their own dialogue. The native name controls
`FFFF2B` and `FFFF2C` resolve the saved hero and partner names. Source paragraphs
contain no manually placed line breaks; the message encoder inserts native
line-feed controls according to the dialogue width and glyph advances.

### Battle tables

Trainer 819 and battle 0 are native special entries and are left intact. The
patch clones the final numeric trainer, party and battle tables into an
extension of REL data section 4, then appends the new records. Counts become
821 trainers, 5516 party records and 567 battles. Existing records retain prior
randomization. Self-relocation aliases, section size, import-table location,
relocation streams and the REL v3 fixed-size boundary are updated together;
pointer-bearing numeric records are refused.

The trainer reuses Nascour's original localized name ID 4167 and native
battle presentation. Its battle copies the player's shrine rematch (battle 543),
retaining story/snatch mode, controllers and battlefield. When trainer randomization is enabled, the five ordinary
members use distinct evolution families where the selected pool allows it.
Generation, species and type exclusions apply to replacements. When disabled,
the original five remain unchanged, even if their species fall outside a
replacement filter. When enabling only the
bonus from Copy mode, its dormant generation switches permit all three
generations for the new team without changing the saved profile; species/type
exclusions and the legendary filter remain enforced. Current species data
supplies abilities, types and stats; trainer moves follow their selected rules.
The table always holds four regular moves: Aeroblast, Psychic, Recover and Hydro
Pump when unchanged, or four selected regular moves when randomized. Colosseum
inserts Shadow Rush itself. An early QA build incorrectly stored Shadow Rush
as the fourth regular move and retained it after purification; this is corrected
in the source and covered by a restoration-data regression test.

The common name banks remain unchanged. Nascour's five ordinary members clone
their corresponding original party slots 4111-4115; Lugia clones slot 4110
with four regular Lugia moves. Held items therefore follow the original member
and honor the held-item randomizer. Map REL section 3 gains separate fifth and
sixth actors for Nascour and Lugia; the native Nascour field asset is copied byte for byte from
`D4_casino_colo.fsys`. No Eagun actor is replaced.

## Scripts and localization

The shrine retains its original twelve functions. Optional gift handling uses
function 12 and Nascour uses function 13; globals move out of the expanded
function table. A separate visibility expression checks story completion,
original captures, original purifications and the bonus capture flag.
The shrine's existing idle loop also refreshes the added actor after its native
yield, using the dedicated mission phase as well as the original prerequisites.
It does not replay map setup or change the original actors. The guarded tail jump at
`0x25AB` runs the new visibility check and resumes the original loop at `0x2056`;
native player event processing and yield bytes remain unchanged. This refresh
has CMS semantic and original-script admission tests, plus the separate native
staged-encounter checks described below.

The event calls native battle function 152 with the option pair used by the
original shrine. Native battle result 2 selects the win-without-capture branch.
The actual native capture flag, rather than the battle result, selects success.

The staged encounter has nineteen dialogue messages in all six playable
languages (`0xF0050`-`0xF0062`). Speaker names come from each original common bank,
including Jakylla and Adelbert in French. The original organization names are
used, including GROUPE OMBRE in French and CRIPTO in Italian. Every spoken line
has a speaker prefix. The hero and partner use their saved names through native
message controls, including when the partner addresses the hero. Source text
has no manually positioned line breaks. The encoder wraps by glyph advance
within 420 pixels and reserves the maximum saved-name width; every new bubble
fits within three lines. Existing text payloads, controls and aliases survive.

## Validation scope

Automated tests cover all original purification counts, each missing original
capture and purification, all 128 story-flag combinations, the pending native
Master Ball handoff, capture success,
win-without-capture retries, losses, permanent disappearance, Eagun's separate
interaction, all six translations, opaque message payloads and REL alias/count
preservation. All three regional originals pass shrine/home archive rebuilding
with event gifts enabled and disabled (six combinations).

The European six-member native battle has passed with the corrected XD base
model, including entry and damage animations, Master Ball capture, Nascour
failure/departure dialogue, Eagun's congratulations and disappearance after a
cold restart. Native capture flag 2221 became 1 while purification flag 1357
remained 0. The captured Pokémon had gauge 5000 and a genuinely shiny saved PID.

The normal Relic Stone ceremony also completed: gauge became -100, purification
flag 1357 became 1, the National Ribbon was awarded, and the PID/owner ID were
unchanged. The ceremony displayed ordinary shiny pink Lugia. Gauge readiness
was an explicit QA precondition (5000 to 0 on a copied captured card); natural
heart reduction and Time Flute consumption were not claimed as observed.

The final level-70 capture and native purification also passed. The saved
PID `CF9DE894` and owner ID `ACC48BC9` retained their shiny XOR of 4. Lugia
kept held item 219, exactly matching the generated report, and restored all
four regular moves (177, 94, 105, 56). No Shadow Rush remained. The National
Ribbon was awarded. The ongoing battle displayed the white XD body and dark
belly; purification displayed the normal shiny pink model.

An independent native win without snagging also passed: both reminder lines
played, Nascour stayed present, and a second interaction restarted his battle.
The final level-70 source passed the real localized speaker-name, camera-facing
actor, Eagun-presence, departure and congratulations checks. A cold restart of
the final production ISO from the purified QA snapshot kept Nascour absent;
Eagun said "Thank you for saving us" in the selected native language. Lugia
retained the same PID, owner, held item, four regular moves and National Ribbon. The remaining
17-hook portrait and transient target-view replay is recorded separately.

Private evidence is under `build/v1220-lugia-qa/`. Tests use separate ISOs,
copied QA cards, a muted private Dolphin profile, controller packets local to
that profile and the original opening movie. The prepared 48 capture and
purification flags are test preconditions, not a claim of playing a full
campaign. Accelerated test-party stats are confined to the copied QA card.

After the story and mail changes, another muted PAL replay used a fresh
production ISO with the original six opponents at levels 65-70. The Master
Ball capture produced Shadow Lugia 96 at level 70, PID `EDECCAE4`, owner
`ACC48BC9`, shiny and with heart gauge 5000. Native flag 2221 was set while
1357 remained unset. Both departure lines played, Nascour disappeared and
Eagun congratulated the player. The captured party was read back from that
private process and archived as a new QA card. This later pass did not replay
the purification ceremony. Evidence is under
`build/v1220-story-driver-20261113/boss-final-01/`; the new portrait-backdrop
follow-up has its own rendering checks.

The final black-matte atlas was also reloaded with the captured native Lugia,
reordered to the first party slot without changing its Pokémon bytes. The native
party menu displayed the white portrait over opaque black, without the baked
violet disc or its thin rim. This is a rendering check on a copied QA card;
it does not claim another capture or purification.

### Staged-encounter replay, 14 November 2026

A fresh muted PAL/French replay covered the new entry cameras, approach,
eleven arrival messages, all six opponents, capture and the initial departure
sequence. The QA save names were Zack and Lina; native name substitution was
visible in the dialogue. Both the white Shadow Lugia field model and the
battle model matched the generated shiny identity.

The completed capture produced level-70 Shadow ID 96 with PID `5173767E`,
owner ID `ACC48BC9`, heart gauge 5000 and moves 177, 94, 105 and 56. Native flag
2221 was set and 1357 remained unset. Nascour reached the exit at
`(0, 0, 102.6)` before being hidden. The partner and Eagun then spoke, the room
camera returned, and movement worked again. A cold launch from a new encrypted
QA snapshot retained the same captured Pokémon, kept the encounter inactive,
and allowed movement. The original caught/purified totals stayed at 48/48.

A separate non-shiny replay covered victory without capture and a second
challenge. Six-language message layout and PAL/USA/Japan archive integration
are automated checks; this does not claim six native language playthroughs.
The earlier full test suite ran 788 tests with two environment-dependent skips.

A subsequent native defeat test exposed an automatic arrival/battle replay
after room reconstruction. An initial CMS103 result-3 guard was tested on a new
production ISO, then superseded by the dedicated mission state described above.
That initial native wipeout returned the healed player
to the shrine entrance with result 3, original totals 48/48 and bonus capture
flag 0. The idle resumed at `0x25A7`, with globals `[0, 0, 0, 1]`. Movement
changed the hero's X coordinate from 0 to 7.1245. Nascour and Lugia remained
present, and a manual interaction opened his challenge again. Evidence is under
`loss-native-v5/`; the original failed replay is retained under `loss-native/`.
The complete final suite then ran 789 tests successfully, with two Windows
symlink-privilege skips and no failures.

Private evidence and the silent verification video are under
`build/v1220-lugia-cutscene-qa/`. The video joins the mail validation with the
complete later capture pass, removes deliberate menu waits, and retains native
animation timing. Only the copied player's test party has accelerated stats;
the production boss still has six members at levels 65-70. The original
`openingdemo.thp` remains byte-identical, as checked by SHA-256. Personal ROMs,
saves and the user's playing Dolphin instance were not modified.

### Version 3 mail, retry and staging checks, 14 November 2026

The walking-mail timing in this historical replay is superseded by the
motorcycle-arrival checks below. The scene and battle changes remain in use.

A version 3 English replay starts with 47 original purifications. The real
last purification reaches 48 without receiving the warning or starting the
encounter in the shrine. The first walking step outside delivers mail 32 once
and advances the dedicated mission state from 0 to 1.

An actual loss against an unrelated native trainer preserves phase 1, so the
eleven-message introduction still plays on returning to the shrine. Losing
the first Nascour battle preserves phase 2, returns control and does not start
another battle. Talking to him starts the retry. Independent French native
replays also cover these two loss cases.

Movement telemetry exposed a remaining collision near the lectern on an
earlier straight first leg. The final build restores both heroes during the
battle-to-field transition and takes the five-point route described above.
The final native trace contains 790 samples, with a maximum sampled displacement
of 1.394 units and no teleport. Nascour reaches Z125 before being hidden; visual
review confirms his cape and hair have already left the frame. Lugia also
faces Eagun on a fresh room load, including the manual retry, rather than only
turning during his introductory lines.

After capture, the three remaining people face one another in a centred
over-the-shoulder shot. All three final replies are readable and complete.
The native idle resumes and player movement works. The captured Lugia is
level 70, shiny, Shadow ID 96, with heart gauge 5000. The original completion
totals remain 48/48. A cold reload of the captured QA card retains its identity
and mission state and keeps the bonus actors hidden; this was checked before
the final camera and human-facing adjustment, which does not execute on load.

The full suite ran 798 tests successfully with two Windows symlink-privilege
skips before the last staging refinements. All 64 focused scene, state, mail,
regional archive and collision checks pass after the final source changes.
Six-language layout checks and USA/Japan ABI/archive checks are automated;
native gameplay in this follow-up covers PAL French and English.

Private evidence is under `build/v1220-lugia-refinement-20261114/`. The English
video joins the purification/mail/two-loss recording with the final corrected
retry, capture and departure. It removes menu holds while retaining native
animation timing; it is not presented as one continuous take. Prepared QA
conditions and boosted auxiliary party stats are confined to copied cards.
The original opening movie remains byte-identical. No personal ROM, save or
running game was modified, and no RAM writes were used.

### Version 5 motorcycle-arrival validation, 14 November 2026

Separate muted PAL replays establish the negative cases: shrine-to-village
walking, cancelling the map and selecting the current area do not send the
warning. A real Agate-to-Pyrite ride on the final version5 ISO first delivers a
retail mail already due, then the bonus32. The bonus envelope is visible in the
loaded town, and its English subject, sender and full body display correctly.
Receipt advances phase0 to1. The native sender and inbox remain in charge.

The trip and arrival wrappers are executed in PPC tests with native-call
volatile clobbers. They cover all103 prerequisites, Master Ball priority,
existing receipt, notification contention, repeated field updates, failed
insertion, completed missions and destination/return-value preservation.
All three regional installs preserve every original executable byte except
the three reviewed call sites and appended-arena metadata.

Evidence, the 56-second English silent clip and test inventory are under
`build/v1220-lugia-travel-20261114/`. The inventory covers807 current tests:
805 passed and two Windows symlink-privilege skips. Execution was split after
the first aggregate run reached its eight-minute budget. The final29 targeted
mail/travel/state/scene tests pass. The original opening is byte-identical.
Regional runtime coverage remains PAL; USA and Japan checks are static and
automated. No personal ROM, save or running game was modified.

### Native whiteout return, 14 November 2026

A discriminating replay on an exact copy of the unmodified PAL ISO healed the
party at Phenac's Pokémon Center, saved at that Center's PC (room4/previous3/
entry2), then saved at Pyrite Colosseum's lobby PC (120/15/2) without healing
elsewhere. Losing Pick's ordinary rematch returned to the lobby PC, at
`32.08,0,-13.07`, with both party members healed. The temporary scenario override
remained disabled throughout. Thus the ordinary retail return in this test is
the last saved PC, even after a heal at a different Center.

The native return routine and all three direct caller functions remain
byte-identical in the final version5 production ISO. The older mission video's
shrine return was caused by its declared QA save coordinates39/37/0, not a new
production respawn rule. Exact observations and function comparisons are in
`build/v1220-lugia-travel-20261114/`, including `whiteout-routing-v5.json` and
`whiteout-center-pc-vanilla/evidence/`. No user save or personal emulator was
changed. This additional retail gameplay experiment covers PAL; the native
return selectors are independently qualified in USA and Japan as well.

## Format references

The native formats were cross-checked against pinned `CMTrainerPokemon.swift`,
`CMBattle.swift`, `Battles.swift`, `XGCharacter.swift` and
`CMScriptBuiltInFunctions.swift` in
[Pokemon-XD-Code](https://github.com/PekanMmd/Pokemon-XD-Code/tree/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0).
Exact regional originals and native fingerprints remain the admission authority.
