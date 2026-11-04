"""Regional Pokémon XD reward constructors and their localized offer text."""
from __future__ import annotations

from collections.abc import Callable, Collection, Mapping
from functools import partial
import struct

from .engine.analyze_game import FormatError, check_range, parse_fsys, u32
from .engine.inspect_tables import u16
from .engine.randomize_trainers import choose_species
from .engine.rebuild_iso import decoded_member, repack_fsys


GIFT_BASELINES = (
    ("hordel-trade", 239, 20),
    ("duking-trapinch", 356, 20),
    ("duking-surskit", 213, 20),
    ("duking-wooper", 246, 20),
    ("mt-battle-1", 152, 5),
    ("mt-battle-2", 155, 5),
    ("mt-battle-3", 158, 5),
)
GIFT_TRADE_REQUIREMENTS = {
    "hordel-trade": 175, "duking-trapinch": 332, "duking-surskit": 311, "duking-wooper": 194,
}

# Four trade constructors, the first Mt. Battle constructor, and its shared level.
_DOL_LAYOUT = {
    "GXXP01": ((0x1C70A0, 0x1C7184, 0x1C71D4, 0x1C7224), 0x1C7270, 0x1C6FE4),
    "GXXE01": ((0x1C57A4, 0x1C5888, 0x1C58D8, 0x1C5928), 0x1C5974, 0x1C56E8),
    "GXXJ01": ((0x1C0CB4, 0x1C0D1C, 0x1C0D6C, 0x1C0DBC), 0x1C0E08, 0x1C0BF8),
}
_REGIONAL_BANKS = {
    "GXXP01": frozenset(("FR", "GE", "IT", "SP", "UK")),
    "GXXE01": frozenset(("US",)),
    "GXXJ01": frozenset(("JP",)),
}
_MOVE_REGISTERS = (0x38C0, 0x38A0, 0x3880, 0x3800)
_TRADE_MOVES = (
    (8, 7, 9, 238),
    (223, 93, 247, 197),
    (92, 164, 188, 227),
    (201, 349, 44, 200),
)
_PRIZE_MOVES = (
    (246, 33, 45, 338),
    (179, 33, 43, 307),
    (242, 10, 43, 308),
)
_DUKING_NAME_WORDS = (
    (0xD30, 1307, 1328, 1653),
    (0xD74, 1213, 1283, 1654),
    (0xDB8, 1246, 1194, 1655),
)
_DUKING_SPECIES_WORDS = ((0xB48, 0xD1C), (0xB98, 0xD60), (0xBE8, 0xDA4))
_DUKING_REMAINING_NAMES = 0x1754
DUKING_TRADES = ("duking-trapinch", "duking-surskit", "duking-wooper")
HORDEL_SHADOW = 81
TOGEPI, TOGETIC = 175, 176
_HORDEL_GIFT_OFFSETS = {"GXXP01": 0x1C705C, "GXXE01": 0x1C5760, "GXXJ01": 0x1C0C70}
_HORDEL_GIFT_WORDS = (0x392000AF, 0x39000051, 0x38E00019, 0x38C0010A, 0x38A000A1, 0x388000F6,
                      0x3860010E, 0xB121000E, 0xB1010010, 0x98E1000D, 0xB0010012, 0xB0C10014,
                      0xB0A10016, 0xB0810018, 0xB061001A)
_HORDEL_OFFER_WORDS = ((TOGEPI, (0xF24, 0x1350, 0x18DC)),
                       (TOGETIC, (0xF34, 0x1100, 0x1200, 0x1330, 0x18B8)))
_HORDEL_OFFER_MESSAGES = (0xA42F, 0xA433, 0xA435, 0xA436)
_HORDEL_MESSAGES = (0xA438, 0xA43B, 0xA43C, 0xA43E, 0xA443)
_PRIZE_MESSAGES = (0x7A49, 0x7A4A, 0x7A4B)


def _native_name(banks: Mapping[str, Mapping[int, str]], language: str, national: int) -> str:
    name = banks.get(language, {}).get(1000 + national)
    if not name or len(name) > 10 or "\x00" in name or "\uffff" in name:
        raise FormatError(f"missing native XD species name {national} for {language}")
    return name


def _patch_messages(source: bytes, edits: Mapping[int, Callable[[bytes], bytes]]) -> bytes:
    """Retarget selected IDs without moving or re-encoding unrelated dialogue."""
    if source[:4] != bytes(4):
        raise FormatError("unexpected XD gift message header")
    count = u16(source, 4)
    check_range(source, 16, 8 * count, "XD gift message directory")
    rows = {}
    for position in range(16, 16 + 8 * count, 8):
        identifier, pointer = struct.unpack_from(">II", source, position)
        identifier &= 0xFFFFF
        if identifier in rows or not 16 + 8 * count <= pointer < len(source) - 1:
            raise FormatError("invalid XD gift message directory")
        rows[identifier] = (position, pointer)
    if not edits.keys() <= rows.keys():
        raise FormatError("missing XD gift message")
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


def _prize_label(original: bytes, expected: str, chosen: str) -> bytes:
    if original != expected.encode("utf-16-be") + b"\0\0":
        raise FormatError("unexpected original Mt. Battle prize label")
    return chosen.encode("utf-16-be") + b"\0\0"


def _hordel_dialogue(original: bytes, language: str, chosen: str) -> bytes:
    # Japanese messages use Elekid's native nickname. Keep the nickname on the
    # Pokémon itself, while the offer and reaction text identify the new species.
    expected = "コンセント" if language == "JP" else "ELEKID"
    old = expected.encode("utf-16-be")
    if original.count(old) != 1:
        raise FormatError("unexpected original Hordel reward name")
    # Correct the original articles when a replacement starts with a consonant.
    article = ("l'" + expected).encode("utf-16-be")
    word = chosen.casefold()
    starts_with_vowel = word[0] in "aeiouyàâäéèêëîïôöùûü"
    if language in ("FR", "IT") and article in original and not starts_with_vowel:
        prefix = "le " if language == "FR" else "il "
        if language == "IT" and (word.startswith(("z", "gn", "ps", "pn", "x"))
                                 or (len(word) > 1 and word[0] == "s" and word[1] not in "aeiou")):
            prefix = "lo "
        return original.replace(article, (prefix + chosen).encode("utf-16-be"), 1)
    if language == "FR" and not starts_with_vowel:
        demonstrative = ("cet " + expected).encode("utf-16-be")
        if demonstrative in original:
            return original.replace(demonstrative, ("ce " + chosen).encode("utf-16-be"), 1)
    return original.replace(old, chosen.encode("utf-16-be"), 1)


def _patch_banks(source: bytes, game_id: str, make_edits, *, languages=None) -> bytes:
    expected = _REGIONAL_BANKS[game_id] if languages is None else languages
    replacements = {}
    found = set()
    for member in parse_fsys(source)["members"]:
        if int(member["identifier_raw"], 16) & 0xFF00 != 0x0A00:
            continue
        original = decoded_member(source, member)
        language = original[6:8].decode("ascii", errors="replace")
        if language not in expected or language in found:
            raise FormatError("unexpected language in XD gift archive")
        found.add(language)
        replacements[member["index"]] = _patch_messages(original, make_edits(language))
    if found != expected:
        raise FormatError("missing playable language in XD gift archive")
    return repack_fsys(source, replacements)[0]


def _patch_script(source: bytes, name: str, edit) -> bytes:
    scripts = [member for member in parse_fsys(source)["members"]
               if member["name"] == name and int(member["identifier_raw"], 16) & 0xFF00 == 0x0E00]
    if len(scripts) != 1:
        raise FormatError(f"unexpected XD script {name}")
    member = scripts[0]
    original = decoded_member(source, member)
    if original[:4] != b"TCOD":
        raise FormatError(f"invalid XD script {name}")
    return repack_fsys(source, {member["index"]: edit(original)})[0]


def patch_species_operand(original, updated, offset, expected, species):
    check_range(original, offset - 4, 8, "XD script species operand")
    if struct.unpack_from(">II", original, offset - 4) != (0x02010000, expected):
        raise FormatError("unexpected XD script species operand")
    struct.pack_into(">I", updated, offset, species)


def _duking_script(original, reward_name_ids, outgoing):
    updated = bytearray(original)
    for slot, ((offset, expected, requirement, flag), reward_name_id) in enumerate(
        zip(_DUKING_NAME_WORDS, reward_name_ids, strict=True)
    ):
        check_range(original, offset - 4, 0x24, "Duking trade call")
        call = struct.unpack_from(">9I", original, offset - 4)
        if call != (0x02010000, expected, 0x02010000, requirement, 0x02010000,
                    flag, 0x0301FFFB, 0x0700031B, 0x06040000):
            raise FormatError("unexpected XD Duking trade name instruction")
        struct.pack_into(">I", updated, offset, reward_name_id)
        if outgoing is not None:
            species, name_id = outgoing[slot]
            old = GIFT_TRADE_REQUIREMENTS[DUKING_TRADES[slot]]
            for position in _DUKING_SPECIES_WORDS[slot]:
                patch_species_operand(original, updated, position, old, species)
            struct.pack_into(">I", updated, offset + 8, name_id)
            # The one- and two-species prompts read their names from ARRY.
            entry = _DUKING_REMAINING_NAMES + 8 * slot
            check_range(original, entry - 4, 8, "Duking remaining trade name")
            if original[0x16F0:0x16F4] != b"ARRY" or struct.unpack_from(">II", original, entry - 4) != (
                0x00010000, requirement,
            ):
                raise FormatError("unexpected XD Duking remaining trade name")
            struct.pack_into(">I", updated, entry, name_id)
    return bytes(updated)


def _patch_duking(source: bytes, reward_name_ids: list[int], outgoing=None) -> bytes:
    return _patch_script(source, "M2_guild_1F_2", lambda raw: _duking_script(raw, reward_name_ids, outgoing))


def replace_species_name(original, language, old, chosen):
    encoded = old.encode("utf-16-be")
    if original.count(encoded) != 1:
        raise FormatError(f"unexpected localized XD species name {old}")
    begins_with_vowel = chosen[0].casefold() in "aeiouyàâäéèêëîïôöùûü"
    articles = ()
    if language == "FR":
        articles = (("Le ", "L'" if begins_with_vowel else "Le "),
                    ("le ", "l'" if begins_with_vowel else "le "),
                    ("L'", "L'" if begins_with_vowel else "Le "),
                    ("l'", "l'" if begins_with_vowel else "le "))
    elif language == "IT":
        lower = chosen.casefold()
        special = lower.startswith(("z", "gn", "ps", "pn", "x")) or (
            len(lower) > 1 and lower[0] == "s" and lower[1] not in "aeiou")
        article = "l'" if begins_with_vowel else "lo " if special else "il "
        articles = (("il ", article), ("Il ", article.capitalize()))
    elif language in ("UK", "US"):
        articles = (("a ", "an " if begins_with_vowel else "a "),)
    for before, after in articles:
        phrase = (before + old).encode("utf-16-be")
        if phrase in original:
            return original.replace(phrase, (after + chosen).encode("utf-16-be"), 1)
    return original.replace(encoded, chosen.encode("utf-16-be"), 1)


def _hordel_offer_script(original, base, evolved):
    updated = bytearray(original)
    for (expected, offsets), chosen in zip(_HORDEL_OFFER_WORDS, (base, evolved), strict=True):
        for offset in offsets:
            patch_species_operand(original, updated, offset, expected, chosen)
    return bytes(updated)


def patch_hordel_gift(dol, source, game_id, base, evolved, national, name_banks):
    """Retarget the gift and the two accepted forms while keeping its native Shadow ID."""
    offset = _HORDEL_GIFT_OFFSETS[game_id]
    check_range(dol, offset, 4 * len(_HORDEL_GIFT_WORDS), "XD Hordel gift constructor")
    if struct.unpack_from(f">{len(_HORDEL_GIFT_WORDS)}I", dol, offset) != _HORDEL_GIFT_WORDS:
        raise FormatError("unexpected XD Hordel gift constructor")
    updated = bytearray(dol)
    struct.pack_into(">H", updated, offset + 2, base)

    def edits(language):
        old = _native_name(name_banks, language, TOGEPI)
        new = _native_name(name_banks, language, national)
        return dict.fromkeys(_HORDEL_OFFER_MESSAGES, partial(replace_species_name, language=language,
                                                            old=old, chosen=new))

    source = _patch_script(source, "S1_shop_1F", partial(_hordel_offer_script, base=base, evolved=evolved))
    return bytes(updated), _patch_banks(source, game_id, edits)


def patch_gifts(
    dol: bytes, game_id: str, seed: str, species: Mapping[int, tuple],
    families: Mapping[int, int], reserved_families: Collection[int],
    read_archive: Callable[[str], bytes], *, name_banks: Mapping[str, Mapping[int, str]],
    eligible: Collection[int] | None = None, balance: bool = True, replace_species: bool = True,
    move_randomizer=None, trade_requirements: Mapping[str, int] = GIFT_TRADE_REQUIREMENTS,
    hordel_evolution: int | None = None,
) -> tuple[bytes, dict[str, bytes], list[dict]]:
    """Apply XD reward settings and synchronize the species requested by Duking."""
    trade_offsets, prize_base, prize_level = _DOL_LAYOUT[game_id]
    if u32(dol, prize_level) != 0x38A00005:
        raise FormatError("unexpected XD Mt. Battle reward level")
    used = set(reserved_families)
    updated = bytearray(dol)
    rows = []
    for slot, (key, original, level) in enumerate(GIFT_BASELINES):
        trade = slot < len(trade_offsets)
        if trade:
            offset = trade_offsets[slot]
            moves = _TRADE_MOVES[slot]
            registers = (0x38E0, 0x38C0, 0x38A0, 0x3800) if game_id == "GXXJ01" and slot == 0 else _MOVE_REGISTERS
            if u32(dol, offset + 8) != 0x38A00014:
                raise FormatError("unexpected XD trade reward level")
            move_offset = offset + 0x24
        else:
            prize = slot - len(trade_offsets)
            offset = prize_base + prize * 0x2C
            moves = _PRIZE_MOVES[prize]
            registers = (0x38A0, 0x3880, 0x3860, 0x3800)
            move_offset = offset + 4
        if u32(dol, offset) != 0x38C00000 | original or any(
            u32(dol, move_offset + i * 4) != register << 16 | move
            for i, (register, move) in enumerate(zip(registers, moves, strict=True))
        ):
            raise FormatError(f"unexpected XD {key} reward instructions")
        chosen = original
        if replace_species:
            excluded = {original}
            required = trade_requirements.get(key)
            if required != GIFT_TRADE_REQUIREMENTS.get(key):
                excluded.add(required)
            if key == "hordel-trade" and hordel_evolution is not None:
                excluded.add(hordel_evolution)
            pool = sorted(set(species if eligible is None else eligible) - excluded)
            candidates = [index for index in pool if families[index] not in used] or pool
            if not candidates:
                raise FormatError(f"no eligible XD gift species for {key}")
            if balance:
                original_total = species[original][2]
                candidates = sorted(candidates, key=lambda index: (abs(species[index][2] - original_total), index))[:40]
            chosen = choose_species(seed, "xd-gift-sha256-v1:" + key, candidates, original)
            struct.pack_into(">H", updated, offset + 2, chosen)
        if move_randomizer is not None:
            moves = move_randomizer.moves(seed, f"xd:gift:{key}", chosen, level, moves)
            for i, move in enumerate(moves):
                struct.pack_into(">H", updated, move_offset + 2 + i * 4, move)
        used.add(families[chosen])
        row = {"key": key, "original": original, "species": chosen, "family": families[chosen],
               "level": level, "moves": list(moves)}
        if trade:
            row["required_species"] = trade_requirements[key]
        if key == "hordel-trade" and hordel_evolution is not None:
            row["required_evolution"] = hordel_evolution
        rows.append(row)

    spot_trades = any(trade_requirements[key] != GIFT_TRADE_REQUIREMENTS[key] for key in DUKING_TRADES)

    def prize_edits(language):
        return {
            message: partial(
                _prize_label,
                expected=_native_name(name_banks, language, species[row["original"]][0]),
                chosen=_native_name(name_banks, language, species[row["species"]][0]),
            )
            for message, row in zip(_PRIZE_MESSAGES, rows[4:], strict=True)
        }

    def hordel_edits(language):
        chosen = _native_name(name_banks, language, species[rows[0]["species"]][0])
        return {message: lambda before: _hordel_dialogue(before, language, chosen)
                for message in _HORDEL_MESSAGES}

    def spot_edits(language, message_ids):
        def edit(before):
            for key in DUKING_TRADES:
                old = _native_name(name_banks, language, species[GIFT_TRADE_REQUIREMENTS[key]][0])
                new = _native_name(name_banks, language, species[trade_requirements[key]][0])
                before = replace_species_name(before, language, old, new)
            return before
        return dict.fromkeys(message_ids, edit)

    crater = "D2_crater_colo.fsys"
    pyrite = "M2_guild_1F_2.fsys"
    outskirt = "S1_shop_1F.fsys"
    archives = {}
    if replace_species:
        archives[crater] = _patch_banks(read_archive(crater), game_id, prize_edits)
        archives[outskirt] = _patch_banks(read_archive(outskirt), game_id, hordel_edits)
    if replace_species or spot_trades:
        outgoing = [(trade_requirements[key], 1000 + species[trade_requirements[key]][0]) for key in DUKING_TRADES]
        archives[pyrite] = _patch_duking(read_archive(pyrite), [1000 + species[row["species"]][0] for row in rows[1:4]],
                                        outgoing if spot_trades else None)
    if spot_trades:
        spot = "esaba_B.fsys"
        archives[pyrite] = _patch_banks(archives[pyrite], game_id, lambda lang: spot_edits(lang, (0x9172, 0x9174)))
        archives[spot] = _patch_banks(read_archive(spot), game_id, lambda lang: spot_edits(lang, (0xB1BE,)))
    return bytes(updated), archives, rows
