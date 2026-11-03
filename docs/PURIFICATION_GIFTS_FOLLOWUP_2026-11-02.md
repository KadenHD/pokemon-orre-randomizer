# Purification gifts: additional validation of November 2, 2026

The three additional checks are completed in Dolphin: backup/reloading of the two gifts,
preservation of the scenes of[Eagun and display of the five new messages in the five PAL languages.
No patch anomaly was found in this area. The test preparations and their limitations are described
below.

This complete follow-up [la validation initiale](PURIFICATION_GIFTS_VALIDATION_2026-11-02.md). It
uses the same ISO PAL `GC6P01`, version 0.13.0, seed `purification-rewards-1`, 25 % Shiny rate
linked to the seed. Its SHA-256 is
`da8e0d6883231b9d1cb5578895ca469db600de4894a86c0d97c2c960a22121a7`.

| Verification | State |
| --- | --- |
| Native backup, new process, loading and no second gift | Validated in this course |
| Skrub, follow-up scenes and unique presence ofEagun after their end | Validated in this French course |
| Issued the five messages in French, English, German, Spanish and Italian | 25 visually controlled displays in Dolphin |

## Backup and absence of duplicate after reloading

Both gifts were obtained by normal conversations of[Eagun. The game called its native 217 function
with the 5 and 6 identifiers and then sent them to the PC, the team being full. The generated
records correspond to the expected draw: Corphish level 30 and Donphan level 45, both ordinary.
Neither the native function, nor its return, nor the received Pokémon were substituted.

The backup was then performed from the PC, with the confirmations given by the game. After closing
the process, the copied card contains the counters `13,14,15`, against `13,14,12` before this
backup: the most recent slot went from 14 to 15. Its checksums are valid and its encryption is
reconstructed exactly. Receipts 2740 and 2737 are worth 1. Each gift appears only once and its 312
bytes correspond exactly to the recording captured during the native acquisition.

A new Dolphin process loaded the same card with "Continue" and then confirmed, without savestate.
Reading its 96 locations — six in the team and 90 in the PC — finds each of the two gifts only once,
in the same boxes of the PC, always identical byte per byte. Both receipts and the six scenario
conditions are retained.

A new normal interaction with Eagun then displays the message "gifts already received" (`0xF0004`).
The observation point of function 217, active during this interaction, does not see any new
acquisition call. This test therefore covers the persistence on card and the refusal of a second
discount after a real restart of the game.

## Skrub and complete end of the scenes

The real introduction of the sanctuary was played, with the automatic duel 525 between Eagun and
Skrub. In this execution, Eagun loses. The scenario then launches the player fight 198, won by
playing his controls. No fighting result, PV, team or progression indicator was written to win it.
The test does not demonstrate a forced defeat dEagun for all the seeds.

The conversations of the house, the visit to Fernand, the tablet, the mail and the last directions
to Mont Bataille then executed their real scripts. The six conditions
`3527,2582,1067,2860,3531,2875` arrived at 1 by these scripts and by the native mail manager.

Eagun remains present during the scenes which use it. After a real exit then returned to the house,
his actor is hidden and inactive there. Oliphie remains visible. At the next loading of the
sanctuary, only one actor dEagun is present, near the Relic Stone. The donor's displacement
therefore awaits the end of the scenes in this journey.

## Dialogues in the five PAL languages

The five added messages were each displayed in Dolphin in French, English, German, Italian and
Spanish, on the same production ISO.

| Message | French | English | German | Italian | Spanish |
| --- | --- | --- | --- | --- | --- |
| Proposal for a gift | Validated | Validated | Validated | Validated | Validated |
| Confirmation of receipt | Validated | Validated | Validated | Validated | Validated |
| Team and PC full | Validated | Validated | Validated | Validated | Validated |
| Thresholds of 10 and 25 purifications | Validated | Validated | Validated | Validated | Validated |
| Two gifts already received | Validated | Validated | Validated | Validated | Validated |

Each capture has been individually inspected: full text, line jumps, accents, particular characters
and no overflow. The message of the thresholds holds on three lines in each language. The others
hold on two.

The language is prepared only in the byte of configuration of the copy in memory. A real exit from
the Relic to the cave, then a return, let the engine unload the old bank and load the new one. The
global language variable is never written directly. The observed order is French, English, German,
Italian, Spanish. One last exit restores the French and its active bank before closing.

To check the texts without handing over the gifts, the test stops a real call for dialogueEagun Only
the message identifier is replaced for the first four texts. The fifth text is displayed without
substitution. Receipts, inventory, scenario conditions, receipt result and scripts do not change. It
is a verification of the rendering of the translation banks, not a new acquisition or a full PC test
in each language. The capacity logic has the distinct native tests described in the initial
validation.

The 25 observations keep both received at 1. No acquisition call 217 is observed during the
reloading session. A final reading of the 96 locations finds each gift exactly once, with the same
312 bytes as before the language tests. These tests do not cover five independent startups or
automatic language selection on startup.

## Preparation of the test and limits

This journey starts with a prepared test backup, not a new part.

- The source copy was already after Skrub. Thirteen indicators of this sequence were reset to zero
  in a new map: `1064,1065,1066,1067,1068,1070,3527,2582,2860,3531,2875,2810,3551`. Its loading
  context was placed on the native entry of the sanctuary `(39,37,0)`, with recalculated checksums.
  The sources remained intact.
- The mail 0 was already received and read in this old part. Its bit "already read" had to be reset
  to zero on the copy, because the game only applies its effects to the first reading not read. The
  new opening of the real P★AD then set 3531 natively. This was not a direct write of 3531. This
  test does not validate a first delivery from an empty mail box.
- The long movements were shortened during real door transitions stopped in the engine. The scenario
  route uses three of these shortcuts. Others join the PC and the sanctuary for the control of
  persistence. The scenes, interactions and local movements remain those of the game. No actor
  coordination was injected to cross them.
- The 25 purification counter was prepared on the QA copy. The 25 purifications were not played. The
  acquisition, receipts, backup and reloading then used the normal game routines.

These preparations limit the scope of the test: they check the scenes and the persistence from
defined preconditions, without replacing a complete part started from zero. No circumvention of
these preconditions was added to the production patch.

The originals, cards and personal profiles are not the destination of the test. Both Dolphin
processes are normally closed, with the code zero. Their monitors confirm that the protected files
and personal profile keep their fingerprints. No language changes were saved: the final QA card is
identical byte to its closed copy after the native backup of the two gifts, at SHA-256
`04b7238d6fe4e382581d6e3b582c5d7be0fd3e902ae8f7b741109255769b3f9c`. The additional validation did
not change the production patch, nor ISO, nor the distributed executables.

## Private evidence

The maps, captures, logs and identities of the Pokémon remain under
`build/purification-followup-2026-11-02/` and are not distributed with the tool.

| Evidence | What it establishes |
| --- | --- |
| `STORY_RUNTIME_FOLLOWUP.md` and checkpoints of `persist-fr/` | Progression played, preparation declared, real homecoming and presence at the sanctuary |
| `native-research/closed-current-validation.json` | Card after native backup: counter 15, checksums, receipts and unique gifts |
| `persist-fr/monitor.json` | End of first process and preservation of protected files |
| `persist-fr/monitor-reload.json` and `after-real-reload.json` | New process, normal loading, zero code closure and unchanged protected files |
| `persist-fr/live-gifts-after-reload.json` | Search for the two exact CK3 records among the 96 locations after loading |
| `persist-fr/bridge-reload.jsonl`, including the observation of the message `0xF0004` | Conversation after reloading and no new call 217 |
| Captures 17 to 21 of `persist-fr/evidence/` | Backup confirmations, return to play after loading and refusal of second release |
| `persist-fr/translation-cases/` and catches `evidence/locale-<langue>-<0..4>.jpg` | 25 actually displayed messages, active language and visual substitution declared |
| `persist-fr/live-gifts-after-translations.json` and `final-runtime-after-translations.json` | Always unique gifts, preserved conditions and French restored |
| `visual-validation-final.json` | 25 catch footprints, mutation audit, unchanged AQ map and final conservation |

The closed chart report precedes the new process: its initial reserve on reloading is lifted by the
following runtime observations. Offline prepared language maps were not used as visual evidence. The
reloaded captures and observations of the session provide this proof. The aggregator controls the
files, fingerprints and invariants. The appraisal of the rendering comes from the catch inspection,
not from an OCR assertion.
