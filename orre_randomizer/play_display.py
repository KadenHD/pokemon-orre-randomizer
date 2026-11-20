"""Per-run display settings; reversible camera patches never alter the ROM.

The projection hook follows Ralf's 16:9 code shipped in Dolphin's GC6P01,
GC6E01 and GXXP01 GameSettings. Other revision-0 regions use the same checked
MTXPerspective instruction sequence and regional r2 addresses. An existing
read-only 0.75 constant supplies both inverse camera scaling and 2D scaling;
no game variables or BSS tail are used for injected constants. Keep the
generic Dolphin widescreen hack off: applying both would widen the scene twice.
"""
from __future__ import annotations

from pathlib import Path
import re


DISPLAY_MODES = ("16:9", "4:3")
PATCH_NAME = "Orre display projection"
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


def projection_entries(game_id, wide):
    hook, r2, constant = PROJECTIONS[game_id]
    branch = _branch(hook, 0x80005300)
    ortho_return = hook + 0x144
    ortho_branch = _branch(ortho_return, 0x80005310)
    if not wide:
        # A state captured in wide mode may contain the hook. Restore only our
        # exact branch; never overwrite a different user-authored hook.
        return [(hook, 0xFFA01090, branch), (ortho_return, 0x4E800020, ortho_branch)]
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
