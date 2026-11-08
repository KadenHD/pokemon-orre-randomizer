"""Explicit documentation media allowlist, shared by build and audit."""
import hashlib
import json


DOCUMENTATION_IMAGES = frozenset(("home.png", "colosseum-settings.png",
                                 "xd-settings.png", "pokemon-sheet.png", "shadow-pokemon.png",
                                 "colosseum-starters-ingame.png", "xd-starter-ingame.png",
                                 "colosseum-advanced.png", "xd-advanced.png",
                                 "colosseum-shadow-moves.png", "xd-shadow-moves.png",
                                 "xd-pokespot-shiny-field.png", "xd-pokespot-shiny-battle.png",
                                 "colosseum-motorcycle-starters.png", "colosseum-motorcycle-arrival.gif",
                                 "colosseum-plusle-gift.png", "colosseum-pyrite-dancers.png", "colosseum-pyrite-dancers.gif",
                                 "xd-lighthouse-dancers.png", "colosseum-simple.png", "xd-starter-preview.png",
                                 "xd-shadow-pokemon.png", "colosseum-gifts.png", "xd-gifts.png", "xd-pokemon-sheet.png"))


def documentation_media(read_bytes):
    manifest = json.loads(read_bytes("manifest.json"))
    if set(manifest["files"]) != DOCUMENTATION_IMAGES:
        raise RuntimeError("Unexpected documentation screenshots")
    for name, record in manifest["files"].items():
        payload = read_bytes(name)
        if len(payload) != record["bytes"] or hashlib.sha256(payload).hexdigest() != record["sha256"]:
            raise RuntimeError("Invalid documentation screenshot: " + name)
    return DOCUMENTATION_IMAGES | {"manifest.json"}
