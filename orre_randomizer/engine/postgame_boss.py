"""A separate Cipher commander at Colosseum's Relic Stone.

Only native numeric tables, a new map actor, appended CMS functions and localized
messages are changed. The Lugia model port is supplied by a separate patch.
"""
from __future__ import annotations

import math
import struct

from . import event_gifts as events
from .analyze_game import FormatError, parse_fsys, parse_rel, sha256, u32
from .evolution_rules import evolution_families
from .gameplay_rules import choose_moves, expanded_layout, move_catalog, pick
from .inspect_tables import localized_names, rel_symbols, u16
from .pool_filters import allowed_replacement
from .rebuild_iso import align, decoded_member, repack_fsys
from .rel_regions import region_for_rel
from .shiny_rules import seeded_status
from .species_rules import species_catalog

VERSION = "colosseum-postgame-nascour-lugia-v4"
LUGIA, SHADOW_ID, TRAINER_ID, PARTY_SLOT, BATTLE_ID = 249, 96, 820, 5510, 566
CAPTURE_FLAG, PURIFICATION_FLAG = 2221, 1357
LEVEL = 70
BOSS_ACTOR = 4
BOSS_MODEL = 35
BOSS_NAME_ID = 4167
BOSS_SCRIPT = 13
MESSAGE_IDS = tuple(range(0xF0010, 0xF001D))
NAMES = {"UK": "NASCOUR", "US": "NASCOUR", "FR": "JAKYLLA", "GE": "JAKIRA",
         "SP": "FÚSTEO", "IT": "NASCOUR", "JP": "ジャキラ"}
_DONOR = "D4_casino_colo.fsys"
_BOSS_ASSET = "0x03240400"
_BOSS_ASSET_SHA = "0c8491d8c9314199d2b2a6835aaf016b0482c41f2cbfd75d2bd95c84afa60b63"


def _require(condition, message):
    if not condition:
        raise FormatError(message)


def _append_strings(current, identifiers, texts, *, dialogue=True):
    count = u16(current, 4)
    end = 16 + count * 8
    _require(end <= len(current) and count <= 65535 - len(identifiers), "invalid commander message bank")
    rows = [struct.unpack_from(">II", current, 16 + i * 8) for i in range(count)]
    _require(not {i & 0xFFFFF for i, _ in rows} & set(identifiers), "colliding commander message IDs")
    _require(all(end <= p < len(current) for _, p in rows), "invalid commander message offset")
    growth = len(identifiers) * 8
    header = bytearray(current[:16])
    struct.pack_into(">H", header, 4, count + len(identifiers))
    directory = bytearray(b"".join(struct.pack(">II", i, p + growth) for i, p in rows))
    payload = bytearray()
    for identifier, text in zip(identifiers, texts, strict=True):
        directory.extend(struct.pack(">II", identifier, len(current) + growth + len(payload)))
        encoded = (text if isinstance(text, bytes) else events._encode_text(text)) if dialogue else text.encode("utf-16-be") + b"\0\0"
        _require(not dialogue or encoded.endswith(bytes.fromhex("ffff020000")),
                 "unterminated commander dialogue")
        payload.extend(encoded)
    return bytes(header + directory + current[end:] + payload)


DEFAULT_TEAM = (394, 178, 362, 343, 282)


def bonus_shadow_species(original, seed, options):
    """Resolve the optional replacement before reserving story families."""
    if (not getattr(options, "postgame_shadow_lugia", False)
            or not getattr(options, "postgame_randomize_lugia", False)):
        return LUGIA
    tables = expanded_layout(original)
    source = species_catalog(original, tables)
    families = evolution_families(original, tables)[0]
    pool = [index for index, row in source.items()
            if index != LUGIA and allowed_replacement(row, options)]
    fixed_families = set()
    if not getattr(options, "postgame_randomize_team", False):
        fixed_families.update(families[index] for index in DEFAULT_TEAM)
    from .species_rules import LEGENDARY_NATIONAL
    shadow_table = tables["shadow"]
    for sid in range(1, shadow_table["count"]):
        index = u16(original, shadow_table["offset"] + sid * shadow_table["stride"] + 2)
        if index and (not options.randomize_shadows or
                      not options.randomize_legendary_shadows and source[index]["national_dex"] in LEGENDARY_NATIONAL):
            fixed_families.add(families[index])
    from .randomize_story import SPECIALS
    from ..options import SPECIAL_OPTIONS
    for target in SPECIALS:
        if not getattr(options, SPECIAL_OPTIONS[target["key"]]) and target["old"] in families:
            fixed_families.add(families[target["old"]])
    for name in ("umbreon", "espeon"):
        dex = getattr(options, "starter_" + name + "_species")
        if getattr(options, "starter_" + name) and dex:
            fixed_families.update(families[index] for index, row in source.items() if row["national_dex"] == dex)
    different = [index for index in pool if families[index] not in fixed_families]
    pool = different or pool
    _require(bool(pool), "no eligible replacement for the bonus Shadow Pokémon")
    return pick(seed, "postgame-shadow:96", pool)


def plan_team(original, current, seed, options):
    """Keep the authored team unless the two event-specific choices are enabled."""
    tables = expanded_layout(original)
    source = species_catalog(original, tables)
    final = species_catalog(current, tables)
    families = evolution_families(original, tables)[0]
    shadow_species = bonus_shadow_species(original, seed, options)
    # Reuse the five ordinary members when trainer species are unchanged.
    # Generation/type/species exclusions apply only when drawing replacements.
    chosen = list(DEFAULT_TEAM)
    if getattr(options, "postgame_randomize_team", options.randomize_trainers):
        pool = [s for s, row in source.items() if s != shadow_species and allowed_replacement(row, options)]
        _require(bool(pool), "no Nascour Pokémon satisfy the selected filters")
        chosen, used = [], {families[shadow_species]}
        for slot in range(5):
            eligible = [s for s in pool if families[s] not in used]
            eligible = eligible or [s for s in pool if s not in chosen] or pool
            species = pick(seed, f"postgame-commander:{slot}", eligible)
            chosen.append(species)
            used.add(families[species])
    chosen.append(shadow_species)
    moves = move_catalog(original, tables)
    team = []
    for index, species in enumerate(chosen):
        level, shadow_id = LEVEL - 5 + index, SHADOW_ID if index == 5 else 0
        key = f"shadow:{SHADOW_ID}" if shadow_id else f"trainer:{PARTY_SLOT + index}"
        randomized = getattr(options, "postgame_randomize_lugia", False) if shadow_id else getattr(options, "postgame_randomize_team", options.randomize_trainers)
        if randomized and options.randomize_trainer_moves:
            selected = choose_moves(seed, key, final[species], level, moves, options, count=4)
        elif shadow_id:
            selected = [177, 94, 105, 56]
        else:
            native_slot = 4111 + index
            p = tables["trainer_pokemon"]["offset"] + native_slot * tables["trainer_pokemon"]["stride"]
            selected = [u16(original, p + field) for field in (0x36, 0x3E, 0x46, 0x4E)]
        shiny = None
        if options.custom_shinies:
            shiny = (seeded_status(seed, key, options.shiny_chance_percent) if options.seeded_shinies else
                     True if options.shiny_chance_percent == 100 else
                     False if options.shiny_chance_percent == 0 else None)
        team.append({"slot": PARTY_SLOT + index, "key": key, "species": species,
                     "national_dex": source[species]["national_dex"], "level": level,
                     "moves": selected, "shadow_id": shadow_id, "shiny": shiny,
                     "gender": 2, "nature": -1, "source_slot": 4111 + index if index < 5 else 4110,
                     "family": families[species], "randomized": randomized})
    return team


def apply_common(original, current, options, *, seed):
    from .postgame_lugia import _extend_tables
    tables = expanded_layout(original)
    symbols = rel_symbols(original, parse_rel(original))
    region = region_for_rel(original)
    trainer, party, species, shadow = (tables[k] for k in ("trainers", "trainer_pokemon", "species", "shadow"))
    lugia = species["offset"] + LUGIA * species["stride"]
    reserved = shadow["offset"] + SHADOW_ID * shadow["stride"]
    _require(u16(original, lugia + 0x10) == LUGIA and u16(original, reserved + 2) == 0
             and u16(original, reserved + 0x12) == CAPTURE_FLAG
             and u16(original, reserved + 0x14) == PURIFICATION_FLAG,
             "unexpected reserved Shadow Lugia allocation")
    template = trainer["offset"] + 437 * trainer["stride"]
    first = u16(original, template + 4)
    _require(first == 4110 and original[template + 3] == 5 and u32(original, template + 8) == 4167,
             "unexpected native commander trainer template")
    new_trainer = bytearray(original[template:template + trainer["stride"]])
    struct.pack_into(">H", new_trainer, 4, PARTY_SLOT)
    struct.pack_into(">I", new_trainer, 8, BOSS_NAME_ID)
    new_trainer[0x24:0x30] = bytes(12)
    new_party = bytearray()
    team = plan_team(original, current, seed, options)
    for index, row in enumerate(team):
        p = party["offset"] + row["source_slot"] * party["stride"]
        template_data = current if row["randomized"] else original
        record = bytearray(template_data[p:p + party["stride"]])
        record[:5] = bytes((0xFF, 2, 0xFF, row["shadow_id"], row["level"]))
        struct.pack_into(">H", record, 0xA, row["species"])
        species_row = species["offset"] + row["species"] * species["stride"]
        struct.pack_into(">I", record, 0x14, u32(current, species_row + 0x18))
        record[0x1C:0x22] = bytes((25,)) * 6
        for n in range(6):
            record[0x23 + n * 2] = 64
        for offset, move in zip((0x36, 0x3E, 0x46, 0x4E), row["moves"], strict=True):
            struct.pack_into(">H", record, offset, move)
        row["held_item"] = u16(record, 0x12)
        new_party.extend(record)
    battle_stride = 0x48 if region.game_id == "GC6P01" else 0x38
    battle_template = symbols[50]["offset"] + 543 * battle_stride
    player = 0x28 if region.game_id == "GC6P01" else 0x18
    _require(u16(original, battle_template + player) == 1
             and u16(original, battle_template + player + 8) == 794,
             "unexpected native shrine battle template")
    new_battle = bytearray(original[battle_template:battle_template + battle_stride])
    # Native Cipher Admin theme (also used by Dakim). A zero would instead
    # inherit the commander's class fallback, not the shrine peon's music.
    struct.pack_into(">I", new_battle, 0xC, 1100)
    struct.pack_into(">H", new_battle, player + 8, TRAINER_ID)
    new_battle[8:12] = bytes(4)
    from .postgame_scene_state import flag_table_extension
    flag_addition, flag_report = flag_table_extension(original, symbols)
    additions = [
        ("trainers", 44, 45, trainer["stride"], TRAINER_ID, bytes(new_trainer)),
        ("trainer_pokemon", 48, 49, party["stride"], PARTY_SLOT, bytes(new_party)),
        ("battles", 50, 51, battle_stride, BATTLE_ID, bytes(new_battle)),
        flag_addition,
    ]
    result, extension = _extend_tables(original, current, symbols, additions)
    result = bytearray(result)
    result[reserved] = 45
    struct.pack_into(">HHHH", result, reserved + 2, team[-1]["species"], TRAINER_ID, 0, 200)
    _require(result[reserved + 0xB] == SHADOW_ID, "reserved Shadow ID changed")
    # Reuse Nascour's original name in every regional language bank.
    names = localized_names(bytes(result), rel_symbols(bytes(result), parse_rel(bytes(result))))[0]
    _require(all(names[language].get(BOSS_NAME_ID) == NAMES[language] for language in region.native_languages),
             "native Nascour names did not survive common REL relocation")
    return bytes(result), {"version": VERSION, "enabled": True, "species": team[-1]["species"], "shadow_id": SHADOW_ID,
                           "trainer_id": TRAINER_ID, "first_party_slot": PARTY_SLOT, "party_slot": PARTY_SLOT + 5,
                           "battle_id": BATTLE_ID, "level": LEVEL, "capture_flag": CAPTURE_FLAG,
                           "battle_music_id": 1100,
                           "introduction_state": flag_report,
                           "purification_flag": PURIFICATION_FLAG, "required_native_captures": 48,
                           "required_native_purifications": 48, "native_shadow_roster_unchanged": True,
                           "native_purification": True, "retry_until_captured": True,
                           "location": events.ARCHIVE_NAMES[0], "opponent": {"trainer_id": TRAINER_ID,
                           "name_id": BOSS_NAME_ID, "field_model": BOSS_MODEL, "names": NAMES}, "team": team,
                           "requirements": {"captures": 48, "purifications": 48, "story_flags": events.STORY_FLAGS},
                           **extension}


def _ready():
    from .postgame_scene_state import INTRO_STATE_FLAG, PHASE_AVAILABLE
    code = events._story_complete()
    for start in (2125, 1261):
        code += (events._push(0) + b"".join(events._call(81, start + sid) + b"\x17\x82\x82"
                                            for sid in events.SHADOW_IDS)
                 + events._push(48) + b"\x1c\x82\x82" + b"\x21\x82\x82")
    return (code + events._call(82, INTRO_STATE_FLAG) + events._push(PHASE_AVAILABLE)
            + b"\x1c\x82\x82\x21\x82\x82")


def _talk(message, *, eagun=False):
    if not eagun:
        return events._talk(message)
    return events._statement(54, events._local(1), 1, message) + events._statement(55, events._local(1), 1)


def _interaction(base):
    from .postgame_scene import interaction
    return interaction(base, ready=_ready(), captured=events._call(81, CAPTURE_FLAG), battle_id=BATTLE_ID)


def _eagun_interaction(base, fallback=None):
    code = events._Assembler(base)
    code.emit(events._story_complete())
    code.jump("return", when_false=True)
    code.emit(events._call(81, CAPTURE_FLAG))
    code.jump("uncaptured", when_false=True)
    # The final scene already thanks both heroes. On subsequent visits, go
    # straight to ordinary purification rewards without another quest bubble.
    # Without event gifts, retain useful purification advice instead.
    if fallback is None:
        code.emit(events._statement(32) + _talk(MESSAGE_IDS[8]) + events._statement(33))
    code.jump("fallback" if fallback is not None else "return")
    code.mark("uncaptured")
    code.emit(_ready())
    code.jump("waiting", when_false=True)
    code.emit(events._statement(32) + _talk(MESSAGE_IDS[12]) + events._statement(33))
    code.jump("return")
    code.mark("waiting")
    if fallback is None:
        code.emit(events._statement(32) + _talk(MESSAGE_IDS[9]) + events._statement(33))
    else:
        code.jump("fallback")
    code.jump("return")
    code.mark("fallback")
    if fallback is not None:
        code.emit(b"\x06" + struct.pack(">I", fallback))
    code.mark("return")
    code.emit(b"\x05")
    return code.finish()


def _patch_script(original, current):
    from . import postgame_scene as scene
    events._fingerprint(original, events.SHRINE_CMS_SHA256, "shrine CMS")
    count = u16(current, 4)
    _require(count in (12, 13) and len(current) >= len(original), "unexpected current shrine functions")
    idle_tail = b"\x06" + struct.pack(">I", 0x2056)
    idle_loop = (events._statement(31) + events._push(1) + b"\x24\x00\x00\x00\x01\x03\x81\x00\x00"
                 + idle_tail)
    _require(original[0x2583:0x25B0] == idle_loop and
             current[0x2583:0x25B0] == original[0x2583:0x25B0],
             "unexpected shrine idle-loop signature")
    output = bytearray(current)
    old_gift = u32(current, 0x48) if count == 13 else None
    eagun = len(output)
    output.extend(_eagun_interaction(eagun, old_gift))
    struct.pack_into(">I", output, 0x48, eagun)
    boss = len(output)
    output.extend(_interaction(boss))
    visibility = len(output)
    # Preserve the native Eagun visibility statement and add a separate actor.
    output.extend(original[0x24A:0x26A] + events._story_complete() + original[0x270:0x279])
    visible = _ready() + events._call(81, CAPTURE_FLAG) + b"\x11\x82\x21\x82\x82"
    for actor in (BOSS_ACTOR, scene.LUGIA_ACTOR):
        output.extend(events._statement(50, events._local(1), actor, visible))
    output.extend(b"\x06" + struct.pack(">I", 0x279))
    output[0x24A:0x24F] = b"\x06" + struct.pack(">I", visibility)
    refresh = len(output)
    # This task also runs during scripted movement. Do not let it hide the
    # commander as soon as the capture flag changes, before his departure.
    refresh_code = b"".join(events._statement(50, events._local(1), actor, visible)
                            for actor in (BOSS_ACTOR, scene.LUGIA_ACTOR))
    output.extend(scene.refresh_guard(refresh, refresh_code, resume=0x2056,
                                     arrival_ready=_ready(), captured=events._call(81, CAPTURE_FLAG),
                                     battle_id=BATTLE_ID))
    output[0x25AB:0x25B0] = b"\x06" + struct.pack(">I", refresh)
    output.extend(bytes(-len(output) % 4))
    globals_offset = len(output)
    old_globals = current[u32(current, 16):u32(current, 16) + 8]
    _require(len(old_globals) == 8, "truncated shrine globals")
    output.extend(old_globals + bytes(8))
    # +16 is the native globals pointer. Preserve +12 (relocation/code table).
    struct.pack_into(">I", output, 16, globals_offset)
    struct.pack_into(">I", output, 0x4C, boss)
    struct.pack_into(">H", output, 4, 14)
    return bytes(output), {"boss_function": BOSS_SCRIPT, "boss_entry": boss,
                           "visibility_entry": visibility, "eagun_function": 12,
                           "eagun_entry": eagun, "event_gift_fallback": old_gift,
                           "visibility_refresh_entry": refresh, "visibility_refresh_patch": 0x25AB,
                           "visibility_refresh_resume": 0x2056,
                           "arrival_after_native_yield": True, "scene_latch_global": scene.SCENE_GLOBAL,
                           "arrival_seen_global": scene.ARRIVAL_GLOBAL,
                           "globals_offset": globals_offset}


def _append_boss_asset(source, donor):
    original, donor_info = parse_fsys(source), parse_fsys(donor)
    matches = [m for m in donor_info["members"] if m["identifier_raw"] == _BOSS_ASSET and m["name"] == "boss999_b1"]
    _require(len(matches) == 1 and not any(m["identifier_raw"] == _BOSS_ASSET for m in original["members"]),
             "unexpected commander field-model assets")
    member = matches[0]
    _require(sha256(decoded_member(donor, member)) == _BOSS_ASSET_SHA, "unknown commander field-model fingerprint")
    members, count = original["members"], len(original["members"])
    first = min(m["offset"] for m in members)
    _require(first == u32(source, 0x48) and source[-4:] == b"FSYS", "unsupported shrine FSYS data layout")
    headers = align(first + (count + 1) * 4)
    name_at = headers + 0x50
    name = b"boss999_b1\0"
    new_data = align(name_at + len(name))
    growth = new_data - first
    output = bytearray(source[:first] + bytes(growth) + source[first:-32])
    struct.pack_into(">I", output, 0xC, count + 1)
    struct.pack_into(">I", output, 0x1C, new_data)
    struct.pack_into(">I", output, 0x40, first)
    struct.pack_into(">I", output, 0x48, new_data)
    for m in members:
        struct.pack_into(">I", output, first + m["index"] * 4, m["header_offset"])
        struct.pack_into(">I", output, m["header_offset"] + 4, m["offset"] + growth)
    output[headers:headers + 0x50] = donor[member["header_offset"]:member["header_offset"] + 0x50]
    output[name_at:name_at + len(name)] = name
    output.extend(bytes(-len(output) % 32))
    struct.pack_into(">I", output, first + count * 4, headers)
    struct.pack_into(">I", output, headers + 4, len(output))
    struct.pack_into(">I", output, headers + 0x24, name_at)
    output.extend(donor[member["offset"]:member["offset"] + member["stored_size"]])
    output.extend(bytes(-len(output) % 32) + bytes(28) + b"FSYS")
    struct.pack_into(">I", output, 0x20, len(output))
    after = parse_fsys(bytes(output))
    _require(len(after["members"]) == count + 1, "commander model was not appended")
    for old, new in zip(members, after["members"]):
        _require(old["name"] == new["name"] and old["identifier_raw"] == new["identifier_raw"]
                 and decoded_member(source, old) == decoded_member(bytes(output), new),
                 "commander model append changed an existing shrine member")
    _require(decoded_member(bytes(output), after["members"][-1]) == decoded_member(donor, member),
             "commander model payload changed")
    return bytes(output)


def _patch_actor(original, current):
    from .postgame_lugia import _extend_tables
    from .postgame_scene_model import ACTOR, MODEL, POSITION
    symbols = rel_symbols(original, parse_rel(original))
    _require(symbols[5]["offset"] == 0x208 and u32(original, symbols[6]["offset"]) == 4,
             "unexpected original shrine actors")
    actor = bytearray(current[0x22C:0x250])
    _require(u16(actor, 6) == 52, "unexpected Eagun actor template")
    actor[0] &= 0x7F
    actor[1] = 0
    struct.pack_into(">hHH", actor, 4, 0, BOSS_MODEL, 0)
    actor[0x10:0x14] = bytes(4)
    actor[0x14] = 1
    struct.pack_into(">H", actor, 0x16, BOSS_SCRIPT)
    struct.pack_into(">fff", actor, 0x18, -14., 0., 15.)
    lugia = bytearray(current[0x274:0x298])
    _require(u16(lugia, 6) == 72, "unexpected native shrine Pokémon template")
    lugia[0] &= 0x7F
    lugia[1] = 0
    # Room reconstruction after a loss does not replay Eagun's introduction.
    # Start facing his actual installed position on every visit as well.
    eagun_x, _, eagun_z = struct.unpack_from(">fff", current, 0x22C + 0x18)
    heading = round(math.degrees(math.atan2(eagun_x - POSITION[0], eagun_z - POSITION[2]))) % 360
    struct.pack_into(">hHH", lugia, 4, heading, MODEL, 0)
    lugia[0x10:0x14] = bytes(4)
    lugia[0x14] = 0
    struct.pack_into(">H", lugia, 0x16, 0)
    struct.pack_into(">fff", lugia, 0x18, *POSITION)
    output, report = _extend_tables(original, current, symbols,
                                    (("actors", 5, 6, 0x24, 4, bytes(actor + lugia)),), section_index=3)
    return output, {"new_actor": BOSS_ACTOR, "model": BOSS_MODEL, "position": [-14., 0., 15.],
                    "lugia_actor": ACTOR, "lugia_model": MODEL, "lugia_position": POSITION,
                    "lugia_heading": heading, **report}


# Each message fits one native line. The renderer does not wrap long prose.
TEXTS = {
    "UK": ("CIPHER will destroy this shrine!", "Shadow LUGIA will finish the job!", "My team will crush you!",
           "Winning a battle is not enough!", "Shadow LUGIA is still ours!", "CIPHER's last plan has failed...",
           "We have lost. I am leaving.", "You saved the RELIC STONE!", "LUGIA can be purified here.",
           "Purify all 48 Shadow POKéMON first.", "Thank you for saving us.", "You cannot stop CIPHER!"),
    "FR": ("Le GROUPE OMBRE revient !", "LUGIA obscur détruira la Relique !", "Mon équipe va t'écraser !",
           "Me vaincre ne suffit pas !", "LUGIA obscur est encore à nous !", "Notre dernier plan a échoué...",
           "Tout est perdu. Je m'en vais.", "Tu as sauvé la Relique !", "LUGIA peut être purifié ici.",
           "Purifie d'abord les 48 obscurs.", "Merci de nous avoir sauvés.", "Tu ne peux pas nous arrêter !"),
    "GE": ("Ich komme im Auftrag von CRYPTO.", "Crypto-LUGIA wird alles zerstören!", "Mein Team wird dich besiegen!",
           "Ein Sieg allein reicht nicht!", "Crypto-LUGIA gehört noch uns!", "Unser Plan ist gescheitert...",
           "Wir haben verloren. Ich gehe.", "Du hast das Sanktuarium gerettet!", "LUGIA kann hier erlöst werden.",
           "Erlöse alle 48 Crypto-POKéMON.", "Danke für deine Hilfe.", "Du kannst CRYPTO nicht aufhalten!"),
    "SP": ("CÍFER destruirá la Piedra Sagrada.", "¡LUGIA oscuro terminará el trabajo!", "¡Mi equipo acabará contigo!",
           "¡Ganar un combate no basta!", "¡LUGIA oscuro sigue siendo nuestro!", "El plan de CÍFER ha fallado...",
           "Hemos perdido. Me marcho.", "¡Salvaste la Piedra Sagrada!", "LUGIA puede purificarse aquí.",
           "Purifica a los 48 POKéMON.", "Gracias por salvarnos.", "¡No puedes detener a CÍFER!"),
    "IT": ("Sono qui per conto della CRIPTO.", "LUGIA OMBRA distruggerà tutto!", "La mia squadra ti schiaccerà!",
           "Vincere un incontro non basta!", "LUGIA OMBRA è ancora nostro!", "Il piano della CRIPTO è fallito...",
           "Abbiamo perso. Me ne vado.", "Hai salvato la SACRA PIETRA!", "LUGIA può essere purificato qui.",
           "Purifica i 48 POKéMON OMBRA.", "Grazie per averci salvati.", "Non fermerai la CRIPTO!"),
    "JP": ("シャドーの　ため　ほこらを　こわす！", "ダークルギアの　ちからを　みよ！", "わたしの　チームに　かてるか！",
           "かつだけでは　だめだ！", "ルギアは　まだ　こちらのものだ！", "さいごの　けいかくが……。",
           "まけだ。　ここを　さる。", "ほこらを　まもったな！", "ルギアも　リライブできるぞ。",
           "４８ひき　すべて　リライブだ。", "たすけてくれて　ありがとう。", "シャドーは　とめられん！"),
}

# Eagun suspends ordinary rewards while the threat is present. This same
# reminder stays valid after a win without a snag; the boss remains available.
_PRESENCE = {
    "UK": "Snag LUGIA to stop him!", "FR": "Snatche LUGIA pour l'arrêter !",
    "GE": "Kralle LUGIA, um ihn aufzuhalten!", "SP": "¡Captura a LUGIA para detenerlo!",
    "IT": "Clepta LUGIA per fermarlo!", "JP": "ルギアを　スナッチするのだ！",
}
TEXTS = {language: (*texts, _PRESENCE[language]) for language, texts in TEXTS.items()}



def localized_dialogue(language, names, *, species_name=None):
    """Native speaker names and punctuation, with no manual line breaks."""
    boss, eagun = names[BOSS_NAME_ID], names[0x10E1]
    key = "UK" if language == "US" else language
    texts = []
    for index, body in enumerate(TEXTS[key]):
        from .postgame_scene_text import event_species_text
        body = event_species_text(body, language, species_name)
        speaker = eagun if index in (7, 8, 9, 10, 12) else boss
        separator = "「" if language == "JP" else " : " if language == "FR" else ": "
        body = body.replace("\u2013", "-").replace("\u2014", "-")
        texts.append(speaker + separator + body)
    return tuple(texts)

def patch_archives(original_rel, read_archive, updates, options, *, shiny=None, species=LUGIA,
                   original_dol=None, seed="postgame-lugia"):
    if not getattr(options, "postgame_shadow_lugia", False):
        return {"version": VERSION, "enabled": False}
    region = region_for_rel(original_rel).game_id
    profile = events._REGIONAL_LAYOUTS[region]
    localized = localized_names(original_rel, rel_symbols(original_rel, parse_rel(original_rel)))[0]
    catalog = species_catalog(original_rel, expanded_layout(original_rel))
    _require(species in catalog, "invalid bonus Shadow species")
    name_id = u32(original_rel, catalog[species]["offset"] + 0x18)
    reports = []
    for name in events.ARCHIVE_NAMES:
        original = read_archive(name)
        events._fingerprint(original, profile["archives"][name], name)
        current = updates.get(name, original)
        old_members = parse_fsys(original)["members"]
        members = parse_fsys(current)["members"]
        _require(len(members) == len(old_members), "unexpected shrine member count before commander patch")
        source_cms, current_cms = decoded_member(original, old_members[1]), decoded_member(current, members[1])
        replacements = {}
        detail = {}
        if name == events.ARCHIVE_NAMES[0]:
            replacements[1], detail["script"] = _patch_script(source_cms, current_cms)
            source_actor = decoded_member(original, old_members[0])
            events._fingerprint(source_actor, profile["actor"], "shrine REL")
            current_actor = bytearray(decoded_member(current, members[0]))
            current_actor[0x240] = 1
            struct.pack_into(">H", current_actor, 0x242, 12)
            replacements[0], detail["actor"] = _patch_actor(source_actor, bytes(current_actor))
            for language, (index, expected) in profile["messages"].items():
                events._fingerprint(decoded_member(original, old_members[index]), expected, f"{language} shrine messages")
                species_name = localized[language][name_id] if species != LUGIA else None
                texts = localized_dialogue(language, localized[language], species_name=species_name)
                from .postgame_scene_text import dialogue_payloads
                scene_texts = dialogue_payloads(language, localized[language], species_name=species_name)
                replacements[index] = _append_strings(decoded_member(current, members[index]),
                    (*MESSAGE_IDS, *scene_texts), (*texts, *scene_texts.values()))
        else:
            # The native home actor still owns story dialogue and handoffs.
            # The bonus never redirects or hides him, even after its unlock.
            events._fingerprint(source_cms, profile["home_cms"], "home CMS")
        if replacements:
            current = repack_fsys(current, replacements)[0]
        if name == events.ARCHIVE_NAMES[0]:
            current = _append_boss_asset(current, read_archive(_DONOR))
            from .postgame_scene_model import append_field_model
            current, detail["lugia_model"] = append_field_model(
                current, original_rel, shiny=shiny, species=species, original_dol=original_dol,
                read_archive=read_archive, seed=seed)
        updates[name] = current
        reports.append({"archive": name, "sha256": sha256(current), "details": detail})
    return {"version": VERSION, "enabled": True, "archives": reports, "story_completion_flags": events.STORY_FLAGS,
            "required_shadow_ids": events.SHADOW_IDS, "capture_flag": CAPTURE_FLAG,
            "purification_flag": PURIFICATION_FLAG, "message_ids": MESSAGE_IDS, "native_battle_function": 152,
            "boss_actor": BOSS_ACTOR, "boss_field_model": BOSS_MODEL, "boss_disappears_after_capture": True,
            "boss_walks_to_exit": True, "partner_participates": True, "saved_player_names": True,
            "arrival_battle": BATTLE_ID, "scene_message_ids": tuple(scene_texts),
            "eagun_congratulates": True, "event_gifts_preserved": bool(options.accessible_event_gifts)}
