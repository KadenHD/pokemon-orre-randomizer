"""Small, allowlisted support reports. Never serialize paths, logs or raw errors."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, fields
import json
from math import isfinite
from pathlib import Path
import re
import sys
import tempfile

from . import __version__
from .engine.analyze_game import FormatError
from .options import Options
from .service import ENGINE_VERSION as COLOSSEUM_ENGINE, UserError, publish_new
from .xd import XDOptions, VERSION as XD_ENGINE

SCHEMA = "orre-support-v1"
MAX_BYTES = 128 * 1024
STAGES = frozenset(("settings", "preview", "creation"))
KINDS = frozenset(("validation", "format", "io", "internal"))
ERROR_CODES = frozenset(("validation_failed", "data_format_failed", "file_access_failed",
                         "operation_failed", "xd_tutorial_matchup", "xd_tutorial_target_filter"))
DISC_IDS = {"colosseum": frozenset(("GC6P01", "GC6E01", "GC6J01")),
            "xd": frozenset(("GXXP01", "GXXE01", "GXXJ01"))}
_PRIVATE_SEED = re.compile(
    r"[A-Za-z]:[\\/]|\\\\|(?:^|\s)/(?:home|Users|tmp|var|mnt|etc)(?:/|\b)|"
    r"(?:^|\s)~[\\/]|(?:https?|file|ssh)://|\b[^\s@]+@[^\s@]+\.[^\s@]+|"
    r"\b(?:github_pat_|gh[pousr]_|sk-|AKIA)[A-Za-z0-9_\-]{8,}|"
    r"(?:password|passwd|token|api[_ -]?key|secret)\s*[:=]", re.IGNORECASE)


def seed_is_shareable(seed):
    """A heuristic, not a promise to detect every user-entered secret."""
    return (type(seed) is str and 0 < len(seed) <= 128
            and not any(ord(char) < 32 or ord(char) == 127 for char in seed)
            and not _PRIVATE_SEED.search(seed))


def _option_value(field, value):
    choices = field.metadata.get("choices")
    if choices:
        return (value, True) if any(type(value) is type(choice) and value == choice for choice, _ in choices) else (None, False)
    if type(field.default) is bool:
        return value, type(value) is bool
    if type(field.default) in (int, float):
        valid = type(value) in ((int,) if type(field.default) is int else (int, float))
        valid = (valid and field.metadata.get("minimum", -1000000) <= value <= field.metadata.get("maximum", 1000000)
                 and isfinite(value))
        return value, valid
    if type(field.default) is tuple:
        maximum = 386 if field.metadata.get("kind") == "species_set" else 17
        valid = type(value) in (tuple, list) and len(value) <= 500 and all(type(item) is int and 0 <= item <= maximum for item in value)
        return list(value) if valid else None, valid
    return None, False


def safe_options(game, values):
    """Only the actual option schema can contribute keys or string values."""
    option_type = XDOptions if game == "xd" else Options
    source = values if type(values) is dict else {}
    result, omitted = {}, []
    for field in fields(option_type):
        value, valid = _option_value(field, source.get(field.name))
        if field.name in source and valid:
            result[field.name] = value
        else:
            omitted.append(field.name)
    return result, omitted


def normalized_error(error):
    if isinstance(error, FormatError):
        code = {"Aucun Pokémon adapté au tutoriel. Élargissez les filtres ou choisissez un starter capable d’attaquer.":
                    "xd_tutorial_matchup",
                "Aucun Pokémon adapté au tutoriel. Élargissez les filtres de Pokémon.":
                    "xd_tutorial_target_filter"}.get(str(error), "data_format_failed")
        return {"kind": "format", "code": code}
    if isinstance(error, UserError):
        return {"kind": "validation", "code": "validation_failed"}
    if isinstance(error, OSError):
        return {"kind": "io", "code": "file_access_failed"}
    return {"kind": "internal", "code": "operation_failed"}


def sanitize_report(document, *, include_seed=True):
    """Reapply the allowlist at the file boundary, including cached snapshots."""
    document = document if type(document) is dict else {}
    game = "xd" if document.get("game") == "xd" else "colosseum"
    options, omitted = safe_options(game, document.get("options"))
    original_operation = document.get("operation") if type(document.get("operation")) is dict else {}
    stage = original_operation.get("stage")
    operation = {"stage": stage if type(stage) is str and stage in STAGES else "settings"}
    error = original_operation.get("error")
    if (type(error) is dict and type(error.get("kind")) is str and type(error.get("code")) is str
            and error["kind"] in KINDS and error["code"] in ERROR_CODES):
        operation["error"] = {"kind": error["kind"], "code": error["code"]}
    seed = document.get("seed")
    shareable = seed_is_shareable(seed)
    if shareable:
        seed_status = "included" if include_seed else "omitted_by_user"
    else:
        seed_status = ("omitted_by_user" if seed is None and document.get("seed_status") == "omitted_by_user"
                       else "omitted_sensitive_or_invalid")
    result = {"schema": SCHEMA, "app": {"version": __version__,
              "platform": sys.platform if sys.platform in ("win32", "linux", "darwin") else "other"},
              "game": game, "engine_version": XD_ENGINE if game == "xd" else COLOSSEUM_ENGINE,
              "seed": seed if seed_status == "included" else None, "seed_status": seed_status,
              "options": options, "omitted_option_fields": omitted,
              "operation": operation, "disc": {"identity": "unavailable"}}
    disc = document.get("disc")
    if (type(disc) is dict and disc.get("identity") == "verified"
            and type(disc.get("game_id")) is str and disc["game_id"] in DISC_IDS[game] and type(disc.get("revision")) is int
            and disc["revision"] == 0):
        result["disc"] = {"identity": "verified", "game_id": disc["game_id"], "revision": 0,
                          "region": {"P": "Europe", "E": "USA", "J": "Japan"}[disc["game_id"][3]]}
    return result


def settings_snapshot(owner, stage="settings", *, arguments=None):
    """No ROM access. A previous successful operation may supply its identity."""
    arguments = arguments or {}
    options = arguments.get("xd_options", arguments.get("options", owner.current_options()))
    game = "xd" if type(options) is XDOptions else "colosseum"
    source = str(arguments.get("source", owner.source.text().strip()))
    identity = getattr(owner, "_support_verified_disc", None)
    disc = identity[1] if identity is not None and identity[0] == source else {}
    return sanitize_report({"game": game, "seed": arguments.get("seed", owner.seed.text()),
                            "options": asdict(options), "disc": disc, "operation": {"stage": stage}})


def remember_verified_disc(owner, result):
    """Call only with the engine's successful preview or creation result."""
    game = "xd" if type(owner.current_options()) is XDOptions else "colosseum"
    game_id, revision = result.get("game_id"), result.get("revision")
    if type(game_id) is str and game_id in DISC_IDS[game] and type(revision) is int and revision == 0:
        owner._support_verified_disc = (owner.source.text().strip(),
                                       {"identity": "verified", "game_id": game_id, "revision": revision})


def operation_snapshot(owner, stage, arguments=None):
    snapshot = settings_snapshot(owner, stage, arguments=arguments)
    owner._support_pending = snapshot
    return snapshot


def request_key(owner):
    return owner.source.text().strip(), owner.seed.text(), owner.current_options()


def remember_failure(owner, error, cancelled, *, snapshot=None, expected_key=None):
    if cancelled:
        return
    if expected_key is not None and expected_key != request_key(owner):
        return
    snapshot = deepcopy(snapshot if snapshot is not None else getattr(owner, "_support_pending", None)
                        or settings_snapshot(owner))
    snapshot["operation"]["error"] = normalized_error(error)
    owner._support_last_failure = sanitize_report(snapshot)


def report_text(document, *, include_seed=True):
    payload = json.dumps(sanitize_report(document, include_seed=include_seed), ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if len(payload.encode("utf-8")) > MAX_BYTES:
        raise UserError("Diagnostic trop volumineux. Vérifiez les réglages et réessayez.")
    return payload


def save_report(destination, document, *, include_seed=True, cancel=None):
    destination = Path(destination)
    if destination.suffix.lower() != ".json":
        raise UserError("Choisissez un fichier JSON pour le diagnostic.")
    if cancel is not None and cancel.is_set():
        from .service import Cancelled
        raise Cancelled("Opération annulée.")
    payload = report_text(document, include_seed=include_seed).encode("utf-8")
    with tempfile.TemporaryDirectory(prefix=".orre-diagnostic-", dir=destination.parent) as folder:
        pending = Path(folder) / "report.json"
        with pending.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            import os
            os.fsync(stream.fileno())
        if cancel is not None and cancel.is_set():
            from .service import Cancelled
            raise Cancelled("Opération annulée.")
        publish_new(pending, destination)
    return destination
