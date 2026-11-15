"""Localized native messages for the optional Colosseum Lugia shrine scene.

Hero and partner names remain native message controls. The game resolves them
from the current save; they must never be replaced with their default names.
"""
from __future__ import annotations

from collections.abc import Mapping
import re

from .analyze_game import FormatError
from .postgame_font_metrics import FONT0_ADVANCES, FONT0_MAX_WIDTH, FONT0_SPACE_ADVANCE


BOSS_NAME_ID = 4167
EAGUN_NAME_ID = 0x10E1
ACTOR_IDS = {"hero": 100, "partner": 101, "eagun": 1, "boss": 4}
NAME_CONTROLS = {"hero": b"\xff\xff\x2b", "partner": b"\xff\xff\x2c"}
MESSAGE_END = b"\xff\xff\x02\0\0"
LINE_BREAK = b"\xff\xff\x00"
CAPTION_WIDTH = 420
SAVED_NAME_ADVANCE = 10 * FONT0_MAX_WIDTH

ARRIVAL_KEYS = (
    "arrival_aura", "arrival_warning", "arrival_return", "arrival_escape", "arrival_freed",
    "arrival_relic", "arrival_lugia", "arrival_heart", "arrival_stand",
    "arrival_snag", "arrival_challenge",
)
CAPTURE_BEFORE_EXIT_KEYS = ("capture_failed", "capture_retreat")
CAPTURE_AFTER_EXIT_KEYS = ("capture_relief", "capture_saved", "capture_purify")
CAPTURE_KEYS = CAPTURE_BEFORE_EXIT_KEYS + CAPTURE_AFTER_EXIT_KEYS
RETRY_KEYS = ("retry_victory", "retry_lugia")
LOSS_KEYS = ("loss_defiance",)
ORDERED_KEYS = ARRIVAL_KEYS + CAPTURE_KEYS + RETRY_KEYS + LOSS_KEYS
MESSAGE_IDS = {key: 0xF0050 + index for index, key in enumerate(ORDERED_KEYS)}
SPEAKERS = dict(zip(ORDERED_KEYS, (
    "partner", "eagun", "boss", "boss", "boss", "boss", "boss", "partner", "eagun",
    "partner", "boss", "boss", "boss", "partner", "eagun", "eagun", "boss",
    "boss", "boss",
), strict=True))

# Each entry is prose for one dialogue bubble. The writer below derives native
# line-break controls from measured glyph advances, rather than hand formatting.
TEXTS = {
    "UK": (
        "That Pokémon... I've never seen such a strong aura!",
        "Stay behind me! He has brought a Shadow Pokémon here.",
        "You dismantled CIPHER. I have not forgotten.",
        "CIPHER still has loyal followers. They freed me.",
        "You purified all 48 Shadow Pokémon. All our work...",
        "I will destroy the RELIC STONE to put an end to that.",
        "LUGIA is our last subject. It will raze this shrine.",
        "Its heart is still there. We can save it!",
        "I will not let CIPHER defile this place!",
        "{hero}, snag LUGIA before it attacks the stone!",
        "Then try! This time, I will finish what we began!",
        "You took LUGIA from me... Our last hope.",
        "It is over. I am leaving this place.",
        "It's safe with us now. We can help it recover!",
        "You saved the RELIC STONE. Thank you, both of you.",
        "LUGIA still needs your help to open its heart.",
        "Beating me is not enough. LUGIA is still ours!",
        "Come back when you can snag it!",
        "The RELIC STONE will fall. You cannot stop us!",
    ),
    "FR": (
        "Ce Pokémon... Je n'ai jamais vu une telle aura !",
        "Restez derrière moi ! C'est un Pokémon obscur.",
        "Tu as démantelé le GROUPE OMBRE. Je n'ai pas oublié.",
        "Des fidèles du GROUPE OMBRE m'ont libéré.",
        "Tu as purifié nos 48 Pokémon obscurs.",
        "Je vais détruire la Relique pour que cela cesse.",
        "LUGIA est notre dernier sujet. Il rasera ce lieu.",
        "Son cœur est encore là. On peut le sauver !",
        "Le GROUPE OMBRE ne profanera pas ce lieu !",
        "{hero}, snatche LUGIA avant qu'il attaque la Relique !",
        "Essaie donc ! Cette fois, j'irai jusqu'au bout !",
        "Tu m'as pris LUGIA... Notre dernier espoir.",
        "Tout est perdu. Je quitte ce lieu.",
        "Il est avec nous. Il ne fera plus de mal ici !",
        "Tu as sauvé la Relique. Merci à vous deux.",
        "LUGIA a encore besoin de toi pour être purifié.",
        "Me battre ne suffit pas. LUGIA est encore à nous !",
        "Reviens quand tu seras capable de le snatcher !",
        "La Relique tombera. Tu ne peux pas nous arrêter !",
    ),
    "GE": (
        "Dieses Pokémon... So eine starke Aura kenne ich nicht!",
        "Bleibt hinter mir! Das ist ein Crypto-Pokémon.",
        "Du hast CRYPTO zerschlagen. Das vergesse ich nicht.",
        "CRYPTO hat noch treue Anhänger. Sie haben mich befreit.",
        "Du hast alle 48 Crypto-Pokémon erlöst.",
        "Ich zerstöre dieses Heiligtum. Dann ist Schluss damit.",
        "LUGIA ist unser letztes Experiment. Es wird alles zerstören.",
        "Sein Herz ist noch da. Wir können es retten!",
        "CRYPTO wird diesen Ort nicht entweihen!",
        "{hero}, kralle LUGIA, bevor es das Heiligtum angreift!",
        "Versuch es! Diesmal bringen wir es zu Ende!",
        "Du hast mir LUGIA genommen... Unsere letzte Hoffnung.",
        "Es ist vorbei. Ich verlasse diesen Ort.",
        "Es ist bei uns in Sicherheit. Wir können ihm helfen!",
        "Du hast das Heiligtum gerettet. Ich danke euch beiden.",
        "LUGIA braucht dich noch, um sein Herz zu öffnen.",
        "Ein Sieg reicht nicht. LUGIA gehört noch uns!",
        "Komm wieder, wenn du es krallen kannst!",
        "Das Heiligtum wird fallen. Du hältst uns nicht auf!",
    ),
    "SP": (
        "Ese Pokémon... ¡Nunca había visto un aura tan fuerte!",
        "¡Quedaos detrás de mí! Es un Pokémon oscuro.",
        "Desmantelaste CÍFER. No lo he olvidado.",
        "Aún quedan fieles a CÍFER. Ellos me liberaron.",
        "Has purificado a nuestros 48 Pokémon oscuros.",
        "Destruiré la Piedra Sagrada para acabar con esto.",
        "LUGIA es nuestro último sujeto. Arrasará este lugar.",
        "Su corazón sigue ahí. ¡Podemos salvarlo!",
        "¡No dejaré que CÍFER profane este lugar!",
        "¡{hero}, captura a LUGIA antes de que ataque la Piedra!",
        "¡Inténtalo! ¡Esta vez acabaré lo que empezamos!",
        "Me has quitado a LUGIA... Nuestra última esperanza.",
        "Se acabó. Me marcho de este lugar.",
        "Está a salvo con nosotros. ¡Podemos ayudarlo!",
        "Has salvado la Piedra Sagrada. Gracias a los dos.",
        "LUGIA aún necesita tu ayuda para abrir su corazón.",
        "No basta con vencerme. ¡LUGIA sigue siendo nuestro!",
        "¡Vuelve cuando puedas capturarlo!",
        "La Piedra Sagrada caerá. ¡No puedes detenernos!",
    ),
    "IT": (
        "Quel Pokémon... Non ho mai visto un'aura così forte!",
        "State dietro di me! Quello è un Pokémon Ombra.",
        "Hai smantellato la CRIPTO. Non l'ho dimenticato.",
        "La CRIPTO ha ancora dei fedeli. Mi hanno liberato.",
        "Hai purificato tutti i nostri 48 Pokémon Ombra.",
        "Distruggerò la SACRA PIETRA per porre fine a tutto.",
        "LUGIA è il nostro ultimo soggetto. Raderà al suolo il tempio.",
        "Il suo cuore è ancora lì. Possiamo salvarlo!",
        "Non lascerò che la CRIPTO profani questo luogo!",
        "{hero}, clepta LUGIA prima che attacchi la PIETRA!",
        "Provaci! Stavolta finirò ciò che abbiamo iniziato!",
        "Mi hai portato via LUGIA... La nostra ultima speranza.",
        "È finita. Me ne vado da questo luogo.",
        "È al sicuro con noi. Possiamo aiutarlo!",
        "Hai salvato la SACRA PIETRA. Vi ringrazio entrambi.",
        "LUGIA ha ancora bisogno di te per aprire il suo cuore.",
        "Battermi non basta. LUGIA è ancora nostro!",
        "Torna quando sarai capace di cleptarlo!",
        "La SACRA PIETRA cadrà. Non puoi fermarci!",
    ),
    "JP": (
        "あのポケモン……　すごく　つよい　オーラだわ！",
        "さがっておれ！　ダークポケモンじゃ！",
        "シャドーを　つぶしたことは　わすれんぞ。",
        "シャドーの　なかまが　わたしを　にがしてくれた。",
        "４８ひき　すべて　リライブしたそうだな。",
        "この　ほこらを　こわせば　リライブも　おわりだ。",
        "ルギアは　さいごの　じっけんたいだ！",
        "でも　こころは　のこってる。　まだ　たすけられる！",
        "シャドーに　このばしょを　あらさせは　せん！",
        "{hero}！　ルギアを　スナッチして！",
        "こんどこそ　ここで　けっちゃくを　つける！",
        "ルギアまで……　さいごの　のぞみだったのに。",
        "もう　おわりだ。　ここを　さる。",
        "もう　だいじょうぶ。　いっしょに　たすけよう！",
        "ほこらを　まもってくれたな。　ふたりとも　ありがとう。",
        "ルギアの　こころも　とりもどしてやってくれ。",
        "かつだけでは　だめだ！　ルギアは　まだ　わたしのものだ！",
        "スナッチできるように　なってから　こい！",
        "ほこらは　こわす！　だれにも　とめられん！",
    ),
}

_NAME_PATTERN = re.compile(r"\{(hero|partner)\}")
_JP_TOKEN_PATTERN = re.compile(r"\{(?:hero|partner)\}|.")


def _encode_words(text: str) -> bytes:
    if not text or any(char in text for char in ("\n", "\r", "\0", "\uffff", "\u2013", "\u2014")):
        raise FormatError("invalid Lugia scene dialogue text")
    result = bytearray()
    start = 0
    for match in _NAME_PATTERN.finditer(text):
        result.extend(text[start:match.start()].encode("utf-16-be"))
        result.extend(NAME_CONTROLS[match[1]])
        start = match.end()
    result.extend(text[start:].encode("utf-16-be"))
    return bytes(result)


def text_advance(text: str) -> int:
    """Measure font0 text, reserving the full native limit for saved names.

    Room-local Japanese glyph additions are not in PAL's Latin font. Their
    unknown advances use24 pixels, conservatively above font0's22-pixel cell.
    """
    width, start = 0, 0
    for match in _NAME_PATTERN.finditer(text):
        width += text_advance(text[start:match.start()]) + SAVED_NAME_ADVANCE
        start = match.end()
    for character in text[start:]:
        width += (FONT0_SPACE_ADVANCE if character == " " else
                  FONT0_ADVANCES.get(ord(character), 24 if ord(character) >= 0x3000 else FONT0_MAX_WIDTH))
    return width


class NewSceneCaptionWriter:
    """Wrap whole Latin words or Japanese glyphs without splitting controls."""

    def __init__(self, language: str, *, width: int = CAPTION_WIDTH):
        if width < SAVED_NAME_ADVANCE:
            raise ValueError("caption width cannot hold a native saved name")
        self.language = language
        self.width = width

    def encode(self, paragraph: str) -> bytes:
        _encode_words(paragraph)  # Validate source prose before adding controls.
        if self.language == "JP":
            tokens = []
            for token in _JP_TOKEN_PATTERN.findall(paragraph):
                # Closing punctuation stays with its preceding glyph/name.
                if token in "、。！？!?」』）)" and tokens and not tokens[-1].isspace():
                    tokens[-1] += token
                else:
                    tokens.append(token)
        else:
            tokens = re.findall(r"\S+|\s+", paragraph)
        lines, current, used, pending_space = [], bytearray(), 0, ""
        for token in tokens:
            if token.isspace():
                pending_space = token
                continue
            advance = text_advance(token)
            if advance > self.width:
                raise FormatError("Lugia dialogue word exceeds the native caption width")
            gap = text_advance(pending_space) if current else 0
            if current and used + gap + advance > self.width:
                lines.append(bytes(current))
                current, used, gap = bytearray(), 0, 0
            if gap:
                current.extend(_encode_words(pending_space))
                used += gap
            current.extend(_encode_words(token))
            used += advance
            pending_space = ""
        if current:
            lines.append(bytes(current))
        if len(lines) > 3:
            raise FormatError("Lugia dialogue exceeds three native caption lines")
        return LINE_BREAK.join(lines)


def event_species_text(text: str, language: str, species_name: str | None = None) -> str:
    """Substitute only this authored encounter's explicit species references."""
    if species_name is None:
        return text
    if not species_name or any(char in species_name for char in ("\n", "\r", "\0", "\uffff", "{", "}")):
        raise FormatError("invalid bonus Shadow species name")
    return text.replace("ルギア" if language == "JP" else "LUGIA", species_name)


def dialogue_payloads(language: str, names: Mapping[int, str], *, species_name=None) -> dict[int, bytes]:
    """Return complete MSG allocations, including native name controls/endings.

    ``names`` is the selected language's original common-REL name dictionary.
    The room's CMS still selects the actor through standard functions54/55.
    """
    language = "UK" if language == "US" else language
    if language not in TEXTS:
        raise FormatError("unsupported Lugia scene dialogue language")
    bodies = TEXTS[language]
    result = {}
    for key, body in zip(ORDERED_KEYS, bodies, strict=True):
        if species_name is not None and key == "arrival_snag":
            # Reserve the maximum width of both saved player names and the
            # longest native species names. The authored Lugia line is longer.
            body = {
                "UK": "{hero}, snag LUGIA!",
                "GE": "{hero}, kralle LUGIA!",
                "FR": "{hero}, snatche LUGIA !",
                "SP": "¡{hero}, arrebata a LUGIA!",
                "IT": "{hero}, clepta LUGIA!",
                "JP": body,
            }[language]
        body = event_species_text(body, language, species_name)
        speaker = SPEAKERS[key]
        if speaker in NAME_CONTROLS:
            prefix = "{" + speaker + "}"
        else:
            name_id = BOSS_NAME_ID if speaker == "boss" else EAGUN_NAME_ID
            name = names.get(name_id)
            if not isinstance(name, str) or not name:
                raise FormatError("missing native Lugia scene speaker name")
            prefix = name
        separator = "「" if language == "JP" else " : " if language == "FR" else ": "
        suffix = "」" if language == "JP" else ""
        try:
            payload = NewSceneCaptionWriter(language).encode(prefix + separator + body + suffix)
        except FormatError as error:
            raise FormatError(f"{language}/{key}: {error}") from error
        result[MESSAGE_IDS[key]] = payload + MESSAGE_END
    return result
