"""Stage specimen-only Shadow resources in the existing retail model archives."""
from __future__ import annotations

from dataclasses import dataclass
import struct

from .deoxys import DEOXYS, FORM_ORDER
from .deoxys_resources import MODEL_RESOURCES, extract_xd_deoxys_models
from .engine.actor_archive import append_actor_models
from .engine.analyze_game import FormatError, parse_fsys
from .engine.plusle_actor import _model_resource, _XD_MODEL_TABLE
from .engine.postgame_lugia_model import _LAYOUTS as COLO_MODELS
from .engine.rebuild_iso import decoded_member
from .engine.shadow_lugia_face import ARCHIVE as FACE_ARCHIVE, COLOSSEUM_RESOURCE, SOURCE_RESOURCE
from .legendary_shadow_assets import PACK, SPECIES, STEMS, VERSION, build_model, face, stem_for

MODEL_KEY = 0x7400
FACE_KEY = 0x7500
FIRST_RESOURCE = 0x7CA0


@dataclass(frozen=True)
class Route:
    species: int
    form: int
    index: int
    group: int
    archive: str = ''

    @property
    def model_key(self):
        return MODEL_KEY + self.index

    def face_key(self, shiny):
        return FACE_KEY + 2 * self.index + int(shiny)

    def model_resource(self, shiny):
        return (FIRST_RESOURCE + 2 * self.index + int(shiny)) << 16 | 0x1E00

    def face_resource(self, shiny, *, xd):
        return (FIRST_RESOURCE + 2 * self.index + int(shiny and xd)) << 16 | 0x1200


def _member(source, identifier):
    matches = [row for row in parse_fsys(source)['members'] if int(row['identifier_raw'], 16) == identifier]
    if len(matches) != 1:
        raise FormatError(f'missing original legendary Shadow model donor {identifier:08x}')
    return decoded_member(source, matches[0])


def field_model(original, game_id, read_archive, species, form, *, shiny, scale):
    """Use the same reviewed material recipe for a verified scripted specimen."""
    stem = stem_for(species, form)
    if stem is None or not PACK.is_file():
        return None
    from .engine.plusle_actor import _FIELD_MOTIONS, _field_model, _pkx_idle_motion

    xd = game_id in _XD_MODEL_TABLE
    game = 'xd' if xd else 'colosseum'
    table, stride = (_XD_MODEL_TABLE[game_id], 8) if xd else (COLO_MODELS[game_id][3], 12)
    group, member = struct.unpack_from('>II', original, table + stride * species)
    name = _model_resource(read_archive('GSfsys.toc'), group)
    donor = _member(read_archive(name), member)
    if species == DEOXYS and form:
        if xd:
            donor = extract_xd_deoxys_models(read_archive)[FORM_ORDER[form], False]
        else:
            from .deoxys_assets import xd_models
            from .deoxys_resources import convert_deoxys_model
            donor = convert_deoxys_model(xd_models()[FORM_ORDER[form], False], donor,
                                          form=FORM_ORDER[form], shiny=False)
    model = build_model(game, stem, shiny, donor)
    if model is None:
        return None
    idle = _pkx_idle_motion(model, xd=xd)
    return _field_model(model, header_size=0xE60 if xd else 0x40, scale=scale, motion_indices=(idle,) * _FIELD_MOTIONS)


def stage_appearances(original, game_id, read_archive, updates, species, *, cancel=None):
    """Build both variants before adding a route. Incompatible donors stay native."""
    game = 'xd' if game_id in _XD_MODEL_TABLE else 'colosseum'
    xd = game == 'xd'
    toc = read_archive('GSfsys.toc')
    table, stride = (_XD_MODEL_TABLE[game_id], 8) if xd else (COLO_MODELS[game_id][3], 12)
    face_members, routes, unavailable = {}, [], []
    xd_forms = None
    for species_id in sorted(set(species) & SPECIES.keys()):
        if cancel is not None:
            cancel()
        group, donor_id = struct.unpack_from('>II', original, table + stride * species_id)
        if not 0 < group < 0x8000:
            raise FormatError('invalid native legendary model directory')
        name = _model_resource(toc, group)
        source = read_archive(name)
        if parse_fsys(source)['group_id'] != group:
            raise FormatError('legendary Shadow model archive group mismatch')
        staged = updates.get(name, source)
        models = {}
        for form in range(4 if species_id == DEOXYS else 1):
            stem = stem_for(species_id, form)
            if form and xd:
                if xd_forms is None:
                    xd_forms = extract_xd_deoxys_models(read_archive)
                donor = xd_forms[FORM_ORDER[form], False]
            else:
                donor = _member(staged, MODEL_RESOURCES[FORM_ORDER[form], False] if form else donor_id)
            variants = [build_model(game, stem, shiny, donor) for shiny in (False, True)]
            if any(value is None for value in variants):
                unavailable.append(stem)
                continue
            route = Route(species_id, form, STEMS.index(stem), group, name)
            for shiny, value in zip((False, True), variants, strict=True):
                models[route.model_resource(shiny)] = (f'orre_{stem}_{int(shiny)}', value)
                if xd or not shiny:
                    face_members[route.face_resource(shiny, xd=xd)] = (f'orre_face_{stem}_{int(shiny)}',
                                                                      face(game, stem, shiny))
            routes.append(route)
        if models:
            updates[name] = append_actor_models(staged, {}, source, donor_id, models, resource_type=0x1E00)
    if face_members:
        source = updates.get(FACE_ARCHIVE)
        if source is None:
            source = read_archive(FACE_ARCHIVE)
        donor = SOURCE_RESOURCE if xd else COLOSSEUM_RESOURCE
        if not any(int(row['identifier_raw'], 16) == donor for row in parse_fsys(source)['members']):
            donor, = [int(row['identifier_raw'], 16) for row in parse_fsys(source)['members']
                      if row['name'] == 'face249' and row['identifier_raw'].endswith('1200')]
        updates[FACE_ARCHIVE] = append_actor_models(source, {}, source, donor, face_members, resource_type=0x1200)
    return routes, unavailable


def install_appearances(original, current, game_id, read_archive, updates, species, *, keep, cancel=None):
    from .legendary_shadow_runtime import install_runtime

    wanted = set(species) & SPECIES.keys()
    if not wanted or not PACK.is_file():
        return current, {'version': VERSION, 'stems': [], 'hooks': []}
    routes, unavailable = stage_appearances(original, game_id, read_archive, updates, wanted, cancel=cancel)
    output, hooks = install_runtime(original, current, game_id, routes, keep=keep)
    return output, {'version': VERSION, 'stems': [STEMS[route.index] for route in routes],
                    'model_archives': sorted({route.archive for route in routes}),
                    'unavailable_donors': unavailable, 'keep_after_purification': keep, 'hooks': hooks}
