"""Install paired native/HD weather appearances without changing saved identity."""
from __future__ import annotations

import hashlib
import re

from .artwork import _png_pixels
from .castform_layouts import LAYOUTS
from .castform_portraits import install_castform_portraits
from .castform_shiny_models import install_castform_shiny_models
from .castform_shiny_palette import make_weather_shiny_pkx
from .engine.analyze_game import FormatError
from .hd_menu_catalog import _asset, _asset_bytes

VERSION = "castform-official-shiny-weather-v1"
CATALOGUE = "castform-shinies/catalog.json"
FORMS = {414: "w", 415: "f", 416: "i"}
_FILE = re.compile(r"[a-z0-9][a-z0-9_-]{0,125}\.png\Z")


def _native_face(catalogue, game, model, normal):
    entry = catalogue.get("faces", {}).get(f"{game}/{model}")
    if not isinstance(entry, dict):
        raise FormatError("missing registered shiny weather portrait")
    name = entry.get("native_file")
    if not isinstance(name, str) or _FILE.fullmatch(name) is None:
        raise FormatError("invalid registered shiny weather portrait path")
    payload, digest = _asset_bytes("castform-shinies/" + name)
    if (entry.get("native_dimensions") != [42, 42]
            or digest != entry.get("native_sha256") or len(payload) != entry.get("native_bytes")):
        raise FormatError("registered shiny weather portrait identity changed")
    pixels = _png_pixels(payload, (42, 42))
    if len(normal) != len(pixels) or pixels[3::4] != normal[3::4]:
        raise FormatError("shiny weather portrait changed its native frame")
    return pixels


def install_weather_appearances(original, current, game_id, read_archive, pending_updates):
    """Compose models and portraits with already prepared Lugia/scene edits.

    Sources are exact retail PKXs. Only color payloads are changed in an added
    resource; native meshes, motion, normal resources and saved PIDs are retained.
    Native generation needs only the bundled artwork, never installed HD packs.
    """
    from .castform_resources import SHINY_FACE_RESOURCES, append_castform_resources

    if game_id not in LAYOUTS:
        raise FormatError("unknown weather appearance game identity")
    catalogue, digest = _asset(CATALOGUE)
    if (not isinstance(catalogue, dict) or catalogue.get("schema") != 1
            or catalogue.get("kind") != "castform-shiny-native-and-hd"
            or catalogue.get("review_only") is not False):
        raise FormatError("shiny weather artwork is unreviewed")
    game = "xd" if game_id.startswith("GXX") else "colosseum"
    palette_reports = {}

    def model_builder(identity, model, source):
        if identity != game_id or model not in FORMS:
            raise FormatError("invalid native weather model request")
        output, report = make_weather_shiny_pkx(source, game=game, form=FORMS[model])
        registered = catalogue.get("source_models", {}).get(f"{game}/{model}")
        if (not isinstance(registered, dict)
                or registered.get("source_sha256") != hashlib.sha256(source).hexdigest()
                or registered.get("sha256") != hashlib.sha256(output).hexdigest()):
            raise FormatError("native shiny weather model and HD artwork disagree")
        palette_reports[str(model)] = report
        return output

    def face_pixels(identity, model, normal):
        if identity != game_id or model not in FORMS:
            raise FormatError("invalid native weather portrait request")
        return _native_face(catalogue, game, model, normal)

    # Validate the complete result before publishing any pending archive edit.
    staged = dict(pending_updates)
    resources = append_castform_resources(game_id, read_archive, staged,
        model_builder=model_builder, shiny_face_pixels=face_pixels)
    current, portraits = install_castform_portraits(original, current, game_id,
        shiny_resources=SHINY_FACE_RESOURCES)
    current, models = install_castform_shiny_models(original, current, game_id)
    pending_updates.clear()
    pending_updates.update(staged)
    return current, {"version": VERSION, "game_id": game_id,
        "catalogue_sha256": digest, "resources": resources, "models": models,
        "portraits": portraits, "palettes": palette_reports,
        "saved_identity_unchanged": True, "normal_resources_preserved": True,
        "required_hd_packs": ["colosseum"]}
