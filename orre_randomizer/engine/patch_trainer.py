"""Single trainer Pokemon witness patch for the validated GC6P01 dump.

Only the species and its default displayed name are replaced. Refuse shared
team slots, shadow Pokemon, other builds, and unexpected original values.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct

from .analyze_game import FormatError, parse_fsys, parse_rel, sha256, u32, write_json
from .inspect_tables import REL_SHA256, SCHEMAS, rel_symbols, u16
from .rebuild_iso import decoded_member, rebuild
from .survey_assets import fst_inventory


def patch_one(data: bytes, trainer_index: int = 771, slot: int = 4,
              species_index: int = 25) -> tuple[bytes, dict]:
    if sha256(data) != REL_SHA256:
        raise FormatError("common.rel is not the exact validated original build")
    symbols = rel_symbols(data, parse_rel(data))
    def table(name):
        pointer, counter, stride = SCHEMAS[name]
        return symbols[pointer]["offset"], u32(data, symbols[counter]["offset"]), stride
    trainers, trainer_count, trainer_stride = table("trainers")
    pokemon, pokemon_count, pokemon_stride = table("trainer_pokemon")
    species, species_count, species_stride = table("species")
    if not 0 <= trainer_index < trainer_count or not 0 <= slot < 6:
        raise ValueError("trainer/slot out of range")
    if not 0 < species_index < species_count:
        raise ValueError("new species out of range")
    trainer_offset = trainers + trainer_index * trainer_stride
    first = u16(data, trainer_offset + 4)
    index = first + slot
    if not first or index >= pokemon_count:
        raise FormatError("trainer team is absent/outside Pokemon table")
    references = []
    for i in range(trainer_count):
        start = u16(data, trainers + i * trainer_stride + 4)
        if start and start <= index < start + 6:
            references.append(i)
    if references != [trainer_index]:
        raise FormatError(f"Pokemon record is shared by trainers {references}")
    base = pokemon + index * pokemon_stride
    old_species = u16(data, base + 0xA)
    old_name = u32(data, base + 0x14)
    new_national = u16(data, species + species_index * species_stride + 0x10)
    new_name = u32(data, species + species_index * species_stride + 0x18)
    if data[base + 3]:
        raise FormatError("witness patch refuses shadow Pokemon")
    if not new_national or not new_name or old_species == species_index:
        raise FormatError("new species must be an actual, different Pokemon")
    if old_name != u32(data, species + old_species * species_stride + 0x18):
        raise FormatError("refuse to overwrite a custom/unknown nickname")
    output = bytearray(data)
    struct.pack_into(">H", output, base + 0xA, species_index)
    struct.pack_into(">I", output, base + 0x14, new_name)
    plan = {"trainer_index": trainer_index, "trainer_offset": trainer_offset,
            "team_first_index": first, "team_slot_zero_based": slot,
            "trainer_pokemon_index": index, "record_offset": base, "record_size": pokemon_stride,
            "referencing_trainers": references, "old_species_index": old_species,
            "new_species_index": species_index, "old_name_id": old_name, "new_name_id": new_name,
            "level_preserved": data[base + 4], "shadow_id_preserved": 0,
            "species_field_offset": base + 0xA, "name_field_offset": base + 0x14,
            "source_rel_sha256": sha256(data), "patched_rel_sha256": sha256(output)}
    changes = validate_payload(data, bytes(output), plan)
    plan["changed_bytes"] = changes
    return bytes(output), plan


def validate_payload(original: bytes, patched: bytes, plan: dict) -> list[dict]:
    if len(original) != len(patched):
        raise FormatError("REL length changed")
    species_offset, name_offset = plan["species_field_offset"], plan["name_field_offset"]
    allowed = set(range(species_offset, species_offset + 2)) | set(range(name_offset, name_offset + 4))
    changes = [{"offset": i, "before": a, "after": b}
               for i, (a, b) in enumerate(zip(original, patched, strict=True)) if a != b]
    if not changes or any(c["offset"] not in allowed for c in changes):
        raise FormatError("unexpected change outside the two selected Pokemon fields")
    for data, prefix in ((original, "old"), (patched, "new")):
        if u16(data, species_offset) != plan[prefix + "_species_index"] or u32(data, name_offset) != plan[prefix + "_name_id"]:
            raise FormatError("Pokemon field values do not match patch plan")
    return changes


def build_patch(game: Path, source_iso: Path, output: Path) -> dict:
    source = (game / "files/common.fsys").read_bytes()
    members = parse_fsys(source)["members"]
    matches = [m for m in members if m["name"] == "common_rel"]
    if len(matches) != 1:
        raise FormatError("expected one common_rel")
    original = decoded_member(source, matches[0])
    patched, plan = patch_one(original)
    # This fixed witness deliberately targets the already observed quick battle.
    if (plan["trainer_pokemon_index"], plan["old_species_index"], plan["old_name_id"]) != (1572, 232, 1232):
        raise FormatError("Basile/Donphan witness target does not match original")
    plan.update(trainer_name_fr="BASILE", old_species_fr="DONPHAN", new_species_fr="PIKACHU",
                common_member_index=matches[0]["index"],
                preserved_fields=["level", "moves", "held item", "ability selector", "gender", "nature", "EVs", "IVs"],
                runtime_validation="pending Dolphin observation")
    result = rebuild(game, source_iso, output, common_replacements={matches[0]["index"]: patched},
                     iso_filename="colosseum-pal-witness-pikachu.iso")
    if result["changed_common_member_indices"] != [matches[0]["index"]]:
        raise FormatError("unexpected changed common member set")
    write_json(output / "witness-patch.json", plan)
    return plan


def verify_patch(game: Path, output: Path) -> dict:
    from .verify_roundtrip import verify
    integrity = verify(game, output)
    plan = json.loads((output / "witness-patch.json").read_text(encoding="utf-8"))
    report = json.loads((output / "rebuild-report.json").read_text(encoding="utf-8"))
    source = (game / "files/common.fsys").read_bytes()
    boot = (game / "sys/boot.bin").read_bytes()
    with Path(report["output_iso"]).open("rb") as stream:
        stream.seek(u32(boot, 0x424))
        fst = stream.read(u32(boot, 0x428))
        entries, _ = fst_inventory(fst)
        entry = next(e for e in entries if e["path"] == "common.fsys")
        stream.seek(entry["disc_offset"])
        patched = stream.read(entry["size"])
    a, b = parse_fsys(source)["members"], parse_fsys(patched)["members"]
    changes = []
    for old, new in zip(a, b, strict=True):
        if (old["name"], old["identifier_raw"], old["compression"]) != (new["name"], new["identifier_raw"], new["compression"]):
            raise FormatError("archive member identity differs")
        old_bytes, new_bytes = decoded_member(source, old), decoded_member(patched, new)
        if old["index"] == plan["common_member_index"]:
            changes = validate_payload(old_bytes, new_bytes, plan)
            if sha256(new_bytes) != plan["patched_rel_sha256"]:
                raise FormatError("patched REL digest differs")
        elif old_bytes != new_bytes:
            raise FormatError("another common member changed")
    result = {"integrity": integrity, "changed_pokemon_record_count": 1,
              "changed_pokemon_record": plan["trainer_pokemon_index"], "changed_bytes": changes,
              "all_other_common_members_identical": True,
              "only_selected_species_and_default_name_changed": True}
    write_json(output / "witness-verification.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", type=Path, default=Path("game"))
    parser.add_argument("--source-iso", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("build/witness-pikachu"))
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        print(json.dumps(verify_patch(args.game, args.output_dir), indent=2))
    elif args.source_iso:
        print(json.dumps(build_patch(args.game, args.source_iso, args.output_dir), indent=2))
    else:
        parser.error("--source-iso is required when building")
