"""Appended weather variants preserve native members, frames and other patches."""
import struct
import unittest
from pathlib import Path

from orre_randomizer.artwork import _texture
from orre_randomizer.castform_resources import (
    SHINY_FACE_RESOURCES, _face_header, append_castform_resources, make_weather_face_atlas,
)
from orre_randomizer.castform_shiny_models import SHINY_RESOURCES
from orre_randomizer.engine.actor_archive import append_actor_models
from orre_randomizer.engine.analyze_game import FormatError, parse_fsys
from orre_randomizer.engine.rebuild_iso import compress_lzss, decoded_member
from orre_randomizer.engine.shadow_lugia_face import make_colosseum_shadow_lugia_face


def face(xd):
    if not xd:
        pixels = bytes(channel for y in range(42) for x in range(42)
                       for channel in (x * 5, y * 5, 90, 255))
        return make_colosseum_shadow_lugia_face(_face_header(indexed=False) + bytes(14784), pixels, pixels)
    result = bytearray(_face_header(indexed=True) + bytes(4544))
    for y in range(84):
        for x in range(42):
            inside = (x + .5 - 21) ** 2 + (y % 42 + .5 - 21) ** 2 < 22.5 ** 2
            at = 128 + (y // 4) * 192 + (x // 8) * 32 + (y % 4) * 8 + x % 8
            result[at] = 1 + ((x // 6 + y % 42 // 6) % 5) if inside else 0
    struct.pack_into(">6H", result, 4160, 0, 0xFFFF, 0xFC00, 0x83E0, 0x801F, 0xAABB)
    return bytes(result)


def archive(rows, group, xd):
    stride = 0x70 if xd else 0x50
    result = bytearray(0x80 + len(rows) * stride)
    result[:4] = b"FSYS"
    for at, value in ((4, 0x201 if xd else 0x102), (8, group), (0xC, len(rows)), (0x40, 0x60)):
        struct.pack_into(">I", result, at, value)
    for index, (resource, name, payload) in enumerate(rows):
        header = 0x80 + index * stride
        struct.pack_into(">I", result, 0x60 + index * 4, header)
        struct.pack_into(">I", result, header + 0x24, len(result))
        result.extend(name.encode("ascii") + b"\0")
        result.extend(bytes(-len(result) % 32))
        stored = compress_lzss(payload)
        for at, value in ((0, resource), (4, len(result)), (8, len(payload)), (0x14, len(stored))):
            struct.pack_into(">I", result, header + at, value)
        result.extend(stored)
    result.extend(bytes(-len(result) % 32 + 28) + b"FSYS")
    struct.pack_into(">I", result, 0x20, len(result))
    return bytes(result)


def fixture(xd):
    ids = {414: 0x03DD1E00, 415: 0x03DA1E00, 416: 0x03DC1E00} if xd else {
        414: 0x045E1E00, 415: 0x045B1E00, 416: 0x045D1E00}
    face_ids = {414: 0x0E9F1200, 415: 0x0E9D1200, 416: 0x0E9E1200} if xd else {
        414: 0x0F691200, 415: 0x0F671200, 416: 0x0F681200}
    result, faces = {}, []
    for model, suffix, group in ((414, "w", 446), (415, "f", 443), (416, "i", 445)):
        result[f"pkx_powalen_{suffix}.fsys"] = archive([
            (ids[model], f"powalen_{suffix}", b"native-model-payload-" + suffix.encode()),
            (0x12341E00, "unrelated", b"unchanged-animation-auxiliary")], group, xd)
        faces.append((face_ids[model], f"face385{suffix}", face(xd)))
    result["poke_face.fsys"] = archive(faces + [(0x12341200, "unrelated", b"native-unrelated-face")], 0x5C0, xd)
    return result, face_ids


def shiny(_game_id, model, normal):
    output = bytearray(normal)
    for at in range(0, len(output), 4):
        output[at:at + 3] = bytes((120 + model % 30, 35, 200)) if output[at + 3] else bytes(3)
    return bytes(output)


def decode_atlas(encoded):
    # The RGB5A3 image uses7520B; the fixed XD copy slot also contains512B
    # explicit zero padding, which is outside the GX texture extent.
    return _texture(encoded[:7520] if encoded[4] == 16 else encoded, (42, 84))


class CastformResourceTests(unittest.TestCase):
    def assert_atlas_pixels(self, decoded, normal, rare, *, xd):
        size = 42 * 42 * 4
        self.assertEqual(decoded[:size], normal)
        self.assertEqual(decoded[size + 3::4], rare[3::4])
        if xd:
            # Native RGB5A3 rounds the new opaque render by at most five units;
            # source normal RGB and every circular-alpha pixel remain exact.
            self.assertLessEqual(max(abs(decoded[size + at + channel] - rare[at + channel])
                for at in range(0, size, 4) if rare[at + 3]
                for channel in range(3)), 5)
        else:
            self.assertEqual(decoded[size:], rare)

    def test_native_atlases_preserve_normal_pixels_and_each_alpha_frame(self):
        for xd in (False, True):
            with self.subTest(xd=xd):
                gid = "GXXP01" if xd else "GC6P01"
                original = face(xd)
                normal = _texture(original, (42, 84))[:42 * 42 * 4]
                rare = shiny(gid, 415, normal)
                encoded = make_weather_face_atlas(original, rare, game_id=gid)
                self.assertEqual(encoded[:128], bytes.fromhex(
                    "002a0054100100000000009000000000" if xd else
                    "002a0054200100000000004500000000") + bytes(24) + b"\0\0\0\x80" + bytes(84))
                self.assertEqual(len(encoded), 0x1F60 if xd else 14912)
                if xd:
                    self.assertEqual(encoded[7520:], bytes(512))
                self.assert_atlas_pixels(decode_atlas(encoded), normal, rare, xd=xd)
                self.assertEqual(normal[3::4], rare[3::4])
                self.assertEqual(face(xd), original)

    def test_models_faces_and_existing_lugia_members_are_preserved_when_appending(self):
        for xd in (False, True):
            with self.subTest(xd=xd):
                gid = "GXXE01" if xd else "GC6E01"
                source, face_ids = fixture(xd)
                original_faces = source["poke_face.fsys"]
                pending_faces = append_actor_models(original_faces, {}, original_faces, face_ids[415],
                    {0x7DF51200: ("face249dark_shiny", b"existing-shadow-lugia-shiny"),
                     0x7DF61200: ("face249dark_bonus", b"existing-shadow-lugia-normal")}, resource_type=0x1200)
                pending = {"poke_face.fsys": pending_faces, "other-game-data.fsys": b"another-pending-patch"}
                before = {**source, "poke_face.fsys": pending_faces}
                calls = []
                def model_builder(game_id, model, native):
                    calls.append((game_id, model, native))
                    return b"qualified-rare-" + native
                report = append_castform_resources(gid, source.__getitem__, pending,
                    model_builder=model_builder, shiny_face_pixels=shiny)
                self.assertEqual(pending["other-game-data.fsys"], b"another-pending-patch")
                self.assertEqual([model for _, model, _ in calls], [414, 415, 416])
                self.assertEqual(report["model_resources"], SHINY_RESOURCES)
                self.assertEqual(report["shiny_face_resources"], SHINY_FACE_RESOURCES)
                for filename, previous in before.items():
                    current = pending[filename]
                    old_members = parse_fsys(previous)["members"]
                    new_members = parse_fsys(current)["members"]
                    new_by_id = {int(row["identifier_raw"], 16): row for row in new_members}
                    for old in old_members:
                        new = new_by_id[int(old["identifier_raw"], 16)]
                        self.assertEqual(old["name"], new["name"])
                        self.assertEqual(decoded_member(previous, old), decoded_member(current, new))
                        self.assertEqual(previous[old["offset"]:old["offset"] + old["stored_size"]],
                                         current[new["offset"]:new["offset"] + new["stored_size"]])
                    self.assertEqual(len(new_members), len(old_members) + (3 if filename == "poke_face.fsys" else 1))
                self.assertEqual(source["poke_face.fsys"], original_faces)
                current = pending["poke_face.fsys"]
                by_id = {int(row["identifier_raw"], 16): row for row in parse_fsys(current)["members"]}
                for model, resource in SHINY_FACE_RESOURCES.items():
                    native = next(row for row in parse_fsys(original_faces)["members"]
                                  if int(row["identifier_raw"], 16) == face_ids[model])
                    normal = _texture(decoded_member(original_faces, native), (42, 84))[:42 * 42 * 4]
                    self.assert_atlas_pixels(decode_atlas(decoded_member(current, by_id[resource])),
                        normal, shiny(gid, model, normal), xd=xd)

    def test_native_indexed_cells_may_have_small_rgb_differences_with_the_same_frame(self):
        # Retail XD's two pre-baked weather cells differ at a few RGB pixels.
        # That must not prevent preserving row0 and appending an authored row1.
        original = bytearray(face(True))
        x, y = 21, 63
        at = 128 + (y // 4) * 192 + (x // 8) * 32 + (y % 4) * 8 + x % 8
        original[at] = 2 if original[at] != 2 else 1
        pixels = _texture(bytes(original), (42, 84))
        normal = pixels[:42 * 42 * 4]
        self.assertNotEqual(normal, pixels[42 * 42 * 4:])
        rare = shiny("GXXP01", 415, normal)
        result = make_weather_face_atlas(bytes(original), rare, game_id="GXXP01")
        self.assert_atlas_pixels(decode_atlas(result), normal, rare, xd=True)

    def test_xd_direct_atlas_fits_native_cache_without_truncating_shiny_circle(self):
        original = bytearray(face(True))
        # Opaque A3RGB4 must remain exact instead of being re-quantized as RGB5.
        struct.pack_into(">H", original, 4162, 0x7ABC)
        normal = _texture(bytes(original), (42, 84))[:42 * 42 * 4]
        rare = shiny("GXXP01", 415, normal)
        result = make_weather_face_atlas(bytes(original), rare, game_id="GXXP01")
        self.assertLessEqual(len(result), 0x1F60)  # XD's native memcpy/allocation length.
        self.assertEqual(result[4], 16)
        self.assertEqual(struct.unpack_from(">I", result, 8)[0], 0x90)
        decoded = decode_atlas(result[:0x1F60])
        self.assertEqual(decoded[:42 * 42 * 4], normal)
        self.assertEqual(sum(bool(v) for v in decoded[42 * 42 * 4 + 3::4]),
                         sum(bool(v) for v in rare[3::4]))
        self.assertGreater(sum(bool(v) for v in rare[3::4]), 1500)

    def test_optional_retail_xd_executables_have_the_verified_fixed_face_cache(self):
        root = Path(__file__).resolve().parents[1]
        checked = 0
        for region in ("eu", "us", "jp"):
            path = root / "build/xd-validation" / region / "main.dol"
            if not path.is_file():
                continue
            original = path.read_bytes()
            # Native callback memcpy length, with its following slot lookup.
            copy = bytes.fromhex("38a01f607c000774540018387c63021480630004")
            # Native cache-slot allocation: size0x1f60, alignment32.
            allocation = bytes.fromhex("38601f6038800020")
            self.assertEqual(original.count(copy), 1)
            self.assertEqual(original.count(allocation), 1)
            checked += 1
        if not checked:
            self.skipTest("Local retail XD executables are optional")

    def test_invalid_face_or_builder_cannot_publish_partial_model_updates(self):
        for xd in (False, True):
            for failure in ("dimensions", "alpha", "model"):
                with self.subTest(xd=xd, failure=failure):
                    gid = "GXXP01" if xd else "GC6P01"
                    source, _ = fixture(xd)
                    pending = {"poke_face.fsys": source["poke_face.fsys"], "unrelated": b"preserve"}
                    before = pending.copy()
                    def model_builder(_game, model, native):
                        return native if failure == "model" and model == 415 else b"rare-" + native
                    def pixels(game, model, normal):
                        value = shiny(game, model, normal)
                        if model != 415:
                            return value
                        if failure == "dimensions":
                            return value[:-4]
                        if failure == "alpha":
                            value = bytearray(value)
                            value[(21 * 42 + 21) * 4 + 3] = 0
                            return bytes(value)
                        return value
                    with self.assertRaises(FormatError):
                        append_castform_resources(gid, source.__getitem__, pending,
                            model_builder=model_builder, shiny_face_pixels=pixels)
                    self.assertEqual(pending, before)

    def test_existing_custom_resource_collision_fails_without_replacing_it(self):
        source, face_ids = fixture(True)
        base = source["poke_face.fsys"]
        previous = append_actor_models(base, {}, base, face_ids[415],
            {SHINY_FACE_RESOURCES[414]: ("reserved-by-another-patch", b"keep-this-resource")}, resource_type=0x1200)
        pending = {"poke_face.fsys": previous}
        with self.assertRaises(FormatError):
            append_castform_resources("GXXP01", source.__getitem__, pending,
                model_builder=lambda _g, _m, native: b"rare-" + native, shiny_face_pixels=shiny)
        self.assertEqual(pending, {"poke_face.fsys": previous})

    def test_invalid_native_header_or_non_native_frame_is_refused(self):
        original = face(True)
        rare = shiny("GXXP01", 415, _texture(original, (42, 84))[:42 * 42 * 4])
        changed = bytearray(original)
        changed[0x18] = 1
        for source in (b"truncated", bytes(changed), face(False)):
            with self.subTest(length=len(source)), self.assertRaises(FormatError):
                make_weather_face_atlas(source, rare, game_id="GXXP01")


if __name__ == "__main__":
    unittest.main()
