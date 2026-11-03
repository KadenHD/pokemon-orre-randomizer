# Version 0.16: Retrieve settings and reread its configuration

The engine remains `details-and-progression-v15`. The **82 parameters, including 57 booleans in 15
categories**, their values and the drawing fields do not change. The version of the application goes
up to 0.16.0. The profile diagram remains 1.

## Search settings

In Advanced mode, **Search settings…** refers to words, aids, categories and choices translated into
the current language. The accents are ignored. Usual synonyms, such as shiny/Shiny terms, facilitate
search.

The results are temporary: a click or Enter opens the category of the setting, scrolls it into the
visible area and gives it the focus. The normal form then resumes its place. This action does not
change any value and does not invalidate an overview whose configuration remains the same. The
search does not cover the names of the Pokémon of the preview, which keep their own search fields.

## Restore the recommended values of a category

The **Recommended values** button refers to the current category and uses the values of **Pokémon +
moves**, i.e. `Options.recommended()`. This reference does not include the last imported profile or
the values of the identical Copy mode.

Only fields in this category are re-established. Seed, paths, other categories and language are
retained. Actual changes invalidate the preview. The engine must then recalculate it with these
values. Constraints between categories remain checked normally.

## Summary before creation

The **Applied settings** pane at the Create step distinguishes the rules that will be applied from
the simply memorized values. It describes in particular the manual choices of starters, constraints,
Shiny status, levels and multipliers active. For example, a different d-EXP value of ×1 is
effective, while the three curve factors are only effective when the progressive difficulty is
activated.

The summary does not reveal the species drawn by the seed. The manually selected starters can be
named as they have been explicitly selected. The full overview remains a separate action. The
cancellation message is simplified in "Cancellation...". The opening of the pane scrolls the page
just enough to show the first lines of detail, keeping the creation action visible.

## Profile and engine compatibility

The profiles v0.15 keep their 82 fields and their values, including manual starters, curve, exp and
obscure gauge. Their version, footprint, game identity, value types and exact list of fields remain
under control. A missing or unknown field is not ignored. The re-export carries the current version
of the application and the same engine ID.

The tests use a profile exported by the preserved public archive v0.15, with the eight non-neutral
additions v0.15. The old v0.14 and previous profiles keep their previous migration rules.

The regression compares the recommended configurations and combined with the evidence v0.15 in the
three regions, with the same ROM, seed and the same options. The six sets of d-offset, size and
payload fingerprints correspond. The three combined ISOs v0.15 are then compared in full to the
current patch source and plane: all bytes correspond. No new ISO image is written by this control.

The 39 files of the engine and drives concerned are also identical to the v0.15 archived sources.
The change in version navigation and metadata does not change these results. The evidence is private
in `build/v16-validation/regression-result.json`. The three original images and the 46 files of the
Dolphin Personal Profile remain unchanged during this trial.

## Automated interface validation

The complete suite executes **449 tests**, with two explicitly ignored cases. Search and summary
tests cover keyboard navigation, focus and scrolling towards a result, category-limited reset,
retention of the seed and other values, inactive rules, and absence of revelation of random hashes.

The two executables v0.16 were built in new staging folders, without reconstructing the Rust codec
or modifying previous distributions. Their on-board diagnosis, executed off-screen with private
preferences and temporary paths, runs **168 statements per edition**, i.e. **336 statements**.

| Editing control | States |
| --- | ---: |
| Navigation existante | 48 |
| Dialogues d’exclusion | 24 |
| Shiny Options | 60 |
| Summary overview | 24 |
| Search, Category and Summary v0.16 | 12 |

The twelve new states correspond to the six languages and two window sizes (1040 × 800 and 680 ×
540). The 156 previous states remain comparable to the diagnoses v0.15. Both editions also check
their Rust codec, application icon and respective resources: local pack present, game resources
absent from public publishing.

These diagnostics do not open any ROMs or personal preference and do not launch Dolphin. After the
visual review, three presentation files were adjusted: the results counter, the width of the
category name, the formulation and scrolling of the summary. Targeted tests and the twelve layout
checks in the six languages in both sizes pass with these adjustments. The two final executables
re-align their 336 diagnostic states in total. The first staging, the applications v0.15 and the 50
old ZIPs are retained.

The review under Windows confirms that the entry joins the setting found, that the reset of the
Shiny Pokémon keeps the seed and theEXP at ×2, and that the summary keeps these values in Japanese.
The final version displays the corrected counter, the full name of the category and the first lines
of the shutter as soon as it opens. This presentation control stops before the creation of a new
ROM. Private evidence is in `build/v16-validation/suite/full-source.log`,
`build/v16-frozen-final/staging-validation.json` and `build/v16-runtime/ui-final/`.

## New QOL Trials in Dolphin

The five stages were observed in each of the three regions: **15 steps validated under Dolphin**.
These tests complement the combat observations recorded in Europe for the v0.15. [Bilan
v0.15](DESKTOP_V15.md)

The tests use the combined images of the matrix v0.15, whose binary control above confirms the
concordance with the current engine. The seed is `feature-v15-validation-1`, with **EXP ×2 and gauge
×3**. The ratios of each image and the private aggregate detail the other options and fingerprints.

| Image | Identity | Start of SHA-256 |
| --- | --- | --- |
| USA | `GC6E01` | `8006d9ba6db9ffb0` |
| Japan | `GC6J01` | `90e1570f628c825a` |
| Europe | `GC6P01` | `e03d4da870d5d5a3` |

| Observation native | USA | Japan | Europe |
| --- | --- | --- | --- |
| March with gauge 1 → 0, zero floor and counter 256 → 0 | Observed | Observed | Observed |
| Relic release with reserve 499 → 0, EXP 57,820 → 58,319 and level 35 retained | Observed | Observed | Observed |
| Final purification with national ribbon, native flag 0 → 1 and total 25 → 26 | Observed | Observed | Observed |
| Normal EXP ×2 in combat and level 35 → 36 | Gain 673 → 1,346, total 58,319 → 59,665 | Gain 448 → 896, total 58,319 → 59,215 | Gain 448 → 896, total 58,319 → 59,215 |
| EXP ×2 actually added to the dark partner's reserve | 12,313 → 13,659 (+1,346) | 12,313 → 13,209 (+896) | 12,313 → 13,209 (+896) |

The Relic transfers **499 points once only**, to the exact value of the reserve. The walk observes
the native delta -0.5, multiplied in -1.5. The game then applies the floor to zero and resets the
counter. Native combat gains are recorded in each region before applying the factor.

The three sessions normally closed with a return code of 0. The aggregate
`build/v16-runtime/result.json` associates each step with its capture and footprint. After the three
closures, `build/v16-runtime/final-preservation.json` confirms by SHA-256 the integrity of **18
protected files**, including **six original ISO and RVZ ROMs**, as well as that of **46 Personal
Dolphin Profile Files**, including backups.

### Preparation and scope of comments

The tests shall be repeated on **new maps prepared offline**The first Pokémon is Lanturn level 35,
with EXP 57,820, Reserve 499, Gauge 1 and Power Meter 255. The initial total purifications is 25.
Blastoise Level 33 begins with a reserve of 12,313 and a gauge of 800. The restored VP comes from
the native healing observed in the previous Europe trial.

The PID, IV, EV, capabilities and stored statistics are inherited from previous fixtures. The
Japanese survey `fixture-stat-comparison.json` combines the initial statistics of Lanturn and
Blastoise with the original tables. The route validates the targeted mechanisms with a pre-existing
team. The acquisition of this team, the initial 25 purifications, balancing and a full part of the
scenario remain outside its scope.

The dialogues, choices, movements and KO are made by the controls of the game. The captures
highlight the arguments, records and changes produced by the native functions. In each region, the
bridge intervenes once to reach the fighting room from a real door transition. After checking the
initial state, it adjusts only the destination and its argument `r3`. The audit keeps the
destinations and every request of the bridge. The reading of the floating registers is limited to
PS0 in the RSP protocol used.

The other multipliers are subject to automated checks. The witness of refusal at the native
threshold of darkEXP appears in the balance sheet v0.15. Evidence, maps, captures and audits are
kept in the private file `build/v16-runtime/`.

## Distribution Windows

The local edition uses the presentation package extracted in this project. The public edition
includes the source code and the Windows application without this package. The archives do not
contain any ROM, backup or copy of Dolphin. Both editions use validated executables and the same
Rust codec.
