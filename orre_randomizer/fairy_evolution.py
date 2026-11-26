"""Offer explicit Fairy evolution moves through each game's native dialogue.

The native evolution producer builds a temporary evolved Pokemon and a bounded
queue of unknown moves. Its existing caller presents the learn/forget choices
and commits the temporary record only after the evolution succeeds. This hook
adds two explicit evolution events to that queue; it does not reinterpret a
level-zero terminator, replace a move slot or mutate a saved Pokemon directly.
"""
from __future__ import annotations

import hashlib
import struct

from .castform_portraits import _reservation
from .deoxys_meteorite import _offset, _read
from .engine.analyze_game import FormatError, parse_dol
from .engine.gift_move_hooks import _arena_guard, branch
from .engine.shiny_rules import _Code

VERSION = "native-fairy-evolution-learning-v1"
# Native species IDs are deliberately distinct from National Dex IDs.
# Togetic National 176 / native 176; Gardevoir National 282 / native 394.
EVOLUTION_EVENTS = ((176, 378), (394, 380))
QUEUE_CAPACITY = 20

# Exact original producer boundaries and native known-move checker calls.
# The Japanese XD compiler allocates its temporary Pokemon to r29, not r27.
# SHA-256 covers the entire original DOL and the complete producer function.
_LAYOUTS = {
    "GC6P01": ("a788176a45eb88dbd227246a7205ab9856bc79f3cca7e4a0f5376cf466664df5",
               0x8012C6D8, 0x1A4, "611d086dd074b2304e5436f54d3bd7ddf2067c44b4bc232811d34e9a430205c8",
               0x8012C864, 0x80127CD0, 27),
    "GC6E01": ("7e6c00a3bd632126d5466cbab856c63ac3c52a5da20b60dba7e756538152c9f4",
               0x80128524, 0x1A4, "142418534011fd84b64315b619bdffd79f8bcad06282893319946ae769c4be1e",
               0x801286B0, 0x80123B5C, 27),
    "GC6J01": ("64cedd009afb5b944310bd626bed4890de200fa978fea72b58f2c80c2b2ebaf2",
               0x80125CC4, 0x1A4, "c29036e99f89b5c7e4d17867c29f44ab57069eb466404aa1b77874597dff362e",
               0x80125E50, 0x80121308, 27),
    "GXXP01": ("a90eae103e6e8471e41c92df1f894f98c2f98d1f9f3a0aca84964492135f5cfd",
               0x8014B9E4, 0x1C8, "b9e7b4a88d53cb096a1bb56ee7582ac873c81709c4b2fdf23526219c19cf6c9d",
               0x8014BB94, 0x80142874, 27),
    "GXXE01": ("c8659341c252d1b088753d508769344eb6f092b5da5cc7cc0ce1560b32478c15",
               0x8014A120, 0x1C8, "b2d053970b4faba0037de66c89c9c360ba1675c62ebc985514e7ec3df7ee0b1f",
               0x8014A2D0, 0x80140FB0, 27),
    "GXXJ01": ("14c129cc0f79682574f635290b09e37fa2a652ac5aa5565281bd583c31c5d702",
               0x801454B8, 0x18C, "979d258efe42e91dd5f10b61013ab667342d5b399c63f5ddef8b80a55b9dd311",
               0x8014562C, 0x8013C3BC, 29),
}


def _queue_stub(address: int, continuation: int, known_checker: int, pokemon_register: int) -> bytes:
    """Inline successful-producer continuation; r30=queue and r31=count."""
    if pokemon_register not in (27, 29):
        raise ValueError("Unknown native evolution register allocation")
    code = _Code(address)
    code.emit(0x9421FFE0, 0x7C0802A6, 0x90010024)  # private frame and LR
    code.emit(0x281F0014)  # native count must leave room in the 20-entry queue
    code.conditional(0x40800000, "done")
    code.emit(0xA0000000 | pokemon_register << 16)  # current evolved species
    for species, move in EVOLUTION_EVENTS:
        code.emit(0x28000000 | species)
        code.conditional(0x41820000, f"species_{species}")
    code.jump("done")
    for species, move in EVOLUTION_EVENTS:
        code.label(f"species_{species}")
        code.emit(0x39600000 | move)  # r11=new ordinary move
        code.jump("event")
    code.label("event")
    code.emit(0x91610008, 0x39400000, 0x7FCCF378)  # save move, index=0, cursor=r30
    code.label("scan")
    code.emit(0x7C0AF840)  # cmplw r10,r31
    code.conditional(0x40800000, "check_known")
    code.emit(0xA00C0000, 0x7C005840)  # lhz r0,0(r12); cmplw r0,r11
    code.conditional(0x41820000, "done")
    code.emit(0x394A0001, 0x398C0002)
    code.jump("scan")
    code.label("check_known")
    code.emit(0x7C000378 | pokemon_register << 21 | 3 << 16 | pokemon_register << 11,
              0x7D645B78)  # r3=record, r4=move
    code.call(known_checker)
    code.emit(0x7C600774, 0x2C00FFFF)  # native signed-byte -1 means not known
    code.conditional(0x40820000, "done")
    code.emit(0x81610008, 0x57EC083C, 0x7D9E6214, 0xB16C0000, 0x3BFF0001)
    code.label("done")
    code.emit(0x80010024, 0x7C0803A6, 0x38210020, 0x7FE3FB78)
    code.emit(branch(address + len(code.words) * 4, continuation))
    return code.finish()


def qualify_evolution_learning(original_dol: bytes, game_id: str) -> dict:
    layout = _LAYOUTS.get(game_id)
    if layout is None or hashlib.sha256(original_dol).hexdigest() != layout[0]:
        raise FormatError("Unknown original Fairy evolution executable")
    digest, start, size, expected, site, known, owner = layout
    if hashlib.sha256(_read(original_dol, start, size)).hexdigest() != expected:
        raise FormatError("Unqualified native evolution producer")
    if _read(original_dol, site, 4) != bytes.fromhex("7fe3fb78"):
        raise FormatError("Unqualified native evolution queue return")
    return {"game_id": game_id, "original_dol_sha256": digest,
            "producer_address": start, "producer_size": size, "producer_sha256": expected,
            "hook_address": site, "known_move_checker": known, "pokemon_register": owner}


def install_evolution_learning(original_dol: bytes, current_dol: bytes, game_id: str, *,
                               additional_tms_report: dict) -> tuple[bytes, dict]:
    """Append after verified new moves; return a candidate requiring Dolphin QA.

    The installation report authenticates the actual added move rows and owned
    native move getters. No new ID is accepted merely because it was allocated.
    """
    from .fairy_tms import read_installed_content
    layout = qualify_evolution_learning(original_dol, game_id)
    if not isinstance(additional_tms_report, dict) or additional_tms_report.get("game_id") != game_id:
        raise FormatError("Fairy evolution learning requires the matching installed move report")
    installed = read_installed_content(current_dol, additional_tms_report)
    if not {move for _species, move in EVOLUTION_EVENTS} <= set(installed["moves"]):
        raise FormatError("Fairy evolution moves are not installed")
    start, size = layout["producer_address"], layout["producer_size"]
    if _read(current_dol, start, size) != _read(original_dol, start, size):
        raise FormatError("The native evolution producer has already been modified")
    checker, checker_size = layout["known_move_checker"], 0x8C if game_id.startswith("GXX") else 0xF8
    if _read(current_dol, checker, checker_size) != _read(original_dol, checker, checker_size):
        raise FormatError("The native evolution known-move checker has already been modified")
    offset, ram, setter, store, code = _reservation(original_dol, current_dol, game_id)
    site = layout["hook_address"]
    stub = ram + len(code)
    payload = _queue_stub(stub, site + 4, layout["known_move_checker"], layout["pokemon_register"])
    code.extend(payload)
    end = ram + len(code)
    if end >= 0x81700000:
        raise FormatError("Fairy evolution learning exceeds reserved memory")
    code[:32] = _arena_guard(end, store)
    output = bytearray(current_dol[:offset])
    output.extend(bytes(offset - len(output)))
    output.extend(code)
    site_offset, setter_offset = _offset(original_dol, site), _offset(original_dol, setter)
    for pos, value in ((8, offset), (0x50, ram), (0x98, len(code)),
                       (setter_offset, branch(setter, ram)), (site_offset, branch(site, stub))):
        struct.pack_into(">I", output, pos, value)
    allowed = [(8, 12), (0x50, 0x54), (0x98, 0x9C), (offset, offset + 32),
               (setter_offset, setter_offset + 4), (site_offset, site_offset + 4)]
    if any(before != after and not any(lo <= pos < hi for lo, hi in allowed)
           for pos, (before, after) in enumerate(zip(current_dol, output))):
        raise FormatError("Fairy evolution learning changed an unrelated executable byte")
    section = next(row for row in parse_dol(bytes(output))["sections"] if row["name"] == "text2")
    if (section["offset"], section["ram_address"], section["size"]) != (offset, ram, len(code)):
        raise FormatError("Fairy evolution learning failed section readback")
    return bytes(output), {
        "version": VERSION, **layout, "stub_address": stub, "stub_size": len(payload),
        "stub_sha256": hashlib.sha256(payload).hexdigest(), "queue_capacity": QUEUE_CAPACITY,
        "events": [{"species_index": species, "move": move} for species, move in EVOLUTION_EVENTS],
        "level_zero_terminators_preserved": True, "native_learning_dialogue": True,
        "native_evolution_cancel_and_commit_preserved": True, "no_direct_pokemon_writes": True,
        "bytes_appended": len(output) - len(current_dol),
        "runtime_validation": "requires Dolphin evolution, four moves, refusal, cancellation and save reload",
    }
