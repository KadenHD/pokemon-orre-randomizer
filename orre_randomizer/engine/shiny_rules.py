"""Regional seed-derived or native-RNG shiny status, retaining the Gen III test.

Seeded encounter flags or one legacy native RNG coin select never/always for
the native constrained PID generator. Shadow PIDs use the player's SID/TID;
the later OT assignment is
aligned to that same owner for unpurified Shadows only. No display threshold,
save file, captured PID, nature or gender rule is rewritten.

Spinda can start the same native PID search from a private encounter seed.
Ordinary Spinda in NPC teams use a fixed OT ID so an enemy trainer's random
OT cannot change their predetermined motif or shiny result.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
import hashlib
import struct

from .analyze_game import FormatError, parse_dol
from .gift_move_hooks import (ORIGINAL_DOL_SHA256, SECTION_RAM, SET_ARENA_LO,
                              TEXT_TO_RAM, ARENA_LO_STORE, _arena_guard, _branch_target, branch)
from .dol_regions import DolLayout, PAL, dol_layout
from .colo_spinda import ORDINARY_SPINDA_OT
from .spinda import SPINDA

VERSION = "native-shiny-generation-v1"
SEEDED_VERSION = "seeded-shiny-status-v1"
PID_GENERATOR = 0x80128584
NATIVE_RNG = 0x800E42A4
OT_EXIT = 0x8012811C
OT_EXIT_WORD = 0xBB410008
PLAYER_POINTER = 0x804C8268
PID_CALLS = {"celebi-event": 0x80134940, "pikachu-event": 0x80134A50,
             "ho-oh": 0x80134B70, "plusle": 0x80134C5C,
             "espeon": 0x80134D54, "umbreon": 0x80134E7C,
             "trainers": 0x801FEC98}
COIN_RANGE = 1 << 32
TRAINER_INDEX_HOOK = 0x801FE83C
TRAINER_INDEX_WORD = 0x7C7C1B78
TRAINER_SLOT_COUNT = 5510
SHADOW_COUNT = 97


def seeded_coin(seed: str, key: str) -> int:
    """Versioned per-encounter draw, independent of species, time and OT IDs."""
    if not isinstance(seed, str):
        raise ValueError("seed must be text")
    raw = seed.encode("utf-8")
    if not seed.strip() or not 1 <= len(raw) <= 256:
        raise ValueError("seed must contain 1..256 UTF-8 bytes")
    prefix = SEEDED_VERSION.encode("ascii") + b"\0" + len(raw).to_bytes(2, "big") + raw
    return int.from_bytes(hashlib.sha256(prefix + b"\0" + key.encode("ascii")).digest()[:4], "big")


def seeded_status(seed: str, key: str, percent) -> bool:
    return seeded_coin(seed, key) < chance_threshold(percent)


def chance_threshold(percent) -> int:
    if type(percent) not in (int, float) or not 0 <= percent <= 100:
        raise ValueError("shiny chance must be a finite percentage from 0 to 100")
    if percent == 0:
        return 0
    if percent == 100:
        return COIN_RANGE
    value = int((Decimal(str(percent)) * COIN_RANGE / 100).to_integral_value(rounding=ROUND_HALF_UP))
    return max(1, min(COIN_RANGE - 1, value))


class _Code:
    """Small relocation builder for the fixed, audited PPC instruction set."""
    def __init__(self, address):
        self.address, self.words, self.labels, self.fixups = address, [], {}, []

    def emit(self, *words):
        self.words.extend(words)

    def label(self, name):
        if name in self.labels:
            raise AssertionError("duplicate PPC label")
        self.labels[name] = len(self.words) * 4

    def conditional(self, word, label):
        self.fixups.append((len(self.words), word, label))
        self.emit(0)

    def jump(self, label):
        self.conditional(0x48000000, label)

    def call(self, target):
        self.emit(branch(self.address + len(self.words) * 4, target, link=True))

    def finish(self):
        for index, word, label in self.fixups:
            offset = self.labels[label] - index * 4
            if offset % 4 or not -32768 <= offset <= 32764:
                raise FormatError("shiny conditional branch is out of range")
            self.words[index] = word | (offset & (0x03FFFFFC if word >> 26 == 18 else 0xFFFC))
        data = struct.pack(f">{len(self.words)}I", *self.words)
        return data + bytes.fromhex("60000000") * ((-len(data) % 32) // 4)


def _emit_spinda_lookup(c, tables):
    trainer_seeds, shadow_seeds = tables
    c.emit(0x39000000, 0x281E0000)  # default seed 0; native Shadow ID in r30
    c.conditional(0x41820000, "spinda_trainer")
    c.emit(0x57CB063E, 0x280B0000 | SHADOW_COUNT)
    c.conditional(0x40800000, "spinda_ready")
    c.emit(0x3D800000 | (shadow_seeds >> 16), 0x618C0000 | (shadow_seeds & 0xFFFF))
    c.jump("spinda_lookup")
    c.label("spinda_trainer")
    c.emit(0x81610088, 0x556B043E, 0x280B0000 | TRAINER_SLOT_COUNT)
    c.conditional(0x40800000, "spinda_ready")
    c.emit(0x3D800000 | (trainer_seeds >> 16), 0x618C0000 | (trainer_seeds & 0xFFFF))
    c.label("spinda_lookup")
    c.emit(0x556B103A, 0x7D0C582E)  # slwi r11,2; lwzx r8,r12,r11
    c.label("spinda_ready")


def _emit_spinda_trainer_owner(c):
    c.emit(0x281E0000)  # Never change a catchable Shadow's owner.
    c.conditional(0x40820000, "spinda_owner_ready")
    c.emit(0x28080000)
    c.conditional(0x41820000, "spinda_owner_ready")
    c.emit(0x3CE00000 | (ORDINARY_SPINDA_OT >> 16), 0x60E70000 | (ORDINARY_SPINDA_OT & 0xFFFF))
    c.label("spinda_owner_ready")


def _spinda_party_owner(address, party_return, native_ot):
    c = _Code(address)
    c.emit(0x81610164, 0x3D800000 | (party_return >> 16), 0x618C0000 | (party_return & 0xFFFF),
           0x7C0B6040)  # Only the native story trainer party builder calls from this LR.
    c.conditional(0x40820000, "native_ot")
    c.emit(0xA1630000, 0x280B0000 | SPINDA)
    c.conditional(0x40820000, "native_ot")
    c.emit(0xA16300D8, 0x280B0000)
    c.conditional(0x40820000, "native_ot")
    c.emit(0x3D000000 | (ORDINARY_SPINDA_OT >> 16), 0x61080000 | (ORDINARY_SPINDA_OT & 0xFFFF))
    c.label("native_ot")
    c.emit(branch(address + len(c.words) * 4, native_ot))
    return c.finish()


def _spinda_party_call(original, current, region):
    party_call = region.trainer_function - 0xF4
    party = _branch_target(party_call, _word(original, party_call - TEXT_TO_RAM))
    owner_call = party + 0xB0
    native_ot = _branch_target(owner_call, _word(original, owner_call - TEXT_TO_RAM))
    signatures = {party: 0x9421FEA0, party + 8: 0x90010164, owner_call - 0xC: 0x7FA8EB78,
                  owner_call - 4: 0x38610008, owner_call: branch(owner_call, native_ot, link=True),
                  party_call: branch(party_call, party, link=True), party_call + 4: 0x7C600735}
    for address, expected in signatures.items():
        if any(_word(data, address - TEXT_TO_RAM) != expected for data in (original, current)):
            raise FormatError("native Colosseum Spinda party signature changed")
    return owner_call, party_call + 4, native_ot


def _spinda_pid_call(address, rng_offset, region):
    """Native PID ABI plus r8 = private LCG starting state, zero to opt out."""
    c = _Code(address)
    c.emit(0x28080000)
    c.conditional(0x41820000, "native")
    c.emit(0x28030000)
    c.conditional(0x41820000, "native")
    c.emit(0xA1230000, 0x28090000 | SPINDA)  # CK3's native species getter reads +0
    c.conditional(0x40820000, "native")
    c.emit(0x2C040002)
    c.conditional(0x40820000, "begin")
    # 2 retains the gender of the constructor's random PID. Draw that
    # otherwise unconstrained gender from this encounter's seed instead.
    c.emit(0x55040FFE)  # srwi r4,r8,31
    c.label("begin")
    c.emit(0x9421FFE0, 0x7C0802A6, 0x90010024,
           0x812D0000 | rng_offset, 0x80090000, 0x91210008, 0x9001000C, 0x91090000)
    c.call(region.pid_generator)
    c.emit(0x81210008, 0x8001000C, 0x90090000,
           0x80010024, 0x7C0803A6, 0x38210020, 0x4E800020)
    c.label("native")
    c.emit(branch(address + len(c.words) * 4, region.pid_generator))
    return c.finish()


def _spinda_rng_offset(original, current, region):
    call = region.native_rng + 0xC
    original_call = _word(original, call - TEXT_TO_RAM)
    target = _branch_target(call, original_call)
    rng_offset = 0x8464 if region.game_id == "GC6J01" else 0x8474
    expected = (0x80AD0000 | rng_offset, 0x3C800003, 0x388443FD, 0x806D0000 | rng_offset,
                0x80050000, 0x7C8021D6, 0x3C840027, 0x38049EC3, 0x90030000,
                0x806D0000 | rng_offset, 0x80030000, 0x5403843E, 0x4E800020)
    if (_word(current, call - TEXT_TO_RAM) != original_call
            or any(struct.unpack_from(">13I", data, target - TEXT_TO_RAM) != expected
                   for data in (original, current))):
        raise FormatError("native Colosseum PID RNG signature changed")
    return rng_offset


def _pid_wrapper(address: int, threshold: int | None, *, trainers=False,
                 region: DolLayout = PAL, spinda_pid=None, spinda_seed=None,
                 spinda_tables=None) -> bytes:
    if threshold is not None and (type(threshold) is not int or not 0 <= threshold <= COIN_RANGE):
        raise ValueError("invalid shiny coin threshold")
    c = _Code(address)
    c.emit(0x9421FFC0, 0x7C0802A6, 0x90010044,  # frame and LR
           0x90610008, 0x9081000C, 0x90A10010, 0x90E10018)  # r3,r4,r5,r7
    if trainers and threshold is not None:
        # r30 is the verified native caller's is-Shadow flag. Non-Shadow
        # opponents retain their own trainer ID and use the same custom chance.
        c.emit(0x281E0000)  # cmplwi r30,0
        c.conditional(0x41820000, "owner_ready")
        c.emit(0x3D600000 | (region.player_pointer >> 16),
               0x616B0000 | (region.player_pointer & 0xFFFF), 0x816B0000, 0x2C0B0000)
        c.conditional(0x41820000, "owner_ready")
        c.emit(0x80EB009C, 0x90E10018)  # player SID/TID32 -> saved r7
        c.label("owner_ready")
    if threshold in (0, COIN_RANGE):
        c.emit(0x38C00000 | int(threshold == COIN_RANGE))
    elif threshold is not None:
        # Two native 16-bit draws form one 32-bit coin, before PID rerolls.
        c.call(region.native_rng)
        c.emit(0x5463801E, 0x9061001C)  # slwi r3,16; store high half
        c.call(region.native_rng)
        c.emit(0x5463043E, 0x8081001C, 0x7C632378,  # low16, load high, or
               0x3C800000 | (threshold >> 16), 0x60840000 | (threshold & 0xFFFF),
               0x7C032040, 0x38C00000)  # cmplw r3,r4; li r6,0
        c.conditional(0x40800000, "coin_ready")  # bge = not shiny
        c.emit(0x38C00001)
        c.label("coin_ready")
    if spinda_tables is not None:
        _emit_spinda_lookup(c, spinda_tables)
    if spinda_seed is not None:
        c.emit(0x3D000000 | (spinda_seed >> 16), 0x61080000 | (spinda_seed & 0xFFFF))
    c.emit(0x80610008, 0x8081000C, 0x80A10010, 0x80E10018)
    if spinda_tables is not None:
        _emit_spinda_trainer_owner(c)
    c.call(spinda_pid if spinda_seed is not None or spinda_tables is not None else region.pid_generator)
    c.emit(0x80010044, 0x7C0803A6, 0x38210040, 0x4E800020)
    return c.finish()


def _ot_wrapper(address: int, *, region: DolLayout = PAL) -> bytes:
    c = _Code(address)
    c.emit(0x281A0000)  # original r26 = CK3 target
    c.conditional(0x41820000, "return")
    c.emit(0xA01A00D8, 0x28000000)  # Shadow ID must be nonzero
    c.conditional(0x41820000, "return")
    c.emit(0x801A00DC, 0x2C00FF9C)  # purification -100 = already purified
    c.conditional(0x41820000, "return")
    c.emit(0x3D800000 | (region.player_pointer >> 16),
           0x618C0000 | (region.player_pointer & 0xFFFF), 0x818C0000, 0x2C0C0000)
    c.conditional(0x41820000, "return")
    c.emit(0x800C009C, 0x901A0014)  # whole SID/TID DWORD, never PID
    c.label("return")
    c.emit(OT_EXIT_WORD)  # displaced lmw r26,8(sp)
    c.emit(branch(address + len(c.words) * 4, region.ot_exit + 4))
    return c.finish()


def _index_trampoline(address: int, *, region: DolLayout = PAL) -> bytes:
    # The original frame reserves 0x80 bytes. Native arrays end at 0x47 and
    # saved r19..r31 begin at 0x4C: the word at +0x48 is unused throughout it.
    c = _Code(address)
    c.emit(0x90610048, TRAINER_INDEX_WORD)
    c.emit(branch(address + 8, region.trainer_index_hook + 4))
    return c.finish()


def _seeded_trainer_wrapper(address: int, trainer_flags: int, shadow_flags: int,
                            *, region: DolLayout = PAL, spinda_pid=None, spinda_tables=None) -> bytes:
    c = _Code(address)
    c.emit(0x9421FFC0, 0x7C0802A6, 0x90010044,
           0x90610008, 0x9081000C, 0x90A10010, 0x90E10018)
    # r30 is the actual native ShadowID; zero denotes an ordinary trainer slot.
    c.emit(0x281E0000)
    c.conditional(0x41820000, "trainer_slot")
    c.emit(0x3D600000 | (region.player_pointer >> 16),
           0x616B0000 | (region.player_pointer & 0xFFFF), 0x816B0000, 0x2C0B0000)
    c.conditional(0x41820000, "shadow_owner_ready")
    c.emit(0x80EB009C, 0x90E10018)
    c.label("shadow_owner_ready")
    c.emit(0x57CB063E, 0x280B0000 | SHADOW_COUNT)  # clrlwi r11,r30,24
    c.conditional(0x40800000, "invalid_index")
    c.emit(0x3D800000 | (shadow_flags >> 16), 0x618C0000 | (shadow_flags & 0xFFFF))
    c.jump("lookup")
    c.label("trainer_slot")
    c.emit(0x81610088, 0x556B043E, 0x280B0000 | TRAINER_SLOT_COUNT)
    c.conditional(0x40800000, "invalid_index")
    c.emit(0x3D800000 | (trainer_flags >> 16), 0x618C0000 | (trainer_flags & 0xFFFF))
    c.label("lookup")
    c.emit(0x7CCC58AE)  # lbzx r6,r12,r11 (one flag per native encounter key)
    c.jump("policy_ready")
    c.label("invalid_index")
    c.emit(0x38C00000)  # safe non-shiny fallback; never read beyond either table
    c.label("policy_ready")
    if spinda_tables is not None:
        _emit_spinda_lookup(c, spinda_tables)
    c.emit(0x80610008, 0x8081000C, 0x80A10010, 0x80E10018)
    if spinda_tables is not None:
        _emit_spinda_trainer_owner(c)
    c.call(spinda_pid if spinda_tables is not None else region.pid_generator)
    c.emit(0x80010044, 0x7C0803A6, 0x38210040, 0x4E800020)
    return c.finish()


def _word(data, offset):
    return struct.unpack_from(">I", data, offset)[0]


def apply_shiny_rules(original: bytes, current: bytes, options, *, seed: str | None = None,
                      trainer_aliases: tuple[tuple[int, int], ...] = (),
                      spinda_seeds=None) -> tuple[bytes, dict]:
    spinda_seeds = spinda_seeds or {}
    custom = options.custom_shinies
    if not custom and not spinda_seeds:
        return current, {"version": VERSION, "enabled": False}
    threshold = chance_threshold(options.shiny_chance_percent) if custom else None
    seeded = custom and options.seeded_shinies
    spinda_trainers = any(not key.startswith("special:") for key in spinda_seeds)
    spinda_ordinary = any(key.startswith("trainer:") for key in spinda_seeds)
    needs_index = seeded or spinda_trainers
    if seeded:
        seeded_coin(seed, "validation")
    region = dol_layout(original)
    SECTION_RAM, SET_ARENA_LO = region.section_ram, region.set_arena_lo
    ARENA_LO_STORE, PID_GENERATOR = region.arena_lo_store, region.pid_generator
    NATIVE_RNG, OT_EXIT = region.native_rng, region.ot_exit
    PID_CALLS, TRAINER_INDEX_HOOK = region.pid_calls, region.trainer_index_hook
    if len(current) < len(original):
        raise FormatError("shiny hooks received a truncated DOL")
    for offset in range(0, 0x100, 4):
        if offset not in (0x08, 0x50, 0x98) and current[offset:offset + 4] != original[offset:offset + 4]:
            raise FormatError("shiny hooks received an unsupported DOL header")
    signatures = {OT_EXIT: OT_EXIT_WORD, PID_GENERATOR: 0x9421FFC0,
                  NATIVE_RNG: 0x9421FFF0,
                  PID_GENERATOR + 0x434: 0x38600008, PID_GENERATOR + 0x460: 0x38600008,
                  PID_CALLS['trainers'] - 4: 0x38C00000, PID_CALLS['espeon'] - 4: 0x38C00000,
                  region.pokemon_store_ot: 0x90830014,
                  0x80003324: 0x3C200000 | (region.stack_top >> 16),
                  0x80003328: 0x60210000 | (region.stack_top & 0xFFFF),
                  region.arena_initialize: 0x3C600000 | (SECTION_RAM >> 16),
                  region.arena_initialize + 4: 0x38630000 | (SECTION_RAM & 0xFFFF),
                  region.get_arena_lo: ARENA_LO_STORE - 0x10000000,
                  region.get_arena_lo + 4: 0x4E800020,
                  region.player_getter: region.player_getter_word,
                  region.player_getter + 4: 0x4E800020}
    if needs_index:
        base = region.trainer_function
        signatures.update({base: 0x9421FF80, base + 0x14: 0xBE61004C,
            TRAINER_INDEX_HOOK: TRAINER_INDEX_WORD, base + 0x8C: 0x547E063E,
            base + 0x248: 0x7FD7F378, base + 0x424: 0x4182003C,
            base + 0x438: 0x40820028, base + 0x440: region.shadow_pid_fetch_words[0],
            base + 0x45C: 0x48000034, base + 0x4D0: region.shadow_pid_fetch_words[1]})
    for address, expected in signatures.items():
        if any(_word(data, address - TEXT_TO_RAM) != expected for data in (original, current)):
            raise FormatError(f"native shiny signature changed at {address:#x}")
    for address in PID_CALLS.values():
        expected = branch(address, PID_GENERATOR, link=True)
        if any(_word(data, address - TEXT_TO_RAM) != expected for data in (original, current)):
            raise FormatError("native PID generation call changed")
    if any(_word(original, offset) for offset in (0x08, 0x50, 0x98)):
        raise FormatError("original DOL text2 slot is occupied")
    section_offset = (len(original) + 31) // 32 * 32
    previous_size = 0
    if _word(current, 0x98):
        previous_size = _word(current, 0x98)
        if ((_word(current, 0x08), _word(current, 0x50)) != (section_offset, SECTION_RAM)
                or section_offset + previous_size != len(current) or previous_size % 32
                or current[section_offset:section_offset + 32] != _arena_guard(SECTION_RAM + previous_size, ARENA_LO_STORE)
                or _word(current, SET_ARENA_LO - TEXT_TO_RAM) != branch(SET_ARENA_LO, SECTION_RAM)):
            raise FormatError("unsupported existing DOL code reservation")
        code = bytearray(current[section_offset:])
    else:
        if (len(current) != len(original) or any(_word(current, o) for o in (0x08, 0x50))
                or _word(current, SET_ARENA_LO - TEXT_TO_RAM) != ARENA_LO_STORE):
            raise FormatError("unexpected DOL layout before shiny reservation")
        code = bytearray(32)
    original_descriptor = parse_dol(original)
    if original_descriptor["bss_ram_address"] + original_descriptor["bss_size"] >= SECTION_RAM:
        raise FormatError("native BSS overlaps shiny code reservation")
    hooks = []
    decisions, tables_report, index_address = None, None, None
    gift_addresses = {}
    trainer_address = None
    spinda_pid, spinda_tables = None, None
    if spinda_seeds:
        spinda_pid = SECTION_RAM + len(code)
        code.extend(_spinda_pid_call(spinda_pid, _spinda_rng_offset(original, current, region), region))
    if spinda_trainers:
        trainer_seeds = SECTION_RAM + len(code)
        code.extend(struct.pack(f">{TRAINER_SLOT_COUNT}I", *(
            spinda_seeds.get(f"trainer:{i}", 0) for i in range(TRAINER_SLOT_COUNT))))
        shadow_seeds = SECTION_RAM + len(code)
        code.extend(struct.pack(f">{SHADOW_COUNT}I", *(
            spinda_seeds.get(f"shadow:{i}", 0) for i in range(SHADOW_COUNT))))
        code.extend(bytes((-len(code)) % 32))
        spinda_tables = trainer_seeds, shadow_seeds
    if seeded:
        specials = {key: seeded_coin(seed, "special:" + key) < threshold
                    for key in PID_CALLS if key != "trainers"}
        trainer_data = bytearray(seeded_coin(seed, f"trainer:{index}") < threshold for index in range(TRAINER_SLOT_COUNT))
        for battle, retry in trainer_aliases:
            trainer_data[retry] = trainer_data[battle]
        shadow_data = bytes(seeded_coin(seed, f"shadow:{sid}") < threshold for sid in range(SHADOW_COUNT))
        trainer_flags = SECTION_RAM + len(code)
        code.extend(trainer_data)
        shadow_flags = SECTION_RAM + len(code)
        code.extend(shadow_data)
        code.extend(bytes((-len(code)) % 32))
        for key, shiny in specials.items():
            gift_addresses[key] = SECTION_RAM + len(code)
            code.extend(_pid_wrapper(gift_addresses[key], COIN_RANGE if shiny else 0, region=region,
                                     spinda_pid=spinda_pid, spinda_seed=spinda_seeds.get(f"special:{key}")))
        index_address = SECTION_RAM + len(code)
        code.extend(_index_trampoline(index_address, region=region))
        trainer_address = SECTION_RAM + len(code)
        code.extend(_seeded_trainer_wrapper(trainer_address, trainer_flags, shadow_flags, region=region,
                                            spinda_pid=spinda_pid, spinda_tables=spinda_tables))
        decisions = {"specials": specials,
                     "shadows": {str(i): bool(value) for i, value in enumerate(shadow_data)},
                     "trainer_slots": {str(i): bool(value) for i, value in enumerate(trainer_data)}}
        tables_report = {"trainer_slots": {"address": trainer_flags, "count": len(trainer_data),
                                           "sha256": hashlib.sha256(trainer_data).hexdigest()},
                         "shadows": {"address": shadow_flags, "count": len(shadow_data),
                                     "sha256": hashlib.sha256(shadow_data).hexdigest()}}
    else:
        if custom:
            gift_address = SECTION_RAM + len(code)
            code.extend(_pid_wrapper(gift_address, threshold, region=region))
            gift_addresses = {key: gift_address for key in PID_CALLS if key != "trainers"}
        for key in PID_CALLS:
            spinda_seed = spinda_seeds.get(f"special:{key}")
            if spinda_seed is not None:
                gift_addresses[key] = SECTION_RAM + len(code)
                code.extend(_pid_wrapper(gift_addresses[key], threshold, region=region,
                                         spinda_pid=spinda_pid, spinda_seed=spinda_seed))
        if needs_index:
            index_address = SECTION_RAM + len(code)
            code.extend(_index_trampoline(index_address, region=region))
        if custom or spinda_trainers:
            trainer_address = SECTION_RAM + len(code)
            code.extend(_pid_wrapper(trainer_address, threshold, trainers=True, region=region,
                                     spinda_pid=spinda_pid, spinda_tables=spinda_tables))
    ot_address = None
    if custom:
        ot_address = SECTION_RAM + len(code)
        code.extend(_ot_wrapper(ot_address, region=region))
    party_hook = None
    if spinda_ordinary:
        owner_call, party_return, native_ot = _spinda_party_call(original, current, region)
        party_hook = SECTION_RAM + len(code)
        code.extend(_spinda_party_owner(party_hook, party_return, native_ot))
    reserved_end = SECTION_RAM + len(code)
    if reserved_end % 32 or reserved_end >= 0x81700000:
        raise FormatError("shiny code exceeds supported arena reservation")
    code[:32] = _arena_guard(reserved_end, ARENA_LO_STORE)
    output = bytearray(current[:section_offset])
    output.extend(bytes(section_offset - len(output)))
    output.extend(code)
    ranges = [(0x08, 0x0C), (0x50, 0x54), (0x98, 0x9C),
              (SET_ARENA_LO - TEXT_TO_RAM, SET_ARENA_LO - TEXT_TO_RAM + 4),
              (section_offset, section_offset + 32), (len(current), len(output))]
    for offset, word in ((0x08, section_offset), (0x50, SECTION_RAM), (0x98, len(code)),
                         (SET_ARENA_LO - TEXT_TO_RAM, branch(SET_ARENA_LO, SECTION_RAM))):
        struct.pack_into(">I", output, offset, word)
    for key, address in PID_CALLS.items():
        target = trainer_address if key == "trainers" else gift_addresses.get(key)
        if target is None:
            continue
        offset = address - TEXT_TO_RAM
        struct.pack_into(">I", output, offset, branch(address, target, link=True))
        ranges.append((offset, offset + 4))
        hooks.append({"key": key, "call_address": address, "wrapper_address": target})
    if needs_index:
        offset = TRAINER_INDEX_HOOK - TEXT_TO_RAM
        struct.pack_into(">I", output, offset, branch(TRAINER_INDEX_HOOK, index_address))
        ranges.append((offset, offset + 4))
    if ot_address is not None:
        offset = OT_EXIT - TEXT_TO_RAM
        struct.pack_into(">I", output, offset, branch(OT_EXIT, ot_address))
        ranges.append((offset, offset + 4))
    if party_hook is not None:
        offset = owner_call - TEXT_TO_RAM
        struct.pack_into(">I", output, offset, branch(owner_call, party_hook, link=True))
        ranges.append((offset, offset + 4))
    if any(a != b and not any(lo <= i < hi for lo, hi in ranges)
           for i, (a, b) in enumerate(zip(current, output))):
        raise FormatError("shiny patch exceeded its exact whitelist")
    added = next(s for s in parse_dol(output)["sections"] if s["name"] == "text2")
    if (added["offset"], added["ram_address"], added["size"]) != (section_offset, SECTION_RAM, len(code)):
        raise FormatError("shiny code section failed readback")
    report = {"version": SEEDED_VERSION if seeded else VERSION, "enabled": custom,
        "requested_percent": options.shiny_chance_percent if custom else None, "coin_threshold": threshold,
        "coin_range": COIN_RANGE, "effective_percent": threshold * 100 / COIN_RANGE if custom else None,
        "hooks": hooks, "ot_exit": OT_EXIT, "ot_wrapper": ot_address,
        "code_section": {"offset": section_offset, "address": SECTION_RAM, "size": len(code),
                         "previous_size": previous_size, "reserved_end": reserved_end},
        "allowed_changed_ranges": ranges, "outside_whitelist_unchanged": True,
        "native_pid_generator_and_shiny_test_unchanged": True,
        "existing_pids_not_rerolled": True, "purified_ot_records_not_rewritten": True,
        "scope": "new trainer, Shadow, starter and identified gift generation; existing Shadow PID reuse remains native",
        "runtime_validation": "requires cold boot, new starters and an actual Shadow capture under Dolphin"}
    report["seeded"] = seeded
    if seeded:
        report.update(seed=seed, seeded_decisions=decisions, status_tables=tables_report,
                      index_hook=TRAINER_INDEX_HOOK, index_trampoline=index_address,
                      index_saved_at_native_stack_offset=0x48,
                      pid_nature_gender_and_ivs_not_fixed_by_seed=not bool(spinda_seeds))
    if spinda_pid is not None:
        generated_call = region.trainer_function + 0x42C
        stored_call = region.trainer_function + 0x440
        report["spinda_pid"] = {
            "resolver": spinda_pid, "seeds": spinda_seeds,
            "shadow_generated": _branch_target(generated_call, _word(original, generated_call - TEXT_TO_RAM)),
            "stored_shadow_pid": _branch_target(stored_call, _word(original, stored_call - TEXT_TO_RAM)),
        }
        if party_hook is not None:
            report["spinda_pid"]["ordinary_trainer_ot"] = ORDINARY_SPINDA_OT
    return bytes(output), report
