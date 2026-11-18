"""Build the Rust codecs and bundled disc converter from locked dependencies."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def build_environment():
    """Keep local account/workspace names out of Rust panic source locations."""
    environment = os.environ.copy()
    encoded = environment.get("CARGO_ENCODED_RUSTFLAGS")
    flags = encoded.split("\x1f") if encoded else environment.get("RUSTFLAGS", "").split()
    for prefix, replacement in ((Path.home(), "build-user"),
            (Path(environment.get("CARGO_HOME", Path.home() / ".cargo")), "cargo"),
            (ROOT, "orre")):
        for spelling in sorted({str(prefix), prefix.as_posix()}):
            flags.append(f"--remap-path-prefix={spelling}={replacement}")
    environment["CARGO_ENCODED_RUSTFLAGS"] = "\x1f".join(flags)
    return environment


def main():
    destination_dir = ROOT / "orre_randomizer/_native"
    destination_dir.mkdir(exist_ok=True)
    for folder, name in (("native", "orre_lzss"), ("native/disc", "orre_disc")):
        manifest = ROOT / folder / "Cargo.toml"
        environment = build_environment()
        subprocess.run(["cargo", "test", "--release", "--locked", "--manifest-path", str(manifest)], check=True, env=environment)
        subprocess.run(["cargo", "build", "--release", "--locked", "--manifest-path", str(manifest)], check=True, env=environment)
        filename = name + ".dll" if sys.platform == "win32" else (
            "lib" + name + ".dylib" if sys.platform == "darwin" else "lib" + name + ".so")
        destination = destination_dir / filename
        compiled = ROOT / folder / "target/release" / filename
        # Windows locks loaded DLLs; identical bytes need no replacement.
        if not destination.is_file() or hashlib.sha256(compiled.read_bytes()).digest() != hashlib.sha256(destination.read_bytes()).digest():
            shutil.copyfile(compiled, destination)
        print(destination)
    collect_disc_licenses()
    launcher = ROOT / "native/launcher/Cargo.toml"
    subprocess.run(["cargo", "build", "--release", "--locked", "--manifest-path", str(launcher)],
                   check=True, env=build_environment())
    launcher_name = "orre-launcher.exe" if sys.platform == "win32" else "orre-launcher"
    shutil.copyfile(launcher.parent / "target/release" / launcher_name,
                    destination_dir / ("OrreLauncher.exe" if sys.platform == "win32" else "OrreLauncher"))
    if sys.platform == "win32":
        subprocess.run([sys.executable, str(ROOT / "scripts/build_music.py")], check=True)
    toolchain = Path(subprocess.check_output(["rustc", "--print", "sysroot"], text=True).strip())
    docs = toolchain / "share/doc/rust"
    licenses = ROOT / "licenses/rust"
    licenses.mkdir(parents=True, exist_ok=True)
    if (docs / "licenses").is_dir():
        shutil.copytree(docs / "licenses", licenses / "licenses", dirs_exist_ok=True)
    for name in ("COPYRIGHT-library.html", "COPYRIGHT.html"):
        if (docs / name).is_file():
            target = licenses / (name + ".txt")
            if (not target.is_file() or hashlib.sha256((docs / name).read_bytes()).digest()
                    != hashlib.sha256(target.read_bytes()).digest()):
                shutil.copyfile(docs / name, target)
    (licenses / "toolchain.txt").write_text(subprocess.check_output(["rustc", "--version"], text=True), encoding="utf-8")


def collect_disc_licenses():
    host = next(line.split(": ", 1)[1] for line in subprocess.check_output(
        ["rustc", "-vV"], text=True).splitlines() if line.startswith("host: "))
    metadata = json.loads(subprocess.check_output(["cargo", "metadata", "--locked",
        "--filter-platform", host, "--format-version", "1", "--manifest-path", str(ROOT / "native/disc/Cargo.toml")], text=True))
    resolved = {node["id"] for node in metadata["resolve"]["nodes"]}
    destination = ROOT / "licenses/disc"
    destination.mkdir(parents=True, exist_ok=True)
    packages = []
    for package in metadata["packages"]:
        if package["source"] is None or package["id"] not in resolved:
            continue
        directory = Path(package["manifest_path"]).parent
        target = destination / (package["name"] + "-" + package["version"])
        notices = []
        # Include bundled C-library licenses as well as each Rust crate's terms.
        candidates = list(directory.rglob("*"))
        if package["source"].startswith("git+"):
            candidates += [path for path in directory.parent.iterdir() if path.is_file()]
        for path in candidates:
            if path.is_file() and path.name.lower().startswith(("license", "licence", "copying", "notice", "copyright")):
                if path.stat().st_size > 1024 * 1024 or path.suffix in {".rs", ".c", ".h"}:
                    continue
                relative = path.relative_to(directory if path.is_relative_to(directory) else directory.parent).as_posix()
                filename = relative.replace("/", "__") + ".txt"
                target.mkdir(exist_ok=True)
                shutil.copyfile(path, target / filename)
                notices.append(filename)
        if not notices:
            raise RuntimeError("Missing dependency license: " + package["name"])
        packages.append({"name": package["name"], "version": package["version"],
            "license": package["license"], "repository": package["repository"],
            "source": package["source"], "notices": sorted(notices)})
    (destination / "dependencies.json").write_text(json.dumps(packages, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
