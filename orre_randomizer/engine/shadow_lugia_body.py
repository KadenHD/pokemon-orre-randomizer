"""Audited whole-body artwork rendered from the native Shadow Lugia models."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..artwork import ArtworkError, _png_pixels
from ..model_artwork import validate_model_body
from .analyze_game import FormatError
from .dna_artwork import outline_dna_body


_FILES = ("dark-lugia-body.png", "dark-lugia-shiny-body.png")


def shadow_lugia_body_pixels(shiny: bool) -> bytes:
    """Return the whole body with the DNA keypad's black silhouette contour."""
    if type(shiny) is not bool:
        raise ValueError("the Shadow Lugia body variant must be a boolean")
    pack = Path(__file__).resolve().parents[1] / "assets" / "game" / "models"
    filename = _FILES[int(shiny)]
    try:
        metadata = json.loads((pack / "fullbody-manifest.json").read_text("utf-8"))
        record = metadata["files"][filename]
        payload = (pack / filename).read_bytes()
        if (metadata["dimensions"] != [64, 64]
                or record["shiny"] is not shiny
                or len(payload) != record["bytes"]
                or hashlib.sha256(payload).hexdigest() != record["sha256"]):
            raise FormatError("the native Shadow Lugia whole-body asset is modified")
        pixels = _png_pixels(payload, (64, 64))
    except (OSError, KeyError, TypeError, ValueError, ArtworkError) as error:
        raise FormatError("the native Shadow Lugia whole-body asset is unavailable") from error
    # A transparent margin keeps the complete native silhouette inside a tile.
    try:
        return validate_model_body(outline_dna_body(validate_model_body(pixels), 64))
    except ValueError as error:
        raise FormatError("the native Shadow Lugia whole-body silhouette is clipped") from error
