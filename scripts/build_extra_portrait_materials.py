"""Reproduce additional-form HD material candidates from original ROMs and packs.

Requires NumPy, Pillow and the application's Qt dependencies. Inputs are read
only; output contains bounded native UV guides, authored PNGs and source hashes.
No Dolphin, save data or personal profile is used by this offline step.

Install the optional tool dependencies with: pip install -e ".[artwork]"
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import platform
import zlib

import PIL
from PIL import features
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from orre_randomizer.artwork import _disc_files, _png
from orre_randomizer.engine.analyze_game import parse_fsys, u32
from orre_randomizer.hd_extra_portrait_catalog import MODEL_IDENTITIES, HD_MATERIAL_SOURCE_PINS
from orre_randomizer.hd_images import load_texture, resolve_texture
from orre_randomizer.hd_overlays import _raw_member, _pkx_dat, _dat_textures, _pixels, _texture_key
from orre_randomizer.hd_packs import PACKS
from scripts.extra_portrait_materials import weather, deoxys, eye_uv, eye_analytic


ARCHIVES = {
    "face385f": "pkx_powalen_f.fsys", "face385i": "pkx_powalen_i.fsys",
    "face385w": "pkx_powalen_w.fsys", "face410atk": "pkx_deoxys_atk.fsys",
    "face410def": "pkx_deoxys_def.fsys", "face410sp": "pkx_deoxys_sp.fsys",
}


def checked_pack(path: Path, game: str) -> Path:
    root = path.resolve()
    if root.name == "Textures":
        root = root.parent
    if root.is_symlink():
        raise ValueError("Pack input cannot be a symbolic link.")
    marker = json.loads((root / "installed.json").read_text("utf8"))
    pack = PACKS[game]
    if marker.get("key") != pack.key or marker.get("archives") != [part.sha256 for part in pack.parts]:
        raise ValueError("The donor pack is not the release-pinned version: " + game)
    return root


def extract_guides(sources: dict[str, Path], packs: dict[str, Path], output: Path) -> dict:
    """Read selected FSYS members only, then verify their complete native DATs."""
    models, source_receipts = {}, []
    for game in ("colosseum", "xd"):
        with sources[game].open("rb") as stream:
            game_id = stream.read(6).decode("ascii")
        if not game_id.startswith("GC6" if game == "colosseum" else "GXX"):
            raise ValueError("Unexpected original source game: " + game)
        wanted = {archive for member, archive in ARCHIVES.items()
                  if (game == "colosseum") == member.startswith("face385")}
        if game == "xd":
            wanted |= {archive.replace(".fsys", "_c.fsys") for archive in list(wanted)}
        archives = _disc_files(sources[game], wanted, is_xd=game == "xd")
        for member, original_archive in ARCHIVES.items():
            if (game == "colosseum") != member.startswith("face385"):
                continue
            for shiny in (False, True) if game == "xd" else (False,):
                archive_name = original_archive.replace(".fsys", "_c.fsys") if shiny else original_archive
                archive = archives[archive_name]
                identity = MODEL_IDENTITIES[member][shiny]
                choices = []
                for row in parse_fsys(archive)["members"]:
                    if int(row["identifier_raw"], 16) & 0xFF00 != 0x1E00:
                        continue
                    raw = _raw_member(archive, row)
                    if hashlib.sha256(raw).hexdigest() == identity["model_sha256"]:
                        choices.append((row, raw))
                if len(choices) != 1:
                    raise ValueError("The original form model changed: " + archive_name)
                row, raw = choices[0]
                dat = _pkx_dat(raw, game == "xd")[:u32(raw, 0)]
                if hashlib.sha256(dat).hexdigest() != identity["dat_sha256"]:
                    raise ValueError("The original form DAT changed: " + archive_name)
                textures, seen_keys = [], {}
                for texture in _dat_textures(dat):
                    key = _texture_key(texture)
                    rgba = _pixels(texture)
                    rgba_sha = hashlib.sha256(rgba).hexdigest()
                    if key in seen_keys:
                        if seen_keys[key] != rgba_sha:
                            raise ValueError("Conflicting native texture interpretations: " + key)
                        continue
                    seen_keys[key] = rgba_sha
                    relative = Path("guides") / game / archive_name / key
                    path = output / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(_png((texture.width, texture.height), rgba))
                    donors = {}
                    for source_game, pins in HD_MATERIAL_SOURCE_PINS.items():
                        if key not in pins:
                            continue
                        loaded = load_texture(resolve_texture(packs[source_game] / "Textures", key),
                                              expected_native_size=(texture.width, texture.height))
                        if loaded.metadata["sha256"] != pins[key] or loaded.metadata["source_scale"] != 4:
                            raise ValueError("The actual HD donor file changed: " + key)
                        donors[source_game] = loaded.metadata
                    textures.append({"native_key": key, "dimensions": [texture.width, texture.height],
                        "png": relative.as_posix(), "rgba_sha256": rgba_sha, "hd": donors})
                if [texture["native_key"] for texture in textures] != identity["material_keys"]:
                    raise ValueError("The original form material inventory changed: " + archive_name)
                models[archive_name] = {"members": [{"name": row["name"], "textures": textures}]}
                source_receipts.append({"game_id": game_id, "archive": archive_name, "member": row["name"],
                    "model_sha256": identity["model_sha256"], "dat_sha256": identity["dat_sha256"],
                    "native_materials": len(textures), "original_source_written": False})
    (output / "original-model-sources.json").write_text(json.dumps(source_receipts, indent=2) + "\n")
    return models


def build(args) -> dict:
    if args.output.is_symlink():
        raise ValueError("Output cannot be a symbolic link.")
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Choose an empty authoring output directory; existing evidence is preserved.")
    output.mkdir(parents=True, exist_ok=True)
    sources = {"colosseum": args.colosseum_iso.resolve(), "xd": args.xd_iso.resolve()}
    packs = {"colosseum": checked_pack(args.colosseum_pack, "colosseum"), "xd": checked_pack(args.xd_pack, "xd")}
    if any(path.is_relative_to(output) or output.is_relative_to(path) for path in packs.values()):
        raise ValueError("Authoring output must be separate from the installed packs.")
    models = extract_guides(sources, packs, output)
    for module in (weather, eye_uv, eye_analytic, deoxys):
        module.configure(output, output, models, packs)
        module.main()
    materials = (json.loads((output / "weather-authored/materials.json").read_text()) +
                 json.loads((output / "deoxys-authored/materials.json").read_text()))
    seen = {}
    for material in materials:
        previous = seen.setdefault(material["target"], material["sha256"])
        if previous != material["sha256"]:
            raise ValueError("A shared native texture has conflicting authored outputs.")
    receipt = {"schema": 1, "kind": "reproducible-extra-portrait-materials", "records": len(materials),
        "environment": {"python": platform.python_version(), "pillow": PIL.__version__,
            "numpy": np.__version__, "stdlib_zlib": zlib.ZLIB_RUNTIME_VERSION,
            "uv_mask_resize_order": "explicit horizontal then vertical",
            "freetype_review_labels": features.version("freetype2"),
            "freetype_used_for_material_pixels": False},
        "unique_authored_textures": len(seen), "native_bitmap_resampled": False,
        "source_packs": {game: {"key": PACKS[game].key, "archives": [part.sha256 for part in PACKS[game].parts]}
                         for game in packs},
        "artwork_status": "requires source-qualified GPU capture and framing review before registry publication",
        "outputs": seen, "personal_profiles_or_saves_used": False}
    (output / "material-authoring-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--colosseum-iso", type=Path, required=True)
    parser.add_argument("--xd-iso", type=Path, required=True)
    parser.add_argument("--colosseum-pack", type=Path, required=True)
    parser.add_argument("--xd-pack", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    receipt = build(parser.parse_args())
    print(json.dumps({"records": receipt["records"], "unique_authored_textures": receipt["unique_authored_textures"]}))


if __name__ == "__main__":
    main()
