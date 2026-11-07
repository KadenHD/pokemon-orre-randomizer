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

A later v1.2.10 replay covers Shadow Lugia's capture and purification below.
Visual checks for every Shadow species and complete campaigns across regions
remain outside this validation. Wild Poké Spot odds are unchanged.

## Shadow Lugia in v1.2.10

The European revision 0 disc ran in French under Dolphin 2609a. The ROM used
the desktop Pokémon + moves preset and seed `xd-final-0`. The preset's 5%
rate marked Shadow ID 73 shiny. The preview and verified ISO report agreed
on Lugia and level 50.

A private test card started at Citadark Isle just before the final encounter,
with the Snag Machine, a Master Ball and a strengthened team. Greevil's
dialogue named XD001 and the scene and battle showed Lugia's special dark
model. The Master Ball captured it through the normal battle menu. Both final
battles were played, and the game wrote the result to the test card at the
end of the story. Its party contained a shiny level 50 Lugia with Shadow ID
73 and a full Heart Gauge.

A copy of that save loaded at the lab with four Normal-type dancers in each
of the nine Purification Chamber sets. Lugia's captured record and Heart
Gauge were carried over unchanged. Lugia was placed in the first set through
the native team and chamber menus. The game recognized it as ready and the
normal ceremony revealed its pink shiny coloration and restored Psycho Boost.
The game put the purified Lugia in the PC. A second in-game save recorded
the same species, level, trainer ID, and PID, with an empty Heart Gauge and
the National Ribbon. After a full emulator restart, Continue loaded that
save and the PC still displayed the pink Lugia. The recorded shiny status
matched the preview.

The protected species remains relevant to the native path. The PAL chamber
readiness routine at `0x8028ECCC` checks for species 249 and requires maximum
tempo in all nine sets. This replay covers the current protected encounter
and does not exercise replacement species.
