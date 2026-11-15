# Eagun's native story takes priority

The original purification-reward patch could hide Eagun at home before the
player exchanged P★DA numbers with him. This obstructed the native story path
towards the laboratory. The original scene remained in the randomized disc;
the patch changed its accessibility.

## Native evidence

The three retail home scripts use the same relevant entry points. Japan has
two unrelated camera constants elsewhere in the script.

| Native home CMS location | Behavior |
| --- | --- |
| Function-table entry `0x38` | Eagun's native interaction at `0x3561` |
| `0x312A` | Persistent story/event loop |
| `0x339C`, message `0x51DA` | Eagun asks for the player's P★DA number |
| `0x33E4`, message `0x517E` | Number-exchange confirmation |
| `0x34E4`, native command 78 | Sets flag 3535 after the exchange |
| `0x3503`, native command 78 | Sets flag 2499 |
| Native interaction `0x3561` | Gives the Master Ball while flag 2531 is set and 3541 is unset |
| `0x3765`, native command 78 | Sets flag 3541 after that handoff |

The pinned community command reference labels commands 78 and 79 in reverse.
The original European executable confirms command 78 at `0x8019489C` loads
the value **1**, while command 79 at `0x80194724` loads **0**. The new predicates
follow those native instructions rather than the misleading labels.

The legacy patch considered six early Relic Stone story flags sufficient. It
redirected entry `0x38` and replaced the setup epilogue at `0x678` to hide the
home actor. Neither redirect checked the number-exchange flag. The confirmed
affected archive still contains the unchanged native number-exchange code.

The purification explanation sets home global 1 at `0x3AC9`. The background
loop checks it at `0x334E`, then command 111 waits for directional input. Its
native PAL implementation at `0x801CF62C` checks the four direction bits and
analog movement above two units; the A button alone does not satisfy it.
Walking after the explanation starts the number-exchange dialogue. There is
no additional telephone-specific doorway or geometric threshold in that branch.

## Current rules

- Eagun's home actor **0**, native interaction pointer and native story setup
  remain unchanged. Future dialogue and item handoffs remain reachable.
- A separate [companion layer](EAGUN_COMPANION_GIFT.md) changes only actor **3**'s
  initial visibility operand after its gift was received and the safe story
  gate is met. It preserves the setup epilogue, phone exchange, pending Master
  Ball path and Eagun's native interaction; it never restores the legacy redirects.
- Purification gifts and the bonus encounter require the six early flags plus
  **3535**, which proves that the number exchange happened.
- While **2531 is set and 3541 is unset**, custom interactions wait for the
  native Master Ball handoff. This does not postpone early purification gifts
  until the Master Ball: before its notice, flag 2531 is unset.
- The same predicate governs custom actor visibility, gift interaction, bonus
  eligibility and its P★DA notification.

The original gift receipt flags, 2737 and 2740, do not alias the phone or Master
Ball flags. All are one-bit definitions in native group 3, assigned distinct
positions by the native initializer. The 127 original map CMS scripts and the
common script contain no direct flag-command references to either gift receipt.
The generic command 80 writes only the specified flag's bits. Taking an added
gift therefore does not itself mark the native phone exchange as completed.

## Recovery support and limits

[`event_story_recovery.py`](../../orre_randomizer/engine/event_story_recovery.py)
contains pure byte transformations for the exact legacy patch. It does not
open a ROM, save, emulator or profile, and performs no filesystem writes.

For a recognized home CMS it restores the native interaction pointer and
epilogue, retaining every other current byte. For the recognized shrine CMS it
retains both configured purification thresholds, receipt checks and original
gift constructors, while adding the phone and native-handoff guards. Other
decoded archive members remain identical. Unknown redirects or altered native
number-exchange code are rejected.

In-memory tests against the affected archive extracts preserve the native
number-exchange sequence byte for byte. The CMS model executes that unchanged
handoff and obtains flags 3535 and 2499 through native command-78 semantics.
Tests also cover missing phone exchange, pending/completed Master Ball,
previously received gifts, reversed thresholds and rejected unknown patches.
The native home route and the unchanged number-exchange handoff are tested at
every purification count from 0 through 48. Exchanging numbers has no
purification-count requirement; only the added gifts have numerical thresholds.

Separate muted PAL Dolphin replays also completed the native contact exchange
at exactly 0 and 25 purifications, obtaining both native flags 3535 and 2499
without receiving either added gift. Another replay completed the original
Master Ball handoff: the copied bag gained one Master Ball and native flag
3541 was set. These cases use new production ISOs and copied QA cards, not a
modified personal ROM or personal save.

This establishes that the known obstruction is in ROM code and does not
require editing saved progression to remove. It is not a claim that a user's
entire game state has been inspected or that recovery has been replayed in
Dolphin. No existing ROM or personal save is changed automatically.
