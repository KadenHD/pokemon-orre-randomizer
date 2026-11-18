"""Validation launcher guards original data and records the native process code."""
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("run_dolphin_validation",
    Path(__file__).resolve().parents[1] / "scripts/run_dolphin_validation.py")
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class DolphinValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.build = self.root / "build"
        self.emulator = self.build / "portable/Dolphin.exe"
        self.emulator.parent.mkdir(parents=True)
        self.emulator.write_bytes(b"test executable identity")
        (self.emulator.parent / "portable.txt").write_bytes(b"")
        self.iso = self.root / "own image.iso"
        self.iso.write_bytes(b"image bytes")
        self.profile = self.build / "isolated profile"
        (self.profile / "Config").mkdir(parents=True)
        (self.profile / "GC").mkdir()
        self.config = self.profile / "Config/Dolphin.ini"
        self.config.write_text("[Core]\nMemcardAPath = " + (self.profile / "GC/card.raw").as_posix() +
                               "\n[General]\nGDBPort = 55001\n", encoding="utf-8")
        self.personal = self.root / "personal"
        self.personal.mkdir()
        (self.personal / "outside-known-directories.bin").write_bytes(b"guard all files")
        (self.personal / "GC").mkdir()
        (self.personal / "GC/card.raw").write_bytes(b"original card")
        self.report = self.build / "run.json"

    def tearDown(self):
        self.temp.cleanup()

    def validate(self, **changes):
        arguments = dict(emulator=self.emulator, iso=self.iso, profile=self.profile,
                         report=self.report, personal_profile=self.personal, workspace=self.root)
        arguments.update(changes)
        return launcher.validate_job(**arguments)

    def texture_view(self, suffix=".png"):
        from PIL import Image
        from orre_randomizer.hd_packs import PACKS
        pack = PACKS["xd"]
        view = self.build / "Shared/TextureViews" / (pack.key + "-GXXP01-initial-" + "a" * 24) / "Load"
        source = view / "Textures/GXXP01" / ("tex1_32x32_0123456789abcdef_14" + suffix)
        source.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new("RGBA", (128, 128), (100, 120, 160, 255))
        image.save(source, **({"pixel_format": "DXT5"} if suffix == ".dds" else {}))
        (view.parent / "complete.json").write_text(json.dumps({"pack": pack.key, "game_id": "GXXP01", "overlays": 0}))
        marker = self.build / "Shared/TexturePacks" / pack.key / "installed.json"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps({"key": pack.key, "archives": [p.sha256 for p in pack.parts]}))
        target = self.profile / "Load/Textures/GXXP01" / source.name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.hardlink_to(source)
        return view, source, target

    def run_job(self, code=0, callback=None):
        class Process:
            def __init__(self, argv, **kwargs):
                self.pid = 12345
                self.argv = argv
                kwargs["stdout"].write(b"native stdout")
                kwargs["stderr"].write(b"native stderr")

            def wait(self):
                if callback:
                    callback()
                return code
        with patch.object(launcher.subprocess, "Popen", Process), patch("sys.stdout", new_callable=io.StringIO):
            return launcher.run_validation(self.emulator, self.iso, self.profile, self.report,
                self.personal, workspace=self.root)

    def test_native_zero_exit_guard_all_profile_files_and_no_shell_quoting(self):
        result = self.run_job()
        self.assertTrue(result["successful_process_and_preservation"])
        self.assertEqual(result["return_code"], 0)
        self.assertEqual(result["argv"], [str(self.emulator), "-u", str(self.profile), "-e", str(self.iso),
                                          "-C", "Dolphin.DSP.Volume=0"])
        self.assertIn("outside-known-directories.bin", result["personal_profile_before"])
        self.assertEqual(result["pid"], 12345)
        self.assertEqual(Path(result["stdout"]).read_bytes(), b"native stdout")
        self.assertEqual(Path(result["stderr"]).read_bytes(), b"native stderr")
        self.assertEqual(json.loads(self.report.read_text("utf-8")), result)

    def test_nonzero_native_exit_never_becomes_success(self):
        result = self.run_job(code=1)
        self.assertEqual(result["return_code"], 1)
        self.assertEqual(result["return_code_hex"], "0x00000001")
        self.assertFalse(result["successful_process_and_preservation"])
        self.assertTrue(result["personal_profile_unchanged"])

    def test_detects_personal_mutation_without_restoring_or_overwriting_it(self):
        selected = self.personal / "GC/card.raw"
        result = self.run_job(callback=lambda: selected.write_bytes(b"external write"))
        self.assertEqual(result["personal_profile_changed"], ["GC/card.raw"])
        self.assertFalse(result["successful_process_and_preservation"])
        self.assertEqual(selected.read_bytes(), b"external write")

    def test_detects_image_removed_while_running_and_still_writes_report(self):
        result = self.run_job(callback=self.iso.unlink)
        self.assertEqual(result["protected_files_changed"], [str(self.iso)])
        self.assertFalse(result["successful_process_and_preservation"])
        self.assertEqual(result["protected_files_after"][str(self.iso)], {"exists": False})

    def test_rejects_profiles_and_emulators_outside_build(self):
        for arguments in (dict(profile=self.personal), dict(emulator=self.root / "Dolphin.exe"),
                          dict(report=self.root / "outside.json")):
            with self.subTest(arguments=arguments), self.assertRaises((ValueError, FileNotFoundError)):
                self.validate(**arguments)

    def test_rejects_external_memory_card_and_game_setting_overrides(self):
        path = (self.personal / "GC/card.raw").as_posix()
        self.config.write_text("[Core]\nMemcardAPath = " + path, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "escapes"):
            self.validate()
        self.config.write_text("[Core]\n", encoding="utf-8")
        (self.profile / "GameSettings").mkdir()
        (self.profile / "GameSettings/GC6P01.ini").write_text("[Core]\nMemcardBPath = " + path, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "escapes"):
            self.validate()

    def test_missing_portable_fallback_or_existing_report_refused(self):
        portable = self.emulator.parent / "portable.txt"
        portable.unlink()
        with self.assertRaisesRegex(ValueError, "portable"):
            self.validate()
        portable.write_bytes(b"")
        self.report.write_text("existing result", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            self.validate()
        self.assertEqual(self.report.read_text("utf-8"), "existing result")

    def test_profile_hardlinks_to_original_are_refused(self):
        (self.profile / "GC/linked.raw").hardlink_to(self.personal / "GC/card.raw")
        with self.assertRaisesRegex(ValueError, "Hardlinked"):
            self.validate()

    def test_readonly_pinned_texture_links_require_explicit_opt_in(self):
        view, source, target = self.texture_view()
        with self.assertRaisesRegex(ValueError, "Hardlinked"):
            self.validate()
        self.config.write_text("[General]\nLoadPath = " + (self.profile / "Load").as_posix())
        result = self.validate(readonly_texture_view=view)
        self.assertEqual(result[2], self.profile)
        self.assertTrue(os.path.samefile(source, target))

    def test_readonly_dds_links_are_validated_without_rewriting_any_pixels(self):
        view, source, target = self.texture_view(".dds")
        before = source.read_bytes()
        self.validate(readonly_texture_view=view)
        self.assertEqual(source.read_bytes(), before)
        self.assertEqual(target.read_bytes(), before)

    def test_real_dolphin_mipmap_and_arbitrary_mip_suffixes_remain_permitted(self):
        view, source, target = self.texture_view(".dds")
        stem = source.stem
        for suffix in ("_mip1", "_arb", "_arb_mip2"):
            target.unlink()
            renamed = source.with_name(stem + suffix + ".dds")
            source.rename(renamed)
            source = renamed
            target = target.with_name(source.name)
            target.hardlink_to(source)
            with self.subTest(suffix=suffix):
                self.validate(readonly_texture_view=view)

    def test_readonly_texture_option_still_rejects_cards_configs_states_and_dumps(self):
        view, source, _ = self.texture_view()
        for relative in ("GC/card.raw", "Config/other.ini", "StateSaves/state.sav",
                         "Dump/Textures/GXXP01/tex1_32x32_0123456789abcdef_14.png"):
            path = self.profile / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.hardlink_to(source)
            with self.subTest(relative=relative), self.assertRaisesRegex(ValueError, "permitted game texture"):
                self.validate(readonly_texture_view=view)
            path.unlink()

    def test_readonly_texture_option_never_allows_external_load_or_write_paths(self):
        view, _, _ = self.texture_view()
        for key, path in (("LoadPath", view), ("MemcardAPath", self.personal / "GC/card.raw")):
            self.config.write_text("[General]\n" + key + " = " + path.as_posix())
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "escapes"):
                self.validate(readonly_texture_view=view)
        self.config.write_text("[General]\nDumpPath = " + (self.profile / "Load").as_posix())
        with self.assertRaisesRegex(ValueError, "overlap readonly"):
            self.validate(readonly_texture_view=view)

    def test_profile_texture_cannot_be_an_unrelated_file_with_the_same_name(self):
        view, source, target = self.texture_view()
        target.unlink()
        unrelated = self.build / "unrelated.png"
        unrelated.write_bytes(source.read_bytes())
        target.hardlink_to(unrelated)
        with self.assertRaisesRegex(ValueError, "exact canonical view"):
            self.validate(readonly_texture_view=view)

    def test_nonflat_or_wrong_game_texture_hardlinks_are_refused(self):
        view, source, target = self.texture_view()
        target.unlink()
        for relative in ("Load/Textures/GC6P01/" + source.name,
                         "Load/Textures/GXXP01/nested/" + source.name):
            wrong = self.profile / relative
            wrong.parent.mkdir(parents=True, exist_ok=True)
            wrong.hardlink_to(source)
            with self.subTest(relative=relative), self.assertRaisesRegex(ValueError, "permitted game texture"):
                self.validate(readonly_texture_view=view)
            wrong.unlink()

    def test_forged_image_or_oversized_input_is_refused_even_when_samefile(self):
        view, source, _ = self.texture_view()
        original = source.read_bytes()
        for payload in (b"card data" * 32, b"\x89PNG\r\n\x1a\n" + b"card data" * 32):
            source.write_bytes(payload)
            with self.subTest(payload=payload[:12]), self.assertRaises(ValueError):
                self.validate(readonly_texture_view=view)
        source.write_bytes(original)
        with source.open("r+b") as stream:
            stream.truncate(64 * 1024**2 + 1)
        with self.assertRaisesRegex(ValueError, "64MB"):
            self.validate(readonly_texture_view=view)

    def test_wrong_pack_receipt_or_noncanonical_view_is_refused(self):
        view, _, _ = self.texture_view()
        marker = view.parent / "complete.json"
        metadata = json.loads(marker.read_text())
        for key, value in (("pack", "untrusted-pack"), ("game_id", "invalid")):
            marker.write_text(json.dumps(dict(metadata, **{key: value})))
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.validate(readonly_texture_view=view)
        marker.write_text(json.dumps(metadata))
        with self.assertRaisesRegex(ValueError, "canonical PackStore"):
            self.validate(readonly_texture_view=self.build)
        with self.assertRaises(ValueError):
            self.validate(readonly_texture_view=self.profile)

    def test_linked_view_ancestor_is_rejected_before_image_access(self):
        view, _, _ = self.texture_view()
        original = Path.is_symlink
        with patch.object(Path, "is_symlink", lambda path: path == view.parent or original(path)):
            with self.assertRaisesRegex(ValueError, "Linked paths"):
                self.validate(readonly_texture_view=view)

    def test_gecko_test_sections_with_bare_codes_do_not_hide_external_paths(self):
        (self.profile / "GameSettings").mkdir()
        (self.profile / "GameSettings/GC6P01.ini").write_text(
            "[Gecko]\n$Test code\n04000000 12345678\n[Core]\nCPUThread = False\n", encoding="utf-8")
        self.validate()

    def test_report_publication_recovers_from_brief_reader_lock(self):
        original_replace = launcher.os.replace
        attempts = []

        def replace(source, target):
            attempts.append(target)
            if len(attempts) <= 2:
                raise PermissionError("Windows reader has no FILE_SHARE_DELETE")
            return original_replace(source, target)

        with patch.object(launcher.os, "replace", side_effect=replace), \
                patch.object(launcher.time, "sleep") as sleep:
            result = self.run_job(code=7)
        self.assertEqual(result["status"], "finished")
        self.assertEqual(result["return_code"], 7)
        self.assertEqual(sleep.call_count, 2)
        self.assertEqual(json.loads(self.report.read_text("utf-8")), result)
        self.assertEqual(list(self.build.glob("run.json.*.tmp")), [])

    def test_persistent_running_report_lock_does_not_abandon_process_or_final_audit(self):
        original_replace = launcher.os.replace
        attempts = []
        card = self.personal / "GC/card.raw"

        def replace(source, target):
            attempts.append(target)
            if len(attempts) <= launcher.REPORT_REPLACE_ATTEMPTS:
                raise PermissionError("reader remains open during running publication")
            return original_replace(source, target)

        with patch.object(launcher.os, "replace", side_effect=replace), \
                patch.object(launcher.time, "sleep"), patch("sys.stderr", new_callable=io.StringIO):
            result = self.run_job(code=9, callback=lambda: card.write_bytes(b"changed during native wait"))
        self.assertEqual(result["status"], "finished")
        self.assertEqual(result["return_code"], 9)
        self.assertEqual(result["personal_profile_changed"], ["GC/card.raw"])
        self.assertIn("while running", result["report_publication_errors"][0])
        self.assertEqual(json.loads(self.report.read_text("utf-8")), result)
        self.assertEqual(list(self.build.glob("run.json.*.tmp")), [])

    def test_report_publication_lock_has_a_bound_and_preserves_previous_json(self):
        self.report.write_text('{"status":"previous"}', encoding="utf-8")
        with patch.object(launcher.os, "replace", side_effect=PermissionError("locked")) as replace, \
                patch.object(launcher.time, "sleep") as sleep, self.assertRaises(PermissionError):
            launcher.publish_report(self.report, {"status": "new"})
        self.assertEqual(replace.call_count, launcher.REPORT_REPLACE_ATTEMPTS)
        self.assertEqual(sleep.call_count, launcher.REPORT_REPLACE_ATTEMPTS - 1)
        self.assertEqual(json.loads(self.report.read_text("utf-8")), {"status": "previous"})
        self.assertEqual(list(self.build.glob("run.json.*.tmp")), [])

    def test_report_publication_does_not_retry_unrelated_io_errors(self):
        with patch.object(launcher.os, "replace", side_effect=OSError("disk error")) as replace, \
                patch.object(launcher.time, "sleep") as sleep, self.assertRaises(OSError):
            launcher.publish_report(self.report, {"status": "new"})
        self.assertEqual(replace.call_count, 1)
        sleep.assert_not_called()
        self.assertEqual(list(self.build.glob("run.json.*.tmp")), [])

    @unittest.skipUnless(os.name == "nt", "Windows reader sharing semantics")
    def test_real_windows_reader_lock_releases_and_publication_finishes(self):
        self.report.write_text('{"status":"previous"}', encoding="utf-8")
        reader = self.report.open("rb")
        timer = threading.Timer(0.12, reader.close)
        timer.start()
        try:
            launcher.publish_report(self.report, {"status": "finished"})
        finally:
            reader.close()
            timer.join()
        self.assertEqual(json.loads(self.report.read_text("utf-8")), {"status": "finished"})
        self.assertEqual(list(self.build.glob("run.json.*.tmp")), [])

    def test_default_personal_profile_uses_absolute_appdata(self):
        roaming = self.root / "roaming"
        with patch.dict(launcher.os.environ, {"APPDATA": str(roaming)}, clear=True):
            self.assertEqual(launcher.default_personal_profile(), roaming / "Dolphin Emulator")

    def test_missing_empty_or_relative_appdata_refuses_before_launch(self):
        argv = ["run_dolphin_validation.py", "--emulator", str(self.emulator), "--iso", str(self.iso),
                "--profile", str(self.profile), "--report", str(self.report)]
        for environment in ({}, {"APPDATA": ""}, {"APPDATA": "   "}, {"APPDATA": "relative"}):
            with self.subTest(environment=environment), patch.dict(launcher.os.environ, environment, clear=True), \
                    patch("sys.argv", argv), patch.object(launcher, "run_validation") as run, \
                    patch("sys.stderr", new_callable=io.StringIO) as stderr:
                self.assertEqual(launcher.main(), 2)
                run.assert_not_called()
                self.assertIn("--personal-profile", stderr.getvalue())

    def test_explicit_personal_profile_does_not_require_appdata(self):
        argv = ["run_dolphin_validation.py", "--emulator", str(self.emulator), "--iso", str(self.iso),
                "--profile", str(self.profile), "--report", str(self.report), "--personal-profile", str(self.personal)]
        with patch.dict(launcher.os.environ, {}, clear=True), patch("sys.argv", argv), \
                patch.object(launcher, "run_validation", return_value={"successful_process_and_preservation": True}) as run, \
                patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(launcher.main(), 0)
        self.assertEqual(run.call_args.args[4], self.personal)


if __name__ == "__main__":
    unittest.main()
