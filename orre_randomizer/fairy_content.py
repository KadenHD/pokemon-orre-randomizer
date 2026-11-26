"""Prepare configured Fairy content inside each generation/preview worker."""
from __future__ import annotations

from functools import wraps
import inspect

from .engine.analyze_game import FormatError
from .fairy_gameplay import content_from_rows, current_context, fairy_gameplay_context
from .fairy_messages import (
    ITEM_MESSAGE_IDS, MOVE_DESCRIPTION_IDS, MOVE_NAME_IDS, CONTEST_DESCRIPTION_ID, install_fairy_messages,
)
from .fairy_tms import prepare_candidate_moves, install_additional_tms


def prepare_content(original_rel, original_dol, game_id):
    """Use the approved retail animation donors; effects are installed separately."""
    pairs = {move: (identifier, MOVE_DESCRIPTION_IDS[move]) for move, identifier in MOVE_NAME_IDS.items()}
    prepared = prepare_candidate_moves(original_rel, game_id, move_message_ids=pairs)
    return content_from_rows(game_id, prepared['move_rows'],
                             original_rel=original_rel, original_dol=original_dol)


def scoped_content(function):
    """Do not prepare anything on the disabled path or on the Qt thread.

    Both production and known-only readers receive an ISO view after the
    existing source identity/conversion checks. Original executable and REL
    fingerprints are authenticated again by the bounded content constructors.
    """
    signature = inspect.signature(function)

    @wraps(function)
    def run(iso, boot, seed, options, *args, **kwargs):
        enabled = getattr(options, 'enable_fairy_type', False)
        if type(enabled) is not bool:
            raise ValueError('enable_fairy_type must be a boolean')
        if not enabled:
            with fairy_gameplay_context(None):
                return function(iso, boot, seed, options, *args, **kwargs)
        game_id = boot[:6].decode('ascii')
        active = current_context()
        if active is not None:
            if active.game_id != game_id:
                raise FormatError('Fairy worker context does not match the requested game')
            return function(iso, boot, seed, options, *args, **kwargs)
        from .known_encounters import _read
        if game_id.startswith('GXX'):
            from .xd import region_for_boot
        else:
            from .engine.regions import region_for_boot
        arguments = signature.bind(iso, boot, seed, options, *args, **kwargs)
        cancel = arguments.arguments['cancel']
        rel, dol, _, _ = _read(iso, boot, region_for_boot(boot), cancel)
        content = prepare_content(rel, dol, game_id)
        with fairy_gameplay_context(content):
            return function(iso, boot, seed, options, *args, **kwargs)
    return run


def install_content(current_rel, current_dol, tm_report, *, preview=False):
    """Install one complete TM plan and validate details against real row bytes."""
    content = current_context()
    if content is None:
        return current_rel, current_dol, None
    from .fairy_badges import LARGE_RESOURCES, SMALL_RESOURCES
    from .fairy_data import NEW_MOVE_IDS, move_definition
    from .fairy_runtime import install_fairy_type, install_move_category_callers
    original = content.original_dol
    dol, _, type_report = install_fairy_type(original, current_dol, content.game_id,
        badge_resources=LARGE_RESOURCES,
        small_badge_resources=SMALL_RESOURCES if content.family == 'xd' else None)
    categories = {375 + index: {'status': 0, 'physical': 1, 'special': 2}[
        move_definition(canonical)['damage_class']] for index, canonical in enumerate(NEW_MOVE_IDS)}
    dol, category_report = install_move_category_callers(original, dol, content.game_id, categories)
    dol, messages = install_fairy_messages(original, dol, content.game_id)
    dol, updated_rel, tms = install_additional_tms(original, dol, content.game_id,
        original_rel=content.original_rel, current_rel=current_rel,
        move_rows=content.move_rows, compatibility=tm_report['extra_compatibility'],
        item_message_ids=ITEM_MESSAGE_IDS, tm_plan=tm_report['tm_plan'],
        contest_description_id=CONTEST_DESCRIPTION_ID,
        message_refresh_address=messages['refresh_address'])
    if updated_rel is not None:
        current_rel = updated_rel
    from .fairy_evolution import install_evolution_learning
    dol, evolution = install_evolution_learning(original, dol, content.game_id, additional_tms_report=tms)
    effects = None
    transfer = None
    if not preview:
        from .fairy_move_effects import install_fairy_move_effects
        from .fairy_transfer import install_fairy_transfer
        dol, effects = install_fairy_move_effects(original, dol, content.game_id)
        dol, transfer = install_fairy_transfer(original, dol, content.game_id,
            message_refresh_address=messages['refresh_address'], refusal_message_id=messages['transfer_refusal_id'])
    report = content.summary()
    report.update(enabled=True, types=type_report, categories=category_report,
                  messages=messages, additional_tms=tms, move_effects=effects,
                  evolution_learning=evolution, gba_transfer=transfer, preview_data_only=preview)
    return current_rel, dol, report


def append_badge_archives(common, read_archive):
    """Install all offline locale resources without replacing a retail badge."""
    content = current_context()
    if content is None:
        return common, {}, []
    from .fairy_badges import LANGUAGES, append_badges
    reports = []
    for language in LANGUAGES:
        common, report = append_badges(common, content.family, language)
        reports.append(dict(archive='common.fsys', **report))
    locales = (('', 'en'), ('_ge', 'de'), ('_fr', 'fr'), ('_it', 'it'), ('_sp', 'es'))
    if content.game_id.endswith('J01'):
        locales = (('', 'ja'),)
    elif content.game_id.endswith('E01'):
        locales = (('', 'en'),)
    updates = {}
    for suffix, language in locales:
        name = 'fight_common' + suffix + '.fsys'
        updates[name], report = append_badges(read_archive(name), content.family, language)
        reports.append(dict(archive=name, **report))
    return common, updates, reports
