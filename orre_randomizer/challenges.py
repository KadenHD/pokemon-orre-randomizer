"""Bounded portable challenge codes, containing settings only, never local paths."""
from __future__ import annotations

import base64
import hashlib
import json
import re
import zlib

from .profiles import (configuration_data, parse_profile, parse_xd_profile,
                       _canonical, _decode_json, MAX_PROFILE_BYTES)
from .service import UserError
from .options import Options
from .xd import XDOptions
from . import __version__

PREFIX = "ORRE1"
MAX_CODE = 100_000


def encode_challenge(seed, options):
    configuration = configuration_data(seed, options)
    names = sorted(configuration["options"])
    raw = _canonical({"schema": 1, "game": "xd" if isinstance(options, XDOptions) else "colosseum",
        "app_version": __version__, "engine_version": configuration["engine_version"],
        "fields_sha256": hashlib.sha256(_canonical(names)).hexdigest(),
        "seed": configuration["seed"], "values": [configuration["options"][name] for name in names]})
    payload = base64.urlsafe_b64encode(zlib.compress(raw, 9)).decode("ascii").rstrip("=")
    return PREFIX + "." + payload + "." + hashlib.sha256(raw).hexdigest()[:16]


def decode_challenge(code):
    if not isinstance(code, str) or len(code) > MAX_CODE:
        raise UserError("Code de défi invalide ou trop long.")
    try:
        prefix, encoded, checksum = "".join(code.split()).split(".")
        if prefix != PREFIX or not re.fullmatch(r"[A-Za-z0-9_-]+", encoded) or not re.fullmatch(r"[0-9a-f]{16}", checksum):
            raise ValueError("Invalid challenge envelope")
        packed = base64.b64decode(encoded + "=" * (-len(encoded) % 4), altchars=b"-_", validate=True)
        decoder = zlib.decompressobj()
        raw = decoder.decompress(packed, MAX_PROFILE_BYTES + 1)
        if len(raw) > MAX_PROFILE_BYTES or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
            raise ValueError("Invalid compressed profile")
        if hashlib.sha256(raw).hexdigest()[:16] != checksum:
            raise ValueError("Challenge checksum mismatch")
        payload = _decode_json(raw)
        required = {"schema", "game", "app_version", "engine_version", "fields_sha256", "seed", "values"}
        if (type(payload) is not dict or set(payload) != required or type(payload["schema"]) is not int
                or payload["schema"] != 1 or payload["game"] not in ("colosseum", "xd")
                or not isinstance(payload["app_version"], str) or type(payload["values"]) is not list):
            raise ValueError("Invalid challenge schema")
        game = payload["game"]
        configuration = configuration_data(payload["seed"], XDOptions() if game == "xd" else Options())
        names = sorted(configuration["options"])
        if payload["engine_version"] != configuration["engine_version"]:
            raise UserError("Ce défi utilise un autre moteur. Utilisez la version Orre de son créateur.")
        if (payload["fields_sha256"] != hashlib.sha256(_canonical(names)).hexdigest()
                or len(payload["values"]) != len(names)):
            raise UserError("Ce défi utilise un autre moteur. Utilisez la version Orre de son créateur.")
        configuration["options"] = dict(zip(names, payload["values"], strict=True))
        configuration.pop("configuration_sha256")
        configuration["configuration_sha256"] = hashlib.sha256(_canonical(configuration)).hexdigest()
        profile_raw = _canonical(configuration)
        profile = parse_xd_profile(profile_raw) if game == "xd" else parse_profile(profile_raw)
    except (ValueError, UnicodeError, AttributeError, zlib.error, RecursionError) as error:
        raise UserError("Code de défi invalide ou trop long.") from error
    if profile.engine_migration:
        raise UserError("Ce défi utilise un autre moteur. Utilisez la version Orre de son créateur.")
    return game, profile
