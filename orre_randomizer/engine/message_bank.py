"""Relocate selected GameCube message records without re-encoding their controls."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from functools import partial
import re
import struct

from .analyze_game import FormatError, check_range, parse_fsys
from .inspect_tables import u16
from .rebuild_iso import decoded_member, repack_fsys


_CONTROL_ARGUMENTS = dict.fromkeys((0x07, 0x09, 0x38, 0x52, 0x53, 0x5B, 0x5C), 1) | {0x08: 4}


def replace_names(source: bytes, changes: Mapping[str, str], language: str) -> bytes:
    """Replace known native names in one pass, including swaps and repeated names."""
    changes = {old: new for old, new in changes.items() if old != new}
    if not changes:
        return source
    alternatives = "|".join(re.escape(name) for name in sorted(changes, key=len, reverse=True))
    pattern = re.compile(alternatives if language == "JP" else rf"(?<!\w)(?:{alternatives})(?!\w)")

    def rewrite(text: bytes) -> bytes:
        decoded = text.decode("utf-16-be", errors="surrogatepass")
        return pattern.sub(lambda match: changes[match[0]], decoded).encode("utf-16-be", errors="surrogatepass")

    # Control codes have odd byte lengths, so decode each intervening span
    # independently and preserve control operands and trailing padding.
    result = bytearray()
    start = cursor = 0
    while cursor + 1 < len(source):
        unit = source[cursor:cursor + 2]
        if unit == b"\0\0":
            break
        if unit == b"\xff\xff" and cursor + 2 < len(source):
            end = cursor + 3 + _CONTROL_ARGUMENTS.get(source[cursor + 2], 0)
            result.extend(rewrite(source[start:cursor]))
            result.extend(source[cursor:end])
            start = cursor = end
        else:
            cursor += 2
    result.extend(rewrite(source[start:cursor]))
    result.extend(source[cursor:])
    return bytes(result)


def patch_species_archive(source: bytes, messages: Mapping[int, Mapping[int, int]],
                          names: Mapping[str, Mapping[int, str]], *, rewrites=None) -> bytes:
    """Update only reviewed message IDs, using the native names of each bank."""
    replacements = {}
    found = set()
    for member in parse_fsys(source)["members"]:
        if int(member["identifier_raw"], 16) & 0xFF00 != 0x0A00:
            continue
        bank = decoded_member(source, member)
        tag = bank[6:8]
        language = "JP" if tag == b"\0\0" else tag.decode("ascii", errors="replace")
        if language not in names:
            raise FormatError("unexpected language in species dialogue archive")
        edits = {}
        for identifier in messages.keys() & message_directory(bank).keys():
            changes = messages[identifier]
            localized = {names[language][old]: names[language][new] for old, new in changes.items()}
            rewrite = (rewrites or {}).get(identifier, replace_names)
            edits[identifier] = partial(rewrite, changes=localized, language=language)
        found.update(edits)
        updated = patch_messages(bank, edits)
        if updated != bank:
            replacements[member["index"]] = updated
    if found != messages.keys():
        raise FormatError("missing reviewed species dialogue")
    return repack_fsys(source, replacements)[0] if replacements else source


def message_directory(source: bytes) -> dict[int, tuple[int, int]]:
    if source[:4] not in (bytes(4), b"\0\0\0\1"):
        raise FormatError("unexpected message header")
    count = u16(source, 4)
    directory_end = 16 + 8 * count
    check_range(source, 16, 8 * count, "message directory")
    rows = {}
    for position in range(16, directory_end, 8):
        identifier, pointer = struct.unpack_from(">II", source, position)
        identifier &= 0xFFFFF
        if identifier in rows or not directory_end <= pointer < len(source) - 1:
            raise FormatError("invalid message directory")
        rows[identifier] = (position, pointer)
    return rows


def patch_messages(source: bytes, edits: Mapping[int, Callable[[bytes], bytes]]) -> bytes:
    """Retarget selected IDs without moving or re-encoding unrelated dialogue."""
    rows = message_directory(source)
    if not edits.keys() <= rows.keys():
        raise FormatError("missing message")
    starts = sorted({pointer for _, pointer in rows.values()} | {len(source)})
    ends = dict(zip(starts, starts[1:]))
    result = bytearray(source)
    for identifier, edit in edits.items():
        position, pointer = rows[identifier]
        original = source[pointer:ends[pointer]]
        updated = edit(original)
        if updated != original:
            struct.pack_into(">I", result, position + 4, len(result))
            result.extend(updated)
    return bytes(result)
