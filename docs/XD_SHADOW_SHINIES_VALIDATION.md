# XD Shadow shiny unlock validation

Implementation: application **1.2.0**, XD engine `xd-story-sha256-v8`.
Checks performed on 5 November 2026. Original discs and personal saves were
preserved; private fixtures and emulator profiles remain outside distributions.

## Patch and preview checks

The verified European, US and Japanese DOLs passed the original SHA-256 and
call-instruction guards at 0%, 5% and 100%. The new text section also composes
with the existing starter/gift, EXP and purification hooks. Disabling the Shadow
option returns the incoming DOL unchanged.

A separate European 100% test ISO passed full output-byte verification. All 83
Shadow rows reported shiny. A 5% preview using seed `xd-shadow-check` produced
shiny IDs **13, 14, 30, 58 and 74**; all 83 decisions matched the patch table,
and all portrait and evolution-portrait data were available.

## Controlled native Dolphin checks

Dolphin 2609a executed the emitted wrappers and the original game's functions
through its local PowerPC debugger. These checks use temporary guest fixtures,
with affected memory and pointers restored after each group. They are distinct
from playing through a capture or purification ceremony.

| Check | Observed result |
| --- | --- |
| Trainer PID wrapper, IDs 1, 19, 73, 81 and 83 | All five shiny at 100%; all five non-shiny at 0% |
| Trainer PID wrapper, every ID 1–83 at 5% | Every native PID matched the seeded preview decision |
| Hero gift Shadow wrapper, IDs 1, 73, 81 and 83 | All four native PIDs shiny at 100% |
| Native player lookup and owner setter | Valid Shadow IDs received the full player SID/TID; IDs 0 and 84 retained the supplied owner |
| Native capture-status setter | All ten tested shiny/non-shiny PID and owner pairs remained unchanged |
| Native purification state transition | Dark state changed from captured (3) to purified (4), with the entire tested Pokémon and its shiny PID unchanged |

The test emulator was terminated after the probes. Monitoring confirmed the
test ISO, original ISO, source QA card and personal Dolphin profile were
unchanged. No firewall permission was granted by automation.

## Supporting checks and limits

The automated suite ran **516 tests**, with 514 passing and two platform skips.
Five tests execute 76 wrapper/ABI combinations using an independent instruction
decoder. The relocated Windows executable passed **204 UI states** across all
six languages, with the Rust codec and complete interface pack available.

Static inspection of all three original executables found no PID regeneration
in capture, party/box insertion, purification or evolution. The enemy-owner hook
runs after the native anti-shiny loop, avoiding a reroll loop. Existing saved
Shadow PIDs are reused by the game and are not retroactively replaced.

A fully played capture → save/reload → purification sequence for this new
unlock, visual checks for every Shadow species, and a complete campaign on each
region remain outside this validation. Shadow Lugia keeps its special dark
model until purification. Wild Poké Spot odds are unchanged.
