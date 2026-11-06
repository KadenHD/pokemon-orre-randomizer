"""Keep Pyrite's rescue and handover text tied to Doking's actual gift."""
from __future__ import annotations

import struct

from ..locales.selection_names import SPECIES_NAMES
from .analyze_game import FormatError, check_range, parse_fsys
from .inspect_tables import u16
from .rebuild_iso import decoded_member, repack_fsys


PLUSLE_DEX = 311

# Native IDs shared by all text banks unless explicitly noted below.
_MESSAGE_IDS = {
    "M2_building_1F.fsys": (0x4FDD, 0x5060, 0x5063, 0x511C),
    "M2_building_4F.fsys": (0x5B32, 0x5B34),
    "M2_cave_1F_2.fsys": (0x5AB9, 0x5B31, 0x5B40, 0x5B43),
    "M2_guild_1F_1.fsys": (0x5A8A, 0x5A8B, 0x5B04, 0x5B18, 0x5B1D, 0x5B1E),
    "M2_guild_1F_2.fsys": (0x50E0, 0x511D, 0x5558, 0x5A57, 0x5A69),
}
ARCHIVE_NAMES = tuple(_MESSAGE_IDS)
_LANGUAGES = {
    "GC6P01": {"FR": "fr", "GE": "de", "IT": "it", "SP": "es", "UK": "en"},
    "GC6E01": {"US": "en"},
    "GC6J01": {"\0\0": "ja"},
}
# CMS std218 plays the cry of its single internal species argument. Both
# regional cave layouts contain the same calls, at different code offsets.
_CRY_COUNTS = {"M2_cave_1F_2.fsys": 5, "M2_guild_1F_1.fsys": 2}
_CRY_MESSAGES = {
    "M2_cave_1F_2.fsys": (0x5A81, 0x5A84, 0x5A86, 0x5A88),
    "M2_guild_1F_1.fsys": (0x5AF5, 0x5AF6),
}
_CRY_PREFIX = bytes.fromhex("080200000000104200010802000000da0802")
_CRY_SUFFIX = bytes.fromhex("250001000203820001")
_PLUSLE_CRY = _CRY_PREFIX + struct.pack(">I", 353) + _CRY_SUFFIX


def _expected_names(archive_name: str, language: str) -> dict[int, int]:
    counts = dict.fromkeys(_MESSAGE_IDS[archive_name], 1)
    if archive_name == "M2_building_1F.fsys" and language == "ja":
        del counts[0x5060]
    if language == "de":
        if archive_name == "M2_building_4F.fsys":
            counts[0x5B37] = 1
        if archive_name == "M2_guild_1F_1.fsys":
            counts[0x5A8D] = 1
    if archive_name == "M2_guild_1F_1.fsys" and language != "it":
        counts[0x5B04] = 2
    return counts


def _patch_bank(source: bytes, archive_name: str, language: str, chosen: str) -> bytes:
    if source[:4] != bytes(4):
        raise FormatError("unexpected Pyrite message header")
    count = u16(source, 4)
    directory_end = 16 + 8 * count
    check_range(source, 16, 8 * count, "Pyrite message directory")
    rows = {}
    for position in range(16, directory_end, 8):
        identifier, pointer = struct.unpack_from(">II", source, position)
        identifier &= 0xFFFFF
        if identifier in rows or not directory_end <= pointer <= len(source) - 2:
            raise FormatError("invalid Pyrite message directory")
        rows[identifier] = (position, pointer)

    old_name = SPECIES_NAMES[language][PLUSLE_DEX].upper()
    native = old_name.encode("utf-16-be")
    chosen_bytes = chosen.encode("utf-16-be")
    starts = sorted({pointer for _, pointer in rows.values()} | {len(source)})
    ends = dict(zip(starts, starts[1:]))
    original_messages = {
        identifier: source[pointer:ends[pointer]]
        for identifier, (_, pointer) in rows.items()
    }
    occurrences = {identifier: message.count(native)
                   for identifier, message in original_messages.items() if native in message}
    if occurrences != _expected_names(archive_name, language):
        raise FormatError(f"unexpected Plusle dialogue in {archive_name} ({language})")

    replacements = {}
    for identifier in occurrences:
        message = original_messages[identifier]
        if language == "fr" and chosen[0].lower() in "aeiouyàâäéèêëîïôöùûü":
            message = message.replace(("de " + old_name).encode("utf-16-be"),
                                      ("d'" + old_name).encode("utf-16-be"))
            message = message.replace(("le " + old_name).encode("utf-16-be"),
                                      ("l'" + old_name).encode("utf-16-be"))
            message = message.replace(b"\x00l\x00e\xff\xff\x00" + native,
                                      b"\xff\xff\x00\x00l\x00'" + native)
        replacements[identifier] = message.replace(native, chosen_bytes)

    # The game plays the actual cry. Keep the speaker icon and use the
    # localized name in place of the written imitation of Plusle's cry.
    prefix = ("＊「" if language == "ja" else "‱: ").encode("utf-16-be")
    exclamation = ("！" if language == "ja" else "!").encode("utf-16-be")
    terminator = b"\xff\xff\x02\x00\x00"
    for identifier in _CRY_MESSAGES.get(archive_name, ()):
        message = original_messages.get(identifier, b"")
        if not message.startswith(prefix) or not message.endswith(terminator):
            raise FormatError("unexpected original Pyrite cry caption")
        replacements[identifier] = prefix + chosen_bytes + exclamation + terminator

    # Append only changed records and redirect their pointers. Existing text
    # and byte-sized control parameters remain exactly where they were.
    output = bytearray(source)
    relocated = {}
    for identifier, message in replacements.items():
        position, pointer = rows[identifier]
        if pointer not in relocated:
            relocated[pointer] = len(output)
            output.extend(message)
        struct.pack_into(">I", output, position + 4, relocated[pointer])
    return bytes(output)


def patch_dialogue(source: bytes, archive_name: str, game_id: str, national_dex: int,
                   *, species_id: int | None = None) -> bytes:
    """Retarget the native dialogue and, with an internal species ID, its cries."""
    if national_dex == PLUSLE_DEX:
        return source
    if game_id not in _LANGUAGES or archive_name not in _MESSAGE_IDS:
        raise FormatError("unsupported Plusle dialogue layout")

    expected = _LANGUAGES[game_id]
    found = set()
    replacements = {}
    members = parse_fsys(source)["members"]
    if species_id is not None and archive_name in _CRY_COUNTS:
        scripts = [member for member in members if int(member["identifier_raw"], 16) & 0xFF00 == 0x0E00]
        if len(scripts) != 1 or not 1 <= species_id <= 411:
            raise FormatError("unexpected Pyrite cry script or replacement species")
        script = decoded_member(source, scripts[0])
        if script.count(_PLUSLE_CRY) != _CRY_COUNTS[archive_name]:
            raise FormatError("unexpected original Plusle cry calls")
        cry = _CRY_PREFIX + struct.pack(">I", species_id) + _CRY_SUFFIX
        replacements[scripts[0]["index"]] = script.replace(_PLUSLE_CRY, cry)
    for member in members:
        if int(member["identifier_raw"], 16) & 0xFF00 != 0x0A00:
            continue
        bank = decoded_member(source, member)
        tag = bank[6:8].decode("ascii", errors="replace")
        if tag not in expected or tag in found:
            raise FormatError("unexpected language in Pyrite dialogue archive")
        found.add(tag)
        language = expected[tag]
        name = SPECIES_NAMES[language].get(national_dex)
        if name is None:
            raise FormatError("invalid replacement species for Plusle dialogue")
        replacements[member["index"]] = _patch_bank(
            bank, archive_name, language, name.upper().replace("’", "'")
        )
    if found != expected.keys():
        raise FormatError("missing playable language in Pyrite dialogue archive")
    return repack_fsys(source, replacements)[0]
