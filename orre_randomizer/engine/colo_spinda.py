"""Identify the seeded Spinda generation calls in Colosseum's final data."""

from .dol_regions import special_targets
from .inspect_tables import u16
from .randomize_trainers import layout
from .spinda import SPINDA, spinda_pid_seed


ORDINARY_SPINDA_OT = 0x5350494E
_GIFT_OWNERS = {"plusle": 0x1911D, "ho-oh": 0x2740, "celebi-event": 0x7991, "pikachu-event": 0x7991}


def colo_spinda_pid(rng_seed, *, owner, gender, nature, shiny):
    """Mirror the verified Colosseum RNG for an encounter whose inputs are known."""
    if gender not in (-1, 0, 1, 2) or not -1 <= nature < 25:
        raise ValueError("invalid Colosseum Spinda PID constraints")
    gender = rng_seed >> 31 if gender == 2 else gender
    owner_xor = (owner >> 16) ^ (owner & 0xFFFF)
    state = rng_seed
    while True:
        state = (0x343FD * state + 0x269EC3) & 0xFFFFFFFF
        high = state >> 16
        state = (0x343FD * state + 0x269EC3) & 0xFFFFFFFF
        low = state >> 16
        pid = (high << 16) | low
        if (gender == -1 or int((low & 0xFF) < 127) == gender) and (nature == -1 or pid % 25 == nature):
            if shiny is None or ((high ^ low ^ owner_xor) < 8) == shiny:
                return pid


def colo_spinda_trainer_pid(original_rel, current_rel, seeds, slot, shiny):
    """Return the actual PID of a seeded ordinary trainer's Spinda."""
    seed = seeds.get(f"trainer:{slot}")
    if seed is None:
        return None
    party = layout(original_rel)[0]["trainer_pokemon"]
    offset = party["offset"] + slot * party["stride"]
    gender, nature = (value if value < 128 else value - 256 for value in current_rel[offset + 1:offset + 3])
    return colo_spinda_pid(seed, owner=ORDINARY_SPINDA_OT, gender=gender, nature=nature, shiny=shiny)


def colo_spinda_gift_pid(seeds, key, shiny):
    """Return the PID for a native reward whose OT is fixed on all three discs."""
    seed = seeds.get(f"special:{key}")
    if seed is None:
        return None
    return colo_spinda_pid(seed, owner=_GIFT_OWNERS[key], gender=-1, nature=-1, shiny=shiny)


def colo_spinda_seeds(original_rel, current_rel, original_dol, current_dol, seed, trainer_aliases=()):
    party = layout(original_rel)[0]["trainer_pokemon"]
    seeds = {}
    for slot in range(party["count"]):
        offset = party["offset"] + slot * party["stride"]
        if u16(current_rel, offset + 0xA) == SPINDA:
            shadow = current_rel[offset + 3]
            key = f"shadow:{shadow}" if shadow else f"trainer:{slot}"
            if key not in seeds:
                seeds[key] = spinda_pid_seed(seed, f"colo:{key}") or 1
    for original_slot, retry_slot in trainer_aliases:
        original_key, retry_key = f"trainer:{original_slot}", f"trainer:{retry_slot}"
        if original_key in seeds and retry_key in seeds:
            seeds[retry_key] = seeds[original_key]
    for target in special_targets(original_dol):
        if u16(current_dol, target["base"] + 2) == SPINDA:
            key = f"special:{target['key']}"
            seeds[key] = spinda_pid_seed(seed, f"colo:{key}") or 1
    return seeds


def colo_spinda_shadow_traits(original_rel, current_rel):
    """Report stable native gender/nature arguments per Spinda Shadow ID."""
    party = layout(original_rel)[0]["trainer_pokemon"]
    traits = {}
    for slot in range(party["count"]):
        offset = party["offset"] + slot * party["stride"]
        gender, nature, shadow = current_rel[offset + 1:offset + 4]
        if shadow and u16(current_rel, offset + 0xA) == SPINDA:
            traits.setdefault(shadow, set()).add((gender, nature))
    return {shadow: tuple(value if value < 128 else value - 256 for value in next(iter(pair)))
            for shadow, pair in traits.items() if len(pair) == 1}
