# Validation of Dolphin Shinies — November 1, 2026

Intermediate state: the capture chain, PC withdrawal, purification, game backup and cold reloading
is observed on the same target. The randomized native gift Plusle is also received and saved. Ho-Oh
and reappearance tests remain in progress. This document does not count them as successful. The
production engine v0.10 did not change during this validation.

## Images and criteria used

The tests use the ISOs produced with the `shiny-native-validation`.

| Private image | SHA-256 |
|---|---|
| `build/shinies-2026-11-01/shinies-100.iso` | `7521dcf9ba13247a6f1cffa1178e28d34ad6ce584da4c49b09e76a0e53384efa` |
| `build/shinies-2026-11-01/shinies-0.iso` | `cf0490109c35e46c5210d7072b2a0992132a77ea5eba30f9ed1a981ba0c7efa9` |

The identity check re-reads the PID and the two OT identifiers in the CK3, then applies the
canonical native test `(PIDhi ^ PIDlo ^ SID ^ TID) < 8`. The palette and visible effects are checked
separately. Complete identifiers, maps, RAM captures and detailed logs remain private under
`build/`.

## Actions actually observed

| Cas | Established result | Main private evidence |
|---|---|---|
| 100 % starters | New part on empty map. Portraits and 3D models of [Horsea] and Abra observed in their summaries. | `starter-100-visual.json`, `starter-100-horsea-summary.jpg`, `starter-100-abra-summary.jpg` |
| Starter limits | At the cold start, the two native starters have a XOR of 2 and 3 to 100%, and 60,615 and 60,243 to 0%. The other locations are empty. The case 0% is a RAM readout, without visual validation. | `build/shinies-2026-11-01/runtime/starter-runtime-validation.json` |
| Meeting and capture | Arcanine Dark level 40, Group 21, built for Dakim's fight. Gold model and visible input effect. Native capture at Master Ball, then automatic reception at PC: 14 → 15 Pokémon. The fourteen old CK3 remain identical byte per byte. | `target-snag-identity.json`, `existing-pc-after-snag.json`, `shadow-100-arcanine-entry.jpg`, `shadow-100-arcanine-pc.jpg` |
| Withdrawal of the PC | Removal by the interface to the first location of the team. The complete CK3 of 312 bytes remains the same as the one received after capture. | `target-capture-pc-purification-identity.json`, `target-after-pc-withdrawal.bin` |
| Purification | After preparation of the gauge described below, native interaction with the Relic. The message of opening of consciousness is visible. Gauge -100, national ribbon 1 and native purification flag 1282 to 1. PID and OT identifiers retained, XOR 6. | `acquisition-rsp.jsonl`, `target-capture-pc-purification-identity.json`, `shadow-100-arcanine-purification.jpg` |
| Backup and reloading | Backup by the game on the private card, normal closing, new start of ISO and "Continue" from the title, without savestate. The purified target is found with its identity and its 312 bytes strictly identical. Its golden model is still visible. | `purified-card-before-cold-load.json`, `target-card-coldload-identity.json`, `arcanine-purified-coldload-summary.jpg` |
| Gift Plusle randomized | Doking native scene at the club of Pyrite Town: the gift produces a Houndour shiny level 13, received at the PC with the expected fixed OT of the gift and an XOR of 6. The fifteen old CK3 of the PC remain identical. The game backup then contains the exact CK3 of the new gift. | `plusle-native-gift-identity.json`, `plusle-native-gift-card.json`, `plusle-gift-shiny-houndour-pc.jpg`, `plusle-native-game-save-complete.jpg` |

Unless the full path is indicated, the evidence in the table is under
`build/shiny-validation-final-2026-11-01/`.

The CK3 after capture and after removal of the PC shares the SHA-256
`4d06f1be447cec8969a1204489a1fa8b3647f99d184f48d6c192208f1bbdbc05`. After purification, the CK3 of
the saved card and the one re-read after restart share the SHA-256
`8d6a48eff988e19f90030fbaa858c15aca5f61a93bc431dba3982907fb7efae5`. The parser confirms the
checksums of the three slots of the card and their exact decryption/recryption. The finding of
persistence is also based on the RAM reading of the actual reloading, beyond this map verification.

The player root is rereferenced after each boot. For reloading retained, it is `0x80455B00`, so the
team starts at `0x80455BA0`. `stale-root-address-diagnostic.bin`, obtained by mistake at an old
address, is explicitly excluded from reloading evidence.

For the gift, the stop point is reached naturally in `std217(3)` to `0x801CF11C`, from the script
interpreter. The return −1 corresponds to the reception to the PC when the team is full. No PID or
OT writing is done for this gift. The new CK3 shares SHA-256
`9fc5f58590956df7bde732fca8fa8625a0ac3b9812a6ae6815663033a7ae4071` between the RAM capture and the
saved card, stored under `plusle-native-saved.raw`. The previous gift already present in the copy,
become Shuppet non shiny, is kept unchanged. The new Houndour has not yet been reloaded from this
card after another cold start.

The shiny model of Houndour is visible in the PC. However, the dialogues of the scene continue to
name POSIPI and announce its transfer: the narrative texts and actors have not been rewritten for
the randomized species. This cosmetic limit should not be confused with the identity actually
received.

## Private and scope preparation

The starting card is a copy of `boss-party-v2.raw`, with team already worn at level 80 and Master
Ball. The dark group 21 was new in this source. Native transitions, warps and placements of the
character speed up access to the scenes. At the natural entrance of Billy's fight, the argument of
battle 13 is replaced by 213. The engine then builds Dakim's real data from ISO. This does not
validate access to Dakim by all the progression of the scenario or the balancing of a normal team.

After capture and removal of the PC, the only Pokémon field prepared is the gauge, lowered from
13,000 to 0 to make the target immediately purifyable. Comparison of the two CK3 confirms that only
bytes of the field `+0xDC..+0xDF` change. PID, OT and all other data are retained. This preparation
does not demonstrate a natural decrease of the gauge. The purification that follows is performed
well by the game. No purified Pokémon is injected to prove backup or reloading.

To replay the gift Plusle on this copy, only the stage flag 1047 is prepared from 1 to 0 after
validation of the descriptors and native signatures. 1046 remains at 1 and the neighbouring bits are
preserved. The private plan `plusle-flag-fixture-plan.json` is corroborated by readings, writing and
its rereading in `acquisition-cold-rsp.jsonl`. The club scene is then played by the interface, and
1047 is observed back to 1 before the release. This reset is a progression fixture, not a new path
until the event.

## Measure of the rate by controlled native calls

`build/shiny-validation-final-2026-11-01/statistics/statistics-summary.json` records executions on
the real Dolphin CPU of native production wrappers, PID generator and PAL RNG. The harness provides
synthetic CK3s, a private RAM PowerPC loop and controlled calls. It does not simulate any meetings
played or gift events.

| Requested rate | Gift mode | Trainer mode | Shadow mode |
|---|---:|---:|---:|
| 1 % — 50,000 appels par mode | 508 / 50,000 | 520 / 50,000 | 499 / 50,000 |
| 0 % — 1,000 appels par mode | 0 / 1,000 | 0 / 1,000 | 0 / 1,000 |
| 100 % — 1,000 appels par mode | 1,000 / 1,000 | 1,000 / 1,000 | 1,000 / 1,000 |

At 1%, the total is 1,527 shinies out of 150,000 PIDs, i.e. **1,018 %**. The 95% rated Wilson
interval is `[0,9684 % ; 1,0701 %]`. This benchmark does not demonstrate that deterministic PRNG is
an IID suite. Nature/genre stresses are −1 in this harness. Their combinations are not covered by
this measure. Targeted stops in these diagnostic processes do not count as normal Dolphin closures.

## Isolation, launcher and fence remaining open

Instrumented trials use Dolphin 2609a and a private copy with the GDB polling patch already
documented in `docs/reverse-engineering/DOLPHIN_RUNTIME_FIXTURES.md`. This adaptation of QA does not
change the game and is not distributed. No old Dolphin savestate is used to establish the
persistence chain of the new ISO.

`acquisition-100-host2-run.json` records a normal closing, native code 0, after the purified backup.
The protected files and **46 files** of the personal profile followed are unchanged.
`acquisition-cold-run.json`, which contains the reloading then the gift Plusle and its backup, is
also completed with the native code 0 and these same successful retention controls on the 46
personal files. The first visual session `visual-100-run.json` also ends with code 0, but its empty
personal inventory does not constitute proof of retention of the actual profile.

Two QA launcher defects are corrected: no`APPDATA` now refused without explicit personal path, and
publication JSON atomic with limited retest in front of temporary locks of Windows drives. **17
dedicated tests** These corrections concern the validation device. They do not alter the shiny rules
of the engine. v0.10.

The final global audit and the cleaning of GDB configurations remain to be recorded after the other
tests. Ho-Oh, the preservation of identity during a reappearance and the cold reloading of the new
Houndour remain out of the results acquired. This pass does not cover a complete part, all species,
all events or a physical console.
