"""Read known encounter data without allocating replacements or scene patches."""
from __future__ import annotations

from dataclasses import replace
import struct

from .engine.analyze_game import FormatError, parse_fsys, parse_rel, u32
from .engine.inspect_tables import rel_symbols, u16
from .engine.rebuild_iso import decoded_member
from .engine.survey_assets import fst_inventory
from .engine.shiny_rules import seeded_status
from .engine.unown_form import unown_form
from .preserved_pokemon import preserve_properties
from .fairy_content import scoped_content


def _read(iso, boot, region, cancel):
    from .service import checkpoint, read_exact
    with iso.open("rb") as stream:
        fst = read_exact(stream, u32(boot, 0x424), u32(boot, 0x428))
        files = {row["path"]: row for row in fst_inventory(fst)[0]}
        dol = read_exact(stream, u32(boot, 0x420), region.dol_size)

    def archive(name):
        checkpoint(cancel)
        row = files[name]
        with iso.open("rb") as stream:
            return read_exact(stream, row["disc_offset"], row["size"])

    def member(data, name):
        rows = [row for row in parse_fsys(data)["members"] if row["name"] == name]
        if len(rows) != 1:
            raise FormatError("missing or ambiguous known-encounter data")
        return decoded_member(data, rows[0])

    rel = member(archive("common.fsys"), "common_rel")
    return rel, dol, archive, member


def _closure(catalog, initial):
    selected, pending = set(), list(initial)
    while pending:
        species = pending.pop()
        if species not in selected:
            selected.add(species)
            pending.extend(row["target_species"] for row in catalog["species"][str(species)]["evolutions"])
    return selected


@scoped_content
def colosseum_known(iso, boot, seed, options, cancel):
    from .service import checkpoint
    from .engine.regions import region_for_boot
    from .engine.rel_regions import region_for_rel
    from .engine.dol_regions import dol_layout, special_targets
    from .engine.randomize_trainers import layout
    from .engine.evolution_rules import patch_evolutions
    from .engine.gameplay_rules import apply_species_gameplay, choose_moves, expanded_layout, move_catalog
    from .engine.level_curve import encounter_level
    from .engine.postgame_boss import DEFAULT_TEAM, LUGIA, PARTY_SLOT
    from .engine.species_rules import species_catalog
    from .engine.tm_rules import apply_tm_tables
    from .options import SPECIAL_OPTIONS
    from .pokemon_details import build_detail_catalog
    from .preview import baseline_rows

    region = region_for_boot(boot)
    original, native_dol, _archive, _member = _read(iso, boot, region, cancel)
    tables, _ = layout(original)
    native_catalog = build_detail_catalog(original, original, native_dol, native_dol)
    baseline = baseline_rows(options)
    native_species = native_catalog["species"]
    national = {row["national_dex"]: int(index) for index, row in native_species.items()}
    targets = {row["key"]: row for row in special_targets(native_dol)}
    specials, shadows, event_team = [], [], []
    for pending in baseline["starters"] + baseline["gifts"]:
        if pending.get("national_dex") is None:
            continue
        key = pending["key"]
        index = national[pending["national_dex"]]
        native = native_catalog["specials"][key]
        level = native["level"]
        if options.accessible_event_gifts and key in ("celebi-event", "pikachu-event"):
            level = getattr(options, "event_celebi_level" if key == "celebi-event" else "event_pikachu_level")
        specials.append(dict(key=key, species=index, national_dex=pending["national_dex"], level=level,
                             original=dict(national_dex=native_species[str(native["species"])]["national_dex"])))
    for pending in baseline["shadows"]:
        if pending.get("national_dex") is None:
            continue
        native = native_catalog["shadows"][str(pending["shadow_id"])]
        shadows.append(dict(shadow_id=pending["shadow_id"], species_index=native["species"],
                            national_dex=pending["national_dex"], original=pending["original"],
                            level=encounter_level(native["level"], options), slot=native["slot_index"]))
    if options.postgame_shadow_lugia:
        for i, index in enumerate((*DEFAULT_TEAM, LUGIA)):
            if options.postgame_randomize_lugia if i == 5 else options.postgame_randomize_team:
                continue
            at = tables["trainer_pokemon"]["offset"] + (4110 if i == 5 else 4111 + i) * tables["trainer_pokemon"]["stride"]
            moves = [177, 94, 105, 56] if i == 5 else [u16(original, at + field) for field in (0x36, 0x3E, 0x46, 0x4E)]
            event_team.append(dict(slot=PARTY_SLOT + i, key="shadow:96" if i == 5 else f"trainer:{PARTY_SLOT+i}",
                                   species=index, national_dex=native_species[str(index)]["national_dex"],
                                   level=65+i, shadow_id=96 if i == 5 else 0, moves=moves,
                                   gender=2, nature=-1, randomized=False))
    selected = _closure(native_catalog, [row["species"] for row in specials + event_team]
                        + [row["species_index"] for row in shadows])
    checkpoint(cancel)
    rel, _ = patch_evolutions(original, tables, options.evolution_groups)
    rel, _ = apply_species_gameplay(original, rel, seed, options, selected_species=selected)
    info = dol_layout(native_dol)
    if options.enable_fairy_type:
        from .fairy_integration import apply_tm_gameplay
        from .preserved_pokemon import colosseum_species
        rel, dol, tm_report = apply_tm_gameplay(original, rel, native_dol, native_dol, seed, options,
            region.game_id, species_table=tables['species'], selected_species=selected,
            preserve_species=colosseum_species(original, tables, options))
    else:
        rel, dol, tm_report = apply_tm_tables(original, rel, native_dol, native_dol, seed, options,
            expanded_layout(original), tm_offset=info.tm_table_offset, item_offset=info.item_table_offset,
            native_languages=region_for_rel(original).native_languages, selected_species=selected)
    catalog = species_catalog(rel, tables)
    moves = move_catalog(original, expanded_layout(original))
    dol = bytearray(dol)
    for row in specials:
        key, index, level = row["key"], row["species"], row["level"]
        target = targets[key]
        native = native_catalog["specials"][key]
        move_mode = options.randomize_starter_moves if key in ("umbreon", "espeon") else options.randomize_gift_moves
        kept = not getattr(options, SPECIAL_OPTIONS[key])
        draw = move_mode and not (kept and preserve_properties(options))
        row["moves"] = (choose_moves(seed, "special:" + key, catalog[index], level, moves, options,
                                    mode=move_mode)
                        if draw else list(native["moves"]))
        if key not in ("umbreon", "espeon") and not draw:
            learned = []
            for entry in native_species[str(index)]["learnset"]:
                if entry["level"] <= level:
                    if entry["move"] in learned:
                        learned.remove(entry["move"])
                    learned.append(entry["move"])
            row["moves"] = learned[-4:] + [0] * max(0, 4 - len(learned))
        struct.pack_into(">H", dol, target["base"] + 2, index)
        struct.pack_into(">H", dol, target["base"] + 6, level)
        if key in ("umbreon", "espeon"):
            for slot, move in enumerate(row["moves"]):
                struct.pack_into(">H", dol, target["base"] + 0x16 + slot * 0x10, move)
        for language, name in native_species[str(index)]["names"].items():
            row["name_" + language] = name
    rel_out = bytearray(rel)
    for row in shadows:
        at = tables["trainer_pokemon"]["offset"] + row["slot"] * tables["trainer_pokemon"]["stride"]
        native = native_catalog["shadows"][str(row["shadow_id"])]
        actual_moves = native["moves"]
        if (options.randomize_trainer_moves and not preserve_properties(options)
                and (options.randomize_trainer_moves == "natural" or not any(m == 0xFFFF or m >= 355 for m in actual_moves))):
            actual_moves = choose_moves(seed, f"trainer:{row['slot']}", catalog[row["species_index"]], row["level"], moves, options,
                                        mode=options.randomize_trainer_moves, originals=actual_moves)
        rel_out[at + 4] = row["level"]
        for field, move in zip((0x36, 0x3E, 0x46, 0x4E), actual_moves, strict=True):
            struct.pack_into(">H", rel_out, at + field, move)
    summary = dict(special_gameplay={"specials": specials}, final_shadow_picks=shadows,
                   postgame_shadow_lugia=dict(enabled=options.postgame_shadow_lugia, team=event_team))
    if options.enable_fairy_type:
        from .fairy_content import install_content
        final_rel, final_dol, summary['fairy'] = install_content(bytes(rel_out), bytes(dol), tm_report, preview=True)
    else:
        final_rel, final_dol = bytes(rel_out), bytes(dol)
    summary["detail_catalog"] = build_detail_catalog(original, final_rel, native_dol, final_dol, summary=summary)
    decisions = dict(specials={}, shadows={}, trainer_slots={})
    for row in specials:
        decisions["specials"][row["key"]] = seeded_status(seed, "special:" + row["key"], options.shiny_chance_percent)
    for row in shadows + event_team:
        key = f"shadow:{row['shadow_id']}" if row.get("shadow_id") else f"trainer:{row['slot']}"
        decisions["shadows" if row.get("shadow_id") else "trainer_slots"][str(row.get("shadow_id") or row["slot"])] = seeded_status(seed, key, options.shiny_chance_percent)
    summary["shinies"] = {"seeded_decisions": decisions}
    summary["unown_form"] = unown_form(seed) if options.has_changes else 0
    return summary


@scoped_content
def xd_known(iso, boot, seed, options, cancel):
    from . import xd
    from .service import checkpoint
    from .xd_preview import baseline_rows
    from .xd_gifts import (GIFT_BASELINES, GIFT_TRADE_REQUIREMENTS, HORDEL_SHADOW,
                           TOGETIC, _TRADE_MOVES, _PRIZE_MOVES)
    from .xd_shiny_rules import encounter_shiny
    from .xd_shadow_shinies import shadow_statuses
    from .xd_species_gameplay import XDMoveRandomizer, detail_catalog, patch_species_gameplay, patch_tm_gameplay
    from .engine.level_curve import encounter_level
    from .engine.pool_filters import allowed_replacement
    from .engine.spinda import SPINDA, spinda_pid_seed
    from .preserved_pokemon import xd_species

    options = xd.validate_options(options)
    region = xd.region_for_boot(boot)
    original, native_dol, archive, member = _read(iso, boot, region, cancel)
    symbols = rel_symbols(original, parse_rel(original))
    species, edges, families = xd._species(original, symbols)
    native_moves = XDMoveRandomizer(original, symbols, species, options)
    native_catalog = detail_catalog(original, native_dol, symbols, region.game_id, edges, native_moves)
    deck = archive("deck_archive.fsys")
    dark = member(deck, "DeckData_DarkPokemon.bin")
    story = member(deck, "DeckData_Story.bin")
    slots = xd._shadow_slots(dark)
    start = 0x20 + u32(story, 0x14)
    baseline = baseline_rows(options)
    shadow_flags = shadow_statuses(seed, options)
    shadows = []
    for pending in baseline["decks"]["Story"]["shadows"]:
        if pending.get("species") is None:
            continue
        sid = pending["shadow_id"]
        pos = start + slots[sid] * 0x20
        index = u16(story, pos)
        battle_level = (story[pos + 2] if sid in xd.PROTECTED_SHADOWS else encounter_level(story[pos + 2], options))
        level = battle_level if sid == HORDEL_SHADOW else dark[0x20 + sid * 0x18 + 2]
        row = dict(pending, species=index, level=level, battle_level=battle_level,
                   family=families[index], moves=[u16(dark, 0x20 + sid * 0x18 + 0xC + 2*i) for i in range(4)])
        if str(sid) in shadow_flags:
            row["shiny"] = shadow_flags[str(sid)]
        shadows.append(row)
    gifts = []
    for i, (key, index, level) in enumerate(GIFT_BASELINES):
        if options.randomize_gifts:
            continue
        row = dict(key=key, original=index, species=index, level=level, family=families[index],
                   moves=list(_TRADE_MOVES[i] if i < 4 else _PRIZE_MOVES[i-4]))
        if key in GIFT_TRADE_REQUIREMENTS:
            row["required_species"] = GIFT_TRADE_REQUIREMENTS[key]
        if key == "hordel-trade":
            row["required_evolution"] = TOGETIC
            if options.randomize_hordel_gift:
                row["required_species"] = row["required_evolution"] = None
        elif key in ("duking-trapinch", "duking-surskit", "duking-wooper") and options.randomize_poke_spots:
            row["required_species"] = None
        gifts.append(row)
    native_options = replace(options, randomize_poke_spots=False)
    rel, spots, _ = xd._rel(original, seed, species, edges, symbols, native_options)
    spots = spots if not options.randomize_poke_spots else []
    for row in spots:
        if options.custom_poke_spot_shinies and options.poke_spot_shiny_chance_percent in (0, 100):
            row["shiny"] = options.poke_spot_shiny_chance_percent == 100
    starter_known = baseline["starter"].get("species") is not None or bool(baseline["starter"].get("national_dex"))
    indices = [row["species"] for row in [*shadows, *gifts, *spots]]
    if starter_known:
        dex = baseline["starter"].get("national_dex") or 133
        indices.append(next(i for i, row in species.items() if row[0] == dex))
    selected = _closure(native_catalog, indices)
    protected = xd_species(options, story, families=families)
    rel, _ = patch_species_gameplay(rel, symbols, seed, species, families, options,
                                    preserve_species=protected, selected_species=selected)
    rel, dol, tm_report = patch_tm_gameplay(rel, native_dol, symbols, region.game_id, seed, species, options,
                                   preserve_species=protected, selected_species=selected)
    moves = XDMoveRandomizer(rel, symbols, species, options)
    starter = None
    if starter_known:
        eligible = {index for index, row in native_moves.species.items() if allowed_replacement(row, options)}
        dol, starter = xd._starter(dol, xd.STARTERS[region.game_id], seed, species, edges, families,
                                   eligible, options, moves)
    for row in gifts:
        if options.randomize_gift_moves and not preserve_properties(options):
            row["moves"] = moves.moves(seed, "xd:gift:" + row["key"], row["species"], row["level"], row["moves"],
                                       mode=options.randomize_gift_moves)
    known_pids = {}
    for row in [starter, *gifts]:
        if row is None:
            continue
        key = row.get("key", "starter")
        status = encounter_shiny(seed, options, key)
        if status is not None:
            row["shiny"] = status
        if row["species"] == SPINDA and xd.effective_xd_setting_names(options):
            known_pids[key] = spinda_pid_seed(seed, "xd:" + key)
    checkpoint(cancel)
    fairy_report = None
    if options.enable_fairy_type:
        from .fairy_content import install_content
        rel, dol, fairy_report = install_content(rel, bytes(dol), tm_report, preview=True)
    return dict(starter=starter, decks={"Story": {"shadows": shadows}}, gifts=gifts, poke_spots=spots,
                national_ids={str(i): row[0] for i, row in species.items()},
                unown_form=unown_form(seed) if xd.effective_xd_setting_names(options) else 0,
                spinda_pid={"known_reward_pids": known_pids},
                detail_catalog=detail_catalog(rel, dol, symbols, region.game_id, edges, moves,
                    fairy_report=fairy_report['additional_tms'] if fairy_report is not None else None))
