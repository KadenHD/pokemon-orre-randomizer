"""Exact, independently checked Colosseum DOL layouts for the three rev-0 discs.

Addresses are native RAM addresses unless the field explicitly says offset.
The PAL constants remain the compatibility default for synthetic core fixtures;
production selectors always fingerprint the unmodified executable first.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib

from .analyze_game import FormatError


@dataclass(frozen=True)
class DolLayout:
    game_id: str
    sha256: str
    special_offsets: tuple[int, ...]
    native_constructor: int
    native_set_move: int
    section_ram: int
    stack_top: int
    bss_end: int
    set_arena_lo: int
    get_arena_lo: int
    arena_lo_store: int
    arena_initialize: int
    clear_arena: int
    pid_generator: int
    native_rng: int
    ot_exit: int
    player_pointer: int
    player_getter: int
    player_getter_word: int
    trainer_function: int
    trainer_pid_call: int
    pokemon_store_ot: int
    shadow_pid_fetch_words: tuple[int, int]
    item_table_offset: int
    tm_table_offset: int

    @property
    def moon_stone_price_offset(self) -> int:
        return self.item_table_offset + 0x3AEC56 - 0x3ADDA0

    @property
    def trainer_index_hook(self) -> int:
        return self.trainer_function + 0x18

    @property
    def pid_calls(self) -> dict[str, int]:
        offsets = (0x60, 0x60, 0x68, 0x60, 0x60, 0x60)
        keys = ('umbreon', 'espeon', 'plusle', 'ho-oh', 'celebi-event', 'pikachu-event')
        calls = {key: base + 0x80003000 + displacement
                 for key, base, displacement in zip(keys, self.special_offsets, offsets, strict=True)}
        # Preserve the historical ordering of wrapper allocation and its bytes.
        return {key: calls[key] for key in ('celebi-event', 'pikachu-event', 'ho-oh',
                                            'plusle', 'espeon', 'umbreon')} | {'trainers': self.trainer_pid_call}


PAL = DolLayout(
    'GC6P01', 'a788176a45eb88dbd227246a7205ab9856bc79f3cca7e4a0f5376cf466664df5',
    (0x131E1C, 0x131CF4, 0x131BF4, 0x131B10, 0x1318E0, 0x1319F0),
    0x80128238, 0x80127ECC, 0x804E3CC0, 0x804DBCB8, 0x804CBCB8,
    0x8009E4F0, 0x8009E4E0, 0x906D8168, 0x8009D07C, 0x8009CE08,
    0x80128584, 0x800E42A4, 0x8012811C, 0x804C8268,
    0x8012CFD8, 0x806DA5A8, 0x801FE824, 0x801FEC98, 0x80121F74,
    (0x4BFF4361, 0x4BFF433D), 0x3ADDA0, 0x3B20D0)
USA = DolLayout(
    'GC6E01', '7e6c00a3bd632126d5466cbab856c63ac3c52a5da20b60dba7e756538152c9f4',
    (0x12DBF0, 0x12DAC8, 0x12D9C8, 0x12D8E4, 0x12D6B4, 0x12D7C4),
    0x801240C4, 0x80123D58, 0x80496740, 0x8048E738, 0x8047E738,
    0x8009AFC8, 0x8009AFB8, 0x906D8168, 0x80099B54, 0x800998E0,
    0x80124410, 0x800E0C54, 0x80123FA8, 0x8047ADB8,
    0x80128E24, 0x806DA598, 0x801F9F78, 0x801FA3EC, 0x8011DF98,
    (0x4BFF4399, 0x4BFF4375), 0x360CE8, 0x365018)
JAPAN = DolLayout(
    'GC6J01', '64cedd009afb5b944310bd626bed4890de200fa978fea72b58f2c80c2b2ebaf2',
    (0x12B2C0, 0x12B198, 0x12B098, 0x12AFB8, 0x12ADD0, 0x12AEBC),
    0x80121870, 0x80121504, 0x80481D40, 0x80479D40, 0x80469D40,
    0x80098C74, 0x80098C64, 0x906D8160, 0x80097800, 0x8009758C,
    0x80121BBC, 0x800DE960, 0x80121754, 0x80466468,
    0x801265C4, 0x806DA568, 0x801F5838, 0x801F5CAC, 0x8011B76C,
    (0x4BFF4399, 0x4BFF4375), 0x34D428, 0x351758)

LAYOUTS = (PAL, USA, JAPAN)
_BY_HASH = {layout.sha256: layout for layout in LAYOUTS}


@lru_cache(maxsize=3)
def dol_layout(original_dol: bytes) -> DolLayout:
    """Reject modified/unknown executables rather than guessing a regional shift."""
    try:
        return _BY_HASH[hashlib.sha256(original_dol).hexdigest()]
    except KeyError:
        raise FormatError('main.dol differs from the verified Europe, USA or Japan revision-0 builds') from None


def special_targets(original_dol: bytes) -> tuple[dict, ...]:
    layout = dol_layout(original_dol)
    keys = ('umbreon', 'espeon', 'plusle', 'ho-oh', 'celebi-event', 'pikachu-event')
    species = (197, 196, 353, 250, 251, 25)
    levels = (26, 25, 13, 70, 10, 10)
    return tuple({'key': key, 'base': offset, 'old': old, 'level': level,
                  **({'xp': 19055 if key == 'umbreon' else 16372} if index < 2 else {})}
                 for index, (key, offset, old, level) in enumerate(
                     zip(keys, layout.special_offsets, species, levels, strict=True)))
