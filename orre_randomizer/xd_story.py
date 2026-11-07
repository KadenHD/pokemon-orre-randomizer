"""Seeded species choices and dialogue for scripted XD encounters."""
from collections import Counter
from functools import partial
import re
import struct

from .engine.analyze_game import FormatError, check_range, u32
from .engine.gameplay_rules import OHKO, SELF_DESTRUCT, damaging
from .engine.inspect_tables import u16
from .engine.plusle_actor import companion_scale, load_actor_model, patch_actor
from .engine.species_rules import LEGENDARY_NATIONAL, WONDER_GUARD
from .xd_battle_rules import DPKM_MOVES
from .xd_field_actors import (
    GLOOM, LIGHTHOUSE_ARCHIVE, LIGHTHOUSE_CRY_MESSAGES, LIGHTHOUSE_TRAINER, LUDICOLO,
    WAKIN_CRY_MESSAGE, WAKIN_LAIR, WAKIN_SHIP, WAKIN_TRAINER,
)
from .xd_gifts import _native_name, _patch_banks, _patch_script, patch_species_operand, replace_species_name


TUTORIAL_SHADOW = 1
TEDDIURSA = 216
STARTER_DIALOGUE_ARCHIVE = "M5_labo_2F.fsys"
STARTER_ITEM_DIALOGUE = ("M6_junk_1F.fsys", (0xA0D0, 0xA0D1, 0xA0E4))
EAGUN_ACTOR_ARCHIVES = ("M3_shrine_1F.fsys", "M3_houseC_1F.fsys")
_EAGUN_TRAINER = 28
_EAGUN_CRY_MESSAGES = {
    EAGUN_ACTOR_ARCHIVES[0]: (0x94CD,),
    EAGUN_ACTOR_ARCHIVES[1]: (0x94F0, 0x94FA, 0x9503, 0x9507, 0x950E, 0x951E, 0x952B),
}
# Character.talk(message, species, 15) displays the text and plays the cry.
_EAGUN_CRY_CALL = re.compile(
    rb"\x02\x01\x00\x00(.{4})\x02\x01\x00\x00\x00\x00\x00\x19"
    rb"\x02\x01\x00\x00\x00\x00\x00\x0f.{4}\x09\x23\x00\x49", re.DOTALL,
)
DRAGONITE_DIALOGUE = {
    "D5_factory_1F.fsys": (0x851F,),
    "M5_labo_1F.fsys": (0x9E53,),
    "M6_tower_top.fsys": (0xA174, 0xA17B),
}
_WAKIN_COMMANDS = (0x7D1C, 0x84E4)
_WAKIN_SHIP_COMMAND = ("{name}, put him to sleep!", "{name}, endors-le !",
                      "{name}, schläfere ihn ein!", "{name}, fallo addormentare!",
                      "¡{name}, duérmelo!", "{name}！　こいつを　ねむらせてやれ！")
# Trainer row, original party slots (None skips a slot), and messages spoken
# about those slots. Field and battle messages can refer to the same team.
_TRAINER_DIALOGUE = {
    "Hundred": (
        (5, (306,), "fight_common.fsys", (0x565D, 0x565E)),
        (6, (286, 191), "fight_common.fsys", (0x565F,)),
        (11, (155,), "fight_common.fsys", (0x566A,)),
        (17, (392,), "fight_common.fsys", (0x5675, 0x5676)),
        (24, (287, 320), "fight_common.fsys", (0x5683,)),
        (25, (388,), "fight_common.fsys", (0x5685, 0x5686)),
        (26, (216,), "fight_common.fsys", (0x5688,)),
        (32, (393,), "fight_common.fsys", (0x5693, 0x5694)),
        (36, (88,), "fight_common.fsys", (0x569C,)),
        (54, (399, 247), "fight_common.fsys", (0x56BF,)),
        (55, (361, 303, 411, 109), "fight_common.fsys", (0x56C1,)),
        (78, (287, 300, 331, 327), "fight_common.fsys", (0x56EF, 0x56F0)),
        (94, (279, 285, 282, 154, 160, 157), "fight_common.fsys", (0x570F,)),
        (11, (155,), "D2_valley_2.fsys", (0x7980,)),
        (14, (298, 165), "D2_valley_2.fsys", (0x7986,)),
        (17, (392,), "D2_valley_2.fsys", (0x798C, 0x798D)),
        (25, (388,), "D2_valley_3.fsys", (0x799C,)),
        (28, (312, 326), "D2_valley_3.fsys", (0x79A2, 0x79A3)),
        (29, (195, 342), "D2_valley_3.fsys", (0x79A4,)),
        (32, (393,), "D2_magma_1.fsys", (0x79AA, 0x79AB)),
        (35, (411, 344), "D2_magma_1.fsys", (0x79B1,)),
        (36, (88,), "D2_magma_1.fsys", (0x79B3,)),
        (37, (317, 207), "D2_magma_1.fsys", (0x79B4,)),
        (38, (44, 168, 193), "D2_magma_1.fsys", (0x79B6,)),
        (38, (44,), "D2_magma_1.fsys", (0x79B7,)),
        (42, (316,), "D2_magma_2.fsys", (0x79BE,)),
        (44, (215, 278, 396), "D2_magma_2.fsys", (0x79C2,)),
        (45, (26, 299), "D2_magma_2.fsys", (0x79C4,)),
        (45, (None, 299), "D2_magma_2.fsys", (0x79C5,)),
        (57, (40, 365), "D2_magma_3.fsys", (0x79DC,)),
        (58, (294, 390, 205, 388), "D2_magma_3.fsys", (0x79DE,)),
        (58, (None, 390, None, 388), "D2_magma_3.fsys", (0x79DF,)),
        (59, (222, 373, 176), "D2_magma_3.fsys", (0x79E0,)),
        (67, (55, 181, 375, 82), "D2_cloud_1.fsys", (0x79F1,)),
        (68, (44, 192, 45), "D2_cloud_1.fsys", (0x79F2,)),
        (78, (287, 300, 331, 327), "D2_cloud_2.fsys", (0x7A06, 0x7A07)),
        (82, (None, None, 385, 314), "D2_cloud_3.fsys", (0x7A0F,)),
        (85, (336,), "D2_cloud_3.fsys", (0x7A15,)),
        (92, (248, 345, 28, 207, 384), "D2_cloud_4.fsys", (0x7A22,)),
        (94, (279, 285, 282, 154, 160, 157), "D2_cloud_4.fsys", (0x7A26, 0x7A27)),
    ),
    "Colosseum": (
        (17, (309, 111, 363), "fight_common.fsys", (0x5DDB,)),
        (21, (304, 177, 280, 358), "fight_common.fsys", (0x5DE5,)),
        (27, (385, 207, 345, 51), "fight_common.fsys", (0x5DF7,)),
        (29, (200, 336, 307, 237), "fight_common.fsys", (0x5DFD,)),
        (32, (299, 188, 321, 369), "fight_common.fsys", (0x5E06,)),
        (35, (369, 314, 289, 184), "fight_common.fsys", (0x5E11,)),
        (47, (None, 132), "fight_common.fsys", (0x5E35,)),
        (54, (366, 94, 65, 400, 329, 319), "fight_common.fsys", (0x5E4A,)),
        (61, (362, 397, 149, 334, 142, 145), "fight_common.fsys", (0x5E5D, 0x5E5F)),
        (63, (297, 375, 139, 230, 338, 211), "fight_common.fsys", (0x5E63, 0x5E65)),
    ),
    "Story": (
        (_EAGUN_TRAINER, (25,), EAGUN_ACTOR_ARCHIVES[0], (0x94CB, 0x94CC, *_EAGUN_CRY_MESSAGES[EAGUN_ACTOR_ARCHIVES[0]])),
        (_EAGUN_TRAINER, (25,), EAGUN_ACTOR_ARCHIVES[1], (0x952A, *_EAGUN_CRY_MESSAGES[EAGUN_ACTOR_ARCHIVES[1]])),
        *((LIGHTHOUSE_TRAINER, (None,) * slot + (LUDICOLO,), LIGHTHOUSE_ARCHIVE, (message,))
          for slot, message in enumerate(LIGHTHOUSE_CRY_MESSAGES)),
        (WAKIN_TRAINER, (GLOOM,), WAKIN_SHIP, (_WAKIN_COMMANDS[0],)),
        (WAKIN_TRAINER, (GLOOM,), WAKIN_LAIR, (_WAKIN_COMMANDS[1], 0x84E9, WAKIN_CRY_MESSAGE)),
    ),
}
_TEAM_CHALLENGE = ("Can you beat my team?", "Sauras-tu battre mon équipe ?",
                   "Kannst du mein Team besiegen?", "Saprai battere la mia squadra?",
                   "¿Podrás con mi equipo?", "わたしのチームに　かてるかな？")
_TEAM_PRAISE = ("My Pokémon did a great job!", "Mes Pokémon se sont bien battus !",
                "Meine Pokémon haben toll gekämpft!", "I miei Pokémon se la sono cavata bene!",
                "¡Mis Pokémon han luchado muy bien!", "ポケモンたち　よくやった！")
_TEAM_LOSS = ("You beat my team. Well done!", "Bravo, tu as battu mon équipe !",
              "Gut gemacht! Du hast mein Team besiegt!", "Bravo, hai battuto la mia squadra!",
              "¡Bien hecho! ¡Has vencido a mi equipo!", "わたしのチームに　かつとは　やるね！")
_SPECIES_REMARKS = {
    **dict.fromkeys((mid for messages in _EAGUN_CRY_MESSAGES.values() for mid in messages),
                    ("{name}!", "{name} !", "{name}!", "{name}!", "¡{name}!", "{name}！")),
    **dict.fromkeys((*LIGHTHOUSE_CRY_MESSAGES, WAKIN_CRY_MESSAGE),
                    ("{name}!", "{name} !", "{name}!", "{name}!", "¡{name}!", "{name}！")),
    _WAKIN_COMMANDS[1]: ("{name}, put them to sleep!", "{name}, endors-les !",
                         "{name}, schläfere sie ein!", "{name}, falli addormentare!",
                         "¡{name}, duérmelos!", "{name}！　ねむらせてやれ！"),
    0x84E9: ("Heh! My {name} comes in handy!", "Plutôt pratique, mon {name} !",
             "Hehe! Mein {name} ist echt nützlich!", "Eh eh! Il mio {name} è proprio utile!",
             "¡Je, je! ¡Mi {name} sí que es útil!", "へへっ。{name}は　やくにたつだろ？"),
    **dict.fromkeys((0x5685, 0x56BF, 0x56C1, 0x56EF, 0x570F, 0x7A27), _TEAM_PRAISE),
    **dict.fromkeys((0x5DE5, 0x5DF7, 0x5DFD, 0x5E5D, 0x5E63, 0x799C, 0x79A2, 0x79AA,
                     0x79B4, 0x79B6, 0x79C2, 0x79C4, 0x79DC, 0x79DE, 0x79E0, 0x7A22), _TEAM_CHALLENGE),
    **dict.fromkeys((0x5E11, 0x5E4A, 0x5E65, 0x79AB), _TEAM_LOSS),
    0x5683: ("Some matchups still make me shiver!", "Certains adversaires me font encore trembler !",
             "Manche Gegner lassen mich zittern!", "Certi avversari mi fanno ancora tremare!",
             "¡Hay rivales que aún me dan escalofríos!", "まだ　ぞっとする　あいても　いるよ！"),
    0x5E06: ("Today's forecast? A tough battle!", "La météo du jour ? Un combat serré !",
             "Meine Vorhersage? Ein harter Kampf!", "Le previsioni? Una lotta dura!",
             "¿El pronóstico? ¡Un combate reñido!", "きょうの　よほうは　はげしいバトル！"),
    0x5693: ("You had trouble with my {name}!", "Mon {name} t'a donné du fil à retordre !",
             "Mein {name} hat es dir schwer gemacht!", "Il mio {name} ti ha dato filo da torcere!",
             "¡Mi {name} te lo ha puesto difícil!", "{name}には　くろうしただろう！"),
    0x5694: ("You knew how to handle my {name}!", "Tu as bien joué contre mon {name} !",
             "Du hast mein {name} gut gekontert!", "Hai saputo affrontare il mio {name}!",
             "¡Has sabido plantarle cara a mi {name}!", "{name}の　あいてを　よくできたね！"),
    0x56F0: ("Oh, dear. My team lost.", "Oh là là, mon équipe a perdu.",
             "Oje, mein Team hat verloren.", "Oh, no. La mia squadra ha perso.",
             "Vaya, mi equipo ha perdido.", "あらら　わたしのチームが　まけちゃった。"),
    0x798D: ("How did my {name} do?", "Il t'a plu, mon {name} ?",
             "Wie fandest du mein {name}?", "Come ti è sembrato {name}?",
             "¿Qué te ha parecido mi {name}?", "{name}は　どうだった？"),
    0x79A4: ("Can you beat {name} and {partner}?", "Tu peux battre {name} et {partner} ?",
             "Besiegst du {name} und {partner}?", "Sai battere {name} e {partner}?",
             "¿Puedes con {name} y {partner}?", "{name}と　{partner}に　かてるかな？"),
    0x79B7: ("My {name} loves the outdoors.", "Mon {name} aime le grand air.",
             "Mein {name} ist gern draußen.", "A {name} piace stare all'aperto.",
             "A mi {name} le gusta el aire libre.", "{name}は　そとが　だいすき。"),
    0x79B3: ("Come and see my {name} again!", "Reviens voir mon {name} !",
             "Besuch mein {name} doch wieder!", "Torna a trovare il mio {name}!",
             "¡Vuelve a ver a mi {name}!", "また　{name}に　あいにきてね！"),
    0x79BE: ("My {name} might surprise you!", "Mon {name} va te surprendre !",
             "Mein {name} wird dich überraschen!", "Il mio {name} ti sorprenderà!",
             "¡Mi {name} te va a sorprender!", "{name}に　びっくりするよ！"),
    0x79C5: ("Isn't my {name} cute?", "Il est mignon, mon {name}, non ?",
             "Ist mein {name} nicht süß?", "Non è carino il mio {name}?",
             "¿A que es adorable mi {name}?", "{name}って　かわいいでしょう？"),
    0x79F1: ("Time to let my Pokémon rest.", "Mes Pokémon ont bien mérité une pause.",
             "Meine Pokémon haben eine Pause verdient.", "I miei Pokémon si meritano una pausa.",
             "Mis Pokémon se merecen un descanso.", "ポケモンたちを　やすませてあげよう。"),
    0x79F2: ("80 years of training. Show me!", "80 ans d'entraînement. À toi !",
             "80 Jahre Training. Zeig's mir!", "80 anni di allenamento. Forza!",
             "¡80 años entrenando! ¡Adelante!", "はちじゅうねんの　しゅぎょうじゃ！　いくぞ！"),
    0x7A06: ("Watch what my {name} can do!", "Regarde ce que sait faire mon {name} !",
             "Schau, was mein {name} kann!", "Guarda cosa sa fare il mio {name}!",
             "¡Mira de qué es capaz mi {name}!", "{name}の　ちからを　みせてあげる！"),
    0x7A07: ("You and my {name} fought well!", "Quel combat contre mon {name} !",
             "Was für ein Kampf gegen mein {name}!", "Che lotta contro il mio {name}!",
             "¡Qué combate contra mi {name}!", "{name}との　いいバトルだったよ！"),
    0x7A0F: ("{name} and {partner}, my duo!", "Mon duo, {name} et {partner} !",
             "{name} und {partner}, mein Duo!", "Che duo, {name} e {partner}!",
             "¡Mi dúo, {name} y {partner}!", "{name}と　{partner}は　めいコンビ！"),
    0x7A15: ("I'll train with my {name}!", "Je vais m'entraîner avec mon {name} !",
             "Ich trainiere mit meinem {name}!", "Mi allenerò con il mio {name}!",
             "¡Voy a entrenar con mi {name}!", "{name}と　トレーニングするわ！"),
    0x7A26: ("Which of my Pokémon would you pick?", "Quel Pokémon choisirais-tu dans mon équipe ?",
             "Welches meiner Pokémon würdest du wählen?", "Quale dei miei Pokémon sceglieresti?",
             "¿Qué Pokémon elegirías de mi equipo?", "わたしのポケモンなら　どれをえらぶ？"),
    0x5E35: ("I thought my {name} would win!", "Je pensais gagner avec mon {name} !",
             "Ich dachte, mein {name} gewinnt!", "Pensavo di vincere con il mio {name}!",
             "¡Creía que ganaría con mi {name}!", "{name}なら　かてると　おもったのに！"),
    0x5E5F: ("Even my best moves weren't enough!", "Mes meilleures capacités n'ont pas suffi !",
             "Selbst meine besten Attacken waren zu schwach!", "Neanche le mie mosse migliori sono bastate!",
             "¡Ni mis mejores movimientos bastaron!", "とくいな　わざでも　だめだった！"),
    0xA0E4: (
        "Thanks for listening! Pick one of my items.", "Merci de m'avoir écouté. Choisis un objet !",
        "Danke fürs Zuhören! Such dir etwas aus.", "Grazie di avermi ascoltato! Scegli un oggetto.",
        "¡Gracias por escuchar! Elige un objeto.", "おれいだよ。ひとつ　えらんでね。",
    ),
}
_ITEM_EEVEE_REFERENCES = {
    0xA0D0: {
        "UK": ("your EEVEE", "an EEVEE", 1),
        "FR": ("ton EVOLI", "un EVOLI", 1),
        "SP": ("tu\nEEVEE", "un\nEEVEE", 1),
    },
    0xA0D1: {
        "UK": ("your EEVEE", "an EEVEE", 3),
        "FR": ("ton EVOLI", "un EVOLI", 2),
        "GE": ("dein EVOLI", "ein EVOLI", 1),
        "IT": ("il tuo EEVEE", "un EEVEE", 1),
        "SP": ("tu EEVEE", "un EEVEE", 3),
    },
}
_TYPE_REMARKS = {0x5683, 0x5685, 0x5693, 0x5694, 0x56EF, 0x56F0, 0x570F,
                 0x5DE5, 0x5DFD, 0x799C, 0x79AA, 0x79AB, 0x79B6, 0x79B7, 0x79F2,
                 0x7A06, 0x7A07, 0x7A26, 0x7A27}
_ABILITY_REMARKS = {0x56C1, 0x798D, 0x79A2, 0x79A4, 0x79BE, 0x79C2, 0x79C4, 0x79DC, 0x79E0}
_MOVE_REMARKS = {0x5DF7, 0x5E06, 0x5E11, 0x5E4A, 0x5E5D, 0x5E5F, 0x5E63, 0x5E65, 0x79F1, 0x7A22}
_IMMUNE_TYPES = {0: 7, 1: 7, 3: 8, 4: 2, 7: 0, 13: 4, 14: 17}
_ABSORB_ABILITIES = {4: 26, 10: 18, 11: 11, 13: 10}
_CONDITIONAL_ATTACKS = OHKO | SELF_DESTRUCT | {68, 117, 138, 173, 243, 255}


def tutorial_candidates(starter, eligible, move_randomizer):
    """Exclude opponents that the starter's regular attacks cannot hit."""
    catalog = move_randomizer.species
    attacks = [move_randomizer.catalog[move] for move in starter["moves"]
               if move in move_randomizer.catalog and move not in _CONDITIONAL_ATTACKS
               and damaging(move_randomizer.catalog[move])]
    result = []
    for index in sorted(eligible):
        row = catalog[index]
        if (index == TEDDIURSA or row["national_dex"] in LEGENDARY_NATIONAL
                or row["total"] > 410 or WONDER_GUARD in row["abilities"]):
            continue
        for move in attacks:
            kind = move["type"]
            if (_IMMUNE_TYPES.get(kind) not in row["types"]
                    and _ABSORB_ABILITIES.get(kind) not in row["abilities"]
                    and (move["index"] not in (253, 304) or 43 not in row["abilities"])):
                result.append(index)
                break
    return result


def hordel_candidates(eligible, edges, families, *, accessible_evolutions):
    """Pick base forms with a single evolution that players can reach in XD."""
    family_sizes = Counter(families.values())
    methods = {4, 7} | ({5, 6, 15} if accessible_evolutions else set())
    result = {}
    for base in sorted(eligible):
        routes = edges.get(base, ())
        if family_sizes[families[base]] == 2 and len(routes) == 1:
            _, method, _, evolved = routes[0]
            if method in methods and not edges.get(evolved):
                result[base] = evolved
    return result


def patch_starter_dialogue(source, game_id, national, name_banks):
    def edits(language):
        old = _native_name(name_banks, language, 133)
        native = old.encode("utf-16-be")
        chosen = _native_name(name_banks, language, national).encode("utf-16-be")

        def replace_starter(original, count, shorten=()):
            if original.count(native) != count:
                raise FormatError("unexpected starter names in the XD lab dialogue")
            for before, after in shorten:
                if original.count(before) != 1:
                    raise FormatError("unexpected XD lab dialogue line")
                original = original.replace(before, after)
            return original.replace(native, chosen)

        # The longest starter names must fit on the existing lines.
        compact = {
            "FR": ("Tu l'as commandé comme si c'était ton ", "Tu l'as mené comme ton "),
            "GE": ("könntest langsam anfangen, neben deinem ", "könntest beginnen, neben deinem "),
            "IT": ("delle stesse dimensioni del tuo ", "grande come il tuo "),
            "UK": ("raising other POKéMON besides your ", "raising others besides your "),
        }
        language_key = "UK" if language == "US" else language
        shorten = []
        if language_key in compact:
            before, after = compact[language_key]
            shorten.append(((before + old).encode("utf-16-be"), (after + old).encode("utf-16-be")))
        elif language_key == "JP":
            your = (b"\xff\xff\x04" + "自分".encode("utf-16-be") + b"\xff\xff\x05"
                    + "じぶん".encode("utf-16-be") + b"\xff\xff\x06" + "の　".encode("utf-16-be"))
            shorten.append((your + native, native))
        return {0x9C42: partial(replace_starter, count=2, shorten=shorten),
                0x9C43: partial(replace_starter, count=1)}

    return _patch_banks(source, game_id, edits)


def patch_eagun_actor(original, current, rel, species_table, species, dol, game_id, read_archive, updates):
    row = 0x20 + _EAGUN_TRAINER * 0x38
    position = 0x20 + u32(original, 0x14) + 0x20 * u16(original, row + 0x1C)
    if original[row + 4] & 1 or u16(original, position) != 25:
        raise FormatError("unexpected XD team for Eagun's field partner")
    chosen = u16(current, position)
    if chosen == 25:
        return None
    national = species[chosen][0]
    scale = companion_scale(national, 0.65)
    model_id = u16(rel, species_table + 0x124 * chosen + 0x2E)
    model = load_actor_model(dol, game_id, model_id, read_archive, scale=scale)
    for archive in EAGUN_ACTOR_ARCHIVES:
        source = updates[archive] if archive in updates else read_archive(archive)
        source = patch_actor(source, model, identifier="0x18830400", name="pikachu")
        updates[archive] = _patch_script(
            source, archive.removesuffix(".fsys"),
            partial(_patch_eagun_cry, chosen=chosen, messages=_EAGUN_CRY_MESSAGES[archive]),
        )
    return {"species": chosen, "national_dex": national, "scale": scale}


def _patch_eagun_cry(source, *, chosen, messages):
    result = bytearray(source)
    found = set()
    for call in _EAGUN_CRY_CALL.finditer(source):
        identifier = u32(source, call.start(1))
        if identifier in messages:
            patch_species_operand(source, result, call.start() + 12, 25, chosen)
            found.add(identifier)
    if found != set(messages):
        raise FormatError("missing scripted cries for Eagun's partner")
    return bytes(result)


def trainer_dialogue_edits(deck_name, original, current, species, game_id, *,
                           randomize_abilities=False, randomize_types=False):
    """Use the post-policy party species for explicitly identified remarks."""
    edits = {}
    rewrite_facts = set()
    if randomize_abilities:
        rewrite_facts.update(_ABILITY_REMARKS)
    if randomize_types:
        rewrite_facts.update(_TYPE_REMARKS)
    pokemon_start = 0x20 + u32(original, 0x14)
    for trainer, expected, archive, identifiers in _TRAINER_DIALOGUE[deck_name]:
        row = 0x20 + trainer * 0x38
        names = {}
        check_moves = not _MOVE_REMARKS.isdisjoint(identifiers) or any(mid in _WAKIN_COMMANDS for mid in identifiers)
        changed_moves = False
        for slot, old in enumerate(expected):
            if old is None:
                continue
            position = pokemon_start + 0x20 * u16(original, row + 0x1C + slot * 2)
            if original[row + 4] & (1 << slot) or u16(original, position) != old:
                raise FormatError("unexpected XD team for trainer dialogue")
            chosen = u16(current, position)
            names[1000 + species[old][0]] = 1000 + species[chosen][0]
            if check_moves:
                changed_moves |= any(u16(original, position + move) != u16(current, position + move)
                                     for move in DPKM_MOVES)
        archives = (archive,)
        if archive == "fight_common.fsys" and game_id == "GXXP01":
            archives += tuple(f"fight_common_{language}.fsys" for language in ("fr", "ge", "it", "sp"))
        changed = any(old != chosen for old, chosen in names.items())
        for identifier in identifiers:
            needs_edit = changed_moves if identifier in _MOVE_REMARKS else changed or identifier in rewrite_facts
            needs_edit |= identifier in _WAKIN_COMMANDS and changed_moves
            if needs_edit:
                for path in archives:
                    edits.setdefault(path, {})[identifier] = names
    return edits


def _replace_species_remark(source, *, changes, language, translations, last_page=False):
    speaker = b"\xff\xff\x59"
    previous = b""
    if last_page:
        if source.count(speaker) != 2:
            raise FormatError("unexpected XD Wakin dialogue pages")
        previous, source = source[:source.rfind(speaker)], source[source.rfind(speaker):]
    # Intro messages can end directly after the text. Field and result
    # messages carry their native wait/close control before the terminator.
    end = source[-5:] if source[-5:-3] == b"\xff\xff" else source[-2:]
    if not source.startswith(speaker) or end not in (b"\0\0", b"\xff\xff\x02\0\0", b"\xff\xff\x6d\0\0"):
        raise FormatError("unexpected XD trainer dialogue controls")
    locale = ("UK", "FR", "GE", "IT", "SP", "JP").index("UK" if language == "US" else language)
    prefix = "「" if language == "JP" else ": "
    names = dict(zip(("name", "partner"), changes.values(), strict=False))
    return previous + speaker + (prefix + translations[locale].format(**names)).encode("utf-16-be") + end


def _replace_item_eevee_reference(source, *, changes, language, references):
    reference = references.get("UK" if language == "US" else language)
    if reference is None:
        return source
    before, after, expected_count = reference
    line_break = b"\xff\xff\x00"
    original = line_break.join(part.encode("utf-16-be") for part in before.split("\n"))
    updated = line_break.join(part.encode("utf-16-be") for part in after.split("\n"))
    if source.count(original) != expected_count:
        raise FormatError("unexpected Eevee reference in the Gateon Port item dialogue")
    return source.replace(original, updated)


TRAINER_REMARK_REWRITES = {
    **{identifier: partial(_replace_species_remark, translations=translations)
       for identifier, translations in _SPECIES_REMARKS.items()},
    _WAKIN_COMMANDS[0]: partial(_replace_species_remark, translations=_WAKIN_SHIP_COMMAND, last_page=True),
    **{identifier: partial(_replace_item_eevee_reference, references=references)
       for identifier, references in _ITEM_EEVEE_REFERENCES.items()},
}


def patch_tutorial(game_id, chosen, national, name_banks, read_archive):
    def edit_script(original):
        offset = 0x816C if game_id == "GXXJ01" else 0x818C
        check_range(original, offset - 4, 28, "XD tutorial dialogue variable")
        if struct.unpack_from(">7I", original, offset - 4) != (
            0x02010000, TEDDIURSA, 0x02010000, 0x4E, 0x11030028, 0x0928001C, 0x06030000,
        ):
            raise FormatError("unexpected XD tutorial dialogue variable")
        updated = bytearray(original)
        patch_species_operand(original, updated, offset, TEDDIURSA, chosen)
        return bytes(updated)

    def edits(language, message):
        old = _native_name(name_banks, language, TEDDIURSA)
        new = _native_name(name_banks, language, national)
        return {message: partial(replace_species_name, language=language, old=old, chosen=new)}

    lab = "M5_labo_1F.fsys"
    rematch = "D1_labo_B2.fsys"
    return {
        lab: _patch_banks(_patch_script(read_archive(lab), "M5_labo_1F", edit_script),
                          game_id, lambda lang: edits(lang, 0x9CDD)),
        rematch: _patch_banks(read_archive(rematch), game_id, lambda lang: edits(lang, 0x759E)),
    }
