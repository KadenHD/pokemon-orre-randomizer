# Interface writing conventions

Write for players choosing a ROM, settings and a destination. A label names the
action or option; its help explains the effect and any useful limit. Use the same
words for the same behavior in both games and in all six interface languages.
See [shared interface behavior](INTERFACE_PARITY.md) for implementation sources
and the intentional differences between Colosseum and XD.

## Presets

| French | English | Effect |
| --- | --- | --- |
| Pokémon + capacités | Pokémon + moves | Replaces Pokémon with similar strength; also randomizes moves, learnsets, TMs, chest items and shop items |
| Pokémon seuls | Pokémon only | Uses the same Pokémon selection and balance; keeps moves, learnsets, TMs and ordinary items |
| Copie à l’identique | Unchanged copy | Keeps all game data; can convert ISO/RVZ |

Both randomizing presets enable accessible evolutions, Evolution stones in shops,
family diversity, base starters from three-stage families and a seeded 5% shiny
chance for supported encounters. Explain native exceptions beside these shared
defaults. Do not imply that wild Poké Spots use the custom shiny rate.

**Custom settings** means that the current options differ from every preset.
Explain how to inspect them in Advanced and that selecting a preset replaces
them. Switching Simple/Advanced alone preserves the current options.

## Vocabulary

| French | English | Meaning |
| --- | --- | --- |
| ROM d’origine | Original ROM | Player-supplied image, preserved by the app |
| Nouvelle ROM | New ROM | Separate generated image |
| Réglages | Settings | Options used for generation |
| Profil | Profile | Portable seed and settings |
| Capacités | Moves | Pokémon moves, including non-damaging moves |
| Talents | Abilities | Species abilities; separate from moves |
| Pokémon obscurs | Shadow Pokémon | The game's Shadow encounters |
| Cadeaux | Gifts | Pokémon received as gifts, trades or rewards |
| Famille d’évolution | Evolution family | Species linked by evolution |
| Chromatique | Shiny | Use a small red star beside a shiny Pokémon's name |
| Réglages appliqués | Applied settings | Effective values, grouped by category, before creation |

Keep the labels for common settings in shared metadata. Avoid alternating
“change”, “replace” and “randomize” for the same control in different workspaces.
French uses *chromatique* consistently; other languages use their own catalog.
The first/second starter labels describe a slot, so they remain valid when the
original species is replaced.

## Preview states

- **Calculate preview** starts the first calculation.
- **Update preview** appears after the ROM, seed or settings change.
- **Cancel preview** remains available while calculating.
- **Try again** follows cancellation or failure.
- **Preview up to date** confirms a completed, current result.

Before calculation, show known original species in the original column and `?`
for unknown replacements. A retained or manually selected species may already be
named. Cosmetic cycling during loading never represents a final draw. Explain
that a preview creates no ROM and applies to a new game.

Use sentence case for Pokémon names, keeping the first letter capitalized. Mark
known shiny encounters with the shared small red star instead of adding “shiny”
or “not shiny” to every row. Retain accessible names and status descriptions.
Changing interface language translates an existing result without recalculating.

## Help, errors and localization

- Name actions directly: **Create ROM**, **Open report**, **Cancel preview**.
- Describe checkbox effects: **Replace the first starter**, **Keep shop healing items**.
- Explain relevant limits such as evolution levels, stone prices and stat thresholds.
- Report what blocked the action and how to recover. Internal offsets, patch
  routines and implementation details belong in diagnostics, not ordinary help.
- Keep seeds, file paths, Pokémon IDs, profile values and format parameters
  literal. Rewording interface text must not change a seeded result.
- Translate complete messages with structured parameters. Keep interface language
  independent of ROM language; in-game names and dialogues follow the ROM.
- Check all six languages at both supported window sizes. Japanese uses installed
  system fonts; no proprietary font is bundled.

Preview properties and portraits come from the verified original and the final
patch plan. Fallback names are licensed under the notices in `licenses/`. The
preview requires no external service.
