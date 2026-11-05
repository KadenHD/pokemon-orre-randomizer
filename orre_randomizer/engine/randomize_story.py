"""Trainer randomizer v1 plus six identified regional starter/gift routines.

Keep trainer draws unchanged for a given v1 seed. DOL edits are restricted to
six species immediates and the two starters' EXP overrides. Never patch inputs.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct

from .analyze_game import FormatError, parse_dol, sha256, u32, write_json
from .inspect_tables import localized_names, u16
from .randomize_trainers import (VERSION as TRAINER_VERSION, choose_species, layout,
                                original_common, randomize_rel, verify_randomized)
from .rebuild_iso import rebuild
from .dol_regions import dol_layout, special_targets

VERSION = "trainers-and-gifts-v2"
DOL_SHA256 = "a788176a45eb88dbd227246a7205ab9856bc79f3cca7e4a0f5376cf466664df5"
ISO_NAME = "colosseum-pal-randomizer-story.iso"
SPECIALS = (
    {"key": "umbreon", "base": 0x131E1C, "old": 197, "level": 26, "xp": 19055},
    {"key": "espeon", "base": 0x131CF4, "old": 196, "level": 25, "xp": 16372},
    {"key": "plusle", "base": 0x131BF4, "old": 353, "level": 13},
    {"key": "ho-oh", "base": 0x131B10, "old": 250, "level": 70},
    {"key": "celebi-event", "base": 0x1318E0, "old": 251, "level": 10},
    {"key": "pikachu-event", "base": 0x1319F0, "old": 25, "level": 10},
)


def experience_at_level(group: int, level: int) -> int:
    """Gen III growth formulas, including each intermediate integer truncation."""
    if group not in range(6) or not 1 <= level <= 100:
        raise ValueError("unknown growth group or level")
    n = level
    if n == 1:
        return 0
    if group == 0:
        return n ** 3
    if group == 1:
        if n <= 50:
            return n ** 3 * (100 - n) // 50
        if n <= 68:
            return n ** 3 * (150 - n) // 100
        if n <= 98:
            return n ** 3 * ((1911 - 10 * n) // 3) // 500
        return n ** 3 * (160 - n) // 100
    if group == 2:
        if n <= 15:
            return n ** 3 * (((n + 1) // 3) + 24) // 50
        if n <= 36:
            return n ** 3 * (n + 14) // 50
        return n ** 3 * ((n // 2) + 32) // 50
    if group == 3:
        return 6 * n ** 3 // 5 - 15 * n ** 2 + 100 * n - 140
    if group == 4:
        return 4 * n ** 3 // 5
    return 5 * n ** 3 // 4


def patch_special_tables(dol: bytes, seed: str, species: dict[int, dict],
                         *, targets: tuple[dict, ...] = SPECIALS) -> tuple[bytes, dict]:
    """Production caller validates the DOL/REL fingerprints before this core."""
    pool = sorted(species)
    if sorted(s["national_dex"] for s in species.values()) != list(range(1, 387)):
        raise FormatError("specials require the same 386 real species")
    result = bytearray(dol)
    changes = []
    for target in targets:
        p, old, level = target["base"], target["old"], target["level"]
        if u32(dol, p) != 0x38800000 | old or u32(dol, p + 4) != 0x38A00000 | level:
            raise FormatError(f"unexpected species/level instructions: {target['key']}")
        new = choose_species(seed, "special:" + target["key"], pool, old)
        struct.pack_into(">H", result, p + 2, new)
        row = {"key": target["key"], "routine_offset": p, "species_field_offset": p + 2,
               "old_species_index": old, "new_species_index": new, "level_preserved": level,
               "old_species_fr": species[old]["name_fr"], "new_species_fr": species[new]["name_fr"],
               "growth_group": species[new]["growth_group"]}
        if "xp" in target:
            if u32(dol, p + 0x90) != 0x38E00000 | target["xp"]:
                raise FormatError("unexpected starter EXP override instruction")
            xp = experience_at_level(species[new]["growth_group"], level)
            if not 0 <= xp < 0x8000:
                raise FormatError("starter EXP exceeds signed li immediate")
            struct.pack_into(">H", result, p + 0x92, xp)
            row.update(exp_field_offset=p + 0x92, old_exp=target["xp"], new_exp=xp,
                       exp_policy="threshold of preserved level, zero progress to next level")
        changes.append(row)
    plan = {"version": VERSION, "draw_algorithm": TRAINER_VERSION, "seed": seed,
            "source_dol_sha256": sha256(dol), "randomized_dol_sha256": sha256(result),
            "special_changes": changes}
    plan.update(validate_dol_changes(dol, bytes(result), plan))
    return bytes(result), plan


def validate_dol_changes(original: bytes, modified: bytes, plan: dict) -> dict:
    if len(original) != len(modified) or original[:0x100] != modified[:0x100]:
        raise FormatError("DOL size/header changed")
    allowed = set()
    if len(plan["special_changes"]) != 6 or {r["key"] for r in plan["special_changes"]} != {s["key"] for s in SPECIALS}:
        raise FormatError("expected exactly six identified special routines")
    for c in plan["special_changes"]:
        pos = c["species_field_offset"]
        if (u16(original, pos), u16(modified, pos)) != (c["old_species_index"], c["new_species_index"]):
            raise FormatError("DOL species differs from manifest")
        allowed.update(range(pos, pos + 2))
        if "exp_field_offset" in c:
            pos = c["exp_field_offset"]
            if (u16(original, pos), u16(modified, pos)) != (c["old_exp"], c["new_exp"]):
                raise FormatError("DOL EXP differs from manifest")
            allowed.update(range(pos, pos + 2))
    actual = [{"offset": i, "before": a, "after": b}
              for i, (a, b) in enumerate(zip(original, modified, strict=True)) if a != b]
    if not actual or any(c["offset"] not in allowed for c in actual):
        raise FormatError("DOL changed outside six species and two EXP fields")
    return {"changed_dol_bytes": len(actual), "byte_changes": actual,
            "only_special_species_and_starter_exp_changed": True}


def randomize_specials(dol: bytes, rel: bytes, seed: str) -> tuple[bytes, dict]:
    region = dol_layout(dol)
    targets = special_targets(dol)
    tables, symbols = layout(rel)
    names, _ = localized_names(rel, symbols)
    native_names = names.get("FR", {})
    meta = tables["species"]
    species = {}
    for i in range(meta["count"]):
        p = meta["offset"] + i * meta["stride"]
        national = u16(rel, p + 0x10)
        if 1 <= national <= 386:
            species[i] = {"national_dex": national, "growth_group": rel[p],
                          "name_fr": native_names.get(u32(rel, p + 0x18))}
    # Validate all six immediate calls against the constructor identified locally.
    sections = parse_dol(dol)["sections"]
    for special in targets:
        pos = special["base"] + 8
        section = next(s for s in sections if s["offset"] <= pos < s["offset"] + s["size"])
        instruction = u32(dol, pos)
        displacement = instruction & 0x03FFFFFC
        if displacement & 0x02000000:
            displacement -= 0x04000000
        address = section["ram_address"] + pos - section["offset"]
        if instruction & 0xFC000003 != 0x48000001 or address + displacement != region.native_constructor:
            raise FormatError("special routine does not call expected Pokemon constructor")
    return patch_special_tables(dol, seed, species, targets=targets)


def build_story(game: Path, source_iso: Path, output: Path, seed: str) -> dict:
    _, member_index, original_rel = original_common(game)
    original_dol = (game / "sys/main.dol").read_bytes()
    rel, trainers = randomize_rel(original_rel, seed)
    dol, specials = randomize_specials(original_dol, original_rel, seed)
    if randomize_specials(original_dol, original_rel, seed) != (dol, specials):
        raise FormatError("specials did not reproduce from seed")
    if randomize_rel(original_rel, seed) != (rel, trainers):
        raise FormatError("trainers did not reproduce from seed")
    report = rebuild(game, source_iso, output, common_replacements={member_index: rel},
                     dol_replacement=dol, iso_filename=ISO_NAME)
    if report["changed_common_member_indices"] != [member_index]:
        raise FormatError("unexpected changed common member set")
    trainers.update(common_member_index=member_index, same_seed_rel_reproduced=True)
    write_json(output / "randomizer-manifest.json", trainers)
    write_json(output / "specials-manifest.json", specials)
    print(json.dumps({"specials": specials["special_changes"], "changed_dol_bytes": specials["changed_dol_bytes"]}, indent=2))
    return specials


def verify_story(game: Path, output: Path) -> dict:
    stored = json.loads((output / "specials-manifest.json").read_text(encoding="utf-8"))
    _, _, rel = original_common(game)
    expected_dol, expected_plan = randomize_specials((game / "sys/main.dol").read_bytes(), rel, stored["seed"])
    for key in ("version", "draw_algorithm", "source_dol_sha256", "randomized_dol_sha256", "special_changes", "byte_changes"):
        if stored[key] != expected_plan[key]:
            raise FormatError(f"special manifest does not reproduce: {key}")
    trainers = json.loads((output / "randomizer-manifest.json").read_text(encoding="utf-8"))
    if trainers["seed"] != stored["seed"]:
        raise FormatError("trainer and special seeds differ")
    verification = verify_randomized(game, output, expected_dol=expected_dol)
    result = {"version": VERSION, "seed": stored["seed"], "specials": expected_plan,
              "trainers": verification, "same_seed_dol_reproduced": True,
              "all_iso_changes_match_seed": True}
    write_json(output / "story-verification.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", type=Path, default=Path("game"))
    parser.add_argument("--source-iso", type=Path)
    parser.add_argument("--seed")
    parser.add_argument("--output-dir", type=Path, default=Path("build/randomizer-story-v2"))
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        if args.seed is not None:
            parser.error("--verify-only reads seed from manifests; omit --seed")
        verify_story(args.game, args.output_dir)
    elif args.source_iso is not None and args.seed is not None:
        build_story(args.game, args.source_iso, args.output_dir, args.seed)
    else:
        parser.error("--seed and --source-iso are required when building")
