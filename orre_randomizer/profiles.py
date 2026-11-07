"""Small, versioned configuration files; never include ROMs or local paths."""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields
import hashlib
import json
from pathlib import Path
import re

from . import __version__
from . import xd
from .options import Options
from .service import ENGINE_VERSION, ISO_SHA256, UserError, validate_options
from .engine.regions import REGIONS, Region

PROFILE_FORMAT = "colosseum-randomizer-profile"
XD_PROFILE_FORMAT = "pokemon-xd-randomizer-profile"
LEGACY_XD_ENGINE = "xd-story-sha256-v3"
PREVIOUS_XD_ENGINE = "xd-story-sha256-v4"
PREVIOUS_XD_QOL_ENGINE = "xd-story-sha256-v5"
PREVIOUS_XD_SHUFFLE_ENGINE = "xd-story-sha256-v6"
PREVIOUS_XD_FULL_SPOT_ENGINE = "xd-story-sha256-v7"
PREVIOUS_XD_SHADOW_SHINY_ENGINE = "xd-story-sha256-v8"
XD_SPOT_MIGRATION = "Réglages XD chargés. Les Poké Places utilisent le nouveau tirage."
SCHEMA_VERSION = 1
MAX_PROFILE_BYTES = 64 * 1024
MAX_REPORT_BYTES = 32 * 1024**2
# Legacy profiles predate the optional native stone-name correction. Import
# their exact signed payload first, then disable that new rule to preserve bytes.
LEGACY_APP_VERSIONS = frozenset(("0.5.0", "0.6.0", "0.6.1"))
LEGACY_ENGINE_VERSION = "starter-shadow-boss-rules-v7"
PREVIOUS_APP_VERSION = "0.7.0"
PREVIOUS_ENGINE_VERSION = "native-text-and-boss-rules-v8"
STAGE_APP_VERSION = "0.8.0"
STAGE_ENGINE_VERSION = "starter-evolution-stages-v9"
NEW_POLICY_FIELDS = frozenset(("trainer_theme_mode", "trainer_force_evolved", "trainer_evolution_level",
                               "excluded_species", "excluded_types"))
POLICY_APP_VERSION = "0.9.0"
POLICY_ENGINE_VERSION = "trainer-policies-and-exclusions-v10"
SHINY_FIELDS = frozenset(("custom_shinies", "shiny_chance_percent", "seeded_shinies"))
SHINY_APP_VERSION = "0.10.0"
NATIVE_SHINY_APP_VERSIONS = frozenset((SHINY_APP_VERSION, "0.10.1"))
NATIVE_SHINY_ENGINE_VERSION = "native-shiny-generation-v11"
SEEDED_SHINY_APP_VERSIONS = frozenset(("0.11.0", "0.12.0"))
SEEDED_SHINY_ENGINE_VERSION = "seeded-shiny-status-v12"
EVENT_GIFT_FIELDS = frozenset(("accessible_event_gifts", "event_pikachu_purifications",
                               "event_celebi_purifications", "event_pikachu_level", "event_celebi_level"))
PURIFICATION_APP_VERSION = "0.13.0"
PURIFICATION_ENGINE_VERSION = "purification-gifts-v13"
REGIONAL_APP_VERSION = "0.14.0"
REGIONAL_ENGINE_VERSION = "regional-purification-gifts-v14"
DETAILS_ENGINE_VERSION = "details-and-progression-v15"
DETAILS_APP_VERSIONS = frozenset(("0.15.0", "0.16.0", "0.16.1", "0.17.0", "0.17.1", "0.17.2", "0.17.3", "0.17.4"))
V15_FIELDS = frozenset(("starter_umbreon_species", "starter_espeon_species", "progressive_levels",
    "early_level_multiplier", "mid_level_multiplier", "late_level_multiplier", "experience_multiplier", "purification_multiplier"))
V16_ENGINE_VERSION = "story-family-diversity-v16"
V16_APP_VERSIONS = ("0.18.0", "0.18.1", "0.18.2", "0.18.3", "0.18.4", "0.19.0", "0.20.0",
    "0.21.0rc1", "0.21.0rc2", "1.0.0", "1.0.1", "1.1.0", "1.2.0", "1.2.1", "1.2.2", "1.2.3",
    "1.2.4", "1.2.5", "1.2.6", "1.2.7", "1.2.8")
V17_ENGINE_VERSION = "story-gift-scenes-v17"
V17_APP_VERSIONS = ("1.2.9", "1.2.10", "1.2.11", "1.2.12")
CURRENT_APP_VERSIONS = (*V16_APP_VERSIONS, *V17_APP_VERSIONS, __version__)
COMPATIBLE_APP_VERSIONS = LEGACY_APP_VERSIONS | NATIVE_SHINY_APP_VERSIONS | SEEDED_SHINY_APP_VERSIONS | DETAILS_APP_VERSIONS | {PREVIOUS_APP_VERSION, STAGE_APP_VERSION, POLICY_APP_VERSION, PURIFICATION_APP_VERSION, REGIONAL_APP_VERSION, *CURRENT_APP_VERSIONS}
LEGACY_GAME = {"id": "GC6P01", "revision": 0, "iso_sha256": ISO_SHA256}
# Profiles describe portable settings. The creation report identifies the exact
# input region and ISO; reproducibility still requires that same source image.
GAME = {"id": "pokemon-colosseum", "roms": [region.profile_identity() for region in REGIONS]}


@dataclass(frozen=True)
class Profile:
    seed: str
    options: Options | xd.XDOptions
    xd_spot_migration: bool = False


@dataclass(frozen=True)
class CreationReport:
    profile: Profile
    region: Region
    source_sha256: str


def validate_seed(seed: str) -> str:
    if not isinstance(seed, str):
        raise UserError("La seed du profil doit être du texte.")
    try:
        size = len(seed.encode("utf-8"))
    except UnicodeError as error:
        raise UserError("La seed du profil contient du texte UTF-8 invalide.") from error
    if not seed.strip() or not 1 <= size <= 256:
        raise UserError("La seed doit contenir de 1 à 256 octets UTF-8.")
    return seed


def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def profile_data(seed: str, options: Options) -> dict:
    payload = {"format": PROFILE_FORMAT, "schema_version": SCHEMA_VERSION,
               "app_version": __version__, "engine_version": ENGINE_VERSION,
               "game": dict(GAME), "seed": validate_seed(seed),
               "options": asdict(validate_options(options))}
    payload["configuration_sha256"] = hashlib.sha256(_canonical(payload)).hexdigest()
    return payload


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Clé JSON répétée : {key}")
        result[key] = value
    return result


def _decode_json(data: bytes):
    return json.loads(data.decode("utf-8-sig"), object_pairs_hook=_unique_object,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def parse_profile(data: bytes) -> Profile:
    if len(data) > MAX_PROFILE_BYTES:
        raise UserError("Profil trop volumineux : la limite est de 64 Ko.")
    try:
        payload = _decode_json(data)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise UserError("Profil JSON invalide. Sélectionnez un profil exporté par l’application.") from error
    required = {"format", "schema_version", "app_version", "engine_version", "game",
                "seed", "options", "configuration_sha256"}
    if type(payload) is not dict or set(payload) != required or payload["format"] != PROFILE_FORMAT:
        raise UserError("Ce fichier n’est pas un profil Colosseum Randomizer pris en charge.")
    if type(payload["schema_version"]) is not int or payload["schema_version"] != SCHEMA_VERSION:
        raise UserError("Format de profil incompatible. Utilisez la version de l’application ayant créé ce profil.")
    return _parse_configuration(payload)


def _parse_configuration(payload: dict, *, report_region: Region | None = None) -> Profile:
    legacy = (type(payload["app_version"]) is str and payload["app_version"] in LEGACY_APP_VERSIONS
              and payload["engine_version"] == LEGACY_ENGINE_VERSION)
    previous = (payload["app_version"] == PREVIOUS_APP_VERSION
                and payload["engine_version"] == PREVIOUS_ENGINE_VERSION)
    current = ((payload["app_version"] == __version__ and payload["engine_version"] == ENGINE_VERSION)
               or (payload["app_version"] in V17_APP_VERSIONS and payload["engine_version"] == V17_ENGINE_VERSION)
               or (payload["app_version"] in V16_APP_VERSIONS and payload["engine_version"] == V16_ENGINE_VERSION))
    details = (type(payload["app_version"]) is str and payload["app_version"] in DETAILS_APP_VERSIONS
               and payload["engine_version"] == DETAILS_ENGINE_VERSION)
    current_fields = current or details
    purification = (payload["app_version"] == PURIFICATION_APP_VERSION
                    and payload["engine_version"] == PURIFICATION_ENGINE_VERSION)
    regional = payload["app_version"] == REGIONAL_APP_VERSION and payload["engine_version"] == REGIONAL_ENGINE_VERSION
    portable = current_fields or regional
    all_fields = current_fields or regional or purification
    seeded_shiny = (type(payload["app_version"]) is str and payload["app_version"] in SEEDED_SHINY_APP_VERSIONS
                    and payload["engine_version"] == SEEDED_SHINY_ENGINE_VERSION)
    native_shiny = (type(payload["app_version"]) is str and payload["app_version"] in NATIVE_SHINY_APP_VERSIONS
                    and payload["engine_version"] == NATIVE_SHINY_ENGINE_VERSION)
    stage = payload["app_version"] == STAGE_APP_VERSION and payload["engine_version"] == STAGE_ENGINE_VERSION
    policy = payload["app_version"] == POLICY_APP_VERSION and payload["engine_version"] == POLICY_ENGINE_VERSION
    if not (legacy or previous or stage or policy or native_shiny or seeded_shiny or purification or regional or details or current):
        if report_region is not None:
            raise UserError("Version du rapport incompatible. Utilisez la version du randomizer qui l’a créé.")
        raise UserError("Version du profil incompatible. Utilisez la même version du randomizer pour reproduire la partie.")
    expected_game = GAME if portable else LEGACY_GAME
    if report_region is not None:
        if not portable and report_region.game_id != LEGACY_GAME["id"]:
            raise UserError("La ROM indiquée dans le rapport ne correspond pas à une version prise en charge.")
    elif (type(payload["game"]) is not dict or payload["game"] != expected_game
          or not portable and type(payload["game"].get("revision")) is not int
          or portable and any(type(rom.get("revision")) is not int for rom in payload["game"]["roms"])):
        raise UserError("Ce profil ne correspond pas aux versions prises en charge de Colosseum.")
    values = payload["options"]
    expected_fields = {item.name for item in fields(Options)}
    if not current:
        expected_fields.remove("diverse_story_families")
    if not current_fields:
        expected_fields.difference_update(V15_FIELDS)
    if not all_fields:
        expected_fields.difference_update(EVENT_GIFT_FIELDS)
    if legacy or previous or stage or policy:
        expected_fields.difference_update(SHINY_FIELDS)
    elif native_shiny:
        expected_fields.remove("seeded_shinies")
    if legacy or previous or stage:
        expected_fields.difference_update(NEW_POLICY_FIELDS)
    if legacy or previous:
        expected_fields.difference_update(("starter_stage", "starter_three_stage_families"))
        expected_fields.add("starter_base_forms")
    if legacy:
        expected_fields.remove("readable_stone_names")
    if type(values) is not dict or set(values) != expected_fields:
        if report_region is not None:
            raise UserError("Réglages du rapport incomplets ou inconnus. Sélectionnez le rapport d’origine.")
        raise UserError("Paramètres du profil incomplets ou inconnus. Réexportez-le avec la même version.")
    seed = validate_seed(payload["seed"])
    if report_region is None:
        digest = payload["configuration_sha256"]
        canonical = {key: value for key, value in payload.items() if key != "configuration_sha256"}
        try:
            expected = hashlib.sha256(_canonical(canonical)).hexdigest()
        except (ValueError, UnicodeError) as error:
            raise UserError("Profil JSON invalide. Sélectionnez un profil exporté par l’application.") from error
        if type(digest) is not str or digest != expected:
            raise UserError("L’empreinte du profil ne correspond pas à son contenu. Réexportez le profil d’origine.")
    values = dict(values)
    if not current_fields:
        defaults = Options()
        values.update({name: getattr(defaults, name) for name in V15_FIELDS})
    if legacy or previous or stage or policy:
        values.update(custom_shinies=False, shiny_chance_percent=Options().shiny_chance_percent)
    if not (all_fields or seeded_shiny):
        values["seeded_shinies"] = False
    if not all_fields:
        defaults = Options()
        values.update({name: getattr(defaults, name) for name in EVENT_GIFT_FIELDS})
        values["accessible_event_gifts"] = False
    if legacy or previous or stage:
        defaults = Options()
        values.update({name: getattr(defaults, name) for name in NEW_POLICY_FIELDS})
    if legacy or previous:
        base = values.pop("starter_base_forms")
        if type(base) is not bool:
            raise UserError("Paramètres du profil incomplets ou inconnus. Réexportez-le avec la même version.")
        values.update(starter_stage="base" if base else "any", starter_three_stage_families=False)
    if legacy:
        values["readable_stone_names"] = False
    options = validate_options(Options(**values))
    return Profile(seed, options)


def load_profile(path: Path, *, is_xd=False) -> Profile:
    with Path(path).open("rb") as stream:
        data = stream.read(MAX_PROFILE_BYTES + 1)
    return parse_xd_profile(data) if is_xd else parse_profile(data)


def parse_xd_profile(data: bytes, *, report=False) -> Profile:
    if len(data) > (MAX_REPORT_BYTES if report else MAX_PROFILE_BYTES):
        raise UserError("Profil trop volumineux : la limite est de 64 Ko." if not report
                        else "Rapport trop volumineux : la limite est de 32 Mio.")
    invalid = "Ce fichier ne contient pas de réglages Pokémon XD compatibles."
    try:
        payload = _decode_json(data)
        if type(payload) is not dict or payload.get("engine_version") not in (
            xd.VERSION, PREVIOUS_XD_SHADOW_SHINY_ENGINE, PREVIOUS_XD_FULL_SPOT_ENGINE, PREVIOUS_XD_SHUFFLE_ENGINE,
            PREVIOUS_XD_QOL_ENGINE, PREVIOUS_XD_ENGINE, LEGACY_XD_ENGINE,
        ):
            raise ValueError
        legacy = payload["engine_version"] == LEGACY_XD_ENGINE
        if report:
            region = xd.REGIONS.get(payload["game_id"])
            if (region is None or payload["source_iso_sha256"] != region.iso_sha256
                    or type(payload["revision"]) is not int or payload["revision"] != region.revision):
                raise ValueError
        else:
            if (payload.get("format") != XD_PROFILE_FORMAT
                    or type(payload.get("schema_version")) is not int or payload["schema_version"] != SCHEMA_VERSION):
                raise ValueError
            digest = payload.pop("configuration_sha256")
            if digest != hashlib.sha256(_canonical(payload)).hexdigest():
                raise ValueError
        options = payload["options"]
        seed = payload["seed"]
        expected = {item.name for item in fields(xd.XDOptions)}
        if payload["engine_version"] not in (xd.VERSION, PREVIOUS_XD_SHADOW_SHINY_ENGINE):
            expected.remove("custom_shadow_shinies")
        if payload["engine_version"] not in (xd.VERSION, PREVIOUS_XD_SHADOW_SHINY_ENGINE, PREVIOUS_XD_FULL_SPOT_ENGINE):
            expected.remove("poke_spots_full_pokedex")
        if payload["engine_version"] in (PREVIOUS_XD_ENGINE, LEGACY_XD_ENGINE):
            expected.remove("randomize_hordel_gift")
        if legacy:
            expected.remove("randomize_tutorial_shadow")
        if type(options) is not dict or set(options) != expected:
            raise ValueError
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError) as error:
        raise UserError(invalid) from error
    return Profile(validate_seed(seed), xd.validate_options(xd.XDOptions(**options)),
                   xd_spot_migration=legacy and options["randomize_poke_spots"] is True)


def load_xd_creation_report(path: Path) -> Profile:
    with Path(path).open("rb") as stream:
        return parse_xd_profile(stream.read(MAX_REPORT_BYTES + 1), report=True)


def parse_creation_report(data: bytes, *, is_xd=False) -> CreationReport:
    if len(data) > MAX_REPORT_BYTES:
        raise UserError("Rapport trop volumineux : la limite est de 32 Mio.")
    invalid = "Rapport JSON invalide. Sélectionnez le fichier .iso.json ou .rvz.json créé avec la ROM."
    try:
        payload = _decode_json(data)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise UserError(invalid) from error
    required = {"application_version", "engine_version", "game_id", "revision",
                "source_sha256", "source_iso_sha256", "seed", "options"}
    if type(payload) is not dict or not required <= payload.keys():
        raise UserError(invalid)
    regions = xd.REGIONS.values() if is_xd else REGIONS
    region = next((item for item in regions if item.game_id == payload["game_id"]), None)
    digest = payload["source_sha256"]
    if (region is None or type(payload["revision"]) is not int or payload["revision"] != region.revision
            or payload["source_iso_sha256"] != region.iso_sha256
            or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
        raise UserError("La ROM indiquée dans le rapport ne correspond pas à une version prise en charge.")
    profile = parse_xd_profile(data, report=True) if is_xd else _parse_configuration(dict(app_version=payload["application_version"],
                                        engine_version=payload["engine_version"],
                                        seed=payload["seed"], options=payload["options"]), report_region=region)
    return CreationReport(profile, region, digest)


def load_creation_report(path: Path, *, is_xd=False) -> CreationReport:
    with Path(path).open("rb") as stream:
        return parse_creation_report(stream.read(MAX_REPORT_BYTES + 1), is_xd=is_xd)


def save_profile(path: Path, seed: str, options: Options | xd.XDOptions) -> dict:
    path = Path(path)
    if path.suffix.lower() != ".json":
        raise UserError("Enregistrez le profil dans un fichier .json.")
    if isinstance(options, xd.XDOptions):
        payload = {"format": XD_PROFILE_FORMAT, "schema_version": SCHEMA_VERSION, "engine_version": xd.VERSION,
                   "seed": validate_seed(seed), "options": asdict(xd.validate_options(options))}
        payload["configuration_sha256"] = hashlib.sha256(_canonical(payload)).hexdigest()
    else:
        payload = profile_data(seed, options)
    content = (json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    try:
        with path.open("xb") as stream:
            stream.write(content)
    except FileExistsError as error:
        raise UserError("Ce fichier existe déjà. Choisissez un nouveau nom de profil.") from error
    return payload
