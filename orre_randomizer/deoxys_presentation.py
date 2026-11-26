"""Use the generation plan's Deoxys forms in previews, sheets and journals."""
from __future__ import annotations

from copy import deepcopy

from .deoxys import BASE_STATS, BASE_STAT_FIELDS, DEOXYS, FORM_ORDER


def form_stat_tables(seed, options, normal_stats):
    """Share native HP across forms, including when other base stats are shuffled."""
    normal = tuple(normal_stats)
    if len(normal) != 6 or any(type(n) is not int or not 1 <= n <= 255 for n in normal):
        raise ValueError('Invalid final Deoxys base stats')
    if not options.randomize_stats:
        return {**BASE_STATS, 'normal': normal}
    from .engine.species_rules import _redistribute
    result = {'normal': normal}
    for form in FORM_ORDER[1:]:
        # A form change must not add HP or heal through a different maximum.
        rest = _redistribute(seed, 'deoxys-form-stats:' + form, sum(normal) - normal[0] + 1, True)
        result[form] = (normal[0], *rest[1:])
    return result


def encounter_key(row):
    if row.get('shadow_id'):
        return f"shadow:{row['shadow_id']}"
    if row.get('spot') and type(row.get('slot')) is int:
        return f"pokespot:{row['spot']}:{row['slot']}"
    key = row.get('key')
    if isinstance(key, str):
        if key.startswith(('special:', 'trainer:', 'shadow:', 'pokespot:')):
            return key
        return 'special:' + key
    slot = row.get('slot_index', row.get('slot'))
    return f'trainer:{slot}' if type(slot) is int else None


def decorate_encounter(row, metadata, *, artwork=True):
    """Apply a known form only; no RNG, ROM read or extra preview computation."""
    if row.get('national_dex') != 386 and row.get('species') != DEOXYS:
        return
    key = encounter_key(row)
    form = row.get('deoxys_form', metadata.get('encounters', {}).get(key, 0))
    if type(form) is not int or not 0 <= form < 4:
        raise ValueError('Invalid Deoxys form in generation metadata')
    row['deoxys_form'] = form
    details = row.get('details')
    if details is not None:
        details['deoxys_form'] = form
        if form or 'base_stats' in metadata:
            stats = metadata.get('base_stats', BASE_STATS)[FORM_ORDER[form]]
            details['base_stats'] = dict(zip(BASE_STAT_FIELDS, stats, strict=True))
            details['base_stat_total'] = sum(stats)
    if artwork and form:
        from .deoxys_assets import artwork_png
        row['portrait_png'] = artwork_png(FORM_ORDER[form], shiny=bool(row.get('shiny')))


def annotate_catalog(catalog, metadata):
    """Persist the form plan alongside final species data without changing species IDs."""
    if not metadata:
        return
    catalog['deoxys_forms'] = deepcopy(metadata)
    for key, row in catalog.get('specials', {}).items():
        if row.get('species') == DEOXYS:
            row['deoxys_form'] = metadata.get('encounters', {}).get('special:' + key, 0)
    for key, row in catalog.get('shadows', {}).items():
        if row.get('species') == DEOXYS:
            row['deoxys_form'] = metadata.get('encounters', {}).get('shadow:' + key, 0)
            for variant in row.get('variants', []):
                variant['deoxys_form'] = row['deoxys_form']
    for trainer in catalog.get('trainers', []):
        for row in trainer.get('team', []):
            if row.get('species') == DEOXYS:
                row['deoxys_form'] = metadata.get('encounters', {}).get(encounter_key(row), 0)
