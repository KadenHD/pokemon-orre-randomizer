"""Pinned downloads, cancellation, archive boundaries and shared texture views."""
import hashlib
import io
import json
from dataclasses import replace
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile

from orre_randomizer.hd_packs import ArchiveFragment, Pack, Part, PackStore, PACKS
from orre_randomizer.service import Cancelled, UserError

PNG = b"\x89PNG\r\n\x1a\n" + bytes(32)
DDS = b"DDS |\x00\x00\x00" + bytes(120)


class Packs(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = PackStore(self.root / "Shared")

    def archive(self, names):
        path = self.root / "pack.zip"
        with zipfile.ZipFile(path, "w") as archive:
            for name in names:
                archive.writestr(name, PNG)
        payload = path.read_bytes()
        part = Part("https://example.invalid/pinned.zip", hashlib.sha256(payload).hexdigest(), len(payload))
        return Pack("colosseum", "2026.11.11", len(PNG) * len(names), (part,)), path

    def install(self, pack, archive, **kwargs):
        with patch.object(self.store, "_download", return_value=archive):
            return self.store.install(pack, **kwargs)

    def test_install_pins_hashes_and_reuses_existing_version(self):
        pack, archive = self.archive(["root/tex1_4x4_deadbeef_6.png"])
        result = self.install(pack, archive)
        self.assertEqual(result["textures"], 1)
        self.assertTrue(self.store.installed(pack))
        self.assertTrue(self.store.install(pack)["already_installed"])

    def test_traversal_never_writes_outside_owned_stage(self):
        pack, archive = self.archive(["../tex1_4x4_deadbeef_6.png"])
        with self.assertRaises(UserError):
            self.install(pack, archive)
        self.assertFalse(self.store.location(pack).exists())
        self.assertFalse((self.root / "tex1_4x4_deadbeef_6.png").exists())
        self.assertFalse(list((self.store.root / "TexturePacks").glob("*.lock")))

    def test_cancel_does_not_publish_or_remove_another_version(self):
        pack, archive = self.archive(["tex1_4x4_deadbeef_6.png"])
        other = self.store.root / "TexturePacks/old/keep.txt"
        other.parent.mkdir(parents=True); other.write_text("keep")
        cancel = threading.Event(); cancel.set()
        with self.assertRaises(Cancelled):
            self.install(pack, archive, cancel=cancel)
        self.assertFalse(self.store.location(pack).exists())
        self.assertEqual(other.read_text(), "keep")

    def test_custom_texture_wins_without_changing_shared_pack(self):
        pack, archive = self.archive(["tex1_4x4_a_6.png", "tex1_4x4_b_6.png"])
        self.install(pack, archive)
        overlays = self.root / "overlays"; overlays.mkdir()
        (overlays / "tex1_4x4_a_6.png").write_bytes(PNG + b"custom")
        load = self.store.texture_view(pack, "GC6P01", overlays)
        target = load / "Textures/GC6P01"
        self.assertEqual((target / "tex1_4x4_a_6.png").read_bytes(), PNG + b"custom")
        self.assertEqual((self.store.location(pack) / "Textures/tex1_4x4_a_6.png").read_bytes(), PNG)
        base = self.store.location(pack) / "Textures/tex1_4x4_b_6.png"
        self.assertTrue(base.samefile(target / base.name))
        self.assertEqual(self.store.texture_view(pack, "GC6P01", overlays), load)

    def local_texture_pack(self, game, textures):
        archive = self.root / (game + ".zip")
        with zipfile.ZipFile(archive, "w") as output:
            for name, payload in textures.items():
                output.writestr(name, payload)
        payload = archive.read_bytes()
        pack = Pack(game, "fixture", sum(map(len, textures.values())),
                    (Part("", hashlib.sha256(payload).hexdigest(), len(payload)),))
        self.store.install(pack, local_archives=(archive,))
        return pack, archive

    def test_dependency_fills_missing_keys_without_replacing_game_or_custom_art(self):
        primary, _ = self.local_texture_pack("xd", {
            "tex1_4x4_a_14.png": PNG + b"primary-a", "tex1_4x4_b_14.png": PNG + b"primary-b"})
        fallback, _ = self.local_texture_pack("colosseum", {
            "tex1_4x4_m_a_14.dds": DDS + b"fallback-a",
            "tex1_4x4_b_14.dds": DDS + b"fallback-b", "tex1_4x4_c_14.dds": DDS + b"fallback-c"})
        custom = self.root / "custom"; custom.mkdir()
        (custom / "tex1_4x4_a_14.png").write_bytes(PNG + b"custom-a")
        load = self.store.texture_view(primary, "GXXP01", custom, fallback_packs=(fallback,))
        target = load / "Textures/GXXP01"
        self.assertEqual({p.name for p in target.iterdir()},
                         {"tex1_4x4_a_14.png", "tex1_4x4_b_14.png", "tex1_4x4_c_14.dds"})
        self.assertEqual((target / "tex1_4x4_a_14.png").read_bytes(), PNG + b"custom-a")
        self.assertTrue((target / "tex1_4x4_b_14.png").samefile(
            self.store.location(primary) / "Textures/tex1_4x4_b_14.png"))
        self.assertTrue((target / "tex1_4x4_c_14.dds").samefile(
            self.store.location(fallback) / "Textures/tex1_4x4_c_14.dds"))
        record = json.loads((load.parent / "complete.json").read_text("utf-8"))
        self.assertEqual(record["stock_files_by_pack"], {primary.key: 1, fallback.key: 1})

    def test_repairing_a_dependency_changes_the_view_and_preserves_its_old_files(self):
        primary, _ = self.local_texture_pack("xd", {"tex1_4x4_a_6.png": PNG})
        fallback, archive = self.local_texture_pack("colosseum", {"tex1_4x4_b_6.png": PNG + b"other"})
        old = self.store.texture_view(primary, "GXXP01", fallback_packs=(fallback,))
        self.store.install(fallback, force=True, local_archives=(archive,))
        new = self.store.texture_view(primary, "GXXP01", fallback_packs=(fallback,))
        self.assertNotEqual(old, new)
        self.assertEqual((old / "Textures/GXXP01/tex1_4x4_b_6.png").read_bytes(), PNG + b"other")
        self.assertEqual((new / "Textures/GXXP01/tex1_4x4_b_6.png").read_bytes(), PNG + b"other")

    def test_missing_dependency_cannot_reuse_an_older_view_or_trigger_a_download(self):
        primary, _ = self.local_texture_pack("xd", {"tex1_4x4_a_6.png": PNG})
        fallback, _ = self.local_texture_pack("colosseum", {"tex1_4x4_b_6.png": PNG})
        old = self.store.texture_view(primary, "GXXP01", fallback_packs=(fallback,))
        (self.store.location(fallback) / "installed.json").unlink()
        with patch.object(self.store, "_download", side_effect=AssertionError("No implicit download")):
            with self.assertRaises(UserError):
                self.store.texture_view(primary, "GXXP01", fallback_packs=(fallback,))
        self.assertTrue((old / "Textures/GXXP01/tex1_4x4_b_6.png").is_file())

    def test_partial_download_with_wrong_hash_is_not_installed(self):
        part = Part("https://example.invalid/pinned.zip", "0" * 64, 3)
        class Response(io.BytesIO):
            status = 200
            headers = {}
        with patch("urllib.request.urlopen", return_value=Response(b"bad")):
            with self.assertRaises(UserError):
                self.store._download(part, threading.Event(), lambda *_: None, 0, 3)
        self.assertFalse((self.store.root / "Downloads" / (part.sha256 + ".zip")).exists())

    def test_completed_pending_download_is_verified_and_published_without_a_request(self):
        payload = b"complete pinned archive"
        part = Part("https://example.invalid/pinned.zip", hashlib.sha256(payload).hexdigest(), len(payload))
        downloads = self.store.root / "Downloads"
        downloads.mkdir(parents=True)
        pending = downloads / (part.sha256 + ".part")
        pending.write_bytes(payload)
        with patch("urllib.request.urlopen", side_effect=AssertionError("Completed download requested again")):
            archive = self.store._download(part, threading.Event(), lambda *_: None, 0, part.size)
        self.assertEqual(archive.read_bytes(), payload)
        self.assertFalse(pending.exists())

    def test_corrupt_completed_pending_download_restarts_without_a_range(self):
        payload = b"valid archive"
        part = Part("https://example.invalid/pinned.zip", hashlib.sha256(payload).hexdigest(), len(payload))
        downloads = self.store.root / "Downloads"
        downloads.mkdir(parents=True)
        (downloads / (part.sha256 + ".part")).write_bytes(b"x" * part.size)

        class Response(io.BytesIO):
            status = 200
            headers = {}

        with patch("urllib.request.urlopen", return_value=Response(payload)) as request:
            archive = self.store._download(part, threading.Event(), lambda *_: None, 0, part.size)
        self.assertIsNone(request.call_args.args[0].get_header("Range"))
        self.assertEqual(archive.read_bytes(), payload)

    def test_short_response_keeps_received_bytes_and_resumes_the_next_request(self):
        payload = b"a pinned archive received in two responses"
        part = Part("https://example.invalid/pinned.zip", hashlib.sha256(payload).hexdigest(), len(payload))
        split = 12

        class Response(io.BytesIO):
            def __init__(self, data, status=200, headers=None):
                super().__init__(data)
                self.status = status
                self.headers = headers or {}

        with patch("urllib.request.urlopen", return_value=Response(payload[:split])):
            with self.assertRaises(UserError):
                self.store._download(part, threading.Event(), lambda *_: None, 0, part.size)
        pending = self.store.root / "Downloads" / (part.sha256 + ".part")
        self.assertEqual(pending.read_bytes(), payload[:split])
        headers = {"Content-Range": f"bytes {split}-{part.size - 1}/{part.size}"}
        with patch("urllib.request.urlopen", return_value=Response(payload[split:], 206, headers)) as request:
            archive = self.store._download(part, threading.Event(), lambda *_: None, 0, part.size)
        self.assertEqual(request.call_args.args[0].get_header("Range"), f"bytes={split}-")
        self.assertEqual(archive.read_bytes(), payload)
        self.assertFalse(pending.exists())

    def test_view_publication_retries_a_transient_windows_directory_lock(self):
        pack, archive = self.archive(["tex1_4x4_a_6.png"])
        self.install(pack, archive)
        rename = Path.rename
        attempts = []

        def temporarily_locked(path, destination):
            if path.name.startswith(".view-"):
                attempts.append(str(path))
                if len(attempts) < 3:
                    raise PermissionError("Temporary scanner handle")
            return rename(path, destination)

        with patch.object(Path, "rename", temporarily_locked), patch("orre_randomizer.hd_packs.time.sleep"):
            view = self.store.texture_view(pack, "GC6P01")
        self.assertEqual(len(attempts), 3)
        self.assertEqual((view / "Textures/GC6P01/tex1_4x4_a_6.png").read_bytes(), PNG)
        self.assertTrue((view.parent / "complete.json").is_file())

    def test_repair_keeps_the_old_texture_view_and_rebuilds_a_new_one(self):
        pack, archive = self.archive(["tex1_4x4_a_6.png"])
        self.install(pack, archive)
        overlays = self.root / "overlays"; overlays.mkdir()
        old_view = self.store.texture_view(pack, "GC6P01", overlays)
        # Damage only the owned installation, then restore the same pinned archive.
        (self.store.location(pack) / "Textures/tex1_4x4_a_6.png").unlink()
        pack, archive = self.archive(["tex1_4x4_a_6.png"])
        self.install(pack, archive, force=True)
        new_view = self.store.texture_view(pack, "GC6P01", overlays)
        self.assertNotEqual(old_view, new_view)
        self.assertEqual((old_view / "Textures/GC6P01/tex1_4x4_a_6.png").read_bytes(), PNG)
        self.assertEqual((new_view / "Textures/GC6P01/tex1_4x4_a_6.png").read_bytes(), PNG)

    def test_local_import_verifies_the_archive_and_preserves_it(self):
        pack, archive = self.archive(["tex1_4x4_a_6.png"])
        with patch.object(self.store, "_download", side_effect=AssertionError("network not expected")):
            self.store.install(pack, local_archives=[archive])
        self.assertTrue(archive.is_file())
        self.assertTrue(self.store.installed(pack))
        archive.write_bytes(b"different archive")
        with self.assertRaises(UserError):
            self.store.install(pack, local_archives=[archive], force=True)
        self.assertTrue(self.store.installed(pack))

    def test_dds_install_and_png_override_share_one_texture_identity(self):
        archive = self.root / "dds.zip"
        with zipfile.ZipFile(archive, "w") as target:
            target.writestr("source/TEX1_4x4_m_abc_14.DDS", DDS)
        payload = archive.read_bytes()
        pack = Pack("colosseum", "2.00", len(DDS),
                    (Part("", hashlib.sha256(payload).hexdigest(), len(payload)),))
        self.store.install(pack, local_archives=[archive])
        overlays = self.root / "overlays"; overlays.mkdir()
        (overlays / "tex1_4x4_abc_14.png").write_bytes(PNG)
        view = self.store.texture_view(pack, "GC6P01", overlays) / "Textures/GC6P01"
        self.assertEqual([p.name for p in view.iterdir()], ["tex1_4x4_abc_14.png"])
        self.assertEqual(len(list((self.store.location(pack) / "Textures").iterdir())), 1)

    def test_duplicate_selection_is_explicit_not_archive_order(self):
        from dataclasses import replace
        pack, archive = self.archive(["first/tex1_4x4_a_6.png", "second/tex1_4x4_a_6.png"])
        with self.assertRaises(UserError):
            self.install(pack, archive)
        pack = replace(pack, excluded_paths=("first/tex1_4x4_a_6.png",))
        self.install(pack, archive)
        self.assertTrue(self.store.installed(pack))

    def test_missing_distribution_source_never_downloads(self):
        with self.assertRaises(UserError):
            self.store._download(Part("", "a" * 64, 1), threading.Event(), lambda *_: None, 0, 1)

    def test_configured_folder_installs_automatically_without_zip_selection(self):
        pack, archive = self.archive(["tex1_4x4_a_6.png"])
        distribution = self.root / "Distribution"
        store = PackStore(self.root / "OtherShared", source=distribution)
        path = store.archive_source(pack, pack.parts[0])
        path.parent.mkdir(parents=True)
        path.write_bytes(archive.read_bytes())
        with patch("urllib.request.urlopen", side_effect=AssertionError("no network")):
            store.install(pack)
        self.assertTrue(store.installed(pack))
        self.assertTrue(path.is_file())

    def test_configured_url_uses_exact_same_layout_as_the_hosting_bundle(self):
        store = PackStore(self.root / "Shared", source="https://textures.example.test/orre/")
        for game, pack in PACKS.items():
            part = pack.parts[0]
            self.assertEqual(store.archive_source(pack, part),
                f"https://textures.example.test/orre/packs/{game}/{pack.version}/{part.sha256[:12]}.zip")
        with self.assertRaises(ValueError):
            PackStore(source="http://textures.example.test").archive_source(pack, part)

    def test_configured_folder_rejects_the_wrong_archive(self):
        pack, archive = self.archive(["tex1_4x4_a_6.png"])
        store = PackStore(self.root / "OtherShared", source=self.root / "Distribution")
        path = store.archive_source(pack, pack.parts[0])
        path.parent.mkdir(parents=True)
        path.write_bytes(bytes(archive.stat().st_size))
        with self.assertRaises(UserError):
            store.install(pack)
        self.assertFalse(store.location(pack).exists())


class FragmentDownloads(unittest.TestCase):
    class Response(io.BytesIO):
        def __init__(self, data, *, status=200, headers=None, chunk=None):
            super().__init__(data)
            self.status = status
            self.headers = headers or {}
            self.chunk = chunk

        def read(self, size=-1):
            return super().read(min(size, self.chunk) if self.chunk else size)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = PackStore(self.root / "Shared")
        self.chunks = (b"first pinned fragment", b"second pinned fragment")
        self.payload = b"".join(self.chunks)
        self.part = Part("", hashlib.sha256(self.payload).hexdigest(), len(self.payload), "original.zip",
                         tuple(ArchiveFragment(f"https://example.invalid/archive.zip.00{index + 1}",
                                               hashlib.sha256(data).hexdigest(), len(data),
                                               f"archive.zip.00{index + 1}")
                               for index, data in enumerate(self.chunks)))
        self.pending = self.store.root / "Downloads" / (self.part.sha256 + ".part")
        self.pending.parent.mkdir(parents=True)

    def download(self, part=None, *, cancel=None, progress=None, source=None):
        part = part or self.part
        return self.store._download(part, cancel or threading.Event(), progress or (lambda *_: None),
                                    0, part.size, source=source)

    def response(self, index, *, start=0, status=None):
        size = len(self.chunks[index])
        return self.Response(self.chunks[index][start:], status=status or (206 if start else 200),
                             headers={"Content-Range": f"bytes {start}-{size - 1}/{size}"} if start else {})

    def test_real_catalog_pins_the_published_original_zip_and_two_fragments(self):
        part = PACKS["xd"].parts[0]
        self.assertEqual(part.sha256, "56bbf26551f26b7bdb1d0d7d4a6eb7073cf4f8fef72130648bd97abde8851cf2")
        self.assertEqual([fragment.size for fragment in part.fragments], [1900000000, 1395188617])
        self.assertEqual(sum(fragment.size for fragment in part.fragments), part.size)
        self.assertEqual([fragment.sha256 for fragment in part.fragments], [
            "c79d409370286de0ea54efc2d76bac088bcb7506c27032a2906ca0715a59b9da",
            "2f0be080df96ba6274c9ed784bc4f90c50f0c2a5556b58f23dc3178dd1d985fe"])
        self.assertEqual([fragment.filename for fragment in part.fragments],
                         ["xd-1.0-56bbf26551f2.zip.001", "xd-1.0-56bbf26551f2.zip.002"])
        self.assertFalse(part.url)
        base = "https://github.com/KadenHD/pokemon-orre-hd-packs/releases/download/packs-2026-11-18/"
        self.assertEqual([fragment.url for fragment in part.fragments],
                         [base + fragment.filename for fragment in part.fragments])
        self.assertEqual(PACKS["colosseum"].parts[0].url, base + "colosseum-2.00-4cac6314d8b3.zip")
        self.assertTrue(self.store.downloads_available(PACKS["xd"]))
        self.assertTrue(self.store.downloads_available(PACKS["colosseum"]))

    def test_rejects_invalid_fragment_and_parent_metadata_before_any_request(self):
        fragment = self.part.fragments[0]
        invalid = ({"url": "http://example.invalid/a"}, {"url": "https://user:secret@example.invalid/a"},
                   {"url": "https://example.invalid/a#fragment"}, {"url": "https://example.invalid/a b"},
                   {"url": "https://example.invalid:bad/a"}, {"url": "https://example.invalid/a\x00"},
                   {"sha256": "x" * 64},
                   {"size": 0}, {"size": True}, {"filename": "../outside"},
                   {"filename": "C:\\outside"}, {"filename": "a\n.zip"}, {"filename": ".."})
        for change in invalid:
            with self.subTest(change=change), self.assertRaises(ValueError):
                replace(fragment, **change)
        with self.assertRaises(ValueError):
            replace(self.part, size=self.part.size + 1)
        with self.assertRaises(ValueError):
            replace(self.part, fragments=list(self.part.fragments))
        with self.assertRaises(ValueError):
            replace(self.part, fragments=(object(),))

    def test_fragment_transport_is_available_only_when_every_required_url_is_configured(self):
        pack = Pack("xd", "test", 1, (self.part,))
        self.assertTrue(self.store.downloads_available(pack))
        unavailable = replace(self.part, fragments=(self.part.fragments[0],
                                                   replace(self.part.fragments[1], url="")))
        self.assertFalse(self.store.downloads_available(replace(pack, parts=(unavailable,))))
        self.assertTrue(PackStore(self.root, source=self.root / "Distribution").downloads_available(
            replace(pack, parts=(unavailable,))))

    def test_fresh_fragments_are_assembled_without_temporary_fragment_files(self):
        with patch("urllib.request.urlopen", side_effect=[self.response(0), self.response(1)]) as requests:
            archive = self.download()
        self.assertEqual(archive.read_bytes(), self.payload)
        self.assertEqual([call.args[0].full_url for call in requests.call_args_list],
                         [fragment.url for fragment in self.part.fragments])
        self.assertTrue(all(call.args[0].get_header("Range") is None for call in requests.call_args_list))
        self.assertEqual(list(self.pending.parent.iterdir()), [archive])

    def test_complete_pending_fragments_are_verified_without_any_request_or_configured_url(self):
        self.pending.write_bytes(self.payload)
        part = replace(self.part, fragments=tuple(replace(fragment, url="") for fragment in self.part.fragments))
        with patch("urllib.request.urlopen", side_effect=AssertionError("no network")):
            archive = self.download(part)
        self.assertEqual(archive.read_bytes(), self.payload)
        self.assertFalse(self.pending.exists())

    def test_complete_prefix_is_verified_then_partial_fragment_uses_its_local_offset(self):
        self.pending.write_bytes(self.chunks[0] + self.chunks[1][:7])
        with patch("urllib.request.urlopen", return_value=self.response(1, start=7)) as request:
            archive = self.download()
        self.assertEqual(request.call_count, 1)
        self.assertEqual(request.call_args.args[0].full_url, self.part.fragments[1].url)
        self.assertEqual(request.call_args.args[0].get_header("Range"), "bytes=7-")
        self.assertEqual(archive.read_bytes(), self.payload)

    def test_ignored_range_restarts_only_the_current_fragment(self):
        self.pending.write_bytes(self.chunks[0] + b"bad-prefix")
        with patch("urllib.request.urlopen", return_value=self.response(1)) as request:
            archive = self.download()
        self.assertEqual(request.call_args.args[0].get_header("Range"), "bytes=10-")
        self.assertEqual(archive.read_bytes(), self.payload)

    def test_corrupt_complete_first_fragment_discards_untrusted_following_bytes(self):
        self.pending.write_bytes(b"x" * len(self.chunks[0]) + self.chunks[1])
        with patch("urllib.request.urlopen", side_effect=[self.response(0), self.response(1)]) as requests:
            archive = self.download()
        self.assertEqual(requests.call_count, 2)
        self.assertTrue(all(call.args[0].get_header("Range") is None for call in requests.call_args_list))
        self.assertEqual(archive.read_bytes(), self.payload)

    def test_corrupt_complete_later_fragment_preserves_the_verified_prefix(self):
        self.pending.write_bytes(self.chunks[0] + b"x" * len(self.chunks[1]))
        with patch("urllib.request.urlopen", return_value=self.response(1)) as request:
            archive = self.download()
        self.assertEqual(request.call_count, 1)
        self.assertEqual(request.call_args.args[0].full_url, self.part.fragments[1].url)
        self.assertIsNone(request.call_args.args[0].get_header("Range"))
        self.assertEqual(archive.read_bytes(), self.payload)

    def test_bad_downloaded_fragment_is_truncated_to_its_beginning_and_can_be_retried(self):
        with patch("urllib.request.urlopen", side_effect=[self.response(0),
                   self.Response(b"x" * len(self.chunks[1]))]):
            with self.assertRaises(UserError):
                self.download()
        self.assertEqual(self.pending.read_bytes(), self.chunks[0])
        self.assertFalse(self.pending.with_suffix(".zip").exists())
        with patch("urllib.request.urlopen", return_value=self.response(1)) as request:
            archive = self.download()
        self.assertIsNone(request.call_args.args[0].get_header("Range"))
        self.assertEqual(archive.read_bytes(), self.payload)

    def test_short_response_preserves_partial_fragment_then_resumes_locally(self):
        with patch("urllib.request.urlopen", side_effect=[self.response(0), self.Response(self.chunks[1][:5])]):
            with self.assertRaises(UserError):
                self.download()
        self.assertEqual(self.pending.read_bytes(), self.chunks[0] + self.chunks[1][:5])
        with patch("urllib.request.urlopen", return_value=self.response(1, start=5)) as request:
            archive = self.download()
        self.assertEqual(request.call_args.args[0].get_header("Range"), "bytes=5-")
        self.assertEqual(archive.read_bytes(), self.payload)

    def test_cancel_keeps_verified_prefix_and_received_current_bytes(self):
        cancel = threading.Event()
        def progress(percent, _):
            if percent > 70 * len(self.chunks[0]) // self.part.size:
                cancel.set()
        with patch("urllib.request.urlopen", side_effect=[self.response(0),
                   self.Response(self.chunks[1], chunk=3)]):
            with self.assertRaises(Cancelled):
                self.download(cancel=cancel, progress=progress)
        self.assertEqual(self.pending.read_bytes(), self.chunks[0] + self.chunks[1][:3])
        self.assertFalse(self.pending.with_suffix(".zip").exists())

    def test_network_failure_preserves_the_verified_prefix(self):
        with patch("urllib.request.urlopen", side_effect=[self.response(0), OSError("connection lost")]):
            with self.assertRaises(UserError):
                self.download()
        self.assertEqual(self.pending.read_bytes(), self.chunks[0])

    def test_invalid_content_range_never_appends_to_the_pending_fragment(self):
        prefix = self.chunks[0] + self.chunks[1][:5]
        for content_range in ("bytes 4-21/22", "bytes 5-21/999", "bytes 5-99/22", "garbage"):
            self.pending.write_bytes(prefix)
            with self.subTest(content_range=content_range), patch("urllib.request.urlopen", return_value=
                    self.Response(self.chunks[1][5:], status=206, headers={"Content-Range": content_range})):
                with self.assertRaises(UserError):
                    self.download()
            self.assertEqual(self.pending.read_bytes(), prefix)

    def test_oversized_fragment_is_removed_without_losing_the_verified_prefix(self):
        with patch("urllib.request.urlopen", side_effect=[self.response(0), self.Response(self.chunks[1] + b"extra")]):
            with self.assertRaises(UserError):
                self.download()
        self.assertEqual(self.pending.read_bytes(), self.chunks[0])

    def test_full_zip_sha_is_required_even_when_every_fragment_matches(self):
        part = replace(self.part, sha256="0" * 64)
        with patch("urllib.request.urlopen", side_effect=[self.response(0), self.response(1)]):
            with self.assertRaises(UserError):
                self.download(part)
        self.assertFalse((self.pending.parent / (part.sha256 + ".zip")).exists())
        self.assertEqual((self.pending.parent / (part.sha256 + ".part")).read_bytes(), self.payload)

    def test_extra_pending_suffix_is_discarded_after_verifying_all_fragments(self):
        self.pending.write_bytes(self.payload + b"untrusted trailing bytes")
        with patch("urllib.request.urlopen", side_effect=AssertionError("no network")):
            self.assertEqual(self.download().read_bytes(), self.payload)

    def test_explicit_full_archive_url_keeps_the_existing_transport(self):
        part = replace(self.part, url="https://example.invalid/full.zip")
        with patch("urllib.request.urlopen", return_value=self.Response(self.payload)) as request:
            archive = self.download(part)
        self.assertEqual(request.call_count, 1)
        self.assertEqual(request.call_args.args[0].full_url, part.url)
        self.assertEqual(archive.read_bytes(), self.payload)

    def test_configured_folder_still_installs_one_full_zip_with_fragment_metadata(self):
        source = self.root / "original.zip"
        with zipfile.ZipFile(source, "w") as archive:
            archive.writestr("tex1_4x4_a_6.png", PNG)
        payload = source.read_bytes()
        split = len(payload) // 2
        fragments = tuple(ArchiveFragment("", hashlib.sha256(data).hexdigest(), len(data))
                          for data in (payload[:split], payload[split:]))
        part = Part("", hashlib.sha256(payload).hexdigest(), len(payload), fragments=fragments)
        pack = Pack("xd", "test", len(PNG), (part,))
        store = PackStore(self.root / "OtherShared", source=self.root / "Distribution")
        full_archive = store.archive_source(pack, part)
        full_archive.parent.mkdir(parents=True)
        full_archive.write_bytes(payload)
        with patch("urllib.request.urlopen", side_effect=AssertionError("no network")):
            store.install(pack)
        self.assertTrue(store.installed(pack))
        self.assertTrue(full_archive.is_file())

    def test_fragment_transport_installs_and_records_the_full_zip_identity(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as archive:
            archive.writestr("root/tex1_4x4_a_6.png", PNG)
        payload = data.getvalue()
        split = len(payload) // 2
        chunks = (payload[:split], payload[split:])
        fragments = tuple(ArchiveFragment(f"https://example.invalid/pack.zip.00{index}",
                                          hashlib.sha256(chunk).hexdigest(), len(chunk))
                          for index, chunk in enumerate(chunks, 1))
        part = Part("", hashlib.sha256(payload).hexdigest(), len(payload), fragments=fragments)
        pack = Pack("xd", "test", len(PNG), (part,))
        with patch("urllib.request.urlopen", side_effect=[self.Response(chunk) for chunk in chunks]) as requests:
            result = self.store.install(pack)
        self.assertEqual(requests.call_count, 2)
        self.assertEqual(result["textures"], 1)
        self.assertTrue(self.store.installed(pack))
        marker = json.loads((self.store.location(pack) / "installed.json").read_text("utf-8"))
        self.assertEqual(marker["archives"], [part.sha256])
        self.assertEqual((self.store.location(pack) / "Textures/tex1_4x4_a_6.png").read_bytes(), PNG)
        self.assertEqual(list((self.store.root / "Downloads").iterdir()), [])


if __name__ == "__main__":
    unittest.main()
