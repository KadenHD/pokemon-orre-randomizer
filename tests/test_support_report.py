"""Support reports preserve reproduction inputs without copying private data."""
from dataclasses import asdict
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from orre_randomizer import __version__
from orre_randomizer.engine.analyze_game import FormatError
from orre_randomizer.options import Options
from orre_randomizer.service import Cancelled, ENGINE_VERSION, UserError
from orre_randomizer.support_report import (normalized_error, operation_snapshot, remember_failure,
    remember_verified_disc, report_text, request_key, sanitize_report, save_report, settings_snapshot)
from orre_randomizer.xd import XDOptions, VERSION as XD_VERSION


def owner(options=None, seed="étoile 日本語"):
    return SimpleNamespace(current_options=lambda: options or Options(),
        source=SimpleNamespace(text=lambda: "C:/Users/private-player/game.iso"),
        seed=SimpleNamespace(text=lambda: seed))


class SupportReports(unittest.TestCase):
    def test_each_game_keeps_exact_safe_seed_typed_options_and_engine(self):
        for options, engine in ((Options(), ENGINE_VERSION), (XDOptions(), XD_VERSION)):
            result = settings_snapshot(owner(options))
            self.assertEqual(result["seed"], "étoile 日本語")
            self.assertEqual(result["engine_version"], engine)
            self.assertEqual(result["app"]["version"], __version__)
            expected = json.loads(json.dumps(asdict(options)))
            self.assertEqual(result["options"], expected)
            self.assertEqual(result["omitted_option_fields"], [])
            self.assertEqual(result["disc"], {"identity":"unavailable"})
            self.assertNotIn("private-player", report_text(result))

    def test_region_only_comes_from_an_engine_success_for_same_selected_source(self):
        instance = owner(XDOptions())
        remember_verified_disc(instance,{"game_id":"GXXJ01","revision":0,
            "source":"C:/Users/private-player/game.iso", "hidden":"secret"})
        self.assertEqual(settings_snapshot(instance)["disc"],
                         {"identity":"verified","game_id":"GXXJ01","revision":0,"region":"Japan"})
        instance.source.text = lambda: "another.rvz"
        self.assertEqual(settings_snapshot(instance)["disc"], {"identity":"unavailable"})

    def test_extra_keys_raw_errors_paths_and_invalid_option_strings_never_escape(self):
        secret = "C:/Users/private-player/private-file.iso"
        document = {"game":"xd","seed":"safe-seed","options":asdict(XDOptions()),
            "source":secret,"log":secret,"app":{"version":secret,"username":secret},
            "engine_version":secret,"disc":{"identity":"verified","game_id":"GXXP01","revision":0,"path":secret},
            "operation":{"stage":"creation","error":{"kind":"format","code":"data_format_failed","message":secret}}}
        document["options"].update(starter_stage=secret, randomize_starter=secret, extra=secret)
        document["operation"]["traceback"] = secret
        result = json.loads(report_text(document))
        self.assertNotIn(secret, json.dumps(result))
        self.assertNotIn("extra", result["options"])
        self.assertEqual(set(result["omitted_option_fields"]), {"starter_stage","randomize_starter"})
        self.assertEqual(result["operation"]["error"], {"kind":"format","code":"data_format_failed"})

    def test_sensitive_or_invalid_seeds_are_omitted_and_safe_seed_can_be_removed(self):
        for seed in ("C:/Users/private-player/a.iso", r"\\server\share\folder", "/home/player/game.iso",
                     "name@example.com", "token=private-value", "github_pat_1234567890", "", "x"*129,
                     "line\nbreak"):
            with self.subTest(seed=seed):
                data = settings_snapshot(owner(seed=seed))
                self.assertIsNone(data["seed"])
                self.assertEqual(data["seed_status"], "omitted_sensitive_or_invalid")
                self.assertIsNone(json.loads(report_text(data))["seed"])
        safe = json.loads(report_text(settings_snapshot(owner(seed="ordinary-seed")), include_seed=False))
        self.assertIsNone(safe["seed"])
        self.assertEqual(safe["seed_status"], "omitted_by_user")

    def test_last_failure_keeps_its_original_options_without_error_text(self):
        instance = owner(XDOptions.species_only(), "first-seed")
        snapshot = operation_snapshot(instance,"creation")
        remember_failure(instance, OSError("C:/Users/private-player/failure"),False,snapshot=snapshot)
        instance.seed.text = lambda:"changed-seed"
        self.assertEqual(instance._support_last_failure["seed"], "first-seed")
        self.assertEqual(settings_snapshot(instance)["seed"], "changed-seed")
        self.assertNotIn("private-player", report_text(instance._support_last_failure))
        self.assertEqual(instance._support_last_failure["operation"]["error"],
                         {"kind":"io","code":"file_access_failed"})

    def test_cancelled_and_stale_workers_do_not_replace_the_last_failure(self):
        instance = owner()
        snapshot, key = operation_snapshot(instance,"preview"), request_key(instance)
        remember_failure(instance, RuntimeError("secret"),True,snapshot=snapshot)
        self.assertFalse(hasattr(instance,"_support_last_failure"))
        instance.seed.text = lambda:"new-seed"
        remember_failure(instance, RuntimeError("secret"),False,snapshot=snapshot,expected_key=key)
        self.assertFalse(hasattr(instance,"_support_last_failure"))

    def test_normalized_errors_only_contain_fixed_classes_and_codes(self):
        for error in (UserError("personal"), FormatError("private"), OSError("secret"), RuntimeError("token"), "arbitrary"):
            self.assertEqual(set(normalized_error(error)), {"kind","code"})
        self.assertEqual(normalized_error(FormatError(
            "Aucun Pokémon adapté au tutoriel. Élargissez les filtres de Pokémon."))["code"], "xd_tutorial_target_filter")

    def test_malformed_generic_values_cannot_add_strings_or_raise_serialization_errors(self):
        for operation in ([], {"stage":[]}, {"stage":{},"error":{"kind":[],"code":{}}}):
            data = {"seed":"safe","options":{"trainer_level_multiplier":10**1000},
                    "operation":operation,"disc":{"identity":"verified","game_id":[],"revision":0}}
            self.assertEqual(json.loads(report_text(data))["operation"], {"stage":"settings"})

    def test_export_is_exclusive_and_cancellation_or_failure_leaves_no_partial_files(self):
        data = settings_snapshot(owner())
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); destination = root/"diagnostic-é.json"
            save_report(destination,data)
            original = destination.read_bytes()
            self.assertEqual(json.loads(original)["seed"], "étoile 日本語")
            with self.assertRaises(UserError):
                save_report(destination,data)
            self.assertEqual(destination.read_bytes(), original)
            cancel = threading.Event(); cancel.set()
            with self.assertRaises(Cancelled):
                save_report(root/"cancelled.json",data,cancel=cancel)
            with patch("orre_randomizer.support_report.publish_new",side_effect=OSError("synthetic disk failure")):
                with self.assertRaises(OSError):
                    save_report(root/"failed.json",data)
            self.assertEqual(list(root.iterdir()), [destination])
            with self.assertRaises(UserError):
                save_report(root/"diagnostic.iso",data)


if __name__ == "__main__":
    unittest.main()
