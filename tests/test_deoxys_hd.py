"""Imported forms keep explicit original/x4 routes and isolated cache dependencies."""
from contextlib import ExitStack
import copy
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from orre_randomizer import hd_overlays as hd
from orre_randomizer.artwork import _png
from orre_randomizer.deoxys_assets import xd_models, portrait_pixels, hd_face_recipes, _rgba8
from orre_randomizer.deoxys_resources import FORMS, MODEL_RESOURCES, FACE_RESOURCES
from orre_randomizer.hd_packs import PACKS, PackStore
from orre_randomizer.play_folders import hd_game_requirements, prepare_custom_hd
from orre_randomizer.service import UserError
from tests.test_hd_overlays import archive


def model_container(original):
    # The fixture only exercises texture extraction, not native animation code.
    size, = struct.unpack_from('>I', original)
    header = bytearray(64)
    struct.pack_into('>I', header, 0, size)
    return bytes(header) + original[0xE60:0xE60 + size]


def form_archives():
    models = xd_models()
    normal, shiny = [], []
    for form in FORMS:
        for rare in (False, True):
            (shiny if rare else normal).append((MODEL_RESOURCES[form, rare], form, model_container(models[form, rare])))
    faces = []
    for form in FORMS:
        header = bytearray(128)
        struct.pack_into('>HHBB', header, 0, 42, 84, 32, 1)
        struct.pack_into('>I', header, 0x28, 128)
        pixels = portrait_pixels(form, False) + portrait_pixels(form, True)
        faces.append((FACE_RESOURCES[form], form, bytes(header) + _rgba8(pixels, 42, 84)))
    # A field actor derived from the same DAT must not be searched in stock
    # Colosseum's model donors or silently fall back to a native texture.
    field = model_container(models['attack', False])[64:]
    return [('people_archive.fsys', archive([(0x7D010400, 'orre_deoxys_actor', field)])),
            ('pkx_deoxys.fsys', archive(normal)), ('pkx_rare_deoxys.fsys', archive(shiny)),
            ('poke_face.fsys', archive(faces))]


class DeoxysHdContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='deoxys HD ')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.iso = self.root / 'synthetic.iso'
        self.iso.write_bytes(b'GC6P01\0\0')
        self.native = self.root / 'native'

    def capture(self):
        with patch.object(hd, '_disc_archives', return_value=form_archives()) as archives, \
             patch.object(hd, '_field_origins', side_effect=AssertionError('Imported DAT was searched in the wrong game')):
            result = hd.capture_native_assets(self.iso, self.native,
                                             asset_context={'deoxys_forms': {'enabled': True}})
        self.assertEqual(archives.call_args.kwargs['extra_names'], {'pkx_deoxys.fsys', 'pkx_rare_deoxys.fsys'})
        return result

    def renderer(self, report):
        def render(contract, roots, target):
            self.assertTrue(contract['enabled'])
            self.assertIn('xd', roots)
            target.mkdir(parents=True, exist_ok=True)
            files = {}
            faces = hd_face_recipes()
            for asset in report['assets']:
                name = asset['base_key']
                if name in faces:
                    payload = faces[name]['png']
                else:
                    width, height = asset['native']['width'] * 4, asset['native']['height'] * 4
                    # Mathematical fixture colours, not an enlarged native asset.
                    payload = _png((width, height), bytes((30, 60, 90, 255)) * width * height)
                (target / name).write_bytes(payload)
                files[name] = hashlib.sha256(payload).hexdigest()
            return {'active': True, 'files': files}
        return render

    def test_complete_dual_registry_is_required_and_stock_dependencies_stay_unchanged(self):
        contract = hd.deoxys_hd_contract()
        self.assertEqual(len(contract['material_keys']), 50)
        self.assertEqual(len(contract['portrait_keys']), 3)
        stock = {'game': 'colosseum', 'features': {}}
        self.assertEqual(hd_game_requirements(stock), ('colosseum',))
        for enabled in (False, True):
            data = {**stock, 'features': {'deoxys_forms': {'enabled': enabled}}}
            self.assertEqual(hd_game_requirements(data), ('colosseum', 'xd') if enabled else ('colosseum',))
        with patch('orre_randomizer.deoxys_assets.artwork_png', side_effect=FileNotFoundError('missing x4 body')):
            with self.assertRaises(FileNotFoundError):
                hd.deoxys_hd_contract()

    def test_native_capture_binds_all_imported_resources_and_shared_field_materials(self):
        report = self.capture()
        roles = {r['role'] for r in report['resources']}
        self.assertTrue({'deoxys_battle', 'deoxys_portrait', 'field'} <= roles)
        self.assertEqual(report['deoxys_forms']['resources'], 9)
        self.assertEqual(report['required_packs'], ['xd'])
        self.assertEqual(report['missing_assets'], [])
        self.assertTrue(any('deoxys_field' in a.get('deoxys_roles', []) for a in report['assets']))
        self.assertTrue(all(a['hd']['transform']['type'] == 'imported-deoxys' for a in report['assets']))
        self.assertEqual(report['deoxys_forms']['asset_registry_sha256'], hd.deoxys_hd_contract()['asset_registry_sha256'])

    def test_imported_faces_without_context_or_complete_models_are_not_silently_ignored(self):
        faces = [form_archives()[-1]]
        for context in (None, {'deoxys_forms': {'enabled': True}}):
            with self.subTest(context=context), patch.object(hd, '_disc_archives', return_value=faces):
                with self.assertRaises(hd.OverlayError):
                    hd.capture_native_assets(self.iso, self.root / ('incomplete-' + str(bool(context))), asset_context=context)

    def test_base_renderer_resolves_imported_assets_before_any_generic_pack_fallback(self):
        report = self.capture()
        with patch.object(hd, 'prepare_deoxys_hd', side_effect=self.renderer(report)) as render, \
             patch.object(hd, '_resolve_hd', side_effect=AssertionError('Unexpected native/stock fallback')):
            result = hd.prepare_hd_overlays(self.native, self.root / 'HD', pack_roots={'xd': self.root / 'pack'})
        self.assertTrue(result['hd_ready'])
        self.assertEqual(render.call_count, 1)
        self.assertEqual(len(result['files']), len(report['assets']))
        self.assertEqual({r['hd_source']['kind'] for r in result['files']}, {'registered-imported-deoxys'})

    def test_missing_artwork_or_changed_capture_route_blocks_hd_without_native_substitution(self):
        report = self.capture()
        with patch.object(hd, 'prepare_deoxys_hd', side_effect=FileNotFoundError('missing reviewed x4 portrait')), \
             patch.object(hd, '_resolve_hd', side_effect=AssertionError('Unexpected native fallback')):
            result = hd.prepare_hd_overlays(self.native, self.root / 'missing', pack_roots={'xd': self.root / 'pack'})
        self.assertFalse(result['hd_ready'])
        self.assertEqual(result['files'], [])
        self.assertTrue(result['missing_assets'])
        changed = copy.deepcopy(report)
        changed['assets'][0]['hd']['transform']['type'] = 'identity'
        (self.native / 'orre-overlays-v2.json').write_text(json.dumps(changed))
        with patch.object(hd, 'prepare_deoxys_hd', side_effect=self.renderer(report)), \
             patch.object(hd, '_resolve_hd', side_effect=AssertionError('Changed imported route fell back to stock')):
            result = hd.prepare_hd_overlays(self.native, self.root / 'changed', pack_roots={'xd': self.root / 'pack'})
        self.assertFalse(result['hd_ready'])
        self.assertTrue(any('unqualified' in row['reason'] for row in result['missing_assets']))


class DeoxysHdCacheTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='deoxys cache ')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.folder = self.root / 'Party'
        (self.folder / 'Textures').mkdir(parents=True)
        (self.folder / 'Textures/orre-overlays-v2.json').write_text('{"schema":2}')
        self.plan = {'schema': 2, 'game': 'colosseum', 'required_packs': [], 'assets': []}
        self.data = {'game': 'colosseum', 'game_id': 'GC6P01', 'shared': str(self.root / 'Shared'),
                     'features': {'overlays': self.plan}, 'packs': {}}
        for pack in PACKS.values():
            path = self.root / 'Shared/TexturePacks' / pack.key
            path.mkdir(parents=True)
            (path / 'installed.json').write_text('{}')

    def patches(self):
        stack = ExitStack()
        stack.enter_context(patch.object(hd, 'native_asset_manifest', return_value=self.plan))
        stack.enter_context(patch.object(PackStore, 'installed', return_value=True))
        def base(_root, destination, **kwargs):
            destination.mkdir(parents=True, exist_ok=True)
            return {'schema': 2, 'hd_ready': True, 'files': []}
        stack.enter_context(patch.object(hd, 'prepare_hd_overlays', side_effect=base))
        for path in ('hd_hud.prepare_hud_overlays', 'hd_extra_portraits.prepare_extra_portrait_overlays',
                     'hd_form_materials.prepare_form_materials'):
            stack.enter_context(patch('orre_randomizer.' + path, return_value={'files': {}, 'assets': [], 'active': False}))
        return stack

    def test_old_cache_never_reads_imported_registry_and_new_cache_tracks_its_fingerprint(self):
        with self.patches(), patch.object(hd, 'deoxys_hd_contract', side_effect=AssertionError('Old run acquired a new requirement')):
            old = prepare_custom_hd(self.folder, self.data)
        contract = hd.deoxys_hd_contract()
        self.plan['deoxys_forms'] = contract
        name = 'tex1_42x84_0123456789abcdef_6.png'
        payload = _png((168, 336), bytes((40, 70, 100, 255)) * 168 * 336)
        def imported(_contract, roots, destination):
            self.assertIn('xd', roots)
            (destination / name).write_bytes(payload)
            return {'active': True, 'files': {name: hashlib.sha256(payload).hexdigest()}}
        with self.patches(), patch.object(hd, 'prepare_deoxys_hd', side_effect=imported) as render:
            new = prepare_custom_hd(self.folder, self.data)
            reused = prepare_custom_hd(self.folder, self.data)
        self.assertNotEqual(old['directory'], new['directory'])
        self.assertEqual(new['directory'], reused['directory'])
        self.assertTrue(new['deoxys_imported_artwork']['active'])
        self.assertEqual(render.call_count, 1)
        altered = {**contract, 'asset_registry_sha256': 'f' * 64}
        self.plan['deoxys_forms'] = altered
        with self.patches(), patch.object(hd, 'deoxys_hd_contract', return_value=altered), \
             patch.object(hd, 'prepare_deoxys_hd', side_effect=imported):
            rebuilt = prepare_custom_hd(self.folder, self.data)
        self.assertNotEqual(new['directory'], rebuilt['directory'])

    def test_changed_required_registry_is_rejected_before_reusing_a_cached_hd_directory(self):
        contract = hd.deoxys_hd_contract()
        self.plan['deoxys_forms'] = {**contract, 'asset_registry_sha256': '0' * 64}
        with self.patches(), patch.object(hd, 'prepare_hd_overlays') as render:
            with self.assertRaises(UserError):
                prepare_custom_hd(self.folder, self.data)
        render.assert_not_called()



if __name__ == '__main__':
    unittest.main()
