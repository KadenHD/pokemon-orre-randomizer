"""Append Shadow Lugia HUD faces without changing existing native resources."""
from __future__ import annotations

import hashlib
from pathlib import Path
import struct

from .actor_archive import append_actor_models
from .analyze_game import FormatError, parse_fsys, u32
from .rebuild_iso import decoded_member
from .shadow_lugia_palette import make_shadow_lugia_portrait
from ..portrait_matte import matte_shadow_lugia_portrait

VERSION = "shadow-lugia-black-matte-face-v4"
XD_VERSION = "shadow-lugia-specimen-round-face-v6"
XD_ARTWORK_SIZE = 36
ARCHIVE = "poke_face.fsys"
GROUP = 0x5C0
SOURCE_RESOURCE = 0x21581200
SHINY_RESOURCE = 0x7DF51200
NORMAL_RESOURCE = 0x7DF71200
COLOSSEUM_RESOURCE = 0x7DF61200
XD_NORMAL_FACE_ID, XD_SHINY_FACE_ID = 0x7F00, 0x7F01
_XD_GETTERS = {'GXXP01': (0x8011389C, 0x80145A20),
               'GXXE01': (0x80112158, 0x8014415C),
               'GXXJ01': (0x8010D978, 0x8013F568)}
_GETTER_TAIL = bytes.fromhex('280300004082000c386000004800000880630004800100147c0803a6382100104e800020')
_RARE_CHECK = bytes.fromhex(
    '5465843e5460043e5486843e5484043e7ca30278380000087cc31a787c831a78'
    '7c0018107c0001107c6000d04e800020')
_XD_FACE_SELECTORS = {'GXXP01': 0x80112FF0, 'GXXE01': 0x801118AC,
                      'GXXJ01': 0x8010D0CC}


def _xd_face_variant_stub(address, continuation, rare_check):
    """Route a genuine Lugia's dark face using that specimen's own PID/OT."""
    from .shiny_rules import _Code
    from .gift_move_hooks import branch
    code = _Code(address)
    code.emit(0x9421FFE0, 0x7C0802A6, 0x90010024,
              0x807C0024, 0x809C0028)  # r28 is this request's real Pokemon*
    code.call(rare_check)
    code.emit(0x28030000)
    code.conditional(0x41820000, 'normal')
    code.emit(0x38600000 | XD_SHINY_FACE_ID)
    code.jump('restore')
    code.label('normal')
    code.emit(0x38600000 | XD_NORMAL_FACE_ID)
    code.label('restore')
    code.emit(0x80010024, 0x7C0803A6, 0x38210020)
    code.emit(branch(address+len(code.words)*4, continuation))
    return code.finish()


def _xd_face_descriptor_stub(address, continuation):
    """Share native dark-face geometry while keeping palette cache keys distinct."""
    from .shiny_rules import _Code
    from .gift_move_hooks import branch
    code = _Code(address)
    code.emit(0x28030000 | XD_NORMAL_FACE_ID)
    code.conditional(0x41820000, 'descriptor')
    code.emit(0x28030000 | XD_SHINY_FACE_ID)
    code.conditional(0x40820000, 'native')
    code.label('descriptor')
    code.emit(0x38600345)
    code.label('native')
    code.emit(0x9421FFF0)
    code.emit(branch(address+len(code.words)*4, continuation))
    return code.finish()


def _xd_face_texid_stub(address, continuation, state, identity, rare_check, *, fallback=False):
    from .shiny_rules import _Code
    from .gift_move_hooks import branch
    from ..xd_spinda import _load_address
    code = _Code(address)
    code.emit(0x28030000 | XD_NORMAL_FACE_ID)
    code.conditional(0x41820000, 'direct_normal')
    code.emit(0x28030000 | XD_SHINY_FACE_ID)
    code.conditional(0x41820000, 'direct_shiny')
    code.emit(0x28030345)
    code.conditional(0x40820000, 'native')
    code.emit(0x9421FFE0, 0x7C0802A6, 0x90010024, 0x90610008, 0x38600049)
    code.call(state.shadow_seen)
    code.emit(0x28030000)
    code.conditional(0x41820000, 'not_generated')
    code.emit(0x38600049)
    code.call(state.shadow_pid)
    code.emit(0x9061000C, 0x38600000, 0x38800002)
    code.call(identity.player_lookup)
    code.emit(0x28030000)
    code.conditional(0x41820000, 'normal')
    code.emit(0x8063002C, 0x8081000C)
    code.call(rare_check)
    code.emit(0x28030000)
    code.conditional(0x41820000, 'normal')
    code.jump('variant')
    code.label('not_generated')
    if not fallback:
        code.jump('normal')
    code.label('variant')
    _load_address(code, 3, SHINY_RESOURCE)
    code.jump('return')
    code.label('normal')
    _load_address(code, 3, NORMAL_RESOURCE)
    code.label('return')
    code.emit(0x80010024, 0x7C0803A6, 0x38210020, 0x4E800020)
    code.label('native')
    code.emit(0x9421FFF0)
    code.emit(branch(address+4*len(code.words), continuation))
    code.label('direct_normal')
    _load_address(code, 3, NORMAL_RESOURCE)
    code.emit(0x4E800020)
    code.label('direct_shiny')
    _load_address(code, 3, SHINY_RESOURCE)
    code.emit(0x4E800020)
    return code.finish()


def install_xd_shadow_lugia_face(original, current, game_id, *, fallback=False):
    """Select the saved shiny face before native load/copy/cache/draw stages."""
    from .gift_move_hooks import branch
    from ..xd_battle_rules import TEXT1_TO_RAM, append_xd_dol_text
    from ..xd_shadow_shinies import _LAYOUTS as IDENTITIES
    from ..xd_spinda_field import _LAYOUTS as SHADOW_STATE
    identity = IDENTITIES.get(game_id)
    if identity is None or hashlib.sha256(original).hexdigest() != identity.original_sha256:
        raise FormatError('unexpected original XD face executable')
    hook, rare_check = _XD_GETTERS[game_id]
    # The native GetPtr is adjacent in all three independently checked DOLs.
    expected = bytes.fromhex('9421fff07c0802a690010014')
    expected += struct.pack('>I', branch(hook+12, hook+52, link=True))+_GETTER_TAIL
    position = hook-TEXT1_TO_RAM
    for data in (original, current):
        if (data[position:position+len(expected)] != expected
                or data[rare_check-TEXT1_TO_RAM:rare_check-TEXT1_TO_RAM+len(_RARE_CHECK)] != _RARE_CHECK):
            raise FormatError('unexpected native XD face identity window')
    selector = _XD_FACE_SELECTORS[game_id]
    descriptor = hook+52
    for data in (original, current):
        if (u32(data, selector-TEXT1_TO_RAM) != 0x38600345
                or data[descriptor-TEXT1_TO_RAM:descriptor-TEXT1_TO_RAM+12] != bytes.fromhex(
                    '9421fff07c0802a690010014')):
            raise FormatError('unexpected native XD specimen face selector')
    output, hooks = append_xd_dol_text(original, current, game_id, ((hook, 0x9421FFF0,
        lambda address, continuation: _xd_face_texid_stub(address, continuation,
            SHADOW_STATE[game_id], identity, rare_check, fallback=fallback)),
        (selector, 0x38600345, lambda address, continuation:
            _xd_face_variant_stub(address, continuation, rare_check)),
        (descriptor, 0x9421FFF0, lambda address, continuation:
            _xd_face_descriptor_stub(address, continuation))))
    return output, {'version': XD_VERSION, 'face_id': 0x345, 'group': GROUP,
                    'source_resource': SOURCE_RESOURCE, 'shiny_resource': SHINY_RESOURCE,
                    'normal_resource': NORMAL_RESOURCE,
                    'saved_shadow_id': 73, 'ungenerated_seeded_fallback': bool(fallback),
                    'specimen_face_ids': (XD_NORMAL_FACE_ID, XD_SHINY_FACE_ID),
                    'all_shadow_lugia_use_native_specimen_pid': True,
                    'scope': 'native texture ID before load, cache registration and display', 'hooks': hooks}


def make_colosseum_shadow_lugia_face(template: bytes, normal: bytes, shiny: bytes) -> bytes:
    """Encode the two 42px faces in Colosseum's existing tiled RGBA8 format."""
    if (len(template) != 14912 or template[:12] != struct.pack(">HHBBHI", 42, 84, 32, 1, 0, 0x45)
            or u32(template, 0x28) != 128 or len(normal) != 42*42*4 or len(shiny) != 42*42*4):
        raise FormatError("unexpected Colosseum Pokémon face texture")
    pixels = normal+shiny
    output = bytearray(template[:128])
    for by in range(0, 84, 4):
        for bx in range(0, 42, 4):
            block = [pixels[((by+dy)*42+bx+dx)*4:((by+dy)*42+bx+dx+1)*4]
                     if bx+dx < 42 else bytes(4) for dy in range(4) for dx in range(4)]
            output.extend(value for r, g, b, a in block for value in (a, r))
            output.extend(value for r, g, b, a in block for value in (g, b))
    assert len(output) == len(template)
    return bytes(output)


def append_colosseum_shadow_lugia_face(archive: bytes, *, normal=None, shiny=None) -> tuple[bytes, dict]:
    """Append one two-frame atlas; the caller assigns its virtual native IDs."""
    if u32(archive, 8) != GROUP:
        raise FormatError("unexpected Colosseum Pokémon face archive group")
    candidates = [row for row in parse_fsys(archive)['members'] if row['name'] == 'face249'
                  and int(row['identifier_raw'], 16) & 0xFF00 == 0x1200]
    if len(candidates) != 1:
        raise FormatError("expected one native Colosseum Lugia face")
    if normal is None or shiny is None:
        from ..artwork import _png_pixels
        pack = Path(__file__).resolve().parents[1]/'assets/game/models'
        normal = _png_pixels((pack/'dark-lugia.png').read_bytes(), (42, 42))
        shiny = _png_pixels((pack/'dark-lugia-shiny.png').read_bytes(), (42, 42))
        reference = normal
        normal = matte_shadow_lugia_portrait(normal, reference=reference)
        shiny = matte_shadow_lugia_portrait(shiny, reference=reference)
    source = decoded_member(archive, candidates[0])
    atlas = make_colosseum_shadow_lugia_face(source, normal, shiny)
    output = append_actor_models(archive, {}, archive, int(candidates[0]['identifier_raw'], 16),
                                 {COLOSSEUM_RESOURCE: ('face249dark_bonus', atlas)}, resource_type=0x1200)
    return output, {'version': VERSION, 'archive': ARCHIVE, 'group': GROUP,
                    'resource': COLOSSEUM_RESOURCE, 'native_format': 'RGBA8 / 42x84',
                    'normal_member_unchanged': True,
                    'background': 'opaque black, original outer Shadow frame unchanged',
                    'atlas_sha256': hashlib.sha256(atlas).hexdigest()}


def make_xd_shadow_lugia_round_portrait(pixels: bytes, *, reference: bytes) -> bytes:
    """Contain the complete native head inside XD's original circular alpha.

    XD draws this 42px tile in a round status frame. Keep its original alpha
    mask, fill only the inside with black, and center a 36px rendering of the
    complete source artwork. Integer area averaging retains contributions
    from every source pixel without inventing a crop or an external library.
    Colosseum and the interface's square portrait do not use this function.
    """
    source_size = 42
    matte = matte_shadow_lugia_portrait(pixels, reference=reference)
    size = XD_ARTWORK_SIZE
    padding = (source_size-size)//2
    spans = []
    for destination in range(size):
        left, right = destination*source_size, (destination+1)*source_size
        spans.append([(sample, min((sample+1)*size, right)-max(sample*size, left))
                      for sample in range(left//size, (right-1)//size+1)])
    output = bytearray(source_size*source_size*4)
    output[3::4] = reference[3::4]
    area = source_size*source_size
    for y, vertical in enumerate(spans):
        for x, horizontal in enumerate(spans):
            at = ((y+padding)*source_size+x+padding)*4
            if not output[at+3]:
                continue
            for channel in range(3):
                total = sum(matte[(sy*source_size+sx)*4+channel]*wx*wy
                            for sy, wy in vertical for sx, wx in horizontal)
                output[at+channel] = (total+area//2)//area
    return bytes(output)


def make_shadow_lugia_face_texture(source: bytes, *, shiny=True) -> bytes:
    """Repack native CI8 so eye-mask colors never leak into shared whites."""
    # Native face249dark has two identical 42px frames sharing one RGB5A3
    # palette. Its ordinary face descriptor always selects the second frame.
    # A distinct resource lets saved-identity routing retain both normal frames.
    if (len(source) != 4672 or source[:12] != struct.pack(">HHBBHI", 42, 84, 8, 1, 0, 1)
            or u32(source, 0xC) != 3 or u32(source, 0x28) != 128
            or u32(source, 0x48) != 4160):
        raise FormatError("unexpected original Shadow Lugia face texture")
    from ..artwork import _texture
    original = _texture(source, (42, 84))
    frames = [original[start:start+42*42*4] for start in (0, 42*42*4)]
    pixels = b''.join(make_xd_shadow_lugia_round_portrait(
        make_shadow_lugia_portrait(frame) if shiny else frame, reference=frame) for frame in frames)
    result = bytearray(source[:128]+bytes(4544))
    palette = {}
    for y in range(84):
        for x in range(42):
            at = (y*42+x)*4
            sample = 128+(y//4)*6*32+(x//8)*32+(y%4)*8+x%8
            r, g, b, alpha = pixels[at:at+4]
            if pixels[at:at+4] == original[at:at+4]:
                # Opaque RGB5A3 may use either RGB555 or A3RGB444. Retain the
                # exact native word for unchanged eyes/teeth/backdrop, avoiding
                # even a one-unit channel round trip between those modes.
                encoded, = struct.unpack_from('>H', source, 4160+source[sample]*2)
            elif alpha == 255:
                r, g, b = ((v*31+127)//255 for v in (r, g, b))
                encoded = 0x8000 | r << 10 | g << 5 | b
            else:
                r, g, b = ((v*15+127)//255 for v in (r, g, b))
                encoded = ((alpha*7+127)//255) << 12 | r << 8 | g << 4 | b
            if encoded not in palette:
                if len(palette) == 256:
                    raise FormatError('Shadow Lugia face exceeds the native CI8 palette')
                palette[encoded] = len(palette)
                struct.pack_into('>H', result, 4160+palette[encoded]*2, encoded)
            result[sample] = palette[encoded]
    return bytes(result)


def append_shadow_lugia_shiny_face(archive: bytes) -> tuple[bytes, dict]:
    """Append native round normal/shiny faces; retain the original source."""
    if u32(archive, 8) != GROUP:
        raise FormatError("unexpected native Pokémon face archive group")
    members = parse_fsys(archive)['members']
    candidates = [row for row in members if row['name'] == 'face249dark'
                  and int(row['identifier_raw'], 16) == SOURCE_RESOURCE]
    if len(candidates) != 1:
        raise FormatError("expected one native Shadow Lugia face")
    source = decoded_member(archive, candidates[0])
    normal = make_shadow_lugia_face_texture(source, shiny=False)
    rare = make_shadow_lugia_face_texture(source)
    output = append_actor_models(archive, {}, archive, SOURCE_RESOURCE,
                                 {NORMAL_RESOURCE: ('face249dark_black', normal),
                                  SHINY_RESOURCE: ('face249dark_shiny', rare)}, resource_type=0x1200)
    report = {'version': XD_VERSION, 'archive': ARCHIVE, 'group': GROUP,
              'source_resource': SOURCE_RESOURCE, 'shiny_resource': SHINY_RESOURCE,
              'normal_resource': NORMAL_RESOURCE, 'normal_sha256': hashlib.sha256(normal).hexdigest(),
              'source_sha256': hashlib.sha256(source).hexdigest(),
              'shiny_sha256': hashlib.sha256(rare).hexdigest(),
              'normal_member_unchanged': True, 'native_format': 'CI8 / RGB5A3',
              'header_unchanged': True, 'native_circular_alpha_unchanged': True,
              'black_background_inside_circle': True, 'artwork_size': XD_ARTWORK_SIZE,
              'eye_mask_palette_split': True}
    return output, report
