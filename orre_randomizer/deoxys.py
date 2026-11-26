"""Initial Deoxys form choices, official base stats and presentation labels."""
from __future__ import annotations

import hashlib

DEOXYS = 410  # Generation III internal species index (National Pokédex 386).
FORM_ORDER = ("normal", "attack", "defense", "speed")
FORM_VERSION = "orre-deoxys-form-v1"
BASE_STAT_FIELDS = ("hp", "attack", "defense", "sp_attack", "sp_defense", "speed")
BASE_STATS = {
    "normal": (50, 150, 50, 150, 50, 150),
    "attack": (50, 180, 20, 180, 20, 150),
    "defense": (50, 70, 160, 70, 160, 90),
    "speed": (50, 95, 90, 95, 90, 180),
}
_LABELS = {
    "fr": ("Forme Normale", "Forme Attaque", "Forme Défense", "Forme Vitesse"),
    "en": ("Normal Forme", "Attack Forme", "Defense Forme", "Speed Forme"),
    "de": ("Normalform", "Angriffsform", "Verteidigungsform", "Initiativeform"),
    "es": ("Forma normal", "Forma ataque", "Forma defensa", "Forma velocidad"),
    "it": ("Forma Normale", "Forma Attacco", "Forma Difesa", "Forma Velocità"),
    "ja": ("ノーマルフォルム", "アタックフォルム", "ディフェンスフォルム", "スピードフォルム"),
}


def form_label(form: int | str, language: str = "en") -> str:
    if isinstance(form, str):
        if form not in FORM_ORDER:
            raise ValueError("Unknown Deoxys form")
        form = FORM_ORDER.index(form)
    if type(form) is not int or not 0 <= form < 4:
        raise ValueError("Unknown Deoxys form")
    return _LABELS.get(language, _LABELS["en"])[form]


def form_seed(seed: str, key: str) -> int:
    """Versioned encounter token; its upper bits choose only the initial form.

    The token is never installed as a PID-generation RNG state. The generated
    record receives an independent persistent form tag.
    """
    if not isinstance(seed, str) or not seed.strip() or not 1 <= len(seed.encode("utf8")) <= 256:
        raise ValueError("Seed must contain 1..256 UTF-8 bytes")
    if not isinstance(key, str) or not key or len(key) > 256 or not key.isascii():
        raise ValueError("Deoxys encounter key must contain 1..256 ASCII characters")
    raw = seed.encode("utf8")
    prefix = FORM_VERSION.encode("ascii") + b"\0" + len(raw).to_bytes(2, "big") + raw
    return int.from_bytes(hashlib.sha256(prefix + b"\0" + key.encode("ascii")).digest()[:4], "big") or 1


def encounter_forms(seeds) -> dict[str, int]:
    """The form is previewable even when shiny status uses native runtime RNG."""
    result = {}
    for key, value in seeds.items():
        if not isinstance(key, str) or type(value) is not int or not 1 <= value <= 0xFFFFFFFF:
            raise ValueError("Invalid Deoxys encounter seed")
        result[key] = value >> 30
    return result
