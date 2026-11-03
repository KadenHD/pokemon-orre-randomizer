# Purification Gifts — November 2, 2026

The [additional validation](PURIFICATION_GIFTS_FOLLOWUP_2026-11-02.md) completes the backup/reload,
scene preservation and dialog rendering trials in the five PAL languages. This document retains the
scope and limitations of the first session.

The version 0.13.0 makes the two event gifts available from [Eagun], at Relic Stone. By default,
Pikachu's gift requires 10 purifications at level 30 and Celebi 25 at level 45. Species and Shiny
status follow the randomizer draw. The four numerical values are set separately in "Starters and
gifts".

## Progress and conservation of the scenario

The access awaits the six persistent indicators `3527, 2582, 1067, 2860, 3531, 2875`. They cover
defeat against Skrub and all the follow-up scenes in the house, until the last indication towards
Mount Battle. A threshold of zero does not circumvent this condition.

The patch re-uses the actor Eagun already present in the sanctuary. After the complete sequence, it
becomes visible and interactive, while its usual actor in the house is masked. Before that, the
original scenes and conversations remain available. The other actors and the unfolding of the scenes
are not rewritten. The tests cover the 64 combinations of these six indicators.

The 48 native purification indicators are added. Gifts use the native 217 function with the 5 and 6
identifiers as well as the 2740 and 2737 persistent reception indicators. An interaction gives at
most one gift. The reception is marked only after a success: location 0 to 5 in the team, or return
-1 for the PC. The return -2, team and PC full, leaves the gift available for another visit.

## Languages and compatibility

Five new texts are added to each of the French, English, German, Spanish and Italian banks of the
sanctuary. The game chooses its own bank. The language of the randomizer interface is independent.
The old text allocations, their aliases and their native controls are kept byte byte.

The option is active in both randomized and inactive presets in "Identical Copy". The 0.5 to 0.12
import profiles are disabled after validation of their original signature. The ISO of the previous
print v0.11 is reproduced exactly with this disabled option in the SHA-256
`e8696b3c7fbb235ed8535e32e8bd9ea0e1309a33dfd69bf5e563f99859031372`.

## Verifications

The source suite performs 365 tests, of which 363 were successful and two ignored. The discount
model covers 785 cases, with thresholds, reception indicators, progression and capacity. The
integration tests check the original archives strictly identified, the modifications allowed and the
retention of the other members. Generation and encounter levels are modified together and the
starting capacities use the final level. Twenty-four Qt renders cover gifts and settings in the six
languages of the tool, with two window sizes.

A separate CPU trial in Dolphin executes 19 cases with the exact ISO CMS and native interpreter. The
19 succeed: each missing progression indicator blocks the discount, the thresholds are respected, a
full team sends the gift to the PC, and a team with the 90 boxes of the full PC produces the return
-2 without validating the reception. Three successive conversations give the first gift in location
0, the second in location 1, then no gift. The synthetic player context is initialized by the game
and the CK3 pass its validator. Only the display and movement functions are intercepted in this CPU
harness. The generation, acquisition and writing functions of the indicators remain native. This
logical coverage is distinct from the interaction described below.

Private ISO `rewards-seeded-25.iso`, seed `purification-rewards-1`, is reconstructed and fully
verified, at SHA-256 `da8e0d6883231b9d1cb5578895ca469db600de4894a86c0d97c2c960a22121a7`The Shiny
rate is 25%, with status linked to the seed.

In Dolphin, a backup copy loaded the true sanctuary and its production script. Eagun appears near
the Relic. The native interaction displays the thresholds, offers the gifts, confirms their receipt
and then refuses to give them back. The purification meters are prepared in RAM in this working
copy. 25 purifications were not played for this trial.

| Gift | Expected and observed result | Destination native |
| --- | --- | --- |
| Pikachu | Corphish, level 30, non-Shiny | PC, back -1 |
| Celebi | Donphan, level 45, non-Shiny | PC, back -1 |

Observation points read the two 312 bytes CK3 at the entrance to the real routine of adding to the
team or PC. They do not replace generation or acquisition. Species, level, level of encounter and
Shiny status correspond to the preview. Both reception indicators go from zero to one. Native
movement indicators confirm that the commands are released after the conversation.

The Dolphin process normally closes with the zero code. Its monitor confirms the unchanged
fingerprints of the protected originals and the personal Dolphin profile. Catches, logs and
recordings remain private in `build/purification-rewards-2026-11-02/` and are not distributed.

This check is not a complete part of the scenario. The masking in the house and the six conditions
of progression have a static cover. The backup/reloading cycle of these new gifts was not played in
this session. The repositioning tests after dialogue encountered a return of the transformation
caches of the character. No circumvention was added to the production patch for this test
preparation.
