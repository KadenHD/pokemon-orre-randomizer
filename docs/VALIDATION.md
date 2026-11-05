# Validation scope

This is the current validation index for v1.0.0. Dated reports in `docs/` describe
their named versions and scenarios; they are historical evidence rather than
the current feature specification.

## Automated and packaged checks

- Python tests cover guarded edits, disc identity, both games' options, allocation,
  previews, profiles, translations, reports and GUI state.
- Preset tests compare all shared fields across games and balance fields across
  modes. Exports from the actual published RC2 source archive verify that imports
  keep old values. RC1 version/engine compatibility is checked too.
- GitHub Actions runs Windows and Linux tests. Tests requiring local ROMs declare
  and skip those prerequisites on public runners.
- Rust/Python codec output is compared. Archive audits check CRCs, hashes, paths,
  notices and the allowlisted interface pack.
- Windows diagnostics cover 204 UI states, six languages and two sizes, including
  both games and home. Isolated smoke tests remove developer tools from PATH and
  use fresh application data. The installer is installed, checked and uninstalled.
- Published asset sizes and SHA-256 digests are verified after release.

Counts evolve; the Actions run for a release tag records that build's results.

## Native Dolphin checks

Colosseum reports cover selected battles, starters, shinies and regional gifts:

- [Disc round trip](reverse-engineering/ROUNDTRIP.md)
- [Dolphin validation](DOLPHIN_VALIDATION_2026-10-31.md)
- [Shiny validation](DOLPHIN_SHINIES_VALIDATION_2026-11-01.md)
- [Seeded preview](SEEDED_SHINIES_VALIDATION_2026-11-02.md)
- [Regional gifts](REGIONAL_GIFTS_DOLPHIN_2026-11-03.md)

XD's [research report](reverse-engineering/XD.md) records regional structures,
story protections and native follow-ups. The corrected v6 runtime hook was
checked with matched European QA saves and separate original/modified images:

| Measurement | Original | Modified |
| --- | --- | --- |
| Vivid Scent, Rhyhorn's Heart Gauge starting at 6000 | 5700 (−300) | 5100 (−900), purification ×3 |
| First measured EXP award in the same trainer battle | 165 | 248, EXP ×1.5 |
| Last measured EXP award | 91 | 137, EXP ×1.5 |
| Total EXP gained by each participant | 522 | 785, rounding per award |

Both battles and the purification flow returned normally. Original ROMs,
personal saves and personal Dolphin settings were preserved. The v1 preset
alignment changes which existing options are selected; it does not change these
native hooks.

## Limits

Selected scenes and synthetic fixtures do not prove a complete playthrough or
balance across all seeds. No full campaign or second physical Windows PC is
claimed for v1.0.0. These are additional coverage opportunities, not completed
checks. Distinguish observed game failures from limitations of prepared QA scenes.
