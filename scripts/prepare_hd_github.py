"""Prepare verified HD assets for GitHub Releases, without publishing anything.

The original ZIPs remain intact. Large ZIPs are split into binary transport
fragments; clients reconstruct the exact original bytes before extraction.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orre_randomizer.hd_packs import PACKS, checkpoint, remove_owned
from scripts.prepare_hd_hosting import _publish, _reject_links, _verify, _copy_archive

GITHUB_ASSET_LIMIT = 2 * 1024**3
DEFAULT_FRAGMENT_BYTES = 1_900_000_000


def prepare_github(colosseum: Path, xd: Path, output: Path, *, repository=None,
                   tag=None, fragment_bytes=DEFAULT_FRAGMENT_BYTES, cancel=None):
    cancel = cancel or threading.Event()
    if type(fragment_bytes) is not int or not 1 <= fragment_bytes < GITHUB_ASSET_LIMIT:
        raise ValueError("Fragment size must be below the GitHub 2 GiB asset limit")
    if repository is not None and not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Expected an owner/repository name")
    if tag is not None and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", tag):
        raise ValueError("Expected a fixed release tag")
    if (repository is None) != (tag is None):
        raise ValueError("Repository and release tag must be supplied together")
    output = Path(os.path.abspath(output))
    _reject_links(output)
    if os.path.lexists(output) or not output.parent.is_dir():
        raise ValueError("Output must be a new directory inside an existing parent")
    inputs = []
    for game, path in (("colosseum", colosseum), ("xd", xd)):
        pack = PACKS[game]
        if len(pack.parts) != 1 or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", pack.version):
            raise ValueError("Expected one original ZIP and a safe fixed version")
        source = Path(os.path.abspath(path))
        part = pack.parts[0]
        _verify(source, part, cancel)
        inputs.append((pack, part, source))
    stage = Path(tempfile.mkdtemp(prefix=f".{output.name}.staging-", dir=output.parent))
    manifest = {"schema": 1, "published": False, "production_configured": False,
        "proposed_repository": repository, "proposed_tag": tag,
        "github_asset_limit": GITHUB_ASSET_LIMIT, "archives": [], "assets": []}
    try:
        for pack, part, source in inputs:
            prefix = f"{pack.game}-{pack.version}-{part.sha256[:12]}.zip"
            fragmented = part.size > fragment_bytes
            archive = {"game": pack.game, "version": pack.version,
                "original_filename": part.filename or source.name,
                "size": part.size, "sha256": part.sha256,
                "author": pack.author, "author_source": pack.source, "assets": []}
            combined = hashlib.sha256()
            with source.open("rb") as incoming:
                offset, index = 0, 1
                while offset < part.size:
                    checkpoint(cancel)
                    count = min(fragment_bytes, part.size - offset)
                    name = prefix + (f".{index:03d}" if fragmented else "")
                    destination = stage / name
                    if not fragmented:
                        try:
                            os.link(source, destination, follow_symlinks=False)
                            storage = "hardlink"
                        except OSError:
                            _copy_archive(source, destination, cancel)
                            storage = "copy"
                        data_hash = part.sha256
                    else:
                        fragment_hash = hashlib.sha256()
                        with destination.open("xb") as outgoing:
                            left = count
                            while left:
                                checkpoint(cancel)
                                chunk = incoming.read(min(4 * 1024**2, left))
                                if not chunk:
                                    raise ValueError("Source archive ended during fragmentation")
                                outgoing.write(chunk)
                                fragment_hash.update(chunk)
                                combined.update(chunk)
                                left -= len(chunk)
                        data_hash, storage = fragment_hash.hexdigest(), "fragment"
                    asset = {"game": pack.game, "name": name, "offset": offset,
                        "size": count, "sha256": data_hash, "storage": storage}
                    if repository:
                        asset["proposed_url"] = f"https://github.com/{repository}/releases/download/{tag}/{name}"
                    manifest["assets"].append(asset)
                    archive["assets"].append(name)
                    offset += count
                    index += 1
            if fragmented and combined.hexdigest() != part.sha256:
                raise ValueError("Transport fragments do not reproduce the original archive")
            _verify(source, part, cancel)
            manifest["archives"].append(archive)
        (stage / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        (stage / "SHA256SUMS").write_text("".join(f"{a['sha256']}  {a['name']}\n" for a in manifest["assets"]), encoding="ascii")
        (stage / "README.md").write_text(
            "# HD release assets - private preparation\n\n"
            "Nothing has been published or configured. Hosting approval is still required.\n"
            "The small ZIP may be hardlinked to its original; do not modify it. Binary\n"
            "fragments reconstruct the unchanged large ZIP in manifest order. Verify each\n"
            "fragment and the complete original ZIP before extraction. The manifest records\n"
            "the authors and fixed checksums. Original pack rights remain separate from\n"
            "Orre's code license; retain author credits and redistribution terms.\n",
            encoding="utf-8")
        checkpoint(cancel)
        _reject_links(output)
        _publish(stage, output)
        return manifest
    finally:
        if os.path.lexists(stage):
            _reject_links(stage)
            remove_owned(stage, output.parent)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--colosseum", required=True, type=Path)
    parser.add_argument("--xd", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--repository")
    parser.add_argument("--tag")
    args = parser.parse_args(argv)
    result = prepare_github(args.colosseum, args.xd, args.output,
        repository=args.repository, tag=args.tag)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
