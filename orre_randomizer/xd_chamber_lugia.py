"""Give each Shadow Lugia its own animated Purify Chamber palette.

Only a new CI8 palette/sprite resource and display selectors are installed.
The retail ANT animation commands, three poses and saved specimen stay intact.
This native-size artwork is not an HD asset.
"""
from __future__ import annotations

import hashlib
import struct

from .artwork import _texture
from .engine.actor_archive import append_actor_models
from .engine.analyze_game import FormatError, parse_fsys, u32
from .engine.gift_move_hooks import branch
from .engine.rebuild_iso import decoded_member
from .engine.shiny_rules import _Code
from .xd_battle_rules import TEXT1_TO_RAM, append_xd_dol_text
from .xd_deoxys_runtime import ANT_LAYOUTS

VERSION = "xd-specimen-shadow-lugia-chamber-v1"
ARCHIVE, GROUP = "poke_dance.fsys", 0x825
SOURCE, SHINY = 0x20083200, 0x7DF93200
SOURCE_SHA256 = "1ed0fa34ff8925495559ac35e58184a2d6f0c764b167f36a0248800fdad789b2"
RARE = {"GXXP01": 0x8014D148, "GXXE01": 0x8014B884, "GXXJ01": 0x80146BE0}


def _pad(payload):
    return payload + bytes(-len(payload) % 32)


def _variant_stub(address, continuation, *, owner, rare):
    """Replace the hardcoded ANT ID using this constructor's real Pokemon*."""
    c = _Code(address)
    c.emit(0x9421FFC0, 0x7C0802A6, 0x90010044)
    for register in range(3, 13):
        c.emit(0x90010000 | register << 21 | (8 + (register - 3) * 4))
    # The replaced addi has no condition-register side effects. Preserve all
    # fields across the specimen getter as well as the constructor's GPRs.
    c.emit(0x7D800026, 0x91810030)  # mfcr r12; stw r12,0x30(r1)
    c.emit(0x7C030378 | owner << 21 | owner << 11)  # mr r3,owner
    c.call(rare)
    c.emit(0x28030000)
    c.conditional(0x41820000, "normal")
    c.emit(0x3C000000 | SHINY >> 16, 0x60000000 | SHINY & 0xFFFF)
    c.jump("restore")
    c.label("normal")
    c.emit(0x3C000000 | SOURCE >> 16, 0x60000000 | SOURCE & 0xFFFF)
    c.label("restore")
    c.emit(0x81810030, 0x7D8FF120)  # lwz r12,0x30(r1); mtcrf 0xff,r12
    c.emit(0x81810044, 0x7D8803A6)
    for register in range(3, 13):
        c.emit(0x80010000 | register << 21 | (8 + (register - 3) * 4))
    c.emit(0x38210040)
    c.emit(branch(address + len(c.words) * 4, continuation))
    return _pad(c.finish())


def make_shiny_ant(source: bytes) -> bytes:
    """Repaint native monochrome body/belly shades, retaining exact ANT poses.

    The white body/dark belly matches the registered custom 3D appearance.
    Native antialiased silhouettes and red eyes retain their authored words.
    """
    if (type(source) is not bytes or len(source) != 13088 or u32(source, 12) != 0xA0
            or hashlib.sha256(source).hexdigest() != SOURCE_SHA256):
        raise FormatError("unexpected original Shadow Lugia chamber ANT")
    tex = source[0xA0:]
    pixels = _texture(tex, (64, 192))
    output, palette = bytearray(source), {}
    for y in range(192):
        for x in range(64):
            at = (y * 64 + x) * 4
            r, g, b, alpha = pixels[at:at + 4]
            sample = 0x120 + (y // 4) * 256 + (x // 8) * 32 + (y % 4) * 8 + x % 8
            original = struct.unpack_from(">H", source, 0x3120 + source[sample] * 2)[0]
            edge = any(not (0 <= nx < 64 and y // 64 * 64 <= ny < y // 64 * 64 + 64)
                       or not pixels[(ny * 64 + nx) * 4 + 3]
                       for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)))
            encoded = original
            if alpha == 255 and r <= g + 12 and not edge:
                # Quantized material shades keep this a lossless CI8 resource;
                # no native silhouette pixels or timing commands are replaced.
                value = max(r, g, b)
                shade = (max(2, round(value * .12 / 8)) if value >= 145 else
                         min(31, round((190 + value * .40) / 8)))
                encoded = 0x8000 | shade << 10 | shade << 5 | min(31, shade + (value >= 145))
            if encoded not in palette:
                if len(palette) >= 256:
                    raise FormatError("Shadow Lugia chamber palette exceeds CI8")
                palette[encoded] = len(palette)
            output[sample] = palette[encoded]
    output[0x3120:0x3320] = bytes(512)
    for encoded, index in palette.items():
        struct.pack_into(">H", output, 0x3120 + index * 2, encoded)
    return bytes(output)


def install_chamber_lugia(original, current, game_id, read_archive, updates, *, keep_after_purification=False):
    """Append the animated rare sprite and qualify three regional CANT consumers."""
    from .castform_layouts import LAYOUTS
    from .xd_shadow_lugia_model import _retained_display_stub
    if (game_id not in ANT_LAYOUTS or type(keep_after_purification) is not bool
            or hashlib.sha256(original).hexdigest() != LAYOUTS[game_id]["sha256"]):
        raise FormatError("unexpected original XD chamber executable")
    archive = read_archive(ARCHIVE)
    directory = parse_fsys(archive)
    rows = [m for m in directory["members"] if int(m["identifier_raw"], 16) == SOURCE]
    if directory["group_id"] != GROUP or len(rows) != 1 or rows[0]["name"] != "darklugia":
        raise FormatError("unexpected native Shadow Lugia chamber resource")
    source = decoded_member(archive, rows[0])
    sprite = make_shiny_ant(source)
    current_archive = updates.get(ARCHIVE, archive)
    staged_directory = parse_fsys(current_archive)
    staged_sources = [m for m in staged_directory['members'] if int(m['identifier_raw'], 16) == SOURCE]
    if (staged_directory['group_id'] != GROUP or len(staged_sources) != 1 or
            decoded_member(current_archive, staged_sources[0]) != source):
        raise FormatError("pending chamber update changed the original Shadow Lugia ANT")
    staged = append_actor_models(current_archive, {}, archive, SOURCE,
        {SHINY: ("orre_darklugia_c", sprite)}, resource_type=0x3200)
    hooks = []
    for index, base in enumerate(ANT_LAYOUTS[game_id][:3]):
        owner, relative = (29, 0x100) if index == 2 else (30, 0xF4)
        hook = base + relative
        position = hook - TEXT1_TO_RAM
        expected = bytes.fromhex("3c60200838033200")
        if any(d[position - 4:position + 4] != expected for d in (original, current)):
            raise FormatError("unexpected native hardcoded Shadow Lugia chamber request")
        hooks.append((hook, 0x38033200, lambda a, c, owner=owner:
                      _variant_stub(a, c, owner=owner, rare=RARE[game_id])))
        if keep_after_purification:
            predicate = hook - 0x10
            pos = predicate - TEXT1_TO_RAM
            native = u32(original, pos)
            if (native >> 26 != 18 or native & 3 != 1 or
                    u32(current, pos) != native or
                    u32(original, pos - 4) != (0x7C030378 | owner << 21 | owner << 11)):
                raise FormatError("unexpected native chamber Shadow Lugia predicate")
            hooks.append((predicate, native, lambda a, _c: _pad(_retained_display_stub(a))))
    # Predicate hooks are calls; variant hooks are inline continuations.
    inline = hooks[::2] if keep_after_purification else hooks
    output, report = append_xd_dol_text(original, current, game_id, inline)
    if keep_after_purification:
        output, retained = append_xd_dol_text(original, output, game_id, hooks[1::2], link=True)
        report += retained
    updates[ARCHIVE] = staged
    return output, {"version": VERSION, "archive": ARCHIVE, "group": GROUP,
        "source_resource": SOURCE, "shiny_resource": SHINY, "hooks": report,
        "source_sha256": hashlib.sha256(source).hexdigest(),
        "shiny_sha256": hashlib.sha256(sprite).hexdigest(),
        "native_animation_and_alpha_preserved": True, "native_bitmap_upscaled_for_hd": False,
        "hd_artwork_included": False, "uses_actual_specimen_shiny_check": True,
        "keep_after_purification": keep_after_purification, "saved_identity_changed": False}
