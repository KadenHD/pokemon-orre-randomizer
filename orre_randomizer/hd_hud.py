"""Localized XD HUD from a genuine pack atlas and the author's vector typography.

Derivative vector artwork: mikeyX, Pokemon XD UI SVGs V1.0, CC BY-NC-SA 4.0.
The included author license explicitly permits derivatives in Pokemon mods
without applying that license to the whole mod; NonCommercial still applies.
No native raster pixels are enlarged. The original ROM and packs are read-only.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPainterPathStroker, QTransform

SOURCE_KEY = "tex1_258x20_2c16611b797dc876_c4d3c43fe0ceb42a_9.png"
SOURCE_SHA256 = "ae9f02fa2b22dd810e3bbdbd3d3558b1adde346d623742ec10dfd0d9d77a56b5"
VECTOR_SOURCE = {
    "author": "mikeyX", "version": "1.0",
    "url": "https://mega.nz/file/gB4GBSSJ#vj7DVhNCdm_MzSLu5KCn3ZdTsPH6wffX0cMolCPfFhY",
    "archive_sha256": "c575a04cb5044a41df620e92557cd6bd5d72fb9c3ad4e726dacf972def262616",
    "member": "Pokemon XD UI SVGs V1.0/svg/" + SOURCE_KEY[:-4] + ".svg",
    "member_sha256": "03867cd71feeca8a1eae99a73f8a96c870b74ac96cb88b1dc063e0fe848e854c",
    "license": "CC BY-NC-SA 4.0; author Pokemon-mod exception in original license.txt",
    "typography": "Bahnschrift outlines, matching the original SVG's text family",
    "font_sha256": "eaad201da94cb323401fdb8cc760650803ddf8fd704cb9fa56317e6c69bc6fd6",
}
# Captured outlines avoid a platform font dependency. Coordinates are in the
# original SVG font's design space, not a trace of a native texture.
_GLYPHS = json.loads("{\"H\":{\"advance\":790,\"path\":[[\"M\",491.21875,0],[\"L\",491.21875,-709.96875],[\"L\",590.82812,-709.96875],[\"L\",590.82812,0],[\"L\",491.21875,0],[\"M\",87.89062,0],[\"L\",87.89062,-709.96875],[\"L\",187.5,-709.96875],[\"L\",187.5,0],[\"L\",87.89062,0],[\"M\",149.90625,-302.25],[\"L\",149.90625,-396.96875],[\"L\",543.95312,-396.96875],[\"L\",543.95312,-302.25],[\"L\",149.90625,-302.25]]},\"P\":{\"advance\":734,\"path\":[[\"M\",139.15625,-275.39062],[\"L\",139.15625,-370.125],[\"L\",366.21875,-370.125],[\"C\",398.77083,-370.125,424.89323,-381.35417,444.58594,-403.8125],[\"C\",464.27865,-426.27083,474.125,-455.72917,474.125,-492.1875],[\"C\",474.125,-529.30208,464.27865,-559.08854,444.58594,-581.54688],[\"C\",424.89323,-604.00521,398.77083,-615.23438,366.21875,-615.23438],[\"L\",139.15625,-615.23438],[\"L\",139.15625,-709.96875],[\"L\",362.79688,-709.96875],[\"C\",405.76562,-709.96875,443.20052,-700.9349,475.10156,-682.86719],[\"C\",507.0026,-664.79948,531.82292,-639.48958,549.5625,-606.9375],[\"C\",567.30208,-574.38542,576.17188,-536.13542,576.17188,-492.1875],[\"C\",576.17188,-448.57292,567.30208,-410.48958,549.5625,-377.9375],[\"C\",531.82292,-345.38542,507.0026,-320.15625,475.10156,-302.25],[\"C\",443.20052,-284.34375,405.76562,-275.39062,362.79688,-275.39062],[\"L\",139.15625,-275.39062],[\"M\",87.89062,0],[\"L\",87.89062,-709.96875],[\"L\",187.5,-709.96875],[\"L\",187.5,0],[\"L\",87.89062,0]]},\"V\":{\"advance\":698,\"path\":[[\"M\",246.09375,0],[\"L\",14.65625,-709.96875],[\"L\",123.04688,-709.96875],[\"L\",293.45312,-153.32812],[\"L\",463.875,-709.96875],[\"L\",572.26562,-709.96875],[\"L\",340.82812,0],[\"L\",246.09375,0]]},\"K\":{\"advance\":753,\"path\":[[\"M\",151.375,-162.10938],[\"L\",166.01562,-311.53125],[\"L\",479.5,-709.96875],[\"L\",602.04688,-709.96875],[\"L\",151.375,-162.10938],[\"M\",87.89062,0],[\"L\",87.89062,-709.96875],[\"L\",187.5,-709.96875],[\"L\",187.5,0],[\"L\",87.89062,0],[\"M\",509.76562,0],[\"L\",284.1875,-378.90625],[\"L\",362.79688,-451.65625],[\"L\",631.84375,0],[\"L\",509.76562,0]]},\"S\":{\"advance\":727,\"path\":[[\"M\",301.26562,7.32812],[\"C\",266.76562,7.32812,234.29688,4.07292,203.85938,-2.4375],[\"C\",173.42188,-8.94792,144.9375,-18.71354,118.40625,-31.73438],[\"C\",91.875,-44.75521,67.05729,-61.03125,43.95312,-80.5625],[\"L\",105.95312,-156.73438],[\"C\",132.97396,-133.29688,162.76042,-115.71875,195.3125,-104],[\"C\",227.86458,-92.28125,263.18229,-86.42188,301.26562,-86.42188],[\"C\",352.70312,-86.42188,392.58073,-96.02604,420.89844,-115.23438],[\"C\",449.21615,-134.44271,463.375,-161.29688,463.375,-195.79688],[\"L\",463.375,-196.29688],[\"C\",463.375,-223.30729,456.21354,-243.97396,441.89062,-258.29688],[\"C\",427.56771,-272.61979,408.77083,-283.28125,385.5,-290.28125],[\"C\",362.22917,-297.28125,336.75521,-303.0625,309.07812,-307.625],[\"C\",282.39062,-312.17708,255.45573,-317.54688,228.27344,-323.73438],[\"C\",201.09115,-329.92188,176.10677,-339.60677,153.32031,-352.78906],[\"C\",130.53385,-365.97135,112.22396,-384.93229,98.39062,-409.67188],[\"C\",84.55729,-434.41146,77.64062,-467.45312,77.64062,-508.79688],[\"L\",77.64062,-509.28125],[\"C\",77.64062,-575.36458,99.61198,-626.55208,143.55469,-662.84375],[\"C\",187.4974,-699.13542,249.51042,-717.28125,329.59375,-717.28125],[\"C\",367.67708,-717.28125,404.94792,-711.17969,441.40625,-698.97656],[\"C\",477.86458,-686.77344,513.34896,-668.13542,547.85938,-643.0625],[\"L\",491.21875,-563.96875],[\"C\",464.19792,-584.14583,437.26042,-599.11719,410.40625,-608.88281],[\"C\",383.55208,-618.64844,356.61458,-623.53125,329.59375,-623.53125],[\"C\",281.09375,-623.53125,243.41406,-613.84896,216.55469,-594.48438],[\"C\",189.69531,-575.11979,176.26562,-547.69271,176.26562,-512.20312],[\"L\",176.26562,-511.71875],[\"C\",176.26562,-485.03125,184.07812,-464.6875,199.70312,-450.6875],[\"C\",215.32812,-436.6875,235.75521,-426.35156,260.98438,-419.67969],[\"C\",286.21354,-413.00781,313.3125,-406.73958,342.28125,-400.875],[\"C\",368.32292,-395.66667,394.36458,-389.40104,420.40625,-382.07812],[\"C\",446.44792,-374.75521,470.13021,-364.17708,491.45312,-350.34375],[\"C\",512.77604,-336.51042,529.86719,-317.54948,542.72656,-293.46094],[\"C\",555.58594,-269.3724,562.01562,-237.95833,562.01562,-199.21875],[\"L\",562.01562,-198.25],[\"C\",562.01562,-132.8125,539.22917,-82.1901,493.65625,-46.38281],[\"C\",448.08333,-10.57552,383.95312,7.32812,301.26562,7.32812]]},\"N\":{\"advance\":811,\"path\":[[\"M\",87.89062,-0.48438],[\"L\",87.89062,-709.96875],[\"L\",178.21875,-709.96875],[\"L\",525.39062,-161.14062],[\"L\",513.67188,-148.4375],[\"L\",513.67188,-709.96875],[\"L\",612.3125,-709.96875],[\"L\",612.3125,-0.48438],[\"L\",521,-0.48438],[\"L\",174.8125,-541.01562],[\"L\",186.53125,-553.71875],[\"L\",186.53125,-0.48438],[\"L\",87.89062,-0.48438]]},\"L\":{\"advance\":684,\"path\":[[\"M\",87.89062,0],[\"L\",87.89062,-709.96875],[\"L\",187.5,-709.96875],[\"L\",187.5,0],[\"L\",87.89062,0],[\"M\",137.70312,0],[\"L\",137.70312,-94.73438],[\"L\",543.95312,-94.73438],[\"L\",543.95312,0],[\"L\",137.70312,0]]},\"v\":{\"advance\":611,\"path\":[[\"M\",252.4375,-145.01562],[\"L\",376.46875,-506.84375],[\"L\",480.46875,-506.84375],[\"L\",290.04688,0],[\"L\",214.84375,0],[\"L\",24.42188,-506.84375],[\"L\",128.42188,-506.84375],[\"L\",252.4375,-145.01562]]},\".\":{\"advance\":338,\"path\":[[\"M\",61.03125,0],[\"L\",61.03125,-104.5],[\"L\",165.53125,-104.5],[\"L\",165.53125,0],[\"L\",61.03125,0]]}}")
_CATALOG = json.loads("{\"tex1_258x20_1de555d12d3658d5_c4d3c43fe0ceb42a_9.png\":{\"language\":\"en\",\"labels\":[\"HP\",\"Lv.\"],\"label_bounds\":[[6,4,24,12],[225,2,20,14]],\"native_sha256\":\"814bb14cd79daa8dc85bad312abe441f44f2e8f4fbe3651c3cdda0496db09323\",\"native_rgba_sha256\":\"8e472bc05d8bdc7db47c974d880252d8dcb916ff2ed0e2530564f531e79e7a42\",\"identifier\":\"0x17171200\"},\"tex1_258x20_0f24338507dc4276_223f8305fab2b998_9.png\":{\"language\":\"fr\",\"labels\":[\"PV\",\"N.\"],\"label_bounds\":[[6,4,24,12],[230,3,17,13]],\"native_sha256\":\"39117158b055e27dc316684fcbdecc90dfe71e936c158a7be2ebb6a6c0ebd3d7\",\"native_rgba_sha256\":\"890d8e0e1d626d54497b178fdf9d2f6ff20c24bba40099bffb3f2279d82929dd\",\"identifier\":\"0x24d21200\"},\"tex1_258x20_8046049068ae1493_8867942afe3299c0_9.png\":{\"language\":\"de\",\"labels\":[\"KP\",\"Lv.\"],\"label_bounds\":[[6,4,24,12],[225,2,21,14]],\"native_sha256\":\"03f8c9486d06f1f6f4b68f7aaee96ccb91c8fbf925466cbe8c30bcc726439195\",\"native_rgba_sha256\":\"69009541ac4bdf13904639e8e0c40e35d4b3143442383f43caa0a09f1b562ee3\",\"identifier\":\"0x24ce1200\"},\"tex1_258x20_f5296a8e04d11ce6_66100a099094e6f0_9.png\":{\"language\":\"it\",\"labels\":[\"PS\",\"L.\"],\"label_bounds\":[[7,4,22,12],[231,2,15,14]],\"native_sha256\":\"b2c302874af01b74bee4fe2f6d18be28645eebd11e17aec34f9f871e665e8af6\",\"native_rgba_sha256\":\"e7320e5a6b7328d161734909b16c74c8c3254bfcae8dee3013b7f6339f7a1c86\",\"identifier\":\"0x24d61200\"},\"tex1_258x20_4a95a650fb7bec51_f99141ce44cf6b84_9.png\":{\"language\":\"es\",\"labels\":[\"PS\",\"Nv.\"],\"label_bounds\":[[7,4,22,12],[223,3,24,13]],\"native_sha256\":\"f4ce963595fa966a796a5216ab56a898f3d5e265f065a4c6ef510007d958f44e\",\"native_rgba_sha256\":\"516a681c7d16c9c28cccb118934052e336145e8327969f3d88b5af5f5e9ec4b3\",\"identifier\":\"0x24da1200\"}}")
_SUPPORTED = {"GC6P01", "GC6E01", "GC6J01", "GXXP01", "GXXE01", "GXXJ01"}
_ERASE_RECTS = ((3, 1, 29, 18), (220, 0, 28, 20))
_REFORMATS = json.loads("{\"tex1_126x207_ea953772b7d9a77e_6.png\":{\"game\":\"colosseum\",\"file\":\"tex1_126x207_fcb6fd14f73268b9_5.png\",\"source_native_dimensions\":[126,207],\"source_sha256\":\"ee8c7321de02ea5b40bf5f8887dbf732cd1df4ebdec3e18814d3799fe839cc90\",\"native_source\":\"GC6J01/field_common.fsys/menu_040\",\"transform\":{\"type\":\"hud_exact_reformat\",\"version\":1,\"target\":\"tex1_126x207_ea953772b7d9a77e_6.png\",\"native_sha256\":\"0cb3081352747560a46eb32d872c96745c35132ce86fdc95cc8df317a3fb1bd2\",\"native_rgba_sha256\":\"7b4f06f5646705a94e6f51dfb502dccd892d193a77e34f8e2e4c342927e76d1b\",\"donor_native_sha256\":\"2ba34bc70e9ed8f965836bff60b5c96e7d1ccf3b57c3b3473584eac1013bbc88\",\"proof\":{\"source_key\":\"tex1_126x207_ea953772b7d9a77e_6.png\",\"quantized_key\":\"tex1_126x207_fcb6fd14f73268b9_5.png\",\"encoder\":\"RGB5A3\",\"opaque_threshold\":224,\"rounding\":\"floor\",\"rgba_exact_after_conversion\":true,\"rgba_sha256\":\"b29712dc0441343c19e01b181de92afe00251503859478fb719266753208739c\"}}},\"tex1_530x318_5f1abbef2b1582bf_6.png\":{\"game\":\"colosseum\",\"file\":\"tex1_530x318_56048c58b0dcc418_5.png\",\"source_native_dimensions\":[530,318],\"source_sha256\":\"65316723aa9070b532ff41288077b65d37115cb0e70af17e80f4dd65697ee739\",\"native_source\":\"GC6J01/waza_menu.fsys/menu_024\",\"transform\":{\"type\":\"hud_exact_reformat\",\"version\":1,\"target\":\"tex1_530x318_5f1abbef2b1582bf_6.png\",\"native_sha256\":\"f91967a51453220210f50e4e4925254eb7f91fc1e4306e087c2040f48f823374\",\"native_rgba_sha256\":\"929b0d8c0d0c54edb59426f3ce9cd6961cba76c061cf41143f0390f0d1d7b00f\",\"donor_native_sha256\":\"3a176a5d1ae4448f260a7a11cecd63f19d78387f2a6810a1988b17bf9885cc41\",\"proof\":{\"source_key\":\"tex1_530x318_5f1abbef2b1582bf_6.png\",\"quantized_key\":\"tex1_530x318_56048c58b0dcc418_5.png\",\"encoder\":\"RGB5A3\",\"opaque_threshold\":224,\"rounding\":\"floor\",\"rgba_exact_after_conversion\":true,\"rgba_sha256\":\"b67cacd542f5adcb51891f264f8d9459f39b74ddfeab50a753e54dd82a1301ff\"}}}}")


def hud_recipes(game_id: str) -> dict[str, dict]:
    """Return verified native identities for status, format and menu additions."""
    from .hd_menu_catalog import menu_recipes
    if game_id not in _SUPPORTED:
        raise ValueError("Unknown HUD game identity")
    if game_id == "GC6J01":
        result = deepcopy(_REFORMATS)
    elif game_id != "GXXP01":
        result = {}
    else:
        result = {key: {"game": "xd", "file": SOURCE_KEY,
            "source_native_dimensions": [258, 20], "source_sha256": SOURCE_SHA256,
            "native_source": "verified original XD PAL localized 258x20 status atlas",
            "transform": {"type": "xd_localized_status", "version": 1,
                "target": key, **deepcopy(record)}} for key, record in _CATALOG.items()}
    additions = menu_recipes(game_id)
    for key in set(result) & set(additions):
        previous, reviewed = result[key], additions[key]
        native = reviewed["transform"].get("native_guide", {})
        source = reviewed["transform"].get("author_source", {})
        # The reviewed PC captions supersede the original five PAL status
        # adapters only for the same independently verified native identities.
        if (previous["transform"]["type"] != "xd_localized_status"
                or reviewed["transform"].get("family") != "xd-pc-hp"
                or reviewed.get("file") is not None or not reviewed.get("bundled_donor")
                or reviewed["source_native_dimensions"] != previous["source_native_dimensions"]
                or native.get("member_sha256") != previous["transform"]["native_sha256"]
                or native.get("rgba_sha256") != previous["transform"]["native_rgba_sha256"]
                or source.get("source_file") != previous["file"]
                or source.get("source_sha256") != previous["source_sha256"]):
            raise ValueError("Menu additions collide with an existing HUD recipe")
    return dict(result, **additions)


def hud_origin(game_id: str, native_key: str, native_size: tuple[int, int]) -> dict | None:
    """Recognize exact native keys, never relabel an unknown changed texture."""
    recipe = hud_recipes(game_id).get(native_key)
    native_dimensions = None
    if recipe is not None:
        native_dimensions = recipe.get("transform", {}).get("native_dimensions")
        if native_dimensions is None:
            native_dimensions = recipe["source_native_dimensions"]
    if recipe is not None and tuple(native_size) != tuple(native_dimensions):
        raise ValueError("Unexpected localized HUD dimensions")
    return recipe


def _word_path(text: str) -> QPainterPath:
    path = QPainterPath()
    cursor = 0.0
    for char in text:
        glyph = _GLYPHS[char]
        part = QPainterPath()
        for command in glyph["path"]:
            kind, *values = command
            if kind == "M":
                part.moveTo(*values)
            elif kind == "L":
                part.lineTo(*values)
            else:
                part.cubicTo(*values)
        path.addPath(QTransform.fromTranslate(cursor, 0).map(part))
        cursor += glyph["advance"]
    return path


def render_hud(image: QImage, transform: dict, *, source_metadata: dict):
    """Localize only HP/level vector labels; preserve all other donor pixels."""
    if transform.get("type", "").startswith("menu_atlas_"):
        from .hd_menu_atlases import render_menu_atlas
        return render_menu_atlas(image, transform, source_metadata=source_metadata)
    target = transform.get("target")
    expected = {**hud_recipes("GXXP01"), **hud_recipes("GC6J01")}.get(target)
    if expected is None or transform != expected["transform"]:
        raise ValueError("Unknown or altered HUD recipe")
    if (source_metadata.get("sha256") != expected["source_sha256"]
            or source_metadata.get("source_scale") != 4
            or (image.width(), image.height()) != tuple(v * 4 for v in expected["source_native_dimensions"])):
        raise ValueError("HUD requires its exact genuine x4 pack donor")
    if transform["type"] == "hud_exact_reformat":
        return image.copy(), {"type": "exact_native_reformat", "version": 1,
            "source": deepcopy(source_metadata), "proof": deepcopy(transform["proof"]),
            "native_source": expected["native_source"],
            "native_raster_used_for_HD_art": False, "runtime_validated": False}
    source = image.convertToFormat(QImage.Format.Format_RGBA8888)
    pixels = bytearray(source.constBits())
    # Remove the donor's English labels. Keep the base alpha for the black
    # HP panel, including its antialiased corners. The level has no panel.
    for index, (left, top, width, height) in enumerate(_ERASE_RECTS):
        for y in range(top * 4, (top + height) * 4):
            for x in range(left * 4, (left + width) * 4):
                at = (y * 1032 + x) * 4
                pixels[at:at + (3 if index == 0 else 4)] = bytes(3 if index == 0 else 4)
    output = QImage(bytes(pixels), 1032, 80, 1032 * 4, QImage.Format.Format_RGBA8888).copy()
    painter = QPainter(output)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        for index, (label, rect) in enumerate(zip(transform["labels"], transform["label_bounds"], strict=True)):
            path = _word_path(label)
            stroke = QPainterPathStroker()
            stroke.setWidth(81.317 if index == 0 else 81.026)
            stroke.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
            stroke.setMiterLimit(4)
            silhouette = path.united(stroke.createStroke(path))
            box = silhouette.boundingRect()
            x, y, width, height = rect
            fit = QTransform()
            fit.translate(x * 4, y * 4)
            fit.scale(width * 4 / box.width(), height * 4 / box.height())
            fit.translate(-box.x(), -box.y())
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#ff3601" if index == 0 else "#ffffff"))
            painter.drawPath(fit.map(silhouette))
    finally:
        painter.end()
    return output, {
        "type": "author_vector_localization", "version": 1,
        "language": transform["language"], "labels": deepcopy(transform["labels"]),
        "source_pack": "xd-1.0", "source": deepcopy(source_metadata),
        "vector_source": deepcopy(VECTOR_SOURCE),
        "native_layout": {"target": target, "dimensions": [258, 20],
            "member_sha256": transform["native_sha256"],
            "native_rgba_sha256": transform["native_rgba_sha256"],
            "label_bounds": deepcopy(transform["label_bounds"])},
        "native_raster_used_for_HD_art": False,
        "unchanged_donor_pixels": "all pixels outside the two recorded label rectangles",
        "runtime_validated": False,
    }


def prepare_hud_overlays(game_id: str, pack_roots: dict, destination: Path) -> dict:
    """Generate a bounded overlay addition without overwriting another epoch."""
    from .hd_images import load_texture, resolve_texture
    recipes = hud_recipes(game_id)
    report = {"version": 3, "game_id": game_id, "assets": [], "files": {},
              "required_packs": sorted({r["game"] for r in recipes.values() if r.get("file")}),
              "runtime_validated": False,
              "scope": "reviewed menu/HUD vectors, pinned HD derivatives and exact native format equivalents"}
    if not recipes:
        return report
    packs = {game: Path(pack_roots[game]).resolve() for game in report["required_packs"]}
    destination = Path(destination)
    if destination.is_symlink():
        raise ValueError("HUD overlay destination cannot be a symbolic link")
    destination = destination.resolve()
    if any(destination == pack or pack in destination.parents for pack in packs.values()):
        raise ValueError("HUD overlays cannot write inside a source pack")
    generated, sources = [], {}
    for key, recipe in recipes.items():
        if recipe.get("bundled_donor"):
            from .hd_menu_catalog import menu_image
            cache_key = "bundled", recipe["bundled_donor"]
            if cache_key not in sources:
                sources[cache_key] = menu_image(recipe["bundled_donor"], tuple(recipe["source_native_dimensions"]))
            source = sources[cache_key]
            image, metadata = render_hud(source.image, recipe["transform"], source_metadata=source.metadata)
        elif recipe.get("file") is None:
            image, metadata = render_hud(QImage(), recipe["transform"],
                                        source_metadata={"kind": "authored-vector-artwork"})
        else:
            cache_key = recipe["game"], recipe["file"]
            if cache_key not in sources:
                pack = packs[recipe["game"]]
                root = pack / "Textures" if (pack / "Textures").is_dir() else pack
                sources[cache_key] = load_texture(resolve_texture(root, recipe["file"]),
                    expected_native_size=tuple(recipe["source_native_dimensions"]))
            source = sources[cache_key]
            image, metadata = render_hud(source.image, recipe["transform"], source_metadata=source.metadata)
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        if not image.save(buffer, "PNG"):
            raise ValueError("Cannot encode localized HUD")
        payload = bytes(buffer.data())
        path = destination / key
        if path.is_symlink() or (path.exists() and path.read_bytes() != payload):
            raise ValueError("Conflicting existing HUD overlay")
        generated.append((path, payload))
        sha = hashlib.sha256(payload).hexdigest()
        report["files"][key] = sha
        report["assets"].append({"file": key, "sha256": sha, "role": "localized_hud",
                                 "origin": recipe, "components": metadata})
    destination.mkdir(parents=True, exist_ok=True)
    for path, payload in generated:
        if not path.exists():
            with path.open("xb") as output:
                output.write(payload)
    return report
