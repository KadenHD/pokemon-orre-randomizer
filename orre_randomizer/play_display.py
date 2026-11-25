"""Per-run display settings; reversible camera patches never alter the ROM.

The projection hook follows Ralf's 16:9 code shipped in Dolphin's GC6P01,
GC6E01 and GXXP01 GameSettings. Other revision-0 regions use the same checked
MTXPerspective instruction sequence and regional r2 addresses. An existing
read-only 0.75 constant supplies both inverse camera scaling and 2D scaling.
Fullscreen clears, fades and snapshots compensate their input bounds before
native command recording; scaling those passes like the HUD leaves stale side
bands. Offscreen texture targets keep their native projection. No game variables
or BSS tail are used for injected constants. Keep the
generic Dolphin widescreen hack off: applying both would widen the scene twice.
"""
from __future__ import annotations

from pathlib import Path
import re

from ._display_regions import RENDER_PASSES, WINDOW_BACKGROUNDS, FLASH_BACKGROUNDS, MENU_CAMERAS


DISPLAY_MODES = ("16:9", "4:3")
PATCH_NAME = "Orre display projection"
# Uninstalled, reserved MetroTRK vector-template padding in each retail .init.
# This stays outside XD's native Anti Action Replay clears at 1800..2FFF and
# outside Dolphin's Gecko handler. Hardware vectors are installed elsewhere;
# the native copy table never selects these reserved source slots.
FLASH_SCRATCH = 0x80004D00

# game ID: (fmr f29,f2 hook, r2, retail read-only float 0.75).
PROJECTIONS = {
    "GC6P01": (0x800A6F6C, 0x804D0B60, 0x804C8C54),
    "GC6E01": (0x800A3930, 0x804836A0, 0x8047B784),
    "GC6J01": (0x800A15DC, 0x8046ED20, 0x80466DFC),
    "GXXP01": (0x800B4AAC, 0x8052E3A0, 0x805265FC),
    "GXXE01": (0x800B3454, 0x804F3DC0, 0x804EC01C),
    "GXXJ01": (0x800AF8E8, 0x804D12A0, 0x804C94FC),
}


def acceleration_target(settings):
    """Old speed=1 meant normal play, with a fixed 200% Tab shortcut."""
    value = settings.get("acceleration", 2)
    if type(value) not in (int, float) or value not in (1, 2, 3):
        raise ValueError("Invalid acceleration target")
    return value


def display_mode(settings):
    value = settings.get("display", "16:9")
    if value not in DISPLAY_MODES:
        raise ValueError("Invalid display mode")
    return value


def _branch(source, target):
    delta = target - source
    if delta % 4 or not -0x2000000 <= delta < 0x2000000:
        raise ValueError("Display branch out of range")
    return 0x48000000 | (delta & 0x03FFFFFC)


def _bounds_adapter(address, target, r2, eighth, *, sdk_order):
    """Undo the HUD's .75 only for this native screen/texture render pass.

    Narrow [left,right] by one eighth at each end before the native matrix
    calculation. Its later .75 multiplication then returns the original matrix.
    This also works for Colosseum's deferred command 58: adjusted arguments are
    recorded once and replayed once. Only ABI-volatile f0/f10 are scratch;
    tail-calling preserves the producer's LR and its other arguments.
    """
    left, right = (3, 4) if sdk_order else (1, 3)
    displacement = eighth - r2
    if not -32768 <= displacement <= 32767:
        raise ValueError("Display bounds constant out of range")
    words = (0xC1420000 | (displacement & 0xFFFF),  # lfs f10, .125(r2)
             0xEC000028 | (right << 16) | (left << 11),  # fsubs f0,right,left
             0xEC0002B2,  # fmuls f0,f0,f10
             0xEC00002A | (left << 21) | (left << 16),  # fadds left,left,f0
             0xEC000028 | (right << 21) | (right << 16),  # fsubs right,right,f0
             _branch(address + 20, target))
    return [(address + i * 4, word, None) for i, word in enumerate(words)]


def _render_pass_entries(game_id, wide):
    target, eighth, fullscreen, textures = RENDER_PASSES[game_id]
    r2 = PROJECTIONS[game_id][1]
    is_xd = game_id.startswith("GXX")
    rows = []
    if wide:
        rows += _bounds_adapter(0x80005330, target, r2, eighth, sdk_order=is_xd)
        if not is_xd:
            # Colosseum's gfxSetOrtho reorders left/top/right/bottom. HSD calls
            # the SDK directly with top/bottom/left/right instead.
            sdk = PROJECTIONS[game_id][0] + 0xB0
            rows += _bounds_adapter(0x80005350, sdk, r2, eighth, sdk_order=True)
    for call in fullscreen:
        original, owned = _branch(call, target) | 1, _branch(call, 0x80005330) | 1
        rows.append((call, owned, original) if wide else (call, original, owned))
    for call, native_target in textures:
        adapter = 0x80005330 if is_xd else 0x80005350
        original, owned = _branch(call, native_target) | 1, _branch(call, adapter) | 1
        rows.append((call, owned, original) if wide else (call, original, owned))
    return rows


def _background_entries(game_id, wide):
    """Expand unrotated full-width window backgrounds, including tiled strips.

    Colosseum records its vertex call; XD writes the same GPU FIFO inline. The
    latter's selected blocks have dead r11/r12/CR7 and a saved LR, so BL/BLR is
    safe there. Keep CR0 intact in XD. UVs, colors, Y and sprite data stay native.
    Rounded X limits overlap the screen by a quarter pixel, avoiding edge gaps.
    """
    callee, textured, solid = WINDOW_BACKGROUNDS[game_id]
    xd = callee is None
    address = 0x80005350 if xd else 0x80005368
    words, labels, jumps = [], {}, []

    def label(name):
        labels[name] = address + len(words) * 4

    def jump(name, condition):
        pc = address + len(words) * 4
        jumps.append((len(words), pc, name, condition))
        words.append(0)

    label('texture')
    if xd:
        words.append(0x7FECFB78)  # mr r12,r31 (textured sprite)
        jump('body', None)
        label('solid')
        words.append(0x7F4CD378)  # mr r12,r26 (solid sprite)
        label('body')
        words.extend((0x816C0070, 0x2F8B0000))  # rotation == +0.0
        jump('store', 0x409E0000)
        words.extend((0xA96C0050, 0x2F8B0000))  # left <= 0
        jump('store', 0x419D0000)
        words.extend((0xA98C0054, 0x7D6B6214, 0x2F8B0280))  # left + width >= 640
        jump('store', 0x419C0000)
        words.extend((0x540B103A, 0x396B0002, 0x39800003, 0x7D6B63D6, 0x380BFF95))
    else:
        words.extend((0xA99A0050, 0x2F8C0000))  # left <= 0
        jump('store', 0x419D0000)
        words.extend((0xA81A0054, 0x7C0C0214, 0x2F800280))  # left + width >= 640
        jump('store', 0x419C0000)
        words.extend((0x819A0070, 0x2F8C0000))  # rotation == +0.0
        jump('store', 0x409E0000)
        # D-form addi treats RA=0 as zero, even when r0 holds a value. Keep
        # the numerator in r12 and use r0 only as the divisor here.
        words.extend((0x546C103A, 0x398C0002, 0x38000003, 0x7C6C03D6, 0x3863FF95))
    # x' = trunc((4*x + 2) / 3) - 107. This includes native overscan panels
    # such as [-20,660], with quarter-pixel overlap at the visible 0/640 edges.
    label('store')
    if xd:
        # Signed -0x8000 offset: CC010000 - 8000 = CC008000, the native FIFO.
        words.extend((0x3D80CC01, 0xB00C8000, 0x4E800020))
    else:
        words.append(_branch(address + len(words) * 4, callee))
    for index, pc, name, condition in jumps:
        target = labels[name]
        words[index] = (_branch(pc, target) if condition is None else
                        condition | ((target - pc) & 0xFFFF))
    if address + len(words) * 4 > 0x800053AC:
        raise ValueError("Display code overlaps the native exception handler")
    rows = [(address + i * 4, word, None) for i, word in enumerate(words)] if wide else []
    for call, entry in ((textured, labels['texture']),
                        *((call, labels.get('solid', address)) for call in solid)):
        original = (_branch(call, callee) | 1) if callee else (0xB0158000 if call == textured else 0xB0068000)
        owned = _branch(call, entry) | 1
        rows.append((call, owned, original) if wide else (call, original, owned))
    return rows


def _flash_entries(game_id, wide):
    """XD's FLASH backgrounds are often 640x240 tiles, rather than one image.

    Recognize all four full-width X values after getUV builds the temporary
    positions. Change only those X values; UVs, Y, labels and bounded portraits
    remain native. r0/r12/CR7 are dead here and the overwritten lha is reissued.
    """
    if game_id not in FLASH_BACKGROUNDS:
        return []
    hook, alpha = FLASH_BACKGROUNDS[game_id]
    start = FLASH_SCRATCH
    words = (0x80010024, 0x8181003C, 0x7C006378, 0x2F800000, 0x409E003C,
             0x8001002C, 0x81810034, 0x7F806000, 0x409E002C,
             0x6C004420, 0x2F800000, 0x409E0020,
             0x3C00C2D6, 0x90010024, 0x9001003C, 0x3C00443A, 0x6000C000,
             0x9001002C, 0x90010034, 0xA87F0000, _branch(start + 80, hook + 4))
    rows = [(start + i * 4, word, None) for i, word in enumerate(words)] if wide else []
    owned = _branch(hook, start)
    rows.append((hook, owned, 0xA87F0000) if wide else (hook, 0xA87F0000, owned))
    # CMetaMenu's fade uses a dedicated, uniquely referenced constant quad.
    for offset, original, expanded in ((0, 0, 0xC2D60000), (8, 0x44200000, 0x443AC000),
                                       (16, 0x44200000, 0x443AC000), (24, 0, 0xC2D60000)):
        rows.append((alpha + offset, expanded, original) if wide else
                    (alpha + offset, original, expanded))
    return rows


def _menu_camera_entries(game_id, wide):
    """Keep Colosseum's finite 3D menu backdrops covering the full screen.

    This camera is separate from the text/window projection. Identify its live
    HSD object through the engine's resource registry and the regional menu
    archive groups, rather than matching a FOV that other scenes could share.
    Only the two checked HSD perspective callsites supply the object in r30.
    Tail-calling the SDK keeps LR and the matrix pointer; scratch registers,
    CTR, CR7 and f0 are ABI-volatile. No resource or camera record is modified.
    """
    if game_id not in MENU_CAMERAS:
        return []
    table, count, first_group, last_group, calls = MENU_CAMERAS[game_id]
    start, sdk = FLASH_SCRATCH, PROJECTIONS[game_id][0] - 0x20
    words, labels, jumps = [], {}, []

    def label(name):
        labels[name] = start + len(words) * 4

    def jump(name, condition):
        jumps.append((len(words), start + len(words) * 4, name, condition))
        words.append(0)

    words.extend((0x818D0000 | (table & 0xFFFF), 0x800D0000 | (count & 0xFFFF),
                  0x2F800000))  # lwz r12,table(r13); lwz r0,count(r13)
    jump('native', 0x419E0000)
    words.append(0x2B802000)  # reject corrupt/unbounded resource counts
    jump('native', 0x419D0000)
    words.extend((0x7C0903A6, 0x2F8C0000))  # mtctr r0; table != NULL
    jump('native', 0x419E0000)
    label('loop')
    # The registry is engine-owned, but reject corrupt/stale entries rather
    # than following an arbitrary address or walking past GameCube MEM1.
    words.extend((0x3D608000, 0x7F8C5840))  # table >= 80000000
    jump('native', 0x419C0000)
    words.extend((0x3D60817F, 0x616BFFE0, 0x7F8C5840))
    jump('native', 0x419D0000)  # table record <= 817FFFE0
    words.extend((0x816C000C, 0x6D6B0FFF, 0x2F8B1800))  # exact camera ID 0FFF1800
    jump('next', 0x409E0000)
    words.extend((0x816C0008, 0x2F8B037C))  # pokechg_menu, all regions
    jump('camera', 0x419E0000)
    words.append(0x2F8B0531)  # cb_menu, all regions
    jump('camera', 0x419E0000)
    words.append(0x2F8B0000 | first_group)
    jump('next', 0x419C0000)
    words.append(0x2F8B0000 | last_group)
    jump('next', 0x419D0000)
    label('camera')
    words.extend((0x816C0004, 0x3C008000, 0x7F8B0040))
    jump('next', 0x419C0000)
    words.extend((0x3C00817F, 0x6000FFF0, 0x7F8B0040))
    jump('next', 0x419D0000)  # the camera's +0xC word must also be in MEM1
    words.extend((0x816B000C, 0x7F8BF000))  # *(GSRenderCamera+0xC) == r30
    jump('next', 0x409E0000)
    displacement = PROJECTIONS[game_id][2] - PROJECTIONS[game_id][1]
    words.extend((0xC0020000 | (displacement & 0xFFFF), 0xEC420032))
    jump('native', None)  # .75 input cancels Hor+ for this backdrop only
    label('next')
    words.append(0x398C0014)
    jump('loop', 0x42000000)  # bdnz, bounded by the checked resource count
    label('native')
    words.append(_branch(start + len(words) * 4, sdk))
    for index, pc, name, condition in jumps:
        target = labels[name]
        words[index] = (_branch(pc, target) if condition is None else
                        condition | ((target - pc) & 0xFFFC))
    if len(words) * 4 > 0x100:
        raise ValueError("Menu camera adapter exceeds its reserved scratch area")
    rows = [(start + i * 4, word, None) for i, word in enumerate(words)] if wide else []
    for call in calls:
        native, owned = _branch(call, sdk) | 1, _branch(call, start) | 1
        rows.append((call, owned, native) if wide else (call, native, owned))
    return rows


def projection_entries(game_id, wide):
    hook, r2, constant = PROJECTIONS[game_id]
    branch = _branch(hook, 0x80005300)
    ortho_return = hook + 0x144
    ortho_branch = _branch(ortho_return, 0x80005310)
    if not wide:
        # A state captured in wide mode may contain the hook. Restore only our
        # exact branch; never overwrite a different user-authored hook.
        return [(hook, 0xFFA01090, branch), (ortho_return, 0x4E800020, ortho_branch),
                *_render_pass_entries(game_id, False), *_background_entries(game_id, False),
                *_flash_entries(game_id, False), *_menu_camera_entries(game_id, False)]
    displacement = constant - r2
    if not -32768 <= displacement <= 32767:
        raise ValueError("Display constant out of range")
    entries = [(0x80005300, 0xC3A20000 | (displacement & 0xFFFF), None),
            (0x80005304, 0xEFA2E824, None),
            (0x80005308, _branch(0x80005308, hook + 4), None),
            (hook, branch, 0xFFA01090)]
    # Preserve 2D text, portraits and movies. MTXOrtho returns the matrix in r3.
    # Scale its X row about the viewport center. LR and all GPRs are untouched;
    # f0/f10 are caller-saved and unspecified after this void SDK function.
    words = (0xC0020000 | (displacement & 0xFFFF),
             0xC1430000, 0xED4A0032, 0xD1430000,
             0xC143000C, 0xED4A0032, 0xD143000C, 0x4E800020)
    entries.extend((0x80005310 + index * 4, value, None) for index, value in enumerate(words))
    entries.extend(_render_pass_entries(game_id, True))
    entries.extend(_background_entries(game_id, True))
    entries.extend(_flash_entries(game_id, True))
    entries.extend(_menu_camera_entries(game_id, True))
    entries.append((ortho_return, ortho_branch, 0x4E800020))
    return entries


def configure_projection(profile: Path, game_id: str, mode: str):
    """Replace just our named native patch; keep unrelated GameINI content."""
    if game_id not in PROJECTIONS or mode not in DISPLAY_MODES:
        raise ValueError("No checked display recipe for this game")
    path = profile / "GameSettings" / (game_id + ".ini")
    for target in (path.parent, path):
        if target.is_symlink() or target.is_junction():
            raise ValueError("Display settings cannot write linked configuration")
    text = path.read_text("utf-8") if path.is_file() else ""
    # Dolphin native patch lists are not ordinary key=value INI sections.
    sections = re.split(r"(?m)^(\[[^\]\r\n]+\])\s*$", text)
    output = sections[0]
    contents = {sections[i][1:-1]: sections[i + 1] for i in range(1, len(sections), 2)}
    body = contents.get("OnFrame", "")
    body = re.sub(r"(?m)^\$" + re.escape(PATCH_NAME) + r"\s*\n[^$\[]*", "", body)
    lines = ["$" + PATCH_NAME]
    for address, value, expected in projection_entries(game_id, mode == "16:9"):
        line = f"0x{address:08X}:dword:0x{value:08X}"
        lines.append(line + (f":0x{expected:08X}" if expected is not None else ""))
    contents["OnFrame"] = body.rstrip() + "\n" + "\n".join(lines) + "\n"
    for section in ("OnFrame_Enabled", "OnFrame_Disabled"):
        content = contents.get(section, "")
        contents[section] = "\n".join(line for line in content.splitlines()
                                     if line.strip() != "$" + PATCH_NAME).strip() + "\n"
    contents["OnFrame_Enabled"] += "$" + PATCH_NAME + "\n"
    output += "".join(f"[{name}]\n{body.strip()}\n\n" for name, body in contents.items())
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix(".ini.orre-tmp")
    pending.write_text(output, encoding="utf-8")
    pending.replace(path)
