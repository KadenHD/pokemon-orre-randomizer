"""Revision-0 render-pass sites, matched independently in each retail DOL.

Fullscreen bounds are compensated before native command recording.
Texture targets keep native bounds; their aspect is set by their consumer.
Movie/HUD projections are deliberately absent from these exceptions.
"""

# (native fullscreen callee, retail float 0.125, fullscreen BL sites,
#  native texture-target BL sites paired with their original callee).
RENDER_PASSES = {
    "GC6P01": (0x800DD1A8, 0x804CB380, (
        0x800D78D0, 0x8010CB04, 0x80142658, 0x80142A7C, 0x801C8A68,
        0x801C8F04, 0x801C9228, 0x801CAB08, 0x801CABBC,
    ), (
        (0x80199F48, 0x800A701C),
    )),
    "GC6E01": (0x800D9B58, 0x8047DE18, (
        0x800D4280, 0x801094EC, 0x8013E2E4, 0x8013E708, 0x801C46F4,
        0x801C4B90, 0x801C4EB4, 0x801C6794, 0x801C6848,
    ), (
        (0x80195BD4, 0x800A39E0),
    )),
    "GC6J01": (0x800D72D4, 0x80469458, (
        0x800D1A00, 0x80106ED0, 0x8013B3BC, 0x8013B7E0, 0x801C02C4,
        0x801C0758, 0x801C0A7C, 0x801C235C, 0x801C2410,
    ), (
        (0x80191798, 0x800A168C),
    )),
    "GXXP01": (0x800F1028, 0x80526E34, (
        0x80115F4C, 0x8015B3B0, 0x8015B8A0, 0x80189ECC, 0x801A9708,
        0x801AA278, 0x801AA750, 0x801AAEEC, 0x801ABD48, 0x801AC730,
        0x801AD4F0, 0x801AE338, 0x801AEC98, 0x801AF6EC, 0x801B073C,
        0x801B1B84, 0x801B2A50, 0x801B3BC0, 0x801B54E8, 0x801B5AAC,
        0x801B8380, 0x801B8680, 0x802BA950, 0x802BB2A4, 0x802C2298,
    ), (
        (0x80089EFC, 0x800F1028),
        (0x8009E6AC, 0x800F1028),
        (0x80261A64, 0x800B4B5C),
    )),
    "GXXE01": (0x800EFA18, 0x804EC874, (
        0x80114808, 0x80159B00, 0x80159FF0, 0x8018861C, 0x801A7E0C,
        0x801A897C, 0x801A8E54, 0x801A95F0, 0x801AA44C, 0x801AAE34,
        0x801ABBF4, 0x801ACA3C, 0x801AD39C, 0x801ADDF0, 0x801AEE40,
        0x801B0288, 0x801B1154, 0x801B22C4, 0x801B3BEC, 0x801B41B0,
        0x801B6A84, 0x801B6D84, 0x802B89F0, 0x802B9344, 0x802C0338,
    ), (
        (0x800890CC, 0x800EFA18),
        (0x8009D7F4, 0x800EFA18),
        (0x8025FB28, 0x800B3504),
    )),
    "GXXJ01": (0x800EBE98, 0x804CC6D8, (
        0x8010FEE8, 0x8015516C, 0x8015565C, 0x80183C5C, 0x801A3374,
        0x801A3EE4, 0x801A43BC, 0x801A4B58, 0x801A59B4, 0x801A639C,
        0x801A715C, 0x801A7FA4, 0x801A8904, 0x801A9358, 0x801AA3A8,
        0x801AB7F0, 0x801AC6BC, 0x801AD82C, 0x801AF154, 0x801AF718,
        0x801B1FEC, 0x801B22EC, 0x802B3418, 0x802B3D6C, 0x802BAD60,
    ), (
        (0x80086980, 0x800EBE98),
        (0x8009A7E8, 0x800EBE98),
        (0x8025A438, 0x800AF998),
    )),
}

# XD FLASH geometry is a temporary stack buffer; its fade quad is a
# dedicated retail constant referenced only by alphaFadeDraw.
FLASH_BACKGROUNDS = {
    "GXXP01": (0x80276758, 0x80323DE8),
    "GXXE01": (0x8027481C, 0x80322460),
    "GXXJ01": (0x8026F12C, 0x80310798),
}

# (native vertex callee, textured vertex site, solid vertex sites).
# XD emits vertices inline; its callee is None.
WINDOW_BACKGROUNDS = {
    "GC6P01": (0x800D9834, 0x8010C1BC, (0x8010C690, 0x8010C6CC)),
    "GC6E01": (0x800D61E4, 0x80108BA4, (0x80109078, 0x801090B4)),
    "GC6J01": (0x800D3964, 0x801065AC, (0x80106A80, 0x80106ABC)),
    "GXXP01": (None, 0x8010F09C, (0x8010F664, 0x8010F690, 0x8010F6B8, 0x8010F6F0)),
    "GXXE01": (None, 0x8010D978, (0x8010DF40, 0x8010DF6C, 0x8010DF94, 0x8010DFCC)),
    "GXXJ01": (None, 0x801091A8, (0x80109770, 0x8010979C, 0x801097C4, 0x801097FC)),
}

# (GSres table/count r13 displacements, localized menu group interval (also allow base groups 37C and 531),
#  HSD_CObjSetCurrent perspective BL sites with its camera in r30).
MENU_CAMERAS = {
    "GC6P01": (-23476, -23472, 0x7CB, 0x7D7, (0x80199EF8, 0x8019A18C)),
    "GC6E01": (-23492, -23488, 0x632, 0x632, (0x80195B84, 0x80195E18)),
    "GC6J01": (-23532, -23528, 0x632, 0x632, (0x80191748, 0x801919DC)),
}
