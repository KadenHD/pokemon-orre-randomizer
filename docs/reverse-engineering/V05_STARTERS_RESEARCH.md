# Couple de starters — PAL GC6P01

Static control and transformations into memory of October 31, 2026. This pass reuses the two
manufacturer's calls already identified for starters. It does not change the conditions for
obtaining, levels, evolution graph, scripts, or size of the DOL. It does not constitute an
observation under Dolphin.

## Identity and fields

- `game/sys/main.dol` : SHA-256 `a788176a45eb88dbd227246a7205ab9856bc79f3cca7e4a0f5376cf466664df5`.
- `game/files/common.fsys`, membre `common_rel` : SHA-256
  `ee2677af555dc59626f978e743235831a76cb23bae93f3fdd1060d808f749d0b`.
- Call Umbreon to the DOL file offset `0x131E1C`. Call Espeon to `0x131CF4`. Species: immediate `li
  r4` to `+2`. Level: entire instruction `li r5` to `+4`, retained. EXP: immediate `li r7` to
  `+0x92`.
- Internal initials 197 and 196, levels 26 and 25, EXPnatives 1955 and 16372. Instruction signatures
  are checked before writing. The wrapper validates the exact original hashes. The explicit table
  core allows synthetic tests.
- Species properties come from the same parser `species_catalog` as global rules. Families and roots
  are calculated from the five native evolution arcs per species (`+0x9C`, not 6 bytes), without
  confusing internal indexes with national numbers. The PAL inventory contains **202 racines**.

## Rules

The four controls are independent and do not trigger randomization of a starter whose species box is
disabled.

- `starter_balance_pair`: difference between the two basic statistics totals at most equal to
  `max(50, plus_petit_total // 5)`. The TSBs are those of the final ADR, including if a new total
  was drawn by the statistic rule.
- `starter_distinct_families`: families of different evolution. All the native branches of the same
  family count together.
- `starter_complementary_types`: no type shared, according to the types of the final ADR. The name
  describes the variety of coverage, not a guarantee of victory, complementary resistance or
  strategic synergy.
- `starter_base_forms`: only replacements without incoming evolution arcs are eligible. Babies
  count: Pichu is a root, Pikachu is not. Non-evolutionary species are also roots, including the
  legendary authorized ones. This rule does not force a retained partner to regress.

Generation and legendary filters remain strict. Shedinja is excluded from new hashes. The original
species of the replaced starter is excluded.

If `balance_species` is active, the previous exclusions are applied first, and then the engine
retains the candidates whose TSB **final** is at `max(50, BST_original // 5)` of the TSB
**original** of the meeting. Like the existing global filter, the absence of a candidate in this
window retains only the closest eligible TSBs. It does not reintroduce any generation, legendary
species or advanced form excluded. The equilibrium constraint **between the two starters** remains
then strict, without any withdrawal.

The engine lists the permissible ordered pairs and pulls evenly among them by SHA-256 with
rejection, domain `starter-pair-sha256-v1`, exact Seed UTF-8. It does not attempt a limited number
of pairs and does not silently release a constraint. An empty set produces an error indicating the
filters to reconsider. If only one starter is randomized, the other common species forces the choice
but its bytes remain intact.

For each replaced starter, the EXP is recalculated at the threshold of the level retained according
to the growth group of the species chosen. The immediate must remain representative by `li` signed.
No byte outside of the two species and two authorized EXPs are written. Previous changes to the DOL
are retained.

## Composition

`apply_starter_rules(original_dol, current_dol, original_rel, rel, seed, options)` returns the DOL
and a ratio `applied`, `rules`, `pair`, `valid_pair_count` and the differences/tlerances TSB. The
engine is called at the beginning of the advanced DOL treatment, after the final properties of the
species of the REL. When it applies, the historical individual filtered draw of the two starters
must be skipped. The starting capacities are then calculated from the final species, with the
already existing attack rules. Gifts remain independent.

Without an active constraint, the current DOL is rendered unchanged and the historical selection
continues. If both starters are kept, no draw, torque constraint and no EXP rewriting is applied.

## Controls

`python -m unittest tests.test_starter_rules -v` : **10 successful tests**, including optional
control over local PAL files. Tests check seed, write mask, EXP and levels, fixed partner, basic
shapes and babies, generation/legendary filters/Shedinja, final types and statistics, composition
with the individual BST window, errors without solution, data forms and invalid signatures.

Direct helper test with the test history, recommended rules and original properties: **21 259
couples admissibles**. Seadra (internal and national 117), level 26, TSB 440, EXP 17576. Electabuzz
(125), level 25, TSB 490, EXP 15625. Difference 50, tolerance 88, types Water and Electric. This
test does not prejudge any other engine version or different rules.

A second helper test with randomized types and statistics, without keeping totals, reads well the
final properties: internal torque 361/350 (nationals 355/298), TSB 503/456, insect/plant types,
deviation 47 for a tolerance of 91. The names/parameters of a complete part remain those of the
final report produced by the service, not of an intermediate draw.

These controls establish the bytes and selection rules. Actual power also depends on abilities,
talents and encounters. A comparable TSB does not certify the balancing of a part. No fight,
acquisition of starter or full course is claimed by this isolated pass.
