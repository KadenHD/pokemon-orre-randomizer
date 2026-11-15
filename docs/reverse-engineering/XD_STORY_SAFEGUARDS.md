# XD story and scripted-encounter safeguards

This audit covers the scripted encounters and trades changed by the randomizer.
It checks preserved native control flow and a concrete tutorial matchup gap;
it does not establish that every seed, battle or optional rule combination is
free of softlocks throughout a complete playthrough.

## First Shadow encounter

The first encounter keeps its native battle link, Shadow ID 1, level 11 and
catch-rate override. Its replacement is selected using the generated starter's
actual moves and the final opponent types and abilities. Ordinary type
immunities, absorption abilities, Levitate, Soundproof and Wonder Guard are
accounted for. Conditional attacks do not establish that an ordinary damaging
attack is available; Focus Punch is included in that exclusion.

The same matchup check now runs when **Randomize tutorial Teddiursa** is off.
Previously, an otherwise valid randomized starter could pass without a way to
damage the retained opponent. A concrete example in all three original data
sets is Gastly's level-10 learnset against Normal-type Teddiursa: Lick is its
damaging starting move and cannot hit that target.

An unsupported matchup stops creation before the output ROM is built, using
the existing translated tutorial error. The check does not silently change the
starter, its moves or the tutorial setting. It establishes an available
conventional attack, not a guaranteed battle victory or capture probability.

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

The current source-only checks use synthetic cases and already extracted
European, American and Japanese originals. Native Hordel, Duking and lab
scripts are compared byte for byte after patching: only the documented species
or name operands may differ. Tests also cover the real Gastly/Teddiursa example,
fixed-target type/ability immunities, conditional attacks, narrow Poké Spot
pools and untouched encounter parameters.

Earlier representative in-game trades, captures and the first tutorial replay
are documented in [XD reverse-engineering notes](XD.md). They are historical
evidence, not a fresh replay of this change. No Dolphin process, ROM, save or
profile was used or modified during the current audit.
