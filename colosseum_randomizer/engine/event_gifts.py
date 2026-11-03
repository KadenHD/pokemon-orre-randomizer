"""Regional event gifts from the existing Eagun actor at the Relic Stone.

Only exact original archives are accepted. Existing story scripts and opaque
text records remain intact; appended CMS code uses the native gift constructor,
receipt flags, party/PC routing and persistent purification flags. No file is
opened for writing by this module.

Format references: PekanMmd/Pokemon-XD-Code at
f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0, CMScript.swift,
CMScriptValueTypes.swift and XGSpecialStringCharacters.swift. Native PAL VM
checks qualified comparisons, call signatures, globals and story flags.
"""
from __future__ import annotations

import struct

from .analyze_game import FormatError, parse_fsys, sha256, u32
from .inspect_tables import u16
from .rebuild_iso import decoded_member, repack_fsys

VERSION = "purification-event-gifts-v1"
ARCHIVE_NAMES = ("M3_shrine_1F.fsys", "M3_houseC_1F.fsys")
ARCHIVE_SHA256 = {
    ARCHIVE_NAMES[0]: "79b8dcff18ec5d768010db1ca33ff0ea4ebeb6c8dcb8f93700f44c9b96ae1fa7",
    ARCHIVE_NAMES[1]: "33ec3db0325f1a70269cd996aaaefb9f9070d4841882f628dd930414c8a4de6d",
}
SHRINE_CMS_SHA256 = "f2215f011d7df99067b90e4ceb59cd64d13b4944f53fa9120249381433cb89ff"
SHRINE_REL_SHA256 = "b99386e0330b95435d75bc3d3e7a101c92f9216e0c2fcbce99032f0c1871006e"
HOME_CMS_SHA256 = "58d574a01f5ee35257b5b57087a4b9ae90a80ccc18f5608f5e4b78c508cf770e"
MESSAGE_BANKS = {
    "GE": (2, "6641f0238c1d99e00bcfe3588782f5e0b043a7d4aef2cd6b7a5683812a092f50"),
    "FR": (3, "a74428e781b23b698ff6345d9a21a492819b3bbb437e838764bfab0f44b205ae"),
    "UK": (4, "8bd4947753825c3ca957d20635281174f5dd1b3a0ebdee385a40e38aa6f1e4ea"),
    "SP": (5, "0cab0eb2cb774583f486d027bd23aff66f5d11ca4a0529eae41eb38570007b59"),
    "IT": (6, "f0effa93a423da9fc824f5f318df993a6882a2baa8a53d1aaae5e93f19aa8c37"),
}
# Defeat at the shrine, return home, tablet, incoming mail, mail read, final
# direction to Mt. Battle. The last flag is set at the end of the last scene.
STORY_FLAGS = (3527, 2582, 1067, 2860, 3531, 2875)
SHADOW_IDS = tuple(range(1, 45)) + (55, 56, 57, 67)
RECEIPT_FLAGS = {"pikachu-event": 2740, "celebi-event": 2737}
GIFT_IDS = {"pikachu-event": 5, "celebi-event": 6}
MESSAGE_IDS = tuple(range(0xF0000, 0xF0005))

# CMS function indices and patch sites are identical in the three original
# releases. Japan's home CMS differs in two unrelated camera float constants;
# its original hash is kept separately, and those bytes remain untouched.
# Actor member tails contain regional native links, so each full original actor
# is independently identified even though the modified actor fields match.
_REGIONAL_LAYOUTS = {
    "GC6P01": {"archives": ARCHIVE_SHA256, "actor": SHRINE_REL_SHA256,
                "home_cms": HOME_CMS_SHA256, "messages": MESSAGE_BANKS},
    "GC6E01": {
        "archives": {
            ARCHIVE_NAMES[0]: "c006d588d871ed8ca1470b6ca3851b97ce1ebd75075ed606a840df4af1cf41d7",
            ARCHIVE_NAMES[1]: "e370f30aa51b5e7a70e5c916c33fb8c3cbdf4b9444e08b0b3fdf7c74b7bc8776",
        },
        "actor": "ae3631ac3efaae69c39f8de1e25c19a111d9c80591280a249b74ff031d5ee74f",
        "home_cms": HOME_CMS_SHA256,
        "messages": {"US": (2, "598414cecbeded636daf045b613f0855f6a19890874931da2501d8e98c70cbb5")},
    },
    "GC6J01": {
        "archives": {
            ARCHIVE_NAMES[0]: "56ff2d8ef70e9af655ad803fe44a8b16361bea24a35f9f07f8969cf24a94a017",
            ARCHIVE_NAMES[1]: "4261a510eee5fb068309ec5e4f445889b500466be0919cd50cb3bba6994c0a67",
        },
        "actor": "45595a448d762addfdd2f877f6d8b9886d129e4a56b9e264a39ecd5d75e3d9ca",
        "home_cms": "1b81aa6f767ac96fe7621d257909da7c08d882292a1e237c7e425df184b0e125",
        "messages": {"JP": (2, "a254e0ad1bc66a6f904c35dec2f8940dd187aa722d2d6fe4cb39c469f31c517f")},
    },
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise FormatError(message)


def _fingerprint(data: bytes, expected: str, label: str) -> None:
    _require(sha256(data) == expected, f"unexpected original {label} fingerprint")


def _only_changes(original: bytes, output: bytes, ranges: tuple[tuple[int, int], ...]) -> None:
    _require(len(output) >= len(original), "event patch truncated original data")
    _require(all(0 <= start < end <= len(original) for start, end in ranges), "invalid event patch whitelist")
    _require(all(a == b or any(start <= index < end for start, end in ranges)
                 for index, (a, b) in enumerate(zip(original, output))), "event patch exceeded byte whitelist")


def _push(value: int) -> bytes:
    return b"\x08\x02" + struct.pack(">I", value & 0xFFFFFFFF)


def _local(index: int) -> bytes:
    return _push(index) + b"\x10\x42\x00\x01"


_POP = b"\x03\x82\x00\x01"


def _call(function: int, *arguments: int | bytes) -> bytes:
    # Local0 is the native script-thread context, not an extra native argument.
    params = b"".join(value if isinstance(value, bytes) else _push(value) for value in arguments)
    return _local(0) + _push(function) + params + b"\x25" + struct.pack(">HH", 1, len(arguments) + 1)


def _statement(function: int, *arguments: int | bytes) -> bytes:
    return _call(function, *arguments) + _POP


def _story_complete() -> bytes:
    return _call(81, STORY_FLAGS[0]) + b"".join(
        _call(81, flag) + b"\x21\x82\x82" for flag in STORY_FLAGS[1:])


def _purified_count() -> bytes:
    # Sum incrementally: at most a few operand values, below the VM's 64 slots.
    return _push(0) + b"".join(_call(81, 1261 + shadow_id) + b"\x17\x82\x82"
                              for shadow_id in SHADOW_IDS)


class _Assembler:
    def __init__(self, base: int):
        self.base = base
        self.code = bytearray()
        self.labels: dict[str, int] = {}
        self.jumps: list[tuple[int, str]] = []

    def emit(self, data: bytes) -> None:
        self.code.extend(data)

    def mark(self, name: str) -> None:
        _require(name not in self.labels, "duplicate event script label")
        self.labels[name] = self.base + len(self.code)

    def jump(self, label: str, *, when_false: bool = False) -> None:
        self.emit(b"\x07" if when_false else b"\x06")
        self.jumps.append((len(self.code), label))
        self.emit(bytes(4))

    def finish(self) -> bytes:
        for offset, label in self.jumps:
            _require(label in self.labels, "missing event script label")
            struct.pack_into(">I", self.code, offset, self.labels[label])
        return bytes(self.code)


def _talk(message: int) -> bytes:
    return _statement(54, _local(1), _local(2), message) + _statement(55, _local(1), _local(2))


def _interaction(base: int, pikachu: int, celebi: int) -> bytes:
    code = _Assembler(base)
    code.emit(_story_complete())
    code.jump("return", when_false=True)
    code.emit(_statement(32))
    for key, threshold in (("pikachu-event", pikachu), ("celebi-event", celebi)):
        code.emit(_call(81, RECEIPT_FLAGS[key]) + b"\x11\x82")
        code.jump(key, when_false=True)
        # Opcode28 is signed postfix A >= B, verified in the native PAL VM.
        code.emit(_purified_count() + _push(threshold) + b"\x1c\x82\x82")
        code.jump(key, when_false=True)
        code.emit(_talk(MESSAGE_IDS[0]))
        # Native217: 0..5 party slot, -1 sent to PC, -2 no room anywhere.
        code.emit(_call(217, GIFT_IDS[key]) + _push(-1) + b"\x1c\x82\x82")
        code.jump("full", when_false=True)
        code.emit(_statement(80, RECEIPT_FLAGS[key], 1))
        code.emit(_talk(MESSAGE_IDS[1]))
        code.jump("end")
        code.mark(key)
    code.emit(_call(81, RECEIPT_FLAGS["pikachu-event"]) +
              _call(81, RECEIPT_FLAGS["celebi-event"]) + b"\x21\x82\x82")
    code.jump("waiting", when_false=True)
    code.emit(_talk(MESSAGE_IDS[4]))
    code.jump("end")
    code.mark("waiting")
    code.emit(_talk(MESSAGE_IDS[3]))
    code.jump("end")
    code.mark("full")
    code.emit(_talk(MESSAGE_IDS[2]))
    code.mark("end")
    code.emit(_statement(33))
    code.mark("return")
    code.emit(b"\x05")
    return code.finish()


def _patch_shrine_cms(original: bytes, pikachu: int, celebi: int) -> tuple[bytes, dict]:
    _fingerprint(original, SHRINE_CMS_SHA256, "shrine CMS")
    _require(u16(original, 4) == 12 and u16(original, 6) == 0, "unexpected shrine function/relocation count")
    _require(u32(original, 12) == 0x48 and u32(original, 16) == 0x48 and
             original[0x48:0x50] == bytes(8), "unexpected shrine globals")
    _require(original[0x24A:0x250] == _push(0) and original[0x26A:0x270] == _push(0),
             "unexpected shrine visibility statement")
    result = bytearray(original + _interaction(len(original), pikachu, celebi))
    visibility = len(result)
    # Copy group/rid argument expressions verbatim; the group is local1.
    result.extend(original[0x24A:0x26A] + _story_complete() + original[0x270:0x279] +
                  b"\x06" + struct.pack(">I", 0x279))
    result[0x24A:0x24F] = b"\x06" + struct.pack(">I", visibility)
    result.extend(bytes(-len(result) % 4))
    globals_offset = len(result)
    result.extend(original[0x48:0x50])
    struct.pack_into(">H", result, 4, 13)
    struct.pack_into(">I", result, 0x48, len(original))
    # Header+0xc is an empty relocation table, +0x10 the two live globals.
    struct.pack_into(">II", result, 12, globals_offset, globals_offset)
    output = bytes(result)
    allowed = ((4, 6), (12, 20), (0x48, 0x4C), (0x24A, 0x24F))
    _only_changes(original, output, allowed)
    _require(output[globals_offset:globals_offset + 8] == original[0x48:0x50], "shrine globals changed")
    return output, {"interaction_index": 12, "interaction_offset": len(original),
                    "visibility_offset": visibility, "globals_offset": globals_offset,
                    "original_globals_preserved": True, "allowed_original_ranges": allowed}


def _patch_actor(original: bytes, expected: str = SHRINE_REL_SHA256) -> tuple[bytes, dict]:
    _fingerprint(original, expected, "shrine REL")
    _require(original[0x240] == 0 and u16(original, 0x242) == 0 and u16(original, 0x232) == 52,
             "unexpected Adelbert actor signature")
    result = bytearray(original)
    result[0x240] = 1
    struct.pack_into(">H", result, 0x242, 12)
    allowed = ((0x240, 0x241), (0x242, 0x244))
    _only_changes(original, bytes(result), allowed)
    return bytes(result), {"actor_index": 1, "model_index": 52, "model_unchanged": True,
                            "no_actor_added": True, "allowed_original_ranges": allowed}


def _patch_home_cms(original: bytes, expected: str = HOME_CMS_SHA256) -> tuple[bytes, dict]:
    _fingerprint(original, expected, "home CMS")
    epilogue = _push(0) + _push(1) + b"\x1f\x82\x42" + _POP + b"\x05"
    _require(original[0x678:0x68C] == epilogue and u32(original, 0x38) == 0x3561,
             "unexpected home setup/talk signature")
    code = _Assembler(len(original))
    code.emit(_story_complete())
    code.jump("epilogue", when_false=True)
    # Native hide50(local1, actor0, false), with the original argument expressions.
    code.emit(original[0x649:0x678])
    code.mark("epilogue")
    code.emit(epilogue)
    result = bytearray(original + code.finish())
    result[0x678:0x67D] = b"\x06" + struct.pack(">I", len(original))
    talk = _Assembler(len(result))
    talk.emit(_story_complete())
    talk.jump("original", when_false=True)
    talk.emit(b"\x05")
    talk.mark("original")
    talk.emit(b"\x06" + struct.pack(">I", 0x3561))
    result.extend(talk.finish())
    struct.pack_into(">I", result, 0x38, talk.base)
    allowed = ((0x38, 0x3C), (0x678, 0x67D))
    _only_changes(original, bytes(result), allowed)
    return bytes(result), {"setup_detour": len(original), "talk_guard": talk.base,
                            "original_talk_entry": 0x3561, "no_actor_added": True,
                            "allowed_original_ranges": allowed}


# Five localized native messages: offer, success, full storage, thresholds, done.
# Neither the species nor its shiny status is invented here: native217 constructs
# the already-patched special gift and routes it to the party or the PC.
_TEXTS = {
    "FR": ("Tu as aidé beaucoup de POKéMON.\nCe compagnon veut te suivre.",
           "Un nouveau compagnon t'a rejoint !\nPrends bien soin de lui.",
           "Ton équipe et tes Boîtes PC sont\npleines. Fais une place et reviens.",
           "Ces deux compagnons sont entre de\nbonnes mains. Prends soin d'eux."),
    "UK": ("You have helped many POKéMON.\nThis one would like to travel with you.",
           "You have a new companion!\nPlease take good care of it.",
           "Your party and PC Boxes are full.\nMake some room, then come back.",
           "Those two companions are in good\nhands. Please take care of them."),
    "GE": ("Du hast vielen POKéMON geholfen.\nDieses möchte dich nun begleiten.",
           "Du hast einen neuen Begleiter!\nKümmere dich gut um ihn.",
           "Dein Team und deine PC-Boxen sind voll.\nSchaffe Platz und komm dann zurück.",
           "Die beiden Begleiter sind bei dir\nin guten Händen. Sorge gut für sie."),
    "SP": ("Has ayudado a muchos POKéMON.\nEste quiere viajar contigo.",
           "¡Tienes un nuevo compañero!\nCuida muy bien de él.",
           "Tu equipo y las Cajas del PC están\nllenos. Haz sitio y vuelve después.",
           "Esos dos compañeros están en buenas\nmanos. Cuida bien de ellos."),
    "IT": ("Hai aiutato molti POKéMON.\nQuesto vorrebbe viaggiare con te.",
           "Hai un nuovo compagno!\nPrenditi cura di lui.",
           "La tua squadra e i BOX del PC sono\npieni. Fai spazio e poi torna.",
           "Quei due compagni sono in buone mani.\nPrenditi cura di loro."),
    "JP": ("リライブを　がんばっておるな。\nこのこを　つれていってくれ。",
           "あたらしい　なかまが　ふえたぞ！\nたいせつに　そだてておくれ。",
           "てもちも　パソコンも　いっぱいじゃ。\nあきを　つくって　また　おいで。",
           "あの２ひきを　よろしくな。\nたいせつに　そだてておくれ。"),
}


def _threshold_line(language: str, value: int, *, other: bool = False) -> str:
    if language == "JP":
        if value == 0:
            return "もうひとつ　うけとれるぞ。" if other else "プレゼントを　うけとれるぞ。"
        # Match the Japanese release's full-width typography. Counts still
        # come from the same independent configurable numerical thresholds.
        count = str(value).translate(str.maketrans("0123456789", "０１２３４５６７８９"))
        return f"つぎは　{count}ひき　リライブじゃ。" if other else f"{count}ひき　リライブで　プレゼントじゃ。"
    if value == 0:
        return {"FR": "Un autre cadeau est déjà disponible." if other else "Un cadeau est déjà disponible.",
                "UK": "Another gift is already available." if other else "One gift is already available.",
                "GE": "Ein weiteres Geschenk ist verfügbar." if other else "Ein Geschenk ist schon verfügbar.",
                "SP": "Ya puedes recibir el otro regalo." if other else "Ya puedes recibir un regalo.",
                "IT": "Un altro dono è già disponibile." if other else "Un dono è già disponibile."}[language]
    unit = {"FR": "purification" if value == 1 else "purifications",
            "UK": "purification" if value == 1 else "purifications",
            "GE": "Erlösung" if value == 1 else "Erlösungen",
            "SP": "purificación" if value == 1 else "purificaciones",
            "IT": "purificazione" if value == 1 else "purificazioni"}[language]
    prefix = {"FR": "Un autre dès" if other else "Un cadeau dès",
              "UK": "Another after" if other else "One gift after",
              "GE": "Ein weiteres nach" if other else "Ein Geschenk nach",
              "SP": "Otro tras" if other else "Un regalo tras",
              "IT": "Un altro dopo" if other else "Un dono dopo"}[language]
    return f"{prefix} {value} {unit}."


def _messages(language: str, pikachu: int, celebi: int) -> tuple[str, ...]:
    language = "UK" if language == "US" else language
    _require(language in _TEXTS, "unsupported event text language")
    first, success, full, done = _TEXTS[language]
    encouragement = {"FR": "Continue de purifier les POKéMON !", "UK": "Keep purifying Shadow POKéMON!",
                     "GE": "Erlöse weiterhin Crypto-POKéMON!", "SP": "¡Sigue purificando POKéMON oscuros!",
                     "IT": "Continua a purificare i POKéMON OMBRA!",
                     "JP": "ポケモンを　リライブしておいで。"}[language]
    thresholds = "\n".join((_threshold_line(language, pikachu),
                             _threshold_line(language, celebi, other=True), encouragement))
    return first, success, full, thresholds, done


def _encode_text(text: str) -> bytes:
    _require(bool(text) and "\0" not in text and "\uffff" not in text, "invalid event dialogue")
    try:
        return b"\xff\xff\x00".join(line.encode("utf-16-be") for line in text.split("\n")) + b"\xff\xff\x02\0\0"
    except UnicodeError as error:
        raise FormatError("invalid event dialogue encoding") from error


def _patch_message_bank(original: bytes, language: str, pikachu: int, celebi: int) -> tuple[bytes, dict]:
    _require(language in (*MESSAGE_BANKS, "US", "JP") and len(original) >= 16, "invalid native event message bank")
    tag = b"\0\0" if language == "JP" else language.encode("ascii")
    _require(original[:4] == bytes(4) and original[6:8] == tag, "unexpected native message header")
    count = u16(original, 4)
    directory_end = 16 + count * 8
    _require(0 < count <= 65535 - len(MESSAGE_IDS) and directory_end <= len(original), "invalid native message count")
    rows = [struct.unpack_from(">II", original, 16 + index * 8) for index in range(count)]
    old_ids = [identifier & 0xFFFFF for identifier, _ in rows]
    _require(len(set(old_ids)) == count and not set(old_ids) & set(MESSAGE_IDS), "duplicate or colliding event message ID")
    _require(all(directory_end <= offset <= len(original) - 2 for _, offset in rows), "native message pointer outside payload")
    growth = 8 * len(MESSAGE_IDS)
    header = bytearray(original[:16])
    struct.pack_into(">H", header, 4, count + len(MESSAGE_IDS))
    directory = bytearray(b"".join(struct.pack(">II", identifier, offset + growth) for identifier, offset in rows))
    payload = bytearray()
    texts = _messages(language, pikachu, celebi)
    for identifier, text in zip(MESSAGE_IDS, texts):
        directory.extend(struct.pack(">II", identifier, len(original) + growth + len(payload)))
        payload.extend(_encode_text(text))
    output = bytes(header + directory + original[directory_end:] + payload)
    # Keep entire old payload opaque: byte-parameter controls can have odd
    # addresses and embedded zeros, and several IDs may alias one allocation.
    _require(output[directory_end + growth:len(original) + growth] == original[directory_end:],
             "original native dialogue payload changed")
    _require(all(u32(output, 20 + index * 8) == offset + growth for index, (_, offset) in enumerate(rows)),
             "original native dialogue pointer changed unexpectedly")
    return output, {"language": language, "added_ids": MESSAGE_IDS, "texts": texts,
                    "original_ids_preserved": count, "opaque_allocations_and_aliases_preserved": True}


def patch_event_archive(source: bytes, name: str, options, *, region: str | None = None) -> tuple[bytes, dict]:
    """Return a separately rebuilt archive; input bytes and all source files stay unchanged."""
    _require(type(options.accessible_event_gifts) is bool, "invalid event-gift switch")
    if not options.accessible_event_gifts:
        return source, {"version": VERSION, "archive": name, "enabled": False}
    _require(name in ARCHIVE_NAMES, "unsupported event-gift archive")
    pikachu, celebi = options.event_pikachu_purifications, options.event_celebi_purifications
    _require(all(type(value) is int and 0 <= value <= 48 for value in (pikachu, celebi)), "invalid event purification threshold")
    fingerprint = sha256(source)
    candidates = [(game_id, profile) for game_id, profile in _REGIONAL_LAYOUTS.items()
                  if profile["archives"][name] == fingerprint and (region is None or region == game_id)]
    _require(len(candidates) == 1, f"unexpected original {name} fingerprint or region")
    _, profile = candidates[0]
    original = parse_fsys(source)
    members = {row["index"]: row for row in original["members"]}
    replacements, details = {}, {}
    texts = []
    if name == ARCHIVE_NAMES[0]:
        replacements[0], details["actor"] = _patch_actor(decoded_member(source, members[0]), profile["actor"])
        replacements[1], details["script"] = _patch_shrine_cms(decoded_member(source, members[1]), pikachu, celebi)
        for language, (index, expected) in profile["messages"].items():
            before = decoded_member(source, members[index])
            _fingerprint(before, expected, f"{language} shrine message bank")
            replacements[index], text_report = _patch_message_bank(before, language, pikachu, celebi)
            texts.append(text_report)
    else:
        replacements[1], details["script"] = _patch_home_cms(decoded_member(source, members[1]), profile["home_cms"])
    output, packing = repack_fsys(source, replacements)
    rebuilt = parse_fsys(output)
    _require(len(rebuilt["members"]) == len(original["members"]), "event archive member count changed")
    checks = []
    for before, after in zip(original["members"], rebuilt["members"]):
        index = before["index"]
        _require(all(before[key] == after[key] for key in ("index", "name", "identifier_raw", "compression")),
                 "event archive member identity changed")
        expected = replacements.get(index, decoded_member(source, before))
        current = decoded_member(output, after)
        _require(current == expected, "event archive decoded member differs from expected payload")
        checks.append({"index": index, "targeted": index in replacements, "sha256": sha256(current)})
    return output, {"version": VERSION, "enabled": True, "archive": name,
                    "before_sha256": sha256(source), "after_sha256": sha256(output),
                    "story_completion_flags": STORY_FLAGS, "receipt_flags": RECEIPT_FLAGS,
                    "native_gift_function": 217, "native_gift_ids": GIFT_IDS,
                    "thresholds": {"pikachu-event": pikachu, "celebi-event": celebi},
                    "party_or_pc_success_minimum": -1, "receipt_set_only_after_success": True,
                    "one_delivery_per_interaction": True, "no_actor_added": True,
                    "original_story_scenes_preserved": True, "home_shrine_exclusive_after_story": True,
                    "untargeted_decoded_members_unchanged": True, "members": checks,
                    "details": details, "native_texts": texts, "packing": packing}
