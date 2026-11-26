"""Scoped, immutable Fairy content shared by existing generation readers.

The caller supplies its qualified native move rows and authenticated original
REL. Original bytes remain available for fingerprints and structural layouts.
Only their deterministic species/move reference view is projected. A context
does not certify that its prepared rows have been installed in a final DOL.
"""
from __future__ import annotations

from collections.abc import Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import hashlib
import json
import struct

from .engine.analyze_game import FormatError, parse_rel, u32
from .engine.inspect_tables import rel_symbols
from .fairy_data import (
    NEW_MOVE_IDS, apply_levelup_baseline, apply_type_baseline,
    new_move_catalog, project_catalog,
)

FAIRY_TYPE = 19
NATIVE_MOVES = tuple(range(375, 382))
NATIVE_MOVE_MAP = dict(zip(NEW_MOVE_IDS, NATIVE_MOVES, strict=True))
_XD_REL_SHA256 = {
    "GXXP01": "10f741259d264315ba3d44af8e87bef3294ba6cc3d7df0db653d533ba4404ed8",
    "GXXE01": "ef03647b307d4e423dc4c71314c97eae55ffffdaa24b1fd50d90666333284450",
    "GXXJ01": "97c6b45b123403561208b830613dbce6d4f4826602090d5102bb45fd223b2d78",
}
_CURRENT: ContextVar[FairyGameplayContent | None] = ContextVar("orre_fairy_gameplay", default=None)


def _family(game_id: str) -> str:
    if game_id in ("GC6P01", "GC6E01", "GC6J01"):
        return "colosseum"
    if game_id in ("GXXP01", "GXXE01", "GXXJ01"):
        return "xd"
    raise ValueError("Unsupported Fairy game ID")


def _layouts(original_rel: bytes, game_id: str) -> dict:
    family = _family(game_id)
    if family == "colosseum":
        from .engine.gameplay_rules import expanded_layout
        from .engine.rel_regions import region_for_rel
        if region_for_rel(original_rel).game_id != game_id:
            raise FormatError("Fairy content and original REL regions differ")
        return expanded_layout(original_rel)
    if hashlib.sha256(original_rel).hexdigest() != _XD_REL_SHA256[game_id]:
        raise FormatError("Fairy content requires the matching original XD REL")
    symbols = rel_symbols(original_rel, parse_rel(original_rel))
    if (u32(original_rel, symbols[89]["offset"]) != 415
            or u32(original_rel, symbols[125]["offset"]) != 375):
        raise FormatError("Unexpected native XD Fairy layouts")
    return {"species": {"offset": symbols[88]["offset"], "count": 415, "stride": 0x124},
            "moves": {"offset": symbols[124]["offset"], "count": 375, "stride": 0x38}}


def catalog_from_rows(game_id: str, move_rows: Mapping[int, bytes]) -> dict[int, dict]:
    """Decode actual row fields; do not substitute canonical effect numbers."""
    family = _family(game_id)
    if not isinstance(move_rows, Mapping) or set(move_rows) != set(NATIVE_MOVES):
        raise ValueError("All seven prepared native Fairy rows are required")
    power_offset, effect_offset = (0x17, 0x1A) if family == "colosseum" else (0x19, 0x1C)
    effects = {}
    for index, row in move_rows.items():
        if (type(index) is not int or type(row) is not bytes or len(row) != 0x38
                or not row[1] or row[2] != FAIRY_TYPE or not u32(row, 0x20)):
            raise ValueError("Invalid prepared native Fairy move row")
        effects[NEW_MOVE_IDS[NATIVE_MOVES.index(index)]] = struct.unpack_from(">H", row, effect_offset)[0]
    catalog = new_move_catalog(NATIVE_MOVE_MAP, effects, fairy_type_id=FAIRY_TYPE)
    for index, row in move_rows.items():
        reference = catalog[index]
        if (row[1] != reference["pp"] or row[power_offset] != reference["power"]
                or row[4] not in ({0, 100} if reference["always_hits"] else {reference["accuracy"]})):
            raise FormatError("Prepared Fairy row differs from its declared move metadata")
        reference.update(pp=row[1], power=row[power_offset], accuracy=row[4], type=row[2],
                         message_id=u32(row, 0x20))
    return catalog


@dataclass(frozen=True)
class FairyGameplayContent:
    game_id: str
    original_rel: bytes
    original_dol: bytes
    baseline_rel: bytes
    rows: tuple[tuple[int, bytes], ...]
    baseline_changes: tuple[tuple[int, int, int], ...]
    reports_json: tuple[bytes, bytes]

    @property
    def family(self):
        return _family(self.game_id)

    @property
    def moves(self) -> dict[int, dict]:
        return catalog_from_rows(self.game_id, dict(self.rows))

    @property
    def move_rows(self) -> dict[int, bytes]:
        return dict(self.rows)

    @property
    def move_map(self) -> dict[int, int]:
        return dict(NATIVE_MOVE_MAP)

    def apply_baseline(self, current_rel: bytes) -> bytes:
        """Overlay only baseline differences before random traits/learnsets."""
        if not isinstance(current_rel, bytes) or len(current_rel) != len(self.original_rel):
            raise FormatError("Fairy baseline REL lengths differ")
        if current_rel == self.original_rel:
            return self.baseline_rel
        result = bytearray(current_rel)
        for position, before, after in self.baseline_changes:
            if result[position] not in (before, after):
                raise FormatError("Apply the Fairy baseline before randomized type or learnset edits")
            result[position] = after
        return bytes(result)

    def project_species(self, catalog, source_rel: bytes):
        # Final/randomized properties are authoritative. Project only the exact
        # authenticated source, never a same-species final catalog by guesswork.
        if source_rel == self.original_rel:
            return project_catalog(catalog, fairy_type_id=FAIRY_TYPE, move_ids=NATIVE_MOVE_MAP)
        return catalog

    def project_moves(self, catalog, source_rel: bytes):
        result = dict(catalog)
        if source_rel == self.original_rel:
            from .fairy_data import RETYPE_MOVE_IDS
            for index in RETYPE_MOVE_IDS:
                if index in result:
                    result[index] = {**result[index], "type": FAIRY_TYPE}
        result.update(self.moves)
        return result

    def summary(self) -> dict:
        return {"game_id": self.game_id, "type_id": FAIRY_TYPE,
                "source_rel_sha256": hashlib.sha256(self.original_rel).hexdigest(),
                "type_baseline": json.loads(self.reports_json[0]),
                "learning_baseline": json.loads(self.reports_json[1]),
                "prepared_move_ids": list(NATIVE_MOVES),
                "prepared_rows_do_not_prove_installation": True}


def content_from_rows(game_id: str, move_rows: Mapping[int, bytes], *,
                      original_rel: bytes, original_dol: bytes, tables: Mapping | None = None) -> FairyGameplayContent:
    """Prepare an immutable reference from explicitly supplied qualified rows.

    Production callers authenticate the disc and omit layouts. Explicit table
    layouts support the same bounded transforms in portable fixtures.
    """
    _family(game_id)
    catalog_from_rows(game_id, move_rows)
    if not isinstance(original_rel, bytes) or not isinstance(original_dol, bytes):
        raise ValueError("Original REL and DOL bytes must be immutable")
    tables = _layouts(original_rel, game_id) if tables is None else tables
    typed, type_report = apply_type_baseline(original_rel, tables, game=_family(game_id), fairy_type_id=FAIRY_TYPE)
    baseline, learning_report = apply_levelup_baseline(typed, tables["species"], game=_family(game_id), move_ids=NATIVE_MOVE_MAP)
    changes = tuple((position, before, after)
                    for position, (before, after) in enumerate(zip(original_rel, baseline, strict=True)) if before != after)
    return FairyGameplayContent(game_id, original_rel, original_dol, baseline,
        tuple(sorted(move_rows.items())), changes,
        tuple(json.dumps(report, ensure_ascii=False).encode('utf-8') for report in (type_report, learning_report)))


def current_context(game: str | None = None) -> FairyGameplayContent | None:
    context = _CURRENT.get()
    if context is not None and game is not None and game not in (context.family, context.game_id):
        raise FormatError("A Fairy generation context crossed into another game")
    return context


@contextmanager
def fairy_gameplay_context(content: FairyGameplayContent | None):
    if content is not None and not isinstance(content, FairyGameplayContent):
        raise TypeError("Expected prepared Fairy content or None")
    token = _CURRENT.set(content)
    try:
        yield content
    finally:
        _CURRENT.reset(token)
