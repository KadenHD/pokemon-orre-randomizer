"""Keep the Colosseum DNA samples, analyzer and keypad in sync with Shadow encounters."""

from collections import Counter
from functools import partial
import struct

from .analyze_game import FormatError, parse_dol, parse_fsys, u32
from .colo_spinda import colo_spinda_shadow_traits
from .dna_keypad import DNA_KEYPAD_SPECIES, patch_dna_keypad
from .dol_regions import dol_layout
from .gift_move_hooks import TEXT_TO_RAM, _arena_guard, branch
from .inspect_tables import localized_names, u16
from .message_bank import patch_messages
from .randomize_trainers import layout
from .rebuild_iso import decoded_member, repack_fsys
from .shiny_rules import _Code
from .spinda import SPINDA


_SAMPLE_SPECIES = (153, 156, 159, 185, 200, 287, 243, 244, 245)
_MIGHTYENA = 287  # One of the samples, but there is no Shadow Mightyena encounter.
_ANALYZER = {
    "GC6P01": (0x801CCBA8, 0x80078BD0),
    "GC6E01": (0x801C8834, 0x800756C8),
    "GC6J01": (0x801C4384, 0x80074798),
}
_DNA_MODEL = 0x2000
_DNA_SHINY = 0x4000


def dna_appearances(original_rel, current_rel, options, shiny_report):
    if not (options.randomize_shadows or options.custom_shinies):
        return {}
    shadow_shinies = shiny_report.get("seeded_decisions", {}).get("shadows", {})
    guaranteed = options.custom_shinies and options.shiny_chance_percent == 100
    tables, _ = layout(original_rel)
    shadow = tables["shadow"]
    appearances = {_MIGHTYENA: (_MIGHTYENA, False)}
    for shadow_id in range(1, shadow["count"]):
        position = shadow["offset"] + shadow_id * shadow["stride"] + 2
        old = u16(original_rel, position)
        if old not in _SAMPLE_SPECIES or old == _MIGHTYENA:
            continue
        if old in appearances:
            raise FormatError("ambiguous original Shadow encounter for a DNA sample")
        appearances[old] = (u16(current_rel, position), shadow_shinies.get(str(shadow_id), guaranteed))
    if appearances.keys() != set(_SAMPLE_SPECIES):
        raise FormatError("missing original Shadow encounter for a DNA sample")
    return appearances if options.custom_shinies or any(
        old != new for old, (new, _) in appearances.items()) else {}


def dna_spinda_samples(original_rel, current_rel, appearances, options, shiny_report):
    pid = shiny_report.get("spinda_pid")
    if not pid or not any(species == SPINDA for species, _ in appearances.values()):
        return {}
    traits = colo_spinda_shadow_traits(original_rel, current_rel)
    shadow = layout(original_rel)[0]["shadow"]
    predictable = options.custom_shinies and (options.seeded_shinies or options.shiny_chance_percent in (0, 100))
    samples = {}
    for shadow_id in range(1, shadow["count"]):
        position = shadow["offset"] + shadow_id * shadow["stride"] + 2
        old = u16(original_rel, position)
        if old in appearances and appearances[old][0] == SPINDA:
            key = f"shadow:{shadow_id}"
            seed = pid["seeds"].get(key)
            mode = int(appearances[old][1]) if predictable and seed and shadow_id in traits else None
            samples[old] = (shadow_id, seed, traits.get(shadow_id), mode)
    return samples


def _player_owner(code, region, unavailable):
    pointer = region.player_pointer
    code.emit(0x3CE00000 | (pointer >> 16), 0x60E70000 | (pointer & 0xFFFF),
              0x80E70000, 0x28070000)
    code.conditional(0x41820000, unavailable)
    code.emit(0x80E7009C)  # lwz r7,0x9c(r7): current player SID/TID


def _emit_sample_pid(code, region, old, sample, pid, unavailable):
    """Resolve the saved or seeded PID into r3 and the current owner into r7."""
    shadow_id, seed, traits, mode = sample
    code.emit(0x38600000 | shadow_id)
    code.call(pid["shadow_generated"])
    code.emit(0x5460063E, 0x28000001)  # native generated flag is a byte
    code.conditional(0x40820000, f"new_{old}")
    code.emit(0x38600000 | shadow_id)
    code.call(pid["stored_shadow_pid"])
    code.jump(f"owner_{old}")
    code.label(f"new_{old}")
    if mode is None:
        code.jump(unavailable)
    else:
        _player_owner(code, region, unavailable)
        gender, nature = traits
        code.emit(0x80610008, 0x38800000 | (gender & 0xFFFF), 0x38A00000 | (nature & 0xFFFF),
                  0x38C00000 | mode, 0x3D000000 | (seed >> 16), 0x61080000 | (seed & 0xFFFF))
        code.call(pid["resolver"])
    code.label(f"owner_{old}")
    _player_owner(code, region, unavailable)


def _emit_spinda_samples(code, region, samples, pid):
    code.emit(0x5484BF3E)  # extrwi r4,r4,4,19: sample index in bits 9..12
    for old in samples:
        index = _SAMPLE_SPECIES.index(old) + 1
        code.emit(0x28040000 | index)
        code.conditional(0x41820000, f"sample_{old}")
    code.jump("palette")
    for old, sample in samples.items():
        code.label(f"sample_{old}")
        _emit_sample_pid(code, region, old, sample, pid, "palette")
        code.jump("save_spinda")
    code.label("save_spinda")
    code.emit(0x80C10008, 0x90660004, 0x90E60014)  # apply the PID and owner to the display CK3
    code.jump("return")


def _model_constructor(address, region, samples, pid):
    native = region.native_constructor
    code = _Code(address)
    # Unmarked calls retain the native constructor. The marker is used only
    # by script function 205 and must never enter the Pokémon structure.
    code.emit(0x70800000 | _DNA_MODEL)  # andi. r0, r4, DNA_MODEL
    code.conditional(0x40820000, "dna")
    code.emit(branch(address + len(code.words) * 4, native))
    code.label("dna")
    code.emit(0x9421FFE0, 0x7C0802A6, 0x90010024, 0x90610008,
              0x9081000C, 0x548405FE)  # save the marker and retain only the actual species
    code.call(native)
    code.emit(0x90610010, 0x8081000C)
    if samples:
        _emit_spinda_samples(code, region, samples, pid)
    code.label("palette")
    # Only this temporary display Pokémon gets a fixed shiny XOR. Unown's
    # letter is resolved separately by the seed-specific native form patch.
    code.emit(0x80C10008, 0x80E60014, 0x81060004,  # object, owner, PID
              0x54E9843E, 0x7D293A78, 0x550A843E, 0x7D295278,
              0x8081000C, 0x70800000 | _DNA_SHINY)
    code.conditional(0x40820000, "shiny")
    code.emit(0x69290008)  # XOR 8 guarantees ordinary colors
    code.label("shiny")
    code.emit(0x5128043E, 0x91060004)
    code.label("return")
    code.emit(0x80610010, 0x80010024, 0x7C0803A6,
              0x38210020, 0x4E800020)
    return code.finish()


def patch_dna_analyzer(original, current, appearances, *, spinda_samples=None, spinda_pid=None):
    """Change the analyzer only. Sample IDs and keypad comparisons stay native."""
    region = dol_layout(original)
    analyzer, menu = _ANALYZER[region.game_id]
    constructor_call = menu + 0x6C
    instructions = {
        analyzer + 0xA4: branch(analyzer + 0xA4, menu, link=True),
        analyzer + 0x1A4: 0x7FE3FB78,  # mr r3, r31: species returned to the script
        constructor_call: branch(constructor_call, region.native_constructor, link=True),
    }
    for index, old in enumerate(_SAMPLE_SPECIES):
        instructions[analyzer + 0x48 + index * 8] = 0x3BE00000 | old
    for address, expected in instructions.items():
        if any(u32(data, address - TEXT_TO_RAM) != expected for data in (original, current)):
            raise FormatError(f"unexpected DNA analyzer instruction at {address:#x}")

    offset = (len(original) + 31) & ~31
    previous_size = u32(current, 0x98)
    arena_offset = region.set_arena_lo - TEXT_TO_RAM
    arena_branch = branch(region.set_arena_lo, region.section_ram)
    if previous_size:
        if ((u32(current, 0x08), u32(current, 0x50)) != (offset, region.section_ram)
                or previous_size % 32 or offset + previous_size != len(current)
                or u32(current, arena_offset) != arena_branch
                or current[offset:offset + 32] != _arena_guard(
                    region.section_ram + previous_size, region.arena_lo_store)):
            raise FormatError("invalid existing DOL reservation before the DNA analyzer hook")
        code = bytearray(current[offset:])
    else:
        if (len(current) != len(original) or any(u32(current, field) for field in (0x08, 0x50))
                or u32(current, arena_offset) != region.arena_lo_store):
            raise FormatError("invalid DOL layout before the DNA analyzer hook")
        code = bytearray(32)

    stub = region.section_ram + len(code)
    samples = spinda_samples or {}
    code.extend(_model_constructor(stub, region, samples, spinda_pid))
    end = region.section_ram + len(code)
    header = parse_dol(original)
    if header["bss_ram_address"] + header["bss_size"] >= region.section_ram or end >= 0x81700000:
        raise FormatError("DNA analyzer hook exceeds the available DOL arena")
    code[:32] = _arena_guard(end, region.arena_lo_store)
    output = bytearray(current[:offset])
    output.extend(bytes(offset - len(output)))
    output.extend(code)

    edits = {
        0x08: offset, 0x50: region.section_ram, 0x98: len(code), arena_offset: arena_branch,
        constructor_call - TEXT_TO_RAM: branch(constructor_call, stub, link=True),
        analyzer + 0x1A4 - TEXT_TO_RAM: 0x57E305FE,  # clrlwi r3, r31, 23
    }
    for index, old in enumerate(_SAMPLE_SPECIES):
        new, shiny = appearances[old]
        if not 0 < new < (1 << 9):
            raise FormatError("invalid DNA sample species")
        sample = (index + 1) << 9 if old in samples else 0
        edits[analyzer + 0x48 + index * 8 - TEXT_TO_RAM] = (
            0x3BE00000 | new | sample | _DNA_MODEL | (_DNA_SHINY if shiny else 0))
    for pos, word in edits.items():
        struct.pack_into(">I", output, pos, word)
    return bytes(output)


def _sample_description(_source, *, name, language, tile):
    labels = {"UK": "DNA sample", "US": "DNA sample", "FR": "Échantillon ADN",
              "GE": "DNS-Probe", "IT": "Campione di DNA", "SP": "Muestra de ADN",
              "JP": "ＤＮＡサンプル"}
    if tile is not None:
        name += f"（{'１２３４５６７８９'[tile - 1]}）" if language == "JP" else f" ({tile})"
    # The Key Items description box is narrow. Keep the native break between
    # a short label and the identified species, with no line broken mid-name.
    return (labels[language].encode("utf-16-be") + b"\xff\xff\x00"
            + name.encode("utf-16-be") + b"\0\0")


def dna_room_updates(original_rel, game_id, read_archive, appearances, *, unown_form_index=0, spinda_samples=()):
    keypad = read_archive("DNA_key.fsys")
    updated_keypad = patch_dna_keypad(keypad, read_archive("poke_face.fsys"), appearances,
                                     unown_form_index=unown_form_index, spinda_samples=spinda_samples)
    updates = {"DNA_key.fsys": updated_keypad} if updated_keypad != keypad else {}
    tables, symbols = layout(original_rel)
    species = tables["species"]
    names = localized_names(original_rel, symbols)[0]
    counts = Counter(new for new, _ in appearances.values())
    messages = {}
    for index, old in enumerate(_SAMPLE_SPECIES):
        new, _ = appearances[old]
        tile = DNA_KEYPAD_SPECIES.index(old) + 1 if counts[new] > 1 else None
        if old == new and tile is None:
            continue
        new_name = u32(original_rel, species["offset"] + new * species["stride"] + 0x18)
        messages[0x2812 + index * 2] = new_name, tile
    if not messages:
        return updates

    menus = ("pcbox_menu", "pcbox_pocket_menu", "pocket_menu", "waza_menu")
    languages = {"": "JP" if game_id == "GC6J01" else "US"}
    if game_id == "GC6P01":
        menus += ("cb_menu", "pokechg_menu")
        languages = {"": "UK", "_fr": "FR", "_ge": "GE", "_it": "IT", "_sp": "SP"}
    for menu in menus:
        for suffix, language in languages.items():
            filename = f"{menu}{suffix}.fsys"
            source = read_archive(filename)
            members = [row for row in parse_fsys(source)["members"]
                       if row["identifier_raw"].endswith("0a00") and row["name"].startswith("pocket_menu")]
            if len(members) != 1:
                raise FormatError("missing DNA sample description bank")
            member = members[0]
            bank = decoded_member(source, member)
            tag = b"\0\1" if language == "JP" else language.encode("ascii")
            if bank[6:8] != tag or any(name_id not in names[language] for name_id, _ in messages.values()):
                raise FormatError("unexpected DNA sample description language or species name")
            edits = {identifier: partial(_sample_description, name=names[language][name_id],
                                        language=language, tile=tile)
                     for identifier, (name_id, tile) in messages.items()}
            updated_bank = patch_messages(bank, edits)
            updates[filename] = repack_fsys(source, {member["index"]: updated_bank})[0]
    return updates
