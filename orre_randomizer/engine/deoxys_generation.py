"""Seeded persistent Deoxys form tags, independent of native PID generation."""
from __future__ import annotations

from collections.abc import Callable

from ..deoxys import DEOXYS, form_seed
from .analyze_game import FormatError


def deoxys_pid_call(address, rng_offset, region, legacy_builder: Callable) -> bytes:
    """Call native generation once, then tag a newly initialized Deoxys record.

    r3..r7 retain the native ABI. r8 supplies only the initial form's upper two
    bits; it never seeds or rewrites PID/RNG. The original routine's result is
    returned intact. Existing tags and foreign reservations are not overwritten.
    Native construction at the qualified gift/starter sites has already cleared
    the reserved halfword. Trainer completion separately covers reused Shadow PIDs.
    """
    from .shiny_rules import _Code
    from ..deoxys_identity import FORM_TAG, form_offset
    c = _Code(address)
    c.emit(0x28080000)
    c.conditional(0x41820000, "legacy")
    c.emit(0x28030000)
    c.conditional(0x41820000, "legacy")
    c.emit(0xA1230000, 0x28090000 | DEOXYS)
    c.conditional(0x40820000, "legacy")
    c.emit(0x9421FFE0, 0x7C0802A6, 0x90010024, 0x90610008,
           0x550017BE, 0x60000000 | FORM_TAG, 0x9001000C)
    c.call(region.pid_generator)
    c.emit(0x81210008, 0xA0090000 | form_offset(region.game_id), 0x28000000)
    c.conditional(0x40820000, "return")
    c.emit(0x8001000C, 0xB0090000 | form_offset(region.game_id))
    c.label("return")
    c.emit(0x80010024, 0x7C0803A6, 0x38210020, 0x4E800020)
    while len(c.words) % 8:
        c.emit(0x60000000)
    c.label("legacy")
    prefix = c.finish()
    return prefix + legacy_builder(address + len(prefix), rng_offset, region)


def trainer_form_tag(address, continuation, tables, *, game_id, trainer_slot_count):
    """Tag the new trainer CK3 before its final native stat calculation.

    Both fresh and cached Shadow-PID paths reach this site. Native r31 is the
    temporary full record, r30 the Shadow ID, and [sp+48] the audited original
    trainer slot. No player-owned record or saved Shadow PID table is edited.
    """
    from .shiny_rules import _Code, SHADOW_COUNT
    from .gift_move_hooks import branch
    from ..deoxys_identity import FORM_TAG, form_offset
    trainer_table, shadow_table = tables
    offset = form_offset(game_id)
    c = _Code(address)
    c.emit(0xA17F0000, 0x280B0000 | DEOXYS)
    c.conditional(0x40820000, "native")
    c.emit(0xA01F0000 | offset, 0x28000000)
    c.conditional(0x40820000, "native")
    c.emit(0x281E0000)
    c.conditional(0x41820000, "trainer")
    c.emit(0x57CB063E, 0x280B0000 | SHADOW_COUNT)
    c.conditional(0x40800000, "native")
    c.emit(0x3D800000 | shadow_table >> 16, 0x618C0000 | (shadow_table & 0xFFFF))
    c.jump("lookup")
    c.label("trainer")
    c.emit(0x81610048, 0x556B043E, 0x280B0000 | trainer_slot_count)
    c.conditional(0x40800000, "native")
    c.emit(0x3D800000 | trainer_table >> 16, 0x618C0000 | (trainer_table & 0xFFFF))
    c.label("lookup")
    c.emit(0x556B103A, 0x7C0C582E, 0x28000000)
    c.conditional(0x41820000, "native")
    c.emit(0x540017BE, 0x60000000 | FORM_TAG, 0xB01F0000 | offset)
    c.label("native")
    c.emit(0x7FE3FB78, branch(address + len(c.words) * 4 + 4, continuation))
    return c.finish()


def colo_deoxys_seeds(original_rel, current_rel, original_dol, current_dol, seed,
                      trainer_aliases=(), *, trainer_special_aliases=(), extra_rows=()):
    """Identify final Deoxys encounters and preserve their aliases.

    A retained native Deoxys stays Normal Forme. A newly drawn Deoxys can use
    all four forms. Extra trainer rows use the report's slot/species/shadow_id
    and optional original_species fields, without reading past native tables.
    """
    from .dol_regions import special_targets
    from .inspect_tables import u16
    from .randomize_trainers import layout
    party = layout(original_rel)[0]["trainer_pokemon"]
    result = {}

    def add(key, original_species):
        chosen = form_seed(seed, "colo:" + key)
        if original_species == DEOXYS:
            chosen = (chosen & 0x3FFFFFFF) or 1
        if key in result and (result[key] >> 30) != (chosen >> 30):
            raise FormatError("Conflicting native Deoxys forms for one encounter")
        result[key] = chosen

    for slot in range(party["count"]):
        offset = party["offset"] + slot * party["stride"]
        if u16(current_rel, offset + 0xA) == DEOXYS:
            shadow = current_rel[offset + 3]
            add(f"shadow:{shadow}" if shadow else f"trainer:{slot}", u16(original_rel, offset + 0xA))
    for row in extra_rows:
        if row["species"] == DEOXYS:
            add(f"shadow:{row['shadow_id']}" if row.get("shadow_id") else f"trainer:{row['slot']}",
                row.get("original_species"))
    for original_slot, retry_slot in trainer_aliases:
        original_key, retry_key = f"trainer:{original_slot}", f"trainer:{retry_slot}"
        if original_key in result and retry_key in result:
            result[retry_key] = result[original_key]
    for target in special_targets(original_dol):
        if u16(current_dol, target["base"] + 2) == DEOXYS:
            add(f"special:{target['key']}", u16(original_dol, target["base"] + 2))
    for slot, key in trainer_special_aliases:
        if f"trainer:{slot}" in result and f"special:{key}" in result:
            result[f"trainer:{slot}"] = result[f"special:{key}"]
    return result
