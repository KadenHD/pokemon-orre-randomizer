"""Two bounded native Fairy mechanics, separate from effects and animation rows.

The native Soundproof flag and the existing drain script are deliberately kept.
Disarming Voice alone bypasses the Substitute HP branch; Draining Kiss alone
changes the native drain amount to 75 percent, rounded as a modern drain move.
The existing ability64 script turns that same amount into Liquid Ooze damage.
"""
from __future__ import annotations

import hashlib
import struct

from .castform_portraits import _reservation
from .engine.analyze_game import FormatError, parse_dol
from .engine.gift_move_hooks import _arena_guard, branch
from .engine.shiny_rules import _Code
from .fairy_runtime import _offset, _read, qualify_fairy_runtime

VERSION = "fairy-native-voice-kiss-v1"
DISARMING_VOICE = 375
DRAINING_KISS = 376


def drain_amount(hit_damage: int) -> int:
    """Modern nearest-half-up 3/4 drain; input is actual bounded HP removed."""
    if type(hit_damage) is not int or not 0 <= hit_damage <= 65535:
        raise ValueError("Drain damage must be a native unsigned HP amount")
    return max(1, (3 * hit_damage + 2) // 4)


def _drain_stub(address: int, site: int, *, xd: bool) -> bytes:
    code = _Code(address)
    code.emit(0xA17F0004,             # lhz r11,4(r31): current runtime move ID
              0x280B0000 | DRAINING_KISS)
    code.conditional(0x40820000, "native")
    # HP removed is bounded by a native u16. Multiplication cannot overflow.
    code.emit(0x1D630003,             # mulli r11,r3,3
              0x396B0002,             # addi r11,r11,2: nearest-half-up
              0x5560F0BE)             # srwi r0,r11,2
    out = 4 if xd else 7
    code.emit(0x7C0000D1 | out << 21) # neg. r{out},r0
    code.conditional(0x40820000, "result")
    code.emit(0x3800FFFF | out << 21)  # min1, represented as a negative HP loss
    code.label("result")
    code.emit(branch(address + len(code.words) * 4, site + 20))
    code.label("native")
    code.emit(0x7C600E70)             # exact displaced native srawi r0,r3,1
    code.emit(branch(address + len(code.words) * 4, site + 4))
    return code.finish()


def _substitute_stub(address: int, row: dict) -> bytes:
    code = _Code(address)
    # The displaced BEQ consumes CR0 from native or. substituteHP,r3,r3.
    code.conditional(0x41820000, "real_hp")
    register = row["move_register"]
    code.emit(0x5400043E | register << 21,  # clrlwi r0,r{move},16
              0x28000000 | DISARMING_VOICE)
    code.conditional(0x41820000, "real_hp")
    code.emit(branch(address + len(code.words) * 4, row["native_continuation"]))
    code.label("real_hp")
    code.emit(branch(address + len(code.words) * 4, row["native_no_substitute"]))
    return code.finish()


def qualify_fairy_move_effects(original_dol: bytes, game_id: str) -> dict:
    qualify_fairy_runtime(original_dol, game_id)
    row = _QUALIFIED[game_id]
    targets = [(row["drain"]["address"], row["drain"]["size"], row["drain"]["sha256"]),
               (row["substitute"]["window_address"], row["substitute"]["window_size"], row["substitute"]["window_sha256"]),
               (row["drain_script_tail"]["address"], row["drain_script_tail"]["size"], row["drain_script_tail"]["sha256"])]
    targets.extend((r["address"], r["size"], r["sha256"]) for r in row["commands"].values())
    for address, size, digest in targets:
        if hashlib.sha256(_read(original_dol, address, size)).hexdigest() != digest:
            raise FormatError("Unqualified Fairy move effect native window")
    tail = _read(original_dol, row["drain_script_tail"]["address"], row["drain_script_tail"]["size"])
    xd = game_id.startswith("GXX")
    if (tail[10:13] != bytes((0x1F if xd else 0x1E, 0x12, 64))
            or tail[-2:] != bytes((0x81 if xd else 0x80, 0))):
        raise FormatError("Native Liquid Ooze drain routing changed")
    return row


def install_fairy_move_effects(original_dol: bytes, current_dol: bytes,
                               game_id: str, *, enabled: bool = True) -> tuple[bytes, dict]:
    if type(enabled) is not bool:
        raise ValueError("Fairy mechanics enablement must be a boolean")
    if not enabled:
        return current_dol, {"enabled": False, "version": VERSION}
    layout = qualify_fairy_move_effects(original_dol, game_id)
    xd = game_id.startswith("GXX")
    drain, substitute = layout["drain"], layout["substitute"]
    site = drain["drain_arithmetic_site"]
    if (_read(current_dol, site, 20) != bytes.fromhex(drain["drain_arithmetic"])
            or _read(current_dol, substitute["address"], 4) != _read(original_dol, substitute["address"], 4)):
        raise FormatError("Fairy move effect instruction window is already modified")
    offset, ram, setter, store, arena = _reservation(original_dol, current_dol, game_id)
    output, hooks = bytearray(current_dol[:offset]), []
    for role, address in (("draining_kiss_fraction", site), ("disarming_voice_substitute", substitute["address"])):
        stub = ram + len(arena)
        payload = (_drain_stub(stub, address, xd=xd) if role == "draining_kiss_fraction"
                   else _substitute_stub(stub, substitute))
        struct.pack_into(">I", output, _offset(original_dol, address), branch(address, stub))
        arena.extend(payload)
        hooks.append({"role": role, "address": address, "stub": stub, "bytes": len(payload)})
    end = ram + len(arena)
    if end >= 0x81700000:
        raise FormatError("Fairy move mechanics exceed owned memory")
    arena[:32] = _arena_guard(end, store)
    output.extend(bytes(offset - len(output)))
    output.extend(arena)
    setter_offset = _offset(original_dol, setter)
    for position, value in ((8, offset), (0x50, ram), (0x98, len(arena)),
                            (setter_offset, branch(setter, ram))):
        struct.pack_into(">I", output, position, value)
    permitted = [(8, 12), (0x50, 0x54), (0x98, 0x9C), (offset, offset + 32),
                 (setter_offset, setter_offset + 4)]
    permitted += [(_offset(original_dol, h["address"]), _offset(original_dol, h["address"]) + 4) for h in hooks]
    if any(a != b and not any(lo <= i < hi for lo, hi in permitted)
           for i, (a, b) in enumerate(zip(current_dol, output))):
        raise FormatError("Fairy mechanics changed an unrelated executable byte")
    section = next(s for s in parse_dol(output)["sections"] if s["name"] == "text2")
    if section["offset"] + section["size"] != len(output):
        raise FormatError("Fairy move mechanics code reservation failed readback")
    return bytes(output), {"version": VERSION, "enabled": True, "hooks": hooks,
        "native_windows_qualified": True, "voice_move_id": DISARMING_VOICE,
        "kiss_move_id": DRAINING_KISS, "drain_fraction": [3, 4],
        "drain_rounding": "nearest-half-up; minimum1; native HP clamp retained",
        "native_other_drains_unchanged": True, "native_soundproof_flag_required": True,
        "native_liquid_ooze_script_preserved": True, "native_substitute_hp_preserved_for_voice": True,
        "native_damage_and_ai_categories_untouched": True, "save_and_animation_data_unchanged": True,
        "dolphin_battle_validation": "not_run_for_this_output",
        "implementation_validation": {
            "regional_bytecode_contracts": ["GC6P01", "GC6E01", "GC6J01",
                                            "GXXP01", "GXXE01", "GXXJ01"],
            "muted_dolphin_probes": {
                "GC6P01": ["75_percent_drain"],
                "GXXP01": ["disarming_voice_soundproof", "disarming_voice_substitute_bypass",
                           "75_percent_drain", "liquid_ooze_75_percent_recoil"]},
            "scope": "Implementation probes on private fixtures; generated outputs are not automatically played."}}


_QUALIFIED = {'GC6P01': {'drain': {'address': 2149714864,
                      'size': 156,
                      'sha256': '163e3e308a9393a2409a6944bac5c7643f4d00854652dea11b1cc113cfe42c2d',
                      'drain_arithmetic_site': 2149714948,
                      'drain_arithmetic': '7c600e707c0001947ce000d14082000838e0ffff'},
            'substitute': {'address': 2149758264,
                           'window_address': 2149758252,
                           'window_size': 28,
                           'window_sha256': 'f58a837291ed181fab3e8d9c74010b4d3398f1c22d3cad4639fecbb158481675',
                           'window_hex': '7c1403784bfd82f97c731b794182009c800dae18540005ef40820090',
                           'native_no_substitute': 2149758420,
                           'native_continuation': 2149758268,
                           'move_register': 30},
            'commands': {'30': {'address': 2149746664,
                                'size': 124,
                                'sha256': '08ad185562d35c07b9401af54ec94078264ee8be492bc2f30bc62aa8e2e936e2'},
                         '53': {'address': 2149740764,
                                'size': 40,
                                'sha256': '45408a152a9fe08e45870f54f5123d316d4e02d9eb2696ec06daa94206fc6664'},
                         '128': {'address': 2149716924,
                                 'size': 256,
                                 'sha256': '23436507e2351ef9a02f2eda20d45b400c6e019cdc09e615887c4274ab9e3dad'}},
            'drain_script_tail': {'address': 2151429444,
                                  'size': 30,
                                  'sha256': 'b9d457daf08603d7d3a4a29a1d39e864e0b937393d8ddae6cb7f1fd40455008f',
                                  'hex': '8835804c8ad8000001001e1240803c35602e804c621d0028803c35688000',
                                  'ooze_negation_target': 2151429472,
                                  'ability_check_opcode': 30,
                                  'target_selector': 18,
                                  'liquid_ooze_id': 64}},
 'GC6E01': {'drain': {'address': 2149695732,
                      'size': 156,
                      'sha256': '4e97488d6daf40c2bf5a07e2b5b6077d379895b35ad06cb507702d86b680fd3f',
                      'drain_arithmetic_site': 2149695816,
                      'drain_arithmetic': '7c600e707c0001947ce000d14082000838e0ffff'},
            'substitute': {'address': 2149739064,
                           'window_address': 2149739052,
                           'window_size': 28,
                           'window_sha256': '79ff32f60345c5fb88543b0c2672a481fff9dc5930c8a5e14685d551f9361a81',
                           'window_hex': '7c1403784bfd85457c731b794182009c800dadf8540005ef40820090',
                           'native_no_substitute': 2149739220,
                           'native_continuation': 2149739068,
                           'move_register': 30},
            'commands': {'30': {'address': 2149727464,
                                'size': 124,
                                'sha256': '02d5d00141139737831eb350cb6b1213c653c315f3e84a5250e7760ccdbd985e'},
                         '53': {'address': 2149721564,
                                'size': 40,
                                'sha256': '3db2edc610c0cdb886596216cc78dbe0f353ba7b47e8f910b658eefa0d4fe68b'},
                         '128': {'address': 2149697792,
                                 'size': 256,
                                 'sha256': '63c922f84c08e9e33c8fe462103b325a17b6cd1be78d1114e08a2eca5b5b0969'}},
            'drain_script_tail': {'address': 2151112884,
                                  'size': 30,
                                  'sha256': '64107ff1708262d60f96a86f7e6ccd65e725f2b1a5504be61966372e2370d825',
                                  'hex': '88358047b618000001001e1240803760d02e80478d7d0028803760d88000',
                                  'ooze_negation_target': 2151112912,
                                  'ability_check_opcode': 30,
                                  'target_selector': 18,
                                  'liquid_ooze_id': 64}},
 'GC6J01': {'drain': {'address': 2149677196,
                      'size': 156,
                      'sha256': '7951824dcb1a9c81b4b08e63953c7c51d8a6a9866535b0f690445b290368d043',
                      'drain_arithmetic_site': 2149677280,
                      'drain_arithmetic': '7c600e707c0001947ce000d14082000838e0ffff'},
            'substitute': {'address': 2149720528,
                           'window_address': 2149720516,
                           'window_size': 28,
                           'window_sha256': '7d79b1678754b96922e44e94451872677a5ea7319934296c8c5410fc9f43458e',
                           'window_hex': '7c1403784bfd866d7c731b794182009c800dadb0540005ef40820090',
                           'native_no_substitute': 2149720684,
                           'native_continuation': 2149720532,
                           'move_register': 30},
            'commands': {'30': {'address': 2149708928,
                                'size': 124,
                                'sha256': 'd87223bf2a2c76aae092951bae4ec39ac611360bbc8ce1d01262d25d2f55d779'},
                         '53': {'address': 2149703028,
                                'size': 40,
                                'sha256': 'b8df819cb2b7417529262055c6902a09f64cc8bc3211bb3e88abd9b1701764a6'},
                         '128': {'address': 2149679256,
                                 'size': 256,
                                 'sha256': 'bc644e982c77beaa3fff52a24b3d3276d3257fb91e64df000e1351f4f8546a92'}},
            'drain_script_tail': {'address': 2151032862,
                                  'size': 30,
                                  'sha256': 'a1030645a69a68949f34a129dca2757f03382733ea0424fbe9a7a82b5d76356e',
                                  'hex': '883580466cb0000001001e12408036283a2e8046444d0028803628428000',
                                  'ooze_negation_target': 2151032890,
                                  'ability_check_opcode': 30,
                                  'target_selector': 18,
                                  'liquid_ooze_id': 64}},
 'GXXP01': {'drain': {'address': 2149729068,
                      'size': 108,
                      'sha256': '48dd31f6642ec11c24cca76985b4d2d5e0e721cbc6215495be578cb287b9464f',
                      'drain_arithmetic_site': 2149729120,
                      'drain_arithmetic': '7c600e707c0001947c8000d1408200083880ffff'},
            'substitute': {'address': 2149676720,
                           'window_address': 2149676708,
                           'window_size': 28,
                           'window_sha256': 'a567e5487059d7feabedcb4a8a1f2c7ebd09d187974656fc2e544cf9b3ba577b',
                           'window_hex': '7fa3eb784bfeb66d7c721b7941820074800dbb18540005ef40820068',
                           'native_no_substitute': 2149676836,
                           'native_continuation': 2149676724,
                           'move_register': 25},
            'commands': {'30': {'address': 2149667504,
                                'size': 140,
                                'sha256': '830c035fd668ba13ea2def9a6f270ced2ef748b91ca74fe1c45b99e7b9f7960e'},
                         '53': {'address': 2149661596,
                                'size': 60,
                                'sha256': '24ea0fcf4ed70a696a4ccd9f03d84fedc659a315fb0ccd64e1b6dde86f900a2a'},
                         '128': {'address': 2149730960,
                                 'size': 212,
                                 'sha256': 'bcf9ed712780f2258dd7c3af092c92a1b1a7d540dad978027df9561ee51f0cf9'}},
            'drain_script_tail': {'address': 2152000500,
                                  'size': 30,
                                  'sha256': '6d2ffc938e7e5e49b33b9dde8c04b80a8390468456442af92894c9e8a303258c',
                                  'hex': '893680525f18000001001f12408044ec102f80522ba500298044ec188100',
                                  'ooze_negation_target': 2152000528,
                                  'ability_check_opcode': 31,
                                  'target_selector': 18,
                                  'liquid_ooze_id': 64}},
 'GXXE01': {'drain': {'address': 2149721320,
                      'size': 108,
                      'sha256': 'c6c550ddf1f172016f23b541aa0ce719f5fc4a82db75b63f1e15a03f0b89ba6f',
                      'drain_arithmetic_site': 2149721372,
                      'drain_arithmetic': '7c600e707c0001947c8000d1408200083880ffff'},
            'substitute': {'address': 2149668972,
                           'window_address': 2149668960,
                           'window_size': 28,
                           'window_sha256': '77a03b6fce6d73335746df0bc30f9d099fea2c9a1d9cc2ea13c6f983c91e9a69',
                           'window_hex': '7fa3eb784bfeb77d7c721b7941820074800dbb18540005ef40820068',
                           'native_no_substitute': 2149669088,
                           'native_continuation': 2149668976,
                           'move_register': 25},
            'commands': {'30': {'address': 2149659756,
                                'size': 140,
                                'sha256': '2e8ecb721a2f00433ddcdfb18750a3caf416ef9eb133da926a409aa7fe853371'},
                         '53': {'address': 2149653848,
                                'size': 60,
                                'sha256': '24ea0fcf4ed70a696a4ccd9f03d84fedc659a315fb0ccd64e1b6dde86f900a2a'},
                         '128': {'address': 2149723212,
                                 'size': 212,
                                 'sha256': '72e6716747a911be16e10f9e06e7cde562950a360412e89b9d14f480cd48240a'}},
            'drain_script_tail': {'address': 2151760388,
                                  'size': 30,
                                  'sha256': '3a185b32e970a92417729b9407c02e2dd75fb2de7c8bf8dfdc162f169a2899bd',
                                  'hex': '8936804eb938000001001f1240804142202f804e85c50029804142288100',
                                  'ooze_negation_target': 2151760416,
                                  'ability_check_opcode': 31,
                                  'target_selector': 18,
                                  'liquid_ooze_id': 64}},
 'GXXJ01': {'drain': {'address': 2149699216,
                      'size': 108,
                      'sha256': '6028a80244faba1d07e3af15d1d520d3dcb3f8d532891e3d113f19ecc545302d',
                      'drain_arithmetic_site': 2149699268,
                      'drain_arithmetic': '7c600e707c0001947c8000d1408200083880ffff'},
            'substitute': {'address': 2149646952,
                           'window_address': 2149646940,
                           'window_size': 28,
                           'window_sha256': 'b4d35f4adcc1df092e5642b9568a442bc8a2bd8a69a7bb68e4719bbbfd3e293f',
                           'window_hex': '7fa3eb784bfeba457c721b7941820074800dbad0540005ef40820068',
                           'native_no_substitute': 2149647068,
                           'native_continuation': 2149646956,
                           'move_register': 25},
            'commands': {'30': {'address': 2149637796,
                                'size': 140,
                                'sha256': '40ca64007979936bbbf71e6554567089c61a520decc761c0199f44f1f395b69b'},
                         '53': {'address': 2149631920,
                                'size': 60,
                                'sha256': '80186be813546427e9b6c0f11766303f16bb45fabb9f4522e7741d64a2653c04'},
                         '128': {'address': 2149701108,
                                 'size': 212,
                                 'sha256': '45b1332ff9b5b177e5bc144c323db1ef0b16a727fc00d76107075f53d121dd59'}},
            'drain_script_tail': {'address': 2151618740,
                                  'size': 30,
                                  'sha256': '1235abb4fa7b25416e4a5bb63dd283be1bd61bc3795f69966eb798134ff7a454',
                                  'hex': '8936804c8e10000001001f1240803f18d02f804c5add0029803f18d88100',
                                  'ooze_negation_target': 2151618768,
                                  'ability_check_opcode': 31,
                                  'target_selector': 18,
                                  'liquid_ooze_id': 64}}}
