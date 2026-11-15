"""Process isolation must not hide failures, crashes, hangs or untested modules."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


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
                                  "--module-timeout", "2", "--suite-timeout", ".4")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Whole-suite deadline exceeded; modules remain untested", result.stderr)
        self.assertNotIn("test_later (", result.stderr)
