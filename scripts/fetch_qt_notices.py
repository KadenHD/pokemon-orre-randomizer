"""Prepare exact upstream Qt sources and license notices before a binary release."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
VERSION = "6.11.2"
SOURCES = {
    "qtbase": f"https://download.qt.io/archive/qt/6.11/{VERSION}/submodules/qtbase-everywhere-src-{VERSION}.tar.xz",
    "qtsvg": f"https://download.qt.io/archive/qt/6.11/{VERSION}/submodules/qtsvg-everywhere-src-{VERSION}.tar.xz",
    "pyside-setup": f"https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-{VERSION}-src/pyside-setup-everywhere-src-{VERSION}.tar.xz",
}


def main():
    folder = ROOT / "dist/third-party-sources"
    folder.mkdir(parents=True, exist_ok=True)
    def prepare(item):
        name, url = item
        target = folder / url.rsplit("/", 1)[1]
        if not target.exists():
            request = urllib.request.Request(url, headers={"User-Agent": "colosseum-randomizer-build"})
            with urllib.request.urlopen(request, timeout=90) as response, target.open("xb") as out:
                while data := response.read(1024**2):
                    out.write(data)
        notices = []
        with tarfile.open(target) as archive:
            for member in archive:
                path = Path(*Path(member.name).parts[1:])
                filename = path.name.lower()
                if (member.isfile() and not path.is_absolute() and ".." not in path.parts and
                    ("LICENSES" in path.parts or filename.startswith(("license", "copying", "copyright"))
                     or filename == "qt_attribution.json")):
                    destination = ROOT / "licenses/qt" / name / str(path)
                    if destination.suffix not in (".txt", ".json", ".md"):
                        destination = destination.with_name(destination.name + ".txt")
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(archive.extractfile(member).read())
                    notices.append(destination.relative_to(ROOT).as_posix())
        return {"name": name, "url": url, "file": target.name,
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "notices": notices}
    with ThreadPoolExecutor(max_workers=3) as executor:
        records = list(executor.map(prepare, SOURCES.items()))
    manifest = ROOT / "licenses/qt/upstream-manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    print(json.dumps([{k: v for k, v in row.items() if k != "notices"} for row in records], indent=2))


if __name__ == "__main__":
    main()
