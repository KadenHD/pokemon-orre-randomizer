# Dolphin validation of October 31, 2026

The functional controls below distinguish between the actions actually played, the teams compared in
memory and the private preparations. They do not constitute an integral part of the scenario or a
measure of its balance.

## Images and comparison reference

The expected values have been re-read in **two ISOs actually launched**: FST, FSYS archives, REL and
DOL. The tables are confirmed by the REL's own relocations and meters. Previous randomization
reports do not serve as a reference for these comparisons.

| Image de test locale | SHA-256 | Usage |
| --- | --- | --- |
| `recommended.iso` | `648cc8c0744c87fce40a7d4dbdd3f6f95f8df29bc48415ee33507cb5d1894b35` | New game and native starter creation |
| `gameplay-check.iso` | `c15ee8d12d6e0351cd60778f78193eaef9b485a77b9f345f3b0f00cf08427e5e` | Purification, TM, evolution, shop, safe and boss fights |

The second test activates the constraints specific to the bosses' Shadow Pokémon and randomization of the
store stocks tested. These fingerprints identify the local images. No images are included in the
distribution.

## Functional checks performed

| Fonction | Observed action and outcome | Control retained |
| --- | --- | --- |
| Story starters | A new game creates a level 26 Seadra with 17,576 EXP and a level 25 Electabuzz with 15,625 EXP. | The two species, levels, EXP and four capacities are consistent with the final DOL/REL of the recommended image. The other four locations are empty. No Pokémon is injected into the execution. |
| Purification | At the Sacred Sanctuary, the prepared Onix level 39 passes 0/national ruban 0 to gauge -100/riban 1. | Species 95, EXP 59,319, abilities and dark identifier 19 remain preserved. The native purification flag is 1 after the action. The animation has not been retained. The transition is proven by the states before/after and the absence of writing in the Pokémon. |
| CT05 | The pocket TM displays Tunnel. Onix is indicated "Apt". The player replaces Charge with Tunnel and the TM is consumed. | The capture after learning contains `[91,20,106,88]`, against `[33,20,106,88]` before. Species 95, level 39 and EXP 59,319 are unchanged. The final image actually associates CT05 with Tunnel 91. |
| Accessible development | A Super Bonbon makes Onix grow from 39 to 40. The native evolution scene displays Onix, then the Steelix confirmation. | Species 208, level 40, EXP 64,000. The four capabilities `[91,20,106,88]` are retained. Super Bonbon is consumed. No exchange or object held is required for this rule of evolution at level 40. |
| Randomized shop | At Pyrite Town, Accuracy+ costs 950. A purchase increases the amount owned from 0 to 1 and money from 99,999 to 99,049. | The visible stock matches the shop 5 of the final ISO. Only one ordinary location changes. The other common bytes of the bag are identical. No inventory or silver writing is done by the RAM tool. |
| Randomized box | The box 1 of Phenac City announces and then gives three Defense+. | Object 76, quantity 0→3, flag 152: 0→1. Silver 99,149 unchanged, other objects unchanged. Room 3 and coordinates of the chest approximately `(-153.04,32.99,84.22)` match with the final REL. No object or safe flag is injected. |
| Shadow Pokémon capture | level 35 Shadow Piloswine of Miror B. appears with its violet aura, is captured with the Master Ball, then the fight ends with a victory and the return to Billy's dialogue. | The PC goes from 14 to 15 Pokémon: an empty box receives Piloswine 221, dark group 19, gauge 10,000, Ball 1 and capabilities `[8,173,133,124]`. The fourteen Pokémon already stored remain identical byte per byte. Master Ball 1→0 and capture flag 2144: 0→1. No Pokémon is injected into the team or PC. |

For CT05 and Super Bonbon, the consumptions were confirmed during the interface interaction. The
binary catches for this case are those of Pokémon, not the bag catches after each consumption. For
the purchase and the trunk, the quantities and the money are also verified by the before/after bag
catches. The capacities after evolution are Tunnel 91, Stretching 20, Armor 106 and Jet-Pierres 88.

The generic message of the relic after purification does not signal a blocking: the entry flag 1067
was already at 1 and Onix purified is no longer counted by the game among the candidates to be
purified. No change of quest was necessary.

## Seven teams of bosses checked

Miror B.'s 164 combat, trainer 162, was built by the native engine. The five Pokémon present match
the final image, including their levels, four capacities stored and obscure identifiers: Heracross
30, Arcanine 31, Torkoal 29, Magneton 28 and Shadow Piloswine 35. The sixth position is empty. The comparison
accepts the actual order of the engine and requires a complete and unique match for each Pokémon.
The first turn was actually played and captured on the screen. Two rounds of attacks, then the
capture turn, the victory and the return to history were observed for this fight.

| Bosses | Combat → trainer | Dark drawn in this ISO | Control in play |
| --- | --- | --- | --- |
| Miror B. | `164 → 162` | Piloswine | 5 exact Pokémon, first menu, attacks, capture and victory |
| Dakim | `213 → 211` | Electhor | 5 exact Pokémon and first menu |
| Venus | `328 → 326` | Raikou | 5 exact Pokémon and first menu |
| Teck | `405 → 403` | Articuno | 5 exact Pokémon and first menu |
| Helgonza | `427 → 425` | Stantler | 5 exact Pokémon and first menu |
| Jakylla | `439 → 437` | Salamence | 6 exact Pokémon and first menu |
| Nosfrat | `441 → 439` | Dragonite | 6 exact Pokémon and first menu |

The **37 Pokémon present and five empty locations** correspond to ISO data. Each species, level,
dark group and set of four stored capabilities is compared, including in the reserve. The seven dark
ones have a positive gauge. The identifiers of the last six trainers were also read in the native
structures. Six reloads of the same recap, created for this exact ISO, allowed these independent
tests. No enemy teams were injected. Screenshots attest to the first seven combat menus.

The capabilities stored in the combat structures have been compared. This does not prove the
execution of each of them. The temporary substitutions of the engine, especially the Shadow Rush in
a dark, require a clean observation. The capture and victory are established for Miror B.. The
other six tests stop at the first menu: they do not prove their complete victory, neither the
capture of each of their Shadow Pokémon, nor their access by all the progress of the scenario.

## Private preparation and genuinely tested actions

The starters come from a new empty card game. Other cases use **copies** of an existing card,
prepared before launch. The Onix fixture contains a Onix 39 ready to purify, its initial
capabilities, a CT05 and a Super Bonbon. It does not contain Steelix, nor Tunnel learned, nor
purification results already applied to this target.

In order to expedite verification, the following preparations are explicit.

- Native Warps to useful scenes and adjustments of position/orientation of the character. The trunk
  uses four coherent position caches. A displacement exceeding the target required a second
  placement.
- Silver 99,999 in the fixture before the boot. After the verified purchase, two Antidotes are sold
  by the native interface for 50 each: one place is released in the twenty ordinary locations and
  the money reaches 99,149 before the trunk.
- The existing team is at level 80 and prepared to be purified for the boss trials. This team
  facilitates the control of the combat and does not measure the normal difficulty.
- Private recovery point before a combat dialogue. At the natural entrance of the combat launch,
  only its identifier is substituted to ask the engine to build the boss team from ISO. No enemy
  team is injected.
- Resetting the only capture flag 2144 of the dark group 19, already captured in the source copy, to
  allow its reappearance for trial. This writing prepares a meeting. It is not a successful capture.
  The other six groups were observed not captured at the point of recovery.

The newspapers separate these preparations from the actions in the interface: purification,
learning, level gain, evolution, purchase, opening of the vault, conduct of the fight and capture.
Cards, states of recovery, RAM captures, backup tools and search references remain private under
`build/` or `analysis/`, excluded from public archives. No name, personal path, backup, binary
extract of ROM or third party code of these tools is published with this report.

## Dolphin and conservation of originals

Instrumented trials use Dolphin 2609a and its GDB protocol. A copy **Private** of the emulator
changes a single byte of the polling time `select` from 20 μs to 0, to avoid the cost of Windows
delay during GDB tests. This adaptation concerns the QA emulator, not the game data. The official
executable source of the project remains intact and the modified copy will not be distributed. The
behavior of the polling and server is documented in [Official sources
pinned](https://github.com/dolphin-emu/dolphin/blob/409881c34357d0f105fd473167d15ab0bd9c1628/Source/Core/Core/PowerPC/GDBStub.cpp)
and [QA device search](reverse-engineering/DOLPHIN_RUNTIME_FIXTURES.md).

The monitor launches an isolated profile, raises the true native closing code and compares the
fingerprints before/after protected files and the entire personal profile. The constraints,
corrections of the launcher and the limits of the environment are described in [l'audit
d'isolation](reverse-engineering/DOLPHIN_VALIDATION_ISOLATION.md).

The completed sessions `baseline-empty-run`, `random-story-host-run`, `random-story-fast-run`,
`onix-gameplay-run`, `bosses-gameplay-run` and `final-official-gameplay-run` all have one **code
natif 0** and retain the **46 files** personal profile followed, as well as the protected images and
executables of each session. The diagnostic trial abandoned in AppContainer is recorded separately.
Its forced shutdown is not counted as normal shutdown.

After the end of the instrumental session, Dolphin's private copy was replaced by its retained
official copy, SHA-256 `17b01a8629d865378a45e58d5fcebf9dcc3f7919c719130a4ffdd1ca2b27b635`. Private
profiles have `GDBPort=-1`, empty socket, debugging mode disabled and cheat codes disabled. The four
former controlled GDB ports are closed. Previous private configurations and diagnostic copy are
archived locally to make this repair reversible.

The last test uses this **official emulator without patch and GDB**: cold start of
`gameplay-check.iso`, title screen, loading by the interface of the recovery point created for the
same ISO, then ordinary launch of Billy's fight without ID substitution. The first menu displays
Kirlia 29 and Pelipper 30. The window is then closed normally, native code 0. This last control is a
start and fight test up to the menu, without full turn.

The overall audit after this close compares the source images, **2,011 files of `game/`**, **2,691
files from original installation Dolphin** and **46 personal profile files** to the beginning
manifest of this pass: **no difference**. No personal files are restored or replaced. The historical
variations of Qt.ini and SRAM in the first pass remain described in [the follow-up
v0.5](DESKTOP_V05.md). The present audit does not re-attribute them.

## Source of evidence

The names below identify private, undistributed reports. Their fingerprints allow us to distinguish
between the statements of evidence without publishing their content or the personal data they
protect.

| Private reference | SHA-256 |
| --- | --- |
| `expected-gameplay.json`, reading both ISOs | `24b01ba7d5cc9a4cf0c7209b323876e1b8deb539425523af4c5e6f3a93d2bc20` |
| `story-starters-runtime-validation.json` | `128e5440526b57121bf1d5775e3c33fbb143043fa2c35d14f7176793a1e44192` |
| `purification-runtime-validation.json` | `a4e89ae91c04f286ccca698edf677f56bf785c3f333d60ae1b7eb72fb0436126` |
| `tm-evolution-runtime-validation.json` | `b1427f04972e10af7e84c2382b38a134dfde91fd0e480c8cb13680aabd739888` |
| `shop-runtime-validation.json` | `133e028a0e3200cddbe1cbe3fddc9b126c9ffb4c9a7bb1d8be971ec697b8d7e0` |
| `chest-runtime-validation.json` | `12b415b4dac60ae86bd77cff7d2ab79b7511f9155535cdb3a8aa4b8d728dfb91` |
| `boss-164-roster-runtime-validation.json` | `2c09e22a052f64238d78a3415ee00c056afe031e100d0d348b9c463fdbe8c6f2` |
| `boss-runtime-suite-validation.json`, seven cases and final audit | `a78f6670fdfa056d012aada486fc5cea540f446143061387c8d3dd95a9e9c2be` |
| `capture-runtime-validation.json` | `0d4544cbe0a29e9202a74fea978809d3b20272c806b701cc42b103e70454eb3d` |
| `final-audit-after-cleanup.json` | `da101096e81934ca71d818004e0ef064a338f871382120405978c382fd505e4f` |
| `final-official-gameplay-run.json` | `7bedfed72a3d28c14d5fa0ca09f85c00dacceb441f75254f9c5f772e0f0b4cba` |
| `final-audit-after-official-run.json` | `774d81a998a6d5f3699f1b84aec8f0acd17c4b5db20f35867de68114ed429feb` |
| `final-official-runtime-validation.json` | `8dca4874411b1ec1ce4402f23d84b643d5b498853e6d41e572162598db1c0fcc` |

These controls do not cover a complete progression of the scenario, all special events, the
execution of all capabilities, the capture of the other six boss Shadow Pokémon, balancing of an ordinary
part or a physical console. No data flaws of the randomizer were reproduced in the cases tested. The
corrections delivered concern the insulation and follow-up of the validation launcher, with nine
dedicated tests, and documentation of evidence and limitations.
