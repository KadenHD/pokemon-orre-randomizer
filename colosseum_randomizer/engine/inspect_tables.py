"""Export validated regional common.rel tables without changing game data.

Field meanings are derived from the community tool referenced in SOURCE.
Indices and byte ranges are checked against this exact local build; this is
static interpretation, not proof that every record is reachable in the game.
"""

from __future__ import annotations

import argparse
import struct
from collections import Counter
from pathlib import Path

from .analyze_game import (FormatError, check_range, decompress_lzss, parse_fsys,
                          parse_rel, sha256, u32, write_json)
from .rel_regions import COMMON_SCHEMAS, region_for_rel

SOURCE = "https://github.com/PekanMmd/Pokemon-XD-Code/tree/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0"
REL_SHA256 = "ee2677af555dc59626f978e743235831a76cb23bae93f3fdd1060d808f749d0b"
SCHEMAS = COMMON_SCHEMAS


def u16(data: bytes, pos: int) -> int:
    check_range(data, pos, 2, "u16")
    return struct.unpack_from(">H", data, pos)[0]


def rel_symbols(data: bytes, rel: dict) -> list[dict]:
    """Community index convention: unique self-relocation targets, in order.

    This is not a native REL symbol table and names are not present in the file.
    Keep the relocation site that justifies each derived target file offset.
    """
    sections, symbols, seen = rel["sections"], [], set()
    own_imports = [i for i in rel["imports"] if i["module_id"] == rel["module_id"]]
    if len(own_imports) != 1:
        raise FormatError("expected exactly one self-import stream")
    start = own_imports[0]["relocations_offset"]
    for pos in range(start, len(data) - 7, 8):
        _, command, section, addend = struct.unpack_from(">HBBI", data, pos)
        if command == 203:  # R_DOLPHIN_END
            return symbols
        if 1 <= command <= 13:
            if section >= len(sections):
                raise FormatError("REL target section outside section table")
            selected = sections[section]
            if not selected["offset"] or addend >= selected["size"]:
                raise FormatError("REL target not backed by bytes")
            target = selected["offset"] + addend
            if target not in seen:
                seen.add(target)
                symbols.append({"index": len(symbols), "offset": target,
                                "relocation_offset": pos, "section": section,
                                "section_offset": addend, "command": command})
    raise FormatError("unterminated REL self-import stream")


def plain_name(data: bytes, pos: int, end: int) -> str | None:
    """Only decode short plain names. Rich text/control codes stay unknown."""
    if pos < 0 or pos + 2 > end:
        raise FormatError("string pointer outside selected table")
    raw = bytearray()
    for offset in range(pos, min(end - 1, pos + 512), 2):
        unit = u16(data, offset)
        if unit == 0:
            return raw.decode("utf-16-be")
        if unit == 0xFFFF:
            return None
        raw.extend(data[offset:offset + 2])
    # Long dialogue and encoded control text are intentionally not reconstructed.
    return None


def localized_names(data: bytes, symbols: list[dict]) -> tuple[dict, list[dict]]:
    names = {lang: {} for lang in ("UK", "GE", "FR", "IT", "SP", "US", "JP")}
    tables = []
    targets = sorted({s["offset"] for s in symbols} | {len(data)})
    for symbol in symbols:
        base = symbol["offset"]
        if base + 16 > len(data):
            continue
        header, tag = data[base:base + 4], data[base + 6:base + 8]
        if header == b"\0\0\0\1":
            lang = tag.decode("ascii", errors="replace")
        elif header == b"\0\0\0\0" and tag == b"\0\1" and data[base + 8:base + 16] == bytes(8):
            # The Japanese name bank uses the native numeric language marker.
            # Its directory and plain names retain the same UTF-16BE encoding.
            lang = "JP"
        else:
            continue
        if lang not in names:
            continue
        count = u16(data, base + 4)
        end = next(t for t in targets if t > base)
        check_range(data, base + 16, count * 8, "localized string directory")
        if base + 16 + count * 8 > end:
            raise FormatError("localized string directory exceeds table boundary")
        plain_count = 0
        for i in range(count):
            pos = base + 16 + i * 8
            raw_id, offset = u32(data, pos), u32(data, pos + 4)
            identifier = raw_id & 0xFFFFF
            if offset < 16 + count * 8:
                raise FormatError("localized string overlaps directory")
            text = plain_name(data, base + offset, end)
            if text is not None:
                if identifier in names[lang] and names[lang][identifier] != text:
                    raise FormatError(f"conflicting localized ID {identifier} in {lang}")
                names[lang][identifier] = text
                plain_count += 1
        tables.append({"symbol_index": symbol["index"], "offset": base, "end": end,
                       "language_tag": lang, "entry_count": count,
                       "plain_short_strings_decoded": plain_count})
    return names, tables


def inspect(game: Path, output: Path) -> dict:
    game, output = game.resolve(), output.resolve()
    if output == game or game in output.parents or output in game.parents:
        raise ValueError("output and game trees must be disjoint")
    boot = (game / "sys/boot.bin").read_bytes()
    fsys = (game / "files/common.fsys").read_bytes()
    archive = parse_fsys(fsys)
    matches = [m for m in archive["members"] if m["name"] == "common_rel"]
    if len(matches) != 1:
        raise FormatError("expected one common_rel member")
    member = matches[0]
    payload = fsys[member["offset"]:member["offset"] + member["stored_size"]]
    data = decompress_lzss(payload) if member["compression"] == "LZSS" else payload
    region = region_for_rel(data)
    if boot[:6] != region.game_id.encode("ascii") or boot[6:8] != b"\0\0":
        raise FormatError("boot header and validated regional REL identity differ")
    rel = parse_rel(data)
    symbols = rel_symbols(data, rel)
    names, string_tables = localized_names(data, symbols)
    meta, exports = {}, {}

    def named(row: dict, identifier: int) -> dict:
        return {**row, "name_id": identifier, "name_fr": names["FR"].get(identifier),
                "name_en": names["UK"].get(identifier) or names["US"].get(identifier),
                "name_ja": names["JP"].get(identifier)}

    for table, (pointer_index, count_index, stride) in SCHEMAS.items():
        symbol = symbols[pointer_index]
        offset, count = symbol["offset"], u32(data, symbols[count_index]["offset"])
        section = rel["sections"][symbol["section"]]
        check_range(data, offset, count * stride, table)
        if offset + count * stride > section["offset"] + section["size"]:
            raise FormatError(f"{table} exceeds REL section")
        meta[table] = {"offset": offset, "count": count, "stride": stride,
                       "pointer_index": pointer_index, "count_index": count_index,
                       "count_offset": symbols[count_index]["offset"]}
        rows = []
        for i in range(count):
            p = offset + i * stride
            row = {"index": i, "offset": p}
            if table == "species":
                row = named({**row, "national_dex": u16(data, p + 0x10),
                             "types": list(data[p + 0x30:p + 0x32]),
                             "abilities": list(data[p + 0x32:p + 0x34]),
                             "base_stats": dict(zip(("hp", "attack", "defense", "sp_attack", "sp_defense", "speed"),
                                                    data[p + 0x85:p + 0x91:2])),
                             "held_item_indices": [u16(data, p + o) for o in (0x70, 0x72)],
                             "evolutions": [{"method": data[p + 0x9C + e * 6],
                                             "condition": u16(data, p + 0x9E + e * 6),
                                             "species_index": u16(data, p + 0xA0 + e * 6)} for e in range(5)],
                             "level_up_moves": [{"level": data[p + 0xBA + m * 4],
                                                 "move_index": u16(data, p + 0xBC + m * 4)} for m in range(19)]},
                            u32(data, p + 0x18))
            elif table == "moves":
                row = named({**row, "pp": data[p + 1], "type": data[p + 2],
                             "accuracy": data[p + 4], "power": data[p + 0x17],
                             "effect": u16(data, p + 0x1A)}, u32(data, p + 0x20))
            elif table == "trainers":
                row = named({**row, "class_id": data[p + 3],
                             "first_pokemon_index": u16(data, p + 4)}, u32(data, p + 8))
            elif table == "trainer_pokemon":
                row = named({**row, "shadow_id": data[p + 3], "level": data[p + 4],
                             "species_index": u16(data, p + 0xA),
                             "held_item_index": u16(data, p + 0x12),
                             "move_indices": [u16(data, p + v) for v in (0x36, 0x3E, 0x46, 0x4E)]},
                            u32(data, p + 0x14))
            else:
                row = {**row, "catch_rate": data[p], "species_index": u16(data, p + 2),
                       "first_trainer_index": u16(data, p + 4), "alternate_trainer_index": u16(data, p + 6),
                       "counter": u16(data, p + 8), "shadow_id": data[p + 0xB]}
            rows.append(row)
        exports[table] = rows

    species_count, move_count, trainer_count, team_count, shadow_count = (
        meta[k]["count"] for k in ("species", "moves", "trainers", "trainer_pokemon", "shadow"))
    issues = []
    for row in exports["trainer_pokemon"]:
        for field, valid in (("species_index", row["species_index"] < species_count),
                             ("shadow_id", row["shadow_id"] < shadow_count),
                             ("level", row["level"] <= 100),
                             ("move_indices", all(m == 0xFFFF or m < move_count for m in row["move_indices"]))):
            if not valid:
                issues.append({"table": "trainer_pokemon", "index": row["index"], "field": field})
        if (0 < row["shadow_id"] < shadow_count and row["species_index"] !=
                exports["shadow"][row["shadow_id"]]["species_index"]):
            issues.append({"table": "trainer_pokemon", "index": row["index"], "field": "shadow_species_consistency"})
        row["species_name_fr"] = exports["species"][row["species_index"]]["name_fr"] if row["species_index"] < species_count else None
    for row in exports["trainers"]:
        # Nonzero first index denotes the beginning of six fixed team slots.
        if row["first_pokemon_index"] and row["first_pokemon_index"] + 6 > team_count:
            issues.append({"table": "trainers", "index": row["index"], "field": "team_range"})
    for row in exports["shadow"]:
        if (row["species_index"] >= species_count or row["first_trainer_index"] >= trainer_count
                or row["alternate_trainer_index"] >= trainer_count):
            issues.append({"table": "shadow", "index": row["index"], "field": "reference"})
    for row in exports["species"]:
        if any(e["species_index"] >= species_count for e in row["evolutions"]):
            issues.append({"table": "species", "index": row["index"], "field": "evolution_reference"})
        if any(m["move_index"] >= move_count for m in row["level_up_moves"]):
            issues.append({"table": "species", "index": row["index"], "field": "level_up_move_reference"})
    national = Counter(r["national_dex"] for r in exports["species"] if 1 <= r["national_dex"] <= 386)
    stats = {"species_slots": species_count, "unique_national_dex_1_to_386": len(national),
             "national_dex_duplicates": {str(k): v for k, v in national.items() if v > 1},
             "species_without_national_dex": sum(r["national_dex"] == 0 for r in exports["species"]),
             "trainer_pokemon_nonzero_species": sum(r["species_index"] != 0 for r in exports["trainer_pokemon"]),
             "shadow_records_nonzero_species": sum(r["species_index"] != 0 for r in exports["shadow"]),
             "trainer_pokemon_with_shadow_id": sum(r["shadow_id"] != 0 for r in exports["trainer_pokemon"]),
             "trainer_pokemon_with_ffff_move_marker": sum(0xFFFF in r["move_indices"] for r in exports["trainer_pokemon"])}
    result = {"evidence_id": "LOCAL-TABLES-001", "source_schema": SOURCE,
              "common_rel_sha256": sha256(data), "game_id": region.game_id, "symbol_count": len(symbols),
              "tables": meta, "statistics": stats, "string_tables": string_tables,
              "reference_checks": {"issues": issues},
              "limitations": ["Community schema interpretation corroborated by byte-level bounds and reference checks.",
                              "Counts include zero, placeholder, duplicate and potentially unreachable records.",
                              "Only short names without text controls are decoded; absent names remain null.",
                              "0xffff move fields are retained as special raw markers; their runtime meaning is unknown.",
                              "No runtime observation, randomization, patching or repacking performed."]}
    for table, rows in exports.items():
        write_json(output / "tables" / f"{table}.json", rows)
    write_json(output / "rel-symbols.json", symbols)
    write_json(output / "tables-summary.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", type=Path, default=Path("game"))
    parser.add_argument("--output", type=Path, default=Path("analysis/generated"))
    args = parser.parse_args()
    result = inspect(args.game, args.output)
    import json
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["reference_checks"]["issues"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
