"""Search and effective configuration summaries without ROM reads or RNG."""
from dataclasses import fields
from functools import lru_cache
import re
import unicodedata

from .detail_texts import detail_text
from .i18n import LANGUAGES, translate
from .locales.selection_names import SPECIES_NAMES
from .options import Options

_FIELDS = {item.name: item for item in fields(Options)}
_SHINY_WORDS = ("chromatiques", "chromatique", "shinies", "shiny", "schillernde", "schillernd",
                "variocolor", "cromatici", "cromatico", "色違い", "いろちがい")


def search_text(value):
    value = ''.join(character for character in unicodedata.normalize('NFKD', str(value)).casefold()
                    if not unicodedata.combining(character))
    for alias in _SHINY_WORDS:
        value = value.replace(alias, 'shiny')
    return ' '.join(re.sub(r'[^\w]+', ' ', value.replace('_', ' '), flags=re.UNICODE).split())


@lru_cache(maxsize=6)
def _search_rows(language):
    rows = []
    for ordinal, item in enumerate(fields(Options)):
        meta = item.metadata
        translated = {key: translate(meta[key], language) for key in ('label', 'group', 'description')}
        all_text = []
        for code in LANGUAGES:
            all_text.extend(translate(meta[key], code) for key in ('label', 'group', 'description'))
            all_text.extend(translate(label, code) for _, label in meta.get('choices', ()))
        rows.append(dict(name=item.name, ordinal=ordinal, **translated,
                         indexed=search_text(' '.join(all_text)), title=search_text(translated['label'])))
    return rows


def search_settings(query, language='fr'):
    tokens = search_text(query).split()
    if not tokens:
        return []
    matches = [row for row in _search_rows(language) if all(token in row['indexed'] for token in tokens)]
    matches.sort(key=lambda row: (not all(token in row['title'] for token in tokens), row['ordinal']))
    return [{key: row[key] for key in ('name', 'label', 'group', 'description')} for row in matches]


def effective_setting_names(options):
    """Select controls which the engine actually consults in this configuration."""
    actions = ('randomize_trainers','randomize_shadows','trainer_force_evolved',
        'starter_umbreon','starter_espeon','gift_plusle','gift_hooh','event_pikachu','event_celebi','diverse_story_families',
        'accessible_event_gifts','evolve_trade','evolve_trade_items','evolve_coquiperl',
        'evolve_day_night','evolve_beauty','stones_phenac','stones_pyrite','readable_stone_names',
        'randomize_trainer_moves','randomize_starter_moves','randomize_gift_moves','randomize_learnsets',
        'randomize_abilities','randomize_stats','randomize_types','randomize_held_items',
        'randomize_tm_moves','randomize_field_items','randomize_shop_items','boss_stronger',
        'boss_team_variety','custom_shinies')
    selected = {name for name in actions if getattr(options,name)}
    def add(names, condition=True):
        if condition:
            selected.update(names)
    add(('unique_shadows','boss_shadow_legendary_mode','boss_shadow_power_mode','boss_shadow_min_bst'), options.randomize_shadows)
    add(('trainer_theme_mode',), options.randomize_trainers)
    add(('trainer_evolution_level',), options.trainer_force_evolved)
    starters = options.starter_umbreon or options.starter_espeon
    add(('starter_balance_pair','starter_distinct_families','starter_complementary_types'), starters)
    random_starter = False
    for key in ('umbreon','espeon'):
        if getattr(options,'starter_'+key):
            add(('starter_'+key+'_species',))
            random_starter |= not getattr(options,'starter_'+key+'_species')
    add(('starter_stage','starter_three_stage_families'), random_starter)
    add(('event_pikachu_purifications','event_celebi_purifications','event_pikachu_level','event_celebi_level'), options.accessible_event_gifts)
    species_changes = any(getattr(options,name) for name in ('randomize_trainers','randomize_shadows',
        'starter_umbreon','starter_espeon','gift_plusle','gift_hooh','event_pikachu','event_celebi','boss_team_variety','trainer_force_evolved'))
    add(('allow_gen1','allow_gen2','allow_gen3','allow_legendaries','excluded_species','excluded_types'), species_changes)
    add(('balance_species',), random_starter or any(getattr(options,name) for name in
        ('randomize_trainers','randomize_shadows','gift_plusle','gift_hooh','event_pikachu','event_celebi','boss_team_variety','trainer_force_evolved')))
    add(('ensure_damaging_move','ensure_stab_move','no_duplicate_moves','ban_self_destruct','ban_ohko','moves_mode'),
        any(getattr(options,name) for name in ('randomize_trainer_moves','randomize_starter_moves','randomize_gift_moves','randomize_learnsets')))
    add(('abilities_family_consistent',), options.randomize_abilities)
    add(('preserve_stat_totals',), options.randomize_stats)
    add(('types_family_consistent',), options.randomize_types)
    add(('useful_held_items_only',), options.randomize_held_items)
    add(('items_similar_value','keep_capture_items'), options.randomize_field_items or options.randomize_shop_items)
    add(('shop_keep_healing',), options.randomize_shop_items)
    add(('tm_compatibility_mode',), options.randomize_tm_moves or options.tm_compatibility_mode!='original')
    add(('tm_ensure_offensive',), options.tm_compatibility_mode!='original')
    add(('shiny_chance_percent',), options.custom_shinies)
    add(('seeded_shinies',), options.custom_shinies and 0<options.shiny_chance_percent<100)
    add(('progressive_levels','early_level_multiplier','mid_level_multiplier','late_level_multiplier'), options.progressive_levels)
    add(('trainer_level_multiplier',), not options.progressive_levels and options.trainer_level_multiplier!=1)
    for name, neutral in (('experience_multiplier',1),('purification_multiplier',1),('capture_rate_multiplier',1),('minimum_catch_rate',0)):
        add((name,), getattr(options,name)!=neutral)
    return [name for name in _FIELDS if name in selected]


def _value(name, options, language):
    value, meta = getattr(options,name), _FIELDS[name].metadata
    if meta.get('selector')=='species':
        if value<0:
            return translate('Choisissez un Pokémon de la liste pour {label}.',language).format(label=translate(meta['label'],language))
        return SPECIES_NAMES[language].get(value, translate('Tirage avec la seed',language))
    if type(value) is bool:
        return detail_text('enabled' if value else 'disabled',language)
    if meta['kind']=='choice':
        return next((translate(label,language) for identifier,label in meta['choices'] if identifier==value),str(value))
    if meta['kind']=='species_set':
        return translate('{count} espèces exclues',language).format(count=len(value))
    if meta['kind']=='type_set':
        return translate('{count} types d’origine exclus',language).format(count=len(value))
    return format(value,'g') if isinstance(value,(float,int)) else str(value)


def configuration_review(options, language="fr"):
    if not options.has_changes:
        return translate("Copie à l’identique : aucune donnée du jeu ne sera modifiée.", language)
    groups = {}
    for name in effective_setting_names(options):
        metadata = _FIELDS[name].metadata
        label = translate(metadata["label"], language)
        value = _value(name, options, language)
        if name == "shiny_chance_percent":
            value += " %"
        elif name.endswith("_multiplier"):
            value = "×" + value
        groups.setdefault(metadata["group"], []).append(f"• {label} : {value}")
    if not options.custom_shinies:
        groups.setdefault("Chromatiques", []).append(translate("Chromatiques : règles du jeu d’origine.", language))
    return "\n\n".join(translate(group, language) + "\n" + "\n".join(rows)
                       for group, rows in groups.items())
