"""Run the extracted Windows EXE offscreen, away from Python and developer PATH."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from colosseum_randomizer import APP_EXECUTABLE


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--edition", choices=("local", "public"), default="local")
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    if sys.platform != "win32":
        parser.error("The frozen Windows app must run on Windows.")
    if args.report.exists() or args.report.with_suffix("").exists():
        parser.error("Choose a new report path; previous evidence is kept.")
    release = ROOT / "dist" / ("public" if args.edition == "public" else "")
    manifest = json.loads((release / "SHA256SUMS.json").read_text("utf-8"))
    archives = [name for name in manifest if name.endswith("-windows-x64.zip")]
    if len(archives) != 1:
        parser.error("Expected exactly one Windows archive in the release manifest.")
    # Run the hash/integrity/media audit before extraction or execution.
    subprocess.run([sys.executable, str(ROOT/"scripts/verify_release.py"), "--edition", args.edition], check=True, cwd=ROOT)
    build = ROOT / "build"
    build.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="smoke-étoile ", dir=build) as folder:
        work = Path(folder).resolve()
        if not work.is_relative_to(build.resolve()):
            raise RuntimeError("Temporary extraction escaped build directory")
        with zipfile.ZipFile(release / archives[0]) as archive:
            for item in archive.infolist():
                name = PurePosixPath(item.filename)
                if (name.is_absolute() or ".." in name.parts or PureWindowsPath(item.filename).drive or
                        "\\" in item.filename or (item.external_attr >> 16) & 0o170000 == 0o120000):
                    raise RuntimeError("Unsafe ZIP extraction path")
            archive.extractall(work)
        executable = work / APP_EXECUTABLE / f"{APP_EXECUTABLE}.exe"
        for name in ("Temp", "AppData", "LocalAppData", "unrelated working directory"):
            (work/name).mkdir()
        windows = Path(os.environ.get("SystemRoot", "C:/Windows"))
        environment = {"SystemRoot": str(windows), "WINDIR": str(windows),
                       "PATH": os.pathsep.join(map(str, (windows/"System32", windows))),
                       "TEMP": str(work/"Temp"), "TMP": str(work/"Temp"),
                       "APPDATA": str(work/"AppData"), "LOCALAPPDATA": str(work/"LocalAppData"),
                       "QT_QPA_PLATFORM": "offscreen"}
        diagnostic = work / "diagnostics.json"
        result = subprocess.run([str(executable), "--diagnostics", str(diagnostic), "--screenshots"],
                                cwd=work/"unrelated working directory", env=environment,
                                timeout=60, capture_output=True)
        if result.returncode != 0 or not diagnostic.is_file():
            raise RuntimeError(f"Packaged diagnostic failed ({result.returncode}): " +
                               (diagnostic.read_text("utf-8") if diagnostic.is_file() else "No report"))
        data = json.loads(diagnostic.read_text("utf-8"))
        assert data["successful"] and data["frozen"] and data["codec"] == "rust-lzss-v1"
        assert data["application_icon_available"] and {16, 256} <= set(data["application_icon_sizes"])
        assert len(data["home_states"]) == 12
        assert len(data["xd_states"]) == 36
        assert len(data["states"]) == 48
        assert len(data["exclusion_states"]) == 24
        assert len(data["shiny_states"]) == 60
        assert len(data["preview_states"]) == 24
        assert {state["language"] for state in data["states"]} == {"fr", "en", "de", "es", "it", "ja"}
        assert not data["rom_opened"] and not data["personal_preferences_opened"]
        if args.edition == "public":
            assert not data["images"] and not data["sounds"] and not data["music_available"]
        else:
            assert len(data["images"]) == 5 and len(data["sounds"]) == 3 and data["music_available"]
        assert not any((work/"AppData").rglob("*.ini"))
        evidence = args.report.with_suffix("")
        evidence.mkdir()
        state_keys = ("home_states", "xd_states", "states", "exclusion_states", "shiny_states", "preview_states")
        for key in state_keys:
            for state in data[key]:
                if "screenshot" in state:
                    shutil.copyfile(work/state["screenshot"], evidence/state["screenshot"])
        data.update(edition=args.edition, archive=archives[0],
                    archive_sha256=manifest[archives[0]]["sha256"],
                    extracted_to_unicode_path=True, developer_path_removed=True,
                    unrelated_working_directory=True,
                    scope="Relocated local smoke test, not an independent clean Windows installation.")
        with args.report.open("x", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    count = sum(len(data[key]) for key in state_keys)
    print(f"Extracted {args.edition} app: {count} UI states, Rust codec and resource edition verified.")


if __name__ == "__main__":
    main()
