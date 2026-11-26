"""Additional ordinary TM identities and qualified native getter extensions.

HM01-HM08 retain their native records and compatibility bytes. Seven added
TMs use separate indices and a separate compatibility matrix. All 57 ordinary
TMs can share one seeded permutation. The native save already reserves 64
item records for this pocket.
Move effects and animation bindings are supplied by the content installer;
this module never disguises a native move as an implemented modern effect.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import struct

from .engine.analyze_game import FormatError, parse_rel, u32
from .engine.dol_regions import dol_layout
from .engine.gift_move_hooks import _arena_guard, branch
from .engine.shiny_rules import _Code
from .castform_portraits import _reservation
from .deoxys_meteorite import _read, _offset, _load, _COLO_ITEM_MAPS

VERSION = "additional-fairy-tms-v1"
CANONICAL_MOVES = (574, 577, 583, 584, 585, 605, 608)
MOVE_IDS = tuple(range(375, 382))
ITEM_IDS = tuple(range(278, 285))
MACHINE_INDICES = tuple(range(58, 65))
TM_NUMBERS = tuple(range(51, 58))
FIRST_MESSAGE = 0xF0400
MOVE_STRIDE = 0x38
ITEM_STRIDE = 0x28
NATIVE_MACHINE_COUNT = 58
NATIVE_POCKET_CAPACITY = 64
NATIONAL_COUNT = 386


@dataclass(frozen=True)
class AdditionalTM:
    number: int
    item_id: int
    machine_index: int
    move_id: int
    canonical_move_id: int


ADDITIONAL_TMS = tuple(AdditionalTM(*row) for row in zip(
    TM_NUMBERS, ITEM_IDS, MACHINE_INDICES, MOVE_IDS, CANONICAL_MOVES, strict=True))
NATIVE_MOVE_MAP = dict(zip(CANONICAL_MOVES, MOVE_IDS, strict=True))

# Exact original common RELs. Row cloning never accepts a randomized/foreign
# table as a donor, and never treats a canonical effect number as a native ID.
_REL_IDENTITIES = {
    "GC6P01": "ee2677af555dc59626f978e743235831a76cb23bae93f3fdd1060d808f749d0b",
    "GC6E01": "0c89e679305f5e84eff3c774b542120c727ff350a0841cfc516235b3556df69e",
    "GC6J01": "62744eba0b4ba39e1019d15d550c35768903952a69f45673c0af31cee4658c42",
    "GXXP01": "10f741259d264315ba3d44af8e87bef3294ba6cc3d7df0db653d533ba4404ed8",
    "GXXE01": "ef03647b307d4e423dc4c71314c97eae55ffffdaa24b1fd50d90666333284450",
    "GXXJ01": "97c6b45b123403561208b830613dbce6d4f4826602090d5102bb45fd223b2d78",
}

_EFFECT_DONORS = {574: (129, 17), 577: (72, 3), 583: (62, 68),
                  584: (304, 0), 585: (296, 71), 605: (304, 0), 608: (45, 18)}
ANIMATION_PROPOSALS = {
    574: {"donor": 304, "name": "Hyper Voice", "reason": "A voice pulse reaching both opponents."},
    577: {"donor": 186, "name": "Sweet Kiss", "reason": "Kiss particles; the damage/drain effect remains separate."},
    583: {"donor": 34, "name": "Body Slam", "reason": "A readable physical contact impact."},
    584: {"donor": 16, "name": "Gust", "reason": "A short wind effect; no Gust-specific airborne damage bonus."},
    585: {"donor": 296, "name": "Mist Ball", "reason": "A luminous projectile; power and stat drop follow Moonblast."},
    605: {"donor": 129, "name": "Swift", "reason": "Bright stars across the opposing side; normal accuracy retained."},
    608: {"donor": 204, "name": "Charm", "reason": "A brief cute gesture; a single Attack stage is removed."},
}


def prepare_candidate_moves(original_rel: bytes, game_id: str, *,
        move_message_ids: Mapping[int, tuple[int, int]],
        animation_donors: Mapping[int, int] | None = None) -> dict:
    """Prepare explicit provisional native rows for review, never qualification.

    Animation donors are proposals until the user chooses them. Disarming
    Voice's Substitute bypass and Draining Kiss's 75% drain require additional
    native hooks. Returning rows does not assert that those hooks are installed.
    """
    from .engine.inspect_tables import rel_symbols
    from .fairy_data import move_definition
    if (type(original_rel) is not bytes or game_id not in _REL_IDENTITIES
            or hashlib.sha256(original_rel).hexdigest() != _REL_IDENTITIES[game_id]):
        raise FormatError("Candidate Fairy moves require an exact original common REL")
    if (not isinstance(move_message_ids, Mapping) or set(move_message_ids) != set(MOVE_IDS)
            or any(not isinstance(pair, tuple) or len(pair) != 2 or
                   any(type(v) is not int or not 0 < v <= 0xFFFFFFFF for v in pair)
                   for pair in move_message_ids.values())):
        raise ValueError("Seven native move name and description message pairs are required")
    donors = ({canonical: row["donor"] for canonical, row in ANIMATION_PROPOSALS.items()}
              if animation_donors is None else animation_donors)
    if (not isinstance(donors, Mapping) or set(donors) != set(CANONICAL_MOVES)
            or any(type(v) is not int or not 1 <= v <= 354 for v in donors.values())):
        raise ValueError("Provide a native ordinary animation donor for every added move")
    xd = game_id.startswith("GXX")
    symbols = rel_symbols(original_rel, parse_rel(original_rel))
    start = symbols[124 if xd else 62]["offset"]
    count = u32(original_rel, symbols[125 if xd else 63]["offset"])
    if count != (375 if xd else 358) or start + count * MOVE_STRIDE > len(original_rel):
        raise FormatError("Candidate native move donor allocation differs")
    power_offset, effect_offset, animation_offset = (0x19, 0x1C, 0x1E) if xd else (0x17, 0x1A, 0x1C)
    rows, effects, contracts = {}, {}, []
    for canonical, move in NATIVE_MOVE_MAP.items():
        definition = move_definition(canonical)
        donor, effect = _EFFECT_DONORS[canonical]
        pos = start + donor * MOVE_STRIDE
        row = bytearray(original_rel[pos:pos + MOVE_STRIDE])
        animation = original_rel[start + donors[canonical] * MOVE_STRIDE:start + (donors[canonical] + 1) * MOVE_STRIDE]
        if (struct.unpack_from(">H", row, effect_offset)[0] != effect
                or u32(row, 0x20) != 2000 + donor or not row[1]
                or u32(animation, 0x20) != 2000 + donors[canonical] or not animation[1]):
            raise FormatError("Candidate native effect or animation donor was not qualified")
        row[0] = definition["priority"] & 0xFF
        row[1], row[2] = definition["pp"], 19
        row[3] = 4 if definition["target"] == "all-opponents" else 0
        if definition["target"] not in ("all-opponents", "selected-pokemon"):
            raise FormatError("New Fairy target mode needs a qualified native encoding")
        row[4], row[5] = definition["accuracy"] or 0, definition["effect_chance"] or 0
        flags = set(definition["flags"])
        for flag, field in (("contact", 6), ("protect", 7), ("reflectable", 8),
                            ("snatch", 9), ("mirror", 10), ("sound", 16)):
            row[field] = int(flag in flags)
        row[18] = 0
        # These modern moves have no authored GameCube Contest performance.
        # Colosseum virtual effect255 provides zero Appeal/Jam and its own text;
        # XD has no Contest sheet and keeps the neutral zero record.
        row[0x16 if xd else 0x14] = 0 if xd else 255
        row[0x17 if xd else 0x15] = 0
        row[power_offset] = definition["power"] or 0
        if xd:
            row[0x13] = {"status": 0, "physical": 1, "special": 2}[definition["damage_class"]]
        for field in (animation_offset, 0x32):
            row[field:field + 2] = animation[field:field + 2]
        struct.pack_into(">I", row, 0x20, move_message_ids[move][0])
        struct.pack_into(">I", row, 0x2C, move_message_ids[move][1])
        rows[move], effects[canonical] = bytes(row), effect
        pending = ["native-effect-runtime-validation", "animation-review-and-runtime-validation"]
        if canonical == 574: pending.append("sound-move-substitute-bypass")
        if canonical == 577: pending.append("drain-75-percent-and-liquid-ooze")
        if canonical == 583: pending.append("physical-category-damage-ai-counter-hustle")
        contracts.append({"canonical_move_id": canonical, "move_id": move,
            "native_effect": effect, "effect_donor": donor,
            "animation_donor": donors[canonical], "animation1": struct.unpack_from(">H", row, animation_offset)[0],
            "animation2": struct.unpack_from(">H", row, 0x32)[0], "pending": pending})
    _move_rows(rows)
    return {"version": VERSION, "game_id": game_id, "qualified": False,
            "move_rows": rows, "native_effect_ids": effects, "contracts": contracts,
            "source_rel_sha256": _REL_IDENTITIES[game_id],
            "original_native_moves_untouched": True, "requires_user_animation_choice": True}


_QUALIFIED = {
    'GC6P01': ('a788176a45eb88dbd227246a7205ab9856bc79f3cca7e4a0f5376cf466664df5', {
        'machine_move': (0x80148264, 0x34, '919e1234ea005a1094eabedff71922254454decb47d852823bcbff0a9b49b7bc'),
        'machine_number': (0x80148298, 0x30, '9bb32310909d3881c694f6385b6fef81b1319aa2b7914f5cfac5c4d4f7959062'),
        'hidden_number': (0x801481FC, 0x68, 'e5880f289d4f0956685e4ac2556a28e915e3979fee9214cd510a656ba5664b8a'),
        'compatibility': (0x80122288, 0x30, 'f69434957cd79f0ed5f13fcfb5a1e2600d458369958580be31e502ad68ba6826'),
        'move_getter': (0x801209E8, 0x2C, '95c908dc0f65310210daf47e5a2c09197b3c67311e0dccd4b33dd158f686236e'),
        'item_name': (0x801483FC, 0x18, 'e54f9ce91a61da85bc3d0af13bf0bf6ba6d4ed25a82d3afc7fdd456b1f66611b'),
        'display': (0x8001711C, 0x4, '0eefd70f75c6bc9cdd71f3ddc2e3c51f110f86fd1c8495fcaf2dfe77c8eb5764'),
        'damage_prolog': (0x80236C10, 0x1C, '730ae3217294ef9942a219e63ae9407734063913b2cd66a05b6c278c41c7f683'),
        'damage_category_0': (0x80236FCC, 0x4, 'dfddb3945f0973babf870079a3f70cdec23f5cba2095b630ebeb450c2ec447ee'),
        'damage_category_1': (0x8023743C, 0x4, 'fe39536103e2ec4cdc48997a83f5d03399209f467460038b6847770997b8c10a'),
        'contest_effect': (0x801f28f0, 0x2C, 'e3b067a27ac08d43710f88a8445767a77b8864dcd2ce651925bff627824d4b54'),
        'item_description': (0x801482F8, 0x18, 'f7767c05ce4d74fb5dc34edf57eb6366c1d8c34fc155d45556b3dd1cfd5ad94a'),
    }),
    'GC6E01': ('7e6c00a3bd632126d5466cbab856c63ac3c52a5da20b60dba7e756538152c9f4', {
        'machine_move': (0x80143EF0, 0x34, '09878825398ed2af8d5970c2201252df8f1613efa310bb190e6ec5e947ce64a3'),
        'machine_number': (0x80143F24, 0x30, '9bb32310909d3881c694f6385b6fef81b1319aa2b7914f5cfac5c4d4f7959062'),
        'hidden_number': (0x80143E88, 0x68, 'e5880f289d4f0956685e4ac2556a28e915e3979fee9214cd510a656ba5664b8a'),
        'compatibility': (0x8011E2AC, 0x30, 'f69434957cd79f0ed5f13fcfb5a1e2600d458369958580be31e502ad68ba6826'),
        'move_getter': (0x8011CA34, 0x2C, '95c908dc0f65310210daf47e5a2c09197b3c67311e0dccd4b33dd158f686236e'),
        'item_name': (0x80144088, 0x18, 'e54f9ce91a61da85bc3d0af13bf0bf6ba6d4ed25a82d3afc7fdd456b1f66611b'),
        'display': (0x80015B90, 0x4, '0eefd70f75c6bc9cdd71f3ddc2e3c51f110f86fd1c8495fcaf2dfe77c8eb5764'),
        'damage_prolog': (0x80232110, 0x1C, '730ae3217294ef9942a219e63ae9407734063913b2cd66a05b6c278c41c7f683'),
        'damage_category_0': (0x802324CC, 0x4, '25568eecfbc751100f51c096a939a012550b09effde18da4517ddfd3673c7f66'),
        'damage_category_1': (0x8023293C, 0x4, '0e95a883e35f863b3a120f977a1ceef17cc999e13cff50ba263a2550956245a4'),
        'contest_effect': (0x801ee07c, 0x2C, 'e3b067a27ac08d43710f88a8445767a77b8864dcd2ce651925bff627824d4b54'),
        'item_description': (0x80143F84, 0x18, 'f7767c05ce4d74fb5dc34edf57eb6366c1d8c34fc155d45556b3dd1cfd5ad94a'),
    }),
    'GC6J01': ('64cedd009afb5b944310bd626bed4890de200fa978fea72b58f2c80c2b2ebaf2', {
        'machine_move': (0x80140FC8, 0x34, '2a83bfdb8321d075e957f6d63f64b6d684249330fde3e203972de7afd5a43436'),
        'machine_number': (0x80140FFC, 0x30, '9bb32310909d3881c694f6385b6fef81b1319aa2b7914f5cfac5c4d4f7959062'),
        'hidden_number': (0x80140F60, 0x68, '679ed8e81efaa3bdee2ebcb84b17efa1a4de9fc53aaf405cc703a09569dd2b6c'),
        'compatibility': (0x8011BA80, 0x30, 'f69434957cd79f0ed5f13fcfb5a1e2600d458369958580be31e502ad68ba6826'),
        'move_getter': (0x8011A21C, 0x2C, '95c908dc0f65310210daf47e5a2c09197b3c67311e0dccd4b33dd158f686236e'),
        'item_name': (0x80141160, 0x18, 'e54f9ce91a61da85bc3d0af13bf0bf6ba6d4ed25a82d3afc7fdd456b1f66611b'),
        'display': (0x80015D28, 0x4, '0eefd70f75c6bc9cdd71f3ddc2e3c51f110f86fd1c8495fcaf2dfe77c8eb5764'),
        'damage_prolog': (0x8022D8A8, 0x1C, '730ae3217294ef9942a219e63ae9407734063913b2cd66a05b6c278c41c7f683'),
        'damage_category_0': (0x8022DC64, 0x4, 'ebdf9a22e6b84ed71f8b085d9e0d5c2225784fe0022c53d8b9923fcd98b2313c'),
        'damage_category_1': (0x8022E0D4, 0x4, '9e2bc58efdd2e4c60c12764eb42315972f664545a96ff4d59d9f7c81a96163e1'),
        'contest_effect': (0x801e993c, 0x2C, 'e3b067a27ac08d43710f88a8445767a77b8864dcd2ce651925bff627824d4b54'),
        'item_description': (0x8014105C, 0x18, 'f7767c05ce4d74fb5dc34edf57eb6366c1d8c34fc155d45556b3dd1cfd5ad94a'),
    }),
    'GXXP01': ('a90eae103e6e8471e41c92df1f894f98c2f98d1f9f3a0aca84964492135f5cfd', {
        'machine_move': (0x80160204, 0x34, '322a7096d84d138c9b40f206fe172290f5b8c3aa38fc53d0f88e9fce7789b70b'),
        'machine_number': (0x80160238, 0x30, '9bb32310909d3881c694f6385b6fef81b1319aa2b7914f5cfac5c4d4f7959062'),
        'hidden_number': (0x8016019C, 0x68, '89e9a1d26d23d17e4d3c1358d739982297e4008a7a9282a008507881bbad0dd2'),
        'compatibility': (0x8014739C, 0x3C, '3b36b158ff53800ad9d19b8d731e2b67b4c2fa22560cd36edbdc38341f7e69b5'),
        'move_getter': (0x8013F8B0, 0x2C, 'ba32250d06a9446968b6655e4967e0039e322f344584c3f1b45e8ac3af448b5d'),
        'item_name': (0x801603CC, 0x18, 'e54f9ce91a61da85bc3d0af13bf0bf6ba6d4ed25a82d3afc7fdd456b1f66611b'),
        'display': (0x80023384, 0x4, 'a07642e7c7152ecf17db0faa09a91b4cc90e039c9b60ab111cc8412d40c12a03'),
        'shadow_classifier': (0x8013E900, 0x28, 'fd0b4855a62f703b84a77b08405c5cd5ef81f7afae4c49ca3745f88cf06622df'),
        'category': (0x801400B4, 0x80, '845a543a67b9bab6a6d6cc21766e1b7a03710806943ca14bf1c7a33093c76182'),
        'item_description': (0x80160298, 0x18, 'f7767c05ce4d74fb5dc34edf57eb6366c1d8c34fc155d45556b3dd1cfd5ad94a'),
    }),
    'GXXE01': ('c8659341c252d1b088753d508769344eb6f092b5da5cc7cc0ce1560b32478c15', {
        'machine_move': (0x8015E954, 0x34, 'c007fcd2b4c297427c328fcc641091308affa0b86af8ca16143f0d1d79284397'),
        'machine_number': (0x8015E988, 0x30, '9bb32310909d3881c694f6385b6fef81b1319aa2b7914f5cfac5c4d4f7959062'),
        'hidden_number': (0x8015E8EC, 0x68, '89e9a1d26d23d17e4d3c1358d739982297e4008a7a9282a008507881bbad0dd2'),
        'compatibility': (0x80145AD8, 0x3C, '3b36b158ff53800ad9d19b8d731e2b67b4c2fa22560cd36edbdc38341f7e69b5'),
        'move_getter': (0x8013DFEC, 0x2C, 'ba32250d06a9446968b6655e4967e0039e322f344584c3f1b45e8ac3af448b5d'),
        'item_name': (0x8015EB1C, 0x18, 'e54f9ce91a61da85bc3d0af13bf0bf6ba6d4ed25a82d3afc7fdd456b1f66611b'),
        'display': (0x800236D4, 0x4, 'a07642e7c7152ecf17db0faa09a91b4cc90e039c9b60ab111cc8412d40c12a03'),
        'shadow_classifier': (0x8013D03C, 0x28, 'fd0b4855a62f703b84a77b08405c5cd5ef81f7afae4c49ca3745f88cf06622df'),
        'category': (0x8013E7F0, 0x80, 'e97edecabc382ac9d89fdc63024c0b20816c36cbcbf13a087c37e11825480bda'),
        'item_description': (0x8015E9E8, 0x18, 'f7767c05ce4d74fb5dc34edf57eb6366c1d8c34fc155d45556b3dd1cfd5ad94a'),
    }),
    'GXXJ01': ('14c129cc0f79682574f635290b09e37fa2a652ac5aa5565281bd583c31c5d702', {
        'machine_move': (0x80159FC0, 0x34, '7491aa40cb0c5318f2b8ffe7a601fe95751da1158081dc05a51f7e50c1e48d7e'),
        'machine_number': (0x80159FF4, 0x30, '9bb32310909d3881c694f6385b6fef81b1319aa2b7914f5cfac5c4d4f7959062'),
        'hidden_number': (0x80159F58, 0x68, '91ad3dbb5a8039a53635acaca91c3e7e110b66683833e6e1bc40bf05e9ace5c9'),
        'compatibility': (0x80140EE4, 0x3C, '3b36b158ff53800ad9d19b8d731e2b67b4c2fa22560cd36edbdc38341f7e69b5'),
        'move_getter': (0x801393F8, 0x2C, 'ba32250d06a9446968b6655e4967e0039e322f344584c3f1b45e8ac3af448b5d'),
        'item_name': (0x8015A188, 0x18, 'e54f9ce91a61da85bc3d0af13bf0bf6ba6d4ed25a82d3afc7fdd456b1f66611b'),
        'display': (0x80023258, 0x4, 'a07642e7c7152ecf17db0faa09a91b4cc90e039c9b60ab111cc8412d40c12a03'),
        'shadow_classifier': (0x80138448, 0x28, 'fd0b4855a62f703b84a77b08405c5cd5ef81f7afae4c49ca3745f88cf06622df'),
        'category': (0x80139BFC, 0x80, 'adf843fb12b8f9b11ac89940a1fd957aaeb16179a4e96dc0cb46cb9e015b47ca'),
        'item_description': (0x8015A054, 0x18, 'f7767c05ce4d74fb5dc34edf57eb6366c1d8c34fc155d45556b3dd1cfd5ad94a'),
    }),
}

# The ordinary-slot predicate is shared by PP healing, move count/forgetting,
# battle eligibility and its AI callers. XD excludes every ID >=355 here;
# Shadow moves use their separate native path. Colosseum instead excludes only
# Shadow Rush355, so its original predicate already accepts the added IDs.
for _game, (_address, _length, _sha) in {
        "GC6P01": (0x80127E48, 0x84, "a04eaca43b5f9bb3b33710b724d1e97a5a7877889392c987fbf6da277b0e0766"),
        "GC6E01": (0x80123CD4, 0x84, "a04eaca43b5f9bb3b33710b724d1e97a5a7877889392c987fbf6da277b0e0766"),
        "GC6J01": (0x80121480, 0x84, "8863a563bfe446fdd98070f6b3950b0d1edd4f3380783bb0168a28e7d49a6349"),
        "GXXP01": (0x801429D8, 0x68, "4d8dcc84c11f84d538bf794985d3afef306cd3a977f429e24d1a1fc7a2b5beb6"),
        "GXXE01": (0x80141114, 0x68, "4d8dcc84c11f84d538bf794985d3afef306cd3a977f429e24d1a1fc7a2b5beb6"),
        "GXXJ01": (0x8013C520, 0x68, "2b14528d5dee4e309560825092ba782d3b0b78a70c013c9b19b50b4d1bd858a0"),
        }.items():
    _QUALIFIED[_game][1]["ordinary_validity_function"] = (_address, _length, _sha)
    if _game.startswith("GXX"):
        _QUALIFIED[_game][1]["ordinary_validity"] = (
            _address + 0x48, 12,
            "74988c5a1a1d3110eec7310191d2e4acca76c3737c7c8fbc628f7217a67e8f1f")

for _game, _address in {"GC6P01": 0x80269A94, "GC6E01": 0x80264F4C,
        "GC6J01": 0x80260670, "GXXP01": 0x8023AAFC,
        "GXXE01": 0x80238BFC, "GXXJ01": 0x80233524}.items():
    _QUALIFIED[_game][1]["menu_move_count"] = (_address, 16,
        "c795b08ca837b53e3099db9c7e964a04f017ad95ab911cac4703a62af6307923"
        if _game.startswith("GXX") else
        "34e44848910ec546159abceeb7a18c679fc67a2a40be99d799cb3717b30a0c88")

# XD's ordinary damage paths resolve category from the effective TYPE, while
# only Shadow attacks call its per-move category getter. Preserve the original
# register/type-override flow and override Play Rough at both real call sites.
for _game, _windows in {
    'GXXP01': {
        'damage_prolog': (0x8022BE28, 0xB8, '5a49a91c814ddfd26e6bed3569a17cd2ae8c8ba95c9e03e1b72c5cb1658307d7'),
        'damage_category_0': (0x8022BEDC, 4, '62385f04ee0c4e2826df72c45ef63903a36b1b07025f841064c292ab1a83660e'),
        'bench_damage_prolog': (0x8022B3BC, 0xB8, '1b13e50ffdc8a673b9bf5278a308a9c512bfc25485ea27e8f6b07e7fff3d3a80'),
        'damage_category_1': (0x8022B470, 4, '907f5291fb2defb10fd1f7b5774134662b10048967a9f0f0dff6da5b6204fb85'),
    },
    'GXXE01': {
        'damage_prolog': (0x80229FE4, 0xB8, '440006d03ab14105c7291fad7f4b617b5e4c3f264a012bc50bc9fed08ed775a6'),
        'damage_category_0': (0x8022A098, 4, 'fc754cd54cae72417984f6d242a013f0f30a42d91403f177182bc8ed32db88ab'),
        'bench_damage_prolog': (0x80229578, 0xB8, '531d997dddaa40364d37532012b1be66752f171633444d8fb4bb380a8d2f3273'),
        'damage_category_1': (0x8022962C, 4, '415b2a22fe0ff3508956c00df7839ac63eed0d71b42e89afd371e2eeed40da19'),
    },
    'GXXJ01': {
        'damage_prolog': (0x8022498C, 0xB8, '34111b2d9b06f0f5b8dee49ce4f6ccd9f7b42043862e1d1caae85b8ad6dbd0c7'),
        'damage_category_0': (0x80224A40, 4, 'a3f22f608aee3bd6f7eff1b93dbf4287c748578c76379e3d051831c3d03c0d78'),
        'bench_damage_prolog': (0x80223F20, 0xB8, '0d9c24da18c2a627d81b85ec5b104d244deb398173e308a87abc41fd6c7dc91d'),
        'damage_category_1': (0x80223FD4, 4, 'a6667f9ab05c622d592a7a80d563781016aebcd2e5cd976097226d746a0eabb7'),
    },
        }.items():
    _QUALIFIED[_game][1].update(_windows)

def extra_item_catalog(*, price=3000):
    """Ordinary acquisition entries, in these games' unshifted ID range."""
    if type(price) is not int or not 1 <= price <= 65535:
        raise ValueError("Additional TM price must be a positive u16")
    return {tm.item_id: {"index": tm.item_id, "script_index": tm.item_id,
            "bag": 4, "category": "tms", "price": price, "safe": True,
            "tm": tm.number, "move": tm.move_id} for tm in ADDITIONAL_TMS}



def _sample(seed, key, count):
    if type(seed) is not str or not 1 <= len(seed.encode("utf-8")) <= 256:
        raise ValueError("TM seed must contain 1..256 UTF-8 bytes")
    prefix = (VERSION + "\0" + seed + "\0" + key + "\0").encode("utf-8")
    limit, counter = (1 << 256) // count * count, 0
    while True:
        value = int.from_bytes(hashlib.sha256(prefix + counter.to_bytes(4, "big")).digest(), "big")
        if value < limit:
            return value % count
        counter += 1


def plan_tms(seed: str, *, extra_description_ids: Mapping[int, int],
             native_description_ids=tuple(range(10195, 10245)), shuffle=False) -> dict:
    """Permute all 57 real TMs while leaving physical HM indices 50..57 alone."""
    from .engine.tm_rules import ORIGINAL_TM_MOVES
    if (type(shuffle) is not bool or not isinstance(extra_description_ids, Mapping)
            or set(extra_description_ids) != set(MOVE_IDS)
            or not isinstance(native_description_ids, Sequence)
            or isinstance(native_description_ids, (str, bytes)) or len(native_description_ids) != 50):
        raise ValueError("The 57-TM plan requires the native50 and new7 description identities")
    descriptions = (*native_description_ids, *(extra_description_ids[move] for move in MOVE_IDS))
    if (any(type(value) is not int or not 1 <= value <= 0xFFFFFFFF for value in descriptions)
            or len(set(descriptions)) != 57):
        raise ValueError("Invalid or overlapping TM description identities")
    _sample(seed, "validate", 1)
    moves, order = (*ORIGINAL_TM_MOVES, *MOVE_IDS), list(range(57))
    if shuffle:
        for index in range(56, 0, -1):
            target = _sample(seed, f"permutation:{index}", index)
            order[index], order[target] = order[target], order[index]
    rows = []
    for slot, source in enumerate(order):
        rows.append({"tm": slot + 1, "machine_index": slot if slot < 50 else slot + 8,
                     "item_index": 289 + slot if slot < 50 else ITEM_IDS[slot - 50],
                     "before_move": moves[slot], "after_move": moves[source],
                     "before_description_id": descriptions[slot],
                     "after_description_id": descriptions[source], "source_tm": source + 1})
    return {"version": VERSION, "shuffle": shuffle, "tm_count": 57,
            "source_order": order, "mapping": rows, "native_hm_indices_unchanged": list(range(50, 58))}


def _validate_plan(plan):
    from .engine.tm_rules import ORIGINAL_TM_MOVES
    if (not isinstance(plan, Mapping) or plan.get("version") != VERSION
            or plan.get("tm_count") != 57 or type(plan.get("shuffle")) is not bool
            or plan.get("native_hm_indices_unchanged") != list(range(50, 58))
            or not isinstance(plan.get("mapping"), list)
            or len(plan["mapping"]) != 57 or not isinstance(plan.get("source_order"), list)
            or any(type(value) is not int for value in plan["source_order"])
            or sorted(plan["source_order"]) != list(range(57))):
        raise ValueError("Invalid complete 57-TM plan")
    moves = (*ORIGINAL_TM_MOVES, *MOVE_IDS)
    rows = plan["mapping"]
    if any(not isinstance(row, Mapping) for row in rows):
        raise ValueError("Invalid 57-TM mapping row")
    descriptions = [row.get("before_description_id") for row in rows]
    if (any(type(value) is not int or not 1 <= value <= 0xFFFFFFFF for value in descriptions)
            or len(set(descriptions)) != 57
            or (not plan["shuffle"] and plan["source_order"] != list(range(57)))):
        raise ValueError("Invalid 57-TM source descriptions or unshuffled ordering")
    for slot, source in enumerate(plan["source_order"]):
        row = rows[slot]
        if any(row.get(key) != value for key, value in {
                "tm": slot + 1, "machine_index": slot if slot < 50 else slot + 8,
                "item_index": 289 + slot if slot < 50 else ITEM_IDS[slot - 50],
                "before_move": moves[slot], "after_move": moves[source],
                "after_description_id": descriptions[source], "source_tm": source + 1}.items()):
            raise ValueError("The 57-TM plan changes a native/extra identity or description pairing")
    return rows


def permute_compatibility(native, added, plan) -> tuple[int, ...]:
    """Carry learnability with the move, including retained Pokémon's native TMs."""
    _validate_plan(plan)
    if (not isinstance(native, Sequence) or not isinstance(added, Sequence)
            or len(native) != 50 or len(added) != 7
            or any(type(value) not in (int, bool) or value not in (0, 1) for value in (*native, *added))):
        raise ValueError("Compatibility permutation requires native50 and added7 Boolean columns")
    values = (*native, *added)
    return tuple(int(values[index]) for index in plan["source_order"])

def compatibility_bytes(rows: Mapping[int, Sequence[bool | int]]) -> bytes:
    """Explicit added-TM columns by national dex; absent species learn none."""
    if not isinstance(rows, Mapping):
        raise ValueError("Additional TM compatibility must be a mapping")
    out = bytearray((NATIONAL_COUNT + 1) * len(ADDITIONAL_TMS))
    for national, values in rows.items():
        if (type(national) is not int or not 1 <= national <= NATIONAL_COUNT
                or not isinstance(values, Sequence) or isinstance(values, (str, bytes))
                or len(values) != len(ADDITIONAL_TMS)
                or any(type(value) not in (bool, int) or value not in (0, 1) for value in values)):
            raise ValueError("Invalid additional TM compatibility row")
        first = national * len(ADDITIONAL_TMS)
        out[first:first + len(ADDITIONAL_TMS)] = bytes(values)
    return bytes(out)


def _move_rows(rows):
    if not isinstance(rows, Mapping) or set(rows) != set(MOVE_IDS):
        raise ValueError("All seven separately qualified new move rows are required")
    for move, row in rows.items():
        if (type(move) is not int or type(row) is not bytes or len(row) != MOVE_STRIDE
                or not row[1] or row[2] != 19 or not u32(row, 0x20)):
            raise ValueError("Additional move row lacks its Fairy type, PP or name")
    return b"".join(rows[move] for move in MOVE_IDS)


def _machine_move(address, continuation, displaced, table):
    c = _Code(address)
    c.emit(0x546C063E, 0x280C003A)  # native input is an unsigned byte
    c.conditional(0x41800000, "native")
    c.emit(0x280C0041)
    c.conditional(0x40800000, "native")
    c.emit(0x398CFFC6, 0x1D8C0002)
    _load(c, 3, table)
    c.emit(0x7C636214, 0xA0630000, 0x4E800020)
    c.label("native")
    c.emit(displaced, branch(address + len(c.words) * 4 + 4, continuation))
    return c.finish()


def _refresh_call(code, target):
    # r3 carries either the move ID or native item pointer across GSmsg calls.
    code.emit(0x9421FFF0, 0x7C0802A6, 0x90010014, 0x90610008)
    code.call(target)
    code.emit(0x80610008, 0x80010014, 0x7C0803A6, 0x38210010)


def _item_name_refresh(address, continuation, displaced, refresh, *, field=0x10):
    """Open only this content's native name bank before an item name is read."""
    c = _Code(address)
    c.emit(0x28030000)
    c.conditional(0x41820000, "native")
    if field not in (0x10, 0x14):
        raise ValueError("Only native item name/description fields can open the private bank")
    c.emit(0x81830000 | field)
    _load(c, 11, 0xF0400)
    c.emit(0x7C0C5840)
    c.conditional(0x41800000, "native")
    _load(c, 11, 0xF0500)
    c.emit(0x7C0C5840)
    c.conditional(0x40800000, "native")
    _refresh_call(c, refresh)
    c.label("native")
    c.emit(displaced, branch(address + len(c.words) * 4 + 4, continuation))
    return c.finish()


def _move_getter(address, continuation, displaced, table, refresh=None):
    c = _Code(address)
    c.emit(0x546C043E, 0x280C0177)
    c.conditional(0x41800000, "native")
    c.emit(0x280C017E)
    c.conditional(0x40800000, "native")
    if refresh is not None:
        _refresh_call(c, refresh)
        c.emit(0x546C043E)
    c.emit(0x398CFE89, 0x1D8C0038)
    _load(c, 3, table)
    c.emit(0x7C636214, 0x4E800020)
    c.label("native")
    c.emit(displaced, branch(address + len(c.words) * 4 + 4, continuation))
    return c.finish()


def _compatibility(address, continuation, displaced, table, *, xd):
    c = _Code(address)
    c.emit(0x548B043E, 0x280B003A)
    c.conditional(0x41800000, "native")
    c.emit(0x280B0041)
    c.conditional(0x40800000, "native")
    c.emit(0x28030000)
    c.conditional(0x41820000, "zero")
    c.emit(0xA183000E if xd else 0xA1830010, 0x280C0001)
    c.conditional(0x41800000, "zero")
    c.emit(0x280C0183)
    c.conditional(0x40800000, "zero")
    c.emit(0x1D8C0007, 0x396BFFC6, 0x7D8C5A14)
    _load(c, 3, table)
    c.emit(0x7C636214, 0x88630000, 0x4E800020)
    c.label("zero")
    c.emit(0x38600000, 0x4E800020)
    c.label("native")
    c.emit(displaced, branch(address + len(c.words) * 4 + 4, continuation))
    return c.finish()


def _display_number(address, continuation, displaced, *, xd):
    """Map physical indices58..64 to visible TM51..57 at the draw site only."""
    source, destination = (25, 24) if xd else (20, 19)
    c = _Code(address)
    c.emit(displaced, 0x2800003A | source << 16)
    c.conditional(0x41800000, "done")
    c.emit(0x28000041 | source << 16)
    c.conditional(0x40800000, "done")
    c.emit(0x3800FFF8 | destination << 21 | destination << 16)
    c.label("done")
    c.emit(branch(address + len(c.words) * 4, continuation))
    return c.finish()



def _physical_category(address, fallback, *, move_register, displaced=None):
    """Only Play Rough is physical; all original category behavior stays native."""
    c = _Code(address)
    c.emit(0x540C043E | move_register << 21, 0x280C0179)
    c.conditional(0x40820000, "native")
    c.emit(0x38600001, 0x4E800020)
    c.label("native")
    if displaced is not None:
        c.emit(displaced)
    c.emit(branch(address + len(c.words) * 4, fallback))
    return c.finish()


def _contest_effect(address, continuation, displaced, table):
    """Virtual index255: zero Appeal/Jam and a private neutral description."""
    c = _Code(address)
    c.emit(0x546C043E, 0x280C00FF)
    c.conditional(0x40820000, "native")
    _load(c, 3, table)
    c.emit(0x4E800020)
    c.label("native")
    c.emit(displaced, branch(address + len(c.words) * 4 + 4, continuation))
    return c.finish()


def _ordinary_validity(address, continuation):
    """Extend only XD's final scalar ID test; all slot/PP/status checks remain.

    Native r0 already holds the u16 move ID. Its original three-instruction
    sequence returns ``move <355``. The earlier null/empty-slot guards still
    execute, and every native result outside375..381 is unchanged.
    """
    c = _Code(address)
    c.emit(0x28000163)
    c.conditional(0x41800000, "yes")
    c.emit(0x28000177)
    c.conditional(0x41800000, "no")
    c.emit(0x2800017E)
    c.conditional(0x40800000, "no")
    c.label("yes")
    c.emit(0x38600001, branch(address + len(c.words) * 4 + 4, continuation))
    c.label("no")
    c.emit(0x38600000, branch(address + len(c.words) * 4 + 4, continuation))
    return c.finish()


def _menu_move_count(address, continuation, displaced):
    """Allow only owned IDs at the human battle-menu scalar count guard.

    r29 is the selected u16 ID and r0 is the original native table count.
    The following native bge still runs, as does its separate Shadow-end guard.
    No register or global count is changed, and all other comparisons are replayed.
    """
    c = _Code(address)
    c.emit(0x281D0177)
    c.conditional(0x41800000, "native")
    c.emit(0x281D017E)
    c.conditional(0x40800000, "native")
    c.emit(branch(address + len(c.words) * 4, continuation))
    c.label("native")
    c.emit(displaced, branch(address + len(c.words) * 4 + 4, continuation))
    return c.finish()

def _item_locations(original_dol, original_rel, game_id):
    if game_id.startswith("GC6"):
        return dol_layout(original_dol).item_table_offset, _offset(original_dol, _COLO_ITEM_MAPS[game_id]), 548
    if type(original_rel) is not bytes:
        raise FormatError("Additional XD TMs require the original common REL")
    from .engine.inspect_tables import rel_symbols
    from .xd_item_rules import _table_offsets
    _, items = _table_offsets(original_rel)
    symbols = rel_symbols(original_rel, parse_rel(original_rel))
    mapping, count = symbols[68]["offset"], u32(original_rel, symbols[69]["offset"])
    if count != 594 or mapping + 2 * count != items:
        raise FormatError("Unexpected XD item conversion allocation")
    return items, mapping, count


def install_additional_tms(original_dol: bytes, current_dol: bytes, game_id: str, *,
        move_rows: Mapping[int, bytes], compatibility: Mapping[int, Sequence[bool | int]],
        item_message_ids: Mapping[int, tuple[int, int]], original_rel: bytes | None = None,
        current_rel: bytes | None = None, price: int = 3000, tm_plan: Mapping | None = None,
        message_refresh_address: int | None = None, contest_description_id: int = 0xF0470):
    """Install qualified getter/data extensions and optional complete TM plan.

    This is infrastructure, not certification of supplied effect/animation rows.
    Pass ``tm_plan`` instead of separately shuffling the original 50 TMs; its
    source descriptions must match the original item table. The caller writes
    the matching first 50 compatibility columns, and passes the final seven as
    ``compatibility``. Without a plan, prior native TM shuffling is retained.
    The seven acquisition entries are returned for treasure/reward/shop use.
    """
    q = _QUALIFIED.get(game_id)
    if (q is None or type(original_dol) is not bytes or type(current_dol) is not bytes
            or hashlib.sha256(original_dol).hexdigest() != q[0]):
        raise FormatError("Unknown retail executable for additional Fairy TMs")
    fields = extra_item_catalog(price=price)
    blob, compat = _move_rows(move_rows), compatibility_bytes(compatibility)
    planned = _validate_plan(tm_plan) if tm_plan is not None else None
    machine_moves = tuple(row["after_move"] for row in planned[50:]) if planned else MOVE_IDS
    for item_id, move in zip(ITEM_IDS, machine_moves, strict=True):
        fields[item_id]["move"] = move
    if (not isinstance(item_message_ids, Mapping) or set(item_message_ids) != set(ITEM_IDS)
            or any(not isinstance(pair, tuple) or len(pair) != 2
                   or any(type(value) is not int or not 1 <= value <= 0xFFFFFFFF for value in pair)
                   for pair in item_message_ids.values())):
        raise ValueError("Explicit localized name/description IDs for all seven TMs are required")
    for role, (address, length, expected) in q[1].items():
        window = _read(original_dol, address, length)
        if hashlib.sha256(window).hexdigest() != expected or _read(current_dol, address, length) != window:
            raise FormatError(f"Additional TM native {role} window was modified")
    xd = game_id.startswith("GXX")
    if type(contest_description_id) is not int or not 0xF0400 <= contest_description_id < 0xF0500:
        raise ValueError("The neutral Contest description must use the registered private F04 bank")
    items, mapping, count = _item_locations(original_dol, original_rel, game_id)
    source = original_rel if xd else original_dol
    current = current_rel if xd else current_dol
    if type(current) is not bytes or len(current) < len(source):
        raise FormatError("Missing or truncated current item table")
    converted = struct.unpack_from(">" + str(count) + "H", source, mapping)
    if len(current) < mapping + count * 2:
        raise FormatError("Current item ID conversion table was truncated")
    if xd:
        from .xd_species_gameplay import TM_OFFSETS
        native_tm_offset = TM_OFFSETS[game_id]
    else:
        native_tm_offset = dol_layout(original_dol).tm_table_offset
    native_tm_payload = original_dol[native_tm_offset:native_tm_offset + 58 * 8]
    if (len(native_tm_payload) != 58 * 8 or
            current_dol[native_tm_offset + 50 * 8:native_tm_offset + 58 * 8] != native_tm_payload[50 * 8:]):
        raise FormatError("Additional TMs require intact native HM records")
    edits, relocations = [], []
    if planned:
        for i, row in enumerate(planned[:50]):
            pos = native_tm_offset + i * 8
            item = items + (289 + i) * 40
            if (u32(source, item + 20) != row["before_description_id"]
                    or original_dol[pos:pos + 6] != bytes(6)
                    or current_dol[pos:pos + 6] != bytes(6)):
                raise FormatError("The 57-TM plan does not match original item/move table identities")
            edits.append((item + 20, struct.pack(">I", row["after_description_id"])))
    donor = source[items + 289 * ITEM_STRIDE:items + 290 * ITEM_STRIDE]
    if len(donor) != ITEM_STRIDE or donor[0] != 4 or donor[0x1B] != 0:
        raise FormatError("Native TM01 donor row is not qualified")
    if xd:
        donor_relocation = _callback_relocation_any(original_rel, items + 289 * ITEM_STRIDE + 28)
        donor_target = u32(original_rel, donor_relocation + 4)
    for tm in ADDITIONAL_TMS:
        pos = items + tm.item_id * ITEM_STRIDE
        row = source[pos:pos + ITEM_STRIDE]
        if (len(row) != ITEM_STRIDE or row[:4] != b"\x05\x01\0\x01"
                or any(row[4:28]) or any(row[32:])
                or current[pos:pos + ITEM_STRIDE] != row
                or converted[tm.item_id] != 0 or tm.item_id in converted
                or current[mapping + tm.item_id * 2:mapping + tm.item_id * 2 + 2] != b"\0\0"):
            raise FormatError("Additional TM placeholder or external item identity is in use")
        new = bytearray(donor)
        new[1] = 1  # native CheckExportable: keep unknown TM IDs out of a GBA game
        new[2] = 0  # ordinary consumable TM, not an Important/Key Item
        new[0x1B] = tm.machine_index
        struct.pack_into(">H", new, 6, price)
        name, description = item_message_ids[tm.item_id]
        if planned:
            row = planned[tm.number - 1]
            if description != row["before_description_id"]:
                raise FormatError("The 57-TM plan does not match an added move description")
            description = row["after_description_id"]
        struct.pack_into(">II", new, 16, name, description)
        if xd:
            record = _callback_relocation_any(original_rel, pos + 28)
            if (_callback_relocation_any(current_rel, pos + 28) != record
                    or u32(current_rel, record + 4) != u32(original_rel, record + 4)):
                raise FormatError("Additional TM callback relocation changed")
            relocations.append((record + 4, donor_target))
        edits.append((pos, bytes(new)))
    offset, ram, setter, store, code = _reservation(original_dol, current_dol, game_id)
    if (message_refresh_address is not None and (type(message_refresh_address) is not int
            or message_refresh_address % 4 or not ram + 32 <= message_refresh_address < ram + len(code))):
        raise FormatError("Additional TM message refresh must be in a prior owned runtime section")
    move_table = ram + len(code)
    code.extend(blob)
    compatibility_table = ram + len(code)
    code.extend(compat)
    code.extend(bytes(-len(code) % 4))
    machine_table = ram + len(code)
    code.extend(struct.pack(">7H", *machine_moves))
    code.extend(bytes(-len(code) % 4))
    contest_table = None
    if not xd:
        contest_table = ram + len(code)
        code.extend(struct.pack(">BBHI", 0, 0, 0, contest_description_id))
    hooks = []
    site = q[1]["menu_move_count"][0]
    target = ram + len(code)
    code.extend(_menu_move_count(target, site + 4, u32(_read(original_dol, site, 4), 0)))
    hooks.append({"role": "menu_move_count", "address": site, "target": target})
    for role, builder, kwargs in (
            ("machine_move", _machine_move, {"table": machine_table}),
            ("move_getter", _move_getter, {"table": move_table, "refresh": message_refresh_address}),
            ("compatibility", _compatibility, {"table": compatibility_table, "xd": xd}),
            ("display", _display_number, {"xd": xd})):
        site = q[1][role][0]
        target = ram + len(code)
        code.extend(builder(target, site + 4, u32(_read(original_dol, site, 4), 0), **kwargs))
        hooks.append({"role": role, "address": site, "target": target})
    if not xd:
        site = q[1]["contest_effect"][0]
        target = ram + len(code)
        code.extend(_contest_effect(target, site + 4, u32(_read(original_dol, site, 4), 0), contest_table))
        hooks.append({"role": "contest_effect", "address": site, "target": target})
    if message_refresh_address is not None:
        for role, field in (("item_name", 0x10), ("item_description", 0x14)):
            site = q[1][role][0]
            target = ram + len(code)
            code.extend(_item_name_refresh(target, site + 4, u32(_read(original_dol, site, 4), 0),
                                            message_refresh_address, field=field))
            hooks.append({"role": role, "address": site, "target": target})
    if xd:
        site = q[1]["ordinary_validity"][0]
        target = ram + len(code)
        code.extend(_ordinary_validity(target, site + 12))
        hooks.append({"role": "ordinary_validity", "address": site, "target": target})
        site = q[1]["category"][0]
        target = ram + len(code)
        code.extend(_physical_category(target, site + 4, move_register=3,
                                       displaced=u32(_read(original_dol, site, 4), 0)))
        hooks.append({"role": "category", "address": site, "target": target})
    for role in ("damage_category_0", "damage_category_1"):
        site = q[1][role][0]
        word = u32(_read(original_dol, site, 4), 0)
        if word & 0xFC000003 != 0x48000001:
            raise FormatError("Play Rough damage category call is unqualified")
        displacement = word & 0x3FFFFFC
        if displacement & 0x2000000: displacement -= 0x4000000
        target = ram + len(code)
        code.extend(_physical_category(target, site + displacement, move_register=17))
        hooks.append({"role": role, "address": site, "target": target, "link": True})
    code.extend(bytes(-len(code) % 32))
    if ram + len(code) >= 0x81700000:
        raise FormatError("Additional TM extension exceeds reserved memory")
    code[:32] = _arena_guard(ram + len(code), store)
    dol = bytearray(current_dol[:offset])
    dol.extend(bytes(offset - len(dol)))
    dol.extend(code)
    for hook in hooks:
        struct.pack_into(">I", dol, _offset(original_dol, hook["address"]), branch(hook["address"], hook["target"], link=hook.get("link", False)))
    text_base = 0x800030A0 if xd else 0x80003000
    for pos, value in ((8, offset), (0x50, ram), (0x98, len(code)), (setter - text_base, branch(setter, ram))):
        struct.pack_into(">I", dol, pos, value)
    if planned:
        for i, row in enumerate(planned[:50]):
            struct.pack_into(">H", dol, native_tm_offset + i * 8 + 6, row["after_move"])
    out = bytearray(current_rel) if xd else dol
    for pos, data in edits:
        out[pos:pos + len(data)] = data
    for tm in ADDITIONAL_TMS:
        struct.pack_into(">H", out, mapping + tm.item_id * 2, tm.item_id)
    for pos, target in relocations:
        struct.pack_into(">I", out, pos, target)
    return bytes(dol), bytes(out) if xd else None, {
        "version": VERSION, "game_id": game_id, "hooks": hooks,
        "moves": list(MOVE_IDS), "move_row_table": move_table,
        "machine_move_table": machine_table, "compatibility_table": compatibility_table,
        "table_hashes": {"moves": hashlib.sha256(blob).hexdigest(),
                         "compatibility": hashlib.sha256(compat).hexdigest(),
                         "machine_moves": hashlib.sha256(struct.pack(">7H", *machine_moves)).hexdigest(),
                         "native_machine_records": hashlib.sha256(dol[native_tm_offset:native_tm_offset + 400]).hexdigest()},
        "native_tm_table_offset": native_tm_offset, "tm_plan": tm_plan,
        "message_refresh_address": message_refresh_address,
        "neutral_contest_effect_table": contest_table,
        "neutral_contest_description_id": contest_description_id if not xd else None,
        "items": [dict(number=tm.number, item_id=tm.item_id, machine_index=tm.machine_index,
                       move_id=machine_moves[i], default_move_id=tm.move_id,
                       canonical_move_id=dict(zip(MOVE_IDS, CANONICAL_MOVES)).get(machine_moves[i]))
                  for i, tm in enumerate(ADDITIONAL_TMS)],
        "acquisition_catalog": fields, "native_tm_count": 50, "native_hm_count": 8,
        "native_tm_hm_rows_preserved": planned is None, "native_hm_rows_preserved": True,
        "native_compatibility_bytes_preserved": True,
        "native_saved_tm_pocket_capacity": NATIVE_POCKET_CAPACITY,
        "maximum_new_plus_native_tm_kinds": 57, "save_format_unchanged": True,
        "important_item_slots_used": 0, "new_tm_gba_export_disabled": True,
        "localized_message_banks_required": True, "supplied_move_effects_and_animations_must_be_qualified": True,
        "ordinary_move_eligibility_extended": list(MOVE_IDS) if xd else [],
        "human_battle_menu_allowed_added_ids": list(MOVE_IDS),
        "native_global_move_count_unchanged": True,
        "native_pp_and_move_status_restrictions_preserved": True,
    }


def _callback_relocation_any(data, target):
    """Find one native module0 pointer relocation for the known donor callback."""
    native = parse_rel(data)
    sections = {row["index"]: row for row in native["sections"]}
    found = []
    for imported in native["imports"]:
        position, selected, offset = imported["relocations_offset"], None, 0
        for _ in range(len(data) // 8):
            entry = position
            delta, kind, section, addend = struct.unpack_from(">HBBI", data, position)
            position += 8
            if kind == 203:
                break
            if kind == 202:
                selected, offset = section, 0
                continue
            offset += delta
            allocation = sections.get(selected)
            if kind in (0, 201) or allocation is None or allocation["bss"]:
                continue
            if allocation["offset"] + offset == target:
                if kind != 1 or imported["module_id"] != 0 or section != 4 or not addend:
                    raise FormatError("Unexpected native TM callback relocation")
                found.append(entry)
        else:
            raise FormatError("Unterminated native TM relocation stream")
    if len(found) != 1:
        raise FormatError("Native TM callback must have exactly one relocation")
    return found[0]


def read_installed_content(dol: bytes, report: Mapping) -> dict:
    """Read exactly the added data from an installed, owned runtime snapshot."""
    if (type(dol) is not bytes or not isinstance(report, Mapping)
            or report.get("version") != VERSION or report.get("game_id") not in _QUALIFIED
            or not isinstance(report.get("hooks"), list)
            or not isinstance(report.get("table_hashes"), Mapping)):
        raise FormatError("Missing qualified additional TM runtime snapshot")
    from .engine.analyze_game import parse_dol
    section = next((row for row in parse_dol(dol)["sections"] if row["name"] == "text2"), None)
    if section is None:
        raise FormatError("Additional TM runtime has no owned executable section")
    start, end = section["ram_address"], section["ram_address"] + section["size"]
    q = _QUALIFIED[report["game_id"]][1]
    expected_roles = {"machine_move", "move_getter", "compatibility", "display", "menu_move_count"}
    refresh = report.get("message_refresh_address")
    if refresh is not None:
        if type(refresh) is not int or refresh % 4 or not start + 32 <= refresh < end:
            raise FormatError("Additional TM snapshot message refresh is outside its owned section")
        expected_roles.update(("item_name", "item_description"))
    expected_roles.update({"damage_category_0", "damage_category_1"})
    expected_roles.update({"category", "ordinary_validity"} if report["game_id"].startswith("GXX") else
                          {"contest_effect"})
    if (len(report["hooks"]) != len(expected_roles)
            or any(not isinstance(row, Mapping) or not isinstance(row.get("role"), str)
                   for row in report["hooks"])
            or {row["role"] for row in report["hooks"]} != expected_roles):
        raise FormatError("Additional TM snapshot has incomplete native hooks")
    for row in report["hooks"]:
        role, address, target = row.get("role"), row.get("address"), row.get("target")
        if (role not in q or type(address) is not int or address != q[role][0]
                or type(target) is not int or not start + 32 <= target < end
                or u32(_read(dol, address, 4), 0) != branch(address, target, link=row.get("link", False))):
            raise FormatError("Additional TM snapshot native hook is no longer installed")
    payloads = {}
    for key, field, length in (("moves", "move_row_table", 7 * MOVE_STRIDE),
            ("machine_moves", "machine_move_table", 14),
            ("compatibility", "compatibility_table", (NATIONAL_COUNT + 1) * 7)):
        address = report.get(field)
        if type(address) is not int or not start + 32 <= address <= end - length:
            raise FormatError("Additional TM snapshot table is outside its owned section")
        payload = _read(dol, address, length)
        if hashlib.sha256(payload).hexdigest() != report["table_hashes"].get(key):
            raise FormatError("Additional TM snapshot data differs from its installation")
        payloads[key] = payload
    if not report["game_id"].startswith("GXX"):
        contest = report.get("neutral_contest_effect_table")
        description = report.get("neutral_contest_description_id")
        if (type(contest) is not int or not start + 32 <= contest <= end - 8
                or type(description) is not int or not 0xF0400 <= description < 0xF0500
                or _read(dol, contest, 8) != struct.pack(">BBHI", 0, 0, 0, description)):
            raise FormatError("Additional TM snapshot neutral Contest record changed")
    extra_moves = struct.unpack(">7H", payloads["machine_moves"])
    native_offset = report.get("native_tm_table_offset")
    if type(native_offset) is not int or not 0 <= native_offset <= len(dol) - 400:
        raise FormatError("Additional TM snapshot native move table is outside its source")
    native_records = dol[native_offset:native_offset + 400]
    if hashlib.sha256(native_records).hexdigest() != report["table_hashes"].get("native_machine_records"):
        raise FormatError("Additional TM snapshot native move table changed after installation")
    native_moves = tuple(struct.unpack_from(">H", native_records, i * 8 + 6)[0] for i in range(50))
    from .engine.tm_rules import ORIGINAL_TM_MOVES
    if sorted((*native_moves, *extra_moves)) != sorted((*ORIGINAL_TM_MOVES, *MOVE_IDS)):
        raise FormatError("Additional TM snapshot loses or duplicates a move in the 57-TM pool")
    planned = _validate_plan(report["tm_plan"]) if report.get("tm_plan") is not None else None
    if planned and tuple(row["after_move"] for row in planned) != (*native_moves, *extra_moves):
        raise FormatError("Additional TM snapshot differs from its complete plan")
    rows = {move: payloads["moves"][i * MOVE_STRIDE:(i + 1) * MOVE_STRIDE]
            for i, move in enumerate(MOVE_IDS)}
    _move_rows(rows)
    matrix = payloads["compatibility"]
    if any(value not in (0, 1) for value in matrix) or any(matrix[:7]):
        raise FormatError("Additional TM snapshot contains invalid compatibility")
    return {"moves": rows, "tm_moves": list(extra_moves),
            "compatibility": {national: tuple(bool(value) for value in
                matrix[national * 7:(national + 1) * 7]) for national in range(1, NATIONAL_COUNT + 1)},
            "tms": [dict(tm=slot + 1, move=move, item_index=289 + slot if slot < 50 else ITEM_IDS[slot - 50],
                         machine_index=slot if slot < 50 else slot + 8)
                    for slot, move in enumerate((*native_moves, *extra_moves))]}
