# Starter patch-plan validation

The v2.1.1 regressions exercise the complete production patch planners, rather
than accepting a species in its constructor and stopping there. This distinction
matters for XD: a starter could pass its constructor while a later tutorial check
still refused the complete plan.

## Regular regression suite

`tests/test_starter_pipeline.py` and `tests/test_xd_starter_pipeline.py` cover:

- Beldum, Metang and Magikarp through complete native patch planning, including
  archive repacking and the planners' original-data and allocation checks.
- Both Colosseum constructor slots at their actual levels, 26 and 25; XD at 10.
- The two real default presets, historical non-random move mode and an XD
  Harden-only starter with randomized types and abilities.
- Real preview results and the exact serialized plan returned through the
  preview callback. Patch payload digests and displayed encounter moves must
  agree with independently built plans for the same source, seed and options.
- Full-image hashes before and after the native checks. These tests never
  publish an ISO or open a save, launcher or emulator.

The native cases require locally retained original European images and skip
explicitly when those prerequisites are unavailable. Public CI does not replace
their retail-identity checks with permissive mock validators. The small matrix
harness tests run without game data. Separate instruction-contract tests cover
XD's native first-capture behavior on the three regional executable layouts.

## Expanded developer matrix

`scripts/validate_starter_matrix.py` accepts explicitly supplied original raw
ISO/GCM images. It verifies each complete image against the production region
allowlist, calls the same patch planner used by creation, validates the final
serialized plan's bounds and records its payload digest. No output ROM is
written. Only the new JSONL report is created; an existing report is never
overwritten.

```powershell
python scripts/validate_starter_matrix.py --image original-colosseum.iso --image original-xd.iso --species all --mode natural --report build/starters-natural.jsonl
```

The `starter-only` scope isolates manual starter selection: it permits all three
generations and legendary species, disables other randomization and tests both
Colosseum slots with the same requested species. This intentionally does not
represent the default family-diversity configuration.

Shedinja remains excluded by the existing engine policy. A matrix attempt
for that species must receive the exact native manual-selection refusal; it is
recorded as `policy-exclusion`, not as a successfully generated plan. Default
preset scopes likewise retain their legendary exclusions. Any other exception,
unexpected message or accepted excluded species remains a failure.

Use the real presets and additional seeds for broader integration cases:

```powershell
python scripts/validate_starter_matrix.py --image original-colosseum.iso --image original-xd.iso --species representative --preset pokemon --seed sample-A --seed sample-B --report build/starters-pokemon.jsonl
python scripts/validate_starter_matrix.py --image original-colosseum.iso --image original-xd.iso --species representative --preset pokemon-moves --seed sample-A --seed sample-B --report build/starters-moves.jsonl
```

Preset matrices keep each preset's actual move mode; the script refuses a
conflicting explicit mode. The starter-only scope also accepts `--mode original`
or `--mode random`, and repeated `--mode` arguments expand the cross-product.
Supply another `--image` to test another supported region; no drive scan or
automatic ROM download is performed.
`--species auto` leaves starter selection automatic, which can reproduce a
reported seed without replacing either randomly selected starter manually.

The report starts with its exact scope, source digests, engine versions and case
count. Each completed case is flushed immediately. Its final record gives pass,
policy-exclusion and failure counts and verifies that the original images are
unchanged. An interrupted report without that final record is incomplete.

Exhaustive full plans can take tens of minutes, so this developer sweep is kept
outside the regular per-module test deadline. It retains production validation;
it does not bypass expensive asset checks to manufacture a fast result.

## Local v2.1.1 results

The November 23, 2026 read-only campaign completed the following European-image
patch-plan scopes. Expected policy refusals are separate from generated plans.

| Scope | Completed attempts | Valid full plans | Expected Shedinja refusals | Unexpected failures |
| --- | ---: | ---: | ---: | ---: |
| Colosseum, every national species, natural moves, both manual slots | 386 | 385 | 1 | 0 |
| XD, every national species, natural moves | 386 | 385 | 1 | 0 |
| Actual Pokémon-only preset, 13 selected species, two seeds, both games | 52 | 48 | 4 | 0 |
| Actual Pokémon + moves preset, same species/seeds/games | 52 | 48 | 4 | 0 |
| Final Colosseum engine, automatic natural pair, three seeds | 3 | 3 | 0 | 0 |
| Final Colosseum engine, manual first starter with automatic partner, two seeds | 6 | 6 | 0 | 0 |

These are 885 completed attempts: 875 valid complete plans and ten explicit
checks of the existing Shedinja exclusion. All original full-image hashes were
unchanged. No ISO, save or emulator profile was created by these matrix runs;
their combined JSONL evidence occupies less than 0.5 MiB.

The exhaustive manual runs began before the final automatic-pair safeguard was
added. That safeguard retains the old domain for two manual selections. Final
engine `natural-starter-pair-safety-v28` / starter rules
`starter-pair-natural-safety-v3` reproduced the complete serialized patch digests
for Metapod, Magikarp and Abra in both manual slots. The automatic and
manual-first samples above were then rerun under the final engine. The formerly
harmless automatic pair for seed `v211-start-pair-5534` became Sandslash at level
26 and Krabby at level 25, without adding moves outside their native learnsets.

The initial developer harness treated every refusal as a failure. Its original
traces and result records were retained. Qualification accepts only the exact
existing manual-exclusion exception for the expected species; all other errors
remain failures. The shipped harness now records these expected cases directly
as `policy-exclusion`, with unit tests against accidental error suppression.

An additional full production plan checks an advanced combination outside the
885-case matrix: natural starters, randomized level-up moves and story-family
diversity with only Abra and Silcoon admitted. Their final learned attacks are
used for pair safety and written unchanged to the starter constructors. Native
integration tests compare those constructor moves with the final REL learnsets.

## Evidence limits

A successful patch plan establishes that the selected species survives the
complete creation path and that its planned output is internally valid. It does
not establish a complete playthrough, battle balance, every camera position,
every regional animation or every combination of advanced rules. Dolphin trials
remain a separate functional check, using isolated images and copied cards.

Natural move sets may contain empty slots or only non-damaging moves. XD's native
first capture is Snag-only and guaranteed for Shadow ID 1; it does not require
the starter to damage that target. Keeping natural moves must not silently add
a random attack or rewrite the player's chosen starter.
