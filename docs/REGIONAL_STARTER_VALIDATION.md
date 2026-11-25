# Regional starter validation

The USA and Japanese extension separates native-data checks, complete patch
planning and Dolphin trials. The existing [European campaign](STARTER_PIPELINE_VALIDATION.md)
completed 885 patch-plan attempts. Those results are not counted again as
USA or Japanese tests.

## November 24, 2026 checks

The four original regional RVZs were decoded with the application's integrated
converter. Every decoded image passed the production whole-disc allowlist, and
each source RVZ's complete digest was unchanged afterward. The native executable
and species-table evidence was then matched byte for byte with these images.
No emulator was started and no save was opened by these checks.

| Check | USA Colosseum | Japanese Colosseum | USA XD | Japanese XD |
| --- | --- | --- | --- | --- |
| Original executable matches the exact supported digest | Passed | Passed | Passed | Passed |
| All 386 native species IDs and learnsets match the corresponding European game | Passed | Passed | Passed | Passed |
| Natural moves at the actual starter levels match Europe | Passed, levels 26 and 25 | Passed, levels 26 and 25 | Passed, level 10 | Passed, level 10 |
| Native first-capture instruction contracts | Not applicable | Not applicable | Passed | Passed |
| Fresh complete regional patch plans | 32 valid, 4 expected exclusions | 32 valid, 4 expected exclusions | 32 valid, 4 expected exclusions | 32 valid, 4 expected exclusions |
| Fresh isolated Dolphin trial | Passed: native start and both move sheets | Passed: native start and both move sheets | Passed: simulator and starter move sheet | Passed: simulator and starter move sheet |

The Colosseum species tables also match the production whole-REL allowlist.
The retained native artifacts from both games match the corresponding members
read directly from the whole-disc-qualified originals. The executable checks
also use their own exact production digests.

All input artifacts were read without alteration. Modified images from earlier
HD or gameplay tests were deliberately excluded from complete patch planning.
The retail-identity validator was not weakened to accept those images.

## Sensitive natural move sets

The following move sets agree across Europe, USA and Japan within each game.
Empty move slots stay empty; they are not filled with random attacks.

| Species | XD, level 10 | Colosseum, levels 26 / 25 |
| --- | --- | --- |
| Ditto | Transform | Transform |
| Wobbuffet | Counter, Mirror Coat, Safeguard, Destiny Bond | Same |
| Smeargle | Sketch | Sketch |
| Beldum | Take Down | Take Down |
| Metang | Take Down | Take Down, Confusion, Metal Claw; Scary Face is also learned at level 26 |
| Magikarp | Splash | Splash, Tackle |
| Abra | Teleport | Teleport |
| Metapod | Harden | Harden |

Shedinja's native learnset was included in the table comparison, but it remains
excluded from starter selection by the existing engine policy.

XD's original first capture is Snag-only and guaranteed for Shadow ID 1. The
four native instruction contracts pass on the retained USA and Japanese
executables, with `starter_attack_required: false`. A starter does not need
a damaging move to pass that encounter. This does not claim that every
natural move set makes later battles easy.

## Complete regional campaign

The completed patch-plan campaign requested Ditto, Wobbuffet, Smeargle, Beldum,
Metang, Magikarp, Abra, Metapod and Shedinja. Each was tested with both actual
default presets and two seeds, on all four USA/Japanese discs.

| Scope | Attempts | Valid complete plans | Expected Shedinja refusals | Unexpected errors |
| --- | ---: | ---: | ---: | ---: |
| Colosseum USA/Japan, Pokémon-only | 36 | 32 | 4 | 0 |
| Colosseum USA/Japan, Pokémon + moves | 36 | 32 | 4 | 0 |
| XD USA/Japan, Pokémon-only | 36 | 32 | 4 | 0 |
| XD USA/Japan, Pokémon + moves | 36 | 32 | 4 | 0 |
| Total | 144 | 128 | 16 | 0 |

The 16 Shedinja requests produced only the exact existing policy refusal.
No other error was suppressed. Each report has its final source-preservation
record, and all four original RVZ and decoded ISO digests were verified again
after the complete campaign.

The 96 natural starter rows were also compared with the regional native
learnsets, including the automatically chosen second Colosseum starter and
empty move slots. All matched. For each admitted species, region and preset,
the two seeds produced distinct complete patch payloads.

These results use Colosseum engine `natural-starter-pair-safety-v28` and XD
engine `xd-native-capture-tutorial-v18`. Median valid-plan durations were
10.09 seconds for Colosseum Pokémon-only, 10.45 seconds for Colosseum Pokémon +
moves, 7.11 seconds for XD Pokémon-only and 7.62 seconds for XD Pokémon + moves.
The matrix itself wrote no randomized output ROM. Its four decoded original
images were subsequently used for the separate Dolphin trials below, then
removed after all source hashes were checked again.

Use explicitly supplied, unmodified ISO/GCM images. The matrix script verifies
the complete image before planning and its digest again afterward. It writes
only a new report, never an output ROM.

```powershell
python scripts/validate_starter_matrix.py --image original-colosseum-us.iso --image original-colosseum-jp.iso --image original-xd-us.iso --image original-xd-jp.iso --species 132,202,235,374,375,129,63,11,292 --preset pokemon --seed regional-A --seed regional-B --report build/regional-starters-pokemon.jsonl
python scripts/validate_starter_matrix.py --image original-colosseum-us.iso --image original-colosseum-jp.iso --image original-xd-us.iso --image original-xd-jp.iso --species 132,202,235,374,375,129,63,11,292 --preset pokemon-moves --seed regional-A --seed regional-B --report build/regional-starters-moves.jsonl
```

These are complete production patch plans, including archive repacking and
native output checks. They do not establish that every selected starter has
finished every battle. Dolphin trials remain a separate functional check,
using test images and private emulator profiles with audio disabled.

## Native Dolphin trials

Four separate test images were created through the production service with
the Pokémon-only preset, seed `v212-regional-sensitive`, and explicit sensitive
starter choices. Each trial began with **NEW GAME on a fresh private profile**,
without an existing card, save state, edited checkpoint or RAM write.

| Disc | Starters observed in the native party | Moves observed in the game |
| --- | --- | --- |
| Colosseum USA | Ditto, level 26; Smeargle, level 25 | Transform only; Sketch only |
| Colosseum Japan | Wobbuffet, level 26; Metapod, level 25 | Counter, Mirror Coat, Safeguard, Destiny Bond; Harden only |
| XD USA | Ditto, level 10 | Transform only |
| XD Japan | Wobbuffet, level 10 | Counter, Mirror Coat, Safeguard, Destiny Bond |

Each one-move Pokémon had three empty slots with no invented replacement
attacks. Both XD trials won the original opening simulation and entered the
lab. English and Japanese native summary pages were inspected directly.
Colosseum's two party IDs were also confirmed through the qualified regional
accessors using a read-only memory mapping.

These are **startup and starter-summary checks**, not full regional campaigns
or first-Snag tests. Early ordinary battles and the first capture require the
separate European fresh-start checks. The regional trials used original
graphics, 4:3 display, 200% QA speed and the `No Audio Output` backend with
volume zero. Controller input went only to each private emulator instance.

All five Colosseum movie files and all 28 XD movie archives were byte-identical
to their respective originals. The four original RVZ hashes and four decoded
image hashes were verified again afterward. Only the four generated test ISOs
and four owned decoded copies were deleted, freeing 10.88 GiB; original RVZs,
test cards, profiles, reports and screenshots were retained. All four owned
emulators were closed after the observations. Their intentional termination
after the test is recorded separately from a game crash.

Private runtime evidence is in `build/v212-regional-runtime/`, including
`regional-runtime-verification.json`, each trial's `preservation.json`,
`original-movies.json`, native screenshots and read-only VI progress samples.

## Regional runtime preparation

The following VI counters were re-derived from the exact original startup
register initialization and SDK getter instructions. Retained read-only monitor
receipts also show each counter advancing; those receipts are historical, not
new gameplay tests.

| Game ID | Region | VI counter | SDK getter | Initial `r13` |
| --- | --- | --- | --- | --- |
| `GC6E01` | Colosseum USA | `0x8047A84C` | `0x800AA280` | `0x80480820` |
| `GC6J01` | Colosseum Japan | `0x80465F14` | `0x800A7F2C` | `0x8046BF00` |
| `GXXE01` | XD USA | `0x804EAC54` | `0x800BA25C` | `0x804EFE20` |
| `GXXJ01` | XD Japan | `0x804C8144` | `0x800B66F0` | `0x804CD340` |

Colosseum's retained original accessors establish party roots at
`0x8047ADB8` (USA) and `0x80466468` (Japan), with each slot at
`read_u32(root_global) + 0xA0 + slot * 0x138`. No regional XD party pointer
was established by this bounded check; European pointers must not be reused
as guesses.

Private local evidence is retained under `build/v211-regional-starter-plans/`:
`retained-runtime-contracts-v2.json`, `retained-starter-catalogs.json`,
`source-preparation.jsonl`, `native-input-bindings.json`, the four preset JSONL
reports and `qualified-matrix.json`.
These reports contain artifact digests and explicit scope limits, not game data
for distribution.
