"""Seeded transformations for the three verified retail Pokémon XD discs."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field, fields, replace
from itertools import permutations
from pathlib import Path
import struct

from .engine.analyze_game import FormatError, check_range, parse_fsys, parse_rel, u32
from .engine.inspect_tables import localized_names, rel_symbols, u16
from .engine.message_bank import patch_species_archive
from .engine.pool_filters import allowed_replacement
from .engine.randomize_story import experience_at_level
from .engine.randomize_trainers import choose_species
from .engine.rebuild_iso import align, decoded_member, repack_fsys
from .engine.regions import DISC_SIZE, Region
from .engine.shadow_boss_rules import _match_families, _power_preference
from .engine.species_rules import LEGENDARY_NATIONAL
from .engine.survey_assets import fst_inventory
from .options import Options, rule, setting
from .xd_battle_rules import (apply_deck_rules, apply_dol_battle_rules, apply_shadow_rules,
                              boss_shadows, deck_rules_active, shadow_rules_active)
from .xd_gifts import (DUKING_TRADES, GIFT_BASELINES, GIFT_TRADE_REQUIREMENTS, HORDEL_SHADOW,
                       TOGEPI, patch_gifts, patch_hordel_gift)
from .xd_item_rules import apply_field_items, apply_shop_items
from .xd_shiny_rules import apply_shiny_rules
from .xd_shadow_shinies import apply_shadow_shiny_rules
from .xd_field_actors import GATEON_SHADOW, patch_gateon_shadow, patch_lighthouse_dancers, patch_wakin_partner
from .xd_poke_spot_actors import patch_poke_spot_actors
from .xd_shops import patch_stone_names, patch_stone_price, patch_stone_stock
from .xd_species_gameplay import XDMoveRandomizer, detail_catalog, patch_species_gameplay, patch_tm_gameplay
from .xd_story import (DRAGONITE_DIALOGUE, STARTER_DIALOGUE_ARCHIVE, STARTER_ITEM_DIALOGUE, TEDDIURSA,
                       TRAINER_REMARK_REWRITES, patch_eagun_actor,
                       TUTORIAL_SHADOW, hordel_candidates,
                       patch_starter_dialogue, patch_tutorial, trainer_dialogue_edits, tutorial_candidates)

VERSION = "xd-story-sha256-v9"
DRAW_VERSION = "xd-story-sha256-v1"
REGIONS = {
    "GXXP01": Region("GXXP01", "Europe",
                    "1cc438ed60e542991b8f1abea4617e67880f2568aceb513602051ca6f310e8c1",
                    4_573_440, ("en", "de", "fr", "it", "es")),
    "GXXE01": Region("GXXE01", "USA",
                    "806a962155560d191435f7ba670bfb3471404c04f3494ad1a02d833508bf482f",
                    4_333_056, ("en",)),
    "GXXJ01": Region("GXXJ01", "Japan",
                    "4a77d6d25292bc97ba18502296415d9297e7138d61e19e2512d0a26d57f90ae2",
                    4_191_488, ("ja",)),
}
STARTERS = {"GXXP01": 0x1CD724, "GXXE01": 0x1CBC50, "GXXJ01": 0x1C6AF4}
DECKS = ("Story", "Colosseum", "Hundred")
# Tutorial Teddiursa, Shadow Lugia, and the in-game Togepi trade.
PROTECTED_SHADOWS = {TUTORIAL_SHADOW: TEDDIURSA, 73: 249, HORDEL_SHADOW: TOGEPI}
SPOT_SPECIES = {"rock": (27, 207, 332), "oasis": (187, 231, 311), "cave": (41, 382, 194)}
STARTER_ATTACKS = {1, 10, 16, 17, 22, 33, 40, 41, 52, 55, 64, 71, 84, 93, 98, 122, 145, 181, 189, 301, 310}
NATIVE_STARTER_MOVES = (33, 39, 44, 28)
COMMON_FIELDS = {item.name: item for item in fields(Options)}


def _shared(name, **overrides):
    source = COMMON_FIELDS[name]
    return field(default=overrides.pop("default", source.default), metadata={**source.metadata, **overrides})


@dataclass(frozen=True, slots=True)
class XDOptions:
    randomize_starter: bool = _shared("starter_umbreon")
    randomize_trainers: bool = _shared("randomize_trainers")
    randomize_shadows: bool = _shared("randomize_shadows", description=
        "Change les obscurs ordinaires. Le premier obscur a son propre réglage.")
    randomize_tutorial_shadow: bool = rule("Remplacer Teddiursa dans le tutoriel", "Dresseurs",
        "Adapte les dialogues au premier obscur. Il garde le niveau 11 et son taux de capture d’origine.", False)
    randomize_poke_spots: bool = rule("Randomiser les Poké Places", "Poké Places",
        "Change les rencontres des Poké Places. Doking demande le Pokémon de l’emplacement rare de chaque lieu.")
    poke_spots_full_pokedex: bool = rule("Piocher dans tout le Pokédex", "Poké Places",
        "Utilise tous les Pokémon autorisés par vos filtres. Désactivé : mélange les trois espèces d’origine de chaque lieu.", False)
    accessible_evolutions: bool = rule("Rendre les évolutions accessibles", "Évolutions",
        "Adapte les évolutions par échange et les conditions impossibles à réaliser dans le jeu. Les évolutions propres à XD, dont celles d’Évoli, sont conservées.")
    unique_shadow_families: bool = _shared("unique_shadows")
    randomize_gifts: bool = rule("Remplacer les Pokémon offerts", "Starters et cadeaux",
        "Change les espèces des Pokémon offerts, en gardant leurs niveaux. Le Togepi obscur a son propre réglage.")
    randomize_hordel_gift: bool = rule("Remplacer le Togepi obscur", "Starters et cadeaux",
        "Le Pokémon offert peut être échangé après purification, même s’il a évolué.", False)
    stone_shops: bool = _shared("stones_phenac", label="Ajouter les pierres d’évolution en boutique")
    starter_species: int = _shared("starter_umbreon_species", description=
        "Tirage avec la seed, ou Pokémon choisi. Un choix manuel remplace les filtres de stade et de puissance individuelle ; les exclusions restent appliquées.")
    starter_stage: str = _shared("starter_stage")
    starter_three_stage_families: bool = _shared("starter_three_stage_families")
    diverse_story_families: bool = _shared("diverse_story_families", default=True)
    balance_species: bool = _shared("balance_species", default=True)
    allow_gen1: bool = _shared("allow_gen1")
    allow_gen2: bool = _shared("allow_gen2")
    allow_gen3: bool = _shared("allow_gen3")
    allow_legendaries: bool = _shared("allow_legendaries")
    excluded_species: tuple[int, ...] = _shared("excluded_species")
    excluded_types: tuple[int, ...] = _shared("excluded_types")
    custom_shinies: bool = _shared("custom_shinies", description=
        "La seed fixe le statut chromatique du starter, des cadeaux et, si activé, des obscurs. Les Poké Places gardent le taux d’origine.")
    custom_shadow_shinies: bool = rule("Appliquer le taux aux Pokémon obscurs", "Chromatiques",
        "Lève le verrouillage de XD. La seed fixe le statut de chaque obscur, conservé après capture et purification. Les Pokémon déjà générés restent inchangés.", False)
    shiny_chance_percent: float = _shared("shiny_chance_percent", default=5.0,
                                         description="La seed fixe le statut chromatique du starter, des cadeaux et, si activé, des obscurs. Les Poké Places gardent le taux d’origine.")
    trainer_theme_mode: str = _shared("trainer_theme_mode")
    trainer_force_evolved: bool = _shared("trainer_force_evolved")
    trainer_evolution_level: int = _shared("trainer_evolution_level")
    randomize_trainer_moves: bool = _shared("randomize_trainer_moves")
    randomize_starter_moves: bool = _shared("randomize_starter_moves")
    randomize_gift_moves: bool = _shared("randomize_gift_moves")
    randomize_learnsets: bool = _shared("randomize_learnsets")
    ensure_damaging_move: bool = _shared("ensure_damaging_move")
    ensure_stab_move: bool = _shared("ensure_stab_move")
    no_duplicate_moves: bool = _shared("no_duplicate_moves")
    ban_self_destruct: bool = _shared("ban_self_destruct")
    ban_ohko: bool = _shared("ban_ohko")
    moves_mode: str = _shared("moves_mode")
    randomize_abilities: bool = _shared("randomize_abilities")
    abilities_family_consistent: bool = _shared("abilities_family_consistent")
    randomize_stats: bool = _shared("randomize_stats")
    preserve_stat_totals: bool = _shared("preserve_stat_totals")
    randomize_types: bool = _shared("randomize_types")
    types_family_consistent: bool = _shared("types_family_consistent")
    randomize_held_items: bool = _shared("randomize_held_items")
    useful_held_items_only: bool = _shared("useful_held_items_only")
    trainer_level_multiplier: float = _shared("trainer_level_multiplier")
    progressive_levels: bool = _shared("progressive_levels")
    early_level_multiplier: float = _shared("early_level_multiplier")
    mid_level_multiplier: float = _shared("mid_level_multiplier")
    late_level_multiplier: float = _shared("late_level_multiplier")
    capture_rate_multiplier: float = _shared("capture_rate_multiplier")
    minimum_catch_rate: int = _shared("minimum_catch_rate")
    experience_multiplier: float = _shared("experience_multiplier")
    purification_multiplier: int = _shared("purification_multiplier", description=
        "Multiplie les diminutions de la jauge obscure. ×1 conserve le jeu d’origine ; la purification finale reste nécessaire.")
    randomize_tm_moves: bool = _shared("randomize_tm_moves")
    tm_compatibility_mode: str = _shared("tm_compatibility_mode")
    tm_ensure_offensive: bool = _shared("tm_ensure_offensive")
    randomize_field_items: bool = _shared("randomize_field_items")
    randomize_shop_items: bool = _shared("randomize_shop_items", description=
        "Change les objets des boutiques prises en charge. Les autres listes, les monnaies spéciales et les pierres restent inchangées.")
    shop_keep_healing: bool = _shared("shop_keep_healing")
    items_similar_value: bool = _shared("items_similar_value")
    keep_capture_items: bool = _shared("keep_capture_items")
    boss_stronger: bool = _shared("boss_stronger")
    boss_team_variety: bool = _shared("boss_team_variety")
    boss_shadow_legendary_mode: str = _shared("boss_shadow_legendary_mode")
    boss_shadow_power_mode: str = _shared("boss_shadow_power_mode")
    boss_shadow_min_bst: int = _shared("boss_shadow_min_bst")

    @classmethod
    def unchanged(cls) -> XDOptions:
        return cls(**{item.name: False for item in fields(cls) if item.metadata["kind"] == "bool"})

    @classmethod
    def recommended(cls) -> XDOptions:
        return cls(randomize_trainer_moves=True, randomize_starter_moves=True, randomize_gift_moves=True,
                   randomize_learnsets=True, randomize_tm_moves=True, tm_compatibility_mode="type",
                   randomize_field_items=True, randomize_shop_items=True, custom_shinies=True,
                   boss_team_variety=True, randomize_tutorial_shadow=True,
                   poke_spots_full_pokedex=True, custom_shadow_shinies=True,
                   randomize_hordel_gift=True)

    @classmethod
    def species_only(cls) -> XDOptions:
        from .presets import without_moves_and_items

        return without_moves_and_items(cls.recommended())


def validate_options(options: XDOptions) -> XDOptions:
    from .service import UserError, validate_setting_values

    options = validate_setting_values(options)
    if any((options.randomize_starter, options.randomize_trainers, options.randomize_shadows,
            options.randomize_gifts, options.randomize_poke_spots, options.randomize_tutorial_shadow,
            options.randomize_hordel_gift,
            options.trainer_force_evolved,
            options.boss_team_variety)) and not any(
                (options.allow_gen1, options.allow_gen2, options.allow_gen3)):
        raise UserError("Activez au moins une génération dans « Pokémon autorisés ».")
    if options.accessible_evolutions and not options.stone_shops:
        raise UserError("Activez la vente de pierres dans « Boutiques », ou désactivez les évolutions par pierre.")
    if options.randomize_shadows and options.boss_shadow_legendary_mode == "preserve" and not options.allow_legendaries:
        raise UserError("Pour garder le statut légendaire des obscurs de boss, autorisez les légendaires dans « Pokémon autorisés ».")
    if not options.randomize_shadows and options.unique_shadow_families:
        return replace(options, unique_shadow_families=False)
    return options


def region_for_boot(boot: bytes) -> Region:
    if (len(boot) < 0x440 or boot[6:8] != b"\0\0"
            or boot[0x1C:0x20] != bytes.fromhex("c2339f3d")):
        raise FormatError("unsupported XD disc header or revision")
    region = REGIONS.get(boot[:6].decode("ascii", errors="replace"))
    if region is None:
        raise FormatError("unsupported XD disc identifier")
    return region


def _table(rel: bytes, symbols: list[dict], index: int, count: int, stride: int) -> int:
    start = symbols[index]["offset"]
    if u32(rel, symbols[index + 1]["offset"]) != count:
        raise FormatError(f"unexpected XD table count at symbol {index}")
    check_range(rel, start, count * stride, "XD table")
    return start


def _species(rel: bytes, symbols: list[dict]):
    table = _table(rel, symbols, 88, 415, 0x124)
    species = {}
    edges = defaultdict(list)
    families = {}
    for index in range(415):
        position = table + index * 0x124
        national = u16(rel, position + 0xE)
        if not 1 <= national <= 386:
            continue
        species[index] = (
            national, rel[position], sum(rel[position + 0x8F:position + 0x9A:2]),
            tuple((rel[pos], u16(rel, pos + 2)) for pos in
                  range(position + 0xC4, position + 0xC4 + 19 * 4, 4)),
        )
        families[index] = index
    if {row[0] for row in species.values()} != set(range(1, 387)) or len(species) != 386:
        raise FormatError("unexpected XD species catalogue")

    def root(index):
        while families[index] != index:
            index = families[index]
        return index

    for index in species:
        for slot in range(5):
            position = table + index * 0x124 + 0xA6 + 6 * slot
            method, _, condition, target = struct.unpack_from(">BBHH", rel, position)
            if not method:
                continue
            if method > 16 or target not in species:
                raise FormatError("invalid XD evolution")
            edges[index].append((position, method, condition, target))
            first, second = sorted((root(index), root(target)))
            families[second] = first
    return species, edges, {index: root(index) for index in species}


def _pick(seed, key, species, original, *, candidates=None, balance=True):
    pool = sorted(species if candidates is None else candidates)
    pool = [index for index in pool if index != original]
    if not pool:
        raise FormatError("Aucun Pokémon admissible avec ces filtres. Autorisez d’autres espèces ou types.")
    if balance:
        # Draw among the closest base-stat totals so low-level tutorial teams
        # cannot randomly become a wall of high-stat Pokémon.
        total = species[original][2]
        pool = sorted(pool, key=lambda index: (abs(species[index][2] - total), index))[:40]
        pool.sort()
    return choose_species(seed, f"{DRAW_VERSION}:{key}", pool, original)


def _starter(dol: bytes, offset: int, seed: str, species, edges, families, eligible,
             options, move_randomizer) -> tuple[bytes, dict]:
    offsets = (0, 8, 0x10, 0x14, 0x18, 0x1C, 0x64)
    signature = (0x38600085, 0x3900000A, 0x38C00021, 0x38A00027, 0x3880002C, 0x3800001C, 0x380004E2)
    if tuple(u32(dol, offset + field) for field in offsets) != signature:
        raise FormatError("unexpected XD starter instructions")
    chosen, moves = 133, list(NATIVE_STARTER_MOVES)
    if options.randomize_starter:
        targets = {edge[3] for routes in edges.values() for edge in routes}
        roots = set(species) - targets
        first = {edge[3] for index in roots for edge in edges.get(index, ())}
        stage_pool = {"any": set(species), "base": roots, "first": first,
                      "final": targets - edges.keys()}[options.starter_stage]
        three_stage = {families[index] for index in roots
                       if any(edges.get(edge[3]) for edge in edges.get(index, ()))}
        candidates = [
            index for index in sorted(stage_pool & eligible)
            if (not options.starter_three_stage_families or families[index] in three_stage)
            and (options.randomize_starter_moves
                 or any(0 < level <= 10 and move in STARTER_ATTACKS for level, move in species[index][3]))
            and (not options.diverse_story_families
                 or families[index] not in {families[native] for native in PROTECTED_SHADOWS.values()})
        ]
        if options.starter_species:
            chosen = next((index for index in eligible if species[index][0] == options.starter_species), None)
            if chosen is None:
                raise FormatError("the selected XD starter is excluded")
            if not options.randomize_starter_moves and not any(
                0 < level <= 10 and move in STARTER_ATTACKS for level, move in species[chosen][3]
            ):
                raise FormatError("the selected XD starter needs randomized starting moves")
        else:
            chosen = _pick(seed, "starter", species, 133, candidates=candidates, balance=False)
        if not options.randomize_starter_moves:
            moves = list(dict.fromkeys(
                move for level, move in species[chosen][3] if 0 < level <= 10 and 0 < move <= 354
            ))[-4:]
            if not set(moves) & STARTER_ATTACKS:
                moves[0] = next(move for level, move in species[chosen][3] if 0 < level <= 10 and move in STARTER_ATTACKS)
    if options.randomize_starter_moves:
        moves = move_randomizer.moves(seed, "xd:starter", chosen, 10, NATIVE_STARTER_MOVES)
    experience = (experience_at_level(species[chosen][1], 10) if chosen != 133 else u16(dol, offset + 0x66))
    result = bytearray(dol)
    struct.pack_into(">H", result, offset + 2, chosen)
    for i, move in enumerate((moves + [0] * 4)[:4]):
        struct.pack_into(">H", result, offset + 0x12 + 4 * i, move)
    struct.pack_into(">H", result, offset + 0x66, experience)
    return bytes(result), {"original": 133, "species": chosen, "level": 10,
                           "experience": experience, "moves": moves}


def _shadow_slots(dark: bytes) -> dict[int, int]:
    if (dark[0x10:0x14] != b"DDPK" or u32(dark, 0x18) != 128
            or len(dark) != 0x20 + 128 * 0x18):
        raise FormatError("unexpected XD Shadow deck")
    result = {index: u16(dark, 0x20 + index * 0x18 + 6) for index in range(1, 84)}
    if not all(result.values()) or len(set(result.values())) != len(result):
        raise FormatError("invalid XD Shadow deck links")
    return result


def _boss_shadow_picks(deck, originals, seed, species, families, eligible, reserved, options, fixed_shadows):
    bosses = boss_shadows(deck)
    if not bosses <= originals.keys():
        raise FormatError("unexpected XD boss Shadow reference")
    protected = {families[index] for index in fixed_shadows.values()}
    catalog = {index: {"total": row[2]} for index, row in species.items()}
    hard, preferred, balanced = {}, {}, {}
    for sid, old in originals.items():
        if sid in fixed_shadows:
            continue
        pool = [index for index in sorted(eligible) if index != old and index not in fixed_shadows.values()
                and (not options.unique_shadow_families or families[index] not in protected)]
        legendary = options.boss_shadow_legendary_mode
        power = options.boss_shadow_power_mode
        if sid in bosses:
            pool = [index for index in pool if species[index][2] >= options.boss_shadow_min_bst
                    and (legendary != "exclude" or species[index][0] not in LEGENDARY_NATIONAL)
                    and (legendary != "preserve" or (species[index][0] in LEGENDARY_NATIONAL)
                         == (species[old][0] in LEGENDARY_NATIONAL))]
        if not pool:
            raise FormatError("Aucun Pokémon admissible avec ces filtres. Autorisez d’autres espèces ou types.")
        hard[sid] = pool
        if options.diverse_story_families:
            pool = [index for index in pool if families[index] not in reserved] or pool
        if sid in bosses and power == "similar":
            pool = _power_preference(pool, old, catalog)
        preferred[sid] = pool
        balanced[sid] = (power == "similar" or (power == "global" and options.balance_species)
                         if sid in bosses else options.balance_species)
    selected = preferred
    if options.unique_shadow_families:
        assignments = _match_families(seed, preferred, families, catalog, originals, balanced, bosses)
        if assignments is None:
            assignments = _match_families(seed, hard, families, catalog, originals, balanced, bosses)
            selected = hard
        if assignments is None:
            raise FormatError("Il manque des familles pour les Pokémon obscurs. Élargissez les filtres ou autorisez les doublons.")
        selected = {sid: [index for index in pool if families[index] == assignments[sid]]
                    for sid, pool in selected.items()}
    return {sid: _pick(seed, f"shadow:{sid}", species, originals[sid], candidates=pool, balance=balanced[sid])
            for sid, pool in selected.items()}


def _deck(deck: bytes, name: str, shadow_slots, seed: str, species, families,
          reserved_families: set[int], options: XDOptions, eligible=None, *,
          fixed_shadows=PROTECTED_SHADOWS) -> tuple[bytes, dict]:
    eligible = species if eligible is None else eligible
    pokemon_header = 0x10 + u32(deck, 0x14)
    trainers, count = u32(deck, 0x18), u32(deck, pokemon_header + 8)
    start = pokemon_header + 0x10
    if (deck[0x10:0x14] != b"DTNR" or deck[pokemon_header:pokemon_header + 4] != b"DPKM"
            or pokemon_header != 0x20 + trainers * 0x38
            or u32(deck, pokemon_header + 4) != 0x10 + count * 0x20):
        raise FormatError("unexpected XD trainer deck")
    check_range(deck, start, count * 0x20, "XD DPKM records")
    regular, shadows = set(), set()
    for trainer in range(trainers):
        row = 0x20 + trainer * 0x38
        mask = deck[row + 4]
        for slot in range(6):
            index = u16(deck, row + 0x1C + 2 * slot)
            if index:
                (shadows if mask & (1 << slot) else regular).add(index)
    if shadows != set(shadow_slots) or regular & set(shadow_slots.values()):
        raise FormatError("inconsistent XD deck links")
    if any(not 0 < index < count or u16(deck, start + index * 0x20) not in species
           for index in regular | set(shadow_slots.values())):
        raise FormatError("invalid XD trainer species or slot")
    result = bytearray(deck)
    if options.randomize_trainers:
        for index in sorted(regular):
            position = start + index * 0x20
            chosen = _pick(seed, f"{name}:trainer:{index}", species, u16(deck, position),
                           candidates=eligible, balance=options.balance_species)
            struct.pack_into(">H", result, position, chosen)
    shadow_report = []
    if shadow_slots:
        for sid, original in PROTECTED_SHADOWS.items():
            if u16(deck, start + shadow_slots[sid] * 0x20) != original:
                raise FormatError("unexpected scripted XD Shadow species")
        used = {families[index] for index in fixed_shadows.values()}
        boss_picks = {}
        if options.randomize_shadows and (options.boss_shadow_legendary_mode, options.boss_shadow_power_mode,
                                          options.boss_shadow_min_bst) != ("any", "global", 0):
            originals = {sid: u16(deck, start + index * 0x20) for sid, index in shadow_slots.items()}
            boss_picks = _boss_shadow_picks(deck, originals, seed, species, families, eligible,
                                            reserved_families, options, fixed_shadows)
        for sid, index in sorted(shadow_slots.items()):
            position = start + index * 0x20
            original = chosen = u16(deck, position)
            if sid in fixed_shadows:
                chosen = fixed_shadows[sid]
                struct.pack_into(">H", result, position, chosen)
            elif sid in boss_picks:
                chosen = boss_picks[sid]
                struct.pack_into(">H", result, position, chosen)
            elif options.randomize_shadows:
                candidates = [species_id for species_id in eligible
                              if species_id not in fixed_shadows.values()
                              and (not options.unique_shadow_families or families[species_id] not in used)]
                preferred = [index for index in candidates if index != original and families[index] not in reserved_families]
                if options.diverse_story_families and preferred:
                    candidates = preferred
                if options.unique_shadow_families and not any(candidate != original for candidate in candidates):
                    raise FormatError("Il manque des familles pour les Pokémon obscurs. Élargissez les filtres ou autorisez les doublons.")
                chosen = _pick(seed, f"shadow:{sid}", species, original, candidates=candidates,
                               balance=options.balance_species)
                used.add(families[chosen])
                struct.pack_into(">H", result, position, chosen)
            shadow_report.append({"shadow_id": sid, "original": original, "species": chosen,
                                  "level": deck[position + 2], "family": families[chosen]})
    return bytes(result), {"trainer_changes": len(regular) if options.randomize_trainers else 0,
                           "shadows": shadow_report}


def _poke_spot_species(seed, species, eligible, options):
    """Draw rare slots first so Duking always has three distinct requests."""
    pool = set(eligible) & species.keys()
    if len(pool) < 3:
        raise FormatError("Autorisez au moins trois Pokémon pour randomiser les Poké Places.")
    picks = {spot: [None, None, None] for spot in SPOT_SPECIES}
    used, rare = set(), set()
    for slot in (2, 0, 1):
        for spot, native in SPOT_SPECIES.items():
            candidates = pool - set(picks[spot])
            if slot == 2:
                candidates -= rare
            candidates = candidates - used or candidates
            original = native[slot]
            chosen = (original if candidates == {original} else
                      _pick(seed, f"poke-spot-species-v1:{spot}:{slot + 1}", species,
                            original, candidates=candidates, balance=options.balance_species))
            picks[spot][slot] = chosen
            used.add(chosen)
            if slot == 2:
                rare.add(chosen)
    return picks


def _rel(rel, seed, species, edges, symbols, options, eligible=None):
    result = bytearray(rel)
    spots, evolutions = [], []
    eligible = species if eligible is None else eligible
    full_draw = (_poke_spot_species(seed, species, eligible, options)
                 if options.randomize_poke_spots and options.poke_spots_full_pokedex else None)
    for spot, symbol in (("rock", 12), ("oasis", 15), ("cave", 18)):
        start = _table(rel, symbols, symbol, 3, 0xC)
        native = tuple(u16(rel, start + slot * 0xC + 2) for slot in range(3))
        if native != SPOT_SPECIES[spot] or any(index not in species for index in native):
            raise FormatError("unexpected native XD Poké Spot roster")
        picked = native
        if full_draw is not None:
            picked = full_draw[spot]
        elif options.randomize_poke_spots:
            supported = [order for order in permutations(native) if order[2] != native[2]
                         and all(old == new or new in eligible for old, new in zip(native, order, strict=True))]
            if supported:
                choice = choose_species(seed, f"xd-poke-spot-permutation-v1:{spot}", range(len(supported)), -1)
                picked = supported[choice]
        for slot, (original, chosen) in enumerate(zip(native, picked, strict=True)):
            position = start + slot * 0xC
            struct.pack_into(">H", result, position + 2, chosen)
            spots.append({"spot": spot, "slot": slot + 1, "original": original, "species": chosen,
                          "levels": [rel[position], rel[position + 1]], "chance": rel[position + 7]})
    if options.accessible_evolutions:
        # Branching species retain different triggers. XD's own key-item
        # evolutions (notably Eevee) are outside this whitelist.
        stones = {199: 97, 374: 95, 375: 98}
        for source, routes in sorted(edges.items()):
            for position, method, old, target in routes:
                if method not in (5, 6, 15):
                    continue
                new_method, condition = (7, stones[target]) if target in stones else (4, 40)
                result[position] = new_method
                struct.pack_into(">H", result, position + 2, condition)
                evolutions.append({"species": source, "target": target, "old_method": method,
                                   "old_condition": old, "method": new_method, "condition": condition})
    return bytes(result), spots, evolutions


def _member(archive, members, name):
    member = members.get(name)
    if member is None:
        raise FormatError(f"missing XD FSYS member {name}")
    return member["index"], decoded_member(archive, member)


def build_patches(iso: Path, boot: bytes, seed: str, options: XDOptions, progress, cancel, *, include_details=False):
    # Use the same bounded ISO reader and cancellation scope as Colosseum.
    from .service import checkpoint, read_exact

    options = validate_options(options)
    region = region_for_boot(boot)
    if options == XDOptions.unchanged() and not include_details:
        return [], {}
    dol_offset, fst_offset, fst_size, fst_max = (u32(boot, pos) for pos in range(0x420, 0x430, 4))
    with iso.open("rb") as stream:
        fst = bytearray(read_exact(stream, fst_offset, fst_size))
        files, _ = fst_inventory(fst)
        entries = {entry["path"]: entry for entry in files}
        dol = read_exact(stream, dol_offset, region.dol_size)
        app_header = read_exact(stream, 0x2440, 0x20)

    def read_archive(name: str) -> bytes:
        checkpoint(cancel)
        if name not in entries:
            raise FormatError(f"missing XD archive {name}")
        entry = entries[name]
        with iso.open("rb") as stream:
            return read_exact(stream, entry["disc_offset"], entry["size"])

    archives = {}
    for name in ("common.fsys", "deck_archive.fsys"):
        archive = read_archive(name)
        archives[name] = archive, {row["name"]: row for row in parse_fsys(archive)["members"]}
    common, members = archives["common.fsys"]
    rel_index, rel = _member(common, members, "common_rel")
    symbols = rel_symbols(rel, parse_rel(rel))
    species, edges, families = _species(rel, symbols)
    native_species = XDMoveRandomizer(rel, symbols, species, options).species
    eligible = {index for index, row in native_species.items() if allowed_replacement(row, options)}
    summary = {"starter": {"original": 133, "species": 133, "level": 10, "moves": list(NATIVE_STARTER_MOVES)},
               "decks": {}}
    summary["national_ids"] = {str(index): row[0] for index, row in species.items()}
    original_dol = dol
    dol, summary["shinies"] = apply_shiny_rules(original_dol, dol, region.game_id, seed, options)
    dol, summary["shadow_shinies"] = apply_shadow_shiny_rules(original_dol, dol, region.game_id, seed, options)
    new_rel, summary["poke_spots"], summary["evolutions"] = _rel(rel, seed, species, edges, symbols, options, eligible)
    trade_requirements = dict(GIFT_TRADE_REQUIREMENTS)
    trade_requirements.update(zip(DUKING_TRADES, (row["species"] for row in summary["poke_spots"] if row["slot"] == 3),
                                  strict=True))
    new_rel, summary["species_gameplay"] = patch_species_gameplay(new_rel, symbols, seed, species, families, options)
    new_rel, dol, summary["tm_gameplay"] = patch_tm_gameplay(new_rel, dol, symbols, region.game_id, seed, species, options)
    new_rel, summary["field_items"] = apply_field_items(rel, new_rel, seed, options)
    move_randomizer = XDMoveRandomizer(new_rel, symbols, species, options)
    if options.randomize_starter or options.randomize_starter_moves:
        dol, summary["starter"] = _starter(dol, STARTERS[region.game_id], seed, species, edges, families,
                                          eligible, options, move_randomizer)
    if options.stone_shops:
        new_rel = patch_stone_price(new_rel, symbols)
        new_rel, name_report = patch_stone_names(rel, new_rel, region.game_id)
        summary["stone_names_changed"] = name_report["changed_names"]
    replacements = {}
    if new_rel != rel:
        replacements["common.fsys"] = {rel_index: new_rel}
    deck_archive, members = archives["deck_archive.fsys"]
    reserved = {families[index] for index in (*PROTECTED_SHADOWS.values(), summary["starter"]["species"])}
    if options.diverse_story_families and not options.randomize_shadows and (
        options.randomize_gifts or options.randomize_tutorial_shadow or options.randomize_hordel_gift
    ):
        _, dark = _member(deck_archive, members, "DeckData_DarkPokemon.bin")
        _, story = _member(deck_archive, members, "DeckData_Story.bin")
        _, native_story = _deck(story, "Story", _shadow_slots(dark), seed, species, families,
                                reserved, XDOptions.unchanged())
        reserved.update(row["family"] for row in native_story["shadows"])
    fixed_shadows = dict(PROTECTED_SHADOWS)
    hordel_evolution = None
    if options.randomize_hordel_gift:
        native_reward = GIFT_BASELINES[0][1]
        protected = {families[index] for index in (*PROTECTED_SHADOWS.values(), native_reward)}
        routes = hordel_candidates(eligible, edges, families, accessible_evolutions=options.accessible_evolutions)
        candidates = [index for index in routes if families[index] not in protected]
        if not candidates:
            raise FormatError("Aucune famille à deux stades adaptée au cadeau de Togepi. Élargissez les filtres de Pokémon.")
        if options.diverse_story_families:
            candidates = [index for index in candidates if families[index] not in reserved] or candidates
        chosen = _pick(seed, "hordel-gift", species, TOGEPI, candidates=candidates, balance=options.balance_species)
        fixed_shadows[HORDEL_SHADOW] = trade_requirements["hordel-trade"] = chosen
        hordel_evolution = routes[chosen]
        reserved.add(families[chosen])
    gift_updates = {}
    edit_gifts = (options.randomize_gifts or options.randomize_gift_moves or include_details
                  or trade_requirements != GIFT_TRADE_REQUIREMENTS)
    starter = summary["starter"]
    starter_changed = starter["species"] != starter["original"]
    name_banks = None
    if edit_gifts or options.randomize_tutorial_shadow or starter_changed:
        name_banks, _ = localized_names(rel, symbols)
    if edit_gifts:
        dol, gift_updates, summary["gifts"] = patch_gifts(
            dol, region.game_id, seed, species, families, reserved if options.diverse_story_families else (),
            read_archive, name_banks=name_banks, eligible=eligible, balance=options.balance_species,
            replace_species=options.randomize_gifts,
            move_randomizer=move_randomizer if options.randomize_gift_moves else None,
            trade_requirements=trade_requirements, hordel_evolution=hordel_evolution,
        )
    else:
        summary["gifts"] = [{"key": key, "original": index, "species": index, "family": families[index], "level": level}
                            for key, index, level in GIFT_BASELINES]
        for row in summary["gifts"]:
            if row["key"] in GIFT_TRADE_REQUIREMENTS:
                row["required_species"] = GIFT_TRADE_REQUIREMENTS[row["key"]]
    if options.randomize_poke_spots and options.poke_spots_full_pokedex:
        summary["poke_spot_actors"] = patch_poke_spot_actors(
            summary["poke_spots"], original_dol, rel, symbols[88]["offset"],
            region.game_id, read_archive, gift_updates,
        )
    if hordel_evolution is not None:
        name = "S1_shop_1F.fsys"
        archive = gift_updates[name] if name in gift_updates else read_archive(name)
        chosen = fixed_shadows[HORDEL_SHADOW]
        dol, gift_updates[name] = patch_hordel_gift(
            dol, archive, region.game_id, chosen, hordel_evolution, species[chosen][0], name_banks,
        )
    if starter_changed:
        gift_updates[STARTER_DIALOGUE_ARCHIVE] = patch_starter_dialogue(
            read_archive(STARTER_DIALOGUE_ARCHIVE), region.game_id, species[starter["species"]][0], name_banks,
        )
    reserved.update(row["family"] for row in summary["gifts"])
    if options.randomize_tutorial_shadow:
        candidates = tutorial_candidates(summary["starter"], eligible, move_randomizer)
        protected_families = {families[index] for sid, index in fixed_shadows.items() if sid != TUTORIAL_SHADOW}
        candidates = [index for index in candidates if families[index] not in protected_families]
        if not candidates:
            raise FormatError("Aucun Pokémon adapté au tutoriel. Élargissez les filtres ou choisissez un starter capable d’attaquer.")
        if options.diverse_story_families:
            candidates = [index for index in candidates if families[index] not in reserved] or candidates
        chosen = _pick(seed, "tutorial-shadow", species, TEDDIURSA, candidates=candidates)
        fixed_shadows[TUTORIAL_SHADOW] = chosen
        reserved.add(families[chosen])
        gift_updates.update(patch_tutorial(region.game_id, chosen, species[chosen][0], name_banks, read_archive))
    # The western archive contains both language variants. Keep them in sync
    # even when the current game build prefers one suffix.
    suffixes = ("", "_EU") if region.game_id != "GXXJ01" else ("",)
    changed_traits = options.randomize_abilities or options.randomize_types
    deck_names = DECKS if options.randomize_trainers or deck_rules_active(options) or changed_traits else ("Story",)
    trainer_dialogues = {}
    for suffix in suffixes:
        dark_name = f"DeckData_DarkPokemon{suffix}.bin"
        dark_index, dark = _member(deck_archive, members, dark_name)
        story_shadows = _shadow_slots(dark)
        if shadow_rules_active(options):
            new_dark, summary["shadow_rules"] = apply_shadow_rules(
                dark, story_shadows, options, protected_shadows=PROTECTED_SHADOWS,
            )
            if new_dark != dark:
                replacements.setdefault("deck_archive.fsys", {})[dark_index] = new_dark
                common_archive, common_members = archives["common.fsys"]
                mirror_index, mirror = _member(common_archive, common_members, dark_name)
                if mirror != dark:
                    raise FormatError("XD Shadow deck copies disagree")
                replacements.setdefault("common.fsys", {})[mirror_index] = new_dark
        for name in deck_names:
            checkpoint(cancel)
            index, deck = _member(deck_archive, members, f"DeckData_{name}{suffix}.bin")
            shadow_slots = story_shadows if name == "Story" else {}
            updated, deck_report = _deck(deck, name, shadow_slots, seed, species, families, reserved, options,
                                         eligible, fixed_shadows=fixed_shadows)
            if deck_rules_active(options):
                updated, battle_report = apply_deck_rules(
                    deck, updated, name, shadow_slots, seed, options, move_randomizer=move_randomizer,
                    edges=edges, protected_shadows=PROTECTED_SHADOWS, eligible_species=eligible,
                    original_species_catalog=native_species, families=families,
                )
                deck_report.update(battle_report)
                levels = {row["shadow_id"]: row["after"] for row in battle_report["trainer_level_edits"]}
                for shadow in deck_report["shadows"]:
                    shadow["level"] = levels.get(shadow["shadow_id"], shadow["level"])
            for shadow in deck_report["shadows"]:
                sid = shadow["shadow_id"]
                shadow["battle_level"] = shadow["level"]
                shadow["level"] = shadow["battle_level"] if sid == HORDEL_SHADOW else dark[0x20 + sid * 0x18 + 2]
                if include_details:
                    pos = 0x20 + sid * 0x18
                    shadow["moves"] = [u16(dark, pos + 0xC + 2 * i) for i in range(4)]
            if name in summary["decks"] and summary["decks"][name] != deck_report:
                raise FormatError("XD deck variants disagree on randomized slots")
            summary["decks"][name] = deck_report
            dialogue = trainer_dialogue_edits(
                name, deck, updated, species, region.game_id, randomize_abilities=options.randomize_abilities,
                randomize_types=options.randomize_types,
            ) if updated != deck or changed_traits else {}
            if suffix and trainer_dialogues[name] != dialogue:
                raise FormatError("XD deck variants disagree on trainer dialogue")
            trainer_dialogues[name] = dialogue
            if name == "Story" and not suffix:
                if updated != deck:
                    actor = patch_eagun_actor(deck, updated, rel, symbols[88]["offset"], species,
                                              original_dol, region.game_id, read_archive, gift_updates)
                    if actor is not None:
                        summary["eagun_field_partner"] = actor
                    dancers = patch_lighthouse_dancers(deck, updated, rel, symbols, species,
                                                        original_dol, region.game_id, read_archive, gift_updates)
                    if dancers:
                        summary["miror_lighthouse_dancers"] = dancers
                    wakin = patch_wakin_partner(deck, updated, rel, symbols[88]["offset"], species,
                                                original_dol, region.game_id, read_archive, gift_updates)
                    if wakin is not None:
                        summary["wakin_field_partner"] = wakin
                shiny = summary["shadow_shinies"].get("statuses", {}).get(str(GATEON_SHADOW), False)
                if options.randomize_shadows or shiny:
                    shadow = next(row for row in deck_report["shadows"] if row["shadow_id"] == GATEON_SHADOW)
                    actor = patch_gateon_shadow(shadow, rel, symbols[88]["offset"], species, original_dol,
                                                region.game_id, read_archive, gift_updates, shiny)
                    if actor is not None:
                        summary["gateon_field_shadow"] = actor
            if updated != deck:
                replacements.setdefault("deck_archive.fsys", {})[index] = updated
    dialogue_edits = {}
    for edits in trainer_dialogues.values():
        for archive, messages in edits.items():
            dialogue_edits.setdefault(archive, {}).update(messages)
    if starter_changed:
        # The sailor also offers an item when the player has never owned an Eevee.
        archive, identifiers = STARTER_ITEM_DIALOGUE
        dialogue_edits.setdefault(archive, {}).update(dict.fromkeys(identifiers, {}))
    dragonite = next(row for row in summary["decks"]["Story"]["shadows"] if row["original"] == 149)
    if dragonite["species"] != dragonite["original"]:
        changes = {1149: 1000 + species[dragonite["species"]][0]}
        for name, identifiers in DRAGONITE_DIALOGUE.items():
            dialogue_edits.setdefault(name, {}).update(dict.fromkeys(identifiers, changes))
    if dialogue_edits:
        if name_banks is None:
            name_banks, _ = localized_names(rel, symbols)
        updated_dialogue = {}
        for name, messages in dialogue_edits.items():
            source = gift_updates[name] if name in gift_updates else read_archive(name)
            payload = patch_species_archive(source, messages, name_banks, rewrites=TRAINER_REMARK_REWRITES)
            if payload != source:
                gift_updates[name] = payload
                updated_dialogue[name] = sorted(messages)
        if updated_dialogue:
            summary["story_dialogue"] = updated_dialogue
    if options.stone_shops or options.randomize_shop_items:
        shop_suffixes = ("", "_fr", "_ge", "_it", "_sp") if region.game_id == "GXXP01" else ("",)
        for suffix in shop_suffixes:
            name = f"pocket_menu{suffix}.fsys"
            archive = read_archive(name)
            native = [row for row in parse_fsys(archive)["members"]
                      if row["name"] == "pocket_menu" and row["identifier_raw"] == "0x02f21c00"]
            if len(native) != 1:
                raise FormatError("missing XD pocket menu executable member")
            member = native[0]
            original_menu = patched = decoded_member(archive, member)
            if options.stone_shops:
                patched, shop_report = patch_stone_stock(original_menu, region.game_id)
                if "stone_shops" in summary and summary["stone_shops"] != shop_report:
                    raise FormatError("localized XD cash stocks disagree")
                summary["stone_shops"] = shop_report
            if options.randomize_shop_items:
                patched, shop_report = apply_shop_items(rel, patched, region.game_id, seed, options)
                if "shop_items" in summary and summary["shop_items"] != shop_report:
                    raise FormatError("localized XD cash stocks disagree")
                summary["shop_items"] = shop_report
            archives[name] = archive, {}
            if patched != original_menu:
                replacements[name] = {member["index"]: patched}
    statuses = summary["shinies"].get("statuses", {})
    if statuses:
        summary["starter"]["shiny"] = statuses["starter"]
        for row in summary["gifts"]:
            row["shiny"] = statuses[row["key"]]
    shadow_status = summary["shadow_shinies"].get("statuses", {})
    if shadow_status:
        for deck in summary["decks"].values():
            for row in deck["shadows"]:
                row["shiny"] = shadow_status[str(row["shadow_id"])]
    dol, summary["battle_progression"] = apply_dol_battle_rules(original_dol, dol, region.game_id, options)
    if include_details:
        summary["detail_catalog"] = detail_catalog(new_rel, dol, symbols, region.game_id, edges, move_randomizer)
    story_families = defaultdict(list)
    story_families[families[summary["starter"]["species"]]].append("starter")
    for row in summary["decks"]["Story"]["shadows"]:
        story_families[families[row["species"]]].append(f"shadow:{row['shadow_id']}")
    for row in summary["gifts"]:
        story_families[families[row["species"]]].append(row["key"])
    summary["family_duplicates"] = [keys for keys in story_families.values() if len(keys) > 1]
    progress(25, "Compression des données du jeu…")
    patches = [(dol_offset, dol)] if dol != original_dol else []
    # Preserve all declared files, the apploader, executable, and FST. When
    # recompression outgrows an archive's slot, allocate from a free disc gap.
    system_end = max(fst_offset + max(fst_size, fst_max), dol_offset + region.dol_size,
                     0x2460 + u32(app_header, 0x14) + u32(app_header, 0x18))
    ranges = [(entry["disc_offset"], entry["disc_offset"] + entry["size"]) for entry in files
              if entry["size"]]
    ranges.sort()
    end = system_end
    gaps = []
    for start, stop in [*ranges, (DISC_SIZE, DISC_SIZE)]:
        if start < end or stop > DISC_SIZE:
            raise FormatError("overlapping or out-of-bounds XD disc files")
        if start > end:
            gaps.append((end, start))
        end = stop

    def allocate(size):
        for i, (start, stop) in enumerate(gaps):
            offset = align(start, 0x20)
            if offset + size <= stop:
                gaps[i] = (offset + size, stop)
                return offset
        raise FormatError("no safe disc gap for rebuilt XD data")

    relocated_fst = len(dol) > len(original_dol)
    if relocated_fst:
        if (fst_offset < dol_offset + len(original_dol)
                or dol_offset + len(dol) > ranges[0][0]):
            raise FormatError("grown XD DOL overlaps an original disc file")
        fst_offset = allocate(max(fst_size, fst_max))
        patches.append((0x424, struct.pack(">I", fst_offset)))

    updates = dict(gift_updates)
    for name, members in replacements.items():
        checkpoint(cancel)
        if name in updates:
            raise FormatError("overlapping XD archive edits")
        updates[name], _ = repack_fsys(archives[name][0], members)
    for name, payload in updates.items():
        checkpoint(cancel)
        entry = entries[name]
        offset = entry["disc_offset"]
        if len(payload) > entry["size"]:
            offset = allocate(len(payload))
        patches.append((offset, payload))
        struct.pack_into(">II", fst, entry["index"] * 12 + 4, offset, len(payload))
    if updates or relocated_fst:
        patches.append((fst_offset, bytes(fst)))
    return sorted(patches), summary
