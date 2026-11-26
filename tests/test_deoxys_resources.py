"""Imported forms retain native DATs, timing, square artwork and HD provenance."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from orre_randomizer.artwork import _png, _texture
from orre_randomizer.deoxys_resources import (
    FACE_RESOURCES, FORMS, FORM_MEMBERS, MODEL_GROUPS, MODEL_RESOURCES,
    _convert_pkx, append_deoxys_resources, convert_deoxys_model,
    deoxys_hd_material_coverage, extract_xd_deoxys_models, prepare_deoxys_hd_materials,
    verify_xd_deoxys_model,
)
from orre_randomizer.engine.actor_archive import append_actor_models
from orre_randomizer.engine.analyze_game import FormatError, parse_fsys
from orre_randomizer.engine.rebuild_iso import align, decoded_member
from orre_randomizer.hd_packs import PACKS
from tests.test_castform_resources import archive, face


def pkx(*, xd, identity=0, flag=0):
    dat = bytearray(64)
    struct.pack_into('>I', dat, 0, len(dat))
    dat[36] = identity
    row = bytearray(0xD0)
    struct.pack_into('>IIIff', row, 0, 2, 1, flag, .1, 2.5)
    struct.pack_into('>II', row, 0x8C, identity % 3, 0x1234 + identity)
    row[0x6C] = 0x55
    if xd:
        output = bytearray(0xE60)
        struct.pack_into('>I', output, 0, len(dat))
        struct.pack_into('>I', output, 0x10, 17)
        struct.pack_into('>I', output, 0x20, 0xFFFFFFFF)
        output[0x84:0x84 + 17 * 0xD0] = row * 17
        return bytes(output + dat)
    header = bytearray(0x40)
    for at, value in ((0, len(dat)), (8, 17), (0x10, 5), (0x20, 0xFFFFFFFF)):
        struct.pack_into('>I', header, at, value)
    output = bytes(header + dat + row * 17)
    return output + bytes(-len(output) % 32)


def fixtures():
    models = {(form, shiny): pkx(xd=True, identity=i * 2 + int(shiny))
              for i, form in enumerate(FORMS) for shiny in (False, True)}
    pins = {FORM_MEMBERS[form]: {shiny: {'model_sha256': hashlib.sha256(models[form, shiny]).hexdigest()}
                              for shiny in (False, True)} for form in FORMS}
    source = {
        'pkx_deoxys.fsys': archive([(0x070A1E00, 'deoxys', pkx(xd=False))], 0x386, False),
        'pkx_rare_deoxys.fsys': archive([(0x128B1E00, 'rare_deoxys', pkx(xd=False, identity=1))], 0x77E, False),
        'poke_face.fsys': archive([(0x0F821200, 'face410', face(False)),
                                   (0x12001200, 'unrelated', b'unchanged')], 0x5C0, False),
    }
    return models, pins, source


def pixels(form, shiny):
    return bytes((FORMS.index(form) * 60, 40 + shiny * 90, 130, 255)) * 42 * 42


class DeoxysModelConversion(unittest.TestCase):
    def test_conversion_preserves_entire_dat_and_animation_track_indices(self):
        template = pkx(xd=False)
        for identity in range(3):
            source = pkx(xd=True, identity=identity)
            converted = _convert_pkx(source, template)
            self.assertEqual(converted[0x40:0x80], source[0xE60:])
            self.assertEqual(converted[:0x40], template[:0x40])
            self.assertEqual(len(converted) % 32, 0)
            start = 0x40 + align(struct.unpack_from('>I', converted)[0])
            for i in range(17):
                at = start + i * 0xD0
                self.assertEqual(struct.unpack_from('>II', converted, at + 0xC), (6, 150))
                self.assertEqual(struct.unpack_from('>II', converted, at + 0x8C),
                                 (1 if identity == 0 else 0, 0x1234 + identity))
                self.assertEqual(converted[at + 0x6C], 0x55)

    def test_opaque_schedule_words_are_preserved_instead_of_copied_from_template(self):
        source, template = pkx(xd=True, flag=48), pkx(xd=False)
        result = _convert_pkx(source, template)
        self.assertEqual(struct.unpack_from('>I', result, 0x88)[0], 48)
        with self.assertRaisesRegex(FormatError, 'must be preserved'):
            _convert_pkx(source, template, schedule_flags=(0,) * 17)
        result = _convert_pkx(source, template, schedule_flags=(48,) * 17)
        self.assertEqual(struct.unpack_from('>I', result, 0x88)[0], 48)
        for flags in ((0,) * 16, [0] * 17, (True,) * 17, (-1,) * 17, (2**32,) * 17):
            with self.assertRaises(FormatError):
                _convert_pkx(source, template, schedule_flags=flags)

    def test_invalid_timing_and_track_kinds_fail_before_output(self):
        for seconds in (float('nan'), float('inf'), -1, 3601):
            source = bytearray(pkx(xd=True))
            struct.pack_into('>f', source, 0x90, seconds)
            with self.assertRaisesRegex(FormatError, 'duration'):
                _convert_pkx(bytes(source), pkx(xd=False))
        for at, value in ((0x84, 17), (0x88, 9), (0x110, 3)):
            source = bytearray(pkx(xd=True))
            struct.pack_into('>I', source, at, value)
            with self.assertRaises(FormatError):
                _convert_pkx(bytes(source), pkx(xd=False))

    def test_incomplete_overlong_or_wrong_containers_are_rejected(self):
        source, template = pkx(xd=True), pkx(xd=False)
        for malformed in (source[:40], source[:-1], source + b'\0', template):
            with self.assertRaises(FormatError):
                _convert_pkx(malformed, template)
        for malformed in (template[:32], template[:-100], source):
            with self.assertRaises(FormatError):
                _convert_pkx(source, malformed)

    def test_public_converter_binds_form_and_shiny_donor_hashes(self):
        models, pins, _ = fixtures()
        with patch('orre_randomizer.hd_extra_portrait_catalog.MODEL_IDENTITIES', pins):
            result = convert_deoxys_model(models['attack', False], pkx(xd=False), form='attack', shiny=False)
            self.assertEqual(result[0x40:0x80], models['attack', False][0xE60:])
            with self.assertRaisesRegex(FormatError, 'checked original'):
                convert_deoxys_model(models['attack', False], pkx(xd=False), form='attack', shiny=True)
            for form, shiny in (('normal', False), ('attack', 1), (['attack'], False)):
                with self.assertRaises(FormatError):
                    verify_xd_deoxys_model(models['attack', False], form, shiny)


class DeoxysArchiveResources(unittest.TestCase):
    def test_staging_preserves_original_members_and_pending_additions(self):
        models, pins, source = fixtures()
        pending = {'unrelated.fsys': b'preserve'}
        pending['pkx_deoxys.fsys'] = append_actor_models(source['pkx_deoxys.fsys'], {},
            source['pkx_deoxys.fsys'], 0x070A1E00, {0x7CC01E00: ('prior', b'prior update')}, resource_type=0x1E00)
        with patch('orre_randomizer.hd_extra_portrait_catalog.MODEL_IDENTITIES', pins):
            report = append_deoxys_resources('GC6P01', source.__getitem__, pending,
                                              xd_models=models, portrait_pixels=pixels)
        self.assertEqual(pending['unrelated.fsys'], b'preserve')
        self.assertEqual(len(report['models']), 6)
        self.assertTrue(report['normal_and_shiny_groups_separate'])
        self.assertFalse(report['dna_body_artwork_included'])
        for shiny, filename in ((False, 'pkx_deoxys.fsys'), (True, 'pkx_rare_deoxys.fsys')):
            directory = parse_fsys(pending[filename])
            self.assertEqual(directory['group_id'], MODEL_GROUPS[shiny])
            resources = {int(row['identifier_raw'], 16): row for row in directory['members']}
            for form in FORMS:
                model = decoded_member(pending[filename], resources[MODEL_RESOURCES[form, shiny]])
                self.assertEqual(model[0x40:0x80], models[form, shiny][0xE60:])
            for original in parse_fsys(source[filename])['members']:
                current = resources[int(original['identifier_raw'], 16)]
                self.assertEqual(decoded_member(pending[filename], current), decoded_member(source[filename], original))
        rows = {int(row['identifier_raw'], 16): row for row in parse_fsys(pending['poke_face.fsys'])['members']}
        for form in FORMS:
            atlas = decoded_member(pending['poke_face.fsys'], rows[FACE_RESOURCES[form]])
            self.assertEqual(_texture(atlas, (42, 84)), pixels(form, False) + pixels(form, True))
        self.assertEqual(decoded_member(pending['poke_face.fsys'], rows[0x12001200]), b'unchanged')
        self.assertEqual(source['pkx_deoxys.fsys'], fixtures()[2]['pkx_deoxys.fsys'])

    def test_artwork_failure_does_not_publish_partial_archive_updates(self):
        models, pins, source = fixtures()
        original = {'poke_face.fsys': source['poke_face.fsys'], 'keep': b'original pending'}
        for callback in (lambda form, shiny: bytes(42 * 42 * 4),
                         lambda form, shiny: (_ for _ in ()).throw(RuntimeError('capture missing'))):
            pending = dict(original)
            with patch('orre_randomizer.hd_extra_portrait_catalog.MODEL_IDENTITIES', pins):
                with self.assertRaises((FormatError, RuntimeError)):
                    append_deoxys_resources('GC6P01', source.__getitem__, pending,
                                             xd_models=models, portrait_pixels=callback)
            self.assertEqual(pending, original)

    def test_colliding_resource_ids_do_not_replace_existing_resources(self):
        models, pins, source = fixtures()
        payload = append_actor_models(source['pkx_deoxys.fsys'], {}, source['pkx_deoxys.fsys'],
            0x070A1E00, {MODEL_RESOURCES['attack', False]: ('prior', b'keep this')}, resource_type=0x1E00)
        pending = {'pkx_deoxys.fsys': payload}
        with patch('orre_randomizer.hd_extra_portrait_catalog.MODEL_IDENTITIES', pins):
            with self.assertRaises(FormatError):
                append_deoxys_resources('GC6P01', source.__getitem__, pending, xd_models=models, portrait_pixels=pixels)
        self.assertEqual(pending, {'pkx_deoxys.fsys': payload})

    def test_missing_donor_and_wrong_game_are_rejected_before_archive_access(self):
        models, _, _ = fixtures()
        for game, given in (('GXXP01', models), ('GC6P01', {}), ('GC6P01', None)):
            with self.assertRaises(FormatError):
                append_deoxys_resources(game, lambda name: self.fail('must not read'), {},
                                         xd_models=given, portrait_pixels=pixels)

    def test_extraction_checks_every_original_donor_identity(self):
        models, pins, _ = fixtures()
        sources = {}
        for form, suffix in (('attack', 'atk'), ('defense', 'def'), ('speed', 'sp')):
            for shiny in (False, True):
                name = 'deoxys_' + suffix + ('_c' if shiny else '')
                sources['pkx_' + name + '.fsys'] = archive([(0x12341E00, name, models[form, shiny])], 123, True)
        with patch('orre_randomizer.hd_extra_portrait_catalog.MODEL_IDENTITIES', pins):
            self.assertEqual(extract_xd_deoxys_models(sources.__getitem__), models)
            sources['pkx_deoxys_sp_c.fsys'] = archive([(0x12341E00, 'deoxys_sp_c', b'wrong source')], 123, True)
            with self.assertRaises(FormatError):
                extract_xd_deoxys_models(sources.__getitem__)


class DeoxysHDResources(unittest.TestCase):
    def fixture(self, root):
        folder = root / 'Pack'
        (folder / 'Textures').mkdir(parents=True)
        marker = {'key': PACKS['xd'].key, 'archives': [part.sha256 for part in PACKS['xd'].parts]}
        (folder / 'installed.json').write_text(json.dumps(marker), encoding='utf8')
        payload = _png((8, 8), bytes((10, 30, 70, 255)) * 64)
        digest = hashlib.sha256(payload).hexdigest()
        exact, authored = 'tex1_2x2_ab12_14.png', 'tex1_2x2_cd34_14.png'
        (folder / 'Textures' / exact).write_bytes(payload)
        coverage = {'materials': {exact: {'kind': 'exact-pack-material', 'sha256': digest},
            authored: {'kind': 'authored-pack-derived-material', 'sha256': digest, 'bytes': len(payload)}},
            'required_packs': ['xd'], 'native_bitmap_upscaled_for_hd': False}
        return folder, payload, coverage

    def test_all_six_original_forms_have_complete_genuine_hd_material_coverage(self):
        report = deoxys_hd_material_coverage()
        kinds = [row['kind'] for row in report['materials'].values()]
        self.assertEqual(len(kinds), 50)
        self.assertEqual(kinds.count('exact-pack-material'), 22)
        self.assertEqual(kinds.count('authored-pack-derived-material'), 28)
        self.assertFalse(report['native_bitmap_upscaled_for_hd'])

    def test_hd_publication_is_x4_and_preserves_source_pack(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder, payload, coverage = self.fixture(root)
            target = root / 'Overlays'
            with patch('orre_randomizer.deoxys_resources.deoxys_hd_material_coverage', return_value=coverage), \
                 patch('orre_randomizer.hd_menu_catalog._asset_bytes', return_value=(payload, hashlib.sha256(payload).hexdigest())):
                report = prepare_deoxys_hd_materials({'xd': folder}, target)
                repeated = prepare_deoxys_hd_materials({'xd': folder}, target)
            self.assertEqual(report, repeated)
            self.assertEqual(set(report['files']), set(coverage['materials']))
            self.assertFalse(report['native_rom_changed'])
            self.assertEqual((folder / 'Textures' / 'tex1_2x2_ab12_14.png').read_bytes(), payload)
            for path in target.glob('*.png'):
                self.assertEqual(struct.unpack_from('>II', path.read_bytes(), 16), (8, 8))

    def test_hd_wrong_pack_corrupt_source_or_conflicting_output_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder, payload, coverage = self.fixture(root)
            target = root / 'Overlays'
            with patch('orre_randomizer.deoxys_resources.deoxys_hd_material_coverage', return_value=coverage), \
                 patch('orre_randomizer.hd_menu_catalog._asset_bytes', return_value=(payload, hashlib.sha256(payload).hexdigest())):
                for given, destination in (({}, target), ({'xd': folder}, folder / 'Textures')):
                    with self.assertRaises(ValueError):
                        prepare_deoxys_hd_materials(given, destination)
                bad = deepcopy(coverage)
                bad['materials']['tex1_2x2_ab12_14.png']['sha256'] = '0' * 64
                with patch('orre_randomizer.deoxys_resources.deoxys_hd_material_coverage', return_value=bad):
                    with self.assertRaises(ValueError):
                        prepare_deoxys_hd_materials({'xd': folder}, target)
                self.assertFalse(target.exists())
                (folder / 'installed.json').write_text('{}', encoding='utf8')
                with self.assertRaises(ValueError):
                    prepare_deoxys_hd_materials({'xd': folder}, target)
