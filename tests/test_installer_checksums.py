"""Installer checksums preserve the audited ZIPs and fail without partial assets."""
import copy
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from orre_randomizer.update_service import allowed_download, release_update
from scripts import release_checksums as checksums
from scripts import verify_release


def pe(machine=0x14c):
    data = bytearray(256)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 60, 128)
    data[128:132] = b"PE\0\0"
    struct.pack_into("<H", data, 132, machine)
    return bytes(data)


class InstallerChecksumTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="installer checksums ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.release = self.root / "public"
        self.release.mkdir()
        self.work = self.root / "compiled"
        self.work.mkdir()
        self.base = "pokemon-orre-randomizer-2.1.2"
        self.source = self.base + "-source.zip"
        self.windows = self.base + "-windows-x64.zip"
        self.name = self.base + "-windows-x64-setup.exe"
        self.manifest = self.release / checksums.MANIFEST
        self.installer = self.work / self.name
        self.installer.write_bytes(pe() + b"compiled installer payload" * 100)
        self.original_records = {}
        for name, payload in ((self.source, b"audited source ZIP"), (self.windows, b"audited Windows ZIP")):
            (self.release / name).write_bytes(payload)
            self.original_records[name] = {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
        self.manifest.write_text(json.dumps(self.original_records, indent=2) + "\n", encoding="utf-8")
        self.original = self.manifest.read_bytes()

    def assert_unpublished(self):
        self.assertEqual(self.manifest.read_bytes(), self.original)
        self.assertFalse((self.release / self.name).exists())
        self.assertEqual(set(path.name for path in self.release.iterdir()),
                         {self.source, self.windows, checksums.MANIFEST})

    def test_publishes_the_separate_installer_and_preserves_both_zip_records(self):
        before = {path.name: path.read_bytes() for path in self.release.iterdir()}
        installer_bytes = self.installer.read_bytes()
        result = checksums.publish_installer(self.release, self.installer)
        self.assertEqual(checksums.load_manifest(self.manifest), result)
        self.assertEqual(list(result), [self.source, self.windows, self.name])
        self.assertEqual({key: result[key] for key in self.original_records}, self.original_records)
        for name in (self.source, self.windows):
            self.assertEqual((self.release / name).read_bytes(), before[name])
        self.assertEqual(result[self.name], {"bytes": len(installer_bytes),
            "sha256": hashlib.sha256(installer_bytes).hexdigest()})
        self.assertEqual((self.release / self.name).read_bytes(), installer_bytes)
        self.assertEqual(self.installer.read_bytes(), installer_bytes)
        self.assertTrue(verify_release.verify_installer(self.release / self.name, result[self.name])[
            "windows_installer_pe_verified"])
        self.assertEqual(len(list(self.release.iterdir())), 4)

    def test_legacy_installer_only_build_keeps_the_absent_source_zip_record(self):
        (self.release / self.source).unlink()
        result = checksums.publish_installer(self.release, self.installer)
        self.assertEqual(result[self.source], self.original_records[self.source])
        self.assertFalse((self.release / self.source).exists())

    def test_release_audit_preflights_two_zip_and_three_asset_manifests(self):
        before, installers = verify_release.verify_manifest_assets(self.release)
        self.assertEqual(before, self.original_records)
        self.assertEqual(installers, {})
        expected = checksums.publish_installer(self.release, self.installer)
        manifest, installers = verify_release.verify_manifest_assets(self.release)
        self.assertEqual(manifest, expected)
        self.assertEqual(set(installers), {self.name})
        self.assertTrue(installers[self.name]["windows_installer_pe_verified"])
        for name in manifest:
            path = self.release / name
            original = path.read_bytes()
            path.write_bytes(original + b"tampered")
            with self.subTest(name=name), self.assertRaisesRegex(RuntimeError, "hash mismatch"):
                verify_release.verify_manifest_assets(self.release)
            path.write_bytes(original)

    def test_installer_and_portable_updates_use_the_same_published_hashes(self):
        manifest = checksums.publish_installer(self.release, self.installer)
        assets = [{"name": name, "state": "uploaded", "size": record["bytes"],
                   "digest": "sha256:" + record["sha256"],
                   "browser_download_url": "https://github.com/KadenHD/pokemon-orre-randomizer/"
                       "releases/download/v2.1.2/" + name} for name, record in manifest.items()]
        payload = {"tag_name": "v2.1.2", "draft": False, "prerelease": False, "assets": assets}
        for kind, name in (("installer", self.name), ("portable", self.windows)):
            update = release_update(payload, "2.1.1", kind)
            self.assertTrue(allowed_download(update))
            self.assertEqual(update.sha256, manifest[name]["sha256"])
            self.assertEqual(update.size, manifest[name]["bytes"])
        # A checksummed manifest does not permit updates with missing GitHub digests.
        for asset in assets:
            asset.pop("digest")
        self.assertIsNone(release_update(payload, "2.1.1"))

    def test_existing_installer_and_recorded_installer_are_never_overwritten(self):
        destination = self.release / self.name
        destination.write_bytes(b"existing unrelated file")
        with self.assertRaises(FileExistsError):
            checksums.publish_installer(self.release, self.installer)
        self.assertEqual(destination.read_bytes(), b"existing unrelated file")
        self.assertEqual(self.manifest.read_bytes(), self.original)
        destination.unlink()
        checksums.publish_installer(self.release, self.installer)
        destination.unlink()
        recorded = self.manifest.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "already recorded"):
            checksums.publish_installer(self.release, self.installer)
        self.assertEqual(self.manifest.read_bytes(), recorded)
        self.assertFalse(destination.exists())

    def test_wrong_version_damaged_zip_and_invalid_pe_leave_the_manifest_unchanged(self):
        wrong_version = self.work / self.name.replace("2.1.2", "2.1.3")
        wrong_version.write_bytes(self.installer.read_bytes())
        with self.assertRaisesRegex(RuntimeError, "version differs"):
            checksums.publish_installer(self.release, wrong_version)
        self.assert_unpublished()
        windows = self.release / self.windows
        windows.write_bytes(b"modified after audit")
        with self.assertRaisesRegex(RuntimeError, "hash mismatch"):
            checksums.publish_installer(self.release, self.installer)
        windows.write_bytes(b"audited Windows ZIP")
        self.assert_unpublished()
        self.installer.write_bytes(b"not an executable")
        with self.assertRaisesRegex(RuntimeError, "PE header"):
            checksums.publish_installer(self.release, self.installer)
        self.assert_unpublished()

    def test_copy_failure_cleans_staging_without_publishing_anything(self):
        def broken_copy(source, output, length):
            output.write(b"partial copy")
            raise OSError("simulated full disk")
        with patch.object(checksums.shutil, "copyfileobj", side_effect=broken_copy):
            with self.assertRaisesRegex(OSError, "full disk"):
                checksums.publish_installer(self.release, self.installer)
        self.assert_unpublished()

    def test_changed_copy_is_not_recorded_even_when_the_pe_header_is_valid(self):
        with patch.object(checksums.shutil, "copyfileobj", side_effect=lambda source, output, length:
                          output.write(pe() + b"modified while copying")):
            with self.assertRaisesRegex(RuntimeError, "hash mismatch"):
                checksums.publish_installer(self.release, self.installer)
        self.assert_unpublished()

    def test_atomic_manifest_failure_removes_only_the_new_owned_installer(self):
        with patch.object(checksums.os, "replace", side_effect=PermissionError("locked manifest")):
            with self.assertRaisesRegex(PermissionError, "locked manifest"):
                checksums.publish_installer(self.release, self.installer)
        self.assert_unpublished()

    def test_interruption_after_atomic_publication_keeps_the_committed_installer(self):
        real_replace = os.replace
        def committed_then_interrupted(source, destination):
            real_replace(source, destination)
            raise KeyboardInterrupt("interrupted after the rename")
        with patch.object(checksums.os, "replace", side_effect=committed_then_interrupted):
            with self.assertRaises(KeyboardInterrupt):
                checksums.publish_installer(self.release, self.installer)
        manifest = checksums.load_manifest(self.manifest)
        checksums.verify_installer(self.release / self.name, manifest[self.name])
        self.assertEqual(len(manifest), 3)
        self.assertFalse(any(path.name.startswith(".") for path in self.release.iterdir()))

    def test_streaming_checksum_covers_more_than_one_buffer(self):
        payload = pe() + b"multi-buffer payload" * 150000
        self.installer.write_bytes(payload)
        result = checksums.publish_installer(self.release, self.installer)
        self.assertEqual(result[self.name], {"bytes": len(payload),
                         "sha256": hashlib.sha256(payload).hexdigest()})

    def test_concurrent_installer_creation_is_preserved(self):
        def competing_link(source, destination):
            Path(destination).write_bytes(b"someone else's installer")
            raise FileExistsError("concurrent installer")
        with patch.object(checksums, "_publish_exclusive", side_effect=competing_link):
            with self.assertRaises(FileExistsError):
                checksums.publish_installer(self.release, self.installer)
        self.assertEqual((self.release / self.name).read_bytes(), b"someone else's installer")
        self.assertEqual(self.manifest.read_bytes(), self.original)
        self.assertFalse(any(path.name.startswith(".") for path in self.release.iterdir()))

    def test_concurrently_changed_manifest_is_preserved_and_new_installer_removed(self):
        real_publish = checksums._publish_exclusive
        changed = self.original + b" "
        def manifest_changes(source, destination):
            real_publish(source, destination)
            self.manifest.write_bytes(changed)
        with patch.object(checksums, "_publish_exclusive", side_effect=manifest_changes):
            with self.assertRaisesRegex(RuntimeError, "manifest changed"):
                checksums.publish_installer(self.release, self.installer)
        self.assertEqual(self.manifest.read_bytes(), changed)
        self.assertFalse((self.release / self.name).exists())
        self.assertFalse(any(path.name.startswith(".") for path in self.release.iterdir()))

    def test_native_publication_primitive_refuses_to_replace_a_concurrent_file(self):
        destination = self.release / self.name
        destination.write_bytes(b"existing")
        with self.assertRaises(FileExistsError):
            checksums._publish_exclusive(self.installer, destination)
        self.assertEqual(destination.read_bytes(), b"existing")
        self.assertTrue(self.installer.is_file())

    def test_source_only_and_complete_manifests_remain_supported(self):
        self.manifest.write_text(json.dumps({self.source: self.original_records[self.source]}), encoding="utf-8")
        self.assertEqual(len(checksums.load_manifest(self.manifest)), 1)
        with self.assertRaisesRegex(RuntimeError, "Windows archive"):
            checksums.publish_installer(self.release, self.installer)
        self.manifest.write_bytes(self.original)
        self.assertEqual(len(checksums.load_manifest(self.manifest)), 2)
        checksums.publish_installer(self.release, self.installer)
        self.assertEqual(len(checksums.load_manifest(self.manifest)), 3)

    def test_manifest_rejects_unsafe_names_mixed_versions_and_invalid_records(self):
        cases = [[], {}, {"../" + self.source: self.original_records[self.source]},
                 {self.source.replace("source.zip", "source.exe"): self.original_records[self.source]},
                 {**self.original_records, self.name.replace("2.1.2", "2.1.3"): checksums.checksum(self.installer)},
                 {self.name: checksums.checksum(self.installer)}]
        for key, value in (("bytes", True), ("bytes", 0), ("bytes", "5"), ("sha256", "0" * 63),
                           ("sha256", "A" * 64), ("sha256", None), ("extra", "unexpected")):
            changed = copy.deepcopy(self.original_records)
            changed[self.windows][key] = value
            cases.append(changed)
        for manifest in cases:
            with self.subTest(manifest=manifest):
                self.manifest.write_text(json.dumps(manifest), encoding="utf-8")
                with self.assertRaises(RuntimeError):
                    checksums.load_manifest(self.manifest)
        self.manifest.write_text('{"' + self.source + '":{},"' + self.source + '":{}}', encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "Duplicate"):
            checksums.load_manifest(self.manifest)

    def test_executable_audit_checks_hash_size_and_pe_without_execution(self):
        for payload in (pe(0x14c), pe(0x8664)):
            self.installer.write_bytes(payload)
            self.assertTrue(verify_release.verify_installer(self.installer, checksums.checksum(self.installer))[
                "windows_installer_pe_verified"])
        for payload in (pe(0xaa64), b"MZ" * 32, pe()[:130]):
            self.installer.write_bytes(payload)
            with self.assertRaisesRegex(RuntimeError, "PE header"):
                verify_release.verify_installer(self.installer, checksums.checksum(self.installer))
        self.installer.write_bytes(pe())
        record = checksums.checksum(self.installer)
        for changed in ({**record, "bytes": record["bytes"] + 1}, {**record, "sha256": "0" * 64}):
            with self.assertRaisesRegex(RuntimeError, "hash mismatch"):
                verify_release.verify_installer(self.installer, changed)

    def test_cli_uses_paths_with_spaces_and_returns_the_complete_manifest(self):
        command = [sys.executable, "-X", "utf8", str(Path(checksums.__file__).resolve()),
                   "--release-dir", str(self.release), "--installer", str(self.installer)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=15, check=True)
        self.assertEqual(json.loads(result.stdout), checksums.load_manifest(self.manifest))
        repeated = subprocess.run(command, capture_output=True, text=True, timeout=15)
        self.assertNotEqual(repeated.returncode, 0)
        self.assertIn("already recorded", repeated.stderr)

    def test_installer_build_publishes_after_the_requested_smoke_and_stops_on_failure(self):
        root = Path(__file__).resolve().parents[1]
        script = (root / "scripts/build_installer.ps1").read_text("utf-8")
        publish = script.index("& python -X utf8")
        self.assertLess(script.index("Verified the installed files, app diagnostics, and uninstall."), publish)
        self.assertIn("release_checksums.py", script[publish:])
        self.assertIn("if ($LASTEXITCODE -ne 0) { throw", script[publish:])
        workflow = (root / ".github/workflows/existing-release-installer.yml").read_text("utf-8")
        self.assertLess(workflow.index("cmp published/SHA256SUMS.json"), workflow.index("gh release upload"))
        uploads = [line.strip() for line in workflow.splitlines() if line.strip().startswith("gh release upload")]
        self.assertEqual(len(uploads), 2)
        self.assertIn("*-setup.exe", uploads[0])
        self.assertNotIn("--clobber", uploads[0])
        self.assertIn("SHA256SUMS.json", uploads[1])
        self.assertIn("--clobber", uploads[1])


if __name__ == "__main__":
    unittest.main()
