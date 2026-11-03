"""Owned converter profile settings; no ROM or Dolphin process is required."""

import configparser
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from colosseum_randomizer import service


class ConverterProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.work = self.root / ".colosseum-owned-job"
        self.work.mkdir()
        self.source = self.root / "source.rvz"
        self.source.write_bytes(b"unchanged source image")
        self.output = self.work / "source.iso"
        self.tool = self.root / "DolphinTool.exe"
        self.tool.touch()
        self.cancel = threading.Event()
        self.config_path = self.work / "dolphin-user/Config/Dolphin.ini"
        self.personal_config = self.root / "personal-dolphin/Config/Dolphin.ini"
        self.personal_config.parent.mkdir(parents=True)
        self.personal_settings = b"[Interface]\nUsePanicHandlers = True\nLanguageCode = fr\n"
        self.personal_config.write_bytes(self.personal_settings)

    def read_config(self):
        result = configparser.ConfigParser(interpolation=None)
        result.optionxform = str
        result.read(self.config_path, encoding="utf-8-sig")
        return result

    def fake_process(self, returncode=0, create_output=True, inspect=None):
        def launch(args, **kwargs):
            self.assertEqual(Path(args[args.index("-u") + 1]), self.work / "dolphin-user")
            self.assertFalse(self.read_config().getboolean("Interface", "UsePanicHandlers"))
            if inspect is not None:
                inspect(args, kwargs)
            if create_output:
                Path(args[args.index("-o") + 1]).write_bytes(b"converted image fixture")
            return Mock(returncode=returncode, poll=Mock(return_value=returncode))
        return launch

    def assert_originals_unchanged(self):
        self.assertEqual(self.source.read_bytes(), b"unchanged source image")
        self.assertEqual(self.personal_config.read_bytes(), self.personal_settings)

    def test_creates_headless_settings_in_owned_job_profile_before_launch(self):
        def inspect(args, kwargs):
            self.assertEqual(self.read_config().sections(), ["Interface"])
            self.assertEqual(self.read_config()["Interface"]["UsePanicHandlers"], "False")
            self.assertEqual(args[args.index("-f") + 1], "iso")
            self.assertEqual(Path(kwargs["stdout"].name), self.work / "conversion.log")

        with patch.object(service.subprocess, "Popen", side_effect=self.fake_process(inspect=inspect)) as launch:
            service.convert(self.tool, self.source, self.output, self.work, self.cancel)
        launch.assert_called_once()
        self.assertTrue(self.output.is_file())
        self.assert_originals_unchanged()

    def test_existing_utf8_bom_settings_preserve_case_values_and_other_files(self):
        self.config_path.parent.mkdir(parents=True)
        self.config_path.write_text(
            "[Interface]\nUsePanicHandlers = True\nThemeName = Été\nMixedCaseKey = KeepCase\n"
            "[Core]\nCPUThread = True\n[General]\nISOPath0 = C:/100% exact/game.iso\n",
            encoding="utf-8-sig")
        expected = {section: dict(self.read_config()[section]) for section in self.read_config().sections()}
        expected["Interface"]["UsePanicHandlers"] = "False"
        other_config = self.config_path.with_name("GFX.ini")
        other_config.write_bytes(b"[Settings]\nBackend = Vulkan\n")
        self.output = self.work / "output.rvz"

        def inspect(args, _kwargs):
            settings = self.read_config()
            self.assertEqual({section: dict(settings[section]) for section in settings.sections()}, expected)
            self.assertEqual(args[-6:], ["-b", "131072", "-c", "zstd", "-l", "5"])

        with patch.object(service.subprocess, "Popen", side_effect=self.fake_process(inspect=inspect)):
            service.convert(self.tool, self.source, self.output, self.work, self.cancel)
        self.assertEqual(other_config.read_bytes(), b"[Settings]\nBackend = Vulkan\n")
        self.assert_originals_unchanged()

    def test_nonzero_exit_still_fails_even_when_output_exists(self):
        with patch.object(service.subprocess, "Popen", side_effect=self.fake_process(returncode=7)):
            with self.assertRaises(service.UserError):
                service.convert(self.tool, self.source, self.output, self.work, self.cancel)
        self.assertTrue(self.output.exists())
        self.assert_originals_unchanged()

    def test_zero_exit_without_output_still_fails(self):
        with patch.object(service.subprocess, "Popen", side_effect=self.fake_process(create_output=False)):
            with self.assertRaises(service.UserError):
                service.convert(self.tool, self.source, self.output, self.work, self.cancel)
        self.assertFalse(self.output.exists())
        self.assert_originals_unchanged()

    def test_precancelled_conversion_never_creates_profile_or_launches_process(self):
        self.cancel.set()
        with patch.object(service.subprocess, "Popen") as launch:
            with self.assertRaises(service.Cancelled):
                service.convert(self.tool, self.source, self.output, self.work, self.cancel)
        launch.assert_not_called()
        self.assertFalse(self.config_path.exists())
        self.assert_originals_unchanged()


if __name__ == "__main__":
    unittest.main()
