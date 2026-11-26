"""Optional Colosseum rescue battle using an unused native Shadow save slot.

A separate Cipher commander and an unused Shadow slot preserve all 48 native
encounters. The dedicated model patch supplies XD's Shadow Lugia appearance.
"""
from __future__ import annotations

import struct

from .analyze_game import FormatError, parse_rel, u32

VERSION = "colosseum-postgame-nascour-lugia-v4"
LUGIA = 249
SHADOW_ID = 96
TRAINER_ID = 820
PARTY_SLOT = 5510
BATTLE_ID = 566
CAPTURE_FLAG = 2221
PURIFICATION_FLAG = 1357
LEVEL = 70
MESSAGE_IDS = tuple(range(0xF0010, 0xF001D))


def _require(condition, message):
    if not condition:
        raise FormatError(message)


def _extend_tables(original, current, symbols, additions, *, section_index=4, payload_overrides=None):
    """Clone numeric tables into the enlarged last data section.

    Original allocations remain intact. All self-relocation targets into each
    cloned table follow its new allocation; relocation sites within the tables
    are rejected because these records must not contain native pointers.
    """
    rel = parse_rel(original)
    data_section_index = section_index
    section = rel["sections"][data_section_index]
    payload_overrides = payload_overrides or {}
    insertion = section["offset"] + section["size"]
    _require(len(current) == len(original) and insertion == u32(original, 0x28),
             "unsupported common REL tail for the Lugia encounter")
    output = bytearray(current)
    extra = bytearray()
    ranges = []
    report = {}
    for name, pointer, counter, stride, count, appended in additions:
        base = symbols[pointer]["offset"]
        _require((counter is None or u32(original, symbols[counter]["offset"]) == count)
                 and len(appended) % stride == 0,
                 "unexpected table allocation for the Lugia encounter")
        extra.extend(bytes(-(insertion + len(extra)) % 4))
        new_base = insertion + len(extra)
        original_payload = current[base:base + count * stride]
        _require(len(original_payload) == count * stride, "truncated Lugia source table")
        payload = payload_overrides.get(name, original_payload)
        _require((counter is None or len(payload) == len(original_payload)) and len(payload) % stride == 0,
                 "invalid Lugia table replacement")
        extra.extend(payload + appended)
        ranges.append((base, base + count * stride, new_base, name in payload_overrides))
        new_count = (len(payload) + len(appended)) // stride
        if counter is not None:
            struct.pack_into(">I", output, symbols[counter]["offset"], new_count)
        report[name] = {"before_offset": base, "offset": new_base, "before_count": count,
                        "count": new_count, "stride": stride}
    extra.extend(bytes(-len(extra) % 4))
    growth = len(extra)
    output[insertion:insertion] = extra
    section_table = u32(original, 0x10)
    struct.pack_into(">I", output, section_table + data_section_index * 8 + 4, section["size"] + growth)
    for field in (0x24, 0x28, 0x48):
        old = u32(original, field)
        _require(old >= insertion, "unexpected REL tail header offset")
        struct.pack_into(">I", output, field, old + growth)
    imports = u32(original, 0x28)
    for index, imported in enumerate(rel["imports"]):
        _require(imported["relocations_offset"] >= insertion, "unexpected early REL import stream")
        struct.pack_into(">I", output, imports + growth + index * 8 + 4,
                         imported["relocations_offset"] + growth)
    retargeted = []
    for imported in rel["imports"]:
        section_index, site = None, 0
        for position in range(imported["relocations_offset"], len(original) - 7, 8):
            delta, command, target_section, addend = struct.unpack_from(">HBBI", original, position)
            if command == 203:
                break
            if command == 202:
                section_index, site = target_section, 0
                continue
            site += delta
            if not 1 <= command <= 13:
                continue
            _require(section_index is not None, "REL relocation before a section selector")
            site_offset = rel["sections"][section_index]["offset"] + site
            _require(not any(start <= site_offset < end for start, end, _, _ in ranges),
                     "Lugia table contains native pointer relocation sites")
            if imported["module_id"] != rel["module_id"] or target_section != data_section_index:
                continue
            target = section["offset"] + addend
            for start, end, new_base, base_only in ranges:
                if start <= target < end:
                    _require(not base_only or target == start, "unexpected interior message-bank relocation")
                    replacement = new_base + target - start - section["offset"]
                    struct.pack_into(">I", output, position + growth + 4, replacement)
                    retargeted.append({"relocation_offset": position + growth,
                                       "before_target": target, "target": new_base + target - start})
                    break
    _require(len(retargeted) >= len(additions), "missing Lugia table relocations")
    parsed = parse_rel(bytes(output))
    _require(parsed["sections"][data_section_index]["size"] == section["size"] + growth,
             "Lugia REL section growth was not preserved")
    return bytes(output), {"tables": report, "growth": growth, "retargeted": retargeted,
                           "original_allocations_preserved": True}



def plan_postgame_lugia_team(original, current, seed, options):
    """Plan bonus identities before installing hooks or extending native tables."""
    if not getattr(options, "postgame_shadow_lugia", False):
        return []
    from .postgame_boss import plan_team
    return plan_team(original, current, seed, options)


def apply_postgame_lugia(original, current, options, *, seed="postgame-lugia"):
    """Append the six-member Cipher team, battle and localized trainer names."""
    if not getattr(options, "postgame_shadow_lugia", False):
        return current, {"version": VERSION, "enabled": False}
    from .postgame_boss import apply_common
    return apply_common(original, current, options, seed=seed)


def patch_postgame_lugia_archives(original_rel, read_archive, updates, options, *, shiny=None,
                                 species=LUGIA, original_dol=None, seed="postgame-lugia", deoxys_form=0):
    """Add a distinct commander and localized event without replacing Eagun."""
    if not getattr(options, "postgame_shadow_lugia", False):
        return {"version": VERSION, "enabled": False}
    from .postgame_boss import patch_archives
    return patch_archives(original_rel, read_archive, updates, options, shiny=shiny,
                          species=species, original_dol=original_dol, seed=seed, deoxys_form=deoxys_form)
