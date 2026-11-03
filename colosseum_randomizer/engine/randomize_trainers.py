"""Seeded species-only trainer randomizer for exact validated regional dumps.

Only referenced, populated trainer slots are randomized. Shared shadow IDs get
one species, also written to their shadow metadata. Preserve moves/levels/items;
normalize an unavailable second ability to the first. Inputs are read-only.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import struct

from .analyze_game import FormatError, check_range, parse_fsys, parse_rel, sha256, u32, write_json
from .inspect_tables import REL_SHA256, SCHEMAS, localized_names, rel_symbols, u16
from .rel_regions import COMMON_COUNTS, region_for_rel
from .rebuild_iso import decoded_member, rebuild, repack_fsys
from .survey_assets import fst_inventory

VERSION = "trainer-species-sha256-v1"
ISO_NAME = "colosseum-pal-randomized.iso"


def choose_species(seed: str, key: str, pool: list[int], old: int) -> int:
    """Versioned SHA-256 rejection sampling; stable across Python versions.

    Exact UTF-8 seed bytes, no normalization; per-record keys avoid dependence
    on iteration order. Exclude the original species so every selected slot changes.
    """
    seed_bytes = seed.encode("utf-8")
    if not 1 <= len(seed_bytes) <= 256:
        raise ValueError("seed must contain 1..256 UTF-8 bytes")
    candidates = sorted(set(pool) - {old})
    if not candidates:
        raise ValueError("no replacement species")
    prefix = VERSION.encode("ascii") + b"\0" + len(seed_bytes).to_bytes(2, "big") + seed_bytes
    prefix += b"\0" + key.encode("ascii") + b"\0"
    limit = (1 << 256) // len(candidates) * len(candidates)
    counter = 0
    while True:
        value = int.from_bytes(hashlib.sha256(prefix + counter.to_bytes(4, "big")).digest(), "big")
        if value < limit:
            return candidates[value % len(candidates)]
        counter += 1


def layout(data: bytes) -> tuple[dict, list[dict]]:
    region_for_rel(data)
    rel = parse_rel(data)
    symbols = rel_symbols(data, rel)
    tables = {}
    for name in ("trainers", "trainer_pokemon", "species", "shadow"):
        pointer, counter, stride = SCHEMAS[name]
        symbol = symbols[pointer]
        offset, count = symbol["offset"], u32(data, symbols[counter]["offset"])
        if count != COMMON_COUNTS[name]:
            raise FormatError(f"unexpected validated regional {name} count")
        check_range(data, offset, count * stride, name)
        section = rel["sections"][symbol["section"]]
        if offset + count * stride > section["offset"] + section["size"]:
            raise FormatError(f"{name} exceeds REL section")
        tables[name] = {"offset": offset, "count": count, "stride": stride}
    return tables, symbols


def randomize_tables(data: bytes, seed: str, tables: dict) -> tuple[bytes, dict]:
    """Core transformation; production callers must first validate via layout()."""
    def base(table, index):
        info = tables[table]
        if not 0 <= index < info["count"]:
            raise FormatError(f"{table} index out of range: {index}")
        pos = info["offset"] + index * info["stride"]
        check_range(data, pos, info["stride"], table)
        return pos

    species = {}
    for i in range(tables["species"]["count"]):
        p = base("species", i)
        national = u16(data, p + 0x10)
        if 1 <= national <= 386:
            name = u32(data, p + 0x18)
            if not name or not data[p + 0x32] or not all(data[p + 0x85:p + 0x91:2]):
                raise FormatError("invalid real species metadata")
            species[i] = {"national_dex": national, "name_id": name,
                          "abilities": list(data[p + 0x32:p + 0x34])}
    if sorted(s["national_dex"] for s in species.values()) != list(range(1, 387)):
        raise FormatError("expected exactly the 386 real species")
    pool = sorted(species)
    # Validate seed even when no populated slot exists.
    choose_species(seed, "validation", pool, pool[0])
    references = defaultdict(list)
    for i in range(tables["trainers"]["count"]):
        start = u16(data, base("trainers", i) + 4)
        if start:
            if start + 6 > tables["trainer_pokemon"]["count"]:
                raise FormatError("trainer team exceeds Pokemon table")
            for index in range(start, start + 6):
                references[index].append(i)
    selected = {i for i in references if u16(data, base("trainer_pokemon", i) + 0xA)}
    shadow_slots = defaultdict(list)
    for i in range(tables["trainer_pokemon"]["count"]):
        p = base("trainer_pokemon", i)
        if u16(data, p + 0xA) and data[p + 3]:
            shadow_slots[data[p + 3]].append(i)
    active_shadows = {data[base("trainer_pokemon", i) + 3] for i in selected} - {0}
    # Never leave an alias of a randomized shadow ID with a different species.
    for sid in active_shadows:
        if not set(shadow_slots[sid]) <= selected:
            raise FormatError("active shadow group includes an unreferenced populated slot")

    output = bytearray(data)
    changes, shadow_changes = [], []
    shadow_picks = {}
    for sid in sorted(active_shadows):
        p = base("shadow", sid)
        old = u16(data, p + 2)
        if old not in species or any(u16(data, base("trainer_pokemon", i) + 0xA) != old
                                     for i in shadow_slots[sid]):
            raise FormatError("original shadow species/group mismatch")
        new = choose_species(seed, f"shadow:{sid}", pool, old)
        shadow_picks[sid] = new
        struct.pack_into(">H", output, p + 2, new)
        shadow_changes.append({"shadow_id": sid, "offset": p + 2,
                               "old_species_index": old, "new_species_index": new,
                               "trainer_pokemon_indices": shadow_slots[sid]})

    for i in sorted(selected):
        p = base("trainer_pokemon", i)
        old, sid = u16(data, p + 0xA), data[p + 3]
        if old not in species or not 1 <= data[p + 4] <= 100:
            raise FormatError("selected Pokemon has invalid species/level")
        old_name = u32(data, p + 0x14)
        if old_name != species[old]["name_id"]:
            raise FormatError("refuse unknown/custom trainer Pokemon nickname")
        ability = data[p]
        if ability not in (0, 1, 0xFF):
            raise FormatError("unknown ability selector")
        new = shadow_picks[sid] if sid else choose_species(seed, f"slot:{i}", pool, old)
        new_ability = 0 if ability == 1 and not species[new]["abilities"][1] else ability
        struct.pack_into(">H", output, p + 0xA, new)
        struct.pack_into(">I", output, p + 0x14, species[new]["name_id"])
        output[p] = new_ability
        changes.append({"index": i, "offset": p, "referencing_trainers": references[i],
                        "shadow_id": sid, "level": data[p + 4],
                        "old_species_index": old, "new_species_index": new,
                        "old_name_id": old_name, "new_name_id": species[new]["name_id"],
                        "old_ability_selector": ability, "new_ability_selector": new_ability})
    plan = {"algorithm": VERSION, "seed": seed, "seed_encoding": "UTF-8, exact bytes",
            "source_rel_sha256": sha256(data), "randomized_rel_sha256": sha256(output),
            "species_pool": pool, "species_pool_size": len(pool),
            "scope": "populated slots referenced by the trainer table, including shared shadows",
            "tables": tables, "trainer_pokemon_changes": changes, "shadow_changes": shadow_changes,
            "summary": {"trainer_pokemon_records_changed": len(changes),
                        "trainers_with_changed_slots": len({t for c in changes for t in c["referencing_trainers"]}),
                        "shared_trainer_slots": sum(len(c["referencing_trainers"]) > 1 for c in changes),
                        "shadow_groups_changed": len(shadow_changes),
                        "shadow_trainer_slots_changed": sum(bool(c["shadow_id"]) for c in changes),
                        "ability_selectors_normalized": sum(c["old_ability_selector"] != c["new_ability_selector"] for c in changes),
                        "populated_unreferenced_slots_preserved": sum(
                            u16(data, base("trainer_pokemon", i) + 0xA) != 0 and i not in selected
                            for i in range(tables["trainer_pokemon"]["count"]))}}
    plan["summary"].update(validate_changes(data, bytes(output), plan))
    return bytes(output), plan


def validate_changes(original: bytes, modified: bytes, plan: dict) -> dict:
    """Whitelist exact field bytes, enforce group consistency and valid abilities."""
    if len(original) != len(modified):
        raise FormatError("REL length changed")
    allowed = set()
    slots = set()
    shadow_species = {c["shadow_id"]: c["new_species_index"] for c in plan["shadow_changes"]}
    species_table = plan["tables"]["species"]
    for c in plan["trainer_pokemon_changes"]:
        p, new = c["offset"], c["new_species_index"]
        if c["index"] in slots or new not in plan["species_pool"] or new == c["old_species_index"]:
            raise FormatError("duplicate slot or invalid/non-changing replacement")
        slots.add(c["index"])
        for source, prefix in ((original, "old"), (modified, "new")):
            if (u16(source, p + 0xA), u32(source, p + 0x14), source[p]) != (
                    c[prefix + "_species_index"], c[prefix + "_name_id"], c[prefix + "_ability_selector"]):
                raise FormatError("trainer fields do not match manifest")
        if c["shadow_id"] and shadow_species.get(c["shadow_id"]) != new:
            raise FormatError("shadow aliases disagree")
        species_pos = species_table["offset"] + new * species_table["stride"]
        if c["new_ability_selector"] == 1 and not modified[species_pos + 0x33]:
            raise FormatError("new second ability is unavailable")
        allowed.update(range(p + 0xA, p + 0xC))
        allowed.update(range(p + 0x14, p + 0x18))
        if c["old_ability_selector"] != c["new_ability_selector"]:
            if (c["old_ability_selector"], c["new_ability_selector"]) != (1, 0) or modified[species_pos + 0x33]:
                raise FormatError("unnecessary/invalid ability normalization")
            allowed.add(p)
    for c in plan["shadow_changes"]:
        p = c["offset"]
        if u16(original, p) != c["old_species_index"] or u16(modified, p) != c["new_species_index"]:
            raise FormatError("shadow metadata does not match manifest")
        allowed.update(range(p, p + 2))
    actual = {i for i, (a, b) in enumerate(zip(original, modified, strict=True)) if a != b}
    if not actual or actual - allowed:
        raise FormatError("unexpected REL bytes changed outside authorized fields")
    return {"changed_rel_bytes": len(actual), "only_authorized_fields_changed": True,
            "shadow_species_consistent": True}


def randomize_rel(data: bytes, seed: str) -> tuple[bytes, dict]:
    tables, symbols = layout(data)
    result, plan = randomize_tables(data, seed, tables)
    names, _ = localized_names(data, symbols)
    trainers = tables["trainers"]
    trainer_names = {i: names["FR"].get(u32(data, trainers["offset"] + i * trainers["stride"] + 8))
                     for i in range(trainers["count"])}
    for c in plan["trainer_pokemon_changes"]:
        c.update(old_species_fr=names["FR"].get(c["old_name_id"]),
                 new_species_fr=names["FR"].get(c["new_name_id"]))
    plan["trainer_names_fr"] = trainer_names
    return result, plan


def original_common(game: Path) -> tuple[bytes, int, bytes]:
    source = (game / "files/common.fsys").read_bytes()
    members = [m for m in parse_fsys(source)["members"] if m["name"] == "common_rel"]
    if len(members) != 1:
        raise FormatError("expected exactly one common_rel member")
    return source, members[0]["index"], decoded_member(source, members[0])


def build_randomized(game: Path, source_iso: Path, output: Path, seed: str) -> dict:
    source, index, original = original_common(game)
    patched, plan = randomize_rel(original, seed)
    # Re-run from the original, never a previous randomized image.
    repeated, repeated_plan = randomize_rel(original, seed)
    if repeated != patched or repeated_plan != plan:
        raise FormatError("same seed did not reproduce the exact transformation")
    result = rebuild(game, source_iso, output, common_replacements={index: patched}, iso_filename=ISO_NAME)
    if result["changed_common_member_indices"] != [index]:
        raise FormatError("unexpected changed archive member set")
    plan["common_member_index"] = index
    plan["same_seed_rel_reproduced"] = True
    write_json(output / "randomizer-manifest.json", plan)
    print(json.dumps(plan["summary"], indent=2))
    return plan


def verify_randomized(game: Path, output: Path, *, expected_dol: bytes | None = None) -> dict:
    from .verify_roundtrip import verify
    integrity = verify(game, output, expected_dol=expected_dol)
    plan = json.loads((output / "randomizer-manifest.json").read_text(encoding="utf-8"))
    report = json.loads((output / "rebuild-report.json").read_text(encoding="utf-8"))
    source, member_index, original = original_common(game)
    if plan["algorithm"] != VERSION or plan["common_member_index"] != member_index:
        raise FormatError("unknown randomizer version/member")
    expected, computed = randomize_rel(original, plan["seed"])
    for key in ("randomized_rel_sha256", "source_rel_sha256", "trainer_pokemon_changes", "shadow_changes", "summary", "species_pool", "tables"):
        if computed[key] != plan[key]:
            raise FormatError(f"manifest does not reproduce from seed: {key}")
    boot = (game / "sys/boot.bin").read_bytes()
    with Path(report["output_iso"]).open("rb") as stream:
        stream.seek(u32(boot, 0x424))
        entries, _ = fst_inventory(stream.read(u32(boot, 0x428)))
        entry = next(e for e in entries if e["path"] == "common.fsys")
        stream.seek(entry["disc_offset"])
        actual_archive = stream.read(entry["size"])
    old_members, new_members = parse_fsys(source)["members"], parse_fsys(actual_archive)["members"]
    for old, new in zip(old_members, new_members, strict=True):
        if (old["name"], old["identifier_raw"], old["compression"]) != (new["name"], new["identifier_raw"], new["compression"]):
            raise FormatError("FSYS member identity changed")
        payload = decoded_member(actual_archive, new)
        if old["index"] == member_index:
            if payload != expected:
                raise FormatError("ISO REL is not the exact seeded result")
            validate_changes(original, payload, plan)
        elif payload != decoded_member(source, old):
            raise FormatError("another common member changed")
    # Full deterministic container reproduction, not only a REL digest comparison.
    expected_archive, _ = repack_fsys(source, {member_index: expected})
    if actual_archive != expected_archive:
        raise FormatError("same seed did not reproduce the archive exactly")
    result = {"integrity": integrity, "algorithm": VERSION, "seed": plan["seed"],
              "summary": computed["summary"], "same_seed_rel_reproduced": True,
              "same_seed_fsys_reproduced": True, "all_other_common_members_identical": True}
    write_json(output / "randomizer-verification.json", result)
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", type=Path, default=Path("game"))
    parser.add_argument("--source-iso", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("build/randomizer-v1"))
    parser.add_argument("--seed", help="exact reproducible seed string, mandatory when building")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        if args.seed is not None:
            parser.error("--verify-only reads the seed from the manifest; omit --seed")
        verify_randomized(args.game, args.output_dir)
    elif args.source_iso is not None and args.seed is not None:
        build_randomized(args.game, args.source_iso, args.output_dir, args.seed)
    else:
        parser.error("--source-iso and --seed are required when building")
