"""Build an offline Windows app and an allowlisted source archive. No ROMs."""
from __future__ import annotations
import argparse
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from orre_randomizer import APP_EXECUTABLE, REPOSITORY_NAME, __version__
from scripts.release_media import (BINGO_AUTHORING_ROOT, bingo_authoring_media,
                                  documentation_media, game_asset_name_allowed)


NATIVE_RUNTIME_NAMES = ("orre_lzss.dll", "orre_disc.dll", "orre_musyx.dll", "OrreLauncher.exe")
RUNTIME_BUILD_RECORD = "_internal/orre_randomizer/_native/build-inputs.json"
REQUIRED_RUNTIME_MODULES = frozenset((
    "orre_randomizer.play_folders", "orre_randomizer.ui_play", "orre_randomizer.play_music",
    "orre_randomizer.native_music_state", "orre_randomizer.native_music_render",
    "orre_randomizer.native_music_output", "orre_randomizer.native_music_volume",
    "orre_randomizer.hd_images", "orre_randomizer.hd_overlays", "orre_randomizer.hd_spinda_diagram",
    "orre_randomizer.hd_hud",
    "orre_randomizer.hd_menu_atlases", "orre_randomizer.hd_menu_catalog",
    "orre_randomizer.hd_text", "orre_randomizer.hd_text_capture", "orre_randomizer.hd_text_runtime",
    "orre_randomizer.hd_text_assets", "orre_randomizer.hd_text_vectors", "orre_randomizer.hd_text_symbols",
    "orre_randomizer.hd_text_layout",
    "orre_randomizer.hd_spinda_face", "orre_randomizer.engine.dna_spinda_face_hd",
    "orre_randomizer.hd_extra_portraits", "orre_randomizer.hd_extra_portrait_catalog",
    "orre_randomizer.hd_form_materials",
    "orre_randomizer.engine.dna_hd_tiles", "orre_randomizer.engine.dna_spinda_hd",
    "orre_randomizer.engine.spinda_diagram",
))
REQUIRED_IMAGE_DECODERS = frozenset(("PIL.DdsImagePlugin", "PIL.PngImagePlugin"))


def validate_build_dependencies():
    for line in (ROOT / "requirements-build.txt").read_text(encoding="utf-8").splitlines():
        if "==" in line and not line.lstrip().startswith("#"):
            name, expected = line.strip().split("==", 1)
            if version(name) != expected:
                raise RuntimeError("Build dependency differs from requirements-build.txt: " + name)


def validate_pe_x64(path: Path):
    """Inspect the PE header without loading or executing a native dependency."""
    data = path.read_bytes()
    if len(data) < 64 or data[:2] != b"MZ":
        raise RuntimeError("Invalid native Windows runtime: " + path.name)
    offset = struct.unpack_from("<I", data, 0x3c)[0]
    if offset > len(data) - 6 or data[offset:offset + 4] != b"PE\0\0" or struct.unpack_from("<H", data, offset + 4)[0] != 0x8664:
        raise RuntimeError("The Windows runtime must be x64: " + path.name)


def validate_native_runtime():
    from scripts.build_music import PIN
    native = ROOT / "orre_randomizer/_native"
    for name in NATIVE_RUNTIME_NAMES:
        validate_pe_x64(native / name)
    record = json.loads((native / "orre_musyx.json").read_text(encoding="utf-8"))
    required = {"abi": 1, "source_commit": PIN,
        "renderer_sha256": hashlib.sha256((native / "orre_musyx.dll").read_bytes()).hexdigest(),
        "patches_sha256": hashlib.sha256((ROOT / "native/music/patches.json").read_bytes()).hexdigest(),
        "adapter_sha256": hashlib.sha256((ROOT / "native/music/renderer_adapter.c").read_bytes()).hexdigest()}
    if any(record.get(key) != value for key, value in required.items()):
        raise RuntimeError("The music renderer is stale or its build provenance differs; rebuild it before freezing.")


def runtime_build_inputs() -> dict:
    """Content identities only; the record never contains local absolute paths."""
    files = list((ROOT / "orre_randomizer").rglob("*.py"))
    files += [ROOT / "orre_randomizer/_native" / name for name in (*NATIVE_RUNTIME_NAMES, "orre_musyx.json")]
    files += [ROOT / name for name in ("scripts/desktop.spec", "scripts/desktop_entry.py", "scripts/build_desktop.py", "scripts/release_media.py",
        "scripts/build_native.py", "scripts/build_music.py", "pyproject.toml", "requirements-build.txt",
        "native/music/patches.json", "native/music/renderer_adapter.c", "orre_randomizer/windows_update.ps1",
        "orre_randomizer/assets/game/provenance.json", "orre_randomizer/assets/app/provenance.json",
        "orre_randomizer/assets/app/logo.json", "orre_randomizer/assets/app/controller.json")]
    for folder in ("native", "native/disc", "native/launcher"):
        files += [ROOT / folder / name for name in ("Cargo.toml", "Cargo.lock")]
        files += list((ROOT / folder / "src").rglob("*.rs"))
    identities = {}
    for path in sorted(files):
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT.resolve()):
            raise RuntimeError("External runtime input refused")
        identities[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"schema": 1, "version": __version__, "files": identities}


def source_files(*, include_game_assets: bool = True) -> list[Path]:
    files = [ROOT / name for name in ("README.md", "CHANGELOG.md", "RESEARCH.md", "LICENSE", "THIRD_PARTY_NOTICES.md",
             "CONTRIBUTING.md", "PRODUCT.md", "DESIGN.md", "pyproject.toml", "requirements-build.txt", ".gitignore", ".gitattributes",
             "lancer-randomizer.ps1")]
    for directory, extensions in (("orre_randomizer", {".py", ".ps1"}), ("tests", {".py"}),
                                  ("scripts", {".py", ".ps1", ".spec", ".iss"}), ("docs", {".md"}),
                                  ("licenses", {".txt", ".json", ".md"}), (".github", {".yml", ".md"})):
        files += [p for p in (ROOT / directory).rglob("*") if p.is_file() and p.suffix in extensions]
    for folder in ("native", "native/disc", "native/launcher"):
        files += [ROOT / folder / name for name in ("Cargo.toml", "Cargo.lock")]
        files += [path for path in (ROOT / folder / "src").rglob("*.rs") if path.is_file()]
    files += [path for path in (ROOT / "native/music").rglob("*") if path.is_file() and path.suffix in {".c", ".h", ".json", ".md", ".txt"}]
    files.append(ROOT / "docs/reverse-engineering/baseline.json")
    files.append(ROOT / "scripts/EXTRA_PORTRAIT_CAPTURE.md")
    files += [ROOT / "scripts/vs_menu_artwork" / name for name in
              ("README.md", "scene-recipe.json", "genuine-gba-reference.json")]
    authoring = ROOT / BINGO_AUTHORING_ROOT
    for name in bingo_authoring_media(lambda name: (authoring / name).read_bytes()):
        path = authoring / name
        if path.is_symlink() or not path.resolve().is_relative_to(authoring.resolve()):
            raise RuntimeError("External Bingo authoring layer refused")
        files.append(path)
    documentation = ROOT / "docs/images"
    for name in documentation_media(lambda name: (documentation / name).read_bytes()):
        files.append(documentation / name)
    files += [ROOT / "tests/fixtures/presets" / f"rc2-{game}-{mode}.json"
              for game in ("colosseum", "xd") for mode in ("moves", "species")]
    files += [ROOT / "orre_randomizer/assets/app" / name
              for name in ("icon.png", "icon.ico", "provenance.json", "logo.png", "logo.json", "controller.png", "controller.json", "README.md")]
    # Explicit local interface pack exported once from the supplied game. Never
    # sweep game/, build/, user caches or arbitrary assets into a distribution.
    if include_game_assets:
        pack = ROOT / "orre_randomizer/assets/game"
        manifest = json.loads((pack / "provenance.json").read_text("utf-8"))
        for name, expected in manifest["files"].items():
            path = pack / name
            if (not path.resolve().is_relative_to(pack.resolve()) or path.is_symlink() or
                    not game_asset_name_allowed(name) or
                    path.stat().st_size != expected["bytes"] or
                    hashlib.sha256(path.read_bytes()).hexdigest() != expected["sha256"]):
                raise RuntimeError("Invalid interface asset: " + name)
            files.append(path)
        if set(pack.rglob("*")) - {path for path in pack.rglob("*") if path.is_dir()} != set(
                pack / name for name in manifest["files"]) | {pack / "provenance.json"}:
            raise RuntimeError("Unlisted files in interface pack")
        files.append(pack / "provenance.json")
    sidecar = ROOT / ".impeccable/design.json"
    if sidecar.is_file():
        files.append(sidecar)
    for path in files:
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT.resolve()):
            raise RuntimeError("Linked or external source file refused: " + str(path))
    return sorted(set(files))


def zip_sources(destination: Path, *, include_game_assets: bool = True):
    # A positive list, not a blacklist: game/, build/, disc images and emulator
    # files can never be accidentally picked up by a new root file or folder.
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in source_files(include_game_assets=include_game_assets):
            archive.write(path, f"{REPOSITORY_NAME}/" + path.relative_to(ROOT).as_posix())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-only", action="store_true")
    parser.add_argument("--output-dir", type=Path, help="Use a separate directory for a local candidate build")
    parser.add_argument("--edition", choices=("local", "public"), default="local",
                        help="Choose the output directory; both editions include the verified interface pack")
    parser.add_argument("--skip-freeze", action="store_true", help="Repackage the already tested executable without recompiling it")
    args = parser.parse_args()
    include_game_assets = True
    app_assets = ROOT / "orre_randomizer/assets/app"
    for filename, allowed in (("provenance.json", {"icon.png", "icon.ico"}), ("logo.json", {"logo.png"}),
                              ("controller.json", {"controller.png"})):
        manifest = json.loads((app_assets / filename).read_text("utf-8"))
        if set(manifest["files"]) != allowed:
            raise SystemExit("Unexpected application assets in " + filename)
        for name, expected in manifest["files"].items():
            path = app_assets / name
            if (path.is_symlink() or not path.resolve().is_relative_to(app_assets.resolve()) or
                    path.stat().st_size != expected["bytes"] or
                    hashlib.sha256(path.read_bytes()).hexdigest() != expected["sha256"]):
                raise SystemExit("Invalid application asset: " + name)
    if include_game_assets:
        from orre_randomizer.resources import MUSIC_FILES, home_logos, interface_assets, music_track, menu_icon
        images, sounds = interface_assets()
        if (len(images) != 5 or len(sounds) != 3 or any(music_track(scene) is None for scene in MUSIC_FILES)
                or menu_icon() is None
                or set(home_logos()) != {"colosseum", "xd"}):
            raise SystemExit("The exported interface pack is incomplete.")
    source_files(include_game_assets=include_game_assets)
    release = args.output_dir.resolve() if args.output_dir else ROOT / "dist" / ("public" if args.edition == "public" else "")
    release.mkdir(parents=True, exist_ok=True)
    source_zip = release / f"{REPOSITORY_NAME}-{__version__}-source.zip"
    if source_zip.exists():
        raise SystemExit(f"Release already exists: {source_zip}; move it aside before rebuilding.")
    if not args.source_only:
        if sys.platform != "win32":
            raise SystemExit("Build the Windows executable on Windows; use --source-only elsewhere.")
        validate_build_dependencies()
        work = ROOT / "build" / ("pyinstaller-public" if args.edition == "public" else "pyinstaller")
        app = release / "windows" / f"{APP_EXECUTABLE}-{__version__}"
        for folder in (app, work):
            if not folder.resolve().is_relative_to(ROOT) or folder.resolve() == ROOT:
                raise SystemExit("Build directory escaped the project; refusing cleanup.")
        command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                   "--distpath", str(release / "windows"), "--workpath", str(work),
                   str(ROOT / "scripts/desktop.spec")]
        # Other developer tools on PATH can have incompatible DLLs named icuuc.dll,
        # libcrypto, or Windows API shims. Resolve against Python/Qt and the OS only.
        environment = os.environ.copy()
        environment["ORRE_BUNDLE_GAME_ASSETS"] = "1" if include_game_assets else "0"
        windows = Path(environment.get("SystemRoot", r"C:\Windows"))
        environment["PATH"] = os.pathsep.join(map(str, (Path(sys.executable).parent,
            Path(sys.base_prefix), Path(sys.base_prefix) / "Scripts", windows / "System32", windows)))
        if not args.skip_freeze:
            subprocess.run([sys.executable, str(ROOT / "scripts/build_native.py")], cwd=ROOT, check=True)
            validate_native_runtime()
            build_inputs = runtime_build_inputs()
            subprocess.run(command, cwd=ROOT, env=environment, check=True)
            if build_inputs != runtime_build_inputs():
                raise SystemExit("Runtime sources changed during compilation. Rebuild in a new candidate directory.")
            (app / RUNTIME_BUILD_RECORD).write_text(json.dumps(build_inputs, indent=2) + "\n", encoding="utf-8")
        elif not (app / f"{APP_EXECUTABLE}.exe").is_file():
            raise SystemExit("No executable to repackage; build it first.")
        elif json.loads((app / "build-edition.json").read_text("utf-8"))["game_assets"] != include_game_assets:
            raise SystemExit("Executable edition mismatch; rebuild it before packaging.")
        else:
            validate_native_runtime()
            record = app / RUNTIME_BUILD_RECORD
            if not record.is_file() or json.loads(record.read_text("utf-8")) != runtime_build_inputs():
                raise SystemExit("The frozen executable does not match the current runtime sources. Rebuild it before packaging.")
        (app / "build-edition.json").write_text(json.dumps({"edition": args.edition,
            "game_assets": include_game_assets}, indent=2) + "\n", encoding="utf-8")
        for name in ("README.md", "CHANGELOG.md", "RESEARCH.md", "CONTRIBUTING.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "requirements-build.txt"):
            shutil.copyfile(ROOT / name, app / name)
        for path in (ROOT / "docs").rglob("*.md"):
            target = app / path.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
        for name in documentation_media(lambda name: (ROOT / "docs/images" / name).read_bytes()):
            target = app / "docs/images" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / "docs/images" / name, target)
        shutil.copytree(ROOT / "licenses", app / "licenses", dirs_exist_ok=True)
        sources = ROOT / "dist/third-party-sources"
        if not sources.is_dir():
            raise SystemExit("Run python scripts/fetch_qt_notices.py before packaging Qt binaries.")
        shutil.copytree(sources, app / "third-party-sources", dirs_exist_ok=True)
        (app / "build-versions.json").write_text(json.dumps({name: version(name) for name in
            ("PySide6-Essentials", "shiboken6", "Pillow", "pyinstaller")}, indent=2) + "\n", encoding="utf-8")
    zip_sources(source_zip, include_game_assets=include_game_assets)
    if not args.source_only:
        # Include the full application source beside replaceable Qt DLLs.
        shutil.copyfile(source_zip, app / source_zip.name)
        # This allowlist lets future portable updates remove obsolete bundled
        # files without sweeping up a user's ROMs, saves or personal files.
        owned = sorted(p.relative_to(app).as_posix() for p in app.rglob("*")
                       if p.is_file() and p != app / "update-files.json")
        (app / "update-files.json").write_text(json.dumps([*owned, "update-files.json"]), encoding="utf-8")
        binary_zip = release / f"{REPOSITORY_NAME}-{__version__}-windows-x64.zip"
        if binary_zip.exists():
            raise SystemExit(f"Release already exists: {binary_zip}")
        with zipfile.ZipFile(binary_zip, "x", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(app.rglob("*")):
                if path.is_file():
                    archive.write(path, f"{APP_EXECUTABLE}/" + path.relative_to(app).as_posix())
    paths = [source_zip] + ([] if args.source_only else [binary_zip])
    manifest = {p.name: {"bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths}
    (release / "SHA256SUMS.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
