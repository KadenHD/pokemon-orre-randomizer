# Chiefs identified and prudent rules — PAL GC6P01

Static observation of October 31, 2026. The transformations work on copies in memory. No original
file, team pointer or script is changed.

## Sources and identity

- `game/files/common.fsys`, membre `common_rel` : SHA-256
  `ee2677af555dc59626f978e743235831a76cb23bae93f3fdd1060d808f749d0b`.
- Tables obtained with `randomize_trainers.layout` and the self-relocations of the REL, controlled
  in the bounds of the sections: trainers `0x15DEEC`, 820 lines of `0x34`. Pokémon of trainers
  `0x16AE44`, 5,510 lines of `0x50`. Species `0x1F05CC`, 413 lines of `0x11C`. Obscure `0x2125A0`,
  97 lines of `0x38`.
- The FR/UK names are decoded from the string directories of the same REL. Each leader is
  simultaneously checked by index, class, name ID, FR/UK strings and first index of his team. No
  detection from the level.
- Primary community diagram pinned: [CMTrainerPokemon.swift, commit
  f2d6c4af](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/enumerable/CMTrainerPokemon.swift),
  local copy `analysis/generated/v03-references/CMTrainerPokemon.swift`, SHA-256
  `a0c5ae733e17ccf9fe63b2bf355302b8850ec0d1f82af29edc139e678bb1f010`. This source specifies the six
  IVs to `+0x1C…+0x21` and the six EVs to the bytes `+0x23,+0x25,+0x27,+0x29,+0x2B,+0x2D`. The
  interlayer bytes remain intact.
- REA 6.8.0: read-only status. No active binary session. This pass exploits the saved schema and the
  exact bytes via existing local parser. It does not constitute an execution observation.

The above offsets are offsets **REL file**, not memory addresses.

## Inventaire explicite

Each pair is `index dresseur → premier index Pokémon`. The engine records the exact offset and
references of each slot in `boss_inventory`.

| Chef FR / UK | Class / ID name | Pinted variants | Populated slots | Dark slots |
|---|---:|---|---:|---:|
| BOULEDISCO / MIROR B. | 4 / 4285 | 162→2478, 163→3991, 164→3998, 165→4831, 166→4838, 793→5412 | 29 | 3 |
| DAKIM / DAKIM | 4 / 4195 | 211→2555, 212→4005, 213→4012, 214→4866, 215→4873, 795→5300 | 29 | 3 |
| VENUS / VENUS | 4 / 4113 | 326→2674, 327→4019, 328→4026, 329→4901, 330→4908, 796→5426 | 29 | 3 |
| TECK / EIN | 4 / 4269 | 403→2814, 404→4033, 405→4040, 406→4936, 407→4943, 807→5293 | 29 | 3 |
| HELGONZA / GONZAP | 23 / 4266 | 425→4047, 426→5209, 427→5216, 811→5328 | 21 | 2 |
| JAKYLLA / NASCOUR | 5 / 4167 | 437→4110, 438→4117 | 12 | 1 |
| NOSFRAT / EVICE | 6 / 4326 | 439→4124, 440→4131 | 12 | 1 |
| **Total** | | **7 personnages, 32 enregistrements** | **161** | **16** |

The six fixed locations per team give 192 locations, 31 of which are empty. The 161 populated
locations each have a single reference since the original 820 erecting lines. The 145 non-Shadow Pokémon
are therefore editable without changing another blocker. This finding is recalculated, not only
assumed by theallowlist.

The Shadow Pokémon observed here bear IDs 19, 21, 23, 34, 38, 43 and 44, repeated in their variants.
Their species also belongs to the global table of the Shadow Pokémon. Their six IVs are worth `0xFF` in
these lines. The non-Shadow Pokémon of this inventory have six IVs and six null EVs. `0xFF` is never
replaced by a literal value 31.

The groups identify the main leaders of the story and their variants present at the table. The
presence of a table variant, including a dark variant, does not prove its scenario state or its
accessibility in a backup. No rewriting of scenario conditions is attempted.

## Contrat de transformation

`apply_boss_rules(original, current, seed, options, tables=None) -> (bytes, summary)` is called
**after** `apply_rel_rules`, before `apply_dol_rules` and the final report. Both options are
independent and disabled by default.

### `boss_stronger`

For eligible non-obscuous slots only.

- Current level multiplied by 1.1, rounded to the nearest integer and capped at 100. It is therefore
  composed with the global multiplier already applied. It is not calculated a second time since the
  original level.
- IV literals between 0 and 31 raised to a minimum of 20. Each upper IV remains superior. The
  sentinels and other off-range bytes remain intact.
- If the proposed total is not more than 510, then all the EVs in the slot remain as they are and
  the report explains the refusal. No existing value is reduced. The original data inventoried give
  a total of 384 after this rule.

These are explicit difficulty parameters, not a pretension to rebuild an original intent of the
game. Dark ones keep their current levels and IV/EV: strengthening a leader does not reinforce the
Pokémon that the player must capture.

### `boss_team_variety`

The engine retains the separate families already present. It replaces only a family duplicate in a
modified non-obscurable slot. The families of the dark and other protected slots are reserved first.
The families of the slots remaining on the team never serve as a rerun.

The pool retains the generations and legendary authorized ones, as well as the potential BST balance
from the original species of the slot. Exclusions are applied before balancing. The TSB withdrawal
uses only authorized candidates. Shedinja is not added by this rule. If no candidate is available,
the duplicate remains present and `unresolved_team_duplicates` gives the trainer, slot and reason.
No filter is implicitly disabled.

The species, its name identifier and, if necessary, a second aptitude selector that has become
unavailable are updated. The ability and types are read from the **courant final** catalogue, which
includes a possible global randomization of the properties. If `randomize_trainer_moves` is active,
the only slots whose species is replaced receive a reprint with the same offensive/STAB guarantees,
anti-doublons and exclusions as the other trainers. If this option is inactive, their capabilities
remain unchanged.

The drawing uses SHA-256, the exact UTF-8 and a versioned key including the trainer and slot. It is
independent of the order of the list provided. The application from the same `current` produces the
same bytes. Applying the reinforcement a second time on an already reinforced output is not an ideal
operation.

### Protections

An obscure slot, shared with another blocker or containing a capacity marker `0xFFFF`/out of
catalogue is entirely preserved by these two rules. No empty slot is filled. The number of locations
and their order are unchanged. The engine refuses any modification outside the authorized offsets of
the only eligible slots.

The global table of the Shadow Pokémon does not receive any writing. The 48 distinct species and
families produced by the previous rule of uniqueness therefore remain as they were. The option does
not change any evolutions, shops, objects held, scripts, scenario conditions, purification counter,
AI or combat references. The themes of type are not offered in this pass.

## Validation and limitations

`python -m unittest tests.test_boss_rules`: **10 successful tests**. Seven synthetic tests check for
inactive options, IV/EV/level terminals and masks, refusal of an EV floor that would exceed 510,
slot sharing, impossible generation exclusions, markers, and the use of the final types for STAB.
Three optional local tests inspect the real REL and its composition with advanced rules.

On the original REL, the two options change 145 non-Shadow Pokémon slots, including **12 species changes**
which eliminate the duplicate families of Bouledisco variants. The 16 dark slots remain completely
identical. The tested composition also activates types/aptitudes/stats/randomized capabilities,
generation 3 alone, legendary prohibited, BST balancing and global levels ×2: the 48 dark families,
level terminals and STAB guarantees are retained. The six bytes before each of the capacity IDs
remain intact.

These controls establish the data produced and their invariants. They do not prove the difficulty
felt, the choice of attacks by AI or the accessibility of each variant in part. No Dolphin start or
leader fight was realized by this isolated pass.
