"""Bounded native texture layers for arbitrary saved Spinda DNA personalities.

Only the two-colour DNA diagram is factored. The original hologram's native
RGB565 face baker is untouched. This module alone does not qualify HD playback.
"""
from __future__ import annotations

import hashlib
import struct

from .analyze_game import FormatError, parse_fsys, u32
from .dna_keypad import DNA_KEYPAD_SPECIES
from .rebuild_iso import decoded_member, repack_fsys
from .spinda_diagram import TEXTURE_BYTES, TEXTURE_SIZE, native_bank, RECIPE


CONTRACT = "dna-spinda-independent-diagrams-v2"


def expanded_layout(base: dict, samples) -> dict:
    """Recompute all native offsets from trusted base dimensions and key IDs."""
    if (not isinstance(samples, (list, tuple)) or not samples or len(samples) > 9
            or any(type(old) is not int or old not in DNA_KEYPAD_SPECIES for old in samples)
            or len(set(samples)) != len(samples) or list(samples) != sorted(samples)):
        raise FormatError("Invalid independent Spinda diagram sample list")
    frozen_atlas = (base["new_data_size"] + 31) & ~31
    bank = frozen_atlas + 0x80000
    cursor = TEXTURE_BYTES
    backgrounds, layers = [], []
    for shiny in range(2):
        backgrounds.append(bank + cursor)
        cursor += TEXTURE_BYTES
        groups = []
        for spot in range(4):
            groups.append(bank + cursor)
            cursor += 256 * TEXTURE_BYTES
        layers.append(groups)
    bank_size = cursor
    cursor += bank
    cells = []
    for old in samples:
        screen = DNA_KEYPAD_SPECIES.index(old)
        cell = next(c for c in base["cells"] if c["screen_index"] == screen)
        # GX encodes texture pointers in32-byte units. Descriptor structures
        # need only4-byte alignment, so each following pixel allocation must
        # explicitly realign after the previous five TObj/ImageDesc records.
        cursor = (cursor + 31) & ~31
        bodies = [cursor, cursor + cell["bytes"]]
        cursor += cell["bytes"] * 2
        frozen = cursor
        cursor += 512
        descriptors, textures = [], []
        for _ in range(5):
            descriptors.append(cursor)
            textures.append(cursor + 24)
            cursor += 24 + 92
        cells.append({"original_species": old, "screen_index": screen,
            "model_index": cell["model_index"], "frozen_diagram_data_offset": frozen,
            "body_data_offsets": bodies, "body_image_descriptor_file_offset": cell["image_descriptor_file_offset"],
            "image_descriptors": descriptors, "texture_objects": textures,
            "base_texture_object": cell["image_descriptor_file_offset"] - 32 + 24,
            "diagram_in_cell": [cell["art_x"] + 8, cell["art_y"] + 88, 32]})
    added_relocations = len(samples) * 15
    old_directory = base["new_dat_size"] - 32 - base["new_data_size"]
    return dict(base, contract=CONTRACT, new_data_size=cursor,
        new_dat_size=32 + cursor + old_directory + added_relocations * 4,
        relocation_count=694 + added_relocations,
        buffer_bytes=cursor + 32 - base["buffer_file_offset"],
        spinda_diagram={"contract": CONTRACT, "samples": list(samples), "bank_data_offset": bank,
            "frozen_case_atlas_data_offset": frozen_atlas, "frozen_case_atlas_bytes": 0x80000,
            "frozen_case_image_descriptor_file_offsets": [32 + 0x4590 + i * 0xA0 for i in (0, 1, 11, 12, 13, 14, 15, 16, 17)],
            "bank_bytes": bank_size, "empty_data_offset": bank,
            "background_data_offsets": backgrounds, "spot_data_offsets": layers,
            "texture_size": TEXTURE_SIZE, "texture_bytes": TEXTURE_BYTES,
            "native_variant_count": 2051, "cells": cells,
            "hologram_policy": "native-face-baker-unchanged-no-hd-face-qualification"})


def body_variants(dat: bytes, cell: dict, original_keypad: bytes, bodies_archive: bytes,
                  number: int) -> tuple[bytes, bytes]:
    from ..artwork import _decode_pixels
    from .dna_keypad import _DAT_SHA256, _tile_rows, _tile_art, _body_pixels, _SPINDA_BODY_ART_RECT
    if not isinstance(original_keypad, bytes) or not isinstance(bodies_archive, bytes):
        raise FormatError("Spinda body variants require original keypad and body archives")
    rows = [m for m in parse_fsys(original_keypad)["members"] if m["identifier_raw"] == "0x107e0200"]
    if len(rows) != 1:
        raise FormatError("Unknown original Spinda keypad template")
    original = decoded_member(original_keypad, rows[0])
    if hashlib.sha256(original).hexdigest() != _DAT_SHA256:
        raise FormatError("Unknown original Spinda keypad artwork")
    template = _decode_pixels(128, 128, 4, b"".join(original[a:b] for a, b in _tile_rows(896, 512)))
    members = {m["name"]: m for m in parse_fsys(bodies_archive)["members"]}
    result = []
    for shiny in (False, True):
        encoded = _tile_art(template, _body_pixels(bodies_archive, members, 308, shiny), 64, 64, number,
                            rect=_SPINDA_BODY_ART_RECT)
        image = bytearray(dat[cell["file_offset"]:cell["file_offset"] + cell["bytes"]])
        for row in range(16):
            start = (cell["art_y"] // 8 + row) * cell["row_bytes"] + cell["art_x"] // 8 * 32
            image[start:start + 512] = encoded[row * 512:(row + 1) * 512]
        result.append(bytes(image))
    return tuple(result)


def extend_spinda_keypad_dat(dat: bytes, base_report: dict, samples,
                            face: bytes, spot: bytes, recipe=RECIPE, *,
                            original_keypad: bytes | None = None,
                            bodies_archive: bytes | None = None) -> tuple[bytes, dict]:
    from .dna_hd_tiles import _validated_layout, CONTRACT as BASE_CONTRACT, MAGIC
    base = _validated_layout(base_report)
    if base["contract"] != BASE_CONTRACT or len(dat) != base["new_dat_size"]:
        raise FormatError("Spinda extension requires one unspecialized independent keypad")
    if struct.unpack_from(">5I", dat) != (len(dat), base["new_data_size"], 694, 1, 0) or u32(dat, 28) != MAGIC:
        raise FormatError("Unknown independent keypad directory")
    bank, bank_report = native_bank(face, spot, tuple(map(tuple, recipe)))
    report = expanded_layout(base, sorted(samples))
    spec = report["spinda_diagram"]
    if len(bank) != spec["bank_bytes"]:
        raise FormatError("Spinda bank serialization changed its bounds")
    data = bytearray(dat[32:32 + base["new_data_size"]])
    data.extend(bytes(spec["frozen_case_atlas_data_offset"] - len(data)))
    data.extend(dat[0x7820:0x87820])
    if len(data) != spec["bank_data_offset"]:
        raise FormatError("Frozen DNA case atlas exceeds its native bounds")
    for desc in spec["frozen_case_image_descriptor_file_offsets"]:
        if struct.unpack_from(">IHHII", dat, desc) != (0x7800, 1024, 1024, 14, 0):
            raise FormatError("Unexpected original DNA case image descriptor")
    data.extend(bank)
    relocations = list(struct.unpack_from(">694I", dat, 32 + base["new_data_size"]))
    for selected in spec["cells"]:
        cell = base["cells"][selected["model_index"]]
        data.extend(bytes(selected["body_data_offsets"][0] - len(data)))
        variants = body_variants(dat, cell, original_keypad, bodies_archive,
                                 cell["screen_index"] + 1 if len(samples) > 1 else 0)
        for at, body in zip(selected["body_data_offsets"], variants):
            if at % 32 or len(data) != at or len(body) != cell["bytes"]:
                raise FormatError("Spinda native body variant exceeds its independent cell")
            data.extend(body)
        left, top, _ = selected["diagram_in_cell"]
        frozen = b"".join(data[cell["data_offset"] + (top // 8 + y) * cell["row_bytes"] + left // 8 * 32:
            cell["data_offset"] + (top // 8 + y) * cell["row_bytes"] + left // 8 * 32 + 128]
            for y in range(4))
        if len(data) != selected["frozen_diagram_data_offset"] or len(frozen) != 512:
            raise FormatError("Spinda frozen diagram bounds changed")
        data.extend(frozen)
        original_tobj = selected["base_texture_object"]
        if u32(data, original_tobj + 4) or original_tobj + 4 in relocations:
            raise FormatError("DNA keypad already has chained texture layers")
        struct.pack_into(">I", data, original_tobj + 4, selected["texture_objects"][0])
        relocations.append(original_tobj + 4)
        for index, (desc, texture) in enumerate(zip(selected["image_descriptors"], selected["texture_objects"])):
            assert len(data) == desc and texture == desc + 24
            data.extend(struct.pack(">IHHIIff", spec["empty_data_offset"], TEXTURE_SIZE, TEXTURE_SIZE, 14, 0, 0., 0.))
            tobj = bytearray(92)
            next_tobj = selected["texture_objects"][index + 1] if index < 4 else 0
            struct.pack_into(">III", tobj, 4, next_tobj, index + 1, 4)
            struct.pack_into(">3f", tobj, 0x1C, TEXTURE_SIZE / cell["width"], TEXTURE_SIZE / cell["height"], 1.)
            struct.pack_into(">3f", tobj, 0x28, (left - 4) / cell["width"], (top - 4) / cell["height"], 0.)
            tobj[0x3C:0x3E] = b"\1\1"
            # Alpha-mask colour composition, material alpha unchanged. All
            # stages sample the same native UV0; clamp rim stays transparent.
            struct.pack_into(">IfII", tobj, 0x40, 0x510010, 1., 1, desc)
            data.extend(tobj)
            relocations.extend((desc, texture + 0x4C))
            if next_tobj:
                relocations.append(texture + 4)
    if len(data) != report["new_data_size"] or len(relocations) != report["relocation_count"]:
        raise FormatError("Spinda independent descriptor layout changed")
    if len(set(relocations)) != len(relocations):
        raise FormatError("Spinda extension produced duplicate relocations")
    header = bytearray(dat[:32])
    struct.pack_into(">III", header, 0, report["new_dat_size"], len(data), len(relocations))
    tail = dat[32 + base["new_data_size"] + 694 * 4:]
    result = bytes(header) + bytes(data) + struct.pack(f">{len(relocations)}I", *sorted(relocations)) + tail
    if len(result) != report["new_dat_size"]:
        raise FormatError("Spinda independent DAT has an invalid final size")
    return result, report | {"source_sha256": hashlib.sha256(dat).hexdigest(),
        "generated_sha256": hashlib.sha256(result).hexdigest(), "spinda_bank": bank_report,
        "runtime_padding_policy": "initial-padding-fixed-own-art-128-only-and-frozen-spinda-swatch",
        "dynamic_spinda_pids_enumerated": False, "spinda_pid_bytes_independently_enumerated": True}


def extend_spinda_keypad_archive(archive: bytes, base_report: dict, samples,
                                face: bytes, spot: bytes, recipe=RECIPE, *,
                                original_keypad: bytes | None = None,
                                bodies_archive: bytes | None = None) -> tuple[bytes, dict]:
    rows = [m for m in parse_fsys(archive)["members"] if m["identifier_raw"] == "0x107e0200"]
    if len(rows) != 1:
        raise FormatError("Expected a unique independent DNA keypad model")
    dat, report = extend_spinda_keypad_dat(decoded_member(archive, rows[0]), base_report, samples, face, spot, recipe,
        original_keypad=original_keypad, bodies_archive=bodies_archive)
    result, _ = repack_fsys(archive, {rows[0]["index"]: dat})
    return result, report | {"archive": "DNA_key.fsys", "member": rows[0]["name"], "resource": "0x107e0200"}
