"""Targeted publication/rebase regressions; actual four-raw checks run separately."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from orre_randomizer.artwork import _png
from orre_randomizer.hd_packs import PACKS
from orre_randomizer.model_portraits import portrait_filename
from scripts import register_hd_model_bodies as registrar


class PairedBodyRegistrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.pack = self.root / 'game'
        models = self.pack / 'models'; models.mkdir(parents=True)
        self.models = models
        # No local game/pack assets are needed by source-archive or CI tests.
        model = {'original_sha256': '1' * 64, 'shiny_sha256': '2' * 64}
        materials = [{'sha256': '3' * 64, 'hd_source': {'pack': PACKS['xd'].key}}]
        self.old_native = {'schema': 1, 'dimensions': [64, 64], 'source_model': model, 'files': {}}
        self.old_hd = {'schema': 1, 'dimensions': [256, 256], 'native_dimensions': [64, 64],
            'source': {'pack': PACKS['xd'].key, 'archives': [part.sha256 for part in PACKS['xd'].parts],
                'model': model, 'hd_art_revision': 2, 'material_recipes': materials,
                'hd_material_coverage': {'total_native_materials': 5, 'exact_pack_materials': 2,
                    'authored_pack_derived': 3, 'derived_shiny_materials': 1, 'inherited_stock': []}},
            'capture': {'method': 'historical body capture'}, 'conversion': {'method': 'historical fit'},
            'material_runtime_ab': {'report_sha256': '4' * 64}, 'files': {}}
        for size, names, manifest in ((64, registrar._NATIVE, self.old_native), (256, registrar._HD, self.old_hd),
                (168, ('dark-lugia-head-x4.png', 'dark-lugia-shiny-head-x4.png'), self.old_hd)):
            for shiny, name in zip((False, True), names):
                payload = _png((size, size), bytes((90, 60, 130, 255)) * size * size)
                (models / name).write_bytes(payload)
                manifest['files'][name] = {'shiny': shiny, 'bytes': len(payload),
                    'sha256': hashlib.sha256(payload).hexdigest(), 'source_capture_sha256': '5' * 64,
                    'materials': copy.deepcopy(materials)}
        native_payload = json.dumps(self.old_native).encode()
        hd_payload = json.dumps(self.old_hd).encode()
        self.old_portraits = {'schema': 1, 'review_only': False,
            'source': {'hd': {'material_manifest_sha256': hashlib.sha256(hd_payload).hexdigest()},
                       'captures': {'original_head': {'capture_sha256': '6' * 64}}}, 'files': {}}
        for game in ('colosseum', 'xd'):
            for shiny in (False, True):
                for scale in (1, 4):
                    name = portrait_filename(game, shiny, scale)
                    size = 42 * scale
                    payload = _png((size, size), bytes((100, 50, 150, 255)) * size * size)
                    (models / name).write_bytes(payload)
                    self.old_portraits['files'][name] = {'game': game, 'shiny': shiny, 'scale': scale,
                        'dimensions': [size, size], 'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}
        portraits_payload = json.dumps(self.old_portraits).encode()
        for name, payload in [('fullbody-manifest.json', native_payload), ('hd-fullbody-manifest.json', hd_payload),
                              ('portrait-variants.json', portraits_payload)]:
            (models / name).write_bytes(payload)
        (self.pack / 'provenance.json').write_text('{"files": {}}')
        self.source = self.root / 'candidate'; self.source.mkdir()
        self.native = copy.deepcopy(self.old_native)
        self.hd = copy.deepcopy(self.old_hd)
        common = {'schema': 1, 'matrix_count': 86, 'pose_signature_sha256': 'a' * 64,
            'camera': {'method': 'synthetic transaction fixture'}, 'roi_normalized': [0.125, 0.125, 0.875, 0.875],
            'fitted_dimensions_native': [56, 42], 'padding_native': [4, 11],
            'native_source_dimensions': [256, 256], 'hd_source_dimensions': [1024, 1024],
            'source_material_parent_sha256': hashlib.sha256(hd_payload).hexdigest(),
            'captures': dict.fromkeys(('native-normal', 'native-shiny', 'hd-normal', 'hd-shiny'), {})}
        for data in (self.native, self.hd):
            data['common_capture'] = copy.deepcopy(common)
            data['review_only'] = False
        self.hd['files'] = {name: self.hd['files'][name] for name in registrar._HD}
        self.payloads = {}
        for size, names, data in ((64, registrar._NATIVE, self.native), (256, registrar._HD, self.hd)):
            for shiny, name in zip((False, True), names):
                pixels = bytes(channel for y in range(size) for x in range(size)
                               for channel in ((210 if shiny else 30, 70, 130, 255)
                                               if size // 8 <= x < size * 7 // 8 and size // 8 <= y < size * 7 // 8
                                               else (0, 0, 0, 0)))
                payload = _png((size, size), pixels)
                self.payloads['models/' + name] = payload
                entry = data['files'][name]
                entry.update(shiny=shiny, bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest(),
                             source_capture_sha256=('c' if shiny else 'b') * 64)
                if size == 256:
                    entry['donor_source_records'] = copy.deepcopy(entry.pop('materials', []))
                (self.source / name).write_bytes(payload)
        self.save()
        # The transaction tests start after raw/probe/image reconstruction;
        # production check-only exercises that stage on all four real captures.
        self.capture_patch = patch.object(registrar, '_capture_assets', return_value=self.payloads.copy())
        self.capture_patch.start(); self.addCleanup(self.capture_patch.stop)

    def save(self):
        (self.source / 'fullbody-manifest.json').write_text(json.dumps(self.native))
        (self.source / 'hd-fullbody-manifest.json').write_text(json.dumps(self.hd))

    def snapshot(self):
        return {path.relative_to(self.pack).as_posix(): path.read_bytes()
                for path in self.pack.rglob('*') if path.is_file()}

    def call(self, **kwargs):
        return registrar.register_paired(self.source, self.source, self.pack,
                                         backup_dir=self.root / 'backup', **kwargs)

    def test_check_only_then_publication_rebases_only_portrait_parent_and_keeps_pixels(self):
        before = self.snapshot()
        result = self.call(check_only=True)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.root / 'backup').exists())
        self.assertEqual(len(result['updated_files']), 8)
        self.call()
        new_hd = json.loads((self.models / 'hd-fullbody-manifest.json').read_text())
        new_native_payload = (self.models / 'fullbody-manifest.json').read_bytes()
        self.assertEqual(new_hd['paired_native']['manifest_sha256'], hashlib.sha256(new_native_payload).hexdigest())
        self.assertEqual(new_hd['source'], self.old_hd['source'])
        after_portrait = json.loads((self.models / 'portrait-variants.json').read_text())
        after_portrait['source']['hd']['material_manifest_sha256'] = self.old_portraits['source']['hd']['material_manifest_sha256']
        self.assertEqual(after_portrait, self.old_portraits)
        for name in self.old_portraits['files']:
            self.assertEqual((self.models / name).read_bytes(), before['models/' + name])
        for name, entry in self.old_hd['files'].items():
            if name not in registrar._HD:
                self.assertEqual(new_hd['files'][name], entry)
                self.assertEqual((self.models / name).read_bytes(), before['models/' + name])
        ledger = json.loads((self.pack / 'provenance.json').read_text())
        for relative in result['updated_files']:
            if relative != 'provenance.json':
                self.assertEqual(ledger['files'][relative]['sha256'], hashlib.sha256((self.pack / relative).read_bytes()).hexdigest())
            self.assertEqual((self.root / 'backup' / relative).read_bytes(), before[relative])

    def test_material_and_camera_changes_are_rejected_without_any_write(self):
        before = self.snapshot()
        original = copy.deepcopy(self.hd)
        for mutation in ('material', 'camera'):
            self.hd = copy.deepcopy(original)
            if mutation == 'material':
                self.hd['source']['material_recipes'][0]['sha256'] = '0' * 64
            else:
                self.hd['common_capture']['camera']['method'] = 'different camera'
            self.save()
            with self.assertRaises(ValueError):
                self.call()
            self.assertEqual(self.snapshot(), before)
            self.assertFalse((self.root / 'backup').exists())

    def test_unreviewed_set_can_be_checked_but_cannot_be_published(self):
        self.native['review_only'] = True; self.save()
        before = self.snapshot()
        self.assertTrue(self.call(check_only=True)['review_only'])
        with self.assertRaisesRegex(ValueError, 'visual review'):
            self.call()
        self.assertEqual(self.snapshot(), before)

    def test_corrupt_installed_portrait_blocks_rebase_before_writes(self):
        name = next(iter(self.old_portraits['files']))
        (self.models / name).write_bytes(b'corrupt')
        before = self.snapshot()
        with self.assertRaises(ValueError):
            self.call()
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.root / 'backup').exists())

    def test_mid_publication_io_failure_restores_all_original_bytes(self):
        before = self.snapshot()
        real_replace = registrar.os.replace
        count = 0
        def fail_once(source, destination):
            nonlocal count
            count += 1
            if count == 3:
                raise OSError('simulated disk failure')
            return real_replace(source, destination)
        with patch.object(registrar.os, 'replace', side_effect=fail_once):
            with self.assertRaisesRegex(OSError, 'disk failure'):
                self.call()
        self.assertEqual(self.snapshot(), before)
        self.assertTrue((self.root / 'backup/registration-backup.json').is_file())


if __name__ == '__main__':
    unittest.main()
