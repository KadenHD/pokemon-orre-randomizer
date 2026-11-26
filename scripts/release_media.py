"""Explicit documentation media allowlist, shared by build and audit."""
import hashlib
import json
import struct
from pathlib import PurePosixPath, PureWindowsPath


GAME_ASSET_EXCEPTIONS = frozenset(("models/dark-lugia-colosseum-v1.pkx",
                                   "models/deoxys/xd-attack-normal.pkx", "models/deoxys/xd-attack-shiny.pkx",
                                   "models/deoxys/xd-defense-normal.pkx", "models/deoxys/xd-defense-shiny.pkx",
                                   "models/deoxys/xd-speed-normal.pkx", "models/deoxys/xd-speed-shiny.pkx",
                                   "fonts/NotoSansJP.ttf", "fonts/OFL-NotoSansJP.txt"))

BINGO_AUTHORING_ROOT = "scripts/bingo_menu_artwork/"
BINGO_AUTHORING_LAYERS = frozenset(
    [f"layers/{kind}-{index:02d}-x4.png" for kind in ("background", "frame-overlay") for index in range(11)]
    + ["layers/geometric-picture-window-x4.png"])


def bingo_authoring_media(read_bytes):
    """Allow only the recorded CPU-authored backgrounds and vector frames."""
    recipe = json.loads(read_bytes("bingo-recipe.json"))
    rows = recipe.get("authored_layers", [])
    if (recipe.get("schema") != 1 or recipe.get("review_only") is not False
            or recipe.get("art_approved_by_root") is not True
            or recipe.get("native_bitmap_upscaled_for_HD") is not False
            or len(rows) != len(BINGO_AUTHORING_LAYERS)
            or {row.get("file") for row in rows} != BINGO_AUTHORING_LAYERS):
        raise RuntimeError("Unexpected Bingo authoring layers")
    for row in rows:
        payload = read_bytes(row["file"])
        if (not 33 <= len(payload) <= 1024 * 1024
                or payload[:16] != b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
                or struct.unpack_from(">II", payload, 16) != (360, 360)
                or hashlib.sha256(payload).hexdigest() != row["sha256"]):
            raise RuntimeError("Invalid Bingo authoring layer: " + row["file"])
    return BINGO_AUTHORING_LAYERS | {"bingo-recipe.json", "README.md"}


def game_asset_name_allowed(name):
    if not isinstance(name, str) or not name or "\\" in name or ":" in name or PureWindowsPath(name).drive:
        return False
    path = PurePosixPath(name)
    return (not path.is_absolute() and ".." not in path.parts and
            (path.suffix in {".png", ".wav", ".json", ".md"} or name in GAME_ASSET_EXCEPTIONS))


DOCUMENTATION_IMAGES = frozenset(("home.png", "colosseum-settings.png",
                                 "colosseum-deoxys-forms.png", "xd-deoxys-forms.png",
                                 "run-library.png", "save-backups.png", "storage.png", "challenge-code.png", "support-diagnostic.png",
                                 "colosseum-launcher.png", "xd-launcher.png", "hd-packs.png", "hd-custom-lugia-portraits.png",
                                 "hd-colosseum-text.png", "hd-xd-text.png", "hd-xd-vs.png", "castform-live-portraits.png",
                                 "castform-colosseum-weather-shinies.png", "castform-xd-weather-shinies.png",
                                 "colosseum-output-formats.png", "xd-output-formats.png",
                                 "xd-settings.png", "pokemon-sheet.png", "shadow-pokemon.png",
                                 "colosseum-starters-ingame.png", "xd-starter-ingame.png",
                                 "colosseum-advanced.png", "xd-advanced.png",
                                 "colosseum-shadow-moves.png", "xd-shadow-moves.png",
                                 "xd-pokespot-shiny-field.png", "xd-pokespot-shiny-battle.png",
                                 "colosseum-motorcycle-starters.png", "colosseum-motorcycle-arrival.gif",
                                 "colosseum-plusle-gift.png", "colosseum-pyrite-dancers.png", "colosseum-pyrite-dancers.gif",
                                 "xd-lighthouse-dancers.png", "colosseum-simple.png", "xd-starter-preview.png",
                                 "xd-shadow-pokemon.png", "colosseum-gifts.png", "xd-gifts.png", "xd-pokemon-sheet.png",
                                 "colosseum-shadow-lugia-event.gif", "colosseum-shiny-settings.png",
                                 "xd-purified-shadow-lugia.png", "xd-shiny-shadow-lugia.png", "colosseum-dna-keypad.png",
                                 "colosseum-dna-keypad-purified.png", "colosseum-fixed-preview.png",
                                 "xd-fixed-preview.png", "colosseum-shadow-lugia-aftermath.png",
                                 "xd-pokespot-preview.png"))


def documentation_media(read_bytes):
    manifest = json.loads(read_bytes("manifest.json"))
    if set(manifest["files"]) != DOCUMENTATION_IMAGES:
        raise RuntimeError("Unexpected documentation screenshots")
    for name, record in manifest["files"].items():
        payload = read_bytes(name)
        if len(payload) != record["bytes"] or hashlib.sha256(payload).hexdigest() != record["sha256"]:
            raise RuntimeError("Invalid documentation screenshot: " + name)
    return DOCUMENTATION_IMAGES | {"manifest.json"}
