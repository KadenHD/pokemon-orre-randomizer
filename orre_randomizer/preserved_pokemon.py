"""Shared preservation rules for retained encounters and species-wide data."""
from __future__ import annotations

def preserve_properties(options):
    return hasattr(options, "randomize_preserved_properties") and not options.randomize_preserved_properties


def colosseum_species(original, tables, options):
    """Protect native species families without selecting any replacements."""
    if not preserve_properties(options):
        return frozenset()
    from .engine.inspect_tables import u16
    from .engine.postgame_boss import DEFAULT_TEAM, LUGIA
    from .engine.randomize_story import SPECIALS
    from .engine.species_rules import LEGENDARY_NATIONAL
    from .options import SPECIAL_OPTIONS
    species = tables["species"]
    result = set()
    for target in SPECIALS:
        switch = SPECIAL_OPTIONS[target["key"]]
        if not getattr(options, switch):
            result.add(target["old"])
    if "shadow" in tables:
        shadow = tables["shadow"]
        for sid in range(1, shadow["count"]):
            index = u16(original, shadow["offset"] + sid * shadow["stride"] + 2)
            if index and (not options.randomize_shadows or not options.randomize_legendary_shadows
                          and u16(original, species["offset"] + index * species["stride"] + 0x10) in LEGENDARY_NATIONAL):
                result.add(index)
    if options.postgame_shadow_lugia:
        if not options.postgame_randomize_team:
            result.update(DEFAULT_TEAM)
        if not options.postgame_randomize_lugia:
            result.add(LUGIA)
    if not options.randomize_trainers and "trainer_pokemon" in tables and "trainers" in tables:
        party = tables["trainer_pokemon"]
        trainers = tables["trainers"]
        active = set()
        for index in range(trainers["count"]):
            start = u16(original, trainers["offset"] + index * trainers["stride"] + 4)
            if start:
                active.update(range(start, start + 6))
        for index in active:
            pos = party["offset"] + index * party["stride"]
            if not original[pos + 3]:
                result.add(u16(original, pos + 0xA))
    from .engine.evolution_rules import evolution_families
    families = evolution_families(original, tables)[0]
    retained = {families[index] for index in result if index in families}
    return frozenset(index for index, family in families.items() if family in retained)


def xd_species(options, story=None, *, families=None):
    if not preserve_properties(options):
        return frozenset()
    from .xd_preview import baseline_rows
    baseline = baseline_rows(options)
    rows = [baseline["starter"], *baseline["decks"]["Story"]["shadows"],
            *baseline["gifts"], *baseline["poke_spots"]]
    result = {row["species"] for row in rows if row.get("species")}
    if story is not None and not options.randomize_trainers:
        from .engine.analyze_game import u32
        from .engine.inspect_tables import u16
        header = 0x10 + u32(story, 0x14)
        start = header + 0x10
        trainers = u32(story, 0x18)
        for trainer in range(trainers):
            pos = 0x20 + trainer * 0x38
            for slot in range(6):
                index = u16(story, pos + 0x1C + slot * 2)
                if index and not story[pos + 4] & (1 << slot):
                    result.add(u16(story, start + index * 0x20))
    if families is not None:
        retained = {families[index] for index in result if index in families}
        return frozenset(index for index, family in families.items() if family in retained)
    return frozenset(result - {0})


def colosseum_encounter_kept(original, pos, options):
    if not preserve_properties(options):
        return False
    sid = original[pos + 3]
    if not sid:
        return not options.randomize_trainers
    # The three native legendary encounters are Entei, Suicune and Raikou.
    # Shadow identities remain stable across all supported regions.
    return not options.randomize_shadows or (not options.randomize_legendary_shadows
                                             and sid in (21, 23, 34))
