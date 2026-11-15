# Treasure item validation

The full preset randomizes ordinary treasure items without restricting the
replacement to the original item's category or price. Key items, DNA samples
and progression-sensitive entries remain protected. The species-only preset
keeps ordinary treasure items unchanged.

The final reconstructed `common.fsys` tables were checked for Europe, USA and
Japan in both games, using `treasure-a` and `treasure-b`. All 43 eligible
Colosseum entries and 86 eligible XD entries changed, and every eligible entry
differed between those two seeds. This is a data audit, not a playthrough of
every chest.

## Native pickups under Dolphin

Four representative European pickups were also exercised with actual
controller interactions. Each seed opened the same chest in its game, from a
cold boot with a separate copy of a QA memory card.

| Game and chest | Original contents | `treasure-a` | `treasure-b` |
| --- | --- | --- | --- |
| Colosseum, Pyrite Cave 3F, table entry 10 | Ether ×3 (item 34) | Pearl ×3 (106) | Up-Grade ×3 (218) |
| XD, ONBS 2F, table entry 100 | Ether ×1 (item 34) | Persim Berry ×1 (140) | Kelpsy Berry ×1 (154) |

The native found and received messages matched the table in every case. The
XD inventory changed from zero to one of the expected berry for both seeds.
Colosseum's copied source bag was full, so its normal full-bag behavior sent
the contents to the PC. A second copy with twenty normal-item slots cleared
received three Up-Grades in the bag; a read-only probe of the running game's
inventory confirmed the quantity changed from zero to three. No items were
injected into the running inventory to produce these results.

The test-only staging changed the player's room entrance and the copied
card's selected chest flag, allowing the native interaction to be reproduced
without replaying the story. It did not alter the chest's randomized item.
These checks confirm representative actual pickups; they do not establish
that every chest was manually opened in every language.

## Script overrides

Colosseum's native `floorEventChangeTresure` wrapper is standard function 203.
A scan found 24 literal calls, all in `D1_labo_B1.fsys` and
`D1_labo_B3.fsys`, addressing DNA entries 62–73. No Pyrite chest override was
found. The scan covered 195 CMS members.

The equivalent XD wrapper is Map class 38, function 27. No literal calls were
found across 242 TCOD scripts and `common_rel`. These scans identify literal
calls and do not prove the absence of a dynamically selected function ID.

## Isolation and evidence

Dolphin used private profiles with both volume zero and mute enabled. Input
came from offline controller movies; no global keyboard or controller input
was used. The original ROMs, QA source cards, emulator executable and personal
save directories had no hash changes. The Colosseum opening video remained
byte-identical to the original in both test ISOs: 64,046,624 bytes, SHA-256
`092d180eec49a002fb2a99d4d25e967c616a4ce8d8f06c1f95b160b1897d2526`.

Local reproduction scripts, fixture and production-image hashes, memory
observations and native screenshots are retained under the ignored
`build/v1220-treasure-runtime/` directory. The aggregate is `RESULTS.json`,
and the selected images are in its `evidence/` subdirectory. Disposable test
ISOs and redundant frame dumps can be removed after validation.
