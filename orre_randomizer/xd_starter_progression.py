"""Preserve XD's first Chobin scene after a randomized starter loses once.

The original loss path returns to Kaminko without running the post-battle
scene. Its second-entry branch normally repeats battle 222 indefinitely for a
passive starter. Neutralize only that retry call; its native stack cleanup,
Jovi scene and story flag write remain byte-identical. One shared reply is
neutral about the battle winner in every retail language. No DOL/deck is edited.
"""
from __future__ import annotations

from .engine.analyze_game import FormatError, parse_fsys, sha256
from .engine.message_bank import _CONTROL_ARGUMENTS, message_directory, patch_messages
from .engine.rebuild_iso import decoded_member, repack_fsys

VERSION = "xd-first-chobin-loss-v1"
ARCHIVE = "S3_out.fsys"
SCRIPT = "S3_out"
SCRIPT_BYTES = 31_664
SCRIPT_SHA256 = {
    "GXXP01": "bac80842c8f83957412d080de0df9fdd86fc536814ea9052c130394ff746d71a",
    "GXXE01": "bac80842c8f83957412d080de0df9fdd86fc536814ea9052c130394ff746d71a",
    "GXXJ01": "0a19df8c2b045547e3019f264199827cc51fafa4793b93182c96528883ed792d",
}
ORIGINAL_ARCHIVES = {
    "GXXP01": "0854f460bc29a4967aa4108002519eb46cefb052e251ace3e8bb9599422b2393",
    "GXXE01": "f456de7dafacc199b7f5ce58a115e95d5e82e1bc3418b27bfa4066876f314d3d",
    "GXXJ01": "04df31ea9bfefcd59660a6ef0d8db6587ef197b7ce47a1a883e695e3dcc0d5cc",
}
FIRST_CALL = 0x4A20
RETRY_CALL = 0x4BDC
WINDOW_START = 0x4BC0
# Two integer arguments, battle ID 222, Battle object, call and pop4, then
# native map-resume handling, scene call and setFlag(964, 40). All three retail
# scripts share this complete window. Their complete fingerprints are checked
# independently; Japan contains unrelated native camera differences.
RETRY_WINDOW = bytes.fromhex(
    "0201000000000001020100000000000102010000000000de1103002a092a001006040000"
    "1000069e020100000000000211030026092600100601000003020000020100000000008a"
    "110300260926001506040000100006a307001274100006a6020100000000002802010000"
    "000003c40900008306020000"
)
CALL = bytes.fromhex("092a0010")
NOP = bytes(4)
MESSAGE_ID = 0xABE4
_LINE = bytes.fromhex("ffff00")
_SPEAKER = bytes.fromhex("ffff59")
_END = bytes.fromhex("ffff030000")
_LANGUAGES = {"GXXP01": {"UK", "FR", "GE", "IT", "SP"}, "GXXE01": {"US"}, "GXXJ01": {"JP"}}


def _message(*lines):
    return _SPEAKER + _LINE.join(line.encode("utf-16-be") if isinstance(line, str) else line
                                 for line in lines) + _END


def _ruby(before, kanji, reading, after):
    return (before.encode("utf-16-be") + bytes.fromhex("ffff04") + kanji.encode("utf-16-be")
            + bytes.fromhex("ffff05") + reading.encode("utf-16-be")
            + bytes.fromhex("ffff06") + after.encode("utf-16-be"))


_ENGLISH = (
    _message(": You've made CHOBIN angry now!", "Even though CHOBIN lost, you're still not going", "past CHOBIN!"),
    _message(": You've made CHOBIN angry now!", "You're still not going past CHOBIN!"),
)
# Retain native speaker/name, page and Japanese ruby controls. Western replies
# use one fewer line break. Only this reply loses its assumed battle winner.
_DIALOGUE = {
    "UK": _ENGLISH, "US": _ENGLISH,
    "FR": (
        _message(": Maintenant DARIUS est en", "colère! Même si DARIUS a perdu, tu ne passes", "pas!"),
        _message(": Maintenant DARIUS est en", "colère ! Tu ne passes pas !"),
    ),
    "GE": (
        _message(": Jetzt ist CALVIN sauer!", "Obwohl du CALVIN besiegt hast, lässt", "dieser CALVIN dich nicht passieren! So!"),
        _message(": Jetzt ist CALVIN sauer!", "CALVIN lässt dich nicht passieren! So!"),
    ),
    "SP": (
        _message(": ¡Has enfadado a ASISTO!", "¡Aunque hayas ganado a ASISTO,", "ASISTO no te dejará pasar!"),
        _message(": ¡Has enfadado a ASISTO!", "¡ASISTO no te dejará pasar!"),
    ),
    "IT": (
        _message(": Hai fatto arrabbiare UGO!", "Anche se UGO ha perso, non la farai franca", "con UGO!"),
        _message(": Hai fatto arrabbiare UGO!", "Non la farai franca con UGO!"),
    ),
    "JP": (
        _message("「おのれ　おのれー！", _ruby("たとえ　バトルに", "負", "ま", "けても"),
                 _ruby("ここを　", "通", "とお", "すわけには　いかないぞ！")),
        _message("「おのれ　おのれー！", _ruby("たとえ　", "何", "なに", "があっても"),
                 _ruby("ここを　", "通", "とお", "すわけには　いかないぞ！")),
    ),
}


def _control_sequence(record):
    result, cursor = [], 0
    while cursor + 1 < len(record) and record[cursor:cursor + 2] != bytes(2):
        if record[cursor:cursor + 2] == b"\xff\xff":
            end = cursor + 3 + _CONTROL_ARGUMENTS.get(record[cursor + 2], 0)
            result.append(record[cursor:end])
            cursor = end
        else:
            cursor += 2
    return tuple(result)


def _dialogue_controls_preserved(before, after, language):
    original, updated = _control_sequence(before), _control_sequence(after)
    if language == "JP":
        return original == updated
    return (original.count(_LINE) == 2 and updated.count(_LINE) == 1
            and tuple(control for control in original if control != _LINE)
            == tuple(control for control in updated if control != _LINE))


def _dialogue_banks(archive, game_id):
    found = {}
    for member in parse_fsys(archive)["members"]:
        if int(member["identifier_raw"], 16) & 0xFF00 != 0x0A00:
            continue
        bank = decoded_member(archive, member)
        language = bank[6:8].decode("ascii", errors="replace")
        _require(language in _LANGUAGES[game_id] and language not in found,
                 "unknown or duplicate first-Chobin dialogue language")
        found[language] = member, bank
    _require(set(found) == _LANGUAGES[game_id], "missing first-Chobin dialogue language")
    return found


def _require_message(bank, expected):
    directory = message_directory(bank)
    _require(MESSAGE_ID in directory, "missing first-Chobin post-battle reply")
    pointer = directory[MESSAGE_ID][1]
    _require(bank[pointer:pointer + len(expected)] == expected,
             "unknown first-Chobin post-battle reply")


def _require(condition, message):
    if not condition:
        raise FormatError(message)


def _retry_window(window: bytes, *, patched: bool = False) -> bytes:
    """A bounded stack/return contract, independently exercisable without a ROM."""
    expected = bytearray(RETRY_WINDOW)
    relative = RETRY_CALL - WINDOW_START
    if patched:
        expected[relative:relative + 4] = NOP
    _require(window == bytes(expected), "unknown first-Chobin retry stack/continuation contract")
    output = bytearray(window)
    output[relative:relative + 4] = NOP
    return bytes(output)


def _script(archive: bytes):
    members = parse_fsys(archive)["members"]
    scripts = [member for member in members
               if member["name"] == SCRIPT and int(member["identifier_raw"], 16) & 0xFF00 == 0x0E00]
    _require(len(scripts) == 1, "missing or ambiguous first-Chobin script")
    return scripts[0], decoded_member(archive, scripts[0])


def _original_script(archive: bytes, game_id: str):
    _require(game_id in ORIGINAL_ARCHIVES, "unsupported first-Chobin script region")
    _require(sha256(archive) == ORIGINAL_ARCHIVES[game_id], "unknown original first-Chobin archive")
    member, script = _script(archive)
    _require(len(script) == SCRIPT_BYTES and sha256(script) == SCRIPT_SHA256[game_id],
             "unknown original first-Chobin script fingerprint")
    _require(script[FIRST_CALL:FIRST_CALL + 4] == CALL, "unknown first-Chobin initial battle call")
    _retry_window(script[WINDOW_START:WINDOW_START + len(RETRY_WINDOW)])
    return member, script


def validate_starter_progression(original_archive: bytes, updated_archive: bytes, game_id: str) -> dict:
    """Validate the final script even when other rules edited archive messages.

    This certifies the retry script and its one localized reply. The creation
    planner retains responsibility for any other message/model archive changes.
    """
    _, original = _original_script(original_archive, game_id)
    _, updated = _script(updated_archive)
    expected = bytearray(original)
    expected[RETRY_CALL:RETRY_CALL + 4] = NOP
    _require(updated == bytes(expected), "first-Chobin script changed outside its single retry call")
    _retry_window(updated[WINDOW_START:WINDOW_START + len(RETRY_WINDOW)], patched=True)
    languages = []
    original_banks = _dialogue_banks(original_archive, game_id)
    for language, (_, bank) in _dialogue_banks(updated_archive, game_id).items():
        before, after = _DIALOGUE[language]
        _require_message(original_banks[language][1], before)
        _require_message(bank, after)
        _require(_dialogue_controls_preserved(before, after, language), "first-Chobin dialogue controls changed")
        languages.append(language)
    return {
        "version": VERSION, "game_id": game_id, "archive": ARCHIVE,
        "script_sha256_before": sha256(original), "script_sha256_after": sha256(updated),
        "enabled": True, "validated": True, "battle_id": 222,
        "retry_call_offset": RETRY_CALL, "retry_call_before": CALL.hex(), "retry_call_after": NOP.hex(),
        "only_retry_instruction_changed": True, "native_pop4_preserved": True,
        "battle_return_value_not_consumed": True,
        "first_attempt_preserved": True, "native_victory_path_preserved": True,
        "native_victory_control_flow_preserved": True,
        "shared_reply_neutralized": True, "neutral_reply_message_id": MESSAGE_ID,
        "neutral_reply_languages": sorted(languages), "native_dialogue_controls_preserved": True,
        "western_reply_line_breaks_removed": 1, "japanese_reply_line_breaks_preserved": True,
        "native_jovi_scene_preserved": True, "later_battles_preserved": True,
        "native_post_scene_flag": {"flag": 964, "value": 40},
        "new_flags_added": False, "species_moves_and_pid_edited": False,
        "scope": "First-Chobin retry script and one neutral localized reply; other changes validated by their owning rules",
    }


def patch_starter_progression(archive: bytes, game_id: str, *, current_archive: bytes | None = None) -> tuple[bytes, dict]:
    """Patch an exact retail archive; the caller chooses gameplay activation."""
    _, original = _original_script(archive, game_id)
    current = archive if current_archive is None else current_archive
    member, current_script = _script(current)
    _require(current_script == original, "current first-Chobin script already differs from its native source")
    updated = bytearray(original)
    updated[WINDOW_START:WINDOW_START + len(RETRY_WINDOW)] = _retry_window(
        original[WINDOW_START:WINDOW_START + len(RETRY_WINDOW)])
    replacements = {member["index"]: bytes(updated)}
    original_banks = _dialogue_banks(archive, game_id)
    for language, (bank_member, bank) in _dialogue_banks(current, game_id).items():
        before, after = _DIALOGUE[language]
        _require_message(original_banks[language][1], before)
        _require_message(bank, before)
        replacements[bank_member["index"]] = patch_messages(bank, {MESSAGE_ID: lambda _before, value=after: value})
    output, _ = repack_fsys(current, replacements)
    report = validate_starter_progression(archive, output, game_id)
    before_members = parse_fsys(current)["members"]
    after_members = parse_fsys(output)["members"]
    _require(len(before_members) == len(after_members), "first-Chobin patch changed archive membership")
    for before, after in zip(before_members, after_members, strict=True):
        _require((before["name"], before["identifier_raw"]) == (after["name"], after["identifier_raw"]),
                 "first-Chobin patch changed archive member identity")
        if before["index"] not in replacements:
            _require(decoded_member(current, before) == decoded_member(output, after),
                     "first-Chobin patch changed another archive payload")
    report["other_archive_payloads_identical"] = True
    report["archive_payload_preservation_basis"] = "current_archive" if current_archive is not None else "original_archive"
    return output, report
