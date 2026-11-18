# Windows review builds

A local review build contains the application EXE, the native game-folder
launcher, a portable Windows ZIP, and the corresponding source ZIP. Building
these files does not publish a release or install the application for a user.

Use the exact dependencies in `requirements-build.txt`. A private environment
keeps the build independent of packages used by concurrent development tools:

```powershell
python -m venv --system-site-packages build/windows-build-env
build/windows-build-env/Scripts/python.exe -m pip install -r requirements-build.txt
build/windows-build-env/Scripts/python.exe scripts/build_desktop.py --output-dir build/windows-review
build/windows-build-env/Scripts/python.exe scripts/smoke_desktop.py --release-dir build/windows-review --report build/windows-smoke.json
```

Choose new output and evidence directories. Preserve existing artifacts and
their JSON receipts. The package does not include ROMs, memory cards, personal
settings, Dolphin binaries, downloaded HD packs, or private validation data.
The interface assets remain restricted to their explicit provenance manifest.

Freeze changes to application code, public interface assets, and the music
renderer before compilation. The build checks PE x64 headers and verifies the
music DLL against its current adapter and patch identities. It records runtime
input hashes and refuses sources that change while PyInstaller is running.
`--skip-freeze` can only repackage an executable with the same recorded inputs.

The archive verifier checks that the binary ZIP contains its corresponding
source ZIP and that its recorded inputs match the packaged native files and
source files. It reads the embedded Python module archive without executing it
to check the game-folder, music, HD, Spinda, and image decoder modules. It also
rejects local build-account paths in release text, native files, and application
bytecode. Source tests run through the test runner extracted from that source
ZIP, rather than through the developer checkout's copy.

The executable smoke test runs the relocated application offscreen with private
AppData and Temp directories, a reduced PATH, and interface music and sounds
disabled. It checks the actual frozen Qt application, native codec, synthetic
disc conversion, bundled resources, and renderer ABI. It does not start Dolphin
or verify physical audio output.

For a portable v1 to v2 update rehearsal, extract the previous Windows ZIP into
a disposable directory and keep the new ZIP separate. Use a private update job
and the same Windows helper as the application. Compare all declared new files
after the update and verify that unmanaged sentinel files remain unchanged.
Never use an installed user directory, a personal game folder, or real memory
cards as update fixtures. An update rehearsal does not establish that a public
release endpoint already serves v2, and it does not validate an installer
upgrade on another Windows PC.

The standalone launcher can be checked separately against a harmless private
runtime fixture. Verify argument order, paths with spaces and accents, and its
working directory without starting an emulator. The same launcher EXE must be
present in the final portable package.
