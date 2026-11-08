"""Local disc pipeline. Inputs are read-only; destinations are never replaced."""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields, replace
from functools import wraps
import configparser
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import threading
import time
from typing import Callable, Sequence

from . import __version__
from .engine.analyze_game import FormatError, parse_fsys, sha256, u32
from .engine.evolution_rules import evolution_families, patch_evolutions
from .engine.inspect_tables import localized_names, u16
from .engine.randomize_accessible import (MOON_STONE_PRICE_OFFSET,
                                         randomize_accessible_rel)
from .engine.randomize_story import DOL_SHA256, SPECIALS, experience_at_level, randomize_specials
from .engine.randomize_trainers import layout, randomize_rel, validate_changes
from .engine.rebuild_iso import align, decoded_member, repack_fsys
from .engine.shop_stones import ARCHIVE_NAMES
from .engine.survey_assets import fst_inventory
from .engine.gameplay_rules import VERSION as GAMEPLAY_VERSION, apply_rel_rules, apply_dol_rules, apply_story_rules
from .engine.species_rules import species_catalog
from .engine.tm_rules import apply_tm_rules
from .engine.boss_rules import apply_boss_rules
from .engine.trainer_policies import apply_trainer_policies
from .engine.shiny_rules import apply_shiny_rules
from .engine.item_rules import apply_field_items, patch_item_archive
from .engine.item_text import apply_item_name_spacing
from .engine.event_gifts import ARCHIVE_NAMES as EVENT_GIFT_ARCHIVES, patch_event_archive
from .engine.colo_trainer_dialogue import TRAINER_REMARK_REWRITES, trainer_dialogue_edits
from .engine.gafar_dialogue import ARCHIVE_NAME as GAFAR_DIALOGUE_ARCHIVE, patch_gafar_dialogue
from .engine.message_bank import patch_species_archive
from .engine.shadow_dialogue import SHADOW_REMARK_REWRITES, shadow_dialogue_edits
from .engine.hooh_reward import patch_hooh_reward_scene
from .engine.colo_spinda import colo_spinda_gift_pid, colo_spinda_seeds, colo_spinda_trainer_pid
from .engine.colo_spinda_field import apply_colo_spinda_starters
from .engine.colo_unown import patch_unown_form
from .engine.dna_lab import dna_appearances, dna_room_updates, dna_spinda_samples, patch_dna_analyzer
from .engine.dna_keypad_runtime import apply_dna_keypad_runtime
from .engine.unown_form import unown_form
from .engine.eagun_scene import patch_eagun_scenes
from .engine.starter_arrival import ARRIVAL_ARCHIVE, patch_starter_arrival
from .engine.plusle_actor import ACTOR_ARCHIVES, OVERSIZED_FIELD_SPECIES, companion_scale, load_actor_model, patch_actor
from .engine.miror_scene import MIROR_CAVE, patch_cave_dancers, synchronize_cave_team
from .engine.plusle_dialogue import ARCHIVE_NAMES as PLUSLE_DIALOGUE_ARCHIVES, patch_dialogue
from .engine.qol_rules import apply_qol_rules
from .pokemon_details import build_detail_catalog
from .journal import render_journal
from .engine.regions import region_for_boot, validate_disc_hash
from .engine.dol_regions import dol_layout, special_targets
from .engine.rel_regions import region_for_rel, shop_archive_names
from .locales.selection_names import SPECIES_NAMES
from .native_codec import backend, cancellation_scope, CodecCancelled
from .options import Options, SPECIAL_OPTIONS
from .i18n import Message, LANGUAGES
from . import xd

ISO_SIZE = 1_459_978_240
ISO_SHA256 = "1e3b4aa806ac3367cca13496f7701137e9437e7bac0101f75b9b137633a10aa9"
DOL_SIZE = 4_096_576
CHUNK = 8 * 1024 * 1024
Progress = Callable[[int, str], None]
ENGINE_VERSION = "story-field-placement-v20"


@dataclass(frozen=True, slots=True)
class PreparedPatches:
    """A verified preview's in-memory plan, never loaded from a profile or disk."""
    source: Path
    source_sha256: str
    iso_sha256: str
    seed: str
    options: Options | xd.XDOptions
    patches: tuple[tuple[int, bytes], ...]
    summary: dict

    def matches(self, source: Path, source_sha256: str, iso_sha256: str, seed: str, options: Options | xd.XDOptions) -> bool:
        return (self.source, self.source_sha256, self.iso_sha256, self.seed, self.options) == (
            source, source_sha256, iso_sha256, seed, options)


class UserError(Exception):
    """A recoverable error suitable for display without a traceback."""

    def __init__(self, message: str, **parameters):
        super().__init__(Message(message, **parameters))


class Cancelled(UserError):
    pass


class RVZToolRequired(UserError):
    """The paths are valid, but RVZ conversion still needs DolphinTool."""


def validate_setting_values(options):
    normalized = {}
    for item in fields(options):
        value = getattr(options, item.name)
        kind = item.metadata["kind"]
        if item.metadata.get("selector") == "species" and value == -1:
            raise UserError("Choisissez un Pokémon de la liste pour {label}.", label=Message(item.metadata["label"]))
        if kind == "bool" and type(value) is not bool:
            raise UserError("Le réglage {label} doit être activé ou désactivé.", label=Message(item.metadata["label"]))
        if kind == "choice" and (type(value) is not str or value not in {choice[0] for choice in item.metadata["choices"]}):
            raise UserError("Choix inconnu : {label}.", label=Message(item.metadata["label"]))
        if kind in ("int", "float") and (type(value) not in (int, float) or
             kind == "int" and type(value) is not int or not item.metadata["minimum"] <= value <= item.metadata["maximum"]):
            raise UserError("Valeur hors limites : {label}.", label=Message(item.metadata["label"]))
        if kind in ("species_set", "type_set"):
            allowed = set(range(1, 387)) if kind == "species_set" else set(range(18)) - {9}
            if not isinstance(value, (list, tuple)) or any(type(i) is not int or i not in allowed for i in value):
                raise UserError("Liste d’exclusions invalide : {label}.", label=Message(item.metadata["label"]))
            normalized[item.name] = tuple(sorted(set(value)))
    return replace(options, **normalized)


def validate_options(options: Options) -> Options:
    options = validate_setting_values(options)
    if (options.randomize_trainers or options.randomize_shadows or options.boss_team_variety or options.trainer_force_evolved or any(getattr(options, name) for name in SPECIAL_OPTIONS.values())) and not any((options.allow_gen1, options.allow_gen2, options.allow_gen3)):
        raise UserError("Activez au moins une génération dans « Pokémon autorisés ».")
    if options.evolution_groups & {"trade_items", "coquiperl", "day_night"} and not options.stone_shops:
        raise UserError("Activez la vente de pierres dans « Boutiques », ou désactivez les évolutions par pierre.")
    if options.randomize_shadows and options.boss_shadow_legendary_mode == "preserve" and not options.allow_legendaries:
        raise UserError("Pour garder le statut légendaire des obscurs de boss, autorisez les légendaires dans « Pokémon autorisés ».")
    return replace(options, unique_shadows=False) if not options.randomize_shadows else options


def checkpoint(cancel: threading.Event) -> None:
    if cancel.is_set():
        raise Cancelled("Création annulée. Aucun fichier de sortie n'a été conservé.")


def file_hash(path: Path, cancel: threading.Event, progress: Progress | None = None,
              start: int = 0, end: int = 0, label: str = "") -> str:
    digest, done, size = hashlib.sha256(), 0, path.stat().st_size
    with path.open("rb") as stream:
        while data := stream.read(CHUNK):
            checkpoint(cancel)
            digest.update(data)
            done += len(data)
            if progress:
                progress(start + int((end - start) * done / max(size, 1)), label)
    checkpoint(cancel)
    return digest.hexdigest()


def find_dolphin_tool() -> Path | None:
    """Discover an existing tool, without installing or distributing Dolphin."""
    import sys
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
    for name in ("DolphinTool.exe", "DolphinTool", "Dolphin-x64/DolphinTool.exe"):
        if (base / name).is_file():
            return base / name
    found = shutil.which("DolphinTool") or shutil.which("DolphinTool.exe")
    return Path(found) if found else None


def validate_paths(source: Path, destination: Path, seed: str,
                   dolphin_tool: Path | None) -> tuple[Path, Path, Path]:
    source, destination = source.expanduser().resolve(), destination.expanduser().resolve()
    report = destination.with_suffix(destination.suffix + ".json")
    if not source.is_file() or source.suffix.lower() not in (".iso", ".rvz"):
        raise UserError("Sélectionnez un fichier ISO ou RVZ existant.")
    if destination.suffix.lower() not in (".iso", ".rvz"):
        raise UserError("Enregistrez la nouvelle ROM au format .iso ou .rvz.")
    if source == destination or (destination.exists() and os.path.samefile(source, destination)):
        raise UserError("Choisissez un autre fichier de sortie pour conserver la ROM d’origine.")
    if os.path.lexists(destination) or os.path.lexists(report) or os.path.lexists(destination.with_suffix(destination.suffix + ".html")):
        raise UserError("Ce nom est déjà utilisé par une ROM ou un rapport. Choisissez-en un autre.")
    if not destination.parent.is_dir():
        raise UserError("Le dossier de sortie n’existe pas. Choisissez un dossier existant.")
    if not seed.strip() or len(seed.encode("utf-8")) > 256:
        raise UserError("Saisissez une seed de 1 à 256 octets UTF-8.")
    if ".rvz" in (source.suffix.lower(), destination.suffix.lower()):
        if dolphin_tool is None or not dolphin_tool.is_file():
            raise RVZToolRequired("Pour utiliser le format RVZ, sélectionnez DolphinTool dans votre installation de Dolphin.")
    return source, destination, report


def convert(tool: Path, source: Path, destination: Path, work: Path,
            cancel: threading.Event) -> None:
    """Run unattended conversion using only this job's temporary Dolphin profile.

    Disable modal panic dialogs, while retaining exit-code/output checks here
    and the pipeline's full-byte and RVZ roundtrip verification.
    """
    checkpoint(cancel)
    user = work / "dolphin-user"
    config_path = user / "Config" / "Dolphin.ini"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config = configparser.ConfigParser(interpolation=None)
    config.optionxform = str
    config.read(config_path, encoding="utf-8-sig")
    if not config.has_section("Interface"):
        config.add_section("Interface")
    config.set("Interface", "UsePanicHandlers", "False")
    with config_path.open("w", encoding="utf-8") as settings:
        config.write(settings)
    args = [str(tool.resolve()), "convert", "-i", str(source), "-o", str(destination),
            "-f", destination.suffix[1:].lower(), "-u", str(user)]
    if destination.suffix.lower() == ".rvz":
        args += ["-b", "131072", "-c", "zstd", "-l", "5"]
    checkpoint(cancel)
    with (work / "conversion.log").open("wb") as log:
        process = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        deadline = time.monotonic() + 1800
        try:
            while process.poll() is None:
                checkpoint(cancel)
                if time.monotonic() > deadline:
                    raise UserError("La conversion RVZ a dépassé 30 minutes. Vérifiez DolphinTool et l'espace libre.")
                cancel.wait(0.15)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
    checkpoint(cancel)
    if process.returncode or not destination.is_file():
        raise UserError("La conversion a échoué. Vérifiez la ROM et le fonctionnement de DolphinTool.")


def read_exact(stream, offset: int, size: int) -> bytes:
    if offset < 0 or size < 0 or offset + size > ISO_SIZE:
        raise FormatError("disc range outside supported ISO")
    stream.seek(offset)
    data = stream.read(size)
    if len(data) != size:
        raise FormatError("truncated disc range")
    return data


def check_header(path: Path, *, is_xd: bool = False) -> bytes:
    with path.open("rb") as stream:
        boot = stream.read(0x440)
    try:
        if path.stat().st_size != ISO_SIZE:
            raise FormatError("invalid disc size")
        (xd.region_for_boot if is_xd else region_for_boot)(boot)
    except FormatError:
        if is_xd:
            raise UserError("ROM non prise en charge. Utilisez Pokémon XD Europe, USA ou Japon (révision 0), complet et sans modification.") from None
        raise UserError("ROM non prise en charge. Utilisez Colosseum Europe, USA ou Japon (révision 0), complet et sans modification.") from None
    return boot


def check_disc_identity(boot: bytes, digest: str, *, is_xd: bool = False):
    try:
        if is_xd:
            region = xd.region_for_boot(boot)
            if digest != region.iso_sha256:
                raise FormatError("disc differs from the exact validated XD revision")
            return region
        return validate_disc_hash(boot, digest)
    except FormatError:
        if is_xd:
            raise UserError("Cette ROM ne correspond pas à une version prise en charge de Pokémon XD. Utilisez une copie complète et non modifiée.") from None
        raise UserError("Cette ROM ne correspond pas à une version prise en charge. Utilisez une copie complète et non modifiée de Colosseum Europe, USA ou Japon.") from None


def transform_rel(original: bytes, seed: str, options: Options) -> tuple[bytes, dict]:
    if options.unique_shadows and options.randomize_shadows:
        payload, full = randomize_accessible_rel(original, seed)
        trainers = copy.deepcopy(full["trainers"])
        shadow_families = full["shadow_families"]
        # Keep trainer draws from v3, then apply only the requested evolution groups.
        output = bytearray(payload)
        for edit in full["evolutions"]["edits"]:
            pos = edit["record_offset"]
            output[pos:pos + 6] = original[pos:pos + 6]
    else:
        payload, trainers = randomize_rel(original, seed)
        output, shadow_families = bytearray(payload), None
    kept = []
    for change in trainers["trainer_pokemon_changes"]:
        selected = options.randomize_shadows if change["shadow_id"] else options.randomize_trainers
        if selected:
            kept.append(change)
        else:
            pos = change["offset"]
            output[pos:pos + 80] = original[pos:pos + 80]
    trainers["trainer_pokemon_changes"] = kept
    if not options.randomize_shadows:
        for change in trainers["shadow_changes"]:
            pos = change["offset"]
            output[pos:pos + 2] = original[pos:pos + 2]
        trainers["shadow_changes"] = []
    summary = dict(trainers["summary"])
    summary.update(trainer_pokemon_records_changed=len(kept),
                   trainers_with_changed_slots=len({t for c in kept for t in c["referencing_trainers"]}),
                   shared_trainer_slots=sum(len(c["referencing_trainers"]) > 1 for c in kept),
                   shadow_groups_changed=len(trainers["shadow_changes"]),
                   shadow_trainer_slots_changed=sum(bool(c["shadow_id"]) for c in kept),
                   ability_selectors_normalized=sum(c["old_ability_selector"] != c["new_ability_selector"] for c in kept))
    if kept:
        summary.update(validate_changes(original, bytes(output), trainers))
    else:
        if output != original:
            raise FormatError("disabled trainer rules changed original bytes")
        summary.update(changed_rel_bytes=0, only_authorized_fields_changed=True, shadow_species_consistent=True)
    evolved, evolution_plan = patch_evolutions(original, layout(original)[0], options.evolution_groups)
    for edit in evolution_plan["edits"]:
        pos = edit["record_offset"]
        output[pos:pos + 6] = evolved[pos:pos + 6]
    return bytes(output), {"trainers": summary, "shadow_families": shadow_families,
                           "evolution_edits": len(evolution_plan["edits"]),
                           "stone_shops": list(options.stone_shops)}


def transform_dol(original: bytes, rel: bytes, seed: str, options: Options) -> tuple[bytes, list[dict]]:
    executable = dol_layout(original)
    output, changes = bytearray(original), []
    if any(getattr(options, name) for name in SPECIAL_OPTIONS.values()):
        modified, plan = randomize_specials(original, rel, seed)
        for change in plan["special_changes"]:
            if getattr(options, SPECIAL_OPTIONS[change["key"]]):
                for field in ("species_field_offset", "exp_field_offset"):
                    if field in change:
                        pos = change[field]
                        output[pos:pos + 2] = modified[pos:pos + 2]
                changes.append(change)
    if options.stone_shops:
        pos = executable.moon_stone_price_offset
        if u16(original, pos) != 0:
            raise FormatError("unexpected original Moon Stone price")
        struct.pack_into(">H", output, pos, 2100)
    return bytes(output), changes


def final_report_summary(original_rel: bytes, base_rel: bytes, rel: bytes,
                         original_dol: bytes, dol: bytes, seed: str,
                         options: Options, summary: dict) -> dict:
    """Describe final bytes, without changing them or replaying any random draw.

    The legacy transformer runs before pool filtering and power balancing. Its
    intermediate species, names and EXP cannot be exposed as the final result.
    Keep legacy report shapes where their provenance still applies, and label
    the base of advanced shadow rerolls explicitly rather than retaining stale
    v3 collision-resolution records.
    """
    result = copy.deepcopy(summary)
    tables, symbols = layout(original_rel)
    names, _ = localized_names(rel, symbols)
    catalog = species_catalog(rel, tables)

    def species(index: int) -> dict:
        if index not in catalog:
            raise FormatError("final report references an invalid species")
        row = catalog[index]
        name_id = u32(rel, row["offset"] + 0x18)
        result = {"national_dex": row["national_dex"], "growth_group": rel[row["offset"]]}
        for language, tag in (("fr", "FR"), ("en", "UK"), ("de", "GE"),
                              ("es", "SP"), ("it", "IT"), ("ja", "JP")):
            native = names.get(tag, {}).get(name_id)
            if language == "en" and not native:
                native = names.get("US", {}).get(name_id)
            # Interface names remain available in every UI language even when
            # a single-language ROM has no corresponding native text bank.
            result["name_" + language] = native or SPECIES_NAMES[language][row["national_dex"]]
        return result

    final_specials = {}
    targets = special_targets(original_dol)
    for target in targets:
        pos = target["base"]
        index, level = u16(dol, pos + 2), u16(dol, pos + 6)
        row = {"species": index, "level": level, **species(index),
               "original_species": target["old"], "original": species(target["old"])}
        if "xp" in target:
            row["experience"] = u16(dol, pos + 0x92)
        final_specials[target["key"]] = row
    for row in result.get("special_changes", []):
        final = final_specials[row["key"]]
        row.update(new_species_index=final["species"], new_species_fr=final["name_fr"],
                   new_national_dex=final["national_dex"],
                   growth_group=final["growth_group"])
        original_level = u16(original_dol, next(t["base"] for t in targets if t["key"] == row["key"]) + 6)
        if final["level"] == original_level:
            row["level_preserved"] = final["level"]
        else:
            row.pop("level_preserved", None)
            row.update(original_level=original_level, level=final["level"], level_changed=True)
        if "exp_field_offset" in row:
            row["old_exp"] = u16(original_dol, row["exp_field_offset"])
            row["new_exp"] = u16(dol, row["exp_field_offset"])
            row["exp_policy"] = (
                "threshold of preserved level, zero progress to next level"
                if row["new_exp"] == experience_at_level(final["growth_group"], final["level"])
                else "observed final DOL EXP override")
    for row in result.get("special_gameplay", {}).get("specials", []):
        row.update(final_specials[row["key"]])

    gameplay = result.get("gameplay", {})
    for row in gameplay.get("trainer_move_edits", []):
        pos = tables["trainer_pokemon"]["offset"] + row["index"] * tables["trainer_pokemon"]["stride"]
        row.update(species=u16(rel, pos + 0xA), level=rel[pos + 4],
                   after=[u16(rel, pos + field) for field in (0x36, 0x3E, 0x46, 0x4E)])
    for row in gameplay.get("trainer_level_edits", []):
        pos = tables["trainer_pokemon"]["offset"] + row["index"] * tables["trainer_pokemon"]["stride"]
        row["after"] = rel[pos + 4]
    if gameplay:
        gameplay["values_scope"] = "final REL after boss and trainer policies; each edit list retains its feature's original selection"
    for row in result.get("bosses", {}).get("edits", []):
        pos = row["offset"]
        row.update(new_species_index=u16(rel, pos + 0xA), level_after=rel[pos + 4],
                   moves_after=[u16(rel, pos + field) for field in (0x36, 0x3E, 0x46, 0x4E)],
                   **species(u16(rel, pos + 0xA)))

    family_by_species, families = evolution_families(original_rel, tables)
    shadow = tables["shadow"]
    final_picks, changed, retained = [], [], []
    for sid in range(1, shadow["count"]):
        pos = shadow["offset"] + sid * shadow["stride"] + 2
        old = u16(original_rel, pos)
        if not old:
            continue
        base, final = u16(base_rel, pos), u16(rel, pos)
        metadata = species(final)
        final_picks.append({"shadow_id": sid, "species_index": final,
                            **metadata, "original_species": old, "original": species(old),
                            "species_fr": metadata["name_fr"],
                            "family": family_by_species[final]})
        if final == base:
            retained.append(sid)
        else:
            changed.append({"shadow_id": sid,
                            "key": f"{GAMEPLAY_VERSION}:species:shadow:{sid}",
                            "old_species_index": old, "base_species_index": base,
                            "new_species_index": final,
                            "base_family": family_by_species[base],
                            "new_family": family_by_species[final]})
    result["final_shadow_picks"] = final_picks
    report = result.get("shadow_families")
    if report is not None:
        report["shadow_group_count"] = len(final_picks)
        report["final_distinct_family_count"] = len({row["family"] for row in final_picks})
        report["final_picks"] = copy.deepcopy(final_picks)
        if changed:
            report.update(version="shadow-family-final-v5", seed=seed,
                          source_rel_sha256=sha256(original_rel),
                          base_pick_source="REL immediately before advanced gameplay rules",
                          available_family_count=len(families),
                          available_family_count_scope="all original REL families before selection filters",
                          base_distinct_family_count=len({
                              family_by_species[u16(base_rel, shadow["offset"] + row["shadow_id"] * shadow["stride"] + 2)]
                              for row in final_picks}),
                          retained_shadow_ids=retained,
                          rerolled_shadow_ids=[row["shadow_id"] for row in changed],
                          rerolls=changed,
                          all_evolution_stages_eligible=True,
                          evolution_stage_eligibility_scope="within configured species filters and per-encounter power window",
                          species_filters={name: getattr(options, name) for name in (
                              "allow_gen1", "allow_gen2", "allow_gen3", "allow_legendaries", "balance_species")})
    return result


def _cancellable_compression(function):
    @wraps(function)
    def run(iso, boot, seed, options, progress, cancel, **kwargs):
        try:
            with cancellation_scope(cancel):
                return function(iso, boot, seed, options, progress, cancel, **kwargs)
        except CodecCancelled as error:
            raise Cancelled("Création annulée. Aucun fichier de sortie n'a été conservé.") from error
    return run


build_xd_patches = _cancellable_compression(xd.build_patches)


@_cancellable_compression
def build_patches(iso: Path, boot: bytes, seed: str, options: Options,
                  progress: Progress, cancel: threading.Event) -> tuple[list[tuple[int, bytes]], dict]:
    """Rebuild only known archives in the same safe gap used by the validated v3."""
    fst_offset, fst_size, fst_max = (u32(boot, p) for p in (0x424, 0x428, 0x42C))
    dol_offset = u32(boot, 0x420)
    region = region_for_boot(boot)
    dol_size = region.dol_size
    with iso.open("rb") as stream:
        original_fst = read_exact(stream, fst_offset, fst_size)
        fst = bytearray(original_fst)
        entries, _ = fst_inventory(fst)
        if any(e["disc_offset"] < 0 or e["disc_offset"] + e["size"] > ISO_SIZE for e in entries):
            raise FormatError("file exceeds disc bounds")
        by_name = {e["path"]: e for e in entries}
        def archive(name: str) -> bytes:
            entry = by_name[name]
            return read_exact(stream, entry["disc_offset"], entry["size"])
        common = archive("common.fsys")
        members = [m for m in parse_fsys(common)["members"] if m["name"] == "common_rel"]
        if len(members) != 1:
            raise FormatError("expected exactly one common_rel")
        member = members[0]
        original = decoded_member(common, member)
        if region_for_rel(original).game_id != region.game_id:
            raise FormatError("common REL region does not match the disc header")
        progress(20, "Application des réglages…")
        base_rel, summary = transform_rel(original, seed, options)
        original_dol = read_exact(stream, dol_offset, dol_size)
        if dol_layout(original_dol).game_id != region.game_id:
            raise FormatError("DOL region does not match the disc header")
        dol, summary["special_changes"] = transform_dol(original_dol, original, seed, options)
        starter_result, gift_picks = None, None
        if options.diverse_story_families:
            rel, summary["gameplay"], starter_result, gift_picks = apply_story_rules(
                original, base_rel, original_dol, dol, seed, options)
        else:
            rel, summary["gameplay"] = apply_rel_rules(original, base_rel, seed, options)
        checkpoint(cancel)
        rel, summary["bosses"] = apply_boss_rules(original, rel, seed, options)
        rel, summary["trainer_policies"] = apply_trainer_policies(original, rel, seed, options)
        dancers, dancer_slots = (), ()
        if options.randomize_trainers:
            rel, dancers, dancer_slots = synchronize_cave_team(original, rel)
        rel, summary["field_items"] = apply_field_items(original, rel, original_dol, seed, options)
        dol, summary["special_gameplay"] = apply_dol_rules(
            original_dol, dol, original, rel, seed, options, starter_result=starter_result, gift_picks=gift_picks)
        rel, dol, summary["tms"] = apply_tm_rules(original, rel, original_dol, dol, seed, options)
        spinda_seeds = colo_spinda_seeds(original, rel, original_dol, dol, seed, dancer_slots) if options.has_changes else {}
        dol, shiny_report = apply_shiny_rules(original_dol, dol, options, seed=seed,
                                              trainer_aliases=dancer_slots, spinda_seeds=spinda_seeds)
        summary["shinies"] = shiny_report
        dol, summary["quality_of_life"] = apply_qol_rules(original_dol, dol, options)
        if options.readable_stone_names:
            rel, summary["item_names"] = apply_item_name_spacing(original, rel)
        else:
            summary["item_names"] = {"enabled": False, "changed_names": 0}
        if options.gift_hooh or options.custom_shinies:
            dol, rel, summary["hooh_reward_scene"] = patch_hooh_reward_scene(
                original_dol, dol, original, rel, sync_native_gift=options.custom_shinies)
        lab_appearances = dna_appearances(original, rel, options, shiny_report)
        samples = {}
        if lab_appearances:
            samples = dna_spinda_samples(original, rel, lab_appearances, options, shiny_report)
            dol = patch_dna_analyzer(original_dol, dol, lab_appearances, spinda_samples=samples,
                                     spinda_pid=shiny_report.get("spinda_pid"))
        form = unown_form(seed)
        if options.has_changes:
            dol = patch_unown_form(original_dol, dol, form)
            summary["unown_form"] = form
        decisions = shiny_report.get("seeded_decisions", {})
        guaranteed_shiny = options.custom_shinies and options.shiny_chance_percent == 100
        spinda_default = (None if options.custom_shinies and not options.seeded_shinies
                          and options.shiny_chance_percent not in (0, 100) else guaranteed_shiny)
        arrival = patch_starter_arrival(original_dol, dol, original, archive,
                                        decisions.get("specials", {}), guaranteed_shiny, unown_form_index=form,
                                        spinda_seeds=spinda_seeds, spinda_default=spinda_default)
        if arrival and any(row.get("spinda_live_pid") for row in arrival[1]):
            dol = apply_colo_spinda_starters(original_dol, dol, shiny_report["spinda_pid"]["resolver"], archive)
        if samples:
            dol = apply_dna_keypad_runtime(original_dol, dol, archive, samples, shiny_report["spinda_pid"])
        summary = final_report_summary(original, base_rel, rel, original_dol, dol, seed, options, summary)
        if lab_appearances:
            summary["dna_lab"] = {
                str(old): {"species": species, "shiny": shiny}
                for old, (species, shiny) in lab_appearances.items()
            }
        if options.diverse_story_families:
            families = evolution_families(original, layout(original)[0])[0]
            members = {}
            for row in summary["special_gameplay"]["specials"]:
                members.setdefault(families[row["species"]], []).append(row["key"])
            for row in summary["final_shadow_picks"]:
                members.setdefault(row["family"], []).append(f"shadow:{row['shadow_id']}")
            summary["story_families"] = {"distinct_family_count": len(members),
                                         "duplicates": [group for group in members.values() if len(group) > 1]}
        summary["detail_catalog"] = build_detail_catalog(original, rel, original_dol, dol, summary=summary)
        progress(25, "Compression des données du jeu…")
        new_common = repack_fsys(common, {member["index"]: rel})[0] if rel != original else common
        checkpoint(cancel)
        old = by_name["common.fsys"]
        next_offset = min((e["disc_offset"] for e in entries if e["disc_offset"] > old["disc_offset"]), default=ISO_SIZE)
        app_header = read_exact(stream, 0x2440, 0x20)
        app_size = 0x20 + u32(app_header, 0x14) + u32(app_header, 0x18)
        sys_end = max(fst_offset + max(fst_size, fst_max), dol_offset + dol_size, 0x2440 + app_size)
        original_dol_offset = dol_offset
        if len(dol) != dol_size:
            # The original DOL can directly precede the FST. Relocate the whole
            # extended DOL, preserving that FST and every original system byte.
            dol_offset = align(sys_end, 0x8000)
            sys_end = dol_offset + len(dol)
            if sys_end > min(e["disc_offset"] for e in entries):
                raise FormatError("no safe gap for extended DOL")
            summary["dol_relocated"] = {"old_offset": original_dol_offset, "new_offset": dol_offset,
                                        "old_size": dol_size, "new_size": len(dol)}
        relocated = len(new_common) > next_offset - old["disc_offset"]
        common_offset = align(sys_end, 0x8000) if relocated else old["disc_offset"]
        first_file = min(e["disc_offset"] for e in entries)
        if relocated and common_offset + len(new_common) > first_file:
            raise FormatError("no safe gap for common archive")
        patches = []
        if dol_offset != original_dol_offset:
            patches.append((0x420, struct.pack(">I", dol_offset)))
        if dol != original_dol:
            patches.append((dol_offset, dol))
        if new_common != common:
            patches.append((common_offset, new_common))
        struct.pack_into(">II", fst, old["index"] * 12 + 4, common_offset, len(new_common))
        cursor = align(common_offset + len(new_common) if relocated else sys_end, 0x8000)
        scene_updates = (dna_room_updates(original, region.game_id, archive, lab_appearances,
                                          unown_form_index=form, spinda_samples=samples) if lab_appearances else {})
        if options.stone_shops or options.randomize_shop_items:
            summary["shop_archives"] = []
            shop_archives = shop_archive_names(original)
            for i, name in enumerate(sorted(shop_archives)):
                progress(30 + int(i * 24 / len(shop_archives)), Message("Boutiques : étape {number}/{total}…", number=i + 1, total=len(shop_archives)))
                source = scene_updates.pop(name) if name in scene_updates else archive(name)
                payload, shop_report = patch_item_archive(source, original_dol, seed, options)
                summary["shop_archives"].append({"archive": name, **shop_report})
                checkpoint(cancel)
                if cursor + len(payload) > first_file:
                    raise FormatError("no safe gap for shop archive")
                patches.append((cursor, payload))
                struct.pack_into(">II", fst, by_name[name]["index"] * 12 + 4, cursor, len(payload))
                cursor = align(cursor + len(payload), 0x8000)
        summary["event_gifts"] = {"enabled": options.accessible_event_gifts, "archives": []}
        if options.accessible_event_gifts:
            for i, name in enumerate(EVENT_GIFT_ARCHIVES):
                progress(54 + i * 2, "Application des réglages…")
                payload, event_report = patch_event_archive(archive(name), name, options, region=region.game_id)
                checkpoint(cancel)
                scene_updates[name] = payload
                summary["event_gifts"]["archives"].append({"archive": name, **event_report})
        if arrival is not None:
            scene_updates[ARRIVAL_ARCHIVE], summary["starter_arrival"] = arrival
        trainer_shinies = decisions.get("trainer_slots", {})
        if options.randomize_trainers or options.custom_shinies:
            partner = patch_eagun_scenes(original, rel, original_dol, region.game_id, archive,
                                          scene_updates, trainer_shinies, guaranteed_shiny, unown_form_index=form,
                                          spinda_seeds=spinda_seeds, spinda_default=spinda_default)
            if partner is not None:
                summary["eagun_field_partner"] = partner
                for report in summary["event_gifts"]["archives"]:
                    if report["archive"] in partner["archives"]:
                        report["after_sha256"] = sha256(scene_updates[report["archive"]])
        shiny_dancers = tuple(trainer_shinies.get(str(slot), guaranteed_shiny) for slot, _ in dancer_slots)
        if dancers and (any(species != 297 for species in dancers) or any(shiny_dancers)):
            dancer_pids = tuple(
                colo_spinda_trainer_pid(original, rel, spinda_seeds, slot, mode) if mode is not None else None
                for slot, mode in ((slot, trainer_shinies.get(str(slot), spinda_default)) for slot, _ in dancer_slots)
            )
            scene_updates[MIROR_CAVE] = patch_cave_dancers(
                archive(MIROR_CAVE), original_dol, region.game_id, dancers, shiny_dancers,
                layout(original)[0]["species"], rel, archive, unown_form_index=form, spinda_pids=dancer_pids,
            )
            summary["miror_cave_dancers"] = list(dancers)
            summary["miror_cave_shiny_models"] = list(shiny_dancers)
        if options.gift_plusle:
            gift = next(row for row in special_targets(original_dol) if row["key"] == "plusle")
            species_id = u16(dol, gift["base"] + 2)
            if species_id != gift["old"]:
                species = species_catalog(rel, layout(original)[0])[species_id]
                national_dex = species["national_dex"]
                model_id = u32(rel, species["offset"] + 0x2C)
                # The captive Pokémon has to fit behind the cage bars.
                scale = 0.5 * companion_scale(national_dex, 1.0) if national_dex in OVERSIZED_FIELD_SPECIES else 1.0
                shiny = decisions.get("specials", {}).get("plusle", guaranteed_shiny)
                spinda_mode = decisions.get("specials", {}).get("plusle", spinda_default)
                spinda_pid = (colo_spinda_gift_pid(spinda_seeds, "plusle", spinda_mode)
                              if spinda_mode is not None else None)
                model = load_actor_model(original_dol, region.game_id, model_id, archive, scale=scale, shiny=shiny,
                                         unown_form_index=form, spinda_pid=spinda_pid)
                for name in PLUSLE_DIALOGUE_ARCHIVES:
                    checkpoint(cancel)
                    room = scene_updates[name] if name in scene_updates else archive(name)
                    payload = patch_dialogue(room, name, region.game_id, national_dex, species_id=species_id)
                    if name in ACTOR_ARCHIVES:
                        payload = patch_actor(payload, model)
                    scene_updates[name] = payload
                summary["plusle_gift_scene"] = {"species": species_id, "national_dex": national_dex,
                    "actor_scale": scale, "shiny_model": shiny,
                    "actor_archives": list(ACTOR_ARCHIVES), "dialogue_archives": list(PLUSLE_DIALOGUE_ARCHIVES)}
        if options.randomize_trainers:
            checkpoint(cancel)
            name = GAFAR_DIALOGUE_ARCHIVE
            room = scene_updates[name] if name in scene_updates else archive(name)
            payload, species_ids = patch_gafar_dialogue(room, original, rel)
            if payload != room:
                scene_updates[name] = payload
                summary["gafar_dialogue"] = {"archive": name, "species": list(species_ids)}
        if options.randomize_trainers or options.randomize_types or options.randomize_trainer_moves:
            trainer_dialogue, native_names = trainer_dialogue_edits(
                original, rel, region.game_id, trainers_changed=options.randomize_trainers,
                types_changed=options.randomize_types, moves_changed=options.randomize_trainer_moves,
            )
            for name, messages in trainer_dialogue.items():
                checkpoint(cancel)
                room = scene_updates[name] if name in scene_updates else archive(name)
                scene_updates[name] = patch_species_archive(room, messages, native_names,
                                                           rewrites=TRAINER_REMARK_REWRITES)
            if trainer_dialogue:
                summary["trainer_dialogue"] = {name: sorted(messages) for name, messages in trainer_dialogue.items()}
        if rel != original:
            dialogue_edits, dialogue_names = shadow_dialogue_edits(original, rel, region.game_id)
            updated_dialogue = {}
            for name, messages in dialogue_edits.items():
                checkpoint(cancel)
                room = scene_updates[name] if name in scene_updates else archive(name)
                payload = patch_species_archive(room, messages, dialogue_names, rewrites=SHADOW_REMARK_REWRITES)
                if payload == room:
                    continue
                scene_updates[name] = payload
                updated_dialogue[name] = sorted(messages)
            if updated_dialogue:
                summary["shadow_dialogue"] = updated_dialogue
        for name, payload in scene_updates.items():
            checkpoint(cancel)
            if cursor + len(payload) > first_file:
                raise FormatError("no safe gap for Colosseum scene archive")
            patches.append((cursor, payload))
            struct.pack_into(">II", fst, by_name[name]["index"] * 12 + 4, cursor, len(payload))
            cursor = align(cursor + len(payload), 0x8000)
        if fst != original_fst:
            patches.append((fst_offset, bytes(fst)))
    patches.sort(key=lambda p: p[0])
    end = 0
    for offset, payload in patches:
        if offset < end or offset + len(payload) > ISO_SIZE:
            raise FormatError("overlapping or out-of-bounds disc patches")
        end = offset + len(payload)
    return patches, summary


def verify_patches(source: Path, output: Path, patches: Sequence[tuple[int, bytes]],
                   progress: Progress, cancel: threading.Event) -> str:
    """Compare every byte, masking only exact expected replacement payloads."""
    if output.stat().st_size != ISO_SIZE:
        raise FormatError("output ISO size changed")
    digest, position = hashlib.sha256(), 0
    with source.open("rb") as before, output.open("rb") as after:
        while original := before.read(CHUNK):
            checkpoint(cancel)
            actual = after.read(len(original))
            expected = bytearray(original)
            for offset, payload in patches:
                lo, hi = max(position, offset), min(position + len(original), offset + len(payload))
                if hi > lo:
                    expected[lo - position:hi - position] = payload[lo - offset:hi - offset]
            if actual != expected:
                raise FormatError(f"unexpected output data near disc offset {position:#x}")
            digest.update(actual)
            position += len(actual)
            progress(70 + int(12 * position / ISO_SIZE), "Vérification de la nouvelle ISO…")
    return digest.hexdigest()


def publish_new(source: Path, destination: Path) -> None:
    """Atomic no-clobber on NTFS; exclusive creation on non-hardlink filesystems."""
    try:
        os.link(source, destination)
        return
    except FileExistsError:
        raise UserError("Un autre programme vient de créer ce fichier. Choisissez un autre nom de sortie.") from None
    except OSError:
        pass
    # xb also refuses existing files/symlinks; never use os.replace on user files.
    created = False
    try:
        with source.open("rb") as stream, destination.open("xb") as out:
            created = True
            shutil.copyfileobj(stream, out, CHUNK)
            out.flush()
            os.fsync(out.fileno())
    except FileExistsError:
        raise UserError("Un autre programme vient de créer ce fichier. Choisissez un autre nom de sortie.") from None
    except BaseException:
        if created:
            destination.unlink(missing_ok=True)
        raise


def randomize(source: Path, destination: Path, seed: str, options: Options = Options(),
              dolphin_tool: Path | None = None, progress: Progress | None = None,
              cancel: threading.Event | None = None, *, journal_language: str = "fr",
              prepared_patches: PreparedPatches | None = None,
              xd_options: xd.XDOptions | None = None) -> dict:
    progress = progress or (lambda percent, message: None)
    cancel = cancel or threading.Event()
    is_xd = xd_options is not None
    if is_xd:
        xd_options = xd.validate_options(xd_options)
    else:
        options = validate_options(options)
    if journal_language not in LANGUAGES:
        raise ValueError("unsupported journal language")
    started = time.monotonic()
    timings = {}
    source, destination, report_path = validate_paths(source, destination, seed, dolphin_tool)
    journal_path = destination.with_suffix(destination.suffix + ".html")
    needed = ISO_SIZE * (1 + (source.suffix.lower() == ".rvz") + (destination.suffix.lower() == ".rvz") * 2) + 64 * 1024**2
    if shutil.disk_usage(destination.parent).free < needed:
        raise UserError("Espace disque insuffisant : il faut au moins {needed:.1f} Gio libres dans le dossier de sortie.", needed=needed / 1024**3)
    checkpoint(cancel)
    progress(0, "Lecture de la ROM d’origine…")
    if source.suffix.lower() == ".iso":
        check_header(source, is_xd=is_xd)
    source_hash = file_hash(source, cancel, progress, 0, 8, "Vérification de la ROM d’origine…")
    # TemporaryDirectory owns only a fresh random directory, under the selected parent.
    with tempfile.TemporaryDirectory(prefix=".orre-", dir=destination.parent) as temp:
        work = Path(temp)
        iso = source
        if source.suffix.lower() == ".rvz":
            progress(8, "Conversion RVZ → ISO avec DolphinTool…")
            iso = work / "source.iso"
            convert(dolphin_tool, source, iso, work, cancel)
        boot = check_header(iso, is_xd=is_xd)
        iso_hash = source_hash if iso == source else file_hash(iso, cancel, progress, 9, 18, "Vérification de l’ISO décompressée…")
        region = check_disc_identity(boot, iso_hash, is_xd=is_xd)
        timings["input_validation"] = round(time.monotonic() - started, 4)
        phase = time.monotonic()
        reused = prepared_patches is not None and prepared_patches.matches(
            source, source_hash, iso_hash, seed, xd_options if is_xd else options)
        if reused:
            checkpoint(cancel)
            progress(20, "Réutilisation du calcul de l’aperçu…")
            patches, summary = prepared_patches.patches, copy.deepcopy(prepared_patches.summary)
        elif is_xd:
            progress(20, "Application des réglages…")
            patches, summary = build_xd_patches(iso, boot, seed, xd_options, progress, cancel)
        else:
            patches, summary = build_patches(iso, boot, seed, options, progress, cancel)
        timings["transform_and_archives"] = round(time.monotonic() - phase, 4)
        phase = time.monotonic()
        pending_iso = work / "randomized.iso"
        progress(56, "Création de la nouvelle ISO…")
        with iso.open("rb") as stream, pending_iso.open("xb") as out:
            done = 0
            while data := stream.read(CHUNK):
                checkpoint(cancel)
                out.write(data)
                done += len(data)
                progress(56 + int(13 * done / ISO_SIZE), "Création de la nouvelle ISO…")
            for offset, payload in patches:
                checkpoint(cancel)
                out.seek(offset)
                out.write(payload)
            out.flush()
            os.fsync(out.fileno())
        timings["copy_and_patch"] = round(time.monotonic() - phase, 4)
        phase = time.monotonic()
        output_iso_hash = verify_patches(iso, pending_iso, patches, progress, cancel)
        timings["iso_verification"] = round(time.monotonic() - phase, 4)
        phase = time.monotonic()
        pending = pending_iso
        if destination.suffix.lower() == ".rvz":
            progress(83, "Compression de la nouvelle RVZ…")
            pending = work / "randomized.rvz"
            convert(dolphin_tool, pending_iso, pending, work, cancel)
            progress(86, "Vérification de la RVZ créée…")
            roundtrip = work / "roundtrip.iso"
            convert(dolphin_tool, pending, roundtrip, work, cancel)
            if file_hash(roundtrip, cancel) != output_iso_hash:
                raise FormatError("RVZ roundtrip changed output ISO bytes")
        output_hash = output_iso_hash if pending == pending_iso else file_hash(pending, cancel)
        if file_hash(source, cancel, progress, 90, 98, "Dernière vérification de la ROM d’origine…") != source_hash:
            raise UserError("La ROM d’origine a changé pendant la création. Aucune ROM n’a été enregistrée. Réessayez avec une copie intacte.")
        timings["rvz_and_source_verification"] = round(time.monotonic() - phase, 4)
        report = {"application_version": __version__, "engine_version": xd.VERSION if is_xd else ENGINE_VERSION,
                  "seed": seed, "options": asdict(xd_options if is_xd else options), "game_id": region.game_id, "revision": region.revision,
                  "source": str(source), "source_sha256": source_hash,
                  "source_iso_sha256": iso_hash, "output": str(destination),
                  "output_sha256": output_hash, "output_iso_sha256": output_iso_hash,
                  "source_unchanged": True, "all_output_iso_bytes_verified": True,
                  "rvz_roundtrip_verified": destination.suffix.lower() == ".rvz",
                  "preview_plan_reused": reused,
                  "summary": summary, "journal": str(journal_path), "journal_language": journal_language,
                  "elapsed_seconds": round(time.monotonic() - started, 2),
                  "codec": backend(), "stage_seconds": timings,
                  "runtime_validation": "Technical verification only; full playthrough and balance are not certified."}
        if is_xd:
            report["game"] = "xd"
        pending_report = work / "report.json"
        pending_journal = work / "journal.html"
        pending_journal.write_text(render_journal(report, journal_language), encoding="utf-8")
        pending_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        checkpoint(cancel)
        progress(99, "Enregistrement de la ROM et du rapport…")
        # Every name was checked before work; each commit independently refuses clobber.
        publish_new(pending_report, report_path)
        journal_published = False
        try:
            publish_new(pending_journal, journal_path)
            journal_published = True
            publish_new(pending, destination)
        except BaseException:
            if journal_published:
                journal_path.unlink(missing_ok=True)
            report_path.unlink(missing_ok=True)
            raise
    progress(100, "ROM créée et vérifiée.")
    return report
