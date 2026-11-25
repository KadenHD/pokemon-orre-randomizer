# XD first-battle progression safeguard

Validated on 24 November 2026. This follow-up uses application version 2.1.1 and the unreleased
`xd-first-battle-progression-v19` engine. It addresses the first Chobin battle,
not the later rematches or Robo Groudon fights.

## Problem reproduced

A private European NEW GAME produced a level-10 Ditto with Transform and
three empty move slots. A copy of its native pre-Chobin save was used for a
deliberate defeat: Call alone let the opposing level-5 Seel win, with no
damage dealt to Seel. XD returned Michael to Kaminko's entrance. On v18,
approaching Chobin again repeated battle 222 before Jovi's scene could run.

Successful Ditto and Wobbuffet victories therefore did not establish that
passive starters could always progress. The separate
[fresh-start report](XD_FRESH_START_VALIDATION_2026-11-24.md) records those
victories and first captures without conflating them with this loss test.

## Narrow correction

The first battle still occurs normally. After a defeat, speaking to Chobin
again continues the original Jovi scene instead of forcing another battle.
Only the retry branch's four-byte battle-call instruction is replaced. Its
native stack cleanup, scene call and post-scene story write are retained.
The first-attempt and winning control flows remain unchanged; no new story
flag is introduced. Later Chobin battles are unchanged.

One shared reply originally assumed that Chobin lost. Its replacement avoids
declaring a winner, using his official name in English, French, German,
Spanish, Italian and Japanese. Western replies use two natural lines;
Japanese ruby, speaker and page controls are preserved. Native font metrics
confirm the replacement glyphs and line widths.

The safeguard is selected when gameplay settings can alter the early
combatants. Copy mode and cosmetic-only changes leave this script untouched.
It does not add moves, change the starter's species or PID, or guarantee a win
against an arbitrary team. The native first Snag remains a separate,
guaranteed capture without attacking.

## Automated and regional checks

- Original Europe, USA and Japan room archives are qualified by their complete
  hashes. All three scripts retain every byte outside the single retry call.
  All seven regional message banks are checked against their expected reply.
- Nine module checks cover the instruction contract, regional archives,
  localized reply, surrounding payload preservation and rejection of unknown
  input. Four integration checks cover activation and full serialized
  production plans for both randomized presets. Magikarp retains Splash only
  when natural starter moves are selected.
- Three migration checks import genuine v2.1.1 exports: seeds and options stay
  unchanged, the engine migration is reported, and historical challenge codes
  still require their original engine.
- The isolated suite completed 1,693 tests across 180 modules. Its initial
  Windows sandbox run refused junction creation in two fixture modules. Both
  entire modules passed when rerun with the necessary filesystem access
  (15 and 16 tests). Three pre-existing symbolic-link privilege skips remain.
  The final localized payload then passed all 16 relevant checks again.

The [regional starter campaign](REGIONAL_STARTER_VALIDATION.md) separately
records four actual USA/Japan startups on v18 and 128 valid production plans.
Those historical runtime checks do not claim to have played the v19 loss
branch on every region.

## Native runtime evidence

A muted European prototype replay used the copied native pre-Chobin card.
The initial battle occurred, Call caused a genuine defeat, and returning to
Chobin ran the Jovi scene without starting a second battle. His door unlocked
and a native save completed. That prototype exposed the win-specific reply
described above; its flow result is retained separately from the final
localized payload.

The final two-line candidate was then replayed in another private profile,
starting from a copy of the same native pre-Chobin save. Eight Calls caused
a genuine defeat against a full-HP Seel. Chobin's loss follow-up appeared on
returning to his door, followed by the new neutral reply on two lines. No
second battle started. The original Jovi scene, manor tour and conversation
continued, including the explicit **JOVI joined the party** receipt.

A native save completed after Jovi joined. The process was closed after an
18-second neutral interval. The final card was archived and hashed; the
generated ISO was verified and removed. All 28 original movie archives, the
original source disc and the native pre-battle card backup remained unchanged.

Private final evidence is under
`build/v212-starter-fix/final-neutral-loss/`: `flow-result.json`, the full input
history, `final-neutral-reply.png`, `49-jovi-joined-receipt.png` and
`final-native-save.png` in its evidence subfolder. The final ROM hash was
`64764b3655f0304caf37e9e1f2544252acad9a84563120eec93b9efde0bfaba5`;
the archived card hash is
`275c1486497707e46e802338521be1eb0abfc7c74850055eac879711a4561149`.

This final loss replay covers European English through Jovi joining and
saving. The fresh-start trials separately cover the winning route through the
first Snag. Other languages and regional loss branches have source-contract,
glyph and line-width checks; they are not represented as full Dolphin
playthroughs.

## Preservation

Tests use private Dolphin profiles and copied or newly created cards, with
No Audio Output. Native controller input is used for gameplay and saving;
no RAM, save structure or story flag is edited. The original 28 movie
archives remain byte-identical. Private reports retain ROM and card hashes,
input histories, screenshots, process receipts and cleanup results.

No personal ROM, save, installed application or published release is changed.
This source follow-up does not publish a new version.
