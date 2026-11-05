"""Explicit documentation screenshot allowlist, shared by build and audit."""
import hashlib
import json


DOCUMENTATION_IMAGES = frozenset(("home.png", "colosseum-settings.png",
                                 "xd-settings.png", "pokemon-sheet.png", "shadow-pokemon.png"))


def documentation_media(read_bytes):
    manifest = json.loads(read_bytes("manifest.json"))
    if set(manifest["files"]) != DOCUMENTATION_IMAGES:
        raise RuntimeError("Unexpected documentation screenshots")
    for name, record in manifest["files"].items():
        payload = read_bytes(name)
        if len(payload) != record["bytes"] or hashlib.sha256(payload).hexdigest() != record["sha256"]:
            raise RuntimeError("Invalid documentation screenshot: " + name)
    return DOCUMENTATION_IMAGES | {"manifest.json"}
