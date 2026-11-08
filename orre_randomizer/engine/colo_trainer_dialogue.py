"""Colosseum battle dialogue shared by the fight and Mt. Battle archives."""
from functools import partial

from .analyze_game import FormatError, u32
from .gameplay_rules import MOVE_FIELDS
from .inspect_tables import localized_names, u16
from .randomize_trainers import layout


_MOUNT_BATTLE = (
    "D2_crater_colo.fsys",
    *(f"D2_{area}_{index}.fsys" for area, count in (("valley", 3), ("magma", 3), ("cloud", 4), ("rest", 9))
      for index in range(1, count + 1)),
)
_DANCE_MOVES = {14, 80, 240, 297, 298, 349}
_LINES = {
    # Rows 190 and 362 point to the shared placeholder team. Avoid claiming
    # which species will be sent out or which move it knows in these battles.
    0x3F81: ("My team can take you!", "Mon équipe peut te battre !", "Mein Team besiegt dich!",
             "La mia squadra ti batterà!", "¡Mi equipo te ganará!", "オレのチームが　あいてだ！"),
    0x405E: ("My team will put you in your place!", "Mon équipe va te donner une leçon !",
             "Mein Team wird dir eine Lektion erteilen!", "La mia squadra ti darà una lezione!",
             "¡Mi equipo te dará una lección!", "あたしのチームが　おしえてあげる！"),
    0x3FCB: ("Watch what my team can do!", "Regarde ce que sait faire mon équipe !",
             "Schau, was mein Team kann!", "Guarda cosa sa fare la mia squadra!",
             "¡Mira de qué es capaz mi equipo!", "わたしのチームの　うでを　みて！"),
    0x4E36: ("Want to take on my {first}?", "Tu veux affronter mon {first} ?",
             "Willst du gegen mein {first} antreten?", "Vuoi affrontare il mio {first}?",
             "¿Quieres enfrentarte a mi {first}?", "ボクの　{first}と　バトルする？"),
    0x4E9B: ("Go, {first}!", "Allez, {first} !", "Los, {first}!", "Forza, {first}!",
             "¡Vamos, {first}!", "いけっ　{first}！"),
    0x5AB6: ("My POKéMON put on a show!", "Mes POKéMON font le spectacle !",
             "Vorhang auf für meine POKéMON!", "In scena, miei POKéMON!",
             "¡Mis POKéMON darán espectáculo!", "あたいのポケモンの　ショーだよ！"),
    # D2_cloud_3 function 32 picks 0x581A for its first opponent. Both
    # original chants are linked to the same Mt. Battle trainer, Reman.
    0x581A: ("{first}, {second}…",) * 5 + ("{first}、{second}……",),
    0x59EE: ("{first}! {second}!",) * 4 + ("¡{first}! ¡{second}!", "{first}！　{second}！"),
}


def _rewrite(source, *, changes, language, lines, speaker_names=None):
    index = ("UK", "FR", "GE", "IT", "SP", "JP").index("UK" if language == "US" else language)
    separator = "「" if language == "JP" else ": "
    speaker = speaker_names[index].encode("utf-16-be") if speaker_names else b"\xff\xff\x59"
    prefix = speaker + separator.encode("utf-16-be")
    end = b"\xff\xff\x02\0\0"
    if not source.startswith(prefix) or not source.endswith(end):
        raise FormatError("unexpected Colosseum battle dialogue controls")
    names = dict(zip(("first", "second"), changes.values()))
    return prefix + lines[index].format(**names).encode("utf-16-be") + end


TRAINER_REMARK_REWRITES = {identifier: partial(_rewrite, lines=lines) for identifier, lines in _LINES.items()}
TRAINER_REMARK_REWRITES[0x5AB7] = partial(
    _rewrite,
    speaker_names=("TOTI", "LOLA", "YULIA", "ROSALIA", "LUPE", "ユロ"),
    lines=("So much for my big show!", "Mon spectacle a fait un flop !", "Das war's mit meiner Show!",
           "Spettacolo finito!", "¡Se acabó el espectáculo!", "ショーは　おしまいだね！"),
)


def trainer_dialogue_edits(original, current, game_id, *, trainers_changed, types_changed, moves_changed):
    tables, symbols = layout(original)
    trainers, party, species = (tables[name] for name in ("trainers", "trainer_pokemon", "species"))
    for index, first_slot, identifiers in ((190, 238, (0x3F81,)), (362, 238, (0x405E,)),
                                            (655, 2156, (0x59EE, 0x581A))):
        row = trainers["offset"] + trainers["stride"] * index
        if u16(original, row + 4) != first_slot or not set(identifiers) <= {
            u32(original, row + field) for field in (0x24, 0x28, 0x2C)
        }:
            raise FormatError("unexpected Colosseum trainer dialogue references")
    def name_edits(expected_slots):
        names = {}
        for slot, expected in expected_slots:
            position = party["offset"] + party["stride"] * slot + 0xA
            if u16(original, position) != expected:
                raise FormatError("unexpected Colosseum team for trainer dialogue")
            chosen = u16(current, position)
            original_id = u32(original, species["offset"] + species["stride"] * expected + 0x18)
            names[original_id] = u32(original, species["offset"] + species["stride"] * chosen + 0x18)
        return names

    messages = {}
    if trainers_changed:
        names = name_edits(((2156, 411), (2157, 40)))
        messages.update({0x3F81: {}, 0x405E: {}, 0x581A: names, 0x59EE: names})
    if moves_changed:
        row = trainers["offset"] + trainers["stride"] * 521
        if u32(original, row + 0x24) != 0x3FCB:
            raise FormatError("unexpected Colosseum combo dialogue reference")
        messages[0x3FCB] = {}

    suffixes = ("", "_fr", "_ge", "_it", "_sp") if game_id == "GC6P01" else ("",)
    fight_archives = tuple(f"fight_common{suffix}.fsys" for suffix in suffixes)
    edits = dict.fromkeys(fight_archives + _MOUNT_BATTLE, messages) if messages else {}
    if moves_changed:
        # Toti uses the same introduction for both Pyrite battles. Every
        # original member has a dance move, even on the rematch team.
        keeps_dance = True
        for index, first_slot in ((120, 2352), (121, 4516)):
            row = trainers["offset"] + trainers["stride"] * index
            if u16(original, row + 4) != first_slot or u16(current, row + 4) != first_slot:
                raise FormatError("unexpected Colosseum Toti team")
            if u32(original, row + 0x2C) != 0x5AB7:
                raise FormatError("unexpected Colosseum Toti defeat dialogue")
            for offset, dance in enumerate((349, 80, 14)):
                position = party["offset"] + party["stride"] * (first_slot + offset)
                if dance not in {u16(original, position + field) for field in MOVE_FIELDS}:
                    raise FormatError("unexpected Colosseum Toti moves")
                keeps_dance &= not _DANCE_MOVES.isdisjoint(
                    u16(current, position + field) for field in MOVE_FIELDS
                )
        if not keeps_dance:
            edits["M2_building_3F.fsys"] = {0x5AB6: {}}
            for archive in fight_archives:
                edits[archive] = {**edits.get(archive, {}), 0x5AB7: {}}
    if trainers_changed:
        # The boy in Phenac reenacts Justy's fight before the gym is cleared.
        # His cheer uses Justy's sixth Pokémon, the native Nosepass.
        row = trainers["offset"] + trainers["stride"] * 34
        start = u16(original, row + 4)
        if start != 3536 or u16(current, row + 4) != start:
            raise FormatError("unexpected Colosseum Justy team")
        names = name_edits(((start + 5, 320),))
        if any(old != new for old, new in names.items()):
            edits["M1_out.fsys"] = {0x4E2B: names}
    gym = {}
    for index, expected, identifier in ((20, (191, 187), 0x4E36), (21, (183, 311), 0x4E9B)):
        row = trainers["offset"] + trainers["stride"] * index
        start = u16(original, row + 4)
        names = name_edits(zip(range(start, start + 2), expected, strict=True))
        if types_changed or any(old != new for old, new in names.items()):
            gym[identifier] = dict(list(names.items())[:1])
    if gym:
        edits["M1_gym_1F.fsys"] = gym
    return edits, localized_names(original, symbols)[0] if edits else {}
