"""Space evolution-stone names in each region's existing native translations.

The original names are tightly packed. A few identical native descriptions are
made to share their existing text, releasing storage for the longer stone names.
No table, section or relocation moves; every other ID resolves to identical bytes.
This module only returns bytes. It never writes to a ROM or a filesystem path.
"""
from __future__ import annotations

from bisect import bisect_right
import struct

from .analyze_game import FormatError, check_range, parse_rel, sha256, u32
from .inspect_tables import REL_SHA256, localized_names, rel_symbols, u16
from .rel_regions import region_for_rel

VERSION = "native-stone-name-spacing-v1"
REPLACEMENTS = {
    "UK": {5077: ("THUNDERSTONE", "THUNDER STONE")},
    "FR": {5074: ("PIERRESOLEIL", "PIERRE SOLEIL"),
           5077: ("PIERREFOUDRE", "PIERRE FOUDRE"),
           5079: ("PIERREPLANTE", "PIERRE PLANTE")},
    "IT": {5074: ("PIETRASOLARE", "PIETRA SOLARE"),
           5075: ("PIETRALUNARE", "PIETRA LUNARE"),
           5076: ("PIETRAFOCAIA", "PIETRA FOCAIA"),
           5077: ("PIETRATUONO", "PIETRA TUONO"),
           5078: ("PIETRAIDRICA", "PIETRA IDRICA"),
           5079: ("PIETRAFOGLIA", "PIETRA FOGLIA")},
    "SP": {5077: ("PIEDRATRUENO", "PIEDRA TRUENO")},
}
# (duplicate ID, retained canonical ID), selected against the original hash.
# German compounds are already natural; no German name or pointer changes.
DONORS = {"UK": ((3375, 3304),),
          "FR": ((3375, 3304), (3377, 3313), (3374, 3337)),
          "IT": tuple((identifier, 5257) for identifier in range(5258, 5265)),
          "SP": ((3375, 3304),)}
REPLACEMENTS["US"] = REPLACEMENTS["UK"].copy()
DONORS["US"] = DONORS["UK"]


def _directory(data: bytes, base: int, end: int, language: str) -> dict[int, dict]:
    check_range(data, base, end - base, "localized name bank")
    if base % 2 or end % 2 or end <= base + 16:
        raise FormatError("invalid localized name bank bounds")
    if data[base:base + 4] != b"\0\0\0\1" or data[base + 6:base + 8] != language.encode("ascii"):
        raise FormatError("unexpected localized name bank header")
    count = u16(data, base + 4)
    directory_end = base + 16 + count * 8
    if not count or directory_end > end:
        raise FormatError("localized name directory exceeds bank")
    entries = {}
    for index in range(count):
        pos = base + 16 + index * 8
        raw_id, relative = u32(data, pos), u32(data, pos + 4)
        identifier, start = raw_id & 0xFFFFF, base + relative
        # Native control opcodes include byte parameters, so unrelated rich
        # records may start on odd addresses. Their complete spans stay opaque.
        if identifier in entries or not directory_end <= start <= end - 2:
            raise FormatError("duplicate ID or invalid localized name pointer")
        entries[identifier] = {"id": identifier, "pointer_offset": pos + 4, "start": start}
    starts = sorted({row["start"] for row in entries.values()})
    for row in entries.values():
        next_index = bisect_right(starts, row["start"])
        row["end"] = starts[next_index] if next_index < len(starts) else end
    return entries


def _plain(data: bytes, row: dict) -> bytes:
    """A complete owned allocation, only for the selected plain-text records."""
    raw = data[row["start"]:row["end"]]
    if len(raw) < 2 or len(raw) % 2 or raw[-2:] != b"\0\0":
        raise FormatError("name allocation has no final UTF-16 terminator")
    # Donor allocations must have exactly one string, with no padding or controls.
    units = struct.unpack(f">{len(raw) // 2}H", raw)
    if any(value in (0, 0xFFFF) for value in units[:-1]):
        raise FormatError("selected name has padding, embedded terminators or controls")
    try:
        raw[:-2].decode("utf-16-be")
    except UnicodeError as error:
        raise FormatError("invalid selected UTF-16 name") from error
    return raw


def _merged(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    result = []
    for start, end in sorted(ranges):
        if result and start < result[-1][1]:
            raise FormatError("name storage ranges overlap")
        if result and start == result[-1][1]:
            result[-1] = (result[-1][0], end)
        else:
            result.append((start, end))
    return result


def _patch_bank(original: bytes, current: bytes, base: int, end: int, language: str,
                replacements: dict, donors: tuple, *, reclaim_replaced: bool = False) -> tuple[bytes, dict]:
    """Bounded table core; production callers must fingerprint the original REL."""
    if len(current) != len(original) or current[base:end] != original[base:end]:
        raise FormatError("localized name bank differs from the original")
    entries = _directory(original, base, end, language)
    donor_ids = {identifier for identifier, _ in donors}
    if len(donor_ids) != len(donors) or donor_ids & replacements.keys():
        raise FormatError("duplicate or conflicting name donors")
    if not (donor_ids | replacements.keys() | {target for _, target in donors}) <= entries.keys():
        raise FormatError("missing localized replacement or donor ID")
    if donor_ids & {target for _, target in donors}:
        raise FormatError("a canonical name cannot also donate storage")
    donors_report, regions = [], []
    for identifier, canonical in donors:
        row, target = entries[identifier], entries[canonical]
        payload = _plain(original, row)
        if payload != _plain(original, target):
            raise FormatError("native donor texts are not byte-identical")
        if any(other["id"] != identifier and row["start"] <= other["start"] < row["end"]
               for other in entries.values()):
            raise FormatError("another ID aliases donated name storage")
        regions.append((row["start"], row["end"]))
        donors_report.append({"id": identifier, "canonical_id": canonical,
                              "text": payload[:-2].decode("utf-16-be"),
                              "before_offset": row["start"], "after_offset": target["start"],
                              "pointer_offset": row["pointer_offset"],
                              "released_range": [row["start"], row["end"]]})
    if reclaim_replaced:
        if replacements.keys() & {target for _, target in donors}:
            raise FormatError("a canonical name cannot also be replaced")
        for identifier in replacements:
            row = entries[identifier]
            if any(other["id"] != identifier and other["start"] == row["start"] for other in entries.values()):
                raise FormatError("another ID aliases replaced name storage")
            regions.append((row["start"], row["end"]))
    regions = _merged(regions)
    free = [list(region) for region in regions]
    output, changes = bytearray(current), []
    for identifier, (before, after) in sorted(replacements.items()):
        row = entries[identifier]
        if _plain(original, row) != before.encode("utf-16-be") + b"\0\0":
            raise FormatError("unexpected original native stone name")
        payload = after.encode("utf-16-be") + b"\0\0"
        if not after or "\0" in after or "\uffff" in after:
            raise FormatError("replacement must be nonempty plain text")
        slot = next((region for region in free if region[1] - region[0] >= len(payload)), None)
        if slot is None:
            raise FormatError("insufficient duplicate-text storage for spaced names")
        start = slot[0]
        slot[0] += len(payload)
        output[start:start + len(payload)] = payload
        struct.pack_into(">I", output, row["pointer_offset"], start - base)
        changes.append({"id": identifier, "before": before, "after": after,
                        "before_offset": row["start"], "after_offset": start,
                        "pointer_offset": row["pointer_offset"],
                        "payload_range": [start, start + len(payload)]})
    for row in donors_report:
        struct.pack_into(">I", output, row["pointer_offset"], row["after_offset"] - base)
    # Compare every original ID's complete owned byte allocation. Rich control
    # strings stay opaque, so embedded zero parameters cannot hide a mutation.
    expected_donors = {row["id"]: row for row in donors_report}
    expected_changes = {row["id"]: row for row in changes}
    for identifier, row in entries.items():
        start = base + u32(output, row["pointer_offset"])
        if identifier in expected_changes:
            expected = expected_changes[identifier]["after"].encode("utf-16-be") + b"\0\0"
        else:
            expected = original[row["start"]:row["end"]]
            if identifier in expected_donors:
                if start != expected_donors[identifier]["after_offset"]:
                    raise FormatError("native duplicate did not retain its canonical text")
            elif start != row["start"]:
                raise FormatError("an unrelated native text pointer changed")
        if bytes(output[start:start + len(expected)]) != expected:
            raise FormatError("a localized ID no longer resolves to its expected bytes")
    allowed = [(row["pointer_offset"], row["pointer_offset"] + 4) for row in changes + donors_report]
    allowed += [tuple(row["payload_range"]) for row in changes]
    allowed.sort()
    if any(a != b and not any(start <= index < finish for start, finish in allowed)
           for index, (a, b) in enumerate(zip(current[base:end], output[base:end]), base)):
        raise FormatError("name edit exceeded the directory/payload whitelist")
    return bytes(output), {"language": language, "bank_range": [base, end],
                           "entry_count": len(entries), "edits": changes, "donors": donors_report,
                           "released_ranges": [list(region) for region in regions],
                           "allowed_ranges": [list(region) for region in allowed],
                           "all_other_ids_resolve_to_identical_bytes": True}


def _relocation_ranges(data: bytes, parsed: dict) -> tuple[list, list]:
    """Conservative four-byte write ranges and self-import target byte ranges."""
    writes, targets = [], []
    sections = parsed["sections"]
    for imported in parsed["imports"]:
        source_section, source_relative = None, 0
        for pos in range(imported["relocations_offset"], len(data) - 7, 8):
            delta, command, section, addend = struct.unpack_from(">HBBI", data, pos)
            if command == 203:
                break
            if command == 202:
                if section >= len(sections) or not sections[section]["offset"]:
                    raise FormatError("relocation source section has no file bytes")
                source_section, source_relative = section, 0
                continue
            source_relative += delta
            if command == 201:
                continue
            if not 1 <= command <= 13 or source_section is None:
                raise FormatError("unverified REL relocation command")
            source = sections[source_section]
            if source_relative + 4 > source["size"]:
                raise FormatError("relocation source exceeds its section")
            start = source["offset"] + source_relative
            writes.append((start, start + 4))
            if imported["module_id"] == parsed["module_id"]:
                if section >= len(sections) or not sections[section]["offset"] or addend >= sections[section]["size"]:
                    raise FormatError("self-relocation target is outside file bytes")
                start = sections[section]["offset"] + addend
                targets.append((start, start + 1))
        else:
            raise FormatError("unterminated REL relocation stream")
    return writes, targets


def apply_item_name_spacing(original_rel: bytes, current_rel: bytes) -> tuple[bytes, dict]:
    region = region_for_rel(original_rel)
    return patch_item_name_banks(original_rel, current_rel, region.name_bank_indices, region.native_languages,
                                 REPLACEMENTS, DONORS)


def patch_item_name_banks(original_rel: bytes, current_rel: bytes, bank_indices: tuple[int, ...],
                          native_languages: tuple[str, ...], replacements: dict, donors: dict,
                          *, reclaim_replaced: bool = False) -> tuple[bytes, dict]:
    if len(original_rel) != len(current_rel):
        raise FormatError("item name spacing requires the fingerprinted original regional REL")
    parsed = parse_rel(original_rel)
    symbols = rel_symbols(original_rel, parsed)
    original_names, tables = localized_names(original_rel, symbols)
    banks = [table for table in tables if table["symbol_index"] in bank_indices]
    if tuple(table["language_tag"] for table in banks) != native_languages:
        raise FormatError("unverified original native name bank layout")
    output, reports = current_rel, []
    for bank in banks:
        language, base, end = bank["language_tag"], bank["offset"], bank["end"]
        if current_rel[base:end] != original_rel[base:end]:
            raise FormatError("native name bank has already been changed")
        if language in replacements:
            output, report = _patch_bank(original_rel, output, base, end, language,
                                          replacements[language], donors[language], reclaim_replaced=reclaim_replaced)
            reports.append(report)
    allowed = [tuple(region) for report in reports for region in report["allowed_ranges"]]
    writes, targets = _relocation_ranges(original_rel, parsed)
    if any(start < reference_end and reference_start < end
           for start, end in allowed for reference_start, reference_end in writes + targets):
        raise FormatError("a name edit intersects a REL relocation source or target")
    if any(a != b and not any(start <= index < end for start, end in allowed)
           for index, (a, b) in enumerate(zip(current_rel, output))):
        raise FormatError("item name spacing exceeded its byte whitelist")
    names, output_tables = localized_names(output, symbols)
    for language, entries in original_names.items():
        for identifier, text in entries.items():
            expected = (replacements.get(language, {}).get(identifier, (text, text))[1]
                        if language in native_languages else text)
            if names[language].get(identifier) != expected:
                raise FormatError("localized native name validation failed")
    if [{k: v for k, v in bank.items() if k != "plain_short_strings_decoded"} for bank in output_tables] != [
            {k: v for k, v in bank.items() if k != "plain_short_strings_decoded"} for bank in tables]:
        raise FormatError("localized name bank positions changed")
    return output, {"version": VERSION, "enabled": True,
                    "changed_names": sum(len(report["edits"]) for report in reports),
                    "native_languages": list(native_languages),
                    "unchanged_compound_language": "GE" if "GE" in native_languages else None, "banks": reports,
                    "allowed_ranges": [list(region) for region in sorted(allowed)],
                    "all_other_ids_resolve_to_identical_bytes": True,
                    "relocation_sources_and_targets_untouched": True,
                    "all_sections_tables_and_relocations_keep_their_offsets": True,
                    "changed_bytes": sum(a != b for a, b in zip(current_rel, output))}
