"""Export XD's Shadow Lugia for Colosseum from verified European revision-0 ISOs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from orre_randomizer.engine.analyze_game import parse_fsys, u32
from orre_randomizer.engine.postgame_lugia_model import ASSET, convert_xd_model
from orre_randomizer.engine.shadow_lugia_palette import (
    VERSION as PALETTE_VERSION, PORTRAIT_VERSION, make_shadow_lugia_shiny, make_shadow_lugia_portrait,
)
from orre_randomizer.engine.shadow_lugia_face import (
    make_shadow_lugia_face_texture, make_colosseum_shadow_lugia_face,
    SOURCE_RESOURCE as XD_FACE_SOURCE, SHINY_RESOURCE as XD_FACE_SHINY,
    NORMAL_RESOURCE as XD_FACE_NORMAL, COLOSSEUM_RESOURCE,
)
from orre_randomizer.engine.rebuild_iso import decoded_member
from orre_randomizer.engine.survey_assets import fst_inventory
from orre_randomizer.service import check_disc_identity, check_header
from orre_randomizer.artwork import _disc_files, _member, _png, _texture
from orre_randomizer.portrait_matte import make_shadow_lugia_ui_portrait, shadow_lugia_background_mask


def read_model(path, archive_name, model_name, *, xd=False):
    boot = check_header(path, is_xd=xd)
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
        check_disc_identity(boot, digest, is_xd=xd)
        stream.seek(u32(boot, 0x424))
        entries = fst_inventory(stream.read(u32(boot, 0x428)))[0]
        entry = next(row for row in entries if row["path"] == archive_name)
        stream.seek(entry["disc_offset"])
        archive = stream.read(entry["size"])
    member = next(row for row in parse_fsys(archive)["members"] if row["name"] == model_name)
    model = decoded_member(archive, member)
    return model, {"game_id": boot[:6].decode("ascii"), "revision": boot[7],
                   "iso_sha256": digest, "archive": archive_name, "member": model_name,
                   "model_sha256": hashlib.sha256(model).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--colosseum", type=Path, required=True)
    parser.add_argument("--xd", type=Path, required=True)
    args = parser.parse_args()
    colo, template = read_model(args.colosseum, "pkx_lugia.fsys", "lugia")
    xd, source = read_model(args.xd, "pkx_darklugia.fsys", "darklugia", xd=True)
    if (template["game_id"], source["game_id"]) != ("GC6P01", "GXXP01"):
        raise SystemExit("This export requires the verified European revision-0 discs.")
    converted = convert_xd_model(xd, colo)
    pack = ROOT / "orre_randomizer/assets/game"
    target = pack / ASSET
    target.parent.mkdir(exist_ok=True)
    target.write_bytes(converted)
    faces = _disc_files(args.xd, {"poke_face.fsys"}, is_xd=True)["poke_face.fsys"]
    face = _member(faces, parse_fsys(faces)["members"], "face249dark")
    portrait = target.parent / "dark-lugia.png"
    face_pixels = _texture(face, (42, 84))[:42 * 42 * 4]
    portrait.write_bytes(_png((42, 42), face_pixels))
    shiny_portrait = target.parent / "dark-lugia-shiny.png"
    shiny_pixels = make_shadow_lugia_portrait(face_pixels)
    shiny_portrait.write_bytes(_png((42, 42), shiny_pixels))
    ui_portrait = target.parent / "dark-lugia-ui.png"
    ui_shiny_portrait = target.parent / "dark-lugia-shiny-ui.png"
    ui_portrait.write_bytes(_png((42, 42), make_shadow_lugia_ui_portrait(face_pixels, reference=face_pixels)))
    ui_shiny_portrait.write_bytes(_png((42, 42), make_shadow_lugia_ui_portrait(shiny_pixels, reference=face_pixels)))
    manifest = {"version": 1, "source": source, "container_template": template,
                "conversion": "Reorder the PKX container; convert float seconds to 60-Hz integer ticks, map XD clip/wait track kinds to Colosseum and use the native scheduling flags. Retain the original HSD mesh, textures, skeleton bindings and DAT animation tracks.",
                "rights": "Original game resource; not covered by the code's MIT license. See THIRD_PARTY_NOTICES.md.",
                "converted_bytes": len(converted), "converted_sha256": hashlib.sha256(converted).hexdigest()}
    manifest["portrait"] = {"archive": "poke_face.fsys", "member": "face249dark",
                            "decoded_sha256": hashlib.sha256(face).hexdigest(), "frame": "upper-left 42x42"}
    shiny = make_shadow_lugia_shiny(converted, xd=False)
    manifest["shiny_variant"] = {"version": PALETTE_VERSION,
        "description": "Swap the native body/belly material lighting colors and shade only the belly's grayscale CMPR map: white body, dark belly, original red eyes. Mesh, other textures, skeleton, animations and alpha are unchanged.",
        "generated_bytes": len(shiny), "generated_sha256": hashlib.sha256(shiny).hexdigest(),
        "portrait": "dark-lugia-shiny.png", "portrait_sha256": hashlib.sha256(shiny_portrait.read_bytes()).hexdigest()}
    manifest["shiny_variant"]["portrait_version"] = PORTRAIT_VERSION
    manifest["shiny_variant"]["portrait_conversion"] = "Native blue-gray head, navy neck and lower jaw become white; the native pale triangle around the red iris becomes charcoal, following their 42px source masks. Teeth, mouth, red iris, violet backdrop gaps, black contours and alpha retained."
    native_white = make_shadow_lugia_face_texture(face)
    native_normal = make_shadow_lugia_face_texture(face, shiny=False)
    colo_faces = _disc_files(args.colosseum, {"poke_face.fsys"})["poke_face.fsys"]
    colo_face = _member(colo_faces, parse_fsys(colo_faces)["members"], "face249")
    colo_atlas = make_colosseum_shadow_lugia_face(colo_face,
        make_shadow_lugia_ui_portrait(face_pixels, reference=face_pixels),
        make_shadow_lugia_ui_portrait(shiny_pixels, reference=face_pixels))
    manifest["native_faces"] = {
        "xd": {"source_resource": XD_FACE_SOURCE, "normal_resource": XD_FACE_NORMAL, "shiny_resource": XD_FACE_SHINY,
               "format": "native CI8/RGB5A3; original circular alpha, black interior, complete 36px artwork centered with 3px padding",
               "artwork_size": 36, "padding": 3, "native_alpha_preserved": True,
               "normal_generated_sha256": hashlib.sha256(native_normal).hexdigest(),
               "generated_sha256": hashlib.sha256(native_white).hexdigest()},
        "colosseum": {"template": "poke_face.fsys/face249", "resource": COLOSSEUM_RESOURCE,
                      "template_sha256": hashlib.sha256(colo_face).hexdigest(),
                      "format": "native tiled RGBA8; opaque-black normal Dark and white frames",
                      "generated_sha256": hashlib.sha256(colo_atlas).hexdigest()}}
    manifest["ui_portraits"] = {
        "normal": ui_portrait.name, "normal_sha256": hashlib.sha256(ui_portrait.read_bytes()).hexdigest(),
        "shiny": ui_shiny_portrait.name, "shiny_sha256": hashlib.sha256(ui_shiny_portrait.read_bytes()).hexdigest(),
        "mask": "Transparent/violet backdrop, eight-connected to the original 42px tile boundary; opaque-black matte shared by interface and native faces",
        "masked_pixels": len(shadow_lugia_background_mask(face_pixels)),
        "source_portraits_unchanged": True, "shared_with_native_faces": True}
    (target.parent / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", "utf-8", newline="\n")
    provenance = pack / "provenance.json"
    catalog = json.loads(provenance.read_text("utf-8"))
    for path in (target, portrait, shiny_portrait, ui_portrait, ui_shiny_portrait, target.parent / "manifest.json", pack / "README.md"):
        payload = path.read_bytes()
        catalog["files"][path.relative_to(pack).as_posix()] = {
            "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
    catalog["bonus_model_metadata"] = "models/manifest.json"
    provenance.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", "utf-8", newline="\n")
    print(json.dumps({"asset": ASSET, "bytes": len(converted), "sha256": manifest["converted_sha256"]}))


if __name__ == "__main__":
    main()
