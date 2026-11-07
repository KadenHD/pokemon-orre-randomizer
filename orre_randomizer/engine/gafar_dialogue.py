"""Name the actual opponents in Folly's first story battle at Phenac."""
from __future__ import annotations

from functools import partial

from .analyze_game import FormatError, parse_fsys, u32
from .inspect_tables import localized_names, u16
from .message_bank import patch_messages
from .randomize_trainers import layout
from .rebuild_iso import decoded_member, repack_fsys
from .rel_regions import region_for_rel


ARCHIVE_NAME = "M1_out.fsys"
MESSAGE_ID = 0x4E8D
_TRAINER = 12
_FIRST_SLOT = 49
_WHISMUR = 370
_NEW_PAGE = b"\xff\xff\x03"
_PAIR_TEXT = {
    "FR": ("GAFAR: Tu as rétamé mon {old}...", "GAFAR: {first} et {second} K.O. !"),
    "GE": (" meinen {old}", " {first} und {second}"),
    "IT": ("Hai sconfitto il mio {old}!", "Hai battuto {first} e {second}!"),
    "SP": ("NELO: Has derrotado a mis {old}...", "NELO: ¡{first} y {second} fuera!"),
    "UK": ("FOLLY: You took out my {old}...", "FOLLY: {first} and {second} lost!"),
    "JP": ("{old}を　", "{first}と{second}を　"),
}


def _victory_line(original: bytes, language: str, old: str, first: str, second: str) -> bytes:
    page, separator, remainder = original.partition(_NEW_PAGE)
    if not separator or not remainder.endswith(b"\xff\xff\x02\x00\x00"):
        raise FormatError("unexpected Phenac victory message controls")
    if first == second:
        needle, replacement = old, first
    else:
        needle, replacement = _PAIR_TEXT["UK" if language == "US" else language]
        needle = needle.format(old=old)
        replacement = replacement.format(first=first, second=second)
    before = needle.encode("utf-16-be")
    if page.count(before) != 1:
        raise FormatError(f"unexpected original Phenac victory text ({language})")
    return page.replace(before, replacement.encode("utf-16-be")) + separator + remainder


def patch_gafar_dialogue(source: bytes, original: bytes, current: bytes) -> tuple[bytes, tuple[int, int]]:
    """Use the final team slots so exclusions and trainer policies are respected."""
    region = region_for_rel(original)
    tables, symbols = layout(original)
    trainers, party, species = (tables[name] for name in ("trainers", "trainer_pokemon", "species"))
    trainer = trainers["offset"] + _TRAINER * trainers["stride"]
    start = u16(original, trainer + 4)
    offsets = [party["offset"] + (start + i) * party["stride"] + 0xA for i in range(2)]
    if start != _FIRST_SLOT or u16(current, trainer + 4) != start or any(
        u16(original, offset) != _WHISMUR for offset in offsets
    ):
        raise FormatError("unexpected original Phenac trainer team")
    first, second = (u16(current, offset) for offset in offsets)
    if first == second == _WHISMUR:
        return source, (first, second)

    names, _ = localized_names(original, symbols)
    name_ids = []
    for index in (_WHISMUR, first, second):
        position = species["offset"] + index * species["stride"]
        if not 0 < index < species["count"] or not 1 <= u16(original, position + 0x10) <= 386:
            raise FormatError("invalid Phenac dialogue species")
        name_ids.append(u32(original, position + 0x18))
    expected = set(region.native_languages)
    found = set()
    replacements = {}
    for member in parse_fsys(source)["members"]:
        if int(member["identifier_raw"], 16) & 0xFF00 != 0x0A00:
            continue
        bank = decoded_member(source, member)
        tag = bank[6:8]
        language = "JP" if tag == b"\0\0" else tag.decode("ascii", errors="replace")
        if language not in expected or language in found:
            raise FormatError("unexpected language in Phenac dialogue archive")
        found.add(language)
        localized = [names[language].get(identifier) for identifier in name_ids]
        if not all(localized):
            raise FormatError(f"missing native Phenac species name ({language})")
        replacements[member["index"]] = patch_messages(
            bank, {MESSAGE_ID: partial(_victory_line, language=language, old=localized[0],
                                       first=localized[1], second=localized[2])}
        )
    if found != expected:
        raise FormatError("missing playable language in Phenac dialogue archive")
    return repack_fsys(source, replacements)[0], (first, second)
