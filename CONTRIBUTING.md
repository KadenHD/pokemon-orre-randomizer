# Contributing

The project's original contributor is [KadenHD](https://github.com/KadenHD).

Use Python 3.12 or later. The application code is MIT licensed. Write repository
documentation, issues, and pull requests in English.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[build]"
python -m unittest discover -s tests -v
python -m orre_randomizer
```

The `orre_randomizer` package hosts both games. `service.py` orchestrates ISO and
RVZ operations for the CLI and GUI. `engine/` contains disc-format utilities and
Colosseum patch rules. The `xd*.py` modules contain XD patch rules, options and
its workspace. Game-specific names identify the game whose data they change.

`ui_workspace.py` and `ui_pokemon_details.py` supply the shared wizard layouts
and Pokémon sheets. Each workspace supplies its own options, preview data and
theme. `resources.py`, `preferences.py` and the `native/` Rust codec belong to
the application as a whole. New shared modules use the Orre namespace.

The older scripts delegate to the same engine. The CLI and GUI both call
`service.randomize` directly with the disc image, seed, and settings.

Format and safety tests run without a ROM. Integration tests that need a dump or
a regional image declare the prerequisite and skip when it is unavailable.
Keep ROMs, raw extracted game data, save files and emulators out of the repository.
The published interface pack is an explicit, hash-verified media allowlist; it is
not permission to add arbitrary game dumps. Documentation screenshots must use
clean demo state without personal paths or saves. Media rights are separate from MIT. Include the app version, settings, and relevant hashes in bug
reports. Review reports for local paths and personal information before sharing.

For a new region or revision, document its hashes and independently verify its
data structures before adding support. Keep full hash validation in place.

Seeds are exact UTF-8 strings. Case and whitespace matter. When a change alters
the results of a seed, bump the engine version and keep evidence of reproducibility.
Preserve evolution family graphs and synchronize every alias of a Shadow Pokémon.

## Interface translations

Follow the [interface writing conventions](docs/INTERFACE_COPY.md) for labels,
help text, and messages.

`i18n.py` resolves the system language and renders messages independently of Qt
and engine state. The interface supports French, English, German, Spanish, Italian,
and Japanese. French phrases are lookup keys for labels and `Options` metadata.
The five files `locales/en.py`, `de.py`, `es.py`, `it.py`, and `ja.py` provide the
other catalogs. Colosseum settings in `options.py` and XD settings in `XDOptions` use stable
identifiers. Shared labels keep the same meaning across both games.
`presets.py` centralizes the common desktop preset scope; preserve low-level
CLI defaults and imported profiles when changing desktop defaults.

`feature_i18n.py` contains additional messages and options. `detail_texts.py`
provides the Pokémon details and journal strings in all six languages.
`settings_i18n.py` and `settings_presentation.py` handle settings search and review
independently of the randomization engine. The fallback names in
`locales/selection_names.py` and `locales/detail_names.py` are documented in
`licenses/pokeapi-*.json` and `licenses/pokeapi.txt`. Game properties come from the
final ROM.

Keep paths, seeds, and setting values literal. Use `Message(template, **parameters)`
for dynamic strings. If a parameter is itself a translatable label, pass a nested
`Message`. Match parameter names and formats across translations.

Keep navigation, search, and review changes separate from `Options`, randomization
results, and `ENGINE_VERSION`. A new app version must still import profiles from
the previous version. Validate the version, fields, and hash before restoring the
values. Test resetting one category and displaying the effective rules in all six
languages with the same settings.

To add a language, create its catalog, register it in `CATALOGS` and `LANGUAGES`,
and set its Qt locale in the UI. Tests cover label and help text, format parameters,
detection, persistence, and switching during generation. The source and executable
include the translations for offline use. Native file dialogs use system controls,
with titles and filters supplied in the app's selected language.

## Building the archives

The accelerated Windows build requires Rust and a compatible MSVC linker.
The `native/` crate has no external dependencies and can be built and tested
offline. Running the Python version with the fallback codec requires no Rust toolchain.

```powershell
python -m pip install -r requirements-build.txt
python scripts/build_native.py
python scripts/fetch_qt_notices.py
python scripts/build_desktop.py
```

The Windows build puts an executable with replaceable DLLs, a Windows ZIP, a source
ZIP, and their SHA-256 hashes in `dist/`. An allowlist keeps `game`, `build`, and
`Dolphin-x64` out of the source archive. Use `--source-only` on other platforms.
Add `--edition public` to build in `dist/public/`. Both editions bundle only the
interface assets listed and verified in the pack manifest. Move existing ZIPs
aside before rebuilding the same version.

Before publishing, audit the archives and test the extracted app on Windows
without Python. Include the exact sources and notices for the Qt libraries in
the distribution. [Release validation guide](docs/RELEASE.md) · [Third-party notices](THIRD_PARTY_NOTICES.md)
