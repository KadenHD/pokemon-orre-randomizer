"""Private six-language messages for added moves and real TM51-TM57 items."""
from __future__ import annotations

import hashlib
import json
import struct
from functools import lru_cache
from pathlib import Path

from .castform_portraits import _reservation
from .deoxys_meteorite import LANGUAGES, _LANG_TAGS, _QUALIFIED, _bank_refresh, _read, _offset
from .engine.analyze_game import FormatError, parse_dol
from .engine.gift_move_hooks import _arena_guard, branch
from .fairy_data import NEW_MOVE_IDS, move_name
from .fairy_message_layout import encode_native_description, native_description

VERSION = 'fairy-move-and-tm-messages-v2'
MOVE_NAME_IDS = {375 + index: 0xF0440 + 2 * index for index in range(7)}
MOVE_DESCRIPTION_IDS = {move: identifier + 1 for move, identifier in MOVE_NAME_IDS.items()}
ITEM_NAME_IDS = {278 + index: 0xF0400 + index for index in range(7)}
ITEM_DESCRIPTION_IDS = {278 + index: 0xF0410 + index for index in range(7)}
ITEM_DESCRIPTION_IDS_BY_MOVE = {375 + index: 0xF0410 + index for index in range(7)}
ITEM_MESSAGE_IDS = {item: (ITEM_NAME_IDS[item], ITEM_DESCRIPTION_IDS[item]) for item in ITEM_NAME_IDS}
CONTEST_DESCRIPTION_ID = 0xF0470
TRANSFER_REFUSAL_ID = 0xF0480
TRANSFER_MESSAGES_SHA256 = '97a27dfac1c8216fbdb413275606a6949cba699083c2f8536e312d5cbf858536'
_PREFIXES = {'en': 'TM', 'fr': 'CT', 'de': 'TM', 'it': 'MT', 'es': 'MT', 'ja': 'わざマシン'}
_NO_CONTEST = {'en': 'No Contest effect.', 'fr': 'Aucun effet de concours.',
               'de': 'Kein Wettbewerbseffekt.', 'es': 'Sin efecto de concurso.',
               'it': 'Nessun effetto nei concorsi.', 'ja': 'コンテストは ひたいおう。'}
# These are native layout-node widths, not estimates from rendered screenshots.
# GSmsgPrintColor receives no width in the Bag. Its separate prose must use the
# Bag node, rather than the wider move-summary node. Heights affect alignment;
# they are not pixel-clipping bounds. Keep the native two/three-line convention.
_DESCRIPTION_LAYOUTS = {
    'GC6': {'move': (351, 2), 'item': (216, 3)},
    'GXX': {'move': (322, 2), 'item': (228, 3)},
}


def description_font(game_id, language):
    """Match the original regional description banks, including Japanese XD."""
    if game_id not in _QUALIFIED or language not in LANGUAGES:
        raise ValueError('Unsupported native Fairy description game or language')
    # Japanese Colosseum also uses font1: its original Tackle10533 and
    # TM01/10195 banks store 0001 at +6. Reading byte3 incorrectly yields0.
    return 0 if language == 'ja' and game_id in ('GC6P01', 'GC6E01') else 1


def message_texts(language):
    if language not in LANGUAGES:
        raise ValueError('Unsupported Fairy message language')
    texts = {}
    for index, canonical in enumerate(NEW_MOVE_IDS):
        move, item = 375 + index, 278 + index
        texts[MOVE_NAME_IDS[move]] = move_name(canonical, language, uppercase=True)
        texts[MOVE_DESCRIPTION_IDS[move]] = native_description(canonical, language)
        texts[ITEM_NAME_IDS[item]] = f'{_PREFIXES[language]}{51 + index:02d}'
        texts[ITEM_DESCRIPTION_IDS[item]] = native_description(canonical, language)
    texts[CONTEST_DESCRIPTION_ID] = _NO_CONTEST[language]
    if len(texts) != 29 or any(not text or any(ord(char) < 32 or char == '\uffff' for char in text)
                               for text in texts.values()):
        raise FormatError('Invalid Fairy message text')
    return texts


@lru_cache(maxsize=1)
def _transfer_messages():
    path = Path(__file__).resolve().parent / 'assets/rules/fairy/transfer-messages.json'
    if path.is_symlink():
        raise FormatError('Changed native transfer refusal messages')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != TRANSFER_MESSAGES_SHA256:
        raise FormatError('Changed native transfer refusal messages')
    data = json.loads(raw.decode('utf-8'))
    if data.get('schema') != 1 or data.get('source_message_id') != 0xC4AB or set(data.get('messages', {})) != set(LANGUAGES):
        raise FormatError('Invalid native transfer refusal message set')
    result = {}
    for language, row in data['messages'].items():
        body = bytes.fromhex(row['body_hex'])
        if (hashlib.sha256(body).hexdigest() != row['body_sha256'] or not body.endswith(b'\xff\xff\x02\0\0')
                or b'\xff\xff\x59' in body or b'\xff\xff\x5b' in body):
            raise FormatError('Invalid native transfer refusal body')
        result[language] = body
    return result


def message_bank(language, *, original_dol, game_id):
    """Wrap the authored menu prose using this original executable's glyphs.

    Full reference descriptions stay in the desktop app. Native line controls
    are encoded only here, after measuring the real font and the specific pane.
    """
    font_id = description_font(game_id, language)
    texts = {identifier: text.encode('utf-16-be') + b'\0\0' for identifier, text in message_texts(language).items()}
    for index, canonical in enumerate(NEW_MOVE_IDS):
        for role, identifier in (('move', MOVE_DESCRIPTION_IDS[375 + index]),
                                  ('item', ITEM_DESCRIPTION_IDS[278 + index])):
            width, max_lines = _DESCRIPTION_LAYOUTS[game_id[:3]][role]
            texts[identifier] = encode_native_description(canonical, language,
                original_dol=original_dol, game_id=game_id, width=width,
                font_id=font_id, max_lines=max_lines) + b'\0\0'
    texts[TRANSFER_REFUSAL_ID] = _transfer_messages()[language]
    if game_id == 'GC6J01':
        # The original Japanese renderer reads fontId as u16 at bank+6
        # (GSmsgPrintRect 0x800F94C4, lhz at 0x800F9620), not the Western
        # byte at +3. A Western language tag here selects a nonexistent font;
        # direct GSchar names still work, hiding the malformed header.
        header = struct.pack('>HHHHII', 0, 0, len(texts), font_id, 0, 0)
    else:
        header = struct.pack('>HBBH2sII', 0, 0, font_id, len(texts), _LANG_TAGS[language], 0, 0)
    out = bytearray(header)
    out.extend(bytes(8 * len(texts)))
    for index, (identifier, raw) in enumerate(sorted(texts.items())):
        struct.pack_into('>II', out, 16 + index * 8, identifier, len(out))
        out.extend(raw)
    out.extend(bytes(-len(out) % 32))
    return bytes(out)


def install_fairy_messages(original_dol, current_dol, game_id):
    """Supply a qualified refresh callback; the added item/move getters call it.

    Closing only our own six buffers before opening the selected buffer keeps
    repeated refreshes balanced. No retail name, dialogue or message is replaced.
    """
    qualified = _QUALIFIED.get(game_id)
    if qualified is None or hashlib.sha256(original_dol).hexdigest() != qualified[0]:
        raise FormatError('Unknown original Fairy message executable')
    functions = {}
    for role in ('bank_open', 'bank_close', 'language'):
        if role not in qualified[1]:
            continue
        address, size, digest = qualified[1][role]
        raw = _read(original_dol, address, size)
        if hashlib.sha256(raw).hexdigest() != digest or _read(current_dol, address, size) != raw:
            raise FormatError('Changed native Fairy message function: ' + role)
        functions[role] = address
    offset, ram, setter, store, arena = _reservation(original_dol, current_dol, game_id)
    banks = {}
    for language in LANGUAGES:
        arena.extend(bytes(-len(arena) % 32))
        banks[language] = ram + len(arena)
        arena.extend(message_bank(language, original_dol=original_dol, game_id=game_id))
    refresh = ram + len(arena)
    arena.extend(_bank_refresh(refresh, functions, banks, game_id))
    end = ram + len(arena)
    if end >= 0x81700000:
        raise FormatError('Fairy messages exceed the owned memory arena')
    arena[:32] = _arena_guard(end, store)
    output = bytearray(current_dol[:offset])
    output.extend(bytes(offset - len(output)))
    output.extend(arena)
    setter_pos = _offset(original_dol, setter)
    for position, value in ((8, offset), (0x50, ram), (0x98, len(arena)),
                            (setter_pos, branch(setter, ram))):
        struct.pack_into('>I', output, position, value)
    allowed = ((8, 12), (0x50, 0x54), (0x98, 0x9C),
               (setter_pos, setter_pos + 4), (offset, offset + 32))
    if any(before != after and not any(lo <= pos < hi for lo, hi in allowed)
           for pos, (before, after) in enumerate(zip(current_dol, output))):
        raise FormatError('Fairy messages changed an unrelated executable byte')
    section = next(s for s in parse_dol(output)['sections'] if s['name'] == 'text2')
    if (section['offset'], section['ram_address'], section['size']) != (offset, ram, len(arena)):
        raise FormatError('Invalid final Fairy message reservation')
    return bytes(output), {'version': VERSION, 'refresh_address': refresh, 'message_count': 30,
                    'banks': banks, 'move_name_ids': MOVE_NAME_IDS,
                    'move_description_ids': MOVE_DESCRIPTION_IDS, 'item_message_ids': ITEM_MESSAGE_IDS,
                    'contest_description_id': CONTEST_DESCRIPTION_ID,
                    'description_fonts': {language: description_font(game_id, language) for language in LANGUAGES},
                    'description_font_field': {'offset': 6, 'bytes': 2} if game_id == 'GC6J01' else {'offset': 3, 'bytes': 1},
                    'description_layouts': _DESCRIPTION_LAYOUTS[game_id[:3]],
                    'transfer_refusal_id': TRANSFER_REFUSAL_ID,
                    'original_message_banks_preserved': True}
