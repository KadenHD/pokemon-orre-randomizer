"""Build reviewed HD belly and eye layers for XD's cinematic field models.

The three verified field DATs and the battle DAT share the exact 102 unique
TEX0 coordinates, identity texture SRT, CLAMP and pale lighting material. The
cinematic belly is a different CMPR color ramp on this same UV layout. This is
an authored material transfer, not a byte-identical upstream field replacement.

Only the actual 128x128 HD battle image supplies output pixels. A fixed,
white-anchored diagonal RGB transfer was fitted to all 1,024 paired native
texels: gain[c] = sum((255-battle[c])*(255-field[c])) / sum((255-battle[c])**2).
The cinematic eyes use an opaque blue support and a separate curved red iris,
unlike the battle atlas's transparent eye plane. Their authored reconstruction
registers the actual HD aperture mask and completes the iris from visible HD
radial arcs, with fixed native-RGBA calibration and explicit residuals.

No native bitmap is enlarged or read at runtime. The caller applies its retail
belly shiny tint afterwards; native models, lighting and payloads are untouched.
"""
from __future__ import annotations

from pathlib import Path
import math
import re
from statistics import median

from PySide6.QtGui import QImage

from .hd_images import load_texture, resolve_texture

FIELD_BELLY = "tex1_32x32_a7a1e0130c44ec22_14.png"
FIELD_BELLY_SHINY = "tex1_32x32_72d6885b2651fd6f_14.png"
BATTLE_BELLY = "tex1_32x32_afade9df5d7d12c3_14.png"
FIELD_EYE_SOCKET = "tex1_64x32_049351b1fbbbcf67_14.png"
FIELD_EYE_IRIS = "tex1_64x32_53e04980a7607ac8_14.png"
BATTLE_EYES = "tex1_64x64_830778f52c6de2c0_44fccd7f7f60660f_9.png"
_EYE_HD_SOURCE_SHA256 = "c51beb4240c25b5a6239df59144a86fdf8928f1172d13f9ffe857824769b1aa5"
_HD_SOURCE_SHA256 = "023c0b407ca63a8ed95869cb643a857999d9e00ef120ad8efa48ea6318e6db91"
_GAINS = ((60301, 65279), (666599, 680998), (1779007, 1581207))
_FIELD_MODELS = (
    ("0x166c0400", "7ca2b475f94dc732ad7d63fd18e2582a62aa4b595ae9714a576cd1e38b9d099a",
     0x6D98, 0x6DB0, 0x6E20, 0x6E0C),
    ("0x1f540400", "dcf5130a1dfbae575783971c0dfc21ba8b324bbb83daf7cc5da1d5d8eb8e4b21",
     0x12A28, 0x129CC, 0x129B4, 0x12A40),
    ("0x220e0400", "a89fe0f90974014961167a4ea8c40c2ef2b7c40e39c138dd0bd8f05a74118750",
     0xE994, 0xE938, 0xE920, 0xE9AC),
)
_SOCKET = (1.01099505664, -.03951874048, 1.028450304,
           -.0013436928, 1.03729358848, .239044608, 2.431438848, .504455424)
_SOCKET_RGB = (60.41588756917845, 58.95922105283566, 151.57730554203386)
_IRIS_GAINS = (.5246632492469486, .9712888107468372, 1.0281871443754813)
_IRIS_OFFSETS = (108.76230509215065, 8.860681457191589, 5.465602906967478)
_COMMON = ("tex1_32x32_f135b3b243a3e441_14.png",
           "tex1_16x16_a70005786d19905c_14.png", "tex1_16x16_50629643191a1a90_14.png")
_FIELD_MATERIALS = (
    (BATTLE_BELLY, *_COMMON, BATTLE_EYES),
    (*_COMMON, "tex1_128x128_0f28d40b050e3138_1.png", FIELD_BELLY, FIELD_EYE_SOCKET, FIELD_EYE_IRIS),
    (*_COMMON, FIELD_BELLY, FIELD_EYE_SOCKET, FIELD_EYE_IRIS),
)


def _key(value: str) -> str | None:
    if not isinstance(value, str):
        return None
    return re.sub(r"^(tex1_\d+x\d+)_m_", r"\1_", value)


def _proof() -> dict:
    return {
        "native_archive": "people_archive.fsys",
        "field_models": [{"resource": resource, "dat_sha256": sha,
                          "image_descriptor": image, "tobj": tobj, "mobj": mobj,
                          "lighting_record": lighting}
                         for resource, sha, image, tobj, mobj, lighting in _FIELD_MODELS],
        "offset_convention": "relative to DAT data section; add 0x20 for raw DAT file offsets",
        "battle_archive": "pkx_darklugia.fsys",
        "battle_dat_sha256": "b506ec554676d25d4d503f857a0af84709fa708afeb77e806f551ac86d7adc9d",
        "native_uv_signature": "2b7d22b5106dd50ddc84d057dfda83b6cf612ec203eccaba3bb81243366a684f",
        "signature_encoding": "SHA256 of byte-sorted unique big-endian float32 TEX0 (u,v) pairs",
        "unique_uv_pairs": 102,
        "uv_bounds": [0.01562422513961792, -0.017386198043823242,
                      0.9843758344650269, 0.9990015029907227],
        "shared_uv_layout": True,
        "texture_srt": {"rotation": [0, 0, 0], "scale": [1, 1, 1], "translation": [0, 0, 0]},
        "wrap": ["CLAMP", "CLAMP"], "tobj_flags": 0x30010,
        "ambient_diffuse_specular_rgba": "b3b3b3ff ffffffff ffffffff",
        "calibration": {
            "native_pairs": 1024,
            "battle_samples_sha256": "394792c2a0e38098d4f19ff73f511cc5fe83e3d8cc5bb632d19b81d7c4497469",
            "field_samples_sha256": "eac76432691ee55028130b5ee6e1e4c3a19fc812e7081e68bdb506f3cc4c8716",
            "battle_rgba_sha256": "8f6659bf8522435536ea95f13e2b15cfa7d035c26ea1b8f819864d102262bab9",
            "field_rgba_sha256": "9c6b0245cfee8731dbc7f00906d9d402ccb555f151f62ad55a44bdef26eba4b7",
            "cross_products_rgb": [3316555, 2666396, 1779007],
            "battle_square_sums_rgb": [3590345, 2723992, 1581207],
            "sse_rgb_before": [24563, 3256, 31833],
            "sse_rgb_after_integer_transfer": [3613, 2120, 7120],
            "sse_total_before": 59652, "sse_total_after_integer_transfer": 12853,
            "measurement": "RGB errors over decoded native level-zero texels, not HD equivalence",
        },
    }


def field_material_inventory(pack: Path) -> dict:
    """List every material in all three custom field DATs; none is exempt from HD."""
    models = []
    for model, keys in zip(_FIELD_MODELS, _FIELD_MATERIALS):
        resource, sha, *_ = model
        materials = []
        for key in keys:
            width, height, fmt = re.fullmatch(r"tex1_(\d+)x(\d+)_.+_(\d+)\.png", key).groups()
            direct = None
            try:
                path = resolve_texture(Path(pack) / "Textures", key)
            except FileNotFoundError:
                pass
            else:
                direct = load_texture(path, expected_native_size=(int(width), int(height)), max_scale=16).metadata
            shiny = {FIELD_BELLY: FIELD_BELLY_SHINY,
                     BATTLE_BELLY: "tex1_32x32_f6069745b908bc2e_14.png"}.get(key, key)
            route = ("field-eye-layer-reconstruction" if key in (FIELD_EYE_SOCKET, FIELD_EYE_IRIS)
                     else "field-belly-material-transfer" if key == FIELD_BELLY
                     else "direct-pack" if direct is not None else "authored-battle-material-transfer")
            materials.append({"native_key": key, "shiny_key": shiny, "width": int(width),
                              "height": int(height), "format": int(fmt), "hd_required": True,
                              "required_scale": 4, "source_available": direct is not None,
                              "direct_source": direct, "hd_route": route})
        models.append({"resource": resource, "native_dat_sha256": sha, "materials": materials})
    return {"archive": "people_archive.fsys", "custom_models_require_every_material": True,
            "models": models}


def _eye_proof(socket: bool) -> dict:
    return {
        "native_archive": "people_archive.fsys",
        "field_models": [{"resource": m[0], "dat_sha256": m[1]} for m in _FIELD_MODELS[1:]],
        "battle_dat_sha256": "b506ec554676d25d4d503f857a0af84709fa708afeb77e806f551ac86d7adc9d",
        "source_native_rgba_sha256": "91b1100518404aea2d48ca55ee91f4d035eb600e3326b0d16e55460eaec0e0ab",
        "field_native_rgba_sha256": ("04bffdd836b1fc5eb9e8b95d26a847e4bc4c5727809dd43e2d3e6a2eef951890"
                                      if socket else "20e6e1a9f109e4660a86eaa42b2ad560bb77c116348b9f28c27c3487b42968c8"),
        "battle_uv_signature": "3288fadcb9f6d69f71fa9179cd03798cbe6db05922ad3a5c6d2c3d9fa9c6cab7",
        "field_uv_signature": ("7bdac2a43850fd21483385bf2a12cb1e794666274ccc629b007451ba834f36fa"
                               if socket else "9ab2111d4a6f1fee44dbf96d2e84a3b499efffbdc84fa6882a3beda6b335ef24"),
        "signature_encoding": "SHA256 of byte-sorted unique big-endian float32 TEX0 (u,v) pairs",
        "field_unique_uv_pairs": 5 if socket else 7,
        "texture_srt": {"rotation": [0, 0, 0], "scale": [1, 1, 1], "translation": [0, 0, 0]},
        "wrap": ["CLAMP", "CLAMP"], "field_tobj_flags": 0x40010,
        "source_tobj_flags": 0x340010,
        "mirror_handling": "both native eye meshes share field UVs; no image flip",
        "source_frame_native_rect": [0, 0, 64, 32],
        "geometry_observation": ("ten socket vertices match battle eye vertices within 0.000001436 model units"
                                 if socket else "fourteen iris vertices form a separate curved layer; direct battle projection is not equivalent"),
        "native_rgb_calibration_rmse": 4.189901226105186 if socket else 3.5552337694925247,
        "native_rgb_calibration_sse": 107859.592916077 if socket else 77658.23788486671,
        "calibration_components": 64 * 32 * 3,
        "calibration_scope": "decoded native RGBA fit, not an HD equivalence claim",
    }


def _eye_frame(loaded):
    from PIL import Image
    rgba = loaded.image.convertToFormat(QImage.Format.Format_RGBA8888)
    return Image.frombytes("RGBA", (256, 256), bytes(rgba.constBits())).crop((0, 0, 256, 128))


def _radial_profile(frame):
    """Recover a complete iris from visible HD arcs, ignoring hidden RGB garbage."""
    bins = [[] for _ in range(265)]  # Half-HD-pixel steps, radius 0..132 HD pixels.
    data = bytes(frame.tobytes())
    anchors = []
    for y in range(128):
        for x in range(256):
            at = (y * 256 + x) * 4
            if data[at + 3] <= 200:
                continue
            radius = math.hypot(x - 131.5, y - 65.5)
            rgb = tuple(data[at:at + 3])
            if 40 <= radius <= 52:
                anchors.append(rgb)
            center = radius * 2
            for index in range(max(0, math.ceil(center - 1.5)), min(264, math.floor(center + 1.5)) + 1):
                bins[index].append(rgb)
    if len(anchors) < 32:
        raise ValueError("The reviewed HD atlas lacks its visible iris arcs")
    available = {i: tuple(median(pixel[c] for pixel in values) for c in range(3))
                 for i, values in enumerate(bins) if values}
    if len(available) < 32:
        raise ValueError("The reviewed HD atlas cannot supply the iris profile")
    indexes = sorted(available)
    profile = []
    for i in range(len(bins)):
        lower = max((v for v in indexes if v <= i), default=indexes[0])
        upper = min((v for v in indexes if v >= i), default=indexes[-1])
        weight = (i - lower) / (upper - lower) if upper != lower else 0
        profile.append(tuple(available[lower][c] * (1 - weight) + available[upper][c] * weight for c in range(3)))
    return profile, tuple(median(pixel[c] for pixel in anchors) for c in range(3))


def _socket_image(frame, anchor):
    from PIL import ImageFilter
    a, b, c, d, e, f, sigma, gamma = _SOCKET
    mask = frame.getchannel("A").filter(ImageFilter.GaussianBlur(sigma * 4)).tobytes()
    # The native fit fixes hue. The actual HD iris highlight supplies illumination.
    native_luminance = 231 * 2126 + 82 * 7152 + 74 * 722
    illumination = sum(v * w for v, w in zip(anchor, (2126, 7152, 722))) / native_luminance
    pixels = bytearray(256 * 128 * 4)
    for y in range(128):
        for x in range(256):
            nx, ny = (x + .5) / 4 - .5, (y + .5) / 4 - .5
            sx, sy = (a * nx + b * ny + c) * 4 + 1.5, (d * nx + e * ny + f) * 4 + 1.5
            x0, y0 = math.floor(sx), math.floor(sy)
            dx, dy = sx - x0, sy - y0
            coverage = 0.
            for xx, yy, weight in ((x0, y0, (1-dx)*(1-dy)), (x0+1, y0, dx*(1-dy)),
                                    (x0, y0+1, (1-dx)*dy), (x0+1, y0+1, dx*dy)):
                if 0 <= xx < 256 and 0 <= yy < 128:
                    coverage += mask[yy * 256 + xx] / 255 * weight
            at = (y * 256 + x) * 4
            pixels[at:at+3] = bytes(min(255, max(0, round(coverage ** gamma * color * illumination)))
                                      for color in _SOCKET_RGB)
            pixels[at+3] = 255
    return pixels, {"affine_native_pixels": list(_SOCKET[:6]), "blur_native_pixels": sigma,
                    "gamma": gamma, "native_fit_rgb": list(_SOCKET_RGB),
                    "hd_highlight_rgb": list(anchor), "hd_illumination_factor": illumination}


def render_lugia_field_eye_material(pack: Path, *, native_key: str, target_key: str
                                    ) -> tuple[QImage, dict] | None:
    """Reconstruct the two opaque field eye layers from the reviewed HD atlas."""
    native = _key(native_key)
    if native not in (FIELD_EYE_SOCKET, FIELD_EYE_IRIS) or _key(target_key) != native:
        return None
    pack = Path(pack)
    if pack.is_symlink() or (pack / "Textures").is_symlink():
        raise ValueError("The reviewed HD material cannot come from a symbolic-link directory")
    try:
        path = resolve_texture(pack / "Textures", BATTLE_EYES)
    except FileNotFoundError:
        return None
    loaded = load_texture(path, expected_native_size=(64, 64), max_scale=4)
    if loaded.metadata["source_scale"] != 4 or loaded.metadata["sha256"] != _EYE_HD_SOURCE_SHA256:
        raise ValueError("The eye layers require the reviewed genuine 4x independent HD atlas")
    frame = _eye_frame(loaded)
    profile, anchor = _radial_profile(frame)
    socket = native == FIELD_EYE_SOCKET
    if socket:
        pixels, construction = _socket_image(frame, anchor)
    else:
        pixels = bytearray(256 * 128 * 4)
        for y in range(128):
            for x in range(256):
                # Beyond 24 native pixels the atlas reaches its black aperture
                # outline. Extend the reviewed red background instead of
                # introducing that unrelated outline into the opaque iris map.
                radius = min(192., 2 * math.hypot(x - 129.5, y - 65.5))
                first = int(radius); last = min(264, first + 1); weight = radius - first
                at = (y * 256 + x) * 4
                pixels[at:at+3] = bytes(min(255, max(0, round(
                    (profile[first][ch] * (1-weight) + profile[last][ch] * weight)
                    * _IRIS_GAINS[ch] + _IRIS_OFFSETS[ch]))) for ch in range(3))
                pixels[at+3] = 255
        construction = {"source_center_native_pixels": [32.5, 16], "target_center_native_pixels": [32, 16],
                        "red_background_extension_radius_native_pixels": 24,
                        "profile_step_hd_pixels": .5, "profile_halfwidth_hd_pixels": .75,
                        "visible_alpha_threshold": 200, "gain_rgb": list(_IRIS_GAINS),
                        "offset_rgb": list(_IRIS_OFFSETS)}
    image = QImage(bytes(pixels), 256, 128, 256 * 4, QImage.Format.Format_RGBA8888).copy()
    return image, {"kind": "authored-hd-field-eye-layer-reconstruction",
        "reference": {"file": BATTLE_EYES, **loaded.metadata}, "native_uv_guide": native,
        "target_key": native, "material_role": "blue_socket" if socket else "red_iris",
        "construction": construction, "material_proof": _eye_proof(socket),
        "alpha": "255 exactly, matching both native opaque field maps; the mesh clips the layers",
        "native_bitmap_resampled": False, "no_upscale_native": True,
        "normal_shiny_identical": True, "shiny_tint_applied": False,
        "native_payload_modified": False, "other_materials_modified": False,
        "limitations": ["Authored reconstruction of separate field layers, not an exact crop of the battle atlas",
                        "Radial completion reconstructs atlas-occluded iris arcs from visible HD arcs",
                        "Native calibration residuals are recorded; visual validation remains separate"]}


def render_lugia_field_material(pack: Path, *, native_key: str, target_key: str
                                ) -> tuple[QImage, dict] | None:
    """Return a registered 4x field material; the caller owns the belly shiny tint.

    Unrelated identities or a missing donor return None. A changed donor or
    unsupported resolution raises ValueError instead of guessing a source.
    Eye layers are identical for normal and shiny appearances. No files, model
    bytes, palettes, texture coordinates or scene state are changed.
    """
    if _key(native_key) in (FIELD_EYE_SOCKET, FIELD_EYE_IRIS):
        return render_lugia_field_eye_material(pack, native_key=native_key, target_key=target_key)
    if _key(native_key) != FIELD_BELLY or _key(target_key) not in (FIELD_BELLY, FIELD_BELLY_SHINY):
        return None
    pack = Path(pack)
    if pack.is_symlink() or (pack / "Textures").is_symlink():
        raise ValueError("The reviewed HD material cannot come from a symbolic-link directory")
    try:
        path = resolve_texture(pack / "Textures", BATTLE_BELLY)
    except FileNotFoundError:
        return None
    loaded = load_texture(path, expected_native_size=(32, 32), max_scale=4)
    if loaded.metadata["source_scale"] != 4:
        raise ValueError("The reviewed field transfer requires the genuine 4x HD material")
    if loaded.metadata["sha256"] != _HD_SOURCE_SHA256:
        raise ValueError("The HD belly donor differs from the reviewed independent pack")
    image = loaded.image.convertToFormat(QImage.Format.Format_RGBA8888)
    pixels = bytearray(image.constBits())
    lookup = tuple(tuple(max(0, min(255, (255 * denominator - numerator * (255 - value)
                                        + denominator // 2) // denominator))
                         for value in range(256)) for numerator, denominator in _GAINS)
    for at in range(0, len(pixels), 4):
        for channel in range(3):
            pixels[at + channel] = lookup[channel][pixels[at + channel]]
    result = QImage(bytes(pixels), image.width(), image.height(), image.width() * 4,
                    QImage.Format.Format_RGBA8888).copy()
    return result, {
        "kind": "authored-hd-field-material-retouch",
        "reference": {"file": BATTLE_BELLY, **loaded.metadata},
        "native_uv_guide": FIELD_BELLY, "target_key": _key(target_key),
        "construction": "shared native UV material; fixed white-anchored diagonal RGB transfer of the real 4x HD donor",
        "uv_mapping": "identity", "native_bitmap_resampled": False, "no_upscale_native": True,
        "alpha": "preserved exactly from the HD donor",
        "shiny_tint_applied": False, "native_payload_modified": False,
        "other_materials_modified": False,
        "color_transfer": {"white_anchor": 255,
                           "gain_numerator_denominator_rgb": [list(pair) for pair in _GAINS],
                           "rounding": "nearest integer, clamped to 0..255"},
        "material_proof": _proof(),
        "limitations": ["Authored field material, not an upstream replacement for the field texture",
                        "Native calibration residual is recorded; pixel equivalence is not claimed",
                        "Dolphin scene appearance requires separate visual validation"],
    }
