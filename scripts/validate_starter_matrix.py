"""Opt-in full patch-plan starter matrix against explicitly supplied retail ISOs.

Never writes an ISO or opens an emulator. Every case reaches the production
patch planner, including archive repacking and its native safety checks. The
JSONL evidence distinguishes the selected scope from a complete playthrough.
The regular test suite keeps a compact native regression subset separately.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orre_randomizer import __version__, service, xd
from orre_randomizer.options import Options
from orre_randomizer.presets import recommended_preset, species_preset
from orre_randomizer.profiles import validate_seed
from orre_randomizer.engine.analyze_game import FormatError
from orre_randomizer.engine.species_rules import LEGENDARY_NATIONAL

MODES = {"original": False, "natural": "natural", "random": True}
REPRESENTATIVE_SPECIES = (1, 11, 14, 63, 129, 132, 201, 202, 227, 235, 249, 292, 327, 351, 374, 375, 386)


def excluded_by_preset(national: int, preset: str) -> bool:
    return national == 292 or preset != "starter-only" and national in LEGENDARY_NATIONAL


def expected_policy_rejection(game_id: str, national: int, preset: str, error: Exception) -> bool:
    """Accept only the exact, existing manual-species exclusion refusal."""
    message = ("the selected XD starter is excluded" if game_id.startswith("GXX") else
               "Le starter choisi est exclu par les filtres. Modifiez le choix manuel ou les Pokémon autorisés.")
    return excluded_by_preset(national, preset) and type(error) is FormatError and str(error) == message


def source_identity(path: Path) -> dict:
    path = Path(path).resolve()
    with path.open("rb") as stream:
        boot = stream.read(0x440)
        stream.seek(0)
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    game_id = boot[:6].decode("ascii")
    region = service.check_disc_identity(boot, digest, is_xd=game_id.startswith("GXX"))
    return {"game_id": region.game_id, "sha256": digest, "bytes": path.stat().st_size,
            "boot": boot, "path": path}


def starter_options(game_id: str, national: int, mode: str, preset: str = "starter-only"):
    if mode not in MODES or not 0 <= national <= 386:
        raise ValueError("Unknown move mode or starter species")
    is_xd = game_id.startswith("GXX")
    if preset == "starter-only":
        base = xd.XDOptions.unchanged() if is_xd else Options.none()
        base = replace(base, allow_gen1=True, allow_gen2=True, allow_gen3=True, allow_legendaries=True,
                       starter_stage="any", starter_three_stage_families=False,
                       randomize_starter_moves=MODES[mode])
        return (replace(base, randomize_starter=True, starter_species=national) if is_xd else
                replace(base, starter_umbreon=True, starter_espeon=True,
                        starter_umbreon_species=national, starter_espeon_species=national))
    if preset not in ("pokemon", "pokemon-moves"):
        raise ValueError("Unknown preset")
    if mode != ("natural" if preset == "pokemon" else "random"):
        raise ValueError("A preset matrix must use that preset's actual move mode")
    base = ((xd.XDOptions.species_only() if preset == "pokemon" else xd.XDOptions.recommended())
            if is_xd else (species_preset() if preset == "pokemon" else recommended_preset()))
    # Keep the complete preset unchanged apart from the selected first starter.
    return replace(base, **({"starter_species": national} if is_xd else {"starter_umbreon_species": national}))


def validate_plan(patches, size: int) -> str:
    """Validate the complete serialized plan and record exact payload identity."""
    previous_end = 0
    digest = hashlib.sha256()
    if not patches:
        raise AssertionError("A requested starter produced no patches")
    for offset, payload in patches:
        if type(offset) is not int or not isinstance(payload, bytes) or not payload:
            raise AssertionError("Invalid final patch record")
        if offset < previous_end or offset + len(payload) > size:
            raise AssertionError("Overlapping or out-of-bounds final patch")
        previous_end = offset + len(payload)
        digest.update(struct.pack(">QQ", offset, len(payload)))
        digest.update(payload)
    return digest.hexdigest()


def plan_case(identity: dict, national: int, mode: str, seed: str, preset: str = "starter-only") -> dict:
    options = starter_options(identity["game_id"], national, mode, preset)
    is_xd = identity["game_id"].startswith("GXX")
    started = time.monotonic()
    build = service.build_xd_patches if is_xd else service.build_patches
    patches, summary = build(identity["path"], identity["boot"], seed, options,
                             lambda *_args: None, threading.Event())
    if excluded_by_preset(national, preset):
        raise AssertionError("The native manual-species exclusion unexpectedly accepted this starter")
    patch_digest = validate_plan(patches, identity["bytes"])
    if is_xd:
        row = summary["starter"]
        actual = summary["national_ids"][str(row["species"])]
        rows = [{"slot": "starter", "national": actual, "species": row["species"],
                 "level": row["level"], "moves": row["moves"]}]
    else:
        specials = {row["key"]: row for row in summary["special_gameplay"]["specials"]}
        keys = ("umbreon", "espeon")
        rows = [{"slot": key, "national": specials[key]["national_dex"],
                 "species": specials[key]["species"], "level": specials[key]["level"],
                 "moves": specials[key].get("moves")} for key in keys]
    checked_rows = rows if preset == "starter-only" or is_xd else rows[:1]
    if national and any(row["national"] != national for row in checked_rows):
        raise AssertionError("The final plan does not retain the selected species")
    for row in rows:
        if row["moves"] is not None and (len(row["moves"]) != 4 or any(type(m) is not int for m in row["moves"])):
            raise AssertionError("The final starter has malformed move slots")
    return {"game_id": identity["game_id"], "national": national, "mode": mode,
            "preset": preset, "seed": seed, "status": "passed", "starters": rows,
            "patch_count": len(patches), "patch_bytes": sum(len(payload) for _, payload in patches),
            "patch_sha256": patch_digest, "seconds": round(time.monotonic() - started, 3),
            "capture_tutorial": summary.get("capture_tutorial")}


def main(arguments=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", action="append", required=True, type=Path,
                        help="Explicit original raw ISO/GCM; repeat for other games/regions")
    parser.add_argument("--species", default="representative", help="all, representative, auto or comma-separated national IDs")
    parser.add_argument("--mode", action="append", choices=tuple(MODES), help="Repeat to cover additional modes")
    parser.add_argument("--preset", choices=("starter-only", "pokemon", "pokemon-moves"), default="starter-only")
    parser.add_argument("--seed", action="append", help="Repeat for a full seed cross-product")
    parser.add_argument("--report", required=True, type=Path, help="New JSONL evidence file; never overwritten")
    args = parser.parse_args(arguments)
    species = ((0,) if args.species == "auto" else tuple(range(1, 387)) if args.species == "all" else REPRESENTATIVE_SPECIES
               if args.species == "representative" else tuple(int(v) for v in args.species.split(",")))
    if not species or len(set(species)) != len(species) or any(not 1 <= value <= 386 for value in species if args.species != "auto"):
        parser.error("Species must be auto or unique national numbers from 1 to 386")
    modes = args.mode or (["random"] if args.preset == "pokemon-moves" else ["natural"])
    if args.preset != "starter-only" and any(mode != ("natural" if args.preset == "pokemon" else "random") for mode in modes):
        parser.error("The selected preset must keep its actual move mode")
    seeds = args.seed or ["starter-matrix-v211"]
    if len(set(modes)) != len(modes) or len(set(seeds)) != len(seeds):
        parser.error("Do not repeat an identical mode or seed")
    try:
        seeds = [validate_seed(seed) for seed in seeds]
    except service.UserError as error:
        parser.error(str(error))
    images = [source_identity(path) for path in args.image]
    if len({row["game_id"] for row in images}) != len(images):
        parser.error("Supply only one image for each game ID")
    total = len(images) * len(species) * len(modes) * len(seeds)
    passed = failed = excluded = 0
    with args.report.open("x", encoding="utf-8") as output:
        def emit(row):
            output.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            output.flush()
        emit({"kind": "scope", "app_version": __version__, "started_utc": datetime.now(timezone.utc).isoformat(),
              "engines": {"colosseum": service.ENGINE_VERSION, "xd": xd.VERSION},
              "production_patch_plans": True, "rom_outputs_written": 0, "emulator_started": False,
              "species": species, "modes": modes, "seeds": seeds, "preset": args.preset,
              "expected_policy_exclusions": [national for national in species if excluded_by_preset(national, args.preset)],
              "case_count": total, "sources": [{k:v for k,v in row.items() if k not in ("boot", "path")} for row in images]})
        for identity in images:
            for national in species:
                for mode in modes:
                    for seed in seeds:
                        try:
                            row = plan_case(identity, national, mode, seed, args.preset)
                            passed += 1
                        except Exception as error:
                            expected = expected_policy_rejection(identity["game_id"], national, args.preset, error)
                            row = {"game_id": identity["game_id"], "national": national, "mode": mode,
                                   "seed": seed, "preset": args.preset, "status": "policy-exclusion" if expected else "failed",
                                   "error_type": type(error).__name__, "error": str(error)}
                            if expected:
                                excluded += 1
                            else:
                                failed += 1
                        emit(row)
                        print(f"{passed + failed + excluded}/{total} {identity['game_id']} #{national} {mode}: {row['status']}", flush=True)
        unchanged = all(source_identity(row["path"])["sha256"] == row["sha256"] for row in images)
        emit({"kind": "result", "passed": passed, "excluded": excluded, "failed": failed, "originals_unchanged": unchanged,
              "successful": failed == 0 and unchanged})
    return 0 if failed == 0 and unchanged else 1


if __name__ == "__main__":
    raise SystemExit(main())
