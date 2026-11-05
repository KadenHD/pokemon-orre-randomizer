"""Read-only starter, Shadow and gift preview through the production pipeline."""
from __future__ import annotations

from dataclasses import asdict
from contextlib import nullcontext
from copy import deepcopy
from functools import wraps
from pathlib import Path
import threading

from .artwork import ArtworkError, extract_portraits
from . import service
from .xd import VERSION as XD_VERSION, XDOptions
from .options import Options, SPECIAL_OPTIONS
from .profiles import CreationReport, validate_seed
from .pokemon_details import encounter_details
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


def report_rom_matches(report: CreationReport, source: Path, dolphin_tool: Path | None,
                       cache: PreviewCache, cancel: threading.Event) -> bool:
    source = source.resolve()
    extension = source.suffix.lower()
    if extension not in (".iso", ".rvz") or not source.is_file():
        raise service.UserError("Sélectionnez un fichier ISO ou RVZ existant.")
    digest = service.file_hash(source, cancel)
    if extension == ".iso":
        return digest == report.region.iso_sha256
    if digest == report.source_sha256:
        return True
    if dolphin_tool is None or not dolphin_tool.is_file():
        raise service.RVZToolRequired("Indiquez DolphinTool à l’étape ROM pour comparer cette RVZ.")
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
                    national_dex=None if options.randomize_shadows else species)
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
    return dict(starters=starters, shadows=shadows, gifts=gifts)


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
                     cache: PreviewCache | None = None, roulette=None, on_prepared=None) -> dict:
    """Compute final bytes in memory, never publish an ISO or a report.

    RVZ conversion owns a temporary directory and an isolated DolphinTool
    profile. An optional per-window cache reuses the decoded ISO across seeds;
    the original input and cached ISO are rehashed on every request.
    No independent RNG or approximation of the starter constraints is used.
    """
    progress = progress or (lambda percent, message: None)
    cancel = cancel or threading.Event()
    seed = validate_seed(seed)
    options = service.validate_options(options)
    source = Path(source).expanduser().resolve()
    if not source.is_file() or source.suffix.lower() not in (".iso", ".rvz"):
        raise service.UserError("Sélectionnez un fichier ISO ou RVZ existant.")
    rvz = source.suffix.lower() == ".rvz"
    if rvz and (dolphin_tool is None or not dolphin_tool.is_file()):
        raise service.RVZToolRequired("Pour utiliser le format RVZ, sélectionnez DolphinTool dans votre installation de Dolphin.")
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
            if roulette is not None:
                try:
                    roulette(extract_portraits(iso, ROULETTE_SPECIES))
                except ArtworkError:
                    pass
                service.checkpoint(cancel)
            patches, summary = service.build_patches(iso, boot, seed, options, progress, cancel)
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

            starters = [special(key) for key in ("umbreon", "espeon")]
            gifts = [special(key) for key in final if key not in ("umbreon", "espeon")]
            shadows = [dict(row, species=row["species_index"])
                       for row in summary.get("final_shadow_picks", [])]
            encounters = starters + shadows + gifts
            catalog = summary.get("detail_catalog")
            if catalog:
                for row in starters + gifts:
                    actual = catalog["specials"][row["key"]]
                    row["details"] = encounter_details(catalog, row["species"], level=row["level"], moves=actual["moves"])
                for row in shadows:
                    actual = catalog["shadows"][str(row["shadow_id"])]
                    row["level"] = actual["level"]
                    row["details"] = encounter_details(catalog, row["species"], level=actual["level"], moves=actual["moves"], shadow=True)
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
            else:
                for row in encounters:
                    row["shiny"] = shiny_policy == "always"

            # An evolution keeps the encounter's known chromatic status. Read
            # its whole chain while the verified ISO (including RVZ) is available.
            requests = []
            for row in encounters:
                chain = row.get("details", {}).get("evolution_chain", ())
                indices = (row["species"], *(step["target_species"] for step in chain))
                requests.append((row, indices))
            portraits = {}
            for shiny in (False, True):
                species = tuple(dict.fromkeys(index for row, chain in requests if row["shiny"] == shiny
                                              for index in chain))
                for start in range(0, len(species), 64):
                    service.checkpoint(cancel)
                    try:
                        batch = species[start:start + 64]
                        images = extract_portraits(iso, batch, shiny=True) if shiny else extract_portraits(iso, batch)
                    except ArtworkError:
                        continue
                    portraits.update({(index, shiny): image for index, image in images.items()})
            for row, chain in requests:
                shiny = row["shiny"]
                row["portrait_png"] = portraits.get((row["species"], shiny), b"")
                if len(chain) > 1:
                    row["evolution_portraits"] = {str(index): portraits[(index, shiny)] for index in chain
                                                   if (index, shiny) in portraits}
            if service.file_hash(source, cancel) != source_hash:
                raise service.UserError("La ROM a changé pendant l’aperçu. Relancez-le avec une copie intacte.")
    except BaseException:
        selected_cache.invalidate()
        raise
    finally:
        if owned_cache:
            selected_cache.close()
    if on_prepared is not None:
        service.checkpoint(cancel)
        on_prepared(service.PreparedPatches(source=source, source_sha256=source_hash, iso_sha256=iso_hash,
                                           seed=seed, options=options, patches=tuple(patches),
                                           summary=deepcopy(summary)))
    return {"seed": seed, "options": asdict(options), "engine_version": service.ENGINE_VERSION,
            "game_id": region.game_id, "revision": region.revision,
            "source_sha256": source_hash, "source_iso_sha256": iso_hash,
            "starters": starters, "shadows": shadows, "gifts": gifts, "shiny_policy": shiny_policy,
            "family_duplicates": summary.get("story_families", {}).get("duplicates", [])}


@_discard_failed_cache
def preview_xd(source: Path, seed: str, xd_options: XDOptions,
               dolphin_tool: Path | None = None, *, progress=None,
               cancel: threading.Event | None = None, cache: PreviewCache | None = None,
               roulette=None, on_prepared=None) -> dict:
    """Read the same verified XD patch plan used by Create, without publishing it."""
    progress = progress or (lambda percent, message: None)
    cancel = cancel or threading.Event()
    seed = validate_seed(seed)
    source = Path(source).expanduser().resolve()
    extension = source.suffix.lower()
    if extension not in (".iso", ".rvz") or not source.is_file():
        raise service.UserError("Sélectionnez un fichier ISO ou RVZ existant.")
    rvz = extension == ".rvz"
    if rvz and (dolphin_tool is None or not Path(dolphin_tool).is_file()):
        raise service.RVZToolRequired("Pour utiliser le format RVZ, sélectionnez DolphinTool dans votre installation de Dolphin.")
    service.checkpoint(cancel)
    if not rvz:
        service.check_header(source, is_xd=True)
    progress(0, "Vérification de la ROM d’origine…")
    digest = service.file_hash(source, cancel)
    with (PreviewCache() if cache is None else nullcontext(cache)) as selected:
        if not rvz:
            selected.invalidate()
        lease = (selected.lease(source, digest, Path(dolphin_tool), progress, cancel)
                 if rvz else nullcontext(PreviewInput(source, digest, False)))
        with lease as image:
            boot = service.check_header(image.iso, is_xd=True)
            region = service.check_disc_identity(boot, image.iso_hash, is_xd=True)
            if roulette is not None:
                try:
                    roulette(extract_portraits(image.iso, ROULETTE_SPECIES, is_xd=True))
                except ArtworkError:
                    pass
                service.checkpoint(cancel)
            progress(20, "Application des réglages…")
            patches, summary = service.build_xd_patches(image.iso, boot, seed, xd_options, progress, cancel,
                                                  include_details=True)
            prepared = service.PreparedPatches(source=source, source_sha256=digest, iso_sha256=image.iso_hash,
                seed=seed, options=xd_options, patches=tuple(patches),
                summary=deepcopy({key: value for key, value in summary.items() if key != 'detail_catalog'}))
            if catalog := summary.pop("detail_catalog", None):
                starter = summary["starter"]
                shadows = summary["decks"]["Story"]["shadows"]
                rows = [starter, *shadows, *summary["gifts"], *summary["poke_spots"]]
                requests = []
                for row in rows:
                    details = encounter_details(catalog, row["species"], level=row.get("level"),
                                                moves=row.get("moves"), shadow="shadow_id" in row)
                    row["details"] = details
                    chain = (row["species"], *(step["target_species"] for step in details["evolution_chain"]))
                    requests.append((row, chain))
                progress(65, "Lecture des portraits…")
                for shiny in (False, True):
                    selected_rows = [(row, chain) for row, chain in requests if bool(row.get("shiny")) == shiny]
                    indices = tuple(dict.fromkeys(index for _, chain in selected_rows for index in chain))
                    portraits = {}
                    for start in range(0, len(indices), 64):
                        service.checkpoint(cancel)
                        try:
                            portraits.update(extract_portraits(image.iso, indices[start:start + 64],
                                                              shiny=shiny, is_xd=True))
                        except ArtworkError:
                            continue
                    for row, chain in selected_rows:
                        row["portrait_png"] = portraits.get(row["species"], b"")
                        row["evolution_portraits"] = {str(index): portraits[index] for index in chain if index in portraits}
            if service.file_hash(source, cancel) != digest:
                raise service.UserError("La ROM a changé pendant l’aperçu. Relancez-le avec une copie intacte.")
    if on_prepared is not None:
        service.checkpoint(cancel)
        on_prepared(prepared)
    return dict(summary, seed=seed, game_id=region.game_id, revision=region.revision, engine_version=XD_VERSION)
