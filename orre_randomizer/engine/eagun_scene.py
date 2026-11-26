"""Keep Eagun's battle, field companion and accessible gift coherent."""

import struct

from .analyze_game import FormatError, parse_fsys, u32
from .colo_spinda import colo_spinda_gift_pid, colo_spinda_trainer_pid
from .dol_regions import special_targets
from . import event_gifts as events
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
PARTNER_SLOT = 2822
GIFT_KEY = "pikachu-event"


def _partner_position(original, game_id):
    tables, symbols = layout(original)
    trainers, party = (tables[name] for name in ("trainers", "trainer_pokemon"))
    extra = 0x10 if game_id == "GC6P01" else 0
    battle = symbols[50]["offset"] + 525 * (0x38 + extra)
    slot = u16(original, trainers["offset"] + 780 * trainers["stride"] + 4)
    position = party["offset"] + slot * party["stride"]
    if ((u16(original, battle + 0x18 + extra), u16(original, battle + 0x20 + extra)) != (780, 779)
            or slot != PARTNER_SLOT or u16(original, position + 0xA) != _PIKACHU
            or original[position + 3]):
        raise FormatError("unexpected Colosseum team for Eagun's field partner")
    return tables, symbols, position


def synchronize_eagun_gift(original, current, original_dol, current_dol, game_id, *, enabled=False):
    """Use the existing gift draw; never draw a second species for this partner."""
    if not enabled:
        return current, None
    tables, _, position = _partner_position(original, game_id)
    gift = next(row for row in special_targets(original_dol) if row["key"] == GIFT_KEY)
    chosen = u16(current_dol, gift["base"] + 2)
    species = tables["species"]
    if not 0 < chosen < species["count"]:
        raise FormatError("invalid Eagun gift species")
    row = species["offset"] + chosen * species["stride"]
    national = u16(original, row + 0x10)
    if not 1 <= national <= 386 or current[position + 3]:
        raise FormatError("invalid Eagun gift/battle link")
    result = bytearray(current)
    before = u16(current, position + 0xA)
    struct.pack_into(">H", result, position + 0xA, chosen)
    struct.pack_into(">I", result, position + 0x14, u32(original, row + 0x18))
    if result[position] == 1 and not current[row + 0x33]:
        result[position] = 0  # The replacement has no second ability slot.
    if national == 327:
        # The gift's native PID constructor has unconstrained gender/nature.
        # Its private Spinda seed and fixed owner can then reproduce the same
        # complete PID in Eagun's earlier battle, not merely a similar pattern.
        result[position + 1:position + 3] = b"\xff\xff"
    allowed = ((position, position + 3), (position + 0xA, position + 0xC),
               (position + 0x14, position + 0x18))
    events._only_changes(current, bytes(result), allowed)
    return bytes(result), {"gift_key": GIFT_KEY, "trainer_id": 780, "trainer_slot": PARTNER_SLOT,
                           "original_trainer_species": before, "species": chosen,
                           "national_dex": national, "level_and_moves_preserved": True,
                           "trainer_special_aliases": ((PARTNER_SLOT, GIFT_KEY),)}


def _ambient_visibility():
    # Legacy saves may already have received the old gift before exchanging
    # P★AD numbers. Keep every native scene visible until the safe story gate;
    # likewise retain the companion for a pending native Master Ball handoff.
    return (events._call(81, events.RECEIPT_FLAGS[GIFT_KEY]) + events._story_complete()
            + b"\x21\x82\x82\x11\x82")


def patch_home_companion_visibility(original, current, game_id):
    """Change only actor3's initial SHOW operand, never Eagun or his talk."""
    profile = events._REGIONAL_LAYOUTS.get(game_id)
    if profile is None:
        raise FormatError("unsupported Eagun companion region")
    events._fingerprint(original, profile["home_cms"], "home companion CMS")
    statement = events._statement(50, events._local(1), 3, 1)
    site, continuation = 0x158, 0x15E
    if (original[0x138:0x138+len(statement)] != statement
            or current[0x138:0x138+len(statement)] != statement
            or current[0x38:0x3C] != original[0x38:0x3C]
            or current[0x678:0x68C] != original[0x678:0x68C]):
        raise FormatError("unexpected native home companion visibility or story redirect")
    result = bytearray(current)
    result[site:site+5] = b"\x06" + struct.pack(">I", len(current))
    result.extend(_ambient_visibility() + b"\x06" + struct.pack(">I", continuation))
    events._only_changes(current, bytes(result), ((site, site+5),))
    return bytes(result), {"actor_index": 3, "receipt_flag": events.RECEIPT_FLAGS[GIFT_KEY],
                           "operand_site": site, "expression_offset": len(current),
                           "continuation": continuation, "native_eagun_actor_untouched": True,
                           "native_story_and_talk_unchanged": True, "safe_story_gate_required": True}


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
                       trainer_shinies, guaranteed_shiny, *, unown_form_index=0,
                       spinda_seeds=None, spinda_default=None, gift_partner=None,
                       special_shinies=None, deoxys_forms=None):
    tables, symbols, position = _partner_position(original, game_id)
    species = tables["species"]
    slot = PARTNER_SLOT
    chosen = u16(current, position + 0xA)
    gift_linked = gift_partner is not None
    if gift_linked and (gift_partner.get("species") != chosen or gift_partner.get("trainer_slot") != slot):
        raise FormatError("Eagun scene does not match its accessible gift")
    shiny = ((special_shinies or {}).get(GIFT_KEY, guaranteed_shiny) if gift_linked
             else trainer_shinies.get(str(slot), guaranteed_shiny))
    replace_model = chosen != _PIKACHU or shiny
    if not replace_model and not gift_linked:
        return None

    original_species = species["offset"] + _PIKACHU * species["stride"]
    chosen_species = species["offset"] + chosen * species["stride"]
    national_dex = u16(original, chosen_species + 0x10)
    voice = u16(original, chosen_species + 0xE)
    if not 1 <= national_dex <= 386 or not voice or u16(original, original_species + 0xE) != _PIKACHU_VOICE:
        raise FormatError("unexpected Colosseum voice for Eagun's field partner")
    scale = companion_scale(national_dex, 0.65)
    spinda_mode = ((special_shinies or {}).get(GIFT_KEY, spinda_default) if gift_linked
                   else trainer_shinies.get(str(slot), spinda_default))
    spinda_pid = ((colo_spinda_gift_pid(spinda_seeds, GIFT_KEY, spinda_mode) if gift_linked
                   else colo_spinda_trainer_pid(original, current, spinda_seeds, slot, spinda_mode))
                  if spinda_seeds and spinda_mode is not None else None)
    model = load_actor_model(dol, game_id, u32(original, chosen_species + 0x2C), read_archive,
                             scale=scale, shiny=shiny, unown_form_index=unown_form_index,
                             spinda_pid=spinda_pid, deoxys_form=(deoxys_forms or {}).get(
                                 'special:' + GIFT_KEY if gift_linked else f'trainer:{slot}', 0)
                             if chosen == 410 else 0) if replace_model else None
    changes = {u32(original, original_species + 0x18): u32(original, chosen_species + 0x18)}
    names = localized_names(original, symbols)[0] if chosen != _PIKACHU else {}
    changed_archives, visibility = [], None
    for archive, captions in _CAPTIONS.items():
        source = updates[archive] if archive in updates else read_archive(archive)
        previous = source
        if archive == _HOME and gift_linked:
            members = parse_fsys(source)["members"]
            native = read_archive(archive)
            before = next(m for m in parse_fsys(native)["members"] if m["identifier_raw"].endswith("0e00"))
            now = next(m for m in members if m["identifier_raw"] == before["identifier_raw"])
            script, visibility = patch_home_companion_visibility(
                decoded_member(native, before), decoded_member(source, now), game_id)
            source = repack_fsys(source, {now["index"]: script})[0]
        if model is not None:
            source = patch_actor(source, model, identifier="0x012b0400", name="pikachu")
        if chosen != _PIKACHU:
            source = _patch_voices(source, archive, chosen, voice)
            messages = dict.fromkeys((*_NAMES.get(archive, ()), *captions), changes)
            source = patch_species_archive(source, messages, names, rewrites=dict.fromkeys(captions, _cry_caption))
        if source != previous:
            updates[archive] = source
            changed_archives.append(archive)
    return {"species": chosen, "national_dex": national_dex, "scale": scale, "shiny": shiny,
            "archives": changed_archives, "gift_linked": gift_linked, "gift_key": GIFT_KEY if gift_linked else None,
            "spinda_pid": spinda_pid, "appearance_determined": spinda_mode is not None,
            "home_visibility": visibility}
