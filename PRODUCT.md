# Pokémon Orre Randomizer

<!-- impeccable:product-schema 1 -->

## Platform and users

A native Python/Qt desktop app, Windows first, for players with an unmodified
Colosseum or XD image. It creates a separate randomized image locally without
requiring extraction or command-line tools. Rust accelerates the shared codec;
the Python fallback remains available. The app does not manage emulator saves.

## Primary workflow

Choose a game, then **ROM → Settings → Create**. Both workspaces share layout,
navigation, profiles, language/audio controls, preview tables and Pokémon sheets.
Game-specific themes use their own logos and media; home uses neutral colors.
One main action per step, visible progress and recoverable errors take priority.

## Defaults and advanced controls

The two randomizing modes share balance, family diversity, base starters from
three-stage families and a seeded 5% shiny chance for supported encounters.
Pokémon-only preserves moves, TMs and items while retaining evolution access.
Native game mechanics determine the exceptions, especially XD Shadow shinies,
Lugia, Poké Spots and optional tutorial/Hordel replacements. Imports preserve
saved values. Detailed behavior belongs in the [user guide](docs/USER_GUIDE.md).

Advanced settings use stable field identifiers and metadata, searchable in all
six interface languages. Switching views does not reset settings. Preview and
creation use the same patch plan off the interface thread. Creation verifies
the result and writes a portable-settings report and offline journal.

## Product constraints

Validate the entire original image and preserve source files and saves. Never
overwrite existing outputs. Explain impossible filters and best-effort family
fallbacks. Keep interface language independent of ROM text. Distinguish tested
scenarios from full-playthrough claims; see [validation](docs/VALIDATION.md).

The [README](README.md) presents the public product; [DESIGN.md](DESIGN.md)
records interface conventions. Application code, original branding and the
verified game-media pack have separate provenance and licensing scopes.
