"""Read-only starter, Shadow and gift preview through the production pipeline."""
from __future__ import annotations

from dataclasses import asdict
from contextlib import nullcontext
from copy import deepcopy
from functools import wraps
from pathlib import Path
import threading

from .artwork import ArtworkError, extract_portraits, extract_spinda_patterns
from .engine.colo_spinda import ORDINARY_SPINDA_OT, colo_spinda_gift_pid, colo_spinda_pid
from .engine.spinda import SPINDA
from .engine.species_rules import LEGENDARY_NATIONAL
from . import service, disc_images
from .legendary_shadow_assets import PACK as LEGENDARY_PACK, STEMS as LEGENDARY_STEMS, decorate_preview
from .xd import VERSION as XD_VERSION, XDOptions
from .options import Options, SPECIAL_OPTIONS
from .gift_presentation import order_purification_gifts
from .profiles import CreationReport, validate_seed
from .pokemon_details import COLOSSEUM_SHADOW_RUSH, encounter_details
from .preview_cache import PreviewCache, PreviewInput

# National Pokédex IDs from the original story tables in the supported revisions.
BASE_SHADOWS = tuple(zip((*range(1, 45), 55, 56, 57, 67), (
    296, 153, 156, 159, 164, 180, 188, 195, 200, 193, 162, 218, 223, 226, 211, 307,
    206, 333, 185, 237, 244, 166, 245, 207, 234, 221, 215, 190, 198, 205, 210, 329,
    168, 243, 192, 225, 214, 227, 241, 359, 229, 357, 376, 248, 235, 217, 213, 176,
), strict=True))
BASE_STARTERS = (("umbreon", 197, 26), ("espeon", 196, 25))
BASE_GIFTS = (("plusle", 311), ("ho-oh", 250), ("celebi-event", 251), ("pikachu-event", 25))
# All of these faces use their national number as the internal Gen III index.
ROULETTE_SPECIES = (1, 4, 7, 25, 37, 43, 54, 58, 63, 92, 133, 147, 152, 155, 158, 172, 194, 246)


def _add_spinda_patterns(iso, entries, *, is_xd=False):
    known = []
    for row, pid, status in entries:
        if row.get("species") != SPINDA:
            continue
        row["spinda_pattern_status"] = status
        if pid is not None:
            known.append((row, (pid, bool(row.get("shiny")))))
    if known:
        try:
            images = extract_spinda_patterns(iso, {key for _, key in known}, is_xd=is_xd)
        except ArtworkError:
            images = {}
        for row, key in known:
            if key in images:
                row["spinda_pattern_png"] = images[key]
            else:
                row["spinda_pattern_status"] = "spinda_pattern_unavailable"


def report_rom_matches(report: CreationReport, source: Path, dolphin_tool: Path | None,
                       cache: PreviewCache, cancel: threading.Event) -> bool:
    source = source.resolve()
    extension = source.suffix.lower()
    if extension not in disc_images.SUFFIXES or not source.is_file():
        raise service.UserError("Sélectionnez un fichier ISO, GCM ou RVZ existant.")
    digest = service.file_hash(source, cancel)
    if extension in disc_images.RAW_SUFFIXES:
        return digest == report.region.iso_sha256
    if digest == report.source_sha256:
        return True
    with cache.lease(source, digest, dolphin_tool, lambda *_: None, cancel) as image:
        matches = image.iso_hash == report.region.iso_sha256
    if service.file_hash(source, cancel) != digest:
        raise service.UserError("La ROM a changé pendant la comparaison. Sélectionnez-la de nouveau.")
    return matches


def baseline_rows(options: Options) -> dict:
    """Known species before the real preview, without reading or guessing a draw."""
    starters = []
    for key, species, level in BASE_STARTERS:
        switch = SPECIAL_OPTIONS[key]
        dex = getattr(options, switch + "_species") if getattr(options, switch) else species
        starters.append(dict(key=key, national_dex=dex if dex > 0 else None, level=level))
    shadows = [dict(shadow_id=key, original=dict(national_dex=species),
                    national_dex=None if options.randomize_shadows and (
                        options.randomize_legendary_shadows or species not in LEGENDARY_NATIONAL) else species)
               for key, species in BASE_SHADOWS]
    gifts = []
    for key, species in BASE_GIFTS:
        row = dict(key=key, original=dict(national_dex=species),
                   national_dex=None if getattr(options, SPECIAL_OPTIONS[key]) else species)
        if key.endswith("-event"):
            event = key.removesuffix("-event")
            if options.accessible_event_gifts:
                row["purifications"] = getattr(options, f"event_{event}_purifications")
            else:
                row["event"] = True
        gifts.append(row)
    return dict(starters=starters, shadows=shadows, gifts=order_purification_gifts(gifts),
                postgame_shadow_lugia={"enabled": options.postgame_shadow_lugia, "team": []})


def _discard_failed_cache(function):
    @wraps(function)
    def run(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except BaseException:
            cache = kwargs.get("cache")
            if cache is not None:
                cache.invalidate()
            raise
    return run


@_discard_failed_cache
def preview_starters(source: Path, seed: str, options: Options,
                     dolphin_tool: Path | None = None, *, progress=None,
                     cancel: threading.Event | None = None,
                     cache: PreviewCache | None = None, roulette=None, on_prepared=None, _known_only=False) -> dict:
    """Compute final bytes in memory, never publish an ISO or a report.

    RVZ conversion uses the integrated library and an owned temporary directory. An optional per-window cache reuses the decoded ISO across seeds;
    the original input and cached ISO are rehashed on every request.
    No independent RNG or approximation of the starter constraints is used.
    """
    progress = progress or (lambda percent, message: None)
    cancel = cancel or threading.Event()
    seed = validate_seed(seed)
    options = service.validate_options(options)
    source = Path(source).expanduser().resolve()
    if not source.is_file() or source.suffix.lower() not in disc_images.SUFFIXES:
        raise service.UserError("Sélectionnez un fichier ISO, GCM ou RVZ existant.")
    rvz = source.suffix.lower() == ".rvz"
    service.checkpoint(cancel)
    if not rvz:
        service.check_header(source)
    progress(0, "Vérification de la ROM d’origine…")
    source_hash = service.file_hash(source, cancel)
    owned_cache = cache is None
    selected_cache = cache if cache is not None else PreviewCache()
    if not rvz:
        selected_cache.invalidate()
    prepared = (selected_cache.lease(source, source_hash, dolphin_tool, progress, cancel)
                if rvz else nullcontext(PreviewInput(source, source_hash, False)))
    try:
        with prepared as image:
            iso = image.iso
            boot = service.check_header(iso)
            iso_hash = image.iso_hash
            region = service.check_disc_identity(boot, iso_hash)
            if roulette is not None and not _known_only:
                try:
                    roulette(extract_portraits(iso, ROULETTE_SPECIES))
                except ArtworkError:
                    pass
                service.checkpoint(cancel)
            if _known_only:
                from .known_encounters import colosseum_known
                patches, summary = [], colosseum_known(iso, boot, seed, options, cancel)
            else:
                patches, summary = service.build_patches(iso, boot, seed, options, progress, cancel)
            legendary_stems = (LEGENDARY_STEMS if _known_only and options.has_changes and LEGENDARY_PACK.is_file()
                               else summary.get('legendary_shadow_appearances', {}).get('stems', ()))
            service.checkpoint(cancel)
            final = {row["key"]: row for row in summary["special_gameplay"]["specials"]}
            def special(key):
                row = final[key]
                event = key in ("celebi-event", "pikachu-event")
                result = dict(key=key, species=row["species"], national_dex=row["national_dex"],
                            level=row["level"], original=row.get("original", {}),
                            event=event and not options.accessible_event_gifts,
                            **{"name_" + language: row["name_" + language]
                               for language in ("fr", "en", "de", "es", "it", "ja")})
                if event and options.accessible_event_gifts:
                    result["purifications"] = getattr(options, "event_celebi_purifications" if key == "celebi-event"
                                                       else "event_pikachu_purifications")
                return result

            starters = [special(key) for key in ("umbreon", "espeon") if key in final]
            gifts = [special(key) for key in final if key not in ("umbreon", "espeon")]
            shadows = [dict(row, species=row["species_index"])
                       for row in summary.get("final_shadow_picks", [])]
            event = deepcopy(summary.get("postgame_shadow_lugia", {"enabled": False}))
            event_team = event.get("team", []) if event.get("enabled") else []
            encounters = starters + shadows + gifts + event_team
            catalog = summary.get("detail_catalog")
            if catalog:
                shadow_rush = catalog["moves"].get(str(COLOSSEUM_SHADOW_RUSH))
                for row in starters + gifts:
                    actual = catalog["specials"][row["key"]]
                    row["details"] = encounter_details(catalog, row["species"], level=row["level"], moves=actual["moves"])
                for row in shadows:
                    actual = catalog["shadows"][str(row["shadow_id"])]
                    row["level"] = actual["level"]
                    row["details"] = encounter_details(catalog, row["species"], level=actual["level"], moves=actual["moves"], shadow=True)
                    if shadow_rush is not None:
                        row["details"]["initial_shadow_moves"] = [deepcopy(shadow_rush)]
                for row in event_team:
                    row["details"] = encounter_details(catalog, row["species"], level=row["level"],
                        moves=row["moves"], shadow=bool(row.get("shadow_id")))
                    if row.get("shadow_id") and shadow_rush is not None:
                        row["details"]["initial_shadow_moves"] = [deepcopy(shadow_rush)]
            shiny_policy = ("original" if not options.custom_shinies else "always" if options.shiny_chance_percent == 100
                            else "never" if options.shiny_chance_percent == 0
                            else "seeded" if options.seeded_shinies else "in-game")
            if options.custom_shinies and options.seeded_shinies:
                # These are the exact decisions used by the ROM patch, never another roll.
                decisions = summary["shinies"]["seeded_decisions"]
                for row in starters + gifts:
                    row["shiny"] = decisions["specials"][row["key"]]
                for row in shadows:
                    row["shiny"] = decisions["shadows"][str(row["shadow_id"])]
                for row in event_team:
                    field = "shadows" if row.get("shadow_id") else "trainer_slots"
                    index = row["shadow_id"] if row.get("shadow_id") else row["slot"]
                    row["shiny"] = decisions[field][str(index)]
            else:
                for row in encounters:
                    row["shiny"] = shiny_policy == "always"

            spinda_seeds = summary.get("shinies", {}).get("spinda_pid", {}).get("seeds", {})
            pattern_entries = [(row, None, "spinda_pattern_save") for row in starters + shadows]
            for row in gifts:
                pid = (colo_spinda_gift_pid(spinda_seeds, row["key"], row["shiny"])
                       if shiny_policy != "in-game" else None)
                pattern_entries.append((row, pid, "spinda_pattern_exact" if pid is not None
                                        else "spinda_pattern_in_game"))
            for row in event_team:
                pid = None
                if (row.get("species") == SPINDA and shiny_policy != "in-game"
                        and row["key"] in spinda_seeds and "gender" in row and "nature" in row):
                    pid = colo_spinda_pid(spinda_seeds[row["key"]], owner=ORDINARY_SPINDA_OT,
                        gender=row["gender"], nature=row["nature"], shiny=row["shiny"])
                pattern_entries.append((row, pid, "spinda_pattern_exact" if pid is not None
                                        else "spinda_pattern_in_game"))
            _add_spinda_patterns(iso, pattern_entries)

            # An evolution keeps the encounter's known chromatic status. Read
            # its whole chain while the verified ISO (including RVZ) is available.
            requests = []
            for row in encounters:
                chain = row.get("details", {}).get("evolution_chain", ())
                indices = (row["species"], *(step["target_species"] for step in chain))
                requests.append((row, indices))
            portraits = {}
            selected_form = summary.get("unown_form", 0)
            for shiny in (False, True):
                species = tuple(dict.fromkeys(index for row, chain in requests if row["shiny"] == shiny
                                              for index in chain))
                for start in range(0, len(species), 64):
                    service.checkpoint(cancel)
                    try:
                        batch = species[start:start + 64]
                        kwargs = {"shiny": True} if shiny else {}
                        if 201 in batch:
                            kwargs["unown_form_index"] = selected_form
                        images = extract_portraits(iso, batch, **kwargs)
                    except ArtworkError:
                        continue
                    portraits.update({(index, shiny): image for index, image in images.items()})
            for row, chain in requests:
                shiny = row["shiny"]
                row["portrait_png"] = portraits.get((row["species"], shiny), b"")
                if row["species"] == 249 and row.get("shadow_id"):
                    from .resources import shadow_lugia_portrait
                    row["portrait_png"] = shadow_lugia_portrait(shiny=bool(shiny))
                if len(chain) > 1:
                    row["evolution_portraits"] = {str(index): portraits[(index, shiny)] for index in chain
                                                   if (index, shiny) in portraits}
                from .deoxys_presentation import decorate_encounter
                decorate_encounter(row, summary.get('deoxys_forms', {}))
                decorate_preview(row, 'colosseum', legendary_stems)
            if service.file_hash(source, cancel) != source_hash:
                raise service.UserError("La ROM a changé pendant l’aperçu. Relancez-le avec une copie intacte.")
    except BaseException:
        selected_cache.invalidate()
        raise
    finally:
        if owned_cache:
            selected_cache.close()
    if on_prepared is not None and not _known_only:
        service.checkpoint(cancel)
        on_prepared(service.PreparedPatches(source=source, source_sha256=source_hash, iso_sha256=iso_hash,
                                           seed=seed, options=options, patches=tuple(patches),
                                           summary=deepcopy(summary)))
    return {"seed": seed, "options": asdict(options), "engine_version": service.ENGINE_VERSION,
            "game_id": region.game_id, "revision": region.revision,
            "source_sha256": source_hash, "source_iso_sha256": iso_hash,
            "starters": starters, "shadows": shadows, "gifts": order_purification_gifts(gifts), "shiny_policy": shiny_policy,
            "postgame_shadow_lugia": event,
            "family_duplicates": summary.get("story_families", {}).get("duplicates", [])}


@_discard_failed_cache
def preview_xd(source: Path, seed: str, xd_options: XDOptions,
               dolphin_tool: Path | None = None, *, progress=None,
               cancel: threading.Event | None = None, cache: PreviewCache | None = None,
               roulette=None, on_prepared=None, _known_only=False) -> dict:
    """Read the same verified XD patch plan used by Create, without publishing it."""
    progress = progress or (lambda percent, message: None)
    cancel = cancel or threading.Event()
    seed = validate_seed(seed)
    source = Path(source).expanduser().resolve()
    extension = source.suffix.lower()
    if extension not in disc_images.SUFFIXES or not source.is_file():
        raise service.UserError("Sélectionnez un fichier ISO, GCM ou RVZ existant.")
    rvz = extension == ".rvz"
    service.checkpoint(cancel)
    if not rvz:
        service.check_header(source, is_xd=True)
    progress(0, "Vérification de la ROM d’origine…")
    digest = service.file_hash(source, cancel)
    with (PreviewCache() if cache is None else nullcontext(cache)) as selected:
        if not rvz:
            selected.invalidate()
        lease = (selected.lease(source, digest, None, progress, cancel)
                 if rvz else nullcontext(PreviewInput(source, digest, False)))
        with lease as image:
            boot = service.check_header(image.iso, is_xd=True)
            region = service.check_disc_identity(boot, image.iso_hash, is_xd=True)
            if roulette is not None and not _known_only:
                try:
                    roulette(extract_portraits(image.iso, ROULETTE_SPECIES, is_xd=True))
                except ArtworkError:
                    pass
                service.checkpoint(cancel)
            progress(20, "Application des réglages…")
            if _known_only:
                from .known_encounters import xd_known
                patches, summary = [], xd_known(image.iso, boot, seed, xd_options, cancel)
            else:
                patches, summary = service.build_xd_patches(image.iso, boot, seed, xd_options, progress, cancel,
                                                          include_details=True)
            from .xd import effective_xd_setting_names
            legendary_stems = (LEGENDARY_STEMS if _known_only and effective_xd_setting_names(xd_options)
                               and LEGENDARY_PACK.is_file()
                               else summary.get('legendary_shadow_appearances', {}).get('stems', ()))
            prepared = None if _known_only else service.PreparedPatches(source=source, source_sha256=digest, iso_sha256=image.iso_hash,
                seed=seed, options=xd_options, patches=tuple(patches),
                summary=deepcopy({key: value for key, value in summary.items() if key != 'detail_catalog'}))
            starter = summary.get("starter")
            shadows = summary.get("decks", {}).get("Story", {}).get("shadows", ())
            gifts = summary.get("gifts", ())
            poke_spots = summary.get("poke_spots", ())
            known_pids = summary.get("spinda_pid", {}).get("known_reward_pids", {})
            rewards = [(row, row.get("key")) for row in gifts]
            if starter is not None:
                rewards.append((starter, "starter"))
            pattern_entries = [(row, None, "spinda_pattern_save") for row in shadows]
            pattern_entries.extend((row, None, "spinda_pattern_in_game") for row in poke_spots)
            pattern_entries.extend((row, known_pids.get(key), "spinda_pattern_palette" if key in known_pids
                                    else "spinda_pattern_save") for row, key in rewards)
            _add_spinda_patterns(image.iso, pattern_entries, is_xd=True)
            if catalog := summary.pop("detail_catalog", None):
                rows = [row for row in [starter, *shadows, *gifts, *poke_spots] if row is not None]
                requests = []
                for row in rows:
                    details = encounter_details(catalog, row["species"], level=row.get("level"),
                                                moves=row.get("moves"), shadow="shadow_id" in row)
                    row["details"] = details
                    chain = (row["species"], *(step["target_species"] for step in details["evolution_chain"]))
                    requests.append((row, chain))
                progress(65, "Lecture des portraits…")
                selected_form = summary.get("unown_form", 0)
                for shiny in (False, True):
                    selected_rows = [(row, chain) for row, chain in requests if bool(row.get("shiny")) == shiny]
                    indices = tuple(dict.fromkeys(index for _, chain in selected_rows for index in chain))
                    portraits = {}
                    for start in range(0, len(indices), 64):
                        service.checkpoint(cancel)
                        try:
                            batch = indices[start:start + 64]
                            kwargs = {"unown_form_index": selected_form} if 201 in batch else {}
                            portraits.update(extract_portraits(image.iso, batch, shiny=shiny, is_xd=True, **kwargs))
                        except ArtworkError:
                            continue
                    for row, chain in selected_rows:
                        row["portrait_png"] = portraits.get(row["species"], b"")
                        row["evolution_portraits"] = {str(index): portraits[index] for index in chain if index in portraits}
            for row in shadows:
                if row.get("shadow_id") and row.get("species") == 249:
                    from .resources import shadow_lugia_portrait
                    row["portrait_png"] = shadow_lugia_portrait(shiny=bool(row.get("shiny")), game="xd")
            from .deoxys_presentation import decorate_encounter
            if starter is not None:
                starter.setdefault('key', 'starter')
            for row in [starter, *shadows, *gifts, *poke_spots]:
                if row is not None:
                    decorate_encounter(row, summary.get('deoxys_forms', {}))
                    decorate_preview(row, 'xd', legendary_stems)
            if service.file_hash(source, cancel) != digest:
                raise service.UserError("La ROM a changé pendant l’aperçu. Relancez-le avec une copie intacte.")
    if on_prepared is not None and not _known_only:
        service.checkpoint(cancel)
        on_prepared(prepared)
    return dict(summary, seed=seed, game_id=region.game_id, revision=region.revision, engine_version=XD_VERSION)


def preview_known(*args, **kwargs):
    """Read only retained/manual encounters, never prepare a full ROM plan."""
    return preview_starters(*args, **kwargs, _known_only=True)


def preview_xd_known(*args, **kwargs):
    return preview_xd(*args, **kwargs, _known_only=True)
