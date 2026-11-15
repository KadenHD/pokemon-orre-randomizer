# Colosseum teams after a Snag

Colosseum often switches to a different trainer row after its Shadow Pokémon
has been captured. Those rows contain copies of the ordinary teammates, with
different record identifiers. Drawing each copy independently made an otherwise
unchanged team appear to reroll after a Snag.

The final ordinary records now share one canonical result across those native
capture-state variants. This includes species, moves, held items, levels,
ability selectors, gender/nature arguments, IVs and EVs. Each record retains its
own opaque identifier at `0x18..0x1B`. Seeded shiny decisions and Spinda's seeded
personality inputs use the same flattened alias map. This does not introduce a
new saved identity or change the normal game's PID generation policy.

## Matching the native variants

The inventory uses the original regional tables, not localized display names:

- All trainer fields match, except the team pointer and the three battle
  dialogue IDs at `0x24`, `0x28` and `0x2C`.
- The first team has a Shadow Pokémon; the captured variant has no Shadow slot.
- Every ordinary teammate has a byte-identical native descriptor, excluding
  only its per-record identifier, and occurs in the same relative order.
- A captured Shadow may be removed, shifting the remaining records, or replaced
  by the game's native ordinary Pokémon. Its replacement is not an alias of the
  captured Shadow.

This identifies 70 native capture-state relationships and 184 ordinary-slot
aliases in each supported Colosseum region. Every admitted native matching is
unambiguous. Empty records, Shadow records, trainer rows and later progression
teams remain outside the copied fields.

Examples from the original tables:

| Trainer rows | Native behavior | Result |
| --- | --- | --- |
| Dakim `211 → 795` | Remove the captured Shadow and shift four unchanged teammates | Keep those four seeded teammates |
| Dakim `212 → 213`, `214 → 215` | Replace the Shadow slot; retain four teammates | Keep the four teammates; handle the replacement separately |
| Dakim `211 → 212` | Different species, levels and battle parameters during progression | Keep separate teams |
| Reath `125 → 126` | Change the captured slot and a defeat dialogue | Keep the two unchanged teammates |

Synchronization runs after trainer moves, item changes, boss rules and optional
type/stage policies. If the captured slot's ordinary replacement conflicts with
the retained boss families or shared type theme, only that replacement can be
redrawn, using the configured species filters, stage and power rules. Hard
filters are not silently relaxed; an impossible combination is reported. The
synchronizer does not change the replacement's species when trainer species
randomization is disabled.

The Pyrite dancer aliases are merged with this map. Overlapping pairs and chains
are flattened to their final canonical source before shiny tables or Spinda
seeds are built, avoiding ordering-dependent identity changes.

## Verification

Synthetic tests cover removal and replacement variants, all final record fields,
identifier preservation, different trainer names, changed progression levels,
changed dialogue, alias chains, disabled species randomization and replacement
family/type/stage constraints.

The separately extracted European, American and Japanese originals admit the
same inventory. In-memory checks exercise Pokémon + moves, Pokémon only, and
random trainer themes with forced final stages in all three regions. They verify
every final alias, all untouched Shadow records, opaque identifiers and source
hashes. The native shiny-table builder and Spinda seed builder are also checked
with the final merged aliases.

This batch does not claim a new Dolphin playthrough of the rematches. No ROM,
save or Dolphin profile is modified by these tests. Local audit results are
retained in the ignored `build/v1220-rematch-audit/RESULTS.json` file.
