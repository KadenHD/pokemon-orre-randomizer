# GiftsEagun USA and Japan — Dolphin validation of the v0.14.0

The two gifts were obtained in the US and Japanese versions, then found after a backup in the game
and a complete restart of Dolphin. Eagun then refuses to give them a second time. This follow-up
completes the [Regional validation](REGIONAL_COMPATIBILITY_2026-11-03.md) and [previous PAL
tests](PURIFICATION_GIFTS_FOLLOWUP_2026-11-02.md).

## Observed results

The tests use the ISOs produced by the engine v0.14.0, with the `regional-validation-1` seed, the
recommended presetting and a 25% Shiny rate linked to the seed. Thresholds remain at 10 and 25
purifications, the levels at 30 and 45. Both gifts drawn are normal in this configuration.

| Monitoring | USA, `GC6E01` | Japon, `GC6J01` |
| --- | --- | --- |
| Pikachu gift | Zigzagoon, level 30 | Zigzagoon, level 30 |
| Celebi gift | Cradily, level 45 | Cradily, level 45 |
| Species, level, experience, four abilities and Shiny status | Conform to the overview | Conform to the overview |
| Five dialogues in the engine of the game | Anglais, lisibles | Japanese, characters and returns to the correct line |
| PC backup of the game | Successful | Successful |
| Loading by "Continue" in a new process | Successful | Successful |
| New conversation with Eagun after loading | No new gift | No new gift |
| Original ROM and Personal Dolphin Profile | Unchanged | Unchanged |

The two gifts go through the script and native routines of the game. The team being full, each
Pokémon is added to the PC. The complete recordings of 312 bytes are captured when they are
inserted, without substitution of Pokémon, call result nor reception indicator.

After acquisition, after loading and after the new conversation, the 96 locations of the team and
the PC are read: each gift appears once, with the same 312 bytes. The two persistent indicators
remain active. The point of observation of the gift routine remains installed during loading and
the final conversation. It is never reached in these steps.

The closed cards pass the controls of the native GameCube card, comment and banner, the three backup
locations and their encryption. The last location goes from counter 13 to 16. The two old ones
remain at counters 14 and 15. In each region, the card after the last restart is identical to that
written by the native backup.

## Preparation of tests and limits

Test cards have been prepared from a closed copy of the QA PAL card, with 25 purifications and the
six script conditions already met. The old test gifts and their indicators have been removed before
gifts. The regional identifier, language and map metadata are adapted to each version. The test
moves use declared door shortcuts to reach the Relic and the PC. Therefore, these tests do not
replay the 25 purifications or the entire progression of the scenario.

The USA trial uses an intermediate instant state to resume navigation after actual acquisitions. The
final control of persistence, in both regions, is done in a new profile containing only the saved
card and the necessary settings: no instant status nor SRAM n的y is imported.

The "team and PC full" and "threshold reminder" messages were visually checked by selecting their
text identifier during a conversation after receiving the two gifts. This validates their rendering,
without pretending to have replayed these two situations of capacity or progress in each region. The
messages of offer, success and gifts already received are observed on their real branches.

A prep anomaly concerned the checksum of the comment and banner of the first American QA card. The
game corrected the load. The encrypted backup data remained the same at this stage. The
manufacturing of QA cards was then corrected and the Japanese card was checked before its first
start. This correction concerns private test files, without changing the engine or ISOs of the
v0.14.0.

The private copy of Dolphin 2609a and its host input patch remain those of the previous harness. A
first US launch blocked before the game was started. It was stopped, with the sources being stored
verified. The five sessions selected normally close with a null code. No Dolphin, ROM, memory card
or proof installation containing the data of the game is distributed.

A complete part, a physical console and a second Windows PC remain outside this perimeter. Start-ups
from the three regions, the configuration matrix and ISO/RVZ creation are covered by the previous
regional report.

## Traceability

Private evidence is stored in `build/regional-gifts-2026-11-03/`: native contracts and observation
logs, dialogue captures, gift records, test cards and post-closure controls. Each region has a
`runtime/<région>/completed-validation.json` file that checks the gifts, backups, reloading,
captures and retention of originals. The common balance sheet and final fingerprints are in
`completed-validation.json`.

The monitoring reports compare all files in the Dolphin Personal Profile and the three original RVZs
before and after each session. The executables of the application remain the same. Only the
documents and archives accompanying them are updated to integrate this follow-up.
