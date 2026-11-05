"""Build the optional Rust codec offline; no third-party Rust crates."""
from pathlib import Path
import hashlib
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    manifest = ROOT / "native/Cargo.toml"
    subprocess.run(["cargo", "test", "--offline", "--manifest-path", str(manifest)], check=True)
    subprocess.run(["cargo", "build", "--release", "--offline", "--manifest-path", str(manifest)], check=True)
    filename = "orre_lzss.dll" if sys.platform == "win32" else (
        "liborre_lzss.dylib" if sys.platform == "darwin" else "liborre_lzss.so")
    destination = ROOT / "orre_randomizer/_native" / filename
    destination.parent.mkdir(exist_ok=True)
    compiled = ROOT / "native/target/release" / filename
    # Windows locks loaded DLLs. An identical codec already in use needs no
    # replacement, so concurrent read-only checks do not block packaging.
    if not destination.is_file() or hashlib.sha256(compiled.read_bytes()).digest() != hashlib.sha256(destination.read_bytes()).digest():
        shutil.copyfile(compiled, destination)
    toolchain = Path(subprocess.check_output(["rustc", "--print", "sysroot"], text=True).strip())
    docs = toolchain / "share/doc/rust"
    licenses = ROOT / "licenses/rust"
    licenses.mkdir(parents=True, exist_ok=True)
    if (docs / "licenses").is_dir():
        shutil.copytree(docs / "licenses", licenses / "licenses", dirs_exist_ok=True)
    for name in ("COPYRIGHT-library.html", "COPYRIGHT.html"):
        if (docs / name).is_file():
            shutil.copyfile(docs / name, licenses / (name + ".txt"))
    (licenses / "toolchain.txt").write_text(subprocess.check_output(["rustc", "--version"], text=True), encoding="utf-8")
    print(destination)


if __name__ == "__main__":
    main()
