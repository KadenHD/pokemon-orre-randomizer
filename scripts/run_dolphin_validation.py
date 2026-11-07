"""Monitor one manually operated Dolphin run without touching personal data.

Use a portable emulator copy and a prepared profile, both below build/. This
launcher records the actual process return code, rather than a shell's status.
It never sends UI input, stops Dolphin, or restores personal files.
"""
from __future__ import annotations

import argparse
import configparser
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
WRITE_PATH_KEYS = frozenset({
    "memcardapath", "memcardbpath", "gcifolderapath", "gcifolderbpath",
    "nandrootpath", "nandroot", "fspath", "wfspath", "dumppath", "loadpath",
    "resourcepackpath", "gbasavespath", "gbasavepath", "wiisdcardpath",
    "wiisdcardsyncfolder", "wiisdcardsyncfolderpath",
})
REPORT_REPLACE_ATTEMPTS = 21
REPORT_REPLACE_DELAY_SECONDS = 0.05


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_personal_profile() -> Path:
    """Never silently audit an invented home-relative profile on Windows."""
    appdata = os.environ.get("APPDATA", "").strip()
    if not appdata or not Path(appdata).is_absolute():
        raise ValueError("APPDATA is missing or is not an absolute path; "
                         "pass --personal-profile explicitly to select the profile to protect.")
    return Path(appdata) / "Dolphin Emulator"


def publish_report(report: Path, result: dict) -> None:
    """Replace JSON atomically, allowing brief Windows reader sharing locks."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=report.parent,
                                         prefix=report.name + ".", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        for attempt in range(REPORT_REPLACE_ATTEMPTS):
            try:
                os.replace(temporary, report)
                return
            except PermissionError:
                # Python readers on Windows omit FILE_SHARE_DELETE. Retry only
                # that sharing/access failure, sleeping at most one second.
                if attempt + 1 == REPORT_REPLACE_ATTEMPTS:
                    raise
                time.sleep(REPORT_REPLACE_DELAY_SECONDS)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def inside(path: Path, directory: Path) -> bool:
    return path != directory and path.is_relative_to(directory)


def reject_links(path: Path) -> None:
    """A lexical path inside build must not redirect to an original elsewhere."""
    selected = path.absolute()
    for part in (selected, *selected.parents):
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise ValueError(f"Linked paths are not allowed in validation jobs: {part}")
    if selected.is_file() and selected.stat().st_nlink > 1:
        raise ValueError(f"Hardlinked files are not allowed in validation jobs: {selected}")


def snapshot_profile(profile: Path) -> dict[str, dict]:
    """Read the complete personal profile; do not create absent directories."""
    result = {}
    if profile.is_dir():
        for path in sorted(profile.rglob("*")):
            if path.is_file():
                result[path.relative_to(profile).as_posix()] = {
                    "bytes": path.stat().st_size, "sha256": sha256(path)}
    return result


def snapshot_files(paths: list[Path]) -> dict[str, dict]:
    return {str(path): ({"bytes": path.stat().st_size, "sha256": sha256(path)}
                       if path.exists() else {"exists": False})
            for path in sorted(set(paths))}


def changed_entries(before: dict, after: dict) -> list[str]:
    return sorted(key for key in before.keys() | after.keys() if before.get(key) != after.get(key))


def validate_job(emulator: Path, iso: Path, profile: Path, report: Path,
                 personal_profile: Path, *, workspace: Path = ROOT) -> tuple[Path, Path, Path, Path, Path]:
    workspace = workspace.resolve(strict=True)
    build = workspace / "build"
    for path in (emulator, profile, report):
        reject_links(path)
    emulator = emulator.resolve(strict=True)
    iso = iso.resolve(strict=True)
    profile = profile.resolve(strict=True)
    report = report.absolute()
    report_parent = report.parent.resolve(strict=True)
    report = report_parent / report.name
    personal_profile = personal_profile.resolve()
    for path in (emulator, profile, report):
        if not inside(path, build):
            raise ValueError("Emulator copy, test profile and report must stay under project build/.")
    if emulator.name.lower() != "dolphin.exe" or not emulator.is_file():
        raise ValueError("Select the copied Dolphin.exe explicitly.")
    portable = emulator.parent / "portable.txt"
    reject_links(portable)
    if not portable.is_file():
        raise ValueError("The emulator copy must have its own portable.txt fallback.")
    if not iso.is_file() or iso.suffix.lower() not in {".iso", ".rvz"}:
        raise ValueError("A readable ISO or RVZ is required.")
    if not profile.is_dir() or not (profile / "Config/Dolphin.ini").is_file():
        raise ValueError("Prepare an isolated Dolphin profile before launching.")
    if profile == personal_profile or profile.is_relative_to(personal_profile) or personal_profile.is_relative_to(profile):
        raise ValueError("The test profile and personal profile must be disjoint.")
    if inside(iso, profile) or inside(iso, emulator.parent):
        raise ValueError("The image must stay outside the writable profile and emulator directory.")
    if report == iso or inside(report, profile) or inside(report, emulator.parent):
        raise ValueError("Keep monitoring reports outside the writable Dolphin directories.")
    for path in profile.rglob("*"):
        reject_links(path)
    # Custom paths can override -u. Reject any writable target outside this run.
    configs = list((profile / "Config").glob("*.ini"))
    configs += list((profile / "GameSettings").glob("*.ini"))
    for path in configs:
        parser = configparser.ConfigParser(interpolation=None, strict=True, allow_no_value=True)
        try:
            parser.read_string(path.read_text("utf-8-sig"))
        except (configparser.Error, UnicodeError) as error:
            raise ValueError(f"Invalid test configuration: {path}") from error
        for section in parser.sections():
            for key, value in parser.items(section):
                if key.lower() not in WRITE_PATH_KEYS or not value or not value.strip():
                    continue
                target = Path(value)
                # Relative Dolphin paths resolve from the executable working dir.
                target = (target if target.is_absolute() else emulator.parent / target).resolve()
                if not inside(target, profile):
                    raise ValueError(f"Writable Dolphin path escapes the isolated profile: {section}.{key}")
                reject_links(target)
    siblings = [report, report.with_suffix(report.suffix + ".stdout.log"),
                report.with_suffix(report.suffix + ".stderr.log")]
    if any(path.exists() for path in siblings):
        raise FileExistsError("A validation report or capture already exists; choose a new report name.")
    return emulator, iso, profile, report, personal_profile


def run_validation(emulator: Path, iso: Path, profile: Path, report: Path,
                   personal_profile: Path, protect_files: list[Path] | None = None,
                   *, workspace: Path = ROOT, debugger: bool = False) -> dict:
    emulator, iso, profile, report, personal_profile = validate_job(
        emulator, iso, profile, report, personal_profile, workspace=workspace)
    protected = [iso, emulator, *(Path(p).resolve(strict=True) for p in protect_files or [])]
    before_files = snapshot_files(protected)
    before_personal = snapshot_profile(personal_profile)
    stdout_path = report.with_suffix(report.suffix + ".stdout.log")
    stderr_path = report.with_suffix(report.suffix + ".stderr.log")
    argv = [str(emulator), "-u", str(profile), "-e", str(iso),
            "-C", "Dolphin.DSP.Volume=0"]
    if debugger:
        argv.append("-d")
    result = {"schema_version": 1, "status": "prepared", "started_utc": utc_now(),
              "argv": argv, "cwd": str(emulator.parent), "profile": str(profile),
              "portable_fallback": str(emulator.parent / "User"),
              "personal_profile": str(personal_profile), "protected_files_before": before_files,
              "personal_profile_before": before_personal,
              "stdout": str(stdout_path), "stderr": str(stderr_path),
              "automatic_termination": False, "automatic_restore": False}
    with report.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")

    def update_report(*, required=True):
        # Readers can safely poll the running report without seeing partial JSON.
        try:
            publish_report(report, result)
        except OSError as error:
            if required:
                raise
            diagnostic = f"Report publication failed while {result['status']}: {error}"
            result.setdefault("report_publication_errors", []).append(diagnostic)
            print(diagnostic, file=sys.stderr, flush=True)

    environment = os.environ.copy()
    for key in ("QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH", "QT_QPA_PLATFORM"):
        environment.pop(key, None)
    started = time.monotonic()
    try:
        with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
            process = subprocess.Popen(argv, cwd=emulator.parent, env=environment,
                                       stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr)
            result.update(status="running", pid=process.pid)
            # A reader lock must not abandon a live child or mislabel its
            # successful launch. Keep waiting and require the final publication.
            update_report(required=False)
            print(json.dumps({"status": "running", "pid": process.pid, "report": str(report)}), flush=True)
            try:
                code = process.wait()
            except KeyboardInterrupt:
                result.update(status="monitor_interrupted", finished_utc=utc_now(),
                              elapsed_seconds=round(time.monotonic() - started, 3),
                              diagnostic="Dolphin was not terminated; close it manually before final audit.")
                update_report(required=False)
                raise
            result.update(status="finished", return_code=code,
                          return_code_hex=f"0x{code & 0xFFFFFFFF:08X}")
    except OSError as error:
        result.update(status="launch_failed", diagnostic=str(error))
    after_files = snapshot_files(protected)
    after_personal = snapshot_profile(personal_profile)
    file_changes = changed_entries(before_files, after_files)
    personal_changes = changed_entries(before_personal, after_personal)
    result.update(finished_utc=utc_now(), elapsed_seconds=round(time.monotonic() - started, 3),
                  protected_files_after=after_files, personal_profile_after=after_personal,
                  protected_files_changed=file_changes, personal_profile_changed=personal_changes,
                  protected_files_unchanged=not file_changes, personal_profile_unchanged=not personal_changes)
    result["successful_process_and_preservation"] = (
        result["status"] == "finished" and result["return_code"] == 0 and not file_changes and not personal_changes)
    update_report()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--emulator", type=Path, required=True)
    parser.add_argument("--iso", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--personal-profile", type=Path,
                        help="Personal profile to protect (default: APPDATA/Dolphin Emulator).")
    parser.add_argument("--protect-file", type=Path, action="append", default=[])
    parser.add_argument("--debugger", action="store_true", help="Show Dolphin's debugger for isolated test fixtures")
    args = parser.parse_args()
    try:
        personal_profile = args.personal_profile if args.personal_profile is not None else default_personal_profile()
        result = run_validation(args.emulator, args.iso, args.profile, args.report,
                                personal_profile, args.protect_file, debugger=args.debugger)
    except (OSError, ValueError) as error:
        print(f"Validation launch refused: {error}", file=sys.stderr)
        return 2
    print(json.dumps({key: result.get(key) for key in (
        "status", "pid", "return_code", "return_code_hex", "protected_files_unchanged", "personal_profile_unchanged")}), flush=True)
    return 0 if result["successful_process_and_preservation"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
