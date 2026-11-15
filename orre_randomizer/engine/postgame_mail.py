"""Native, persistent P★AD notification for the optional Colosseum Lugia rescue.

Append mail32 without replacing any retail message. A guarded hook sends it
only after a completed motorcycle trip to another overworld area.
Native sending owns insertion, the unread bit, sound and notification icon.
"""
from __future__ import annotations

import struct

from .analyze_game import FormatError, parse_fsys, parse_rel, sha256, u32
from .dol_regions import dol_layout
from .event_gifts import MASTER_BALL_NOTICE_FLAG, MASTER_BALL_RECEIPT_FLAG, SHADOW_IDS, STORY_FLAGS
from .gift_move_hooks import TEXT_TO_RAM, branch
from .inspect_tables import rel_symbols, u16
from .message_bank import message_directory
from .postgame_lugia import CAPTURE_FLAG, _extend_tables
from .postgame_scene_state import INTRO_STATE_FLAG, PHASE_AVAILABLE
from .rebuild_iso import decoded_member, repack_fsys
from .shiny_rules import _Code

VERSION = "colosseum-postgame-lugia-mail-v5"
MAIL_ID = 32
SENDER_ID = 0x3ED3  # Retail Eagun sender, including its localized hometown.
SUBJECT_ID, BODY_ID = 0xF0030, 0xF0031
REQUIRED_FLAGS = STORY_FLAGS + tuple(start + sid for start in (2125, 1261) for sid in SHADOW_IDS)

# Independently inspected revision-0 callbacks, not a shared regional shift.
# hook, native chkMailSend, mailGetReceiveNumber, std081_flagCheckTrue
_LAYOUTS = {
    "GC6P01": (0x801D7098, 0x801D6DE4, 0x801D64D0, 0x80194654),
    "GC6E01": (0x801D2A18, 0x801D2764, 0x801D1E50, 0x801902E0),
    "GC6J01": (0x801CE3DC, 0x801CE0C8, 0x801CD6B4, 0x8018BEA4),
}
# Native mission-state accessors, qualified independently in each region.
_STATE_LAYOUTS = {
    "GC6P01": (0x80194A14, 0x80194AD0, (
        "b148e4825affeed0a1859b1372cba43d653a19fa5e6b85c60d4b7f5e2a896c67",
        "ea5eaad0a58212d3e01ff5316e98ce42cbe24de57272b24e40762716bed665cd")),
    "GC6E01": (0x801906A0, 0x8019075C, (
        "fe0bea265e2e565807db04f15b5733e88db90f363fe700e94ab9879f18c3a12a",
        "ea5eaad0a58212d3e01ff5316e98ce42cbe24de57272b24e40762716bed665cd")),
    "GC6J01": (0x8018C264, 0x8018C320, (
        "14a15053f05700f75f8c838f0f60dba93dc68fadafc68fd0d98ad30e07e6bac2",
        "ea5eaad0a58212d3e01ff5316e98ce42cbe24de57272b24e40762716bed665cd")),
}
# Manual sending bypasses automatic eligibility; the native mailbox owns receipt.
_SENDER_LAYOUTS = {
    "GC6P01": (0x801D6700, 0xEC, "c76629dde3462bd36b1e3cc14032f3fccff4da7517e57b42f4eb0c6ee625c88b"),
    "GC6E01": (0x801D2080, 0xEC, "c19b7ed74b0e1f3c0528b2c32d41b8d3767da2ca911620c155275057405bf630"),
    "GC6J01": (0x801CD8E4, 0x134, "746dc208622aa3c865d4e0d877266547ef5c101ce3dcbfb58f8a9164db3d78a0"),
}
# worldMapMain terminal floorLink call and the native completed-ride marker.
# Pin Main, Pre/reset, floorLink and the separate ride body where present.
# The Japanese executable inlines BikeRide in Main.
_TRAVEL_LAYOUTS = {
    "GC6P01": (0x80027574, 0x801170CC, -0x6494, (
        (0x80027318, 0x280, "9d6befb75c73fefe7748fc211954fcd2512d5e2716a215ec7a80365290224ad2"),
        (0x80027598, 0xCC, "45cacf647e4e94525fd768546db7834496792ac7eefafb44e519fb20e5079720"),
        (0x801170CC, 0x64, "54ff7fa808daa46e7bcf52aff7108b5d67747570f055567ac58756fe3d59beee"),
        (0x80027B6C, 0x3EC, "22b4d75baf08444319dd65dd897d83760a7c99dd4b2de85be60010961bd77f37"),
    )),
    "GC6E01": (0x8002598C, 0x80113828, -0x649C, (
        (0x80025730, 0x280, "a54dc1c939920ef9032b1dc1ffa7ef0c65ce28a02d4dc90907e77cc7c8835cfb"),
        (0x800259B0, 0xCC, "aaa4918144c8af16361d687994dddb00a3547294b0e763cae0ca3394100bc874"),
        (0x80113828, 0x64, "537d83eddc80fcb8595032985cd82b2b324f27ff63d31e5b9a818e185df24e62"),
        (0x80025F84, 0x3EC, "190f32ccc3c2a8bf0a026829ea4302f3d9229bd32a47e1e0c6c511af3a5e5c05"),
    )),
    "GC6J01": (0x80025B74, 0x801110F8, -0x64B4, (
        (0x80025640, 0x54C, "160f41838c3ba7f5848e81d86b0469e0bc8007ba10afd6b042179118ee664ddd"),
        (0x80025B8C, 0xCC, "34be57a40bb8e8b125e395cd0536b15f91403bf6ec07eb689ba33bc2c009b3db"),
        (0x801110F8, 0x64, "1d9994574bb06e3c4b2962566feb9846c58331ac7bd7c6fb6b04ccd3b520e186"),
    )),
}
# First unconditional call in the native field-update callback. World-map
# transitions terminate mail notifications, so send only on the loaded field.
# hook, original callee, notification-active word, full callback fingerprint
_ARRIVAL_LAYOUTS = {
    "GC6P01": (0x801172C8, 0x8011AB8C, 0x804B4810,
                (0x801172B0, 0x178, "e9074d60380b454a67e91292f5bb32ffc9b9767a1280ae097bd86258d15fc266")),
    "GC6E01": (0x80113A24, 0x801171C8, 0x80467390,
                (0x80113A0C, 0x178, "034c7d0d5563d21eb4df45d48b70cd8b66f3ef94281b681959eaec59aa7a96ec")),
    "GC6J01": (0x801112F4, 0x801149EC, 0x80452A70,
                (0x801112DC, 0x178, "420fe9d8d1e756a4183c56d9ea17d64115f2d374c9081f0bf1b9e510df3a0eb8")),
}
_MAIL_HASHES = {
    "GC6P01": "91c50ed50e7a879b61a4be44d8665c429e9a586681daf2805418183b68672fbe",
    "GC6E01": "f410ee6c1c8c55dbeda1b620da9721ecdee15460c1bd17d82763d4f14e201c92",
    "GC6J01": "cec84cfb06380fe5dacaa9bab04a2a2e614e6dce7d2f8887c42383ac4a94ac65",
}
_BANK_HASHES = {
    "UK": "2423f0300be38f1909d8f817552767746a5a3bc852da6dfc5ddf029070ee59f1",
    "US": "42cd440b9aaebc39ca81e426858927ba8ab2c9e1543ce791fac4af69b0880dab",
    "FR": "47628160ca313131bc7a8ab4c350607be62004125833219b3208b656a659913e",
    "GE": "6ee23f6cf3b76f4e095e9c543f932ea8de0e4330b38c7eec3385fe678745f7e2",
    "IT": "af9fb874db712a62704b6444d694d864016299f498b00c5f6a2037331c35acd8",
    "SP": "1e61b6547648137105e47233df511ffbbe7134c635a377b7d762f8eaaaff8fff",
    "JP": "92f971f7d013c04dbfd5e4618b63ccbc3a1d97592b1647b1aa7a02ef7f96b3ab",
}
_SUFFIXES = {"UK": "", "US": "", "JP": "", "FR": "_fr", "GE": "_ge", "IT": "_it", "SP": "_sp"}
_REGION_LANGUAGES = {"GC6P01": ("UK", "GE", "FR", "IT", "SP"), "GC6E01": ("US",), "GC6J01": ("JP",)}

# Mail uses explicit native line feeds, unlike dialogue pages. Keep lines short
# enough for the retail P★AD body panel and let its existing scrollbar paginate.
TEXTS = {
    "UK": ("Relic Stone SOS",
           "NASCOUR has returned!\nCIPHER has sent him with a\nShadow LUGIA to destroy the\nRELIC STONE. We need your help!\nMeet me at the RELIC STONE."),
    "FR": ("SOS Relique",
           "JAKYLLA est revenu !\nLe GROUPE OMBRE lui a confié un\nLUGIA obscur pour détruire la\nRelique Sacrée. Nous avons\nbesoin de ton aide !\nRejoins-moi à la Relique Sacrée."),
    "GE": ("SOS Sanktuarium",
           "JAKIRA ist zurück!\nCRYPTO hat ihn mit Crypto-LUGIA\ngeschickt, um das Sanktuarium\nzu zerstören. Wir brauchen\ndeine Hilfe!\nKomm zum Sanktuarium!"),
    "SP": ("SOS en la Piedra",
           "¡FÚSTEO ha vuelto!\nCÍFER le ha enviado con un\nLUGIA oscuro para destruir la\nPiedra Sagrada. ¡Te necesitamos!\nVen a verme a la Piedra Sagrada."),
    "IT": ("SOS SACRA PIETRA",
           "NASCOUR è tornato!\nLa CRIPTO lo ha mandato con un\nLUGIA OMBRA per distruggere la\nSACRA PIETRA. Ci serve il tuo\naiuto! Raggiungimi alla\nSACRA PIETRA."),
    "JP": ("ほこらがあぶない",
           "ジャキラが　もどってきた！\nシャドーは　ダークルギアで\nほこらを　こわすつもりだ。\nきみの　ちからが　ひつようだ！\nほこらまで　きてくれ！"),
}
TEXTS["US"] = TEXTS["UK"]


def _require(condition, message):
    if not condition:
        raise FormatError(message)


def _mail_record():
    record = bytearray(0x2C)
    # Disable other automatic send paths, including native "send all". Only the
    # guarded completed-trip flow below can send this new ID.
    record[:2] = b"\xff\xff"
    for offset in (2, 4, 6, 8):
        struct.pack_into(">H", record, offset, 0xFFFF)
    struct.pack_into(">III", record, 12, SENDER_ID, SUBJECT_ID, BODY_ID)
    return bytes(record)


def patch_mail_rel(original, game_id):
    _require(game_id in _MAIL_HASHES and sha256(original) == _MAIL_HASHES[game_id],
             "unexpected native Colosseum mail REL")
    symbols = rel_symbols(original, parse_rel(original))
    _require(len(symbols) == 4 and u32(original, symbols[3]["offset"]) == MAIL_ID,
             "unexpected native mailbox table")
    output, report = _extend_tables(original, original, symbols,
                                   (("mail", 2, 3, 0x2C, MAIL_ID, _mail_record()),), section_index=3)
    return output, {"id": MAIL_ID, "sender_id": SENDER_ID, "subject_id": SUBJECT_ID,
                    "body_id": BODY_ID, "unread_on_receipt": True, "native_mail_preserved": True,
                    "read_has_no_story_effects": True, **report}


def _requirements(code, flag_check, *, available="available", unavailable="unavailable"):
    """The same original completion and story checks for sending and migration."""
    code.emit(0x38600000 | CAPTURE_FLAG)
    code.call(flag_check)
    code.emit(0x5463063E, 0x28030000)
    code.conditional(0x40820000, unavailable)
    for flag in REQUIRED_FLAGS:
        code.emit(0x38600000 | flag)
        code.call(flag_check)
        code.emit(0x5463063E, 0x28030000)
        code.conditional(0x41820000, unavailable)
    code.emit(0x38600000 | MASTER_BALL_NOTICE_FLAG)
    code.call(flag_check)
    code.emit(0x5463063E, 0x28030000)
    code.conditional(0x41820000, available)
    code.emit(0x38600000 | MASTER_BALL_RECEIPT_FLAG)
    code.call(flag_check)
    code.emit(0x5463063E, 0x28030000)
    code.conditional(0x41820000, unavailable)


def _automatic_mail_guard(address, native):
    """Keep retail automatic mail intact; only the trip hook can send mail32."""
    code = _Code(address)
    code.emit(0x28030000 | MAIL_ID)
    code.conditional(0x41820000, "bonus")
    code.emit(branch(address + len(code.words) * 4, native))
    code.label("bonus")
    code.emit(0x38600000, 0x4E800020)
    return code.finish()


def _completed_trip_stub(address, native_link, *, flag_check, state_get,
                         ride_displacement, pending):
    """Queue an eligible completed ride, then tail-call unchanged floorLink.

    The selected destination and entrance are live in r3/r4 at this callsite.
    Keep them outside the outgoing argument area while native mail calls run.
    Other volatile registers and CR/FPRs are not live across floorLink.
    """
    _require(-32768 <= ride_displacement <= 32767, "invalid native ride marker offset")
    code = _Code(address)
    code.emit(0x9421FFC0, 0x7C0802A6, 0x90010044,
              0x90610028, 0x9081002C)
    code.emit(0x800D0000 | (ride_displacement & 0xFFFF), 0x2C000000)
    code.conditional(0x41820000, "finish")
    code.emit(0x38600000 | INTRO_STATE_FLAG)
    code.call(state_get)
    code.emit(0x28030000)
    code.conditional(0x40820000, "finish")
    _requirements(code, flag_check, available="queue", unavailable="finish")
    code.label("queue")
    code.emit(0x3D800000 | (pending >> 16), 0x618C0000 | (pending & 0xFFFF),
              0x38000001, 0x900C0000)
    code.label("finish")
    code.emit(0x80610028, 0x8081002C, 0x80010044,
              0x7C0803A6, 0x38210040)
    code.emit(branch(address + len(code.words) * 4, native_link))
    return code.finish()


def _arrival_mail_stub(address, native_update, send, *, received, flag_check,
                       state_get, state_set, pending, notification):
    """Consume the trip on the loaded field, after any retail mail notification.

    The original zero-argument update is always called first; retain its return
    value as well as SP/LR/nonvolatiles. The pending word belongs to the appended
    DOL reservation, starts at zero and is never written into a save.
    """
    code = _Code(address)
    code.emit(0x9421FFC0, 0x7C0802A6, 0x90010044)
    code.call(native_update)
    code.emit(0x90610028,
              0x3D800000 | (pending >> 16), 0x618C0000 | (pending & 0xFFFF),
              0x800C0000, 0x2C000000)
    code.conditional(0x41820000, "finish")
    code.emit(0x3D600000 | (notification >> 16), 0x616B0000 | (notification & 0xFFFF),
              0x800B0000, 0x2C000000)
    code.conditional(0x40820000, "finish")
    code.emit(0x38000000, 0x900C0000)
    code.emit(0x38600000 | INTRO_STATE_FLAG)
    code.call(state_get)
    code.emit(0x28030000)
    code.conditional(0x40820000, "finish")
    _requirements(code, flag_check, available="receipt", unavailable="finish")
    code.label("receipt")
    code.emit(0x38600000 | MAIL_ID)
    code.call(received)
    code.emit(0x2C030000)
    code.conditional(0x40800000, "activate")
    code.emit(0x38600000 | MAIL_ID)
    code.call(send)
    code.emit(0x38600000 | MAIL_ID)
    code.call(received)
    code.emit(0x2C030000)
    code.conditional(0x41800000, "finish")
    code.label("activate")
    code.emit(0x38600000 | INTRO_STATE_FLAG, 0x38800000 | PHASE_AVAILABLE)
    code.call(state_set)
    code.label("finish")
    code.emit(0x80610028, 0x80010044, 0x7C0803A6, 0x38210040, 0x4E800020)
    return code.finish()


def install_mail_hook(original, current):
    from ..snag_list import _append_colo
    region = dol_layout(original)
    automatic_hook, native, received, flag_check = _LAYOUTS[region.game_id]
    state_get, state_set, state_hashes = _STATE_LAYOUTS[region.game_id]
    send, send_size, send_hash = _SENDER_LAYOUTS[region.game_id]
    trip_hook, native_link, ride_displacement, travel_dependencies = _TRAVEL_LAYOUTS[region.game_id]
    arrival_hook, native_update, notification, arrival_dependency = _ARRIVAL_LAYOUTS[region.game_id]
    dependencies = [(target, 64, expected) for target, expected in
                    zip((state_get, state_set), state_hashes, strict=True)]
    dependencies.extend(((send, send_size, send_hash), *travel_dependencies, arrival_dependency))
    for target, size, expected in dependencies:
        offset = target - TEXT_TO_RAM
        _require(all(sha256(data[offset:offset + size]) == expected for data in (original, current)),
                 "unexpected native Lugia mail or motorcycle dependency")
    expected_prefixes = (
        (native, "9421ffd07c0802a690010034dbe10020"),
        (received, "9421ffe07c0802a690010024bf61000c7c7b1b78"),
        (flag_check, "9421fff07c0802a6546718389001001480cd877c806d86cc7c8638ae5480eef8"),
    )
    for target, prefix in expected_prefixes:
        data = bytes.fromhex(prefix)
        offset = target - TEXT_TO_RAM
        _require(all(d[offset:offset + len(data)] == data for d in (original, current)),
                 "unexpected native mail eligibility dependency")
    output, hooks = _append_colo(original, current, region, automatic_hook,
                                 branch(automatic_hook, native, link=True),
                                 lambda address: _automatic_mail_guard(address, native))
    def trip_bundle(address):
        arguments = dict(flag_check=flag_check, state_get=state_get, ride_displacement=ride_displacement)
        size = len(_completed_trip_stub(address, native_link, pending=0, **arguments))
        return _completed_trip_stub(address, native_link, pending=address + size, **arguments) + bytes(32)

    output, trip_hooks = _append_colo(original, output, region, trip_hook,
                                      branch(trip_hook, native_link, link=True),
                                      trip_bundle)
    hooks.extend(trip_hooks)
    pending = trip_hooks[0]["stub_address"] + trip_hooks[0]["stub_size"] - 32
    output, arrival_hooks = _append_colo(original, output, region, arrival_hook,
        branch(arrival_hook, native_update, link=True),
        lambda address: _arrival_mail_stub(address, native_update, send, received=received,
            flag_check=flag_check, state_get=state_get, state_set=state_set,
            pending=pending, notification=notification))
    hooks.extend(arrival_hooks)
    return output, {"version": VERSION, "hooks": hooks,
                    "trigger": "first completed motorcycle trip to a different area",
                    "required_captures": 48, "required_purifications": 48,
                    "story_flags": STORY_FLAGS, "pending_master_ball_takes_priority": True,
                    "one_time_native_mailbox": True, "automatic_bonus_mail_disabled": True,
                    "travel_hook_address": trip_hook, "ride_marker_displacement": ride_displacement,
                    "arrival_hook_address": arrival_hook, "transient_pending_address": pending,
                    "notification_after_arrival": True, "native_mail_notification_priority": True,
                    "native_step_callbacks_preserved": True, "native_destination_preserved": True,
                    "activation_requires_native_receipt": True}


def mail_texts(language, species_name=None):
    subject, body = TEXTS[language]
    if species_name is not None:
        import textwrap
        from .postgame_scene_text import event_species_text
        body = event_species_text(body.replace("\n", " "), language, species_name)
        # The native mailbox scrolls vertically. Reflow the whole body so a
        # longer replacement name cannot overflow an authored Lugia line.
        lines = ([body[index:index + 14] for index in range(0, len(body), 14)] if language == "JP"
                 else textwrap.wrap(body, width=29, break_long_words=False, break_on_hyphens=False))
        body = "\n".join(lines)
    return subject, body


def _append_texts(source, language, *, species_name=None):
    rows = message_directory(source)
    _require(SENDER_ID in rows and not {SUBJECT_ID, BODY_ID} & rows.keys(), "unexpected P★AD message IDs")
    count = u16(source, 4)
    _require(count <= 65533, "full P★AD message directory")
    subject, body = mail_texts(language, species_name)
    # Subject has the same native style as existing mail subjects. The body has
    # no dialogue pause/close opcode and no callbacks, just text and line feeds.
    payloads = (b"\xff\xff\x07\x03" + subject.encode("utf-16-be") + b"\0\0",
                b"\xff\xff\x00".join(line.encode("utf-16-be") for line in body.split("\n")) + b"\0\0")
    directory_end = 16 + count * 8
    header = bytearray(source[:16])
    struct.pack_into(">H", header, 4, count + 2)
    directory = bytearray()
    for pos in range(16, directory_end, 8):
        identifier, pointer = struct.unpack_from(">II", source, pos)
        directory.extend(struct.pack(">II", identifier, pointer + 16))
    payload = bytearray()
    for identifier, text in zip((SUBJECT_ID, BODY_ID), payloads, strict=True):
        directory.extend(struct.pack(">II", identifier, len(source) + 16 + len(payload)))
        payload.extend(text)
    return bytes(header + directory + source[directory_end:] + payload)


def patch_mail_archives(game_id, read_archive, updates, *, species_names=None):
    report = {}
    for language in _REGION_LANGUAGES[game_id]:
        filename = f"pda_menu{_SUFFIXES[language]}.fsys"
        original = read_archive(filename)
        current = updates.get(filename, original)
        members = [m for m in parse_fsys(original)["members"] if int(m["identifier_raw"], 16) & 0xFF00 == 0x0A00]
        _require(len(members) == 1, "unexpected P★AD language bank allocation")
        member = members[0]
        bank = decoded_member(original, member)
        _require(sha256(bank) == _BANK_HASHES[language], "unexpected original P★AD message bank")
        current_member = parse_fsys(current)["members"][member["index"]]
        _require(current_member["identifier_raw"] == member["identifier_raw"], "P★AD member moved")
        existing = decoded_member(current, current_member)
        species_name = species_names[language] if species_names is not None else None
        updated = _append_texts(existing, language, species_name=species_name)
        updates[filename] = repack_fsys(current, {member["index"]: updated})[0]
        subject, body = mail_texts(language, species_name)
        report[language] = {"archive": filename, "subject": subject, "body": body}
    return report
