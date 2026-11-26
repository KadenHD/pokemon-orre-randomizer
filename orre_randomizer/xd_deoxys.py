"""Collect XD form choices without changing a Pokémon's personality."""
from __future__ import annotations

from .deoxys import DEOXYS, encounter_forms, form_seed
from .engine.analyze_game import FormatError
from .engine.inspect_tables import u16
from .xd_battle_rules import DPKM_STRIDE, _deck_teams


def token(seed, key, original_species):
    value = form_seed(seed, 'xd:' + key)
    # Keeping a native specimen also keeps its native Normal Forme.
    return ((value & 0x3FFFFFFF) or 1) if original_species == DEOXYS else value


def deck_tokens(original, current, shadow_slots, seed, resource, deck_name):
    start, _, ordinary = _deck_teams(current, shadow_slots)
    native_start = _deck_teams(original, shadow_slots)[0]
    trainers, shadows, encounters = {}, {}, {}
    for index in sorted(ordinary):
        if u16(current, start + DPKM_STRIDE * index) != DEOXYS:
            continue
        original_species = u16(original, native_start + DPKM_STRIDE * index)
        # Localized deck resources differ; the logical encounter is shared.
        value = token(seed, f'{deck_name}:trainer:{index}', original_species)
        trainers[index] = value
        encounters[f'trainer:{resource}:{index}'] = value >> 30
    for sid, index in shadow_slots.items():
        if u16(current, start + DPKM_STRIDE * index) == DEOXYS:
            shadows[sid] = token(seed, f'shadow:{sid}', u16(original, native_start + DPKM_STRIDE * index))
    return trainers, shadows, encounters


def reward_tokens(summary, seed):
    rewards, spots = {}, {}
    starter = summary.get('starter')
    if starter and starter['species'] == DEOXYS:
        rewards['starter'] = token(seed, 'starter', starter['original'])
    for row in summary.get('gifts', ()):
        if row['species'] == DEOXYS:
            rewards[row['key']] = token(seed, row['key'], row['original'])
    for row in summary.get('poke_spots', ()):
        if row['species'] == DEOXYS:
            key = (row['spot'], row['slot'])
            spots[key] = token(seed, f'pokespot:{key[0]}:{key[1]}', row['original'])
    return rewards, spots


def encounter_metadata(rewards, shadows, decks, poke_spots):
    result = {**encounter_forms({'special:' + key: value for key, value in rewards.items()}),
              **encounter_forms({f'shadow:{sid}': value for sid, value in shadows.items()}),
              **encounter_forms({f'trainer:{resource}:{slot}': value
                                for resource, rows in decks.items() for slot, value in rows.items()}),
              **encounter_forms({f'pokespot:{spot}:{slot}': value
                                for (spot, slot), value in poke_spots.items()})}
    return result


def merge_shadows(target, new):
    for sid, value in new.items():
        if sid in target and target[sid] != value:
            raise FormatError('Localized XD decks disagree on a Deoxys form')
        target[sid] = value


def annotate_summary(summary):
    from .deoxys_presentation import annotate_catalog, decorate_encounter
    metadata = summary.get('deoxys_forms', {})
    starter = summary.get('starter')
    rows = [*summary.get('gifts', ()), *summary.get('poke_spots', ())]
    if starter:
        # Avoid adding a key to every legacy non-Deoxys starter report.
        if starter['species'] == DEOXYS:
            starter.setdefault('key', 'starter')
        rows.append(starter)
    for deck in summary.get('decks', {}).values():
        rows.extend(deck.get('shadows', ()))
    for row in rows:
        decorate_encounter(row, metadata, artwork=False)
    if catalog := summary.get('detail_catalog'):
        annotate_catalog(catalog, metadata)
