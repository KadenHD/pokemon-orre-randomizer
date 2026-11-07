"""Synchronize the Mt. Battle reward presentation with its native gift constructor."""

import struct

from .analyze_game import FormatError, check_range, parse_dol, u32
from .dol_regions import dol_layout
from .gift_move_hooks import TEXT_TO_RAM, _arena_guard, _words, branch
from .inspect_tables import localized_names, u16
from .randomize_trainers import layout
from .rel_regions import region_for_rel
from .species_rules import species_catalog


_HO_OH = 250
_MESSAGE_IDS = (0x44B9, 0x44BA, 0x44BB, 0x44BC)
_NEXT_MESSAGE = 0x44C4
# d2presentPlayGiftScene resolves the battle model and the cry separately.
_SCENE = {
    "GC6P01": (0x267B7C, 0x267C4C),
    "GC6E01": (0x262F9C, 0x26306C),
    "GC6J01": (0x25E6C0, 0x25E790),
}
# Final heroGetPokemon call (gift constructor + 0xA0), native shiny test,
# and the sequence model constructor used by the presentation.
_APPEARANCE = {
    "GC6P01": (0x8012DFE8, 0x80129504, 0x801E2A04),
    "GC6E01": (0x80129E20, 0x80125390, 0x801DE190),
    "GC6J01": (0x8012755C, 0x80122B30, 0x801D9B04),
}
# Language, main.dol bank, common.rel mirror when present.
_BANKS = {
    "GC6P01": (("UK", 0x2C1B20, 0x995EC), ("GE", 0x2D3FA0, 0xABA6C),
               ("FR", 0x2E73B0, 0xBEE7C), ("IT", 0x2FA2D8, 0xD1DA4),
               ("SP", 0x30D714, 0xE51E0)),
    "GC6E01": (("US", 0x2CC810, 0x66000),),
    "GC6J01": (("JP", 0x2BECE0, None),),
}
_TEXTS = {
    "UK": ("Your party and PC are full.\nThere is no room for {name}.\fMake room and try again.",
           "{name} arrived to celebrate\nyour mastery of purification\nand battling!",
           "{name} was sent to the PC!", "You received {name}!"),
    "GE": ("Dein Team und dein PC sind voll.\nKein Platz für {name}.\fMach Platz und versuch es erneut.",
           "{name} gratuliert dir zu deinen\nKämpfen und Crypto-Erlösungen!",
           "{name} wurde auf\nden PC übertragen!", "Du erhältst {name}!"),
    "FR": ("Votre équipe et le PC sont pleins.\nVous ne pouvez pas recevoir {name}.\fFaites de la place et revenez.",
           "{name} vient vous féliciter\npour vos victoires et votre\nmaîtrise de la purification !",
           "{name} a été envoyé au PC.", "Vous obtenez {name} !"),
    "IT": ("La squadra e il PC sono pieni.\nNon c'è spazio per {name}.\fFai spazio e torna a lottare.",
           "Ecco {name}!\nComplimenti per le tue vittorie\ne le purificazioni!",
           "{name} è ora nel PC!", "Hai ottenuto {name}!"),
    "SP": ("Tu equipo y tu PC están llenos.\nNo hay sitio para {name}.\fHaz sitio y vuelve a combatir.",
           "¡{name} celebra tus victorias\ny tu dominio de la purificación!",
           "¡{name} se ha enviado al PC!", "¡Has obtenido a {name}!"),
    "JP": ("てもちも　パソコンも　いっぱいです。\n{name}を　うけとれません。\fあきを　つくってから\nまた　ちょうせんしてください。",
           "リライブと　バトルの\nうでまえを　おいわいして\n{name}が　やってきた！",
           "{name}は　パソコンに\nおくられた！", "{name}を　てにいれた！"),
}
_PREFIX = b"\xff\xff\x07\x00"
_END = b"\xff\xff\x02\x00\x00"
_SUCCESS = b"\xff\xff\x5d\xff\xff\x5e" + _END


def _encode_dialogue(template: str, name: str, suffix: bytes) -> bytes:
    pages = template.format(name=name).split("\f")
    body = b"\xff\xff\x03".join(
        b"\xff\xff\x00".join(line.encode("utf-16-be") for line in page.split("\n"))
        for page in pages
    )
    return _PREFIX + body + suffix


def _patch_bank(original: bytes, output: bytearray, base: int, language: str, name: str) -> None:
    count = u16(original, base + 4)
    directory = base + 16
    check_range(original, directory, count * 8, "Ho-Oh message directory")
    original_directory = original[directory:directory + count * 8]
    if output[directory:directory + count * 8] != original_directory:
        raise FormatError("Ho-Oh message directory was already modified")
    rows = list(struct.iter_unpack(">II", original_directory))
    targets = (*_MESSAGE_IDS, _NEXT_MESSAGE)
    first = next((i for i, (identifier, _) in enumerate(rows) if identifier == targets[0]), -1)
    selected = rows[first:first + len(targets)] if first >= 0 else []
    if tuple(identifier for identifier, _ in selected) != targets:
        raise FormatError("unexpected Ho-Oh reward message IDs")
    offsets = [offset for _, offset in selected]
    if offsets != sorted(set(offsets)) or offsets[0] < 16 + count * 8:
        raise FormatError("unexpected Ho-Oh reward message positions")
    if any(offsets[0] <= offset < offsets[-1] and identifier not in _MESSAGE_IDS for identifier, offset in rows):
        raise FormatError("another message shares Ho-Oh dialogue storage")
    start, end = base + offsets[0], base + offsets[-1]
    check_range(original, start, end - start, "Ho-Oh reward messages")
    if output[start:end] != original[start:end]:
        raise FormatError("Ho-Oh reward messages were already modified")

    # Keep the original window and message endings, including the award fanfare.
    arrival_end = {"FR": b"\x00\x00", "IT": b"\xff\xff\x00\x00\x00"}.get(language, _END)
    suffixes = (_END, arrival_end, _SUCCESS, _SUCCESS)
    templates = _TEXTS["UK" if language == "US" else language]
    old_name = ("ホウオウ" if language == "JP" else "HO-OH").encode("utf-16-be")
    payload = bytearray()
    pointers = []
    for index, (template, suffix) in enumerate(zip(templates, suffixes, strict=True)):
        raw = original[base + offsets[index]:base + offsets[index + 1]]
        expected_names = 0 if language == "SP" and index == 0 else 1
        if not raw.startswith(_PREFIX) or not raw.endswith(suffix) or raw.count(old_name) != expected_names:
            raise FormatError("unexpected native Ho-Oh reward text")
        pointers.append(offsets[0] + len(payload))
        payload.extend(_encode_dialogue(template, name, suffix))
    if len(payload) > end - start:
        raise FormatError("localized Ho-Oh dialogue does not fit its native allocation")
    for index, offset in enumerate(pointers, start=first):
        struct.pack_into(">I", output, directory + index * 8 + 4, offset)
    output[start:end] = payload.ljust(end - start, b"\x00")


def _sync_appearance(original: bytes, current: bytes, region) -> bytes:
    # Reserve two transient words in text2. The gift writes them immediately
    # before the native handover, including when the party and PC are full.
    # The scene then consumes them once, after the warp to the reward room.
    award, check_rare, load_model = _APPEARANCE[region.game_id]
    award_call = region.special_offsets[3] + 0xA0 + TEXT_TO_RAM
    model_call = _SCENE[region.game_id][0] + 0x48 + TEXT_TO_RAM
    for call, native in ((award_call, award), (model_call, load_model)):
        expected = branch(call, native, link=True)
        if any(u32(data, call - TEXT_TO_RAM) != expected for data in (original, current)):
            raise FormatError("unexpected native Mt. Battle appearance hook")
    model_args = model_call - TEXT_TO_RAM - 8
    if current[model_args:model_args + 8] != bytes.fromhex("38800000 38a00000"):
        raise FormatError("unexpected native Mt. Battle model parameters")
    section_offset = (len(original) + 31) & ~31
    previous_size = u32(current, 0x98)
    arena_offset = region.set_arena_lo - TEXT_TO_RAM
    if any(u32(original, offset) for offset in (0x08, 0x50, 0x98)):
        raise FormatError("original Mt. Battle DOL text2 slot is occupied")
    if previous_size:
        if ((u32(current, 0x08), u32(current, 0x50)) != (section_offset, region.section_ram)
                or previous_size % 32 or section_offset + previous_size != len(current)
                or u32(current, arena_offset) != branch(region.set_arena_lo, region.section_ram)
                or current[section_offset:section_offset + 32] != _arena_guard(
                    region.section_ram + previous_size, region.arena_lo_store)):
            raise FormatError("unsupported existing DOL reservation before Mt. Battle hooks")
        code = bytearray(current[section_offset:])
    else:
        if (len(current) != len(original) or any(u32(current, offset) for offset in (0x08, 0x50))
                or u32(current, arena_offset) != region.arena_lo_store):
            raise FormatError("unexpected DOL layout before Mt. Battle hooks")
        code = bytearray(32)

    state = region.section_ram + len(code)
    code.extend(bytes(32))
    state_high = 0x3D800000 | (state >> 16)  # lis r12, state@h
    state_low = 0x618C0000 | (state & 0xFFFF)  # ori r12, r12, state@l
    award_stub = region.section_ram + len(code)
    award_words = [
        0x9421FFD0, 0x7C0802A6, 0x90010034,   # stack frame, save LR
        0x90610008, 0x9081000C, 0x90A10010,   # save the three handover arguments
        0x7C832378,                            # mr r3, r4: completed Pokémon buffer
    ]
    award_words.append(branch(award_stub + 4 * len(award_words), check_rare, link=True))
    award_words.extend([
        state_high, state_low, 0x906C0004,     # stw r3, 4(r12): native shiny result
        0x8081000C, 0x80040004, 0x900C0000,   # store the native Pokémon personality
        0x80610008, 0x80A10010,
        0x80010034, 0x7C0803A6, 0x38210030,   # restore arguments, LR and stack
    ])
    award_words.append(branch(award_stub + 4 * len(award_words), award))
    code.extend(_words(award_words))
    model_stub = region.section_ram + len(code)
    model_words = [
        state_high, state_low,
        0x808C0000, 0x80AC0004,               # r4 = personality, r5 = shiny variant
        0x38000000, 0x900C0000, 0x900C0004,   # reset the transient handover values
    ]
    model_words.append(branch(model_stub + 4 * len(model_words), load_model))
    code.extend(_words(model_words))
    code.extend(bytes((-len(code)) % 32))
    reserved_end = region.section_ram + len(code)
    descriptor = parse_dol(original)
    if (descriptor["bss_ram_address"] + descriptor["bss_size"] >= region.section_ram
            or reserved_end >= 0x81700000):
        raise FormatError("Mt. Battle hooks exceed the available arena")
    code[:32] = _arena_guard(reserved_end, region.arena_lo_store)
    output = bytearray(current[:section_offset])
    output.extend(bytes(section_offset - len(output)))
    output.extend(code)
    for offset, word in (
        (0x08, section_offset), (0x50, region.section_ram), (0x98, len(code)),
        (arena_offset, branch(region.set_arena_lo, region.section_ram)),
        (award_call - TEXT_TO_RAM, branch(award_call, award_stub, link=True)),
        (model_call - TEXT_TO_RAM, branch(model_call, model_stub, link=True)),
    ):
        struct.pack_into(">I", output, offset, word)
    return bytes(output)


def patch_hooh_reward_scene(original_dol: bytes, current_dol: bytes,
                            original_rel: bytes, current_rel: bytes, *,
                            sync_native_gift: bool = False) -> tuple[bytes, bytes, dict]:
    """Use the final gift species and its actual appearance in the prize scene."""
    dol_region = dol_layout(original_dol)
    rel_region = region_for_rel(original_rel)
    if dol_region.game_id != rel_region.game_id or len(current_rel) != len(original_rel):
        raise FormatError("Ho-Oh gift DOL and REL are incompatible")
    gift = dol_region.special_offsets[3]
    constructor = u32(current_dol, gift)
    if u32(original_dol, gift) != 0x388000FA or constructor & 0xFFFF0000 != 0x38800000:
        raise FormatError("unexpected Ho-Oh reward constructor")
    species = constructor & 0xFFFF
    if species == _HO_OH:
        if sync_native_gift:
            dol = _sync_appearance(original_dol, current_dol, dol_region)
            return dol, current_rel, {"applied": True, "species": species, "languages": [],
                                      "appearance_from_reward": True}
        return current_dol, current_rel, {"applied": False}

    tables, symbols = layout(original_rel)
    catalog = species_catalog(original_rel, tables)
    if species not in catalog:
        raise FormatError("Ho-Oh reward species is outside the Pokédex")
    name_id = u32(original_rel, catalog[species]["offset"] + 0x18)
    names, _ = localized_names(original_rel, symbols)
    dol, rel = bytearray(current_dol), bytearray(current_rel)
    for offset, word in zip(_SCENE[dol_region.game_id], (0x388000FA, 0x386000FA), strict=True):
        if u32(original_dol, offset) != word or u32(dol, offset) != word:
            raise FormatError("unexpected Ho-Oh reward presentation instruction")
        struct.pack_into(">H", dol, offset + 2, species)

    languages = []
    for language, dol_bank, rel_bank in _BANKS[dol_region.game_id]:
        name = names[language].get(name_id)
        if not name or len(name) > 10 or any(char in name for char in "\x00\uffff\n\f"):
            raise FormatError(f"missing native Ho-Oh reward species name for {language}")
        _patch_bank(original_dol, dol, dol_bank, language, name)
        if rel_bank is not None:
            _patch_bank(original_rel, rel, rel_bank, language, name)
        languages.append(language)
    return _sync_appearance(original_dol, bytes(dol), dol_region), bytes(rel), {
        "applied": True, "species": species, "languages": languages, "appearance_from_reward": True}
