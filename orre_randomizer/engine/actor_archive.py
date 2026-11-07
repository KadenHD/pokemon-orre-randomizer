"""Room-local field model copies using the retail FSYS directory format."""

import struct

from .analyze_game import FormatError, parse_fsys, u32
from .rebuild_iso import align, compress_lzss, decoded_member


def append_actor_models(source, replacements, donor_archive, donor_id, models):
    """Add model resources cloned from an original member header."""
    original = parse_fsys(source)
    donor = parse_fsys(donor_archive)
    members = original["members"]
    stride = {"0x00000102": 0x50, "0x00000104": 0x50, "0x00000201": 0x70}.get(original["version_raw"])
    template = [m for m in donor["members"] if int(m["identifier_raw"], 16) == donor_id]
    existing_ids = {int(m["identifier_raw"], 16) for m in members}
    if (not stride or donor["version_raw"] != original["version_raw"] or len(template) != 1
            or template[0]["compression"] != "LZSS" or donor_id & 0xFF00 != 0x0400
            or existing_ids & models.keys() or any(ident & 0xFF00 != 0x0400 for ident in models)
            or set(replacements) - {m["index"] for m in members}):
        raise FormatError("unexpected original FSYS actor directory")

    def header(archive, member):
        position = member["header_offset"]
        data = bytearray(archive[position:position + stride])
        # Room archives in both versions store one optional name pointer.
        if len(data) != stride or u32(data, 0x28):
            raise FormatError("unsupported FSYS actor directory entry")
        return data

    entries = [(m["name"], header(source, m), source[m["offset"]:m["offset"] + m["stored_size"]],
                replacements.get(m["index"])) for m in members]
    for ident, (name, payload) in models.items():
        cloned = header(donor_archive, template[0])
        struct.pack_into(">I", cloned, 0, ident)
        entries.append((name, cloned, b"", payload))

    directory = u32(source, 0x40)
    names_start = align(directory + 4 * len(entries), 16)
    output = bytearray(source[:directory])
    output.extend(bytes(names_start - len(output)))
    for name, entry, _, _ in entries:
        if u32(entry, 0x24) or name:
            struct.pack_into(">I", entry, 0x24, len(output))
            output.extend(name.encode("ascii") + b"\0")
    headers_start = align(len(output), 16)
    first_data = align(headers_start + stride * len(entries))
    output.extend(bytes(first_data - len(output)))
    for index, (_, entry, stored, payload) in enumerate(entries):
        if payload is not None:
            stored = compress_lzss(payload) if not stored or stored[:4] == b"LZSS" else payload
            struct.pack_into(">I", entry, 8, len(payload))
            struct.pack_into(">I", entry, 0x14, len(stored))
        output.extend(bytes(align(len(output)) - len(output)))
        struct.pack_into(">I", entry, 4, len(output))
        output.extend(stored)
        offset = headers_start + stride * index
        output[offset:offset + stride] = entry
        struct.pack_into(">I", output, directory + 4 * index, offset)
    output.extend(bytes(align(len(output)) - len(output) + 28) + b"FSYS")
    struct.pack_into(">I", output, 0xC, len(entries))
    struct.pack_into(">II", output, 0x1C, first_data, len(output))
    struct.pack_into(">II", output, 0x44, names_start, first_data)
    rebuilt = bytes(output)
    actual = parse_fsys(rebuilt)["members"]
    for (name, entry, stored, payload), member in zip(entries, actual, strict=True):
        if (member["name"], int(member["identifier_raw"], 16)) != (name, u32(entry, 0)):
            raise FormatError("rebuilt FSYS actor identity changed")
        if payload is not None:
            if decoded_member(rebuilt, member) != payload:
                raise FormatError("FSYS actor payload roundtrip failed")
        elif rebuilt[member["offset"]:member["offset"] + member["stored_size"]] != stored:
            raise FormatError("FSYS preserved payload changed")
    return rebuilt
