# Rules of Shadow Pokémon bosses — v0.5

Local static checks of October 31, 2026 on the original `common_rel` PAL GC6P01, SHA-256
`ee2677af555dc59626f978e743235831a76cb23bae93f3fdd1060d808f749d0b`. This pass reuses the parsers,
schematics and verified identities of [The v0.4 boss investigation](V04_BOSS_RESEARCH.md). No
original file, scenario script or Dolphin status ns is modified by this engine.

## Inventory observed

The 32 variants of the seven leaders identified contain 16 obscure appearances, grouped under only
seven global identifiers. The engine recalculates these groups from `boss_inventory` and the
original bytes, without heuristic level or power.

| Chef | Dark ID | Original species | Appearances in the boss inventory |
| --- | ---: | --- | ---: |
| Bouledisco | 19 | Sudowoodo, national 185 | 3 |
| Dakim | 21 | Entei, national 244 | 3 |
| Venus | 23 | Suicune, national 245 | 3 |
| Teck | 34 | Raikou, national 243 | 3 |
| Helgonza | 38 | Skarmory, national 227 | 2 |
| Jakylla | 43 | Metagross, national 376 | 1 |
| Nosfrat | 44 | Tyranitar, national 248 | 1 |

A table appearance does not prove that a variant is available at a given time in the scenario. Rules
follow the dark group in all its appearances, including out of this boss list. No new obscure group
or fight is created.

## Design choice and contract

`apply_shadow_boss_rules(original, current, seed, options, tables=None)` validates the original
footprint and the seven boss identities, then calls the pure heart `apply_shadow_boss_tables`. It
must execute before the changes of types, talents, statistics and abilities, instead of the ordinary
drawing of dark species when its specific rules are active. The ordinary Pokémon of the trainers
remain entirely as provided in `current`.

- `boss_shadow_legendary_mode`: `any` follows the general authorizations. `preserve` retains the
  legendary or non-gendary status of the original group. `exclude` prohibits legendary and fabulous
  in these seven groups only.
- `boss_shadow_power_mode`: `global` follows `balance_species`. `similar` strictly imposes a
  deviation from the original total at the most `max(50, 20 % du total)`. `free` disables only the
  power preference in the seven groups.
- `boss_shadow_min_bst`: minimum native total of the species of the seven groups, between 0 and 780.
  0 adds no limit. The original species of the first three generations culminate under this entry
  terminal. Too high a value produces a clear error, it is not reduced implicitly.

The totals used are the statistics **natives**, before their possible redistribution. If another
setting changes the totals themselves, this minimum does not promise a minimum of the final
statistics. This scope appears in the report `bst_scope` and must be announced in the interface.

The general exclusions of generations and legends remain strict. Thus, keeping legendary bosses
while banning all legendary globally is an impossible configuration, signalled by an error. Shedinja
is excluded from new draws, and the original species of each group is not its own replacement.

With `unique_shadows`, the engine simultaneously resolves the 48 groups by bipartial pairing between
groups and families of evolution. It first seeks a complete pairing according to the power
preferences. If necessary, it resumes on the sets of candidates satisfying all the strict
exclusions. Only the preferences of the mode `global` can then come out of their nearest window or
choice. Each fold is entered in `power_preference_fallback_ids` and in the line of the group
concerned.

The `similar` mode, the native minimum, the generations and the legendary status are never relaxed
to get 48 families. If no complete match exists, the generation fails with a message that describes
the constraints to be modified. No partially validated ISO is produced by this engine.

The order of families, groups and the choice of species of a family follows the exact UTF-8 and
SHA-256 domains, regardless of the order of dictionaries or inventory list. A species is chosen from
each assigned family, then written in the dark metadata and all the records of the trainer that
share this identifier.

The only permitted modifications are the species u16 of the metadata, and the species u16, the name
identifier u32 and the talent selector of the Pokémon trainer. The level, catch rate, obscure
identifier, abilities, objects, IV/EV, flags and all other bytes provided remain intact.

The default specific values (`any`, `global`,0) keep exactly the draw v0.4. Disable
`randomize_shadows` The reinforcement and the unobscured diversity of the bosses then execute, as
before, without retouching the Shadow Pokémon selected here.

## Validation de cette passe

`python -m unittest tests.test_shadow_boss_rules -v`: **14 successful tests**, three of which use
the local PAL dump. They cover the seven distinct groups and 48 families, legendary, generations,
native thresholds, strict power, declared global folds, complete pairing, explained impossibility,
reproducibility, synchronization of all aliases and whitelist bytes.

These results validate the data produced and the invariants. They are not combats observed under
Dolphin and do not guarantee the balance felt. The validation of integration and ISO belongs to the
main pass v0.5, not to this isolated submodule.
