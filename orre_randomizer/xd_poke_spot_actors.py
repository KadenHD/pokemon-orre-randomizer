"""Keep the three XD Poké Spot actors in sync with their encounter rosters."""

from functools import partial
import re
import struct

from .engine.actor_archive import append_actor_models
from .engine.analyze_game import FormatError, check_range, parse_fsys
from .engine.inspect_tables import u16
from .engine.plusle_actor import companion_scale, load_actor_model
from .engine.rebuild_iso import repack_fsys
from .xd_gifts import _patch_script


_SPOT_ACTORS = {
    "rock": ("esaba_A", (0x16600400, 0x165A0400, 0x165F0400)),
    "oasis": ("esaba_B", (0x165C0400, 0x165B0400, 0x187A0400)),
    "cave": ("esaba_C", (0x20560400, 0x161D0400, 0x16610400)),
}
_SHARED_ARCHIVE = "people_archive.fsys"
_CAVE_SHARED_ONLY = 0x20560400
_FIRST_SHINY_MODEL = 0x23000400


def _replace_models(archive, replacements, *, shared_only=()):
    members = parse_fsys(archive)["members"]
    updated = {}
    found = set()
    for member in members:
        resource = int(member["identifier_raw"], 16)
        if resource in replacements:
            if resource in found:
                raise FormatError("duplicate Poké Spot model")
            found.add(resource)
            updated[member["index"]] = replacements[resource]
    if replacements.keys() - found - set(shared_only):
        raise FormatError("missing Poké Spot model")
    return repack_fsys(archive, updated)[0] if updated else archive


def _patch_species_checks(script, *, branches):
    updated = bytearray(script)
    for original, species, resource, shiny_resource, filter_index in branches:
        compare = struct.pack(">II", 0x02010000, original)
        model = struct.pack(">II", 0x02010000, resource)
        # Species comparison followed by Character.setModel for this branch.
        pattern = (re.escape(compare) + rb"\x01\x30\x00\x00\x0b.{3}\x10.{3}"
                   + re.escape(model) + rb"\x03\x03.{2}\x09\x23\x00\x46")
        hits = list(re.finditer(pattern, script, re.DOTALL))
        if len(hits) != 1 or hits[0].start() % 4:
            raise FormatError("unexpected Poké Spot appearance branch")
        start = hits[0].start()
        # The stock branch calls Pokespot.isEncounterShiny, then applies one
        # species-specific filter. Use the same condition and argument layout
        # to select the randomized Pokémon's shiny model instead.
        check_range(script, start + 0x58, 16, "Poké Spot shiny model call")
        actor = struct.unpack_from(">I", script, start + 0x1C)[0]
        if (struct.unpack_from(">I", script, start + 0x40)[0] != 0x093C0014
                or struct.unpack_from(">4I", script, start + 0x58)
                != (0x02010000, filter_index, actor, 0x09230070)):
            raise FormatError("unexpected Poké Spot shiny branch")
        struct.pack_into(">I", updated, start + 4, species)
        struct.pack_into(">I", updated, start + 0x5C, shiny_resource)
        struct.pack_into(">I", updated, start + 0x64, 0x09230046)
    return bytes(updated)


def patch_poke_spot_actors(rows, original_dol, rel, species_offset, game_id, read_archive, updates):
    """Retarget only the regular encounter branches. Native special actors are separate."""
    shared_models = {}
    shiny_models = {}
    report = []
    for spot_index, (spot, (room, resources)) in enumerate(_SPOT_ACTORS.items()):
        selected = [row for row in rows if row["spot"] == spot]
        native = {row["original"]: resource for row, resource in zip(selected, resources, strict=True)}
        drawn = {row["species"] for row in selected}
        if len(drawn) != len(native):
            raise FormatError("Poké Spot appearance branches require distinct species")
        unused = ((index, old, resource) for index, (old, resource) in enumerate(native.items()) if old not in drawn)
        branches = []
        room_models = {}
        # Native residents retain their species-specific field animations even
        # when they move to a different encounter slot within the same spot.
        for row in selected:
            species = row["species"]
            if species in native:
                continue
            slot, old, resource = next(unused)
            record = species_offset + species * 0x124
            national = u16(rel, record + 0x0E)
            scale = companion_scale(national, 1.0)
            model_id = u16(rel, record + 0x2E)
            room_models[resource] = load_actor_model(original_dol, game_id, model_id, read_archive, scale=scale)
            filter_index = spot_index * 3 + slot
            shiny_id = _FIRST_SHINY_MODEL + (filter_index << 16)
            shiny_models[shiny_id] = (
                f"orre_spot_shiny_{filter_index + 1}",
                load_actor_model(original_dol, game_id, model_id, read_archive, scale=scale, shiny=True),
            )
            branches.append((old, species, resource, shiny_id, filter_index))
            report.append({"spot": spot, "species": species, "model_resource": resource,
                           "shiny_model_resource": shiny_id, "scale": scale})
        if not branches:
            continue
        name = room + ".fsys"
        source = updates[name] if name in updates else read_archive(name)
        source = _patch_script(source, room, partial(_patch_species_checks, branches=branches))
        updates[name] = _replace_models(source, room_models, shared_only=(_CAVE_SHARED_ONLY,))
        shared_models.update(room_models)
    if shared_models:
        source = updates[_SHARED_ARCHIVE] if _SHARED_ARCHIVE in updates else read_archive(_SHARED_ARCHIVE)
        # Character.setModel resolves the shared archive before room-local
        # aliases. Give the shiny models their own IDs to keep both palettes.
        updated = _replace_models(source, shared_models)
        updates[_SHARED_ARCHIVE] = append_actor_models(updated, {}, source, _CAVE_SHARED_ONLY, shiny_models)
    return report
