"""The serialized production image carries the first-duel retry safeguard."""
from dataclasses import replace
import hashlib
from pathlib import Path
import threading
import unittest

from orre_randomizer import service, xd
from orre_randomizer.engine.analyze_game import u32
from orre_randomizer.engine.survey_assets import fst_inventory
from orre_randomizer.xd_starter_progression import ARCHIVE, validate_starter_progression
from scripts.validate_starter_matrix import source_identity, validate_plan


ROOT = Path(__file__).resolve().parents[1]


class FirstDuelPolicyTests(unittest.TestCase):
    def test_copy_and_cosmetic_only_settings_keep_the_native_retry(self):
        original = xd.XDOptions.unchanged()
        self.assertFalse(xd.starter_progression_active(original))
        for field in ('custom_shinies', 'custom_shadow_shinies',
                      'keep_shadow_lugia_after_purification'):
            with self.subTest(field=field):
                self.assertFalse(xd.starter_progression_active(replace(original, **{field: True})))
        self.assertTrue(xd.starter_progression_active(xd.XDOptions.species_only()))
        self.assertTrue(xd.starter_progression_active(xd.XDOptions.recommended()))

    def test_changing_either_battler_enables_the_safeguard(self):
        original = xd.XDOptions.unchanged()
        for field in ('randomize_starter', 'randomize_trainers', 'randomize_learnsets',
                      'randomize_abilities', 'randomize_types', 'randomize_stats',
                      'randomize_held_items', 'trainer_force_evolved', 'progressive_levels'):
            with self.subTest(field=field):
                self.assertTrue(xd.starter_progression_active(replace(original, **{field: True})))
        for field in ('randomize_starter_moves', 'randomize_trainer_moves'):
            for mode in ('natural', True):
                with self.subTest(field=field, mode=mode):
                    self.assertTrue(xd.starter_progression_active(replace(original, **{field: mode})))
        self.assertTrue(xd.starter_progression_active(replace(original, trainer_level_multiplier=2.0)))


class NativeFirstDuelProductionPlan(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        image = ROOT / 'build/xd-validation/verified-eu.iso'
        if not image.is_file():
            raise unittest.SkipTest('requires a locally retained original European XD ISO')
        cls.identity = source_identity(image)

    @classmethod
    def tearDownClass(cls):
        with cls.identity['path'].open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != cls.identity['sha256']:
                raise AssertionError('Original XD image changed during projected-image checks')

    def projected(self, patches, offset, size):
        with self.identity['path'].open('rb') as stream:
            stream.seek(offset)
            result = bytearray(stream.read(size))
        for start, payload in patches:
            low, high = max(start, offset), min(start + len(payload), offset + size)
            if low < high:
                result[low - offset:high - offset] = payload[low - start:high - start]
        self.assertEqual(len(result), size)
        return bytes(result)

    def archive(self, patches):
        header = self.projected(patches, 0, 0x440)
        fst = self.projected(patches, u32(header, 0x424), u32(header, 0x428))
        files, _ = fst_inventory(fst)
        entry = next(row for row in files if row['path'] == ARCHIVE)
        return self.projected(patches, entry['disc_offset'], entry['size'])

    def test_both_complete_presets_publish_the_qualified_retry_script(self):
        native = self.archive([])
        for name, options in (('pokemon', xd.XDOptions.species_only()),
                              ('pokemon-moves', xd.XDOptions.recommended())):
            with self.subTest(preset=name):
                patches, summary = service.build_xd_patches(
                    self.identity['path'], self.identity['boot'], 'first-duel-production',
                    replace(options, starter_species=129), lambda *_args: None, threading.Event())
                validate_plan(patches, self.identity['bytes'])
                proof = validate_starter_progression(native, self.archive(patches), 'GXXP01')
                self.assertTrue(proof['only_retry_instruction_changed'])
                self.assertTrue(proof['native_victory_path_preserved'])
                self.assertEqual(proof, {key: summary['starter_progression'][key] for key in proof})
                self.assertTrue(summary['starter_progression']['other_archive_payloads_identical'])
                self.assertTrue(summary['capture_tutorial']['native_guaranteed_capture'])
                if name == 'pokemon':
                    self.assertEqual(summary['starter']['moves'], [150, 0, 0, 0])

    def test_complete_copy_plan_keeps_every_byte(self):
        patches, summary = service.build_xd_patches(
            self.identity['path'], self.identity['boot'], 'first-duel-copy',
            xd.XDOptions.unchanged(), lambda *_args: None, threading.Event())
        self.assertEqual(patches, [])
        self.assertEqual(summary, {})
