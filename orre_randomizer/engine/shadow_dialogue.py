"""Colosseum field dialogue and mail tied to specific Shadow encounters."""
from .analyze_game import FormatError
from .inspect_tables import localized_names, u16, u32
from .randomize_trainers import layout


# Keys in each row are the original National Pokédex numbers, independent of
# the order in which an individual localization lists the Shadow Pokémon.
_FIELD = {
    "M2_out.fsys": {
        0x4284: (153,), 0x44CC: (156,), 0x44CD: (159,),
    },
    "M4_out.fsys": {
        0x42B8: (156,), 0x42BA: (153,), 0x42BE: (159,),
    },
    "D4_tower_1F_2.fsys": {
        **dict.fromkeys((0x54FB, 0x56DD, 0x56E0, 0x56E1), (156,)),
        **dict.fromkeys((0x56E2, 0x56E3, 0x56E6, 0x56E7), (153,)),
        **dict.fromkeys((0x56E8, 0x56E9, 0x56EC, 0x56ED), (159,)),
    },
    "S2_building_1F_2.fsys": {0x5BF2: (235,), 0x5BF3: (235,)},
    "S2_building_2F_2.fsys": {0x5C08: (227,)},
}
_MAIL = {
    0x3EAA: (153,),
    0x3EC9: (235, 217),
    0x3ECC: (213,), 0x3ED0: (213,),
    0x3EEE: (248, 200, 218, 235, 359, 214),
    0x3EF0: (217, 188, 195, 357, 227, 192),
    0x3EF2: (164, 180, 229, 213, 241, 225),
    0x3EF3: (176,), 0x3EF4: (176,), 0x3F07: (176,),
    0x3EFD: (153,), 0x3F0A: (153,), 0x3F2C: (156,), 0x3F2D: (159,),
    0x3F31: (156,), 0x3F32: (159,),
    0x3F33: (156,), 0x3F34: (159,),
}
_JAPANESE_MAIL = {
    0x3EA2: (329,), 0x3EB0: (192,), 0x3EB2: (329,), 0x3EB4: (329,),
    0x3EC3: (237,), 0x3ED1: (237,), 0x3EDA: (237,),
    0x3EDE: (235,), 0x3EE0: (359,),
    0x3EF5: (188, 195, 192, 162, 218),
    0x3EF6: (168, 166, 213, 200, 359),
    0x3EF7: (237, 223, 226, 307),
    0x3EF8: (333, 235, 207, 234, 198),
    0x3EFE: (211,), 0x3EFF: (206,), 0x3F01: (229,),
    0x3F05: (221, 205, 210, 215), 0x3F06: (214,),
    0x3F0B: (211,), 0x3F0C: (206,), 0x3F0D: (229,), 0x3F0E: (229,),
    0x3F11: (193,), 0x3F12: (190,), 0x3F13: (190,), 0x3F1A: (193,),
    **dict.fromkeys((0x3F1C, 0x3F1E, 0x3F1F, 0x3F21, 0x3F23, 0x3F27), (190,)),
    0x3F20: (237,), 0x3F2A: (235,),
    0x416C: (329,), 0x4174: (329,),
    0x418E: (190,), 0x4193: (190,), 0x41B0: (229,),
    **dict.fromkeys((0x41BD, 0x41CB, 0x41D1, 0x41D8), (190,)),
    0x41E3: (192,),
}

_SMEARGLE_INTRO = {
    "UK": "I thought I'd win with my {name}...",
    "FR": "Je pensais gagner avec mon {name}…",
    "GE": "Ich wollte mit {name} gewinnen…",
    "IT": "Pensavo di vincere con {name}…",
    "SP": "Creía que ganaría con mi {name}…",
    "JP": "{name}と　かつつもりだったのに……。",
}
_SMEARGLE_DEFEAT = {
    "UK": "But you sure showed us!",
    "FR": "Mais tu nous as bien eus !",
    "GE": "Aber du hast es uns gezeigt!",
    "IT": "Invece ci hai battuti!",
    "SP": "¡Pero nos ganaste tú!",
}


def _rewrite_smeargle(source, *, changes, language):
    # The second page in Japanese refers to the actual Snag. Western versions
    # continue the original painting joke, which only works with Smeargle.
    speaker = b"\xff\xff\x59"
    page = b"\xff\xff\x03"
    end = b"\xff\xff\x02\0\0"
    first, separator, rest = source.partition(page)
    if not first.startswith(speaker) or not source.endswith(end):
        raise FormatError("unexpected Colosseum Smeargle dialogue controls")
    locale = "UK" if language == "US" else language
    prefix = "「" if locale == "JP" else ": "
    name, = changes.values()
    intro = speaker + (prefix + _SMEARGLE_INTRO[locale].format(name=name)).encode("utf-16-be")
    if not separator:
        return intro + end
    if locale != "JP":
        rest = speaker + (prefix + _SMEARGLE_DEFEAT[locale]).encode("utf-16-be") + end
    return intro + page + rest


SHADOW_REMARK_REWRITES = dict.fromkeys((0x5BF2, 0x5BF3), _rewrite_smeargle)


def shadow_dialogue_edits(original: bytes, current: bytes, game_id: str):
    """Prepare message edits from the final Shadow table, after all trainer rules."""
    tables, symbols = layout(original)
    species = tables["species"]
    shadow = tables["shadow"]

    def species_position(index):
        return species["offset"] + species["stride"] * index

    mail = {**_MAIL, **_JAPANESE_MAIL} if game_id == "GC6J01" else _MAIL
    referenced = {national for messages in (*_FIELD.values(), mail)
                  for nationals in messages.values() for national in nationals}
    replacements = {}
    for index in range(1, shadow["count"]):
        pos = shadow["offset"] + shadow["stride"] * index + 2
        old, new = u16(original, pos), u16(current, pos)
        if not old:
            continue
        national = u16(original, species_position(old) + 0x10)
        if national not in referenced:
            continue
        change = (u32(original, species_position(old) + 0x18), u32(original, species_position(new) + 0x18))
        if national in replacements and replacements[national] != change:
            raise FormatError("ambiguous species in Colosseum Shadow dialogue")
        replacements[national] = change
    suffixes = ("", "_fr", "_ge", "_it", "_sp") if game_id == "GC6P01" else ("",)
    targets = {**_FIELD, **{f"pda_menu{suffix}.fsys": mail for suffix in suffixes}}
    edits = {}
    for archive, messages in targets.items():
        for identifier, nationals in messages.items():
            changes = {old: new for old, new in (replacements[n] for n in nationals) if old != new}
            if changes:
                edits.setdefault(archive, {})[identifier] = changes
    return edits, localized_names(original, symbols)[0] if edits else {}
