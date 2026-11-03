"""Read-only Europe/USA/Japan matrix of final patches, previews and invariants.

Accepts only the exact original revision-0 ISO for its region. No ROM, profile
or save is written; the only persistent output is a new validation report.
"""
from __future__ import annotations
import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import struct
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from colosseum_randomizer import service
from colosseum_randomizer.engine.analyze_game import parse_dol, parse_fsys, u32
from colosseum_randomizer.engine.dol_regions import special_targets
from colosseum_randomizer.engine.evolution_rules import evolution_families, evolution_stage_info
from colosseum_randomizer.engine.gameplay_rules import MOVE_FIELDS, damaging, expanded_layout, move_catalog
from colosseum_randomizer.engine.inspect_tables import localized_names, u16
from colosseum_randomizer.engine.item_text import REPLACEMENTS
from colosseum_randomizer.engine.randomize_story import experience_at_level
from colosseum_randomizer.engine.randomize_trainers import layout
from colosseum_randomizer.engine.regions import region_for_boot
from colosseum_randomizer.engine.rebuild_iso import decoded_member
from colosseum_randomizer.engine.shiny_rules import seeded_status
from colosseum_randomizer.engine.species_rules import LEGENDARY_NATIONAL, species_catalog
from colosseum_randomizer.engine.survey_assets import fst_inventory
from colosseum_randomizer.options import Options, SPECIAL_OPTIONS


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_overlay(source, patches, offset, size):
    with source.open("rb") as stream:
        stream.seek(offset)
        result = bytearray(stream.read(size))
    assert len(result) == size
    for start, data in patches:
        left, right = max(offset, start), min(offset + size, start + len(data))
        if left < right:
            result[left-offset:right-offset] = data[left-start:right-start]
    return bytes(result)


def archive_data(source, boot, patches, name):
    fst = read_overlay(source, patches, u32(boot, 0x424), u32(boot, 0x428))
    entries, _ = fst_inventory(fst)
    entry = next(entry for entry in entries if entry["path"] == name)
    return read_overlay(source, patches, entry["disc_offset"], entry["size"])


def game_data(source, boot, patches):
    archive = archive_data(source, boot, patches, "common.fsys")
    member = next(member for member in parse_fsys(archive)["members"] if member["name"] == "common_rel")
    return decoded_member(archive, member)


def dol_bytes_at(dol, address, size):
    """Read a mapped final DOL range, including appended code/status sections."""
    matches = [section for section in parse_dol(dol)["sections"]
               if section["ram_address"] <= address
               and address + size <= section["ram_address"] + section["size"]]
    assert size > 0 and len(matches) == 1, "range is not uniquely mapped in final DOL"
    section = matches[0]
    offset = section["offset"] + address - section["ram_address"]
    result = dol[offset:offset + size]
    assert len(result) == size
    return result


def check_seeded_shinies(dol, summary, seed, options):
    """Inspect final embedded tables/wrappers, rather than trusting report hashes."""
    if not (options.custom_shinies and options.seeded_shinies):
        return None
    report = summary["shinies"]
    assert report["enabled"] and report["seeded"]
    assert report["requested_percent"] == options.shiny_chance_percent
    decisions = report["seeded_decisions"]
    counts = {}
    for group, prefix in (("trainer_slots", "trainer"), ("shadows", "shadow")):
        descriptor = report["status_tables"][group]
        actual = dol_bytes_at(dol, descriptor["address"], descriptor["count"])
        expected = bytes(seeded_status(seed, f"{prefix}:{i}", options.shiny_chance_percent)
                         for i in range(descriptor["count"]))
        assert actual == expected
        assert hashlib.sha256(actual).hexdigest() == descriptor["sha256"]
        assert [decisions[group][str(i)] for i in range(len(actual))] == list(map(bool, actual))
        counts[group] = {"checked": len(actual), "shiny": sum(actual)}
        if options.shiny_chance_percent == 100:
            assert all(actual)
        elif options.shiny_chance_percent == 25:
            assert 0 < sum(actual) < len(actual)
    for hook in report["hooks"]:
        if hook["key"] == "trainers":
            continue
        expected = seeded_status(seed, "special:" + hook["key"], options.shiny_chance_percent)
        assert decisions["specials"][hook["key"]] == expected
        # Seeded special wrappers put the exact never/always selector into r6
        # after their seven-word prologue, before calling the native generator.
        assert u32(dol_bytes_at(dol, hook["wrapper_address"] + 0x1C, 4), 0) == 0x38C00000 | int(expected)
    return {"embedded_status_tables_and_special_selectors_verified": True,
            "specials_checked": len(decisions["specials"]), **counts}


def check_preview(source, seed, options, summary, final_specials, picks):
    """Run the actual public preview API and compare it with composed final data."""
    from colosseum_randomizer.preview import preview_starters
    preview = preview_starters(source, seed, options)
    actual = {row["key"]: row for row in preview["starters"] + preview["gifts"]}
    assert actual.keys() == final_specials.keys()
    for key, expected in final_specials.items():
        assert (actual[key]["species"], actual[key]["level"]) == (expected["species"], expected["level"])
        for language in ("fr", "en", "de", "es", "it", "ja"):
            assert actual[key]["name_" + language] == expected["name_" + language]
        if options.custom_shinies and options.seeded_shinies:
            assert actual[key]["shiny"] == summary["shinies"]["seeded_decisions"]["specials"][key]
        if key in ("pikachu-event", "celebi-event") and options.accessible_event_gifts:
            required = options.event_pikachu_purifications if key == "pikachu-event" else options.event_celebi_purifications
            assert actual[key]["purifications"] == required
    assert {row["shadow_id"]: row["species"] for row in preview["shadows"]} == picks
    if options.custom_shinies and options.seeded_shinies:
        for row in preview["shadows"]:
            assert row["shiny"] == summary["shinies"]["seeded_decisions"]["shadows"][str(row["shadow_id"])]
    return {"actual_preview_api_verified": True, "specials_checked": len(actual),
            "shadows_checked": len(preview["shadows"]),
            "portrait_count": sum(bool(row["portrait_png"]) for row in
                                  preview["starters"] + preview["gifts"] + preview["shadows"])}


def cases():
    recommended = Options.recommended()
    return [
        ("recommended-ascii", "validation-000", recommended),
        ("recommended-unicode", "été-étoile-🌟", recommended),
        ("recommended-spaces", " seed avec espaces ", recommended),
        ("species", "species-42", Options()),
        ("first-evolution", "first-42", replace(recommended, starter_stage="first")),
        ("final-evolution", "final-42", replace(recommended, starter_stage="final")),
        ("any-stage-three-family", "any-42", replace(Options(), starter_stage="any")),
        ("copy", "copy-42", Options.none()),
        ("gen1-no-legendaries", "gen1-42", replace(recommended, allow_gen2=False, allow_gen3=False, allow_legendaries=False)),
        ("gen2-duplicates-allowed", "gen2-42", replace(recommended, allow_gen1=False, allow_gen3=False, allow_legendaries=False, unique_shadows=False)),
        ("gen3-no-legendaries", "gen3-42", replace(recommended, allow_gen1=False, allow_gen2=False, allow_legendaries=False)),
        ("advanced-chaos", "chaos-42", replace(recommended, randomize_types=True, randomize_stats=True,
            randomize_abilities=True, randomize_held_items=True, moves_mode="chaos", boss_stronger=True,
            trainer_level_multiplier=2.0, capture_rate_multiplier=5.0, minimum_catch_rate=255,
            tm_compatibility_mode="universal")),
        ("specials-preserved", "specials-42", replace(recommended, **{name: False for name in SPECIAL_OPTIONS.values()})),
        ("boss-status-preserved", "boss-status-42", replace(recommended, boss_shadow_legendary_mode="preserve", boss_shadow_power_mode="similar")),
        ("boss-power-minimum", "boss-power-42", replace(recommended, boss_shadow_min_bst=500, boss_shadow_power_mode="free")),
        ("shiny-seeded-25", "regional-shiny-25", replace(recommended, custom_shinies=True,
            seeded_shinies=True, shiny_chance_percent=25.0)),
        ("shiny-seeded-100", "regional-shiny-100", replace(recommended, custom_shinies=True,
            seeded_shinies=True, shiny_chance_percent=100.0)),
        ("events-custom", "regional-events-custom", replace(recommended,
            event_pikachu_purifications=0, event_celebi_purifications=48,
            event_pikachu_level=17, event_celebi_level=88)),
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    for _, _, options in cases():
        service.validate_options(options)
    if args.report.exists():
        parser.error("Choose a new report file; existing evidence is preserved.")
    started = time.monotonic()
    source_hash = digest(args.source)
    boot = service.check_header(args.source)
    region = service.check_disc_identity(boot, source_hash)
    assert region == region_for_boot(boot)
    original_dol = read_overlay(args.source, [], u32(boot, 0x420), region.dol_size)
    targets = special_targets(original_dol)
    original = game_data(args.source, boot, [])
    tables, symbols = layout(original)
    all_tables = expanded_layout(original)
    catalog = species_catalog(original, tables)
    families, _ = evolution_families(original, tables)
    stages = evolution_stage_info(original, tables)
    names, _ = localized_names(original, symbols)
    expected_languages = {"GC6P01": {"UK", "GE", "FR", "IT", "SP"},
                          "GC6E01": {"US"}, "GC6J01": {"JP"}}[region.game_id]
    assert {language for language, entries in names.items() if entries} == expected_languages
    moves = move_catalog(original, all_tables)
    trainer = tables["trainers"]
    pokemon = tables["trainer_pokemon"]
    shadow = tables["shadow"]
    referenced = set()
    for index in range(trainer["count"]):
        first = u16(original, trainer["offset"] + index * trainer["stride"] + 4)
        if first:
            referenced.update(range(first, first + 6))
    active_shadows = {original[pokemon["offset"] + index * pokemon["stride"] + 3]
                      for index in referenced
                      if u16(original, pokemon["offset"] + index * pokemon["stride"] + 0xA)} - {0}
    assert len(active_shadows) == 48
    results = []
    for label, seed, requested in cases():
        options = service.validate_options(requested)
        before = time.monotonic()
        patches, summary = service.build_patches(args.source, boot, seed, options, lambda *_: None, threading.Event())
        repeated, _ = service.build_patches(args.source, boot, seed, options, lambda *_: None, threading.Event())
        assert repeated == patches, label + ": nondeterministic bytes"
        final_boot = read_overlay(args.source, patches, 0, len(boot))
        rel = game_data(args.source, final_boot, patches)
        final_catalog = species_catalog(rel, tables)
        assert evolution_families(rel, tables)[0] == families
        picks = {sid: u16(rel, shadow["offset"] + sid * shadow["stride"] + 2) for sid in active_shadows}
        assert set(picks.values()) <= set(catalog)
        if options.randomize_shadows and options.unique_shadows:
            assert len({families[pick] for pick in picks.values()}) == 48
        checked_slots = 0
        for index in sorted(referenced):
            pos = pokemon["offset"] + index * pokemon["stride"]
            species = u16(rel, pos + 0xA)
            if not species:
                continue
            assert species in catalog
            assert 1 <= rel[pos + 4] <= 100
            sid = rel[pos + 3]
            if sid:
                assert picks[sid] == species
            if options.randomize_shadows if sid else options.randomize_trainers:
                national = catalog[species]["national_dex"]
                generation = 1 if national <= 151 else 2 if national <= 251 else 3
                assert getattr(options, f"allow_gen{generation}")
                assert options.allow_legendaries or national not in LEGENDARY_NATIONAL
            if options.randomize_trainer_moves:
                selected = [u16(rel, pos + field) for field in MOVE_FIELDS]
                original_moves = [u16(original, pos + field) for field in MOVE_FIELDS]
                if any(move >= 355 for move in original_moves):
                    assert selected == original_moves, "Native special move markers changed"
                else:
                    assert set(selected) <= set(moves)
                    if options.no_duplicate_moves:
                        assert len(set(selected)) == 4
                    if options.ensure_damaging_move:
                        assert any(damaging(moves[move]) for move in selected)
                    if options.ensure_stab_move:
                        assert any(damaging(moves[move]) and moves[move]["type"] in final_catalog[species]["types"] for move in selected)
            checked_slots += 1
        final_names, _ = localized_names(rel, symbols)
        assert {language for language, entries in final_names.items() if entries} == expected_languages
        native_item_names = {}
        for language, entries in names.items():
            if language not in expected_languages:
                assert not entries and not final_names[language]
                continue
            edits = REPLACEMENTS.get(language, {})
            for identifier, original_text in entries.items():
                replacement = edits.get(identifier, (original_text, original_text))[1]
                assert final_names[language][identifier] == (replacement if options.readable_stone_names else original_text)
            for identifier in range(5074, 5080):
                assert final_names[language][identifier]
            native_item_names[language] = {str(i): final_names[language][i] for i in range(5074, 5080)}
        dol_offset = u32(final_boot, 0x420)
        dol_size = next((len(payload) for offset, payload in patches if offset == dol_offset), region.dol_size)
        dol = read_overlay(args.source, patches, dol_offset, dol_size)
        final_specials = {row["key"]: row for row in summary["special_gameplay"]["specials"]}
        starter_species = []
        for target in targets:
            species = u16(dol, target["base"] + 2)
            assert species in catalog
            level = u16(dol, target["base"] + 6)
            expected_level = (getattr(options, "event_pikachu_level" if target["key"] == "pikachu-event" else "event_celebi_level")
                              if options.accessible_event_gifts and target["key"] in ("pikachu-event", "celebi-event")
                              else target["level"])
            assert level == expected_level
            assert (final_specials[target["key"]]["species"], final_specials[target["key"]]["level"]) == (species, level)
            if target["key"] in ("pikachu-event", "celebi-event"):
                assert u16(dol, target["base"] + 0x3A) == expected_level
            if "xp" in target:
                starter_species.append(species)
                if getattr(options, SPECIAL_OPTIONS[target["key"]]):
                    assert u16(dol, target["base"] + 0x92) == experience_at_level(rel[catalog[species]["offset"]], target["level"])
                    info = stages[species]
                    if options.starter_stage == "base":
                        assert info["base_form"]
                    elif options.starter_stage == "first":
                        assert info["stage"] == 1
                    elif options.starter_stage == "final":
                        assert info["final_form"]
                    if options.starter_three_stage_families:
                        assert info["family_stages"] == 3
        if options.starter_distinct_families and (options.starter_umbreon or options.starter_espeon):
            assert families[starter_species[0]] != families[starter_species[1]]
        if label == "copy":
            assert patches == []
        shiny_checks = check_seeded_shinies(dol, summary, seed, options)
        preview_checks = (check_preview(args.source, seed, options, summary, final_specials, picks)
                          if label in ("shiny-seeded-25", "shiny-seeded-100", "events-custom") else None)
        event_checks = None
        if options.accessible_event_gifts:
            event_reports = summary["event_gifts"]["archives"]
            assert len(event_reports) == 2
            expected_thresholds = {"pikachu-event": options.event_pikachu_purifications,
                                   "celebi-event": options.event_celebi_purifications}
            for report in event_reports:
                assert report["thresholds"] == expected_thresholds
                assert report["untargeted_decoded_members_unchanged"]
                final_archive = archive_data(args.source, final_boot, patches, report["archive"])
                assert hashlib.sha256(final_archive).hexdigest() == report["after_sha256"]
            event_checks = {"thresholds": expected_thresholds, "rebuilt_archives_verified": 2,
                            "constructor_and_met_levels_verified": True}
        patch_hash = hashlib.sha256()
        for offset, payload in patches:
            patch_hash.update(struct.pack(">QI", offset, len(payload)))
            patch_hash.update(payload)
        row = {"case": label, "seed": seed, "reproducible": True, "patch_sha256": patch_hash.hexdigest(),
               "patch_count": len(patches), "trainer_slots_checked": checked_slots,
               "distinct_shadow_families": len({families[pick] for pick in picks.values()}),
               "evolution_graph_preserved": True, "native_item_names_verified": True,
               "native_stone_names": native_item_names,
               "final_special_metadata_matches_dol": True,
               "seeded_shiny_checks": shiny_checks, "preview_checks": preview_checks,
               "event_checks": event_checks,
               "seconds": round(time.monotonic() - before, 3)}
        results.append(row)
        print(json.dumps({key: row[key] for key in ("case", "seed", "reproducible", "patch_sha256",
                         "patch_count", "trainer_slots_checked", "distinct_shadow_families", "seconds")},
                         ensure_ascii=True), flush=True)
    unchanged = digest(args.source) == source_hash
    assert unchanged
    result = {"game_id": region.game_id, "region": region.name, "revision": region.revision,
              "engine_version": service.ENGINE_VERSION,
              "source_sha256": source_hash, "source_unchanged": unchanged, "cases": results,
              "successful": True, "elapsed_seconds": round(time.monotonic() - started, 3),
              "scope": "Static integration of composed final disc patches, not a gameplay playthrough."}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
