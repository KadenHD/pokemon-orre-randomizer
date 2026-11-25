# XD fresh-start validation - 24 November 2026

The application version is **2.1.1**; the engine revision for each generated
trial is listed below. Tests use a verified, unmodified European XD disc image
(`GXXP01`, English). This report covers unusual natural starter moves through
the first ordinary battle and the first Shadow capture.

## Method

Each species starts with a new isolated Dolphin profile and a blank memory
card, using native **NEW GAME**. The Pokémon-only preset is used unchanged
except for the manual starter choice. No attack, story flag, RAM value or save
structure is edited to force progression. Native Save/Continue is allowed.

Dolphin uses **No Audio Output**, original graphics and a requested 200% QA
speed. Inputs and screenshots come from a private loopback controller; the
user's Dolphin, ROMs and saves are not controlled. All 28 original movie
archives remain byte-identical in every generated test ISO.

The generated ISO is hashed and checked against its creation report, then
removed after the completed run. Native cards, profiles, input histories,
screenshots and reports are retained as private evidence.

## Completed cases

| Starter | Engine | Initial moves | First ordinary Chobin battle (222) | First Snag (224) | Post-battle state |
| --- | --- | --- | --- | --- | --- |
| Ditto, Lv10 | v18 | Transform only; three empty slots | Transform copied Seel's model and Headbutt. Copied Headbutt won the battle; 5/30HP remained. | Full-HP Shadow Gastly, Lv11, caught with an ordinary Poké Ball without attacking. | Ditto's own model returned; Transform 9/10 and three empty slots. Gastly 28/28 in party. Native save confirmed. |
| Wobbuffet, Lv10 | v18 | Counter, Mirror Coat, Safeguard, Destiny Bond | Counter alone won against Seel. 43/58HP remained; Counter 16/20. | Full-HP Shadow Drowzee, Lv11, caught with an ordinary Poké Ball without attacking. | All four natural moves retained. Drowzee 35/35 in party. Native save confirmed. |
| Smeargle, Lv10 | v19 | Sketch 1/1 only; three empty slots | Call on turn 1, then Sketch copied Headbutt. The copied move won the battle; 23/32HP remained. | Full-HP Shadow Drowzee, Lv11, caught with an ordinary Poké Ball without attacking. | Headbutt 13/15 remained learned, with three empty slots. Drowzee 36/36 in party. Native save confirmed. |

All three cases complete Jovi's return, receive the native Snag Machine and
five Poké Balls, and continue through Krane's kidnapping and the post-capture
scene. The old man in Krane's
2F office is a required native handoff before the equipment scene; merely
examining the case beforehand does not grant it.

Ditto's run uses two normal Save/Continue transitions on the card created by
that NEW GAME. Wobbuffet and Smeargle each reach their final save in one
Dolphin session. Smeargle also makes a normal early save on its new card.
Each final save confirmation is followed by an 18-second neutral interval
before the owned process is closed and the card is copied and hashed.

## Deliberate first-Chobin loss

A separate profile uses a copy of Ditto's native pre-Chobin card. Call alone
lets Seel knock out Ditto, with no damage dealt to the opponent. On the v18
engine, XD returns Michael to the manor entrance. Reapproaching Chobin starts
another battle after his explicit loss follow-up dialogue. This is a real
retail retry gate, so the successful Ditto/Wobbuffet cases do **not** prove that
every passive natural starter can progress through Chobin.

The v19 correction and its separate native loss replay are documented in
[XD first-battle progression validation](XD_FIRST_BATTLE_PROGRESSION_VALIDATION.md).
The initial battle and the winning path remain unchanged. Smeargle's
independent v19 NEW GAME confirms that winning path through the first Snag.
The final Western caption wrapping is checked separately in that companion
report; this does not reclassify the earlier v18 regional checks as v19 tests.

## Evidence and limits

Private evidence is under `build/v212-validation/`: creation and movie-hash
reports, per-session `commands.jsonl`, native screenshots, process receipts
and final-card hashes. The first abandoned Ditto helper failed on a Windows
control-file read, not inside the game. Its entire private profile was
archived and a new blank profile/card was created for the qualifying trial.

This is an English European early-game runtime test, not a full-campaign
playthrough or a claim that every species wins every random battle. Regional
USA/Japan startup checks and the full starter planning matrix are separate
validation scopes. No personal original files are modified.

## Retained evidence

| Case | Native result | Final card SHA-256 |
| --- | --- | --- |
| Ditto | `ditto-continue-2/native-result.json` | `2cb924ce8778bfbfd6dfa7f9b2a8586be523f8840b46e26a1853c4d333dc98e9` |
| Wobbuffet | `wobbuffet-fresh/native-result.json` | `56a12c114ff29b487f7b43f905c0e6fd8939f3ee16d9b72c582759c4b6d1eb4d` |
| Smeargle | `smeargle-fresh/native-result.json` | `cff6d8f68d99689b77a6b89a2db97f105fe366fcf8ca5b3d9de594a0b98a3ace` |

Paths are relative to the private `build/v212-validation` evidence folder.
Each case also has a `verified-iso-cleanup.json` receipt. All three qualifying
Dolphin processes are confirmed closed; only their generated ISO copies and
now-archived sidecar copies are removed. The native cards and profiles remain.
