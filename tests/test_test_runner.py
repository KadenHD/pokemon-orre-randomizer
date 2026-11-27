"""Process isolation must not hide failures, crashes, hangs or untested modules."""
from pathlib import Path
from contextlib import redirect_stderr
import io
import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch


RUNNER = Path(__file__).resolve().parents[1] / "scripts/run_tests.py"


class TestRunnerTests(unittest.TestCase):
    def run_fixture(self, files, *arguments):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tests").mkdir()
            for name, body in files.items():
                (root / "tests" / name).write_text(body, encoding="utf-8")
            return subprocess.run([sys.executable, str(RUNNER), *arguments], cwd=root,
                                  capture_output=True, text=True, timeout=20)

    def test_modules_are_isolated_and_all_tests_and_skips_are_counted(self):
        files = {
            "test_a.py": "import builtins,unittest\nbuiltins._runner_fixture=True\nclass T(unittest.TestCase):\n def test_a(self): self.assertTrue(True)\n",
            "test_b.py": "import builtins,unittest\nclass T(unittest.TestCase):\n def test_b(self): self.assertFalse(hasattr(builtins,'_runner_fixture'))\n @unittest.skip('fixture')\n def test_skip(self): pass\n",
        }
        result = self.run_fixture(files)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Ran 3 tests across 2/2 isolated modules", result.stderr)
        self.assertIn("OK (skipped=1)", result.stderr)

    def test_failed_module_remains_a_failure_and_later_modules_run(self):
        files = {
            "test_a.py": "import unittest\nclass T(unittest.TestCase):\n def test_fails(self): self.fail('deliberate fixture failure')\n",
            "test_b.py": "import unittest\nclass T(unittest.TestCase):\n def test_later(self): pass\n",
        }
        result = self.run_fixture(files)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("deliberate fixture failure", result.stderr)
        self.assertIn("test_later", result.stderr)
        self.assertIn("Ran 2 tests across 2/2 isolated modules", result.stderr)

    def test_crash_and_hang_are_bounded_failures(self):
        crash = self.run_fixture({"test_crash.py": "import os\nos._exit(7)\n"})
        self.assertNotEqual(crash.returncode, 0)
        self.assertIn("without a test result", crash.stderr)
        hang = self.run_fixture({"test_hang.py": "import time\ntime.sleep(20)\n"}, "--module-timeout", ".4")
        self.assertNotEqual(hang.returncode, 0)
        self.assertTrue("timed out" in hang.stderr or "without a test result" in hang.stderr, hang.stderr)

    def test_empty_test_directory_is_not_a_success(self):
        result = self.run_fixture({})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No test modules", result.stderr)

    def test_global_deadline_does_not_report_unexecuted_modules_as_passed(self):
        result = self.run_fixture({"test_a.py": "import time\ntime.sleep(20)\n",
                                   "test_b.py": "import unittest\nclass T(unittest.TestCase):\n def test_later(self): pass\n"},
                                  "--jobs", "1", "--module-timeout", "2", "--suite-timeout", ".4")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Whole-suite deadline exceeded; modules remain untested", result.stderr)
        self.assertNotIn("test_later (", result.stderr)

    def test_early_suite_timeout_does_not_launch_another_worker(self):
        from scripts import run_tests

        with tempfile.TemporaryDirectory() as directory:
            modules = [Path(directory) / name for name in ("test_a.py", "test_b.py")]
            for module in modules:
                module.touch()
            clock = iter((100.0, 100.0, 100.01))
            output = io.StringIO()
            process = Mock()
            process.poll.return_value = 7
            with patch.object(Path, "glob", return_value=modules), \
                    patch.object(run_tests.time, "monotonic", side_effect=lambda: next(clock, 100.399)), \
                    patch.object(run_tests.subprocess, "Popen", return_value=process) as worker, \
                    redirect_stderr(output):
                result = run_tests.run(module_timeout=2, suite_timeout=.4, jobs=1)

        self.assertEqual(result, 1)
        self.assertEqual(worker.call_count, 1)
        self.assertIn("Whole-suite deadline exceeded; modules remain untested", output.getvalue())
        self.assertIn("1/2 isolated modules", output.getvalue())
        self.assertNotIn("[2/2]", output.getvalue())

    def test_two_workers_overlap_without_exceeding_the_limit_and_logs_remain_grouped(self):
        body = (
            "from pathlib import Path\nimport time, unittest\n"
            "class T(unittest.TestCase):\n"
            " def test_parallel(self):\n"
            "  active=Path(__name__+'.active'); active.touch()\n"
            "  try:\n"
            "   self.assertLessEqual(len(list(Path('.').glob('*.active'))),2)\n"
            "   Path(__name__+'.started').touch()\n"
            "   deadline=time.monotonic()+4\n"
            "   while len(list(Path('.').glob('*.started')))<2:\n"
            "    self.assertLess(time.monotonic(),deadline,'workers did not overlap')\n"
            "    time.sleep(.01)\n"
            "   time.sleep(.15)\n"
            "  finally: active.unlink()\n"
        )
        result = self.run_fixture({f"test_{name}.py": body for name in "abcd"}, "--jobs", "2")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Ran 4 tests across 4/4 isolated modules", result.stderr)
        positions = [result.stderr.index(f"[{index}/4] test_{name}.py (isolated process)")
                     for index, name in enumerate("abcd", 1)]
        self.assertEqual(positions, sorted(positions))

    def test_parallel_timeout_does_not_prevent_other_modules_from_running(self):
        result = self.run_fixture({"test_a.py": "import time\ntime.sleep(20)\n",
                                   "test_b.py": "import unittest\nclass T(unittest.TestCase):\n def test_later(self): pass\n"},
                                  "--jobs", "2", "--module-timeout", "1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("test_later", result.stderr)
        self.assertTrue("timed out" in result.stderr or "without a test result" in result.stderr, result.stderr)
        self.assertNotIn("Whole-suite deadline exceeded", result.stderr)

    def test_parallel_suite_deadline_joins_workers_and_records_unstarted_modules(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "timings.json"
            result = self.run_fixture({f"test_{name}.py": "import time\ntime.sleep(20)\n" for name in "abc"},
                                      "--jobs", "2", "--module-timeout", "5", "--suite-timeout", ".6",
                                      "--timings", str(report))
            summary = json.loads(report.read_text("utf-8"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Whole-suite deadline exceeded", result.stderr)
        self.assertNotIn("Starting [3/3]", result.stderr)
        self.assertEqual(summary["jobs"], 2)
        self.assertEqual(summary["totals"]["tests"], 0)
        self.assertEqual(summary["modules"][2]["status"], "not_started")
        self.assertTrue(all(module["status"] in {"crashed", "timed_out"} for module in summary["modules"][:2]))

    def test_timings_report_covers_every_module_and_result(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "reports" / "timings.json"
            result = self.run_fixture({"test_pass.py": "import unittest\nclass T(unittest.TestCase):\n def test_pass(self): pass\n",
                                       "test_fail.py": "import unittest\nclass T(unittest.TestCase):\n def test_fail(self): self.fail('fixture')\n"},
                                      "--jobs", "2", "--timings", str(report))
            summary = json.loads(report.read_text("utf-8"))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(summary["completed"], 2)
        self.assertEqual(summary["totals"]["tests"], 2)
        self.assertEqual([module["status"] for module in summary["modules"]], ["failed", "passed"])
        self.assertTrue(all(module["seconds"] > 0 for module in summary["modules"]))
        self.assertIn("Slowest modules:", result.stderr)

    def test_invalid_concurrency_and_nonfinite_deadlines_are_rejected(self):
        for arguments in (("--jobs", "0"), ("--jobs", "-1"), ("--module-timeout", "nan"),
                          ("--suite-timeout", "inf")):
            with self.subTest(arguments=arguments):
                result = self.run_fixture({"test_a.py": ""}, *arguments)
                self.assertEqual(result.returncode, 2)

    def test_automatic_concurrency_respects_cpu_and_available_memory(self):
        from scripts import run_tests

        with patch.object(run_tests.sys, "platform", "linux"), \
                patch.object(run_tests.os, "cpu_count", return_value=64) as cpu, \
                patch.object(run_tests.os, "sysconf", create=True,
                             side_effect=lambda name: {"SC_AVPHYS_PAGES": 1024 ** 2, "SC_PAGE_SIZE": 4096}[name]) as memory:
            self.assertEqual(run_tests.default_jobs(), 2)
            cpu.return_value = 1
            self.assertEqual(run_tests.default_jobs(), 1)
            cpu.return_value = 64
            memory.side_effect = lambda name: 1024
            self.assertEqual(run_tests.default_jobs(), 1)
            memory.side_effect = OSError("unavailable")
            self.assertEqual(run_tests.default_jobs(), 1)

    def test_invalid_worker_report_is_a_failure_and_other_modules_still_run(self):
        result = self.run_fixture({
            "test_bad.py": "from pathlib import Path\nimport os,sys\nPath(sys.argv[sys.argv.index('--report')+1]).write_text('{\"tests\":\"invalid\"}')\nos._exit(0)\n",
            "test_good.py": "import unittest\nclass T(unittest.TestCase):\n def test_later(self): pass\n",
        }, "--jobs", "2")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid test result", result.stderr)
        self.assertIn("test_later", result.stderr)

    def test_launch_failure_joins_already_running_workers(self):
        from scripts import run_tests

        with tempfile.TemporaryDirectory() as directory:
            modules = [Path(directory) / name for name in ("test_a.py", "test_b.py")]
            for module in modules:
                module.touch()
            process = Mock()
            process.poll.return_value = None
            with patch.object(Path, "glob", return_value=modules), \
                    patch.object(run_tests.subprocess, "Popen", side_effect=[process, OSError("fixture")]), \
                    redirect_stderr(io.StringIO()):
                with self.assertRaisesRegex(OSError, "fixture"):
                    run_tests.run(jobs=2)
            process.kill.assert_called_once()
            process.wait.assert_called_once()

    def test_explicit_module_selection_excludes_other_modules_and_reports_its_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            timings = Path(directory) / "selected.json"
            result = self.run_fixture({
                "test_chosen.py": "import unittest\nclass T(unittest.TestCase):\n def test_chosen(self): pass\n",
                "test_other.py": "raise AssertionError('unselected module was imported')\n",
            }, "--module", "test_chosen.py", "--jobs", "1", "--timings", str(timings))
            report = json.loads(timings.read_text("utf-8"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Selected 1/2 test modules explicitly", result.stderr)
        self.assertNotIn("unselected module was imported", result.stderr)
        self.assertEqual(report["selection"], "explicit")
        self.assertEqual(report["available_modules"], 2)
        self.assertEqual([row["module"] for row in report["modules"]], ["test_chosen.py"])

    def test_module_option_can_be_repeated_and_keeps_discovery_order(self):
        body = "import unittest\nclass T(unittest.TestCase):\n def test_runs(self): pass\n"
        result = self.run_fixture({"test_a.py": body, "test_b.py": body,
                                   "test_unselected.py": "raise AssertionError('unselected')\n"},
                                  "--module", "test_b.py", "--module", "test_a.py", "--jobs", "2")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Ran 2 tests across 2/2 isolated modules", result.stderr)
        self.assertLess(result.stderr.index("[1/2] test_a.py (isolated process)"),
                        result.stderr.index("[2/2] test_b.py (isolated process)"))

    def test_invalid_duplicate_and_missing_module_selections_are_rejected(self):
        for modules in (("../test_a.py",), ("tests/test_a.py",), ("tests\\test_a.py",),
                        ("helper.py",), ("test_a.py", "test_a.py"), ("test_missing.py",)):
            arguments = [argument for name in modules for argument in ("--module", name)]
            with self.subTest(modules=modules):
                result = self.run_fixture({"test_a.py": "raise AssertionError('worker must not start')\n"},
                                          *arguments)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertNotIn("Starting [", result.stderr)
                self.assertNotIn("worker must not start", result.stderr)
