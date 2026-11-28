"""The bonus Shadow Lugia's room-local model, separate from Eagun's companion."""
from __future__ import annotations

from .actor_archive import append_actor_models
from .analyze_game import FormatError, parse_rel, sha256, u32
from .inspect_tables import rel_symbols
from .plusle_actor import _field_model, _pkx_idle_motion, _FIELD_MOTIONS, companion_scale, load_actor_model
from .postgame_lugia_model import verified_model_asset
from .shadow_lugia_palette import make_shadow_lugia_shiny

ACTOR = 5
MODEL = 69
RESOURCE = 0x009B0400
SCALE = 0.38
# Leave room for the wings through their complete idle cycle, including when
# Lugia turns toward Eagun. The former position crossed Nascour's shoulder.
POSITION = (-32.0, 0.0, 0.0)


def append_field_model(source, original_common, *, shiny, species=249, original_dol=None,
                       read_archive=None, seed="postgame-lugia", deoxys_form=0):
    """Clone only a room-local DAT; never replace the global model or Pikachu."""
    symbols = rel_symbols(original_common, parse_rel(original_common))
    if u32(original_common, symbols[73]["offset"]) != 150:
        raise FormatError("unexpected native character-model allocation")
    row = symbols[72]["offset"] + MODEL * 0x2C
    if u32(original_common, row + 12) != RESOURCE:
        raise FormatError("unexpected unused shrine character-model resource")
    if species == 249:
        model, manifest = verified_model_asset()
        if shiny:
            model = make_shadow_lugia_shiny(model, xd=False)
        idle, scale = _pkx_idle_motion(model, xd=False), SCALE
        field = _field_model(model, scale=scale, motion_indices=(idle,) * _FIELD_MOTIONS)
        source_hash = manifest["converted_sha256"]
    else:
        from .gameplay_rules import expanded_layout
        from .species_rules import species_catalog
        from .unown_form import unown_form
        from .rel_regions import region_for_rel
        catalog = species_catalog(original_common, expanded_layout(original_common))
        if species not in catalog or original_dol is None or read_archive is None:
            raise FormatError("missing native model data for the bonus Shadow replacement")
        national = catalog[species]["national_dex"]
        scale = companion_scale(national, 0.65)
        game_id = region_for_rel(original_common).game_id
        from ..legendary_shadow_rom import field_model
        field = field_model(original_dol, game_id, read_archive, species, deoxys_form,
                            shiny=bool(shiny), scale=scale)
        if field is None:
            field = load_actor_model(original_dol, game_id, species,
                                 read_archive, scale=scale, shiny=bool(shiny),
                                 unown_form_index=unown_form(seed), deoxys_form=deoxys_form if species == 410 else 0)
        idle, source_hash = None, None
    # Nascour was already appended using this verified room-local donor entry.
    output = append_actor_models(source, {}, source, 0x03240400,
                                 {RESOURCE: ("darklugia_shrine", field)})
    return output, {"actor": ACTOR, "model": MODEL, "resource": RESOURCE,
                    "scale": scale, "position": POSITION, "shiny": shiny, "species": species,
                    "source_model_sha256": source_hash,
                    "field_sha256": sha256(field), "idle_motion": idle,
                    "native_pikachu_resource_preserved": True}
