"""Build the original-bank music renderer from SHA256-pinned public source.

Requires the existing x64 MSVC C11 toolchain and Windows SDK. No game assets,
Dolphin hooks or private prototype binaries are inputs to this build.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PIN = "717404d77c17a95dd101bbe737d0f9549ab600e6"
ARCHIVE_SHA256 = "378a43b85da94a64549019956dc1cfac8134ce1ffbe6d9e31f9358659906e29d"
URL = f"https://codeload.github.com/AxioDL/musyx/zip/{PIN}"
EXPORTS = ["orre_music_abi_version", "orre_decode_dsp", "orre_init", "orre_reverb", "orre_room_shutdown",
    "orre_set_native_src", "orre_native_envelope", "orre_retail_predelay", "orre_sample581_outside",
    "orre_sample581_count", "sndQuit", "sndPushGroup", "sndSeqPlayEx", "sndSeqStop",
    "sndSeqGetValid", "sndSeqVolume", "sndPCRender", "sndPCValidateGroup", "sndPCValidateArrangement"]


def extract_source(data: bytes, destination: Path):
    if hashlib.sha256(data).hexdigest() != ARCHIVE_SHA256:
        raise ValueError("Pinned MusyX source archive SHA256 differs")
    archive = zipfile.ZipFile(io.BytesIO(data))
    total = 0
    for member in archive.infolist():
        target = (destination / member.filename).resolve()
        total += member.file_size
        if (not target.is_relative_to(destination.resolve()) or (member.external_attr >> 16) & 0o170000 == 0o120000
                or total > 16 * 1024 * 1024 or "\\" in member.filename):
            raise ValueError("Unsafe pinned MusyX archive member")
    archive.extractall(destination)
    return destination / ("musyx-" + PIN)


def apply_renderer_patches(source: Path):
    patches = json.loads((ROOT / "native/music/patches.json").read_text(encoding="utf-8"))
    for patch in patches:
        path = source / patch["path"]
        original = path.read_bytes()
        if hashlib.sha256(original).hexdigest() != patch["sha256"]:
            raise ValueError("MusyX patch source SHA256 differs: " + patch["path"])
        text = original.decode("utf-8")
        for change in patch["changes"]:
            if text.count(change["before"]) != 1:
                raise ValueError("MusyX patch preimage is ambiguous: " + patch["path"])
            text = text.replace(change["before"], change["after"], 1)
        path.write_text(text, encoding="utf-8", newline="\n")


def build_environment():
    environment = os.environ.copy()
    compiler = shutil.which("cl.exe")
    if (compiler and environment.get("INCLUDE") and environment.get("LIB")
            and environment.get('VSCMD_ARG_TGT_ARCH', 'x64').lower() == 'x64'):
        return Path(compiler), environment
    program_files = Path(os.environ.get("ProgramFiles", "C:/Program Files"))
    candidates = list((program_files / "Microsoft Visual Studio").glob("*/*/VC/Tools/MSVC/*/bin/Hostx64/x64/cl.exe"))
    program_files_x86 = Path(os.environ.get('ProgramFiles(x86)', 'C:/Program Files (x86)'))
    vswhere = program_files_x86 / 'Microsoft Visual Studio/Installer/vswhere.exe'
    if vswhere.is_file():
        installations = subprocess.check_output([str(vswhere), '-all', '-prerelease', '-products', '*',
            '-requires', 'Microsoft.VisualStudio.Component.VC.Tools.x86.x64', '-property', 'installationPath'], text=True)
        for installation in installations.splitlines():
            candidates.extend(Path(installation).glob('VC/Tools/MSVC/*/bin/Hostx64/x64/cl.exe'))
    if not candidates:
        raise RuntimeError("An installed x64 MSVC C11 toolchain is required")
    compiler = max(candidates, key=lambda path: tuple(int(part) for part in path.parents[3].name.split(".")))
    vc = compiler.parents[3]
    sdk = program_files_x86 / "Windows Kits/10"
    versions = [path.name for path in (sdk / "Include").glob("*") if (sdk / "Lib" / path.name / "um/x64").is_dir()]
    if not versions:
        raise RuntimeError("An installed Windows SDK is required")
    version = max(versions, key=lambda value: tuple(int(part) for part in value.split(".")))
    environment["INCLUDE"] = ";".join(str(path) for path in [vc / "include", sdk / "Include" / version / "ucrt", sdk / "Include" / version / "shared", sdk / "Include" / version / "um"])
    environment["LIB"] = ";".join(str(path) for path in [vc / "lib/x64", sdk / "Lib" / version / "ucrt/x64", sdk / "Lib" / version / "um/x64"])
    environment["PATH"] = str(compiler.parent) + os.pathsep + environment.get("PATH", "")
    return compiler, environment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, help="Use a previously downloaded pinned source archive")
    parser.add_argument("--output", type=Path, default=ROOT / "orre_randomizer/_native")
    args = parser.parse_args()
    work = ROOT / "build/music-renderer"
    work.mkdir(parents=True, exist_ok=True)
    data = args.archive.read_bytes() if args.archive else urllib.request.urlopen(URL, timeout=45).read(12_000_001)
    source = extract_source(data, work)
    apply_renderer_patches(source)
    compiler, environment = build_environment()
    cmake = (source / "CMakeLists.txt").read_text(encoding="utf-8")
    block = re.search(r"add_library\(musyx STATIC(.*?)\n\)", cmake, re.S).group(1)
    sources = re.findall(r"src/[^\s)]+\.c", block) + ["src/musyx/runtime/hw_pc_null.c"]
    definition = work / "orre_musyx.def"
    definition.write_text("LIBRARY orre_musyx\nEXPORTS\n" + "\n".join(EXPORTS) + "\n", encoding="ascii")
    compiled = work / "orre_musyx.dll"
    adapter = ROOT / "native/music/renderer_adapter.c"
    command = [str(compiler), "/nologo", "/LD", "/MT", "/O2", "/Brepro", "/std:c11", "/experimental:c11atomics",
        "/D_USE_MATH_DEFINES", "/DMUSY_TARGET=0", "/DMUSY_VERSION_MAJOR=2", "/DMUSY_VERSION_MINOR=0",
        "/DMUSY_VERSION_PATCH=0", "/DNDEBUG", "/I" + str(source / "include")]
    command += [str(source / name) for name in sources] + [str(adapter)]
    command += ["/link", "/DEF:" + str(definition), "/OUT:" + str(compiled)]
    result = subprocess.run(command, cwd=work, env=environment, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (work / "build.log").write_text(result.stdout, encoding="utf-8")
    if result.returncode:
        raise RuntimeError("MusyX compilation failed:\n" + result.stdout[-6000:])
    library = ctypes.CDLL(str(compiled))
    library.orre_music_abi_version.restype = ctypes.c_uint32
    if library.orre_music_abi_version() != 1:
        raise RuntimeError("Built music renderer ABI differs")
    for name in EXPORTS:
        getattr(library, name)
    args.output.mkdir(parents=True, exist_ok=True)
    destination = args.output / "orre_musyx.dll"
    if not destination.is_file() or hashlib.sha256(compiled.read_bytes()).digest() != hashlib.sha256(destination.read_bytes()).digest():
        shutil.copyfile(compiled, destination)
    provenance = {"abi": 1, "source_url": URL, "source_commit": PIN, "archive_sha256": ARCHIVE_SHA256,
        "patches_sha256": hashlib.sha256((ROOT / "native/music/patches.json").read_bytes()).hexdigest(),
        "adapter_sha256": hashlib.sha256(adapter.read_bytes()).hexdigest(),
        "compiler_sha256": hashlib.sha256(compiler.read_bytes()).hexdigest(),
        "renderer_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(), "license": "CC0-1.0"}
    (args.output / "orre_musyx.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    print("Built and checked music renderer", provenance["renderer_sha256"])


if __name__ == "__main__":
    main()
