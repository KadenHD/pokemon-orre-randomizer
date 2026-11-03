# Exclusions and teams of trainers — 0.9

New settings are in **Advanced** and remain disabled by default.

| Adjustment | Effect |
| --- | --- |
| Pokémon allowed → Pokémon excluded | Remove the checked species from all replacement hashes. Search by name or national number. |
| Pokémon allowed → Types of origin excluded | Removes species with one of the types checked in the original game, even in double type. |
| Trainers → Non-Shadow team types | Without theme, a common type at random, or a common type of origin if possible. |
| Trainers → Non-Shadow opponents at the final stage | From the chosen level, use a species that no longer evolves. |

The exclusions concern trainers, Shadow Pokémon, starters and replaced gifts. They do not remove
explicitly preserved Pokémon and do not automatically prohibit other family members. List names
follow the language of the interface. The numbers remain the same. Check to exclude. Group actions
only concern the visible results of the search. **Cancel** keeps the previous selection.

The themes only apply to the non-Shadow Pokémon whose replacement is activated. The original mode
looks for a type shared by the original non-Shadow members. If this type does not exist or does not
allow to respect the constraints, another eligible theme is chosen. The theme uses the final types,
after their possible randomization. Exclusions remain based on the original types. An obscure is
never changed to adapt to the theme.

The final stage uses the level after the general multiplier and the bonus of the bosses. The
threshold is independent of the usual levels of evolution. Without random replacement of the
species, only the final downward evolutions of the Pokémon are allowed. The Pokémon already at the
final stage are retained. With the random replacement, the candidates above the threshold are the
final authorised forms, including the species without evolution.

Shared team recordings are treated together and are not duplicated. The diversity of boss families
is taken into account in the allocation. Power balancing is a preference. Exclusions, the theme and
the stage requested remain mandatory. An impossible set causes an error recoverable before
publication of the ROM.

Capabilities are recalculated when additional species changes only if their randomization is
enabled. Special markers, levels, IV, EV, objects, team pointers and obscure identifiers are
retained by this step. Separate options that change levels, IV, EV or objects run before it.

The 0.5 to 0.8 profiles are checked with their original footprint and then migrated with these new
empty or deactivated settings. The current engine is `trainer-policies-and-exclusions-v10`, and the
0.8 preset hashes are retained. The current profiles require the 66 fields and validate the
identifier lists. The creation report contains `summary.trainer_policies` with themes, shared
groups, final species, levels and capabilities.

The LTB exposes `--trainer-theme-mode none|random|preserve`, `--trainer-force-evolved` /
`--no-trainer-force-evolved`, `--trainer-evolution-level 40`, `--excluded-species 25,133` and
`--excluded-types 10,17`. The species use national numbers. The types use the native Colossium
identifiers.

| ID | Type | ID | Type |
| --- | --- | --- | --- |
| 0 | Normal | 10 | Feu |
| 1 | Combat | 11 | Eau |
| 2 | Vol | 12 | Plante |
| 3 | Poison | 13 | Electric |
| 4 | Sol | 14 | Psy |
| 5 | Roche | 15 | Glace |
| 6 | Insecte | 16 | Dragon |
| 7 | Spectre | 17 | Darkness |
| 8 | Acier | 9 | Invalid, refused |

Local validation: tests of binary masks and stress on fixtures, composition on PAL data, matrix of
reproducible seeds, comparison of data produced with archived sources 0.8 and Qt controls in six
languages. These technical controls do not certify a complete part or its balancing.
