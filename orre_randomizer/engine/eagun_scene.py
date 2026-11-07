"""Keep Colosseum's Pikachu actor tied to Eagun's scripted shrine battle."""

import struct

from .analyze_game import FormatError, parse_fsys, u32
from .inspect_tables import localized_names, u16
from .message_bank import patch_species_archive
from .plusle_actor import companion_scale, load_actor_model, patch_actor
from .randomize_trainers import layout
from .rebuild_iso import decoded_member, repack_fsys


_SHRINE = "M3_shrine_1F.fsys"
_HOME = "M3_houseC_1F.fsys"
_FINALE = "D4_casino_colo.fsys"
_PIKACHU = 25
_PIKACHU_VOICE = 594
_NAMES = {_SHRINE: (0x5168, 0x518A, 0x5232)}
_CAPTIONS = {
    _SHRINE: (0x51E8, 0x51E9, 0x51EA),
    _HOME: (0x5213, 0x5214, 0x5216),
    _FINALE: (0x56D4,),
}
_VOICE_PREFIX = bytes.fromhex("08020000000010420001")
_VOICE_SUFFIX = bytes.fromhex("03820001")
_MESSAGE_END = b"\xff\xff\x02\0\0"


def _voice_call(command, *arguments):
    pushes = b"".join(struct.pack(">BBI", 8, 2, value) for value in (command, *arguments))
    return _VOICE_PREFIX + pushes + struct.pack(">BHH", 37, 1, len(arguments) + 1) + _VOICE_SUFFIX


def _patch_voices(source, archive, chosen, voice):
    members = [m for m in parse_fsys(source)["members"] if m["identifier_raw"].endswith("0e00")]
    if len(members) != 1:
        raise FormatError("expected one Colosseum companion scene script")
    member = members[0]
    script = decoded_member(source, member)
    if archive == _FINALE:
        # The finale plays the species' raw sound ID, then waits for it.
        calls = [(105, (_PIKACHU_VOICE, 0, 255), (voice, 0, 255)),
                 (106, (_PIKACHU_VOICE, 0), (voice, 0))]
        expected_count = 1
    else:
        calls = [(218, (_PIKACHU,), (chosen,))]
        expected_count = 2
    for command, original, replacement in calls:
        pattern = _voice_call(command, *original)
        if script.count(pattern) != expected_count:
            raise FormatError(f"unexpected Pikachu voice calls in {archive}")
        script = script.replace(pattern, _voice_call(command, *replacement))
    return repack_fsys(source, {member["index"]: script})[0]


def _cry_caption(source, *, changes, language):
    (old, new), = changes.items()
    named_prefix = old + ("「" if language == "JP" else ": ")
    icon_prefix = "＊「" if language == "JP" else "‱: "
    if source.startswith(named_prefix.encode("utf-16-be")):
        prefix = new + ("「" if language == "JP" else ": ")
    elif source.startswith(icon_prefix.encode("utf-16-be")):
        prefix = icon_prefix
    else:
        raise FormatError("unexpected Colosseum Pikachu caption")
    punctuation = {"FR": ("", " !"), "SP": ("¡", "!"), "JP": ("", "！")}.get(language, ("", "!"))
    return (prefix + punctuation[0] + new + punctuation[1]).encode("utf-16-be") + _MESSAGE_END


def patch_eagun_scenes(original, current, dol, game_id, read_archive, updates,
                       trainer_shinies, guaranteed_shiny):
    tables, symbols = layout(original)
    trainers, party, species = (tables[name] for name in ("trainers", "trainer_pokemon", "species"))
    # The shrine starts an NPC battle between Eagun (780) and Skrub (779).
    # PAL records reserve sixteen additional bytes before the trainers.
    pal_extra = 0x10 if game_id == "GC6P01" else 0
    battle = symbols[50]["offset"] + 525 * (0x38 + pal_extra)
    trainer = trainers["offset"] + 780 * trainers["stride"]
    slot = u16(original, trainer + 4)
    position = party["offset"] + slot * party["stride"]
    if ((u16(original, battle + 0x18 + pal_extra), u16(original, battle + 0x20 + pal_extra)) != (780, 779)
            or u16(original, position + 0xA) != _PIKACHU or original[position + 3]):
        raise FormatError("unexpected Colosseum team for Eagun's field partner")
    chosen = u16(current, position + 0xA)
    shiny = trainer_shinies.get(str(slot), guaranteed_shiny)
    if chosen == _PIKACHU and not shiny:
        return None

    original_species = species["offset"] + _PIKACHU * species["stride"]
    chosen_species = species["offset"] + chosen * species["stride"]
    national_dex = u16(original, chosen_species + 0x10)
    voice = u16(original, chosen_species + 0xE)
    if not 1 <= national_dex <= 386 or not voice or u16(original, original_species + 0xE) != _PIKACHU_VOICE:
        raise FormatError("unexpected Colosseum voice for Eagun's field partner")
    scale = companion_scale(national_dex, 0.65)
    model = load_actor_model(dol, game_id, u32(original, chosen_species + 0x2C), read_archive,
                             scale=scale, shiny=shiny)
    changes = {u32(original, original_species + 0x18): u32(original, chosen_species + 0x18)}
    names = localized_names(original, symbols)[0] if chosen != _PIKACHU else {}
    for archive, captions in _CAPTIONS.items():
        source = updates[archive] if archive in updates else read_archive(archive)
        source = patch_actor(source, model, identifier="0x012b0400", name="pikachu")
        if chosen != _PIKACHU:
            source = _patch_voices(source, archive, chosen, voice)
            messages = dict.fromkeys((*_NAMES.get(archive, ()), *captions), changes)
            source = patch_species_archive(source, messages, names, rewrites=dict.fromkeys(captions, _cry_caption))
        updates[archive] = source
    return {"species": chosen, "national_dex": national_dex, "scale": scale, "shiny": shiny,
            "archives": list(_CAPTIONS)}
