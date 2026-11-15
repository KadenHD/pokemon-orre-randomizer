"""Pure, guarded archive transforms for the legacy Eagun story obstruction.

No files, discs or saves are opened by this module. The caller must supply an
exact regional original and a separate archive from the affected randomized
disc. Only the two known legacy CMS redirects are admitted.
"""
from __future__ import annotations

import struct

from . import event_gifts as events
from .analyze_game import parse_fsys, sha256, u32
from .inspect_tables import u16
from .rebuild_iso import align, decoded_member, repack_fsys


LEGACY_STORY_FLAGS = (3527, 2582, 1067, 2860, 3531, 2875)


def _legacy_predicate():
    return events._call(81, LEGACY_STORY_FLAGS[0]) + b"".join(
        events._call(81, flag) + b"\x21\x82\x82" for flag in LEGACY_STORY_FLAGS[1:])


def _legacy_home(original):
    """Reconstruct the admitted v1 append only; never use it for new ROMs."""
    epilogue = original[0x678:0x68C]
    code = events._Assembler(len(original))
    code.emit(_legacy_predicate())
    code.jump("epilogue", when_false=True)
    code.emit(original[0x649:0x678])
    code.mark("epilogue")
    code.emit(epilogue)
    result = bytearray(original + code.finish())
    result[0x678:0x67D] = b"\x06" + struct.pack(">I", len(original))
    talk = events._Assembler(len(result))
    talk.emit(_legacy_predicate())
    talk.jump("original", when_false=True)
    talk.emit(b"\x05")
    talk.mark("original")
    talk.emit(b"\x06" + struct.pack(">I", 0x3561))
    result.extend(talk.finish())
    struct.pack_into(">I", result, 0x38, talk.base)
    return bytes(result)


def restore_native_home(original: bytes, current: bytes, expected: str = events.HOME_CMS_SHA256):
    events._patch_home_cms(original, expected)  # Native fingerprint and entry checks.
    template = _legacy_home(original)
    events._require(len(current) == len(template) and
                    current[0x38:0x3C] == template[0x38:0x3C] and
                    current[0x678:0x68C] == template[0x678:0x68C] and
                    current[0x312A:0x351F] == original[0x312A:0x351F] and
                    current[len(original):] == template[len(original):],
                    "unknown legacy home story redirects")
    result = bytearray(current)
    for start, end in ((0x38, 0x3C), (0x678, 0x68C)):
        result[start:end] = original[start:end]
    events._only_changes(current, result, ((0x38, 0x3C), (0x678, 0x68C)))
    return bytes(result), {"native_talk_entry": 0x3561,
                           "native_home_actor_restored": True,
                           "saved_progression_modified": False}


def gate_legacy_shrine(original: bytes, current: bytes):
    events._fingerprint(original, events.SHRINE_CMS_SHA256, "shrine CMS")
    events._require(u16(current, 4) == 13 and u32(current, 0x48) == len(original)
                    and current[0x24A] == 6, "unknown legacy shrine entry")
    old_entry = len(original)
    visibility = u32(current, 0x24B)
    events._require(old_entry < visibility < len(current), "invalid legacy shrine visibility entry")
    interaction = current[old_entry:visibility]
    counter = events._purified_count()
    thresholds = []
    position = 0
    while (position := interaction.find(counter, position)) >= 0:
        after = position + len(counter)
        events._require(interaction[after:after + 2] == b"\x08\x02", "invalid legacy gift threshold")
        thresholds.append(u32(interaction, after + 2))
        position = after + 6
    events._require(len(thresholds) == 2 and all(0 <= value <= 48 for value in thresholds),
                    "unknown legacy gift thresholds")
    events._require(interaction == events._interaction(old_entry, *thresholds,
                                                       story_predicate=_legacy_predicate()),
                    "unknown legacy gift handler")
    old_visibility = (original[0x24A:0x26A] + _legacy_predicate() + original[0x270:0x279]
                      + b"\x06" + struct.pack(">I", 0x279))
    globals_offset = align(visibility + len(old_visibility), 4)
    globals_ = original[0x48:0x50]
    events._require(current[visibility:visibility + len(old_visibility)] == old_visibility
                    and u32(current, 12) == globals_offset and u32(current, 16) == globals_offset
                    and current[globals_offset:] == globals_, "unknown legacy shrine globals or visibility")
    result = bytearray(current[:globals_offset])
    entry = len(result)
    wrapper = events._Assembler(entry)
    wrapper.emit(events._story_complete())
    wrapper.jump("return", when_false=True)
    wrapper.emit(b"\x06" + struct.pack(">I", old_entry))
    wrapper.mark("return")
    wrapper.emit(b"\x05")
    result.extend(wrapper.finish())
    new_visibility = len(result)
    result.extend(original[0x24A:0x26A] + events._story_complete() + original[0x270:0x279]
                  + b"\x06" + struct.pack(">I", 0x279))
    result.extend(bytes(-len(result) % 4))
    new_globals = len(result)
    result.extend(globals_)
    struct.pack_into(">II", result, 12, new_globals, new_globals)
    struct.pack_into(">I", result, 0x48, entry)
    result[0x24A:0x24F] = b"\x06" + struct.pack(">I", new_visibility)
    events._only_changes(current[:globals_offset], result,
                         ((12, 20), (0x48, 0x4C), (0x24A, 0x24F)))
    return bytes(result), {"guard_entry": entry, "original_gift_entry": old_entry,
                           "thresholds": thresholds, "visibility_entry": new_visibility,
                           "phone_exchange_flag": events.PHONE_EXCHANGE_FLAG,
                           "pending_native_master_ball_respected": True,
                           "saved_progression_modified": False}


def repair_legacy_event_archive(original: bytes, current: bytes, name: str, *, region: str):
    profile = events._REGIONAL_LAYOUTS.get(region)
    events._require(profile is not None and name in events.ARCHIVE_NAMES,
                    "unsupported legacy event archive or region")
    events._fingerprint(original, profile["archives"][name], name)
    before, now = parse_fsys(original)["members"], parse_fsys(current)["members"]
    events._require(len(before) == len(now) and all(
        all(a[key] == b[key] for key in ("index", "name", "identifier_raw"))
        for a, b in zip(before, now)), "legacy archive member identities differ")
    source_cms, current_cms = decoded_member(original, before[1]), decoded_member(current, now[1])
    if name == events.ARCHIVE_NAMES[0]:
        output_cms, detail = gate_legacy_shrine(source_cms, current_cms)
    else:
        output_cms, detail = restore_native_home(source_cms, current_cms, profile["home_cms"])
    output = repack_fsys(current, {1: output_cms})[0]
    after = parse_fsys(output)["members"]
    events._require(all(decoded_member(output, b) == (output_cms if i == 1 else decoded_member(current, a))
                        for i, (a, b) in enumerate(zip(now, after))),
                    "story recovery changed another archive member")
    return output, {"archive": name, "region": region, "before_sha256": sha256(current),
                    "after_sha256": sha256(output), "only_cms_changed": True, "details": detail}
