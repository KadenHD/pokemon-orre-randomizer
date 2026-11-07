"""Roll a shiny policy when XD creates an ordinary Poké Spot encounter."""

from .engine.analyze_game import FormatError, u32
from .engine.gift_move_hooks import branch
from .engine.shiny_rules import COIN_RANGE, _Code, chance_threshold
from .xd_battle_rules import TEXT1_TO_RAM, append_xd_dol_text


# Offsets in DOL text1: HSD_Rand, pokemonCreateRnd, heroGetStatus,
# GSflagSet and the five ordinary appearance paths that store the PID.
_LAYOUTS = {
    "GXXP01": (0x25B8A4, 0x13FE8C, 0x14BF04, 0x19EC00,
               (0x294320, 0x2944D8, 0x294764, 0x294870, 0x294A28)),
    "GXXE01": (0x259968, 0x13E5C8, 0x14A640, 0x19D304,
               (0x2923E4, 0x29259C, 0x292828, 0x292934, 0x292AEC)),
    "GXXJ01": (0x254278, 0x1399D4, 0x145988, 0x198874,
               (0x28CE0C, 0x28CFC4, 0x28D250, 0x28D35C, 0x28D514)),
}


def _encounter_pid(address, rng, create_pid, hero_status, threshold):
    code = _Code(address)
    code.emit(0x9421FFE0, 0x7C0802A6, 0x90010024,  # stack and return address
              0x38600000, 0x38800002, 0x38A00000)  # heroGetStatus(0, 2, 0): SID/TID
    code.call(hero_status)
    code.emit(0x5464843E, 0x7C632278, 0x90610008)  # fold the two owner halves
    if threshold in (0, COIN_RANGE):
        code.emit(0x38600000 | int(threshold == COIN_RANGE))
    else:
        code.call(rng)
        code.emit(0x5463801E, 0x90610010)  # save the high half of the coin
        code.call(rng)
        code.emit(0x80810010, 0x7C632378,  # combine the two native 16-bit draws
                  0x3C800000 | (threshold >> 16), 0x60840000 | (threshold & 0xFFFF),
                  0x7C032040, 0x38600000)  # cmplw r3,r4; li r3,0
        code.conditional(0x40800000, "policy_ready")
        code.emit(0x38600001)
    code.label("policy_ready")
    code.emit(0x9061000C)
    code.label("draw_pid")
    code.call(create_pid)
    code.emit(0x5464843E, 0x5465043E,  # r4 = high PID, r5 = low PID
              0x80C10008, 0x54C6043E, 0x7C842A78, 0x7C843278,  # shiny XOR in r4
              0x80E1000C, 0x28070000)
    code.conditional(0x40820000, "make_shiny")
    code.emit(0x28040008)
    code.conditional(0x41800000, "draw_pid")  # reject a shiny PID for the normal policy
    code.jump("return")
    code.label("make_shiny")
    # Keep the random low half and the three random shiny XOR bits. This
    # maps to the shiny PID space directly, without thousands of rerolls.
    code.emit(0x5484077E, 0x7C842A78, 0x7C843278, 0x5484801E, 0x7C832B78)
    code.label("return")
    code.emit(0x80010024, 0x7C0803A6, 0x38210020, 0x4E800020)
    return code.finish()


def apply_poke_spot_shinies(original, current, game_id, options):
    if not options.custom_poke_spot_shinies:
        return current, {"enabled": False}

    rng, create_pid, hero_status, flag_set, calls = _LAYOUTS[game_id]
    for index, offset in enumerate(calls):
        indexed_flag = (0x7C60EA14, 0x7C60FA14, 0x7C60DA14, 0x7C60DA14, 0x7C60EA14)[index]
        expected = (0x800D8B64 if game_id == "GXXJ01" else 0x800D8B6C,
                    0x7C641B78, indexed_flag, 0x80630010, branch(offset + 20, flag_set, link=True))
        if tuple(u32(original, offset + 4 * i) for i in range(1, 6)) != expected:
            raise FormatError("unexpected XD Poké Spot PID storage")
    # The special Bonsly/Munchlax path calls the same owner getter. Check its
    # call and arguments before using it from the ordinary encounter wrapper.
    owner_call = calls[2] - 0x64
    owner = (0x38600000, 0x38800002, 0x38A00000, branch(owner_call, hero_status, link=True))
    if tuple(u32(original, owner_call - 12 + 4 * i) for i in range(4)) != owner:
        raise FormatError("unexpected XD Poké Spot owner getter")

    rate = options.poke_spot_shiny_chance_percent
    threshold = chance_threshold(rate)

    def stub(address, _continuation):
        return _encounter_pid(address, rng + TEXT1_TO_RAM, create_pid + TEXT1_TO_RAM,
                              hero_status + TEXT1_TO_RAM, threshold)

    patched, hooks = append_xd_dol_text(original, current, game_id, (
        (offset + TEXT1_TO_RAM, branch(offset, create_pid, link=True), stub)
        for offset in calls
    ), link=True)
    return patched, {"enabled": True, "chance_percent": rate, "hooks": hooks}
