"""Known retail XD encounters for the pre-calculation UI, without a ROM read."""
from .xd import PROTECTED_SHADOWS, SPOT_SPECIES
from .xd_gifts import GIFT_BASELINES, GIFT_TRADE_REQUIREMENTS, HORDEL_SHADOW, TOGETIC

# (internal species ID, National Pokédex ID), in native Shadow-ID order.
# Checked against the Story/DDPK tables of the three supported revision-0 discs.
BASE_SHADOWS = (
    (216, 216), (37, 37), (341, 363), (318, 343), (179, 179), (367, 316),
    (298, 273), (167, 167), (339, 322), (330, 318), (363, 315), (316, 301),
    (320, 299), (228, 228), (335, 296), (361, 355), (392, 280), (355, 303),
    (346, 361), (204, 204), (220, 220), (177, 177), (306, 285), (52, 52),
    (21, 21), (88, 88), (86, 86), (348, 337), (100, 100), (380, 335),
    (58, 58), (46, 46), (90, 90), (15, 15), (17, 17), (12, 12),
    (114, 114), (20, 20), (49, 49), (70, 70), (24, 24), (57, 57),
    (97, 97), (55, 55), (322, 302), (82, 82), (85, 85), (83, 83),
    (359, 334), (115, 115), (378, 354), (126, 126), (127, 127), (219, 219),
    (78, 78), (107, 107), (106, 106), (108, 108), (123, 123), (113, 113),
    (349, 338), (121, 121), (125, 125), (305, 277), (143, 143), (62, 62),
    (122, 122), (51, 51), (338, 310), (397, 373), (105, 105), (131, 131),
    (249, 249), (145, 145), (146, 146), (144, 144), (128, 128), (112, 112),
    (103, 103), (149, 149), (175, 175), (286, 261), (165, 165),
)
NATIONAL_IDS = dict(BASE_SHADOWS) | {
    133: 133, 239: 239, 356: 307, 213: 213, 246: 246, 152: 152, 155: 155,
    158: 158, 27: 27, 207: 207, 332: 328, 187: 187, 231: 231, 311: 283,
    41: 41, 382: 304, 194: 194, TOGETIC: TOGETIC,
}


def baseline_rows(options):
    def row(original, pending, **values):
        return dict(original=original, species=None if pending else original, **values)

    starter = row(133, options.randomize_starter, level=10)
    if options.randomize_starter and options.starter_species > 0:
        starter['national_dex'] = options.starter_species
    shadows = []
    for sid, (original, _) in enumerate(BASE_SHADOWS, 1):
        pending = (options.randomize_tutorial_shadow if sid == 1 else
                   options.randomize_hordel_gift if sid == HORDEL_SHADOW else
                   options.randomize_shadows and sid not in PROTECTED_SHADOWS)
        shadows.append(row(original, pending, shadow_id=sid))
    gifts = []
    for key, original, level in GIFT_BASELINES:
        gift = row(original, options.randomize_gifts, key=key, level=level)
        if key in GIFT_TRADE_REQUIREMENTS:
            gift['required_species'] = GIFT_TRADE_REQUIREMENTS[key]
        if key == 'hordel-trade':
            gift['required_evolution'] = TOGETIC
        gifts.append(gift)
    spots = [row(original, options.randomize_poke_spots, spot=spot, slot=index)
             for spot, species in SPOT_SPECIES.items() for index, original in enumerate(species, 1)]
    return dict(starter=starter, decks={'Story': {'shadows': shadows}}, gifts=gifts,
                poke_spots=spots, national_ids={str(key): value for key, value in NATIONAL_IDS.items()})
