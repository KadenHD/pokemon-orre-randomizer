"""Deoxys curation preserves existing assets and rolls back failed publication."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from orre_randomizer.deoxys_assets import asset_directory, asset_manifest, artwork_png, xd_models
from scripts import register_deoxys_assets as registration


class DeoxysRegistrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='deoxys registration ')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / 'source'
        shutil.copytree(asset_directory(), self.source)
        self.pack = self.root / 'pack'
        self.pack.mkdir()
        metadata = json.loads((self.source / registration.CATALOG).read_text('utf-8'))
        game_pack = asset_directory().parents[1]
        rows = {}
        for relative in metadata['source_catalogs']:
            path = self.pack / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(game_pack / relative, path)
            rows[relative] = {'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        (self.pack / 'unrelated.md').write_bytes(b'keep this original file')
        rows['unrelated.md'] = {'bytes': 23, 'sha256': hashlib.sha256(b'keep this original file').hexdigest()}
        self.provenance = self.pack / 'provenance.json'
        self.provenance.write_text(json.dumps({'version': 1, 'files': rows, 'unrelated_metadata': {'keep': True}}), 'utf-8')
        self.backups = self.root / 'backups'

    def register(self, **kwargs):
        return registration.register(self.source, self.pack, backup_root=self.backups, **kwargs)

    def source_manifest(self):
        path = self.source / registration.CATALOG
        return path, json.loads(path.read_text('utf-8'))

    def test_complete_set_registers_without_changing_unrelated_files_and_is_idempotent(self):
        old = json.loads(self.provenance.read_text('utf-8'))
        result = self.register()
        self.assertTrue(result['registered'])
        target = self.pack / 'models/deoxys'
        _, manifest = asset_manifest(target)
        self.assertEqual(len(manifest['files']), 30)
        self.assertEqual(len(xd_models(target)), 6)
        self.assertEqual(len(artwork_png('speed', shiny=True, hd=True, role='body', directory=target)) > 0, True)
        updated = json.loads(self.provenance.read_text('utf-8'))
        self.assertEqual(updated['unrelated_metadata'], old['unrelated_metadata'])
        self.assertEqual((self.pack / 'unrelated.md').read_bytes(), b'keep this original file')
        for name, row in old['files'].items():
            self.assertEqual(updated['files'][name], row)
        self.assertTrue(self.register()['already_registered'])
        self.assertEqual(len(list(self.backups.iterdir())), 1)

    def test_check_only_does_not_create_assets_backups_or_rewrite_provenance(self):
        before = self.provenance.read_bytes()
        result = self.register(check_only=True)
        self.assertTrue(result['check_only'])
        self.assertEqual(self.provenance.read_bytes(), before)
        self.assertFalse((self.pack / 'models/deoxys').exists())
        self.assertFalse(self.backups.exists())

    def test_changed_png_and_non_original_pkx_are_refused_before_any_write(self):
        before = self.provenance.read_bytes()
        for name in ('head-attack-normal-native.png', 'xd-speed-shiny.pkx'):
            with self.subTest(name=name):
                path = self.source / name
                payload = path.read_bytes()
                path.write_bytes(payload + b'changed')
                try:
                    with self.assertRaises(ValueError):
                        self.register()
                finally:
                    path.write_bytes(payload)
        self.assertEqual(self.provenance.read_bytes(), before)
        self.assertFalse(self.backups.exists())

    def test_unreviewed_private_and_mismatched_capture_identity_are_refused(self):
        path, original = self.source_manifest()
        for kind in ('unreviewed', 'private', 'model'):
            with self.subTest(kind=kind):
                metadata = json.loads(json.dumps(original))
                row = metadata['files']['head-attack-normal-native.png']['capture']
                if kind == 'unreviewed':
                    metadata['art_approved_by_root'] = False
                elif kind == 'private':
                    row['profile_path'] = 'C:/Users/private/capture'
                else:
                    row['source_model_sha256'] = '0' * 64
                path.write_text(json.dumps(metadata), 'utf-8')
                with self.assertRaises(ValueError):
                    self.register()
        path.write_text(json.dumps(original), 'utf-8')
        self.assertFalse(self.backups.exists())

    def test_runtime_addresses_cannot_replace_original_joint_descriptors(self):
        path, metadata = self.source_manifest()
        pose = metadata['pose_recipes']['attack/head']['joints_by_original_dat_offset']
        key = next(iter(pose))
        pose['0x80001234'] = pose.pop(key)
        path.write_text(json.dumps(metadata), 'utf-8')
        with self.assertRaisesRegex(ValueError, 'runtime rather than source descriptor'):
            self.register()
        self.assertFalse(self.backups.exists())

    def test_provenance_write_failure_restores_previous_assets_and_records_rollback(self):
        self.register()
        target = self.pack / 'models/deoxys'
        before = {p.name: p.read_bytes() for p in target.iterdir()}
        provenance = self.provenance.read_bytes()
        path, metadata = self.source_manifest()
        metadata['review']['transaction_test'] = 'new reviewed metadata'
        path.write_text(json.dumps(metadata), 'utf-8')
        with patch.object(registration, '_atomic_write', side_effect=OSError('simulated publication lock')):
            with self.assertRaises(OSError):
                self.register()
        self.assertEqual(self.provenance.read_bytes(), provenance)
        self.assertEqual({p.name: p.read_bytes() for p in target.iterdir()}, before)
        receipts = [json.loads(p.read_text('utf-8')) for p in self.backups.glob('*/registration.json')]
        self.assertIn('rolled-back', [row['status'] for row in receipts])

    def test_concurrent_provenance_edit_is_preserved_and_publication_refused(self):
        write = Path.write_bytes
        observed = []
        def writing(path, data):
            result = write(path, data)
            if path.name == 'provenance-before.json':
                changed = json.loads(self.provenance.read_text('utf-8'))
                changed['concurrent_curator'] = 'keep'
                payload = json.dumps(changed).encode('utf-8')
                write(self.provenance, payload)
                observed.append(payload)
            return result
        with patch.object(Path, 'write_bytes', writing):
            with self.assertRaisesRegex(ValueError, 'changed during registration'):
                self.register()
        self.assertEqual(self.provenance.read_bytes(), observed[0])
        self.assertFalse((self.pack / 'models/deoxys').exists())

    def test_unknown_existing_files_and_changed_source_catalog_are_preserved(self):
        target = self.pack / 'models/deoxys'
        target.mkdir(parents=True)
        unknown = target / 'personal.raw'
        unknown.write_bytes(b'never replace this file')
        with self.assertRaisesRegex(ValueError, 'Unrecognized existing files'):
            self.register()
        self.assertEqual(unknown.read_bytes(), b'never replace this file')
        path = self.pack / 'form-materials/catalog.json'
        path.write_bytes(path.read_bytes() + b' ')
        with self.assertRaisesRegex(ValueError, 'source catalog changed'):
            self.register()
        self.assertFalse(self.backups.exists())


if __name__ == '__main__':
    unittest.main()
