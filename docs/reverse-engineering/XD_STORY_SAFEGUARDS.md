# XD story and scripted-encounter safeguards

This audit covers the scripted encounters and trades changed by the randomizer.
It checks preserved native control flow and the first capture tutorial;
it does not establish that every seed, battle or optional rule combination is
free of softlocks throughout a complete playthrough.

## First Shadow encounter

The first encounter keeps battle 224, Shadow ID 1, level 11 and the native
catch-rate field. The game presents a dedicated Snag-only encounter: its menu
prevents Fight/Run and opens the Ball pocket. The original Ball routine gives
Shadow ID 1 four shakes without consulting HP, status, species, catch rate or
random shake rolls. This special case does not apply to other Shadow IDs.

Version 2.1.1 removes the earlier attack-based suitability check. That check
mistakenly treated the scene as a normal battle, rejecting Magikarp's Splash,
Abra's Teleport and other short or conditional learnsets. Some variable-power
moves were also incorrectly classified as unusable. Every starter retains its
selected natural/original/random move policy; no extra attack is inserted.
The existing tutorial replacement pool and native story progression remain.
Keeping Teddiursa instead of randomizing it does not require an attacking
starter either.

Before relying on the native capture guarantee, generation checks four exact
instruction windows in the original European, American or Japanese revision-0
DOL: the Shadow-ID-1 branch, encounter predicate, menu restriction and Ball
pocket selection. It checks them again after later DOL patches. A mismatched
contract fails before the output ROM is published. No runtime patch is added
to the capture routine, no Ball is replaced with a Master Ball, and the starter's
learnset, PP and empty move slots stay intact.

The lab script patch changes only the species operand used for its dialogue
variable. It does not change scene flags, battle outcomes, inventory, branches,
NPC visibility or the native capture progression.

## Hordel's gift and trade

The replacement gift retains Shadow ID 81, its level-25 gift constructor and
native ownership and purification requirements. Both the accepted base form
and evolution are updated in the original trade script, together with the gift
species. The candidate family has two members and one supported evolution route;
trade/Beauty adaptations are admitted only when accessible evolutions are on.
The purified base form itself remains acceptable, so evolution is not required
to complete the exchange.

The original one-time trade flags, full-party handling, ownership checks and
purification checks remain in place. No replacement NPC or visibility gate is
introduced. Incoming rewards and outgoing requirements are separate operands.

## Duking and the Poké Spots

Each requested species comes directly from the corresponding rare encounter
slot. Those three requests remain distinct. Native encounter weights, level
ranges, bait requirements and the two special encounters are preserved.
Insufficient filters are rejected instead of creating unavailable requests.
Poké Snacks use native item ID 361, outside the ordinary-item randomizer's
catalogue, so their supplies are not replaced by the field/shop item shuffle.

The trade patch changes both native species comparisons, incoming/outgoing
name arguments and the remaining-trades name array. It preserves the original
trade flags and control instructions. Field-model patches select models for
the regular encounter branches; they do not replace the native story or bait
conditions that decide when those encounters exist.

## Other changed field appearances

XD's Eagun-partner, Gateon, lighthouse and Gloom changes retarget model/cry
resources. They do not install the additional Colosseum event-gift NPC logic
or change the corresponding XD NPC visibility flags. Shadow Lugia retains its
protected species and Shadow ID for native story/purification checks; its new
display selectors read existing identity data without writing story flags.

## Evidence boundary

Source checks use synthetic cases and already extracted European, American
and Japanese originals. Native Hordel, Duking and lab
scripts are compared byte for byte after patching: only the documented species
or name operands may differ. Tests execute the native forced-capture branch
through its ordinary/forced exits and verify that only Shadow ID 1 or the
native Master Ball case bypasses catch calculation. Mutated/truncated tutorial
contracts are rejected. Complete starter patch-plan checks cover natural,
original and random moves, narrow Poké Spot pools and untouched encounter
parameters. Source analysis is distinct from the recorded Dolphin trials.

Earlier representative in-game trades, captures and the first tutorial replay
are documented in [XD reverse-engineering notes](XD.md). They are historical
evidence. The current release's muted, isolated trials and exact scope are
recorded in the [validation index](../VALIDATION.md).
