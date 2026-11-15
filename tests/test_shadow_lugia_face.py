"""Native HUD face palettes retain normal resources, opacity and red irises."""
import struct
from types import SimpleNamespace
import unittest
import json
import hashlib
from pathlib import Path

from orre_randomizer.artwork import _texture, _png_pixels
from orre_randomizer.engine.analyze_game import FormatError, parse_fsys
from orre_randomizer.engine.rebuild_iso import compress_lzss, decoded_member
from orre_randomizer.engine.shadow_lugia_face import (
    GROUP, SOURCE_RESOURCE, NORMAL_RESOURCE, SHINY_RESOURCE, make_shadow_lugia_face_texture,
    COLOSSEUM_RESOURCE, append_shadow_lugia_shiny_face,
    make_colosseum_shadow_lugia_face, append_colosseum_shadow_lugia_face,
    _xd_face_texid_stub, install_xd_shadow_lugia_face,
    XD_NORMAL_FACE_ID, XD_SHINY_FACE_ID, _xd_face_variant_stub, _xd_face_descriptor_stub,
    make_xd_shadow_lugia_round_portrait, XD_ARTWORK_SIZE,
)
from orre_randomizer.engine.shadow_lugia_palette import make_shadow_lugia_portrait
from orre_randomizer.portrait_matte import matte_shadow_lugia_portrait, shadow_lugia_background_mask
from tests.test_xd_shadow_shinies import ADDRESS, RETURN, WrapperMachine


def texture():
    data = bytearray(4672)
    struct.pack_into('>HHBBHI', data, 0, 42, 84, 8, 1, 0, 1)
    for at, value in ((0xC, 3), (0x28, 128), (0x48, 4160)):
        struct.pack_into('>I', data, at, value)
    for y in range(84):
        for x in range(42):
            data[128+(y//4)*6*32+(x//8)*32+(y%4)*8+x%8] = x//7
    struct.pack_into('>6H', data, 4160, 0xA134, 0xFC43, 0xFFFF, 0x8000, 0x3145, 0x0015)
    return bytes(data)


def colosseum_texture():
    data = bytearray(14912)
    struct.pack_into('>HHBBHI', data, 0, 42, 84, 32, 1, 0, 0x45)
    struct.pack_into('>I', data, 0x28, 128)
    return bytes(data)


def archive(colosseum=False):
    rows = [('face249', 0x0EFE1200, colosseum_texture())] if colosseum else [('face249dark', SOURCE_RESOURCE, texture())]
    rows.append(('unrelated', 0x12341200, b'ordinary-resource'))
    stride = 0x50 if colosseum else 0x70
    data = bytearray(0x80+len(rows)*stride)
    data[:4] = b'FSYS'
    for at, value in ((4, 0x102 if colosseum else 0x201), (8, GROUP), (0xC, len(rows)), (0x40, 0x60)):
        struct.pack_into('>I', data, at, value)
    for index, (name, ident, raw) in enumerate(rows):
        header = 0x80+index*stride
        struct.pack_into('>I', data, 0x60+index*4, header)
        struct.pack_into('>I', data, header+0x24, len(data))
        data.extend(name.encode('ascii')+b'\0')
        data.extend(bytes(-len(data)%32))
        stored = compress_lzss(raw)
        for field, value in ((0, ident), (4, len(data)), (8, len(raw)), (0x14, len(stored))):
            struct.pack_into('>I', data, header+field, value)
        data.extend(stored)
    data.extend(bytes(-len(data)%32+28)+b'FSYS')
    struct.pack_into('>I', data, 0x20, len(data))
    return bytes(data)


class ShadowLugiaFaceTests(unittest.TestCase):
    def test_xd_specimen_face_reads_its_own_pid_and_owner_for_every_shadow_slot(self):
        rare_check, specimen = 0x80103000, 0x80603000
        for shadow in (1, 30, 73, 83):
            for rare in (False, True):
                with self.subTest(shadow=shadow, rare=rare):
                    machine = WrapperMachine(_xd_face_variant_stub(ADDRESS, RETURN, rare_check))
                    machine.reg[28] = specimen
                    machine.store(specimen, 249, 2)
                    machine.store(specimen+0xBA, shadow, 2)
                    pid = 0xABCDEF01
                    owner = (pid >> 16) ^ (pid & 65535) ^ (0 if rare else 8)
                    machine.store(specimen+0x24, owner, 4)
                    machine.store(specimen+0x28, pid, 4)
                    before, memory = machine.reg.copy(), machine.memory.copy()

                    def native(m):
                        self.assertEqual(m.reg[3:5], [owner, pid])
                        m.clobber_volatile()
                        m.reg[3] = int(rare)

                    machine.callbacks[rare_check] = native
                    machine.run()
                    self.assertEqual(machine.reg[3], XD_SHINY_FACE_ID if rare else XD_NORMAL_FACE_ID)
                    self.assertEqual(machine.reg[1:3], before[1:3])
                    self.assertEqual(machine.reg[13:], before[13:])
                    self.assertTrue(all(machine.memory.get(k) == v for k, v in memory.items()))

    def test_xd_virtual_face_ids_have_distinct_textures_and_shared_native_descriptor(self):
        state = SimpleNamespace(shadow_seen=0x80101000, shadow_pid=0x80101010)
        identity = SimpleNamespace(player_lookup=0x80101020)
        native = 0x80104000
        for face, texture_id in ((XD_NORMAL_FACE_ID, NORMAL_RESOURCE),
                                  (XD_SHINY_FACE_ID, SHINY_RESOURCE)):
            machine = WrapperMachine(_xd_face_texid_stub(ADDRESS, native, state, identity, 0x80101030))
            machine.reg[3] = face
            before, memory = machine.reg.copy(), machine.memory.copy()
            machine.run()
            self.assertEqual(machine.reg[3], texture_id)
            self.assertEqual(machine.reg[1:3], before[1:3])
            self.assertEqual(machine.reg[4:], before[4:])
            self.assertEqual(machine.memory, memory)
            self.assertEqual(machine.calls, [])
        for face in (XD_NORMAL_FACE_ID, XD_SHINY_FACE_ID, 0, 249, 0x345, 0x7F02):
            machine = WrapperMachine(_xd_face_descriptor_stub(ADDRESS, native))
            machine.reg[3] = face
            before = machine.reg.copy()

            def descriptor(m):
                self.assertEqual(m.reg[3], 0x345 if face in (XD_NORMAL_FACE_ID, XD_SHINY_FACE_ID) else face)
                self.assertEqual(m.reg[1], before[1]-16)
                m.reg[1] += 16

            machine.callbacks[native] = descriptor
            machine.run()
            self.assertEqual(machine.reg[1:3], before[1:3])
            self.assertEqual(machine.reg[4:], before[4:])

    def test_xd_texture_id_uses_saved_identity_with_native_abi_and_seed_fallback(self):
        seen, saved, player_lookup, rare_check, native = (0x80100100, 0x80100200, 0x80100300, 0x80100400, 0x80100500)
        player = 0x80600000
        state = SimpleNamespace(shadow_seen=seen, shadow_pid=saved)
        identity = SimpleNamespace(player_lookup=player_lookup)
        for face, generated, hero, rare, fallback, expected_rare in (
                (0x345, 1, player, True, False, True),
                (0x345, 1, player, False, True, False),
                (0x345, 1, 0, True, True, False),
                (0x345, 0, player, False, True, True),
                (0x345, 0, player, True, False, False),
                (249, 1, player, True, True, False),
                (0x344, 1, player, True, True, False),
                (0x346, 1, player, True, True, False)):
            with self.subTest(face=face, generated=generated, hero=hero, rare=rare, fallback=fallback):
                machine = WrapperMachine(_xd_face_texid_stub(ADDRESS, native, state, identity, rare_check, fallback=fallback))
                machine.reg[3] = face
                machine.store(player+0x2C, 0x12345678, 4)
                original = machine.reg.copy()
                original_memory = machine.memory.copy()

                def result(m, value):
                    m.clobber_volatile()
                    m.reg[3] = value

                def seen_call(m):
                    self.assertEqual(m.reg[3], 73)
                    result(m, generated)

                def pid_call(m):
                    self.assertEqual(m.reg[3], 73)
                    result(m, 0xABCDEF81)

                def player_call(m):
                    self.assertEqual(m.reg[3:5], [0, 2])
                    result(m, hero)

                def rare_call(m):
                    self.assertEqual(m.reg[3:5], [0x12345678, 0xABCDEF81])
                    result(m, rare)

                def native_call(m):
                    self.assertEqual(m.reg[3], face)
                    self.assertEqual(m.reg[1], original[1]-16)  # replayed retail prologue
                    m.reg[1] += 16
                    result(m, SOURCE_RESOURCE)

                machine.callbacks = {seen: seen_call, saved: pid_call, player_lookup: player_call,
                                     rare_check: rare_call, native: native_call}
                machine.run()
                self.assertEqual(machine.reg[3], SHINY_RESOURCE if expected_rare else
                                 NORMAL_RESOURCE if face == 0x345 else SOURCE_RESOURCE)
                self.assertEqual(machine.reg[1:3], original[1:3])
                self.assertEqual(machine.reg[13:], original[13:])
                self.assertEqual(machine.lr, RETURN)
                self.assertEqual(machine.load(player+0x2C, 4), 0x12345678)
                self.assertTrue(all(value == machine.memory.get(at)
                                    for at, value in original_memory.items()))
                if face != 0x345:
                    self.assertEqual([target for target, _ in machine.calls], [native])
                if not generated:
                    self.assertNotIn(saved, [target for target, _ in machine.calls])

    def test_xd_face_hook_rejects_unknown_or_modified_executables(self):
        for game in ('invalid', 'GXXP01'):
            with self.subTest(game=game), self.assertRaises(FormatError):
                install_xd_shadow_lugia_face(bytes(256), bytes(256), game)

    def test_colosseum_native_rgba8_atlas_has_distinct_lossless_normal_and_shiny_frames(self):
        normal = bytes((21, 33, 62, 253))*(42*42)
        shiny = bytes((237, 239, 241, 127))*(42*42)
        template = colosseum_texture()
        output = make_colosseum_shadow_lugia_face(template, normal, shiny)
        self.assertEqual(template[:128], output[:128])
        self.assertEqual(_texture(output, (42, 84)), normal+shiny)
        with self.assertRaises(FormatError):
            make_colosseum_shadow_lugia_face(template, normal[:-1], shiny)

        source = archive(colosseum=True)
        result, report = append_colosseum_shadow_lugia_face(source, normal=normal, shiny=shiny)
        before, after = parse_fsys(source)['members'], parse_fsys(result)['members']
        self.assertEqual([row['sha256_stored'] for row in before],
                         [row['sha256_stored'] for row in after[:-1]])
        self.assertEqual(int(after[-1]['identifier_raw'], 16), COLOSSEUM_RESOURCE)
        self.assertEqual(_texture(decoded_member(result, after[-1]), (42, 84)), normal+shiny)
        self.assertTrue(report['normal_member_unchanged'])

    def test_native_format_preserves_alpha_and_encodes_round_face(self):
        source = texture()
        output = make_shadow_lugia_face_texture(source)
        self.assertEqual(len(output), len(source))
        self.assertEqual(source[:128], output[:128])
        before, after = (_texture(blob, (42, 84)) for blob in (source, output))
        self.assertEqual(after[3::4], before[3::4])
        self.assertNotEqual(before, after)
        expected = b''.join(make_xd_shadow_lugia_round_portrait(
            make_shadow_lugia_portrait(before[start:start+42*42*4]),
            reference=before[start:start+42*42*4]) for start in (0,42*42*4))
        for index in range(0, len(before), 4):
            if before[index:index+4] == expected[index:index+4]:
                self.assertEqual(before[index:index+4], after[index:index+4])
            else:
                error = 4 if expected[index+3] == 255 else 8  # RGB555 / A3RGB444
                self.assertTrue(all(abs(a-b) <= error for a, b in
                                    zip(expected[index:index+3], after[index:index+3])))

    def test_shared_white_palette_is_split_only_for_the_eye_mask_not_teeth(self):
        source = bytearray(texture())
        source[128:4160] = bytes((2,))*4032  # one white entry shared by every region
        for base in (0,42):
            for y in range(base+12,base+18):
                for x in range(23,29):
                    source[128+(y//4)*6*32+(x//8)*32+(y%4)*8+x%8] = 1  # red iris
        struct.pack_into('>H', source, 4160+6*2, 0x7C53)  # opaque A3RGB444 red/brown
        for base in (0,42):
            for y in range(base+30,base+35):
                for x in range(8,13):
                    source[128+(y//4)*6*32+(x//8)*32+(y%4)*8+x%8] = 6
        before, after = (_texture(blob, (42, 84)) for blob in (source, make_shadow_lugia_face_texture(bytes(source))))
        for base in (0, 42):
            def pixel(data, x, y):
                at = ((y+base)*42+x)*4
                return data[at:at+4]
            self.assertEqual(pixel(before, 25, 14), pixel(after, 24, 15))
            self.assertLess(max(pixel(after, 33, 12)[:3]), 48)
            self.assertEqual(pixel(before, 18, 27), pixel(after, 18, 26))  # teeth
            self.assertEqual(pixel(before, 30, 5), pixel(after, 29, 7))  # forehead
            self.assertEqual(pixel(before, 12, 31), pixel(after, 12, 31))  # opaque RGB444 exact

    def test_append_keeps_every_existing_compressed_member(self):
        source = archive()
        output, report = append_shadow_lugia_shiny_face(source)
        before, after = parse_fsys(source)['members'], parse_fsys(output)['members']
        self.assertEqual(len(after), len(before)+2)
        for old, new in zip(before, after, strict=False):
            self.assertEqual(old['identifier_raw'], new['identifier_raw'])
            self.assertEqual(old['sha256_stored'], new['sha256_stored'])
            self.assertEqual(decoded_member(source, old), decoded_member(output, new))
        self.assertEqual(int(after[-1]['identifier_raw'], 16), SHINY_RESOURCE)
        self.assertEqual(decoded_member(output, after[-1]), make_shadow_lugia_face_texture(texture()))
        normal = next(row for row in after if int(row['identifier_raw'],16) == NORMAL_RESOURCE)
        self.assertEqual(decoded_member(output,normal),make_shadow_lugia_face_texture(texture(),shiny=False))
        self.assertEqual(report['group'], GROUP)
        self.assertTrue(report['normal_member_unchanged'])
        self.assertTrue(report['black_background_inside_circle'])
        self.assertTrue(report['native_circular_alpha_unchanged'])
        with self.assertRaises(FormatError):
            append_shadow_lugia_shiny_face(output)

    def test_other_formats_and_archive_groups_are_rejected(self):
        for source in (b'', texture()[:-1], bytes(4672)):
            with self.subTest(length=len(source)), self.assertRaises(FormatError):
                make_shadow_lugia_face_texture(source)
        source = bytearray(archive())
        struct.pack_into('>I', source, 8, GROUP+1)
        with self.assertRaises(FormatError):
            append_shadow_lugia_shiny_face(bytes(source))

    def test_default_colosseum_atlas_matches_opaque_interface_faces(self):
        pack=Path(__file__).resolve().parents[1]/'orre_randomizer/assets/game/models'
        if not (pack/'dark-lugia.png').exists():
            self.skipTest('requires optional game interface pack')
        output,report=append_colosseum_shadow_lugia_face(archive(colosseum=True))
        member=next(row for row in parse_fsys(output)['members']if int(row['identifier_raw'],16)==COLOSSEUM_RESOURCE)
        frames=_texture(decoded_member(output,member),(42,84))
        expected=b''.join(_png_pixels((pack/name).read_bytes(),(42,42))for name in
                          ('dark-lugia-ui.png','dark-lugia-shiny-ui.png'))
        self.assertEqual(frames,expected)
        self.assertEqual(frames[3::4],bytes((255,))*(42*84))
        reference=_png_pixels((pack/'dark-lugia.png').read_bytes(),(42,42))
        for index in shadow_lugia_background_mask(reference):
            for start in (0,42*42*4):
                at=start+index*4
                self.assertEqual(frames[at:at+4],b'\0\0\0\xff')
        self.assertIn('opaque black',report['background'])

    def test_real_xd_faces_keep_native_circle_and_contain_entire_source_artwork(self):
        root=Path(__file__).resolve().parents[1]
        source_path=root/'build/v1220-snag-qa/face249dark-original.bin'
        manifest=root/'orre_randomizer/assets/game/models/manifest.json'
        if not source_path.exists()or not manifest.exists():
            self.skipTest('requires locally retained verified native XD face')
        source=source_path.read_bytes()
        self.assertEqual(hashlib.sha256(source).hexdigest(),json.loads(manifest.read_text('utf8'))['portrait']['decoded_sha256'])
        original=_texture(source,(42,84))
        for shiny in (False,True):
            actual=_texture(make_shadow_lugia_face_texture(source,shiny=shiny),(42,84))
            self.assertEqual(actual[3::4],original[3::4])
            for start in (0,42*42*4):
                frame=original[start:start+42*42*4]
                expected=make_xd_shadow_lugia_round_portrait(make_shadow_lugia_portrait(frame)if shiny else frame,reference=frame)
                for index in range(42*42):
                    at=index*4
                    self.assertTrue(all(abs(a-b)<=4 for a,b in zip(actual[start+at:start+at+3],expected[at:at+3])))
                    if not frame[at+3]:
                        self.assertEqual(actual[start+at:start+at+4],bytes(4))
                    if index%42<3 or index%42>38 or index//42<3 or index//42>38:
                        self.assertEqual(actual[start+at:start+at+3],bytes(3))
                    if any(actual[start+at:start+at+3]):
                        x,y=index%42,index//42
                        for ny in range(y-1,y+2):
                            for nx in range(x-1,x+2):
                                self.assertTrue(0<=nx<42 and 0<=ny<42)
                                self.assertEqual(frame[(ny*42+nx)*4+3],255)

                # Every non-black source-artwork pixel contributes wholly to
                # opaque destination pixels. The circle never clips a beak,
                # neck, jaw or antialiased silhouette pixel during fitting.
                matte=matte_shadow_lugia_portrait(frame,reference=frame)
                for index in range(42*42):
                    if not any(matte[index*4:index*4+3]):
                        continue
                    sx,sy=index%42,index//42
                    for dy in range(sy*36//42,((sy+1)*36-1)//42+1):
                        for dx in range(sx*36//42,((sx+1)*36-1)//42+1):
                            self.assertEqual(frame[((dy+3)*42+dx+3)*4+3],255)

        archive_path=root/'build/v1220-snag-qa/poke_face-xd-original.fsys'
        if archive_path.exists():
            native=archive_path.read_bytes()
            for member in parse_fsys(native)['members']:
                if member['name']in('face009','face133','face249'):
                    self.assertEqual(_texture(decoded_member(native,member),(42,84))[3::4],original[3::4])

    def test_area_fit_retains_small_source_features_and_black_padding(self):
        self.assertEqual(XD_ARTWORK_SIZE,36)
        source=bytearray(bytes((0,0,0,255))*(42*42))
        source[(21*42+21)*4:(21*42+21)*4+4]=bytes((255,0,0,255))
        fitted=make_xd_shadow_lugia_round_portrait(bytes(source),reference=bytes(source))
        self.assertGreater(sum(fitted[0::4]),0)  # a one-pixel iris cannot disappear
        self.assertEqual(fitted[3::4],source[3::4])
        for y in range(42):
            for x in range(42):
                if x<3 or x>38 or y<3 or y>38:
                    self.assertEqual(fitted[(y*42+x)*4:(y*42+x)*4+3],bytes(3))

    def test_face_hook_installs_against_three_original_xd_executables(self):
        root=Path(__file__).resolve().parents[1]/'build/xd-validation'
        cases=(('eu','GXXP01'),('us','GXXE01'),('jp','GXXJ01'))
        if not all((root/tag/'main.dol').exists()for tag,_ in cases):
            self.skipTest('requires local extracted EU/US/JP original XD executables')
        for tag,game in cases:
            source=(root/tag/'main.dol').read_bytes()
            for fallback in (False,True):
                output,report=install_xd_shadow_lugia_face(source,source,game,fallback=fallback)
                self.assertEqual(report['normal_resource'],NORMAL_RESOURCE)
                self.assertEqual(report['shiny_resource'],SHINY_RESOURCE)
                self.assertGreater(len(output),len(source))
                self.assertEqual((root/tag/'main.dol').read_bytes(),source)


if __name__ == '__main__':
    unittest.main()
