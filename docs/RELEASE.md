# Building and verifying a release

The local edition in `dist/` and public edition in `dist/public/` include the
same verified interface pack. Logos, menu sounds and music work before a ROM is
selected. Game-media provenance and licenses remain separate from the MIT code.

Both editions include the Eclipse icon and approved Orre logo from `assets/app/`. The sources include
the PNG master and the Qt generator. The executable uses the ICO and its provenance
manifest. The logo's transparent PNG and generation provenance are included in both
source and Windows archives. The archive audit checks the recorded hashes of the
application assets and interface pack. Run `python scripts/build_app_icon.py` to regenerate all nine sizes.

## Build

Use Python 3.12 or later with Rust and MSVC.

```powershell
python -m pip install -r requirements-build.txt
python scripts/fetch_qt_notices.py
python scripts/build_desktop.py --edition public
python scripts/verify_release.py --edition public
python scripts/smoke_desktop.py --edition public --report build/public-smoke.json
```

Omit `--edition public` to place the local edition directly under `dist/`.
Use `--source-only` for a source ZIP. Move existing ZIPs aside before rebuilding
the same version.

The audit checks hashes, ZIP CRCs, and archive paths. It rejects ROMs, save files,
and emulator binaries. It also rejects media outside the declared interface pack. The Windows ZIP
includes the application sources, notices, and corresponding Qt sources.

## Executable diagnostics

Diagnostics run the real Qt widgets with a temporary preferences file. They compare
the Rust codec with the Python reference and check that the edition has the expected
resources. The interface checks cover six languages at 1040 × 800 and 680 × 540,
including the home screen, wizard, preview, and exclusion dialogs.

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
& .\OrreRandomizer.exe --diagnostics .\diagnostics.json --screenshots
```

Choose a new report path in a writable directory. A successful diagnostic exits
with code zero. `smoke_desktop.py` extracts the ZIP into a new path with spaces and
accents, removes Python and developer tools from `PATH`, changes the working directory,
and isolates AppData and Temp. It writes the report and screenshots under `build/`.

Run **Package Windows release** manually on GitHub Actions for test artifacts from
a hosted Windows runner. The public runner uses the committed interface pack and no ROM.

## Publish a release

Check that `pyproject.toml` and `orre_randomizer/__init__.py` declare the same
version. Push a Git tag named `v<version>` on the release commit. The workflow checks
the version, tests the public build, and publishes the Windows setup EXE, the
portable Windows ZIP, the source ZIP, and `SHA256SUMS.json` for the ZIPs.

```powershell
git tag -a v0.20.0 -m "Pokémon Orre Randomizer 0.20.0"
git push origin v0.20.0
```

For a release candidate, use a matching version and tag such as `0.21.0rc1`
and `v0.21.0rc1`. The workflow publishes it as a prerelease.

The Windows installer uses the verified public ZIP as its payload. It installs
for the current user, including the application, replaceable Qt DLLs, and notices.
The build script downloads a hash-pinned portable Inno Setup compiler into
`build/`. Its smoke test checks installed files, launches the app diagnostics,
and uninstalls the test copy.

```powershell
pwsh -File scripts/build_installer.ps1 -SmokeTest
```

For a release that already has a public Windows ZIP, run **Add Windows installer
to an existing release** and enter its tag. GitHub builds and tests the installer
from the published ZIP before attaching the new asset.

## Local engine and audio validation

```powershell
python -m unittest discover -s tests -v
python scripts/validate_seed_matrix.py original.iso build/seed-matrix.json
python scripts/validate_audio_pack.py build/audio-levels.json
```

The seed matrix requires a verified original PAL ISO. It builds the patches twice
for twelve configurations, then reads the final REL and DOL. Checks cover species,
filters, all 48 Shadow Pokémon groups, aliases, regular moves, special markers,
evolution families, starter experience, and stone names. The matrix also checks
that the source image is preserved. Configurations cover an unchanged copy, all
three generations, boss rules, and advanced settings.

The preview uses `build_patches` to read the final starter values. ROM-free tests
cover temporary conversion, cancellation, language changes, late results, and error
handling. Local validation compares the species and levels with the final DOL across
the three presets, a fixed starter, randomized types and stats, and base forms.
It also compares ISO and RVZ inputs. Both editions decode preview portraits from
the supplied ROM.

The audio check measures PCM16 length, duration, peaks, clipping, and loop
transitions. Evidence from a local playback test spanning more than one full
loop is kept in the private QA folder.

## In-game validation

The [Dolphin validation report](DOLPHIN_VALIDATION_2026-10-31.md) records the
scenarios that were played. A full playthrough and balance across several seeds
require separate testing. A visual check of each in-game menu complements the
verification of item names in the five text banks.

Before marking a release stable, record a test on a second Windows installation
and a regular playthrough through the ending. List the tested features and any
remaining gaps in the release notes.
