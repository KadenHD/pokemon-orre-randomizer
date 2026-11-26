"""Pinned Fairy reference data and lossless generation-III baseline transforms.

Reference species numbers are National Dex IDs. New canonical move IDs must be
translated explicitly; neither namespace is a GameCube table index. Native
effects, table relocation and bytecode remain the caller's qualified work.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import struct

from .engine.analyze_game import FormatError, check_range

VERSION = "fairy-bdsp-pokeapi-v1"
REFERENCE_COMMIT = "de6760be38b60a3024f1d9054330ff265f0dc619"
REFERENCE_VERSION_GROUP = 23  # Brilliant Diamond / Shining Pearl.
LANGUAGES = ("en", "fr", "de", "es", "it", "ja")
RETYPE_MOVE_IDS = (186, 204, 236)
NEW_MOVE_IDS = (574, 577, 583, 584, 585, 605, 608)
FAIRY_SPECIES = (35, 36, 39, 40, 122, 173, 174, 175, 176, 183, 184,
                209, 210, 280, 281, 282, 298, 303)
DATA_SHA256 = "7d92febcfc3f846244d2c2015e1d0aa222d99fc614a11bb16445e111ac0c0cdc"
DATA_DIRECTORY = Path(__file__).resolve().parent / "assets/rules/fairy"
# The API has no mystery slot. GameCube keeps Mystery=9 and Shadow=18.
API_TO_NATIVE_TYPE = {**{index: index - 1 for index in range(1, 10)},
                      **{index: index for index in range(10, 18)}}


@lru_cache(maxsize=1)
def _data() -> dict:
    payload = (DATA_DIRECTORY / "catalog.json").read_bytes()
    if hashlib.sha256(payload).hexdigest() != DATA_SHA256:
        raise FormatError("The pinned Fairy reference data changed")
    data = json.loads(payload)
    if (data.get("schema") != 1 or data.get("version") != VERSION
            or data.get("source_commit") != REFERENCE_COMMIT
            or data.get("reference_version_group", {}).get("id") != REFERENCE_VERSION_GROUP
            or set(map(int, data.get("species", {}))) != set(FAIRY_SPECIES)
            or set(map(int, data.get("moves", {}))) != set(RETYPE_MOVE_IDS + NEW_MOVE_IDS)):
        raise FormatError("The Fairy reference schema is unqualified")
    return data


def reference_manifest() -> dict:
    """Return an independent copy; callers cannot mutate the shared registry."""
    return json.loads(json.dumps(_data(), ensure_ascii=False))


def _national(index: int) -> int:
    if type(index) is not int or not 1 <= index <= 386:
        raise ValueError("Fairy species references require a National Dex ID from 1 to 386")
    return index


def _fairy_type(index: int) -> int:
    if type(index) is not int or not 19 <= index <= 255:
        raise ValueError("The allocated Fairy type must not overwrite Mystery, Shadow or an existing type")
    return index


def native_type(api_type: int, *, fairy_type_id: int) -> int:
    """Convert an API type explicitly, keeping both native special slots intact."""
    _fairy_type(fairy_type_id)
    if type(api_type) is not int or api_type not in (*API_TO_NATIVE_TYPE, 18):
        raise ValueError("Unsupported canonical type")
    return fairy_type_id if api_type == 18 else API_TO_NATIVE_TYPE[api_type]


def _type_pair(values, fairy_type_id):
    values = tuple(native_type(value, fairy_type_id=fairy_type_id) for value in values)
    if len(values) == 1:
        return values * 2
    if len(values) != 2 or values[0] == values[1]:
        raise FormatError("Invalid canonical species typing")
    return values


def species_types(national_dex: int, *, fairy_type_id: int) -> tuple[int, int] | None:
    _national(national_dex)
    _fairy_type(fairy_type_id)
    row = _data()["species"].get(str(national_dex))
    return None if row is None else _type_pair(row["modern_types"], fairy_type_id)


def type_name(language: str = "en", *, uppercase: bool = False) -> str:
    name = _data()["type_names"].get(language, _data()["type_names"]["en"])
    return name.upper() if uppercase else name


def fairy_matchups(*, fairy_type_id: int) -> dict[tuple[int, int], int]:
    """Percent factors for the 35 Fairy pairs; no Mystery/Shadow policy is added."""
    _fairy_type(fairy_type_id)
    return {(native_type(row["attack_type"], fairy_type_id=fairy_type_id),
             native_type(row["defense_type"], fairy_type_id=fairy_type_id)): row["percent"]
            for row in _data()["fairy_matchups"]}


def _move(canonical_id: int) -> dict:
    if type(canonical_id) is not int or canonical_id not in RETYPE_MOVE_IDS + NEW_MOVE_IDS:
        raise ValueError("Unsupported canonical Fairy move")
    return _data()["moves"][str(canonical_id)]


def move_definition(canonical_id: int) -> dict:
    """Canonical metadata, with canonical_effect_id deliberately not 'effect'."""
    return {"canonical_move_id": canonical_id,
            **json.loads(json.dumps(_move(canonical_id), ensure_ascii=False))}


def move_name(canonical_id: int, language: str = "en", *, uppercase: bool = False) -> str:
    names = _move(canonical_id)["names"]
    name = names.get(language, names["en"])
    return name.upper() if uppercase else name.capitalize()


def move_description(canonical_id: int, language: str = "en") -> str:
    descriptions = _move(canonical_id)["descriptions"]
    return descriptions.get(language, descriptions["en"])


def native_move_ids(move_ids: Mapping[int, int]) -> dict[int, int]:
    """Require an explicit safe allocation, while retaining the three old IDs."""
    if not isinstance(move_ids, Mapping) or set(move_ids) not in (set(NEW_MOVE_IDS), set(RETYPE_MOVE_IDS + NEW_MOVE_IDS)):
        raise ValueError("Supply all seven canonical-to-native Fairy move allocations")
    if any(type(key) is not int for key in move_ids):
        raise ValueError("Move IDs must be integers")
    result = dict(zip(RETYPE_MOVE_IDS, RETYPE_MOVE_IDS))
    for canonical_id in NEW_MOVE_IDS:
        index = move_ids[canonical_id]
        if type(index) is not int or not 375 <= index <= 65535:
            raise ValueError("A new move cannot overwrite native ordinary or Shadow moves")
        result[canonical_id] = index
    if len(set(result.values())) != len(result):
        raise ValueError("Fairy move allocations must be distinct")
    if any(move_ids.get(index, index) != index for index in RETYPE_MOVE_IDS):
        raise ValueError("Existing moves keep their native IDs")
    return result


def localized_move_names(move_ids: Mapping[int, int], language: str = "en", *, uppercase=False) -> dict[int, str]:
    return {native_id: move_name(canonical_id, language, uppercase=uppercase)
            for canonical_id, native_id in native_move_ids(move_ids).items()}


def new_move_catalog(move_ids: Mapping[int, int], native_effect_ids: Mapping[int, int], *, fairy_type_id: int) -> dict[int, dict]:
    """Build selection rows using separately qualified native effect IDs.

    These rows are not compiled native move records. Flags such as sound,
    Substitute bypass and 75% draining still require native implementations.
    """
    mapping = native_move_ids(move_ids)
    _fairy_type(fairy_type_id)
    if (not isinstance(native_effect_ids, Mapping) or set(native_effect_ids) != set(NEW_MOVE_IDS)
            or any(type(value) is not int or not 0 <= value <= 65535 for value in native_effect_ids.values())):
        raise ValueError("Every new move needs its qualified native effect ID")
    result = {}
    for canonical_id in NEW_MOVE_IDS:
        row = move_definition(canonical_id)
        result[mapping[canonical_id]] = {
            **row, "index": mapping[canonical_id], "pp": row["pp"],
            "type": fairy_type_id, "power": row["power"] or 0,
            "accuracy": row["accuracy"] or 0, "always_hits": row["accuracy"] is None,
            "effect": native_effect_ids[canonical_id],
        }
    return result


def learning_records(national_dex: int) -> tuple[dict, ...]:
    """Exact BDSP methods: 1=level-up, 2=egg, 4=machine; level 0=evolution."""
    _national(national_dex)
    return tuple(dict(row) for row in _data()["learning"].get(str(national_dex), ()))


def compatibility(national_dex: int, *, method: str = "machine") -> tuple[bool, ...]:
    """Return seven columns in NEW_MOVE_IDS order.

    'machine' is the actual BDSP TM evidence. 'learnable' also accepts natural
    and egg access, a distinct possible policy for the newly authored TMs.
    It is never silently substituted for official machine compatibility.
    """
    if method not in ("machine", "learnable"):
        raise ValueError("Select machine or learnable compatibility explicitly")
    known = {row["move"] for row in learning_records(national_dex)
             if method == "learnable" or row["method"] == 4}
    return tuple(index in known for index in NEW_MOVE_IDS)


@dataclass(frozen=True)
class LearnsetPlan:
    national_dex: int
    native: tuple[tuple[int, int], ...]
    learnset: tuple[tuple[int, int], ...]
    additions: tuple[tuple[int, int], ...]
    evolution_moves: tuple[int, ...]
    native_capacity: int

    @property
    def requires_relocation(self) -> bool:
        return len(self.learnset) > self.native_capacity

    @property
    def overflow_records(self) -> tuple[tuple[int, int], ...]:
        return self.learnset[self.native_capacity:]

    def require_inline_capacity(self) -> tuple[tuple[int, int], ...]:
        if self.requires_relocation:
            raise FairyLearnsetOverflow(self)
        return self.learnset


class FairyLearnsetOverflow(ValueError):
    def __init__(self, plan: LearnsetPlan):
        self.plan = plan
        super().__init__(f"Species {plan.national_dex} needs {len(plan.learnset)} learnset rows; "
                         f"its native capacity is {plan.native_capacity}. Relocate without truncation.")


def merge_natural_learnset(national_dex: int, native: Sequence[tuple[int, int]],
                          move_ids: Mapping[int, int], *, native_capacity: int = 19) -> LearnsetPlan:
    """Keep native moves/levels and add absent Fairy level-up moves losslessly.

    Evolution-only moves stay separate. They must never become the native
    zero-level terminator or an invented level-1 learning event.
    """
    _national(national_dex)
    mapping = native_move_ids(move_ids)
    if type(native_capacity) is not int or not 1 <= native_capacity <= 65535:
        raise ValueError("Invalid native learnset capacity")
    before = tuple(tuple(row) for row in native)
    if any(len(row) != 2 or type(row[0]) is not int or not 1 <= row[0] <= 100
           or type(row[1]) is not int or not 1 <= row[1] <= 65535 for row in before):
        raise ValueError("Native learnsets contain active (level, move) records only")
    if any(before[index][0] > before[index + 1][0] for index in range(len(before) - 1)):
        raise ValueError("Native learnset levels must be ordered")
    existing = {move for _level, move in before}
    additions, evolution = [], []
    for row in learning_records(national_dex):
        if row["method"] != 1:
            continue
        move = mapping[row["move"]]
        if row["level"] == 0:
            if move not in evolution:
                evolution.append(move)
        elif move not in existing:
            additions.append((row["level"], move))
            existing.add(move)
    # Python's stable sort leaves original ties and their order intact.
    merged = tuple(sorted((*before, *additions), key=lambda row: row[0]))
    return LearnsetPlan(national_dex, before, merged, tuple(additions), tuple(evolution), native_capacity)


def project_catalog(catalog: Mapping[int, Mapping], *, fairy_type_id: int,
                    move_ids: Mapping[int, int] | None = None, enabled: bool = True) -> dict:
    """Project parsed species rows without treating their keys as National IDs.

    A supplied move allocation also projects full natural learnsets. The native
    installer must inspect the corresponding LearnsetPlans for relocation.
    """
    if type(enabled) is not bool:
        raise ValueError("Fairy enablement must be a boolean")
    if not enabled:
        return catalog
    _fairy_type(fairy_type_id)
    if move_ids is not None:
        native_move_ids(move_ids)
    result = {}
    for index, source in catalog.items():
        national = _national(source["national_dex"])
        row = dict(source)
        types = species_types(national, fairy_type_id=fairy_type_id)
        if types is not None:
            row["types"] = types
        if move_ids is not None:
            row["learnset"] = merge_natural_learnset(national, row.get("learnset", ()), move_ids).learnset
        result[index] = row
    return result


def _table(rel: bytes, table: Mapping, minimum_stride: int, name: str) -> tuple[int, int, int]:
    try:
        start, count, stride = (table[key] for key in ("offset", "count", "stride"))
    except (KeyError, TypeError) as error:
        raise FormatError(f"Missing Fairy {name} layout") from error
    if (any(type(value) is not int for value in (start, count, stride))
            or start < 0 or not 1 <= count <= 65535 or stride < minimum_stride):
        raise FormatError(f"Invalid Fairy {name} layout")
    check_range(rel, start, count * stride, f"Fairy {name} table")
    return start, count, stride


def apply_type_baseline(rel: bytes, tables: Mapping, *, game: str, fairy_type_id: int,
                        enabled: bool = True) -> tuple[bytes, dict]:
    """Retag 18 species and three existing moves before randomizing properties.

    The caller must authenticate the retail original and provide its layouts.
    This transform preserves every byte outside the selected type fields and
    accepts its own output idempotently. It does not install a type chart.
    """
    if type(enabled) is not bool:
        raise ValueError("Fairy enablement must be a boolean")
    if not enabled:
        return rel, {"applied": False, "version": VERSION, "changed_bytes": 0}
    if game not in ("colosseum", "xd"):
        raise ValueError("Select colosseum or xd")
    _fairy_type(fairy_type_id)
    if not isinstance(rel, bytes):
        raise ValueError("The authenticated baseline must be bytes")
    species = _table(rel, tables.get("species"), 0x34, "species")
    moves = _table(rel, tables.get("moves"), 5, "moves")
    if max(species[0], moves[0]) < min(species[0] + species[1] * species[2], moves[0] + moves[1] * moves[2]):
        raise FormatError("Fairy species and move tables overlap")
    if moves[1] <= max(RETYPE_MOVE_IDS):
        raise FormatError("The Fairy baseline move table is incomplete")
    output, permitted, species_edits, move_edits, seen = bytearray(rel), set(), [], [], set()
    national_offset = 0x10 if game == "colosseum" else 0x0E
    for index in range(species[1]):
        pos = species[0] + index * species[2]
        national = struct.unpack_from(">H", rel, pos + national_offset)[0]
        row = _data()["species"].get(str(national))
        if row is None:
            continue
        if national in seen:
            raise FormatError("Duplicate National Dex ID in the Fairy baseline")
        seen.add(national)
        before = tuple(rel[pos + 0x30:pos + 0x32])
        after = _type_pair(row["modern_types"], fairy_type_id)
        legacy = _type_pair(row["native_generation_three_types"], fairy_type_id)
        if before not in (legacy, after):
            raise FormatError("Apply the Fairy baseline before randomized species types")
        if before != after:
            output[pos + 0x30:pos + 0x32] = bytes(after)
            species_edits.append({"species_index": index, "national_dex": national,
                                  "before": before, "after": after})
        permitted.update((pos + 0x30, pos + 0x31))
    if seen != set(FAIRY_SPECIES):
        raise FormatError("The Fairy baseline species table is incomplete")
    for index in RETYPE_MOVE_IDS:
        pos = moves[0] + index * moves[2]
        before = rel[pos + 2]
        if not rel[pos + 1] or before not in (0, fairy_type_id):
            raise FormatError("Apply the Fairy baseline before changing native move types")
        output[pos + 2] = fairy_type_id
        if before != fairy_type_id:
            move_edits.append({"move_index": index, "before": before, "after": fairy_type_id})
        permitted.add(pos + 2)
    result = bytes(output)
    changed = {index for index, (before, after) in enumerate(zip(rel, result, strict=True)) if before != after}
    if changed - permitted:
        raise AssertionError("Fairy baseline escaped its type-field whitelist")
    return result, {"applied": True, "version": VERSION, "reference_version_group": REFERENCE_VERSION_GROUP,
                    "type_id": fairy_type_id, "species_edits": species_edits, "move_edits": move_edits,
                    "changed_bytes": len(changed), "only_type_fields_changed": True}


def apply_levelup_baseline(rel: bytes, species_table: Mapping, *, game: str,
                           move_ids: Mapping[int, int], enabled: bool = True) -> tuple[bytes, dict]:
    """Merge the selected Fairy learning records into qualified inline tables.

    All six retail tables fit this dataset's additions in their 19 native slots.
    A later larger dataset must relocate an overflowing row; this routine raises
    with its complete plan. It never truncates a learnset or writes a level-0
    evolution event into an end marker. The two evolution events are reported
    separately for a qualified evolution handler.
    """
    if type(enabled) is not bool:
        raise ValueError("Fairy enablement must be a boolean")
    if not enabled:
        return rel, {"applied": False, "version": VERSION, "changed_bytes": 0}
    if game not in ("colosseum", "xd") or not isinstance(rel, bytes):
        raise ValueError("Supply a qualified Colosseum or XD byte baseline")
    native_move_ids(move_ids)
    national_offset, learning_offset = (0x10, 0xBA) if game == "colosseum" else (0x0E, 0xC4)
    start, count, stride = _table(rel, species_table, learning_offset + 19 * 4, "species")
    output, permitted, edits, evolution, seen = bytearray(rel), set(), [], [], set()
    for index in range(count):
        pos = start + index * stride
        national = struct.unpack_from(">H", rel, pos + national_offset)[0]
        if not 1 <= national <= 386:
            continue
        if national in seen:
            raise FormatError("Duplicate National Dex ID in the Fairy learning baseline")
        seen.add(national)
        records = []
        for slot in range(19):
            field = pos + learning_offset + slot * 4
            level, move = rel[field], struct.unpack_from(">H", rel, field + 2)[0]
            if level:
                records.append((level, move))
            elif move:
                raise FormatError("A Fairy learnset terminator contains an active move")
        plan = merge_natural_learnset(national, records, move_ids)
        if plan.evolution_moves:
            evolution.append({"species_index": index, "national_dex": national,
                              "moves": plan.evolution_moves})
        if not plan.additions:
            continue
        complete = plan.require_inline_capacity()
        # All qualified retail records use zero in this field. Do not invent
        # semantics for a foreign nonzero flag while moving its active rows.
        if any(rel[pos + learning_offset + slot * 4 + 1] for slot in range(19)):
            raise FormatError("Unknown native learnset flag requires qualification")
        for slot in range(19):
            field = pos + learning_offset + slot * 4
            level, move = complete[slot] if slot < len(complete) else (0, 0)
            output[field] = level
            struct.pack_into(">H", output, field + 2, move)
            permitted.update((field, field + 2, field + 3))
        edits.append({"species_index": index, "national_dex": national,
                      "before": plan.native, "after": plan.learnset, "additions": plan.additions})
    if seen != set(range(1, 387)):
        raise FormatError("The Fairy learning baseline must cover all 386 native species")
    result = bytes(output)
    changed = {index for index, (before, after) in enumerate(zip(rel, result, strict=True)) if before != after}
    if changed - permitted:
        raise AssertionError("Fairy learning baseline escaped its record-field whitelist")
    return result, {"applied": True, "version": VERSION, "reference_version_group": REFERENCE_VERSION_GROUP,
                    "species_edits": edits, "rows_added": sum(len(row["additions"]) for row in edits),
                    "evolution_events": evolution, "changed_bytes": len(changed),
                    "only_level_and_move_fields_changed": True, "native_capacity": 19,
                    "all_native_records_preserved": True}
