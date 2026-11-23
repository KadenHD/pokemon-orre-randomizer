"""Verified native-form portrait identities and registered mesh-rendered HD atlases.

This catalogue does not change native portraits or substitute ordinary forms.
The renderer accepts reviewed captures only; absent captures remain unavailable.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from collections.abc import Mapping

from .hd_extra_portrait_catalog import MODEL_IDENTITIES, HD_MATERIAL_SOURCE_PINS


_ROWS = """
colosseum face385f tex1_42x84_ac0864273261e561_6.png fc701feb7bd848fa68402a419a09502749fa20b668984440027b7bfab5051bb0
colosseum face385i tex1_42x84_69738576843938c5_6.png 9879a36d8de2344e716b82394c8b305ea30bc77bcc9991a4b80581f22ebe56f9
colosseum face385w tex1_42x84_81b9ef93cb9585d4_6.png fbe4eaa440ba8b0902227ec7d905b0e7adaa4e392cf4f6ea335f1aafe156fc94
xd face385f tex1_42x84_f9569de6ef136597_03eb1bd4be1c7367_9.png 13803301d126291d5736d66140334660cb18c611942583fe81b91f293b174f22
xd face385i tex1_42x84_07c2186faf6dd57a_d8594b824fbcc207_9.png 2d1264061949ab0ca074b5bfc8f321be4f11afb1526df7f5b3671e56701094cc
xd face385w tex1_42x84_504bce8c83335d51_0c05b30166eebe35_9.png 47d9b811adda33da29a6c143e7bfa9e96232e5d7543aad5ffeb22e58658ddd6a
xd face410atk tex1_42x84_edddd8fac1d1c913_d1d2ffb2ac470c26_9.png 94e2b26e06de9cb37ce42ca6b417caeda046dc453d923818f3a7f8667155f380
xd face410def tex1_42x84_abd232af8de977f4_822a8f9d6151c906_9.png b92fc4bbc277a13e89cd3188b1ca60d8bba59c5ecefff19a21eeaa77e98e1238
xd face410sp tex1_42x84_a744aee7101e126a_ee5d9a18ff8c9057_9.png db880bf599027b3024fef67a58c5ca74be3bb7153387f5f373aeaa971973473f
"""
_CATALOG = {(game, key): (member, rgba) for game, member, key, rgba in
            (row.split() for row in _ROWS.splitlines() if row.strip())}
_KIND = "native-form-mesh-render-portrait"
_SHA = re.compile(r"[0-9a-f]{64}\Z")


def _game(value: str) -> str:
    if value in ("colosseum", "xd"):
        return value
    if re.fullmatch(r"GC6[A-Z0-9]{3}", value):
        return "colosseum"
    if re.fullmatch(r"GXX[A-Z0-9]{3}", value):
        return "xd"
    raise ValueError("Unknown game for the additional portrait catalogue.")


def portrait_origin(game: str, native_key: str, native_size: tuple[int, int]) -> dict | None:
    """Recognize an exact native atlas, including Dolphin's mipmap-name alias."""
    game = _game(game)
    key = re.sub(r"^(tex1_\d+x\d+)_m_", r"\1_", native_key)
    identity = _CATALOG.get((game, key))
    if identity is None:
        return None
    if tuple(native_size) != (42, 84):
        raise ValueError("The verified additional portrait has changed dimensions.")
    member, rgba_sha256 = identity
    source_game = "colosseum" if member.startswith("face385") else "xd"
    return {"game": source_game, "required_packs": [source_game],
            "native_source": "verified " + game + " poke_face.fsys/" + member,
            "transform": {"type": "captured-extra-portrait", "version": 1,
                "game": game, "member": member, "native_key": key,
                "native_size": [42, 84], "native_rgba_sha256": rgba_sha256,
                "output_scale": 4}}


def portrait_coverage_report() -> dict:
    """Distinguish registered portrait captures from stock model-texture coverage."""
    return {"texture_atlases": 9, "weather_atlases_per_game": 3, "xd_deoxys_forms": 3,
            "registered": extra_portraits_registered(), "scope": "portrait atlases only",
            "stock_3d_materials_installed": False,
            "stock_3d_materials_catalogued_separately": True,
            "normal_and_shiny": True, "native_rom_changed": False,
            "castform_weather_shiny": "legacy native-source atlases share weather colours; modern shiny variants use separate registered resources",
            "publication_policy": "reviewed native-mesh captures with complete HD material provenance"}


def is_extra_portrait_member(name: str, game: str) -> bool:
    return any(g == _game(game) and member == name for (g, _), (member, _) in _CATALOG.items())


def extra_portraits_registered(asset_directory: Path | None = None) -> bool:
    """Enable the new capture route only after the complete registry is reviewed.

    File integrity and capture provenance are checked again by the renderer.
    Until the nine atlases are delivered, historical retail fallback is retained.
    """
    from .resources import bundle_root
    directory = Path(asset_directory) if asset_directory is not None else bundle_root() / "models/extra-portraits"
    path = directory / "extra-portraits.json"
    if not path.is_file() or path.is_symlink():
        return False
    try:
        manifest = json.loads(path.read_text("utf8"))
        targets = {game + "/" + member for (game, _), (member, _) in _CATALOG.items()}
        return (manifest.get("schema") == 1 and manifest.get("kind") == _KIND and
                manifest.get("review_only") is False and targets <= manifest.get("files", {}).keys())
    except (OSError, ValueError, AttributeError, TypeError):
        return False


def _checked_sha(value, what: str) -> str:
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise ValueError("Invalid " + what + " SHA-256.")
    return value


def _capture(manifest: Mapping, capture_id: str, *, source_game: str, member: str, shiny: bool) -> Mapping:
    from .hd_packs import PACKS
    capture = manifest.get("captures", {}).get(capture_id)
    if not isinstance(capture, Mapping):
        raise ValueError("Missing additional portrait capture receipt.")
    for field in ("sha256", "pose_signature_sha256", "model_sha256", "dat_sha256"):
        _checked_sha(capture.get(field), field)
    camera = capture.get("camera")
    if (not isinstance(camera, Mapping) or not camera.get("method") or
            camera.get("render_target") != [256, 256] or
            type(camera.get("cobj_readback_captured")) is not bool):
        raise ValueError("Missing or invalid declared portrait camera recipe.")
    if (capture.get("source_dimensions") != [1024, 1024] or
            not isinstance(capture.get("matrix_count"), int) or capture["matrix_count"] <= 0 or
            capture.get("native_bitmap_upscaled_for_hd") is not False):
        raise ValueError("The additional portrait requires an actual GPU4x mesh render.")
    recipes, required = capture.get("material_recipes"), capture.get("material_keys")
    model = MODEL_IDENTITIES[member][shiny]
    if (capture.get("model_sha256") != model["model_sha256"] or
            capture.get("dat_sha256") != model["dat_sha256"] or
            capture.get("matrix_count") != model["matrix_count"] or required != model["material_keys"]):
        raise ValueError("The additional portrait does not render its verified native form.")
    if (not isinstance(recipes, list) or not isinstance(required, list) or not required or
            len(set(required)) != len(required) or
            {row.get("target") for row in recipes} != set(required) or len(recipes) != len(required)):
        raise ValueError("The additional portrait has incomplete HD material coverage.")
    pack = PACKS[source_game]
    if (capture.get("pack") != pack.key or
            capture.get("archives") != [part.sha256 for part in pack.parts]):
        raise ValueError("The additional portrait uses an unrecognized HD pack.")
    for recipe in recipes:
        reference = recipe.get("reference", {})
        if (recipe.get("kind") not in ("exact-pack-material", "authored-pack-derived-material") or
                recipe.get("native_bitmap_resampled") is not False or
                reference.get("source_scale") not in (4, 8, 16)):
            raise ValueError("A portrait material lacks genuine HD provenance.")
        reference_sha = _checked_sha(reference.get("sha256"), "HD material")
        physical = reference.get("physical_file", "")
        if not isinstance(physical, str) or Path(physical).name != physical or Path(physical).suffix.lower() not in (".png", ".dds"):
            raise ValueError("Invalid physical HD material source filename.")
        logical = re.sub(r"^(tex1_\d+x\d+)_m_", r"\1_", Path(physical).stem + ".png")
        if HD_MATERIAL_SOURCE_PINS[source_game].get(logical) != reference_sha:
            raise ValueError("The portrait material differs from its actual pinned HD source file.")
        _checked_sha(recipe.get("sha256"), "rendered HD material")
    return capture


def _registered_extra_portrait(origin: Mapping, *, asset_directory: Path | None = None,
                               identity_validation: str = "catalogued-native-dolphin-key"):
    """Shared registry, model, HD source, pose, frame and PNG validation."""
    from PySide6.QtGui import QImage
    from .resources import bundle_root
    transform = origin.get("transform", {})
    if transform.get("type") != "captured-extra-portrait" or transform.get("version") != 1:
        raise ValueError("Unsupported additional portrait recipe.")
    expected = portrait_origin(transform.get("game", ""), transform.get("native_key", ""),
                               tuple(transform.get("native_size", ())))
    if expected is None or dict(origin) != expected:
        raise ValueError("The additional portrait identity changed.")
    directory = Path(asset_directory) if asset_directory is not None else bundle_root() / "models/extra-portraits"
    manifest_path = directory / "extra-portraits.json"
    if directory.is_symlink() or manifest_path.is_symlink():
        raise ValueError("Additional portrait assets cannot be symbolic links.")
    manifest = json.loads(manifest_path.read_text("utf8"))
    if (manifest.get("schema") != 1 or manifest.get("kind") != _KIND or
            manifest.get("review_only") is not False):
        raise ValueError("The additional portrait registry has not passed review.")
    key = transform["game"] + "/" + transform["member"]
    entry = manifest.get("files", {}).get(key)
    if not isinstance(entry, Mapping):
        raise FileNotFoundError("No registered HD capture for " + key)
    if (entry.get("native_key") != transform["native_key"] or
            entry.get("native_rgba_sha256") != transform["native_rgba_sha256"] or
            entry.get("dimensions") != [168, 336]):
        raise ValueError("The registered additional portrait has changed identity.")
    frames = entry.get("frames", [])
    if len(frames) != 2 or [frame.get("shiny") for frame in frames] != [False, True]:
        raise ValueError("The additional portrait must contain normal and shiny frames.")
    captures = [_capture(manifest, frame.get("capture"), source_game=origin["game"],
                         member=transform["member"], shiny=frame["shiny"]) for frame in frames]
    for field in ("pose_signature_sha256", "camera", "matrix_count"):
        if captures[0][field] != captures[1][field]:
            raise ValueError("Normal and shiny portraits must share exactly one camera and pose.")
    crops = [frame.get("source_crop") for frame in frames]
    if crops[0] != crops[1] or not isinstance(crops[0], list) or len(crops[0]) != 4:
        raise ValueError("Normal and shiny portrait crops must match.")
    left, top, right, bottom = crops[0]
    if (any(not isinstance(value, int) for value in crops[0]) or
            not 0 <= left < right <= 1024 or not 0 <= top < bottom <= 1024 or
            right - left != bottom - top or right - left < 168):
        raise ValueError("Portrait cropping may not enlarge a smaller source.")
    filename = entry.get("file", "")
    if not isinstance(filename, str) or not re.fullmatch(r"[a-z0-9-]+\.png", filename):
        raise ValueError("Invalid additional portrait asset filename.")
    path = directory / filename
    if path.is_symlink() or not path.resolve().is_relative_to(directory.resolve()) or path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError("Invalid additional portrait asset path or size.")
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != _checked_sha(entry.get("sha256"), "portrait"):
        raise ValueError("Additional portrait PNG integrity check failed.")
    image = QImage.fromData(payload, "PNG").convertToFormat(QImage.Format.Format_RGBA8888)
    if image.isNull() or (image.width(), image.height()) != (168, 336):
        raise ValueError("Invalid additional portrait atlas dimensions.")
    pixels = bytes(image.constBits())
    alpha = pixels[3::4]
    if transform["game"] == "colosseum":
        if any(value != 255 for value in alpha):
            raise ValueError("Colosseum additional portraits require a complete opaque square frame.")
    else:
        normal_alpha, shiny_alpha = alpha[:168 * 168], alpha[168 * 168:]
        corners = (0, 167, 168 * 167, 168 * 168 - 1)
        if (normal_alpha != shiny_alpha or any(normal_alpha[at] for at in corners) or
                not 1300 * 16 <= sum(value > 127 for value in normal_alpha) <= 1580 * 16 or
                any(pixels[at:at + 3] != b"\0\0\0" for at in range(0, len(pixels), 4) if not pixels[at + 3])):
            raise ValueError("XD additional portraits must preserve their shared native round frame.")
    return image, {"kind": _KIND, "output_scale": 4,
        "identity_validation": identity_validation,
        "native_key": transform["native_key"], "native_rgba_sha256": transform["native_rgba_sha256"],
        "sha256": entry["sha256"], "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "pose_signature_sha256": captures[0]["pose_signature_sha256"],
        "camera": captures[0]["camera"], "frames": frames,
        "native_bitmap_upscaled_for_hd": False, "required_packs": origin["required_packs"]}


def render_extra_portrait(origin: Mapping, *, native_image, asset_directory: Path | None = None):
    """Check actual captured native RGBA, then load the reviewed registered atlas."""
    from PySide6.QtGui import QImage
    transform = origin.get("transform", {})
    native = native_image.convertToFormat(QImage.Format.Format_RGBA8888)
    if ((native.width(), native.height()) != (42, 84) or
            hashlib.sha256(bytes(native.constBits())).hexdigest() != transform.get("native_rgba_sha256")):
        raise ValueError("The native additional portrait pixels changed.")
    return _registered_extra_portrait(origin, asset_directory=asset_directory,
                                      identity_validation="native-rgba-checked")


def prepare_extra_portrait_overlays(game_id: str, pack_roots: Mapping[str, Path], destination: Path,
                                    *, asset_directory: Path | None = None) -> dict:
    """Add exact-key stock portraits even when an old contract has no native refs.

    Dolphin applies a file only to the identical native samples and palette in
    its name. This route validates catalogued identity, without manufacturing or
    claiming a newly read native bitmap. New contracts use the RGBA route above.
    """
    from .artwork import _png
    from .hd_packs import PACKS
    game = _game(game_id)
    report = {"version": 1, "game_id": game_id, "assets": [], "files": {},
        "required_packs": [], "active": False,
        "identity_validation": "catalogued-native-dolphin-key",
        "native_rgba_read_at_launch": False, "native_rom_changed": False}
    if not extra_portraits_registered(asset_directory):
        return report
    registered = []
    # Review is atomic across all nine atlas files, including the other game.
    for (target_game, key), (_, _) in _CATALOG.items():
        origin = portrait_origin(target_game, key, (42, 84))
        image, proof = _registered_extra_portrait(origin, asset_directory=asset_directory)
        if target_game == game:
            registered.append((key, origin, image, proof))
    required = sorted({origin["game"] for _, origin, _, _ in registered})
    packs = {}
    for source_game in required:
        if source_game not in pack_roots:
            raise ValueError("Required pinned portrait pack is not installed: " + source_game)
        folder = Path(pack_roots[source_game]).resolve()
        folder = folder.parent if folder.name == "Textures" else folder
        marker = json.loads((folder / "installed.json").read_text("utf8"))
        pack = PACKS[source_game]
        if marker.get("key") != pack.key or marker.get("archives") != [part.sha256 for part in pack.parts]:
            raise ValueError("Additional portrait pack differs from its pinned release.")
        packs[source_game] = folder
    if Path(destination).is_symlink():
        raise ValueError("Additional portrait output cannot be a symbolic link.")
    target = Path(destination).resolve()
    if any(target == folder or target.is_relative_to(folder) for folder in packs.values()):
        raise ValueError("Additional portraits cannot write inside a source HD pack.")
    generated = []
    for key, origin, image, proof in registered:
        payload = _png((168, 336), bytes(image.constBits()))
        path = target / key
        if path.is_symlink() or (path.exists() and path.read_bytes() != payload):
            raise ValueError("Conflicting existing additional portrait overlay.")
        sha = hashlib.sha256(payload).hexdigest()
        report["files"][key] = sha
        report["assets"].append({"file": key, "sha256": sha, "role": "retail_form",
            "identity_validation": "catalogued-native-dolphin-key", "origin": origin, "components": proof})
        generated.append((path, payload))
    target.mkdir(parents=True, exist_ok=True)
    for path, payload in generated:
        if not path.exists():
            with path.open("xb") as stream:
                stream.write(payload)
    report.update(active=True, required_packs=required, registered_atlases=9)
    return report
