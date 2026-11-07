"""Standalone, script-free HTML journals with optional spoiler sections.

This is a presentation of the verified final-byte report. It performs no ROM
reads, random draws, web requests or writes unless save_journal is called.
"""
from __future__ import annotations

from dataclasses import fields
from html import escape
from pathlib import Path

from .detail_texts import LANGUAGES, detail_text
from .pokemon_details import STAT_NAMES, display_name, encounter_details


def _e(value) -> str:
    return escape(str(value), quote=True)


def _section(title: str, body: str) -> str:
    return '<details><summary>' + _e(title) + '</summary><div class="section">' + body + '</div></details>'


def _table(headers, rows) -> str:
    return '<div class="table-wrap"><table><thead><tr>' + ''.join('<th scope="col">' + _e(h) + '</th>' for h in headers) + '</tr></thead><tbody>' + ''.join(
        '<tr>' + ''.join('<td>' + _e(cell) + '</td>' for cell in row) + '</tr>' for row in rows) + '</tbody></table></div>'


def _sheet(details: dict, language: str) -> str:
    tr = lambda key, **params: detail_text(key, language, **params)
    title = display_name(details, language)
    if details.get('level') is not None:
        title += ' · ' + tr('level', level=details['level'])
    body = '<h3>' + _e(title) + '</h3>'
    body += '<p>' + _e(tr('types')) + ': ' + _e(' / '.join(details['type_names'][language])) + '<br>'
    body += _e(tr('abilities')) + ': ' + _e(' / '.join(details['ability_names'][language])) + '</p>'
    body += '<p class="note">' + _e(tr('ability_note')) + '</p>'
    if details.get('moves_known'):
        body += '<p>' + _e(tr('moves')) + ': ' + _e(', '.join(display_name(row, language) for row in details['moves']) or tr('none')) + '</p>'
    body += _section(tr('stats'), _table([tr(name) for name in STAT_NAMES],
        [[details['base_stats'][name] for name in STAT_NAMES]]))
    evolutions = '<p>' + _e(tr('shadow_first')) + '</p>' if details.get('shadow') else ''
    if details['evolutions']:
        evolutions += _table([tr('evolutions'), tr('on_this_rom')],
            [[row['source_names'][language] + ' → ' + display_name(row, language), row['texts'][language]]
             for row in details['evolution_chain']])
    else:
        evolutions += '<p>' + _e(tr('no_evolution')) + '</p>'
    body += _section(tr('evolutions'), evolutions)
    body += _section(tr('learnset'), _table([tr('level', level=''), tr('moves')],
        [[row['level'], display_name(row['details'], language)] for row in details['learnset']]))
    body += _section(tr('tms'), _table([tr('tms'), tr('moves')],
        [[f"{row['tm']:02d}", display_name(row['details'], language)] for row in details['tms']]))
    return '<article>' + body + '</article>'


def _shiny(row: dict, report: dict, key: str | None = None, sid=None) -> bool | None:
    options = report.get('options', {})
    if not options.get('custom_shinies'):
        return None
    chance = options.get('shiny_chance_percent')
    if chance == 0:
        return False
    if chance == 100:
        return True
    if options.get('seeded_shinies'):
        decisions = report.get('summary', {}).get('shinies', {}).get('seeded_decisions', {})
        result = decisions.get('specials', {}).get(key) if key else decisions.get('shadows', {}).get(str(sid))
        if type(result) is bool:
            return result
    return None


def _options(report: dict, language: str) -> str:
    # Delay imports so the journal reader can also inspect legacy or minimal
    # reports without instantiating options or changing application state.
    from .i18n import translate
    from .options import Options
    from .locales.selection_names import SPECIES_NAMES, TYPE_NAMES
    metadata = {item.name: item.metadata for item in fields(Options)}
    if report.get('game') == 'xd':
        from .xd import XDOptions
        metadata = {item.name: item.metadata for item in fields(XDOptions)}
    rows = []
    for key, value in report.get('options', {}).items():
        meta = metadata.get(key, {})
        label = translate(meta.get('label', key), language)
        if type(value) is bool:
            shown = detail_text('enabled' if value else 'disabled', language)
        elif meta.get('selector') == 'species':
            shown = SPECIES_NAMES[language].get(value, detail_text('seeded_choice', language))
        elif meta.get('kind') == 'choice':
            shown = next((translate(label, language) for identifier, label in meta.get('choices', ())
                          if identifier == value), str(value))
        elif isinstance(value, (list, tuple)):
            lookup = (SPECIES_NAMES[language] if meta.get('kind') == 'species_set'
                      else TYPE_NAMES[language] if meta.get('kind') == 'type_set' else {})
            shown = ', '.join(lookup.get(item, str(item)) for item in value) or detail_text('none', language)
        else:
            shown = str(value)
        rows.append((label, shown))
    return _table([detail_text('options', language), detail_text('on_this_rom', language)], rows)


def _xd_spoilers(summary: dict, language: str) -> str:
    from .i18n import translate
    from .locales.selection_names import SPECIES_NAMES

    tr = lambda key, **params: detail_text(key, language, **params)
    national_ids = summary.get('national_ids', {})

    def name(index):
        return SPECIES_NAMES[language].get(national_ids.get(str(index)), str(index))

    starter = summary.get('starter')
    if not starter:
        return ''
    body = _section(tr('starters'), _table([tr('details'), tr('level', level='')],
                    [[name(starter['species']), starter['level']]]))
    shadows = summary.get('decks', {}).get('Story', {}).get('shadows', ())
    if shadows:
        body += _section(tr('shadows') + f" · {len(shadows)}",
                         _table(['#', tr('details'), tr('level', level='')],
                                [[row['shadow_id'], name(row['species']), row['level']] for row in shadows]))
    spots = summary.get('poke_spots', ())
    if spots:
        labels = {'rock': 'Roche', 'oasis': 'Oasis', 'cave': 'Grotte'}
        wild_shinies = summary.get('poke_spot_shinies', {})
        note = ''
        if wild_shinies.get('enabled'):
            text = translate('Chromatiques sauvages : {rate} % par nouvelle rencontre.', language)
            note = '<p>' + _e(text.format(rate=format(wild_shinies['chance_percent'], 'g'))) + '</p>'
        body += _section(translate('Poké Places ({count})', language).format(count=len(spots)),
                         note + _table(['#', tr('details'), tr('level', level=''), '%'],
                                [[translate(labels.get(row['spot'], row['spot']), language) + f" · {row['slot']}",
                                  name(row['species']) + (' ★' if row.get('shiny') else ''),
                                  '–'.join(map(str, row['levels'])), row['chance']]
                                 for row in spots]))
    gifts = summary.get('gifts', ())
    if gifts:
        def gift_label(row):
            label = name(row['species'])
            if row.get('required_species') is None:
                return label
            pokemon = name(row['required_species'])
            if row.get('required_evolution') is not None:
                trade = translate('Échange contre {pokemon} ou {evolution}', language).format(
                    pokemon=pokemon, evolution=name(row['required_evolution']))
            else:
                trade = translate('Échange contre {pokemon}', language).format(pokemon=pokemon)
            return f'{label} · {trade}'

        body += _section(tr('gifts') + f" · {len(gifts)}",
                         _table([tr('details'), tr('level', level='')],
                                [[gift_label(row), row['level']] for row in gifts]))
    return body


def render_journal(report: dict, language: str = 'fr') -> str:
    """Render a private report without exposing paths or active HTML content."""
    if language not in LANGUAGES:
        raise ValueError('unsupported journal language')
    if not isinstance(report, dict):
        raise TypeError('journal report must be a dictionary')
    tr = lambda key, **params: detail_text(key, language, **params)
    summary = report.get('summary', {})
    catalog = summary.get('detail_catalog') or report.get('detail_catalog')
    metadata = [(tr('seed'), report.get('seed', '')),
                (tr('version'), ' / '.join(str(report.get(key, '')) for key in ('application_version', 'engine_version'))),
                (tr('rom'), report.get('game_id', ''))]
    for key in ('source_iso_sha256', 'output_iso_sha256'):
        if report.get(key):
            metadata.append((tr('hash') + ' · ' + ('ISO' if key.startswith('output') else tr('rom')), report[key]))
    body = '<header><h1>' + _e(tr('journal')) + '</h1><p>' + _e(tr('new_game')) + '</p></header>'
    body += _table([tr('journal'), tr('on_this_rom')], metadata)
    body += '<p class="note">' + _e(tr('spoilers')) + '</p>'
    body += _section(tr('options'), _options(report, language))
    if report.get('game') == 'xd':
        return _journal_page('Pokémon XD · ' + tr('journal'), language, body + _xd_spoilers(summary, language))
    final_specials = {row['key']: row for row in summary.get('special_gameplay', {}).get('specials', [])}

    def special_group(keys):
        chunks = []
        for key in keys:
            row = final_specials.get(key) or (catalog or {}).get('specials', {}).get(key)
            if not row:
                continue
            status = _shiny(row, report, key=key)
            if catalog:
                native = catalog.get('specials', {}).get(key, row)
                sheet = encounter_details(catalog, row['species'], level=row.get('level'), moves=native.get('moves'))
                chunks.append(_sheet(sheet, language))
            else:
                chunks.append('<h3>' + _e(display_name(row, language)) + '</h3>')
            chunks.append('<p>' + _e(tr('unknown_shiny' if status is None else 'shiny' if status else 'ordinary')) + '</p>')
            if key in ('pikachu-event', 'celebi-event'):
                options = report.get('options', {})
                if options.get('accessible_event_gifts'):
                    count = options.get('event_pikachu_purifications' if key == 'pikachu-event' else 'event_celebi_purifications')
                    chunks.append('<p>' + _e(tr('adelbert') + ' · ' + tr('purifications', count=count)) + '</p>')
                else:
                    chunks.append('<p>' + _e(tr('event')) + '</p>')
        return ''.join(chunks) or '<p>' + _e(tr('none')) + '</p>'

    body += _section(tr('starters'), special_group(('umbreon', 'espeon')))
    shadow_parts = []
    for row in summary.get('final_shadow_picks', []):
        sid, index = row['shadow_id'], row['species_index']
        title = f"{sid:02d} · " + display_name(row, language)
        if catalog:
            encounter = catalog.get('shadows', {}).get(str(sid), {})
            content = _sheet(encounter_details(catalog, index, level=encounter.get('level'),
                moves=encounter.get('moves'), shadow=True), language)
        else:
            content = '<p>' + _e(display_name(row, language)) + '</p>'
        status = _shiny(row, report, sid=sid)
        content += '<p>' + _e(tr('unknown_shiny' if status is None else 'shiny' if status else 'ordinary')) + '</p>'
        shadow_parts.append(_section(title, content))
    body += _section(tr('shadows') + f" · {len(shadow_parts)}", ''.join(shadow_parts))
    body += _section(tr('gifts'), special_group(('plusle', 'ho-oh', 'pikachu-event', 'celebi-event')))
    if catalog:
        trainer_parts = []
        for trainer in catalog.get('trainers', []):
            rows = []
            for row in trainer['team']:
                details = catalog['species'][str(row['species'])]
                moves = ', '.join(display_name(catalog['moves'].get(str(move), {
                    'names': {language: tr('move_marker', id=move)}}), language) for move in row['moves'] if move)
                rows.append([display_name(details, language), row['level'],
                    tr('shadows') + f" {row['shadow_id']}" if row['shadow_id'] else '', moves])
            title = display_name(trainer, language) + f" · #{trainer['trainer_id']}"
            trainer_parts.append(_section(title, _table([tr('details'), tr('level', level=''), tr('shadows'), tr('moves')], rows)))
        body += _section(tr('trainers') + f" · {len(trainer_parts)}", ''.join(trainer_parts))
        evolution_rows = [[display_name(species, language), display_name(branch, language), branch['texts'][language]]
            for species in catalog['species'].values() for branch in species['evolutions']]
        body += _section(tr('evolutions'), _table([tr('details'), tr('evolutions'), tr('on_this_rom')], evolution_rows))
        body += _section(tr('tms'), _table([tr('tms'), tr('moves')], [[f"{row['tm']:02d}",
            display_name(catalog['moves'][str(row['move'])], language)] for row in catalog['tms']]))
    return _journal_page(tr('journal'), language, body)


def _journal_page(title: str, language: str, body: str) -> str:
    css = '''
    :root{color-scheme:light dark;font:16px/1.55 system-ui,sans-serif;color:#edf5f2;background:#101e22}
    body{max-width:76rem;margin:0 auto;padding:1.5rem}header{border-bottom:3px solid #71e2e6;margin-bottom:1.5rem}
    h1{line-height:1.15;font-size:2rem}h3{font-size:1.1rem}p,td,th,summary{overflow-wrap:anywhere}
    details{margin:.8rem 0;border:1px solid #829e98;border-radius:4px}summary{cursor:pointer;padding:.8rem 1rem;font-weight:650}
    summary:hover,summary:focus-visible{background:#125359}summary:focus-visible{outline:3px solid #71e2e6;outline-offset:2px}
    .section{padding:0 1rem 1rem}.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}
    td,th{text-align:start;vertical-align:top;padding:.6rem;border-bottom:1px solid #45615d}th{color:#bfe8dc}
    .note{color:#bfd5cd}article+article{margin-top:2rem;border-top:1px solid #45615d}article details{margin:.5rem 0}
    @media print{ :root{color:#111;background:white}body{padding:0}th,.note{color:#333}details{break-inside:avoid} }
    '''
    return ('<!doctype html><html lang="' + language + '"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">'
        '<title>' + _e(title) + '</title><style>' + css + '</style></head><body>' + body + '</body></html>')


def save_journal(path: Path, report: dict, language: str = 'fr') -> None:
    """Publish an explicit new HTML file; never overwrite an existing file."""
    path = Path(path)
    if path.suffix.lower() not in ('.html', '.htm'):
        raise ValueError('journal destination must be an HTML file')
    content = render_journal(report, language).encode('utf8')
    with path.open('xb') as stream:
        stream.write(content)
