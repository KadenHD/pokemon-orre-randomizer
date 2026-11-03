"""Story randomizer v3: unique shadow families and accessible evolution routes.

All transformations start from fingerprinted originals. Preserve ordinary trainer
draws and six special draws; only colliding shadow groups are redrawn. Restore
blocked evolution methods and supply native stones in the early cash buy menus.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import struct

from .analyze_game import FormatError, sha256, u32, write_json
from .evolution_rules import evolution_families, patch_evolutions, unique_shadow_picks
from .inspect_tables import localized_names, u16
from .randomize_story import randomize_specials
from .randomize_trainers import layout, original_common, randomize_rel, validate_changes
from .rebuild_iso import rebuild, repack_fsys
from .shop_stones import patch_shop_archives
from .survey_assets import fst_inventory
from .verify_roundtrip import verify
from .dol_regions import dol_layout

VERSION = "unique-shadow-families-accessible-evolutions-v3"
ISO_NAME = "colosseum-pal-randomizer-v3.iso"
MOON_STONE_PRICE_OFFSET = 0x3AEC56


def randomize_accessible_rel(original: bytes, seed: str) -> tuple[bytes, dict]:
    tables, symbols = layout(original)
    base_payload, trainers = randomize_rel(original, seed)
    trainers = copy.deepcopy(trainers)
    trainers["trainer_names_fr"] = {str(key): value for key, value in trainers["trainer_names_fr"].items()}
    base_picks = {c["shadow_id"]: c["new_species_index"] for c in trainers["shadow_changes"]}
    picks, shadow_families = unique_shadow_picks(original, tables, seed, base_picks)
    output = bytearray(base_payload)
    names, _ = localized_names(original, symbols)
    species = tables["species"]
    for c in trainers["trainer_pokemon_changes"]:
        if not c["shadow_id"]:
            continue
        new = picks[c["shadow_id"]]
        species_pos = species["offset"] + new * species["stride"]
        name = u32(original, species_pos + 0x18)
        ability = c["old_ability_selector"]
        if ability == 1 and not original[species_pos + 0x33]:
            ability = 0
        pos = c["offset"]
        struct.pack_into(">H", output, pos + 0xA, new)
        struct.pack_into(">I", output, pos + 0x14, name)
        output[pos] = ability
        c.update(new_species_index=new, new_name_id=name, new_species_fr=names["FR"].get(name),
                 new_ability_selector=ability)
    for c in trainers["shadow_changes"]:
        new = picks[c["shadow_id"]]
        struct.pack_into(">H", output, c["offset"], new)
        c["new_species_index"] = new
    trainers["algorithm"] = "trainer-unique-shadow-families-v3"
    trainers["base_draw_algorithm"] = "trainer-species-sha256-v1"
    trainers["randomized_rel_sha256"] = sha256(output)
    trainers["summary"]["ability_selectors_normalized"] = sum(
        c["old_ability_selector"] != c["new_ability_selector"] for c in trainers["trainer_pokemon_changes"])
    trainers["summary"].update(validate_changes(original, bytes(output), trainers))
    # The evolution transformer validates its own whitelist against the original.
    evolved, evolution_plan = patch_evolutions(original, tables)
    for edit in evolution_plan["edits"]:
        pos = edit["record_offset"]
        output[pos:pos + 6] = evolved[pos:pos + 6]
    family_map, members = evolution_families(original, tables)
    after_map, after_members = evolution_families(bytes(output), tables)
    if family_map != after_map or members != after_members:
        raise FormatError("evolution changes altered family membership")
    if len({family_map[new] for new in picks.values()}) != len(picks):
        raise FormatError("two shadow IDs belong to the same evolution family")
    return bytes(output), {
        "version": VERSION, "seed": seed, "randomized_rel_sha256": sha256(output),
        "source_rel_sha256": sha256(original), "trainers": trainers,
        "shadow_families": shadow_families, "evolutions": evolution_plan,
        "family_count": len(members), "all_evolution_families_preserved": True,
        "changed_rel_bytes": sum(a != b for a, b in zip(original, output, strict=True)),
    }


def randomize_accessible_dol(original: bytes, rel: bytes, seed: str) -> tuple[bytes, dict]:
    output, specials = randomize_specials(original, rel, seed)
    price_offset = dol_layout(original).moon_stone_price_offset
    if u16(original, price_offset) != 0:
        raise FormatError("unexpected original Moon Stone price")
    result = bytearray(output)
    struct.pack_into(">H", result, price_offset, 2100)
    return bytes(result), {
        "specials": specials, "randomized_dol_sha256": sha256(result),
        "moon_stone_price": {"offset": price_offset, "before": 0, "after": 2100},
        "changed_dol_bytes": sum(a != b for a, b in zip(original, result, strict=True)),
    }


def transform(game: Path, seed: str) -> tuple[bytes, bytes, dict[str, bytes], dict]:
    _, member, original = original_common(game)
    rel, rel_plan = randomize_accessible_rel(original, seed)
    dol, dol_plan = randomize_accessible_dol((game / "sys/main.dol").read_bytes(), original, seed)
    files, shops = patch_shop_archives(game)
    return rel, dol, files, {
        "version": VERSION, "seed": seed, "common_member_index": member,
        "rel": rel_plan, "dol": dol_plan, "shops": shops,
    }


def build_accessible(game: Path, source_iso: Path, output: Path, seed: str) -> dict:
    rel, dol, files, plan = transform(game, seed)
    # Reproducibility of each pure component is also checked by verification of
    # the actual ISO. Tests pin the selection and evolution rules independently.
    result = rebuild(game, source_iso, output, common_replacements={plan["common_member_index"]: rel},
                     dol_replacement=dol, file_replacements=files, iso_filename=ISO_NAME)
    if result["changed_common_member_indices"] != [plan["common_member_index"]]:
        raise FormatError("unexpected changed common member set")
    write_json(output / "accessible-manifest.json", plan)
    print(json.dumps({"shadow_families": plan["rel"]["shadow_families"],
                      "evolution_edits": len(plan["rel"]["evolutions"]["edits"])}, indent=2))
    return plan


def verify_accessible(game: Path, output: Path) -> dict:
    saved = json.loads((output / "accessible-manifest.json").read_text(encoding="utf-8"))
    rel, dol, files, plan = transform(game, saved["seed"])
    for key in ("version", "seed", "common_member_index", "rel", "dol", "shops"):
        if saved[key] != plan[key]:
            raise FormatError(f"manifest does not reproduce from originals and seed: {key}")
    integrity = verify(game, output, expected_dol=dol, expected_files=files)
    report = json.loads((output / "rebuild-report.json").read_text(encoding="utf-8"))
    source, member_index, _ = original_common(game)
    archive, _ = repack_fsys(source, {member_index: rel})
    boot = (game / "sys/boot.bin").read_bytes()
    with Path(report["output_iso"]).open("rb") as stream:
        stream.seek(u32(boot, 0x424))
        entries, _ = fst_inventory(stream.read(u32(boot, 0x428)))
        entry = next(e for e in entries if e["path"] == "common.fsys")
        stream.seek(entry["disc_offset"])
        if stream.read(entry["size"]) != archive:
            raise FormatError("actual ISO common archive differs from exact seeded expected bytes")
    result = {"version": VERSION, "seed": plan["seed"], "integrity": integrity,
              "same_seed_rel_dol_archives_reproduced": True,
              "shadow_families": plan["rel"]["shadow_families"],
              "evolution_edits": len(plan["rel"]["evolutions"]["edits"]),
              "evolution_families_preserved": True,
              "stone_shop_archives": sorted(files), "all_original_shop_stock_preserved": True}
    write_json(output / "accessible-verification.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", type=Path, default=Path("game"))
    parser.add_argument("--source-iso", type=Path)
    parser.add_argument("--seed")
    parser.add_argument("--output-dir", type=Path, default=Path("build/randomizer-v3"))
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        if args.seed is not None:
            parser.error("--verify-only reads the seed from the manifest")
        print(json.dumps(verify_accessible(args.game, args.output_dir), indent=2))
    elif args.source_iso is not None and args.seed is not None:
        build_accessible(args.game, args.source_iso, args.output_dir, args.seed)
    else:
        parser.error("--source-iso and --seed are required when building")
