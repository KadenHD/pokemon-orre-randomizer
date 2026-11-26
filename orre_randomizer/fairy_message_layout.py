"""Compact native move prose, measured against caller-qualified GSmsg fonts.

The app keeps the full reference descriptions from ``fairy_data``. These
separate descriptions fit generation-III menus without changing move effects.
Rectangle width and font selection must be qualified at the native caller;
neither is inferred from an unrelated dialogue box or character count.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
import re

from .engine.analyze_game import FormatError
from .fairy_data import LANGUAGES, NEW_MOVE_IDS
from .hd_text import font_banks_from_dol

LINE_BREAK = b'\xff\xff\x00'
GAME_IDS = ('GC6P01', 'GC6E01', 'GC6J01', 'GXXP01', 'GXXE01', 'GXXJ01')

# Authored concise native-menu descriptions, not abbreviated UI/source data.
# PP, power and accuracy are separate native fields. Drain retains its exact
# three-quarter fraction; both spread attacks and priority are explicit.
_TEXTS = {
    'en': (
        'A cry that hits both foes without fail.',
        'Restores HP by 3/4 of the damage dealt.',
        "Rough play that may lower the foe's Attack.",
        'Strikes the foe with a fairy wind.',
        "Moonlight may lower the foe's Sp. Atk.",
        'Strikes both foes with a brilliant light.',
        "Lowers the foe's Attack. Moves first.",
    ),
    'fr': (
        'Un cri qui touche les deux ennemis à coup sûr.',
        'Restaure les PV à hauteur des 3/4 des dégâts.',
        "Une attaque qui peut baisser l'Attaque ennemie.",
        "Frappe l'ennemi avec un vent féerique.",
        "Un rayon de lune qui peut baisser l'Atq. Spé.",
        'Une lumière vive frappe les deux ennemis.',
        "Baisse l'Attaque ennemie. Frappe en premier.",
    ),
    'de': (
        'Ein Ruf, der beide Gegner stets trifft.',
        'Heilt KP um 3/4 des angerichteten Schadens.',
        'Ein Angriff, der den Angriff des Ziels senken kann.',
        'Trifft den Gegner mit einem Feenwind.',
        'Senkt eventuell den Spezial-Angriff.',
        'Grelles Licht trifft beide Gegner.',
        'Senkt den Angriff des Ziels. Hat Erstschlag.',
    ),
    'es': (
        'Un grito que acierta siempre a ambos rivales.',
        'Recupera en PS 3/4 del daño causado.',
        'Un ataque que puede bajar el Ataque del rival.',
        'Golpea al rival con un viento feérico.',
        'Luz lunar que puede bajar el At. Esp. del rival.',
        'Una luz intensa golpea a ambos rivales.',
        'Baja el Ataque del rival. Ataca primero.',
    ),
    'it': (
        'Un grido che colpisce sempre i due nemici.',
        'Ridà PS pari a 3/4 dei danni inflitti.',
        "Un attacco che può ridurre l'Attacco del nemico.",
        'Colpisce il nemico con un vento fatato.',
        "Luce lunare che può ridurre l'Att. Sp. del nemico.",
        'Una luce intensa colpisce i due nemici.',
        "Riduce l'Attacco del nemico. Colpisce per primo.",
    ),
    'ja': (
        'こえで　あいて２たいを　かならず　こうげきする。',
        'ダメージの　４ぶんの３　ＨＰを　かいふくする。',
        'こうげきし　たまに　あいての　こうげきを　さげる。',
        'ようせいの　かぜを　おこして　あいてを　こうげきする。',
        'つきの　ひかりで　とくこうを　さげることがある。',
        'まばゆい　ひかりで　あいて２たいを　こうげきする。',
        'せんせいして　あいての　こうげきを　さげる。',
    ),
}
_CLOSING = frozenset('、。，．！？!?」』）)]｝}〉》】〕〗〙〛ーぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮヵヶ々')
_OPENING = frozenset('「『（([｛{〈《【〔〖〘〚')


def native_description(canonical_id: int, language: str) -> str:
    """Return prose without embedded controls, terminators or hard line breaks."""
    if type(canonical_id) is not int or canonical_id not in NEW_MOVE_IDS:
        raise ValueError('Unsupported new Fairy move description')
    if language not in LANGUAGES:
        raise ValueError('Unsupported native Fairy description language')
    return _TEXTS[language][NEW_MOVE_IDS.index(canonical_id)]


@dataclass(frozen=True)
class NativeFontMetrics:
    font_id: int
    maximum_width: int
    advances: tuple[tuple[int, int], ...]

    def measure(self, text: str) -> Fraction:
        advances = dict(self.advances)
        width = Fraction(0)
        for char in text:
            if char == ' ':
                # Native gs_msg.c uses an integer right shift for spaces.
                width += self.maximum_width // 2
            elif ord(char) in advances:
                width += advances[ord(char)]
            else:
                raise FormatError(f'Native font {self.font_id} lacks glyph U+{ord(char):04X}')
        return width


@lru_cache(maxsize=6)
def _font_records(original_dol: bytes, game_id: str):
    """Scan each original once, including when two language fonts are used."""
    return font_banks_from_dol(original_dol, source=game_id + ' original DOL')


@lru_cache(maxsize=12)
def native_font_metrics(original_dol: bytes, game_id: str, font_id: int) -> NativeFontMetrics:
    """Read exact stored advances; never estimate unknown glyph widths."""
    if game_id not in GAME_IDS:
        raise ValueError('Unsupported native Fairy description game')
    if type(font_id) is not int or not 0 <= font_id <= 8:
        raise ValueError('A caller-qualified native font ID is required')
    banks, glyphs = _font_records(original_dol, game_id)
    selected = [bank for bank in banks if bank['font_id'] == font_id]
    maximums = {bank['maximum_width'] for bank in selected}
    if len(maximums) != 1:
        raise FormatError('Native description font is missing or has conflicting metrics')
    advances = {}
    for glyph in glyphs:
        if glyph.font_id != font_id:
            continue
        if glyph.code in advances and advances[glyph.code] != glyph.width:
            raise FormatError('Native description glyph has conflicting advances')
        advances[glyph.code] = glyph.width
    if not advances:
        raise FormatError('Native description font has no glyphs')
    return NativeFontMetrics(font_id, maximums.pop(), tuple(sorted(advances.items())))


def _tokens(text: str, language: str) -> list[str]:
    if language != 'ja':
        return re.findall(r'\S+|\s+', text)
    tokens = []
    for token in re.findall(r'[A-Za-z0-9]+|.', text):
        if tokens and (token[0] in _CLOSING or tokens[-1][-1] in _OPENING):
            tokens[-1] += token
        else:
            tokens.append(token)
    return tokens


def wrap_native_text(text: str, language: str, *, metrics: NativeFontMetrics,
                     width: int | Fraction, max_lines: int = 3) -> tuple[str, ...]:
    """Wrap complete words/glyph groups using exact advances, or reject overflow."""
    if language not in LANGUAGES or type(text) is not str or not text:
        raise ValueError('Invalid native description prose or language')
    if any(ord(char) < 32 or char == '\uffff' or 0xD800 <= ord(char) <= 0xDFFF for char in text):
        raise FormatError('Native description prose contains controls or invalid Unicode')
    if type(width) not in (int, Fraction) or width <= 0 or type(max_lines) is not int or max_lines < 1:
        raise ValueError('A positive measured rectangle width and line bound are required')
    lines, current, pending = [], '', ''
    for token in _tokens(text, language):
        if token.isspace():
            pending += token
            continue
        if metrics.measure(token) > width:
            raise FormatError('Native description word exceeds its measured rectangle width')
        candidate = current + (pending if current else '') + token
        if current and metrics.measure(candidate) > width:
            lines.append(current)
            current = token
        else:
            current = candidate
        pending = ''
    if current:
        lines.append(current)
    if len(lines) > max_lines:
        raise FormatError('Native description exceeds its measured line bound')
    if language == 'ja' and any(line[0] in _CLOSING or line[-1] in _OPENING for line in lines):
        raise FormatError('Native Japanese description violates line punctuation bounds')
    return tuple(lines)


def encode_native_description(canonical_id: int, language: str, *, original_dol: bytes,
                              game_id: str, width: int | Fraction | None = None,
                              font_id: int | None = None, max_lines: int = 3) -> bytes:
    """Encode native FFFF00 wraps, without adding an end-of-message terminator.

    ``width`` is expressed in the selected font's native advance units, after
    the caller accounts for any print-rectangle scale. Both width and font ID
    remain explicit until each native menu caller has been qualified.
    """
    if width is None or font_id is None:
        raise ValueError('The native description caller must qualify width and font_id')
    metrics = native_font_metrics(original_dol, game_id, font_id)
    lines = wrap_native_text(native_description(canonical_id, language), language,
                             metrics=metrics, width=width, max_lines=max_lines)
    return LINE_BREAK.join(line.encode('utf-16-be') for line in lines)
