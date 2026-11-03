"""RVZ reuse never weakens byte identity, ownership or cancellation."""
from contextlib import contextmanager, ExitStack
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from colosseum_randomizer import service
from colosseum_randomizer.engine.regions import REGIONS
from colosseum_randomizer.options import Options
from colosseum_randomizer.preview import preview_starters
from colosseum_randomizer.preview_cache import PreviewCache


class PreviewCacheTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        self.source = self.root / 'original.rvz'
        self.source.write_bytes(b'source A')
        self.tool = self.root / 'DolphinTool.exe'
        self.tool.write_bytes(b'tool A')
        self.works = []
        names = {f'name_{language}': 'Test' for language in ('fr', 'en', 'de', 'es', 'it', 'ja')}
        self.summary = {'special_gameplay': {'specials': [dict(key=key, species=1,
            national_dex=1, level=level, **names) for key, level in (('umbreon', 26), ('espeon', 25))]}}

    def tearDown(self):
        self.folder.cleanup()

    @contextmanager
    def pipeline(self):
        def convert(tool, source, destination, work, cancel):
            self.works.append(work)
            destination.write_bytes(b'iso:' + source.read_bytes() + tool.read_bytes())
        with ExitStack() as stack:
            stack.enter_context(patch.object(service, 'check_header', return_value=b'header'))
            stack.enter_context(patch.object(service, 'check_disc_identity', return_value=REGIONS[0]))
            build = stack.enter_context(patch.object(service, 'build_patches', return_value=([], self.summary)))
            conversion = stack.enter_context(patch.object(service, 'convert', side_effect=convert))
            stack.enter_context(patch('colosseum_randomizer.preview.extract_portraits', return_value={}))
            yield build, conversion

    def preview(self, cache, seed='seed', cancel=None):
        return preview_starters(self.source, seed, Options.recommended(), self.tool,
                                cache=cache, cancel=cancel)

    def test_successive_seeds_reuse_one_conversion_and_close_cleans_owned_iso(self):
        before = self.source.read_bytes()
        with self.pipeline() as (build, conversion), PreviewCache() as cache:
            results = [self.preview(cache, seed) for seed in ('one', 'two', 'three')]
            self.assertEqual(conversion.call_count, 1)
            self.assertEqual(build.call_count, 3)
            self.assertEqual([row['seed'] for row in results], ['one', 'two', 'three'])
            self.assertTrue(self.works[0].is_dir())
        self.assertFalse(self.works[0].exists())
        self.assertEqual(self.source.read_bytes(), before)
        self.assertEqual(set(self.root.iterdir()), {self.source, self.tool})

    def test_changed_bytes_invalidate_even_with_same_size_and_timestamp(self):
        with self.pipeline() as (_, conversion), PreviewCache() as cache:
            self.preview(cache)
            previous = self.source.stat()
            self.source.write_bytes(b'source B')
            os.utime(self.source, ns=(previous.st_atime_ns, previous.st_mtime_ns))
            self.preview(cache)
            self.assertEqual(conversion.call_count, 2)
            self.assertFalse(self.works[0].exists())
            self.tool.write_bytes(b'tool B')
            self.preview(cache)
            self.assertEqual(conversion.call_count, 3)
            self.assertFalse(self.works[1].exists())

    def test_corrupt_cached_iso_is_rejected_and_not_returned(self):
        with self.pipeline() as (_, conversion), PreviewCache() as cache:
            self.preview(cache)
            (self.works[0] / 'source.iso').write_bytes(b'corrupt')
            with self.assertRaisesRegex(service.UserError, 'changé'):
                self.preview(cache)
            self.assertFalse(self.works[0].exists())
            self.preview(cache)
            self.assertEqual(conversion.call_count, 2)

    def test_pipeline_failure_discards_conversion_and_next_attempt_rebuilds(self):
        with self.pipeline() as (build, conversion), PreviewCache() as cache:
            build.side_effect = RuntimeError('failed calculation')
            with self.assertRaisesRegex(RuntimeError, 'failed calculation'):
                self.preview(cache)
            self.assertFalse(self.works[0].exists())
            build.side_effect = None
            self.preview(cache)
            self.assertEqual(conversion.call_count, 2)

    def test_close_while_reading_defers_cleanup_and_refuses_future_readers(self):
        with self.pipeline() as (build, _):
            cache = PreviewCache()
            def in_flight(*_):
                cache.close()
                self.assertTrue((self.works[0] / 'source.iso').is_file())
                return [], self.summary
            build.side_effect = in_flight
            self.preview(cache)
            self.assertFalse(self.works[0].exists())
            with self.assertRaises(service.Cancelled):
                self.preview(cache)

    def test_waiting_reader_can_cancel_without_deleting_active_readers_file(self):
        with self.pipeline(), PreviewCache() as cache:
            source_hash = service.file_hash(self.source, threading.Event())
            cancelled = threading.Event()
            errors = []
            def wait_for_lease():
                try:
                    with cache.lease(self.source, source_hash, self.tool, lambda *_: None, cancelled):
                        self.fail('cancelled waiter acquired a lease')
                except BaseException as error:
                    errors.append(error)
            with cache.lease(self.source, source_hash, self.tool, lambda *_: None, threading.Event()) as image:
                waiter = threading.Thread(target=wait_for_lease)
                waiter.start()
                cancelled.set()
                waiter.join(1)
                self.assertFalse(waiter.is_alive())
                self.assertIsInstance(errors[0], service.Cancelled)
                self.assertTrue(image.iso.is_file())
            self.assertTrue(image.iso.exists())
            # A waiting user's cancellation must not invalidate the active
            # owner's verified file. It is cleaned only by the cache scope
            # exiting, not by the interrupted waiter.
        self.assertFalse(image.iso.exists())

    def test_explicit_invalidation_releases_only_its_own_temporary_folder(self):
        with self.pipeline() as (_, conversion), PreviewCache() as cache:
            self.preview(cache)
            cache.invalidate()
            self.assertFalse(self.works[0].exists())
            self.assertTrue(self.source.is_file())
            self.assertTrue(self.tool.is_file())
            self.preview(cache)
            self.assertEqual(conversion.call_count, 2)

    def test_validation_error_also_releases_previous_decoded_iso(self):
        with self.pipeline(), PreviewCache() as cache:
            self.preview(cache)
            with self.assertRaises(service.UserError):
                self.preview(cache, seed='')
            self.assertFalse(self.works[0].exists())

    def test_cached_iso_changed_during_calculation_is_not_returned(self):
        with self.pipeline() as (build, _), PreviewCache() as cache:
            def change_decoded_input(*_):
                (self.works[0] / 'source.iso').write_bytes(b'changed during calculation')
                return [], self.summary
            build.side_effect = change_decoded_input
            with self.assertRaisesRegex(service.UserError, 'changé'):
                self.preview(cache)
            self.assertFalse(self.works[0].exists())


if __name__ == '__main__':
    unittest.main()
