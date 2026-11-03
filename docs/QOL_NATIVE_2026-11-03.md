# EXP and accelerated purification: regional native contracts

Both settings are independent and are worth **×1 by default**. At both ×1 the patch returns received
bytes without adding a section or changing the game. These options do not rewrite any backup.

## Effect of settings

**Combat EXP ×0.25 to ×5** multiplys the final gain of each beneficiary, after the native bonus of
the object and owner. The result is rounded to the nearest integer, with a minimum of 1 for an
initial gain positive. The same setting applies to the EXP set aside for a Shadow Pokémon when the
game allows. This reserve is not multiplied upon its release. The initial starters' EXPP, the
starting level and the Super Bonbons keep their original processing. Level climbs and the gain
display use the modified value in the native course.

**Decreased Heart Gauge ×1 to ×10** multiplys only negative variations calculated by the native
routine of purification progression. Gauge increases are not accelerated. The effects of nature and
objects are calculated before this multiplier. The game then retains its floor at zero. The option
does not automatically purify a Pokémon and does not unlock any scene, Relic or reward.

## Qualification of executables

The names and readings of the USA route come from the primary sources of [Colosseum decompilation
project](https://github.com/dougchansan/pkmn-colosseum/tree/ad02df4900c623d16d02b9a8ddd9c53ea0cd3db2),
notably `pokemon_range_8011F77C.c` and `fight_range_80211A00.c`. This source is used to interpret
the instructions. It is not executed or compiled by the application.

The functions are found separately in the three original DOLs by searching for their complete
sequence, with normalization of the calls and addresses relocated. Each search has a unique result
in a code section. The production patch then checks the **non-standardized of the entire function**
print, the replaced instruction and the exact identity of the original DOL. It does not calculate
the regional addresses from a common offset.

| Region | Fonction EXP | Targeted EXP instruction | Fonction de jauge | Targeted gauge instruction |
| --- | --- | --- | --- | --- |
| Europe `GC6P01` | `0x80227DF4` | `0x80228150` | `0x80123A84` | `0x80123CE0` |
| USA `GC6E01` | `0x802232F4` | `0x80223650` | `0x8011F910` | `0x8011FB6C` |
| Japon `GC6J01` | `0x8021EA8C` | `0x8021EDE8` | `0x8011D0C8` | `0x8011D324` |

The EXP point precedes the separation between the normal gain and the dark reserve. The gauge point
replaces the addition of the variation to the gauge, just before the native floor at zero. The
displaced instructions are replayed and the execution resumes with the following instruction,
without modifying the return log. The registers still necessary for the native course are retained.

The full calculation of EXP uses a denominator of 10,000. A defensive ceiling of 65,535 before
multiplication avoids any overrun of the 32-bit calculation. It exceeds the eligible native
earnings: the 413 cash lines in each region have a maximum EXP yield of 255. Even at the 100 level
with three consecutive bonuses of ×1.5, the gain per beneficiary remains less than 12,295.
Randomized statistics do not change this yield.

The added code uses the `text2` section already reserved by gift and Shiny capability patches, or
creates the same reservation if it is absent. The arena guard is extended accordingly. The function
footprint, the old reservation and the exact list of editable ranges must match before writing the
new bytes.

## Verifications and limitations

The tests perform the PowerPC instructions produced in an independent decoder: 189 combinations of
gains/rates/regions and 72 combinations of gauges/variations/multipliers/regions, with feedback
control, registers, rounding, minimum and native floor control. The three original executables are
also subject to repeatability checks, composition checks with existing patches and rejection of
altered instructions or headers.

### Actual observations in Dolphin Europe

The combined ISO Europe was played with **EXP ×2 and gauge ×3**, on a copy of a test card isolated
from the personal profile. The stops on native instructions allowed to compare the values before and
after the added blocks, then after the play entries in the Pokémon records.

| Witness | Native value and observed result |
| --- | --- |
| Combat gauge reduction, Lanturn | Change -0.5 to -1.5. Whole gauge **6 650 → 6 500** |
| Combat gauge reduction, Blastoise | Change -0,75 become -2,25. Whole gauge **800 → 575** |
| EXP, Lanturn still too dark | Gain **673 → 1 346** in the block. The native threshold then refuses to reserve, which remains at **0** |
| EXP, Blastoise ready to receive its reserve | Gain **673 → 1 346**. Reservation actually written by the game **12 313 → 13 659**, that is **+1 346** |

The rejected Lanturn witness therefore does not count as an applied gain. The one of Blastoise
proves the actual addition of the EXP in reserve. The catches control the registers still used and
the return link. The raw Pokémon files before/after differ only in the gauge or the expected
reserve. The debugger exposes the half PS0 of the floating registers, not the paired-single PS1. No
capture forces a PC, a gauge, an EXP, a combat result or a reward. Two actual doorways use a
declared and kept navigation shortcut to Pyrite Town. Destination and native argument are redirected
together, without jumping to a combat instruction.

The test cards contain a synthetic progression inherited from the gift tests. An inconsistency of
this data was corrected in **nouvelles** v3 cards: six team Pokémon had a positive gauge but their
overall flag indicated purification. Twelve bits were adjusted by keeping the total of 25, without
changing the Pokémon, the EXP, the gauges, the scenario or the old backup locations. The first
witness Blastoise came from the old card. The Lanturn gauge witness and the two EXP witnesses came
from the new consistent test. This fixture change is not a patch of the production patch and does
not prove 25 purifications performed.

The healing of the six Pokémon was also performed with the native nurse in the Europe trial.
Separate USA/Japan maps were then received only the three restored PV bytes observed in this
healing, to prepare any tests. This offline preparation does not constitute a healing performed or a
QOL validation on these two regions.

The two Dolphin Europe processes were closed normally. The fingerprints before/after protected
files, original ROMs and the Dolphin Personal Profile are identical. The guards of the test tool
also refused out-of-contract applications. These refusals and reading errors are kept separately
from successful captures.

### Limites restantes

**The new QOL USA and Japan races were not played in this essay.** Their native contracts, the data
matrix and the PowerPC instructions are qualified separately. This does not replace a real regional
observation. No rise in the level of a normal Pokémon, reserve release during the final
purification, decrease triggered by the step or branch of the zero gauge floor was observed here.
The other multipliers remain covered by the automated controls. No complete part or validation of
the balancing is claimed.

Previous creation reports shall retain their initial validation indication to be performed. Private
aggregate dated `build/v15-runtime/result.json` describes subsequent observations and their
limitations, without rewriting these reports.

Listings, search hashes and the pinned source clone remain private in `build/qol-v15/`. The
captures, maps and monitors of this execution remain in `build/v15-runtime/`. The game data are not
distributed.

### Suivi distinct en v0.16

The [notes de validation v0.16](DESKTOP_V16.md) records the additional US/Japan observations and the
state of the new Europe trial. They distinguish each stage actually played, the synthetic
preconditions and the boundaries of the bridge. They complement this historical account without
broadening its scope.
