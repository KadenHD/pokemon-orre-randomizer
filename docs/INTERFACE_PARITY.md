# Shared interface vocabulary and behavior

Colosseum and XD use the same **ROM → Settings → Create** workflow and the
same shared wording in French, English, German, Spanish, Italian and Japanese.
Game themes change colors and artwork, not the meaning of shared controls.

## Sources of truth

- `workspace_copy.py`: shared step help, preset explanations and category help.
- `workspace_i18n.py`: canonical translations of new shared messages. These take
  precedence over historical catalogs so a game-specific synonym cannot replace
  a shared label.
- `options.py`: metadata for shared settings. `XDOptions` reuses this metadata
  through `_shared`, including controls with different stored identifiers.
- `ui_workspace.py`: shared layouts, navigation, search fields, encounter tables
  and starter slots. `ui_pokemon_details.py` provides both games' Pokémon sheets.
- `settings_presentation.py`: localized search and effective-settings summaries,
  including values, units and dependent controls. Dormant saved values are omitted.

Use the same action for the same state: **Calculate preview** initially,
**Update preview** after a change, **Cancel preview** during calculation,
**Try again** after failure/cancellation, and **Preview up to date** after success.
Presets are **Pokémon + moves**, **Pokémon only** and **Unchanged copy**.
The creation summary is **Applied settings** in both games.

## Shared behavior

Before calculation, encounter lists show the native species in the original
column and a question mark for an unknown replacement. A manually selected or
unchanged species can already be named. Search works before and after calculation
using names in all six languages and National Pokédex numbers.

Both previews use the same Qt worker lifecycle. Cosmetic cycling during loading
does not draw Pokémon or alter the seed. The final result comes from the production
patch plan. ROM, seed or rule changes invalidate that result and any open sheet.
Creation may reuse a matching plan only after validating the original again.

Both games provide starter sheets, single-click encounter sheets, evolution
portraits, shiny markers, visible-range counts and duplicate-family warnings.
Report import restores settings without replacing input/output paths and compares
the selected original to the report. Creation exposes progress, cancellation, a
stage log, and links to the resulting folder, JSON report and offline journal.

## Intentional native differences

| Surface | Colosseum | XD |
| --- | --- | --- |
| Encounter tabs | 2 starters, 48 Shadows, 4 gifts | 1 starter, 83 Shadows, 7 gifts, 9 Poké Spot slots |
| Starter controls | Separate first/second starter and pair rules | One starter |
| Special encounters | Event gifts and purification rewards | Tutorial Teddiursa, Hordel and Duking trades, Poké Spots |
| Evolutions and shops | Individual evolution/stone-shop controls | Native XD evolution rules and shop locations |
| Shiny scope | Optional in-game or seeded draws | Seeded supported encounters; optional Shadow unlock; wild Poké Spots keep native odds |
| Protected species | Depends on selected encounter controls | Shadow Lugia retains its species |

Different mechanics need accurate help. Keep those exceptions explicit rather
than using a shared sentence that would describe the wrong game.

`tests/test_ui_parity.py` checks shared metadata and text across all six languages,
initial rosters, search, cancellation, stale results, sheets, reports and patch-plan
reuse. Update these checks when a shared feature changes.
