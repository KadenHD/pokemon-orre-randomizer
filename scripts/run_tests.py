"""Run every test module in a fresh, bounded process.

Qt owns process-wide native state. Isolating modules prevents earlier GUI tests
from retaining wrappers, threads or queued deletes in later modules. The same
runner works in the checkout and in an extracted source release.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import faulthandler
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

if __package__:
    from .test_processes import windows_test_job
else:
    from test_processes import windows_test_job

MODULE_TIMEOUT = 120
SUITE_TIMEOUT = 12 * 60


def worker(pattern: str, report: Path, timeout: float) -> int:
    """Discover one module through unittest so local fixture imports still work."""
    if Path(pattern).name != pattern or not pattern.startswith("test") or not pattern.endswith(".py"):
        raise ValueError("Invalid test module pattern")
    sys.path.insert(0, str(Path.cwd()))
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    faulthandler.enable()
    faulthandler.dump_traceback_later(max(.05, timeout * .85), exit=True)
    with ExitStack() as silent:
        if sys.platform == "win32":
            silent.enter_context(patch("winsound.PlaySound", return_value=None))
            # Music's own unit tests supply an explicit fake backend; do not
            # replace the method under test in that module.
            if pattern != "test_ui_music.py":
                try:
                    from orre_randomizer.ui_music import NativeMusic
                except ImportError:
                    pass
                else:
                    silent.enter_context(patch.object(NativeMusic, "play", return_value=None))
        suite = unittest.defaultTestLoader.discover("tests", pattern=pattern)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        report.write_text(json.dumps({"tests": result.testsRun, "skipped": len(result.skipped),
            "failures": len(result.failures), "errors": len(result.errors),
            "successful": result.wasSuccessful()}), encoding="utf-8")
    faulthandler.cancel_dump_traceback_later()
    return 0 if result.wasSuccessful() else 1


def run(*, module_timeout: float = MODULE_TIMEOUT, suite_timeout: float = SUITE_TIMEOUT) -> int:
    modules = sorted(path.name for path in Path("tests").glob("test*.py") if path.is_file())
    if not modules:
        print("No test modules found in the current directory.", file=sys.stderr)
        return 1
    started = time.monotonic()
    totals = {"tests": 0, "skipped": 0, "failures": 0, "errors": 0}
    completed = 0
    failures = []
    with tempfile.TemporaryDirectory(prefix="orre-test-results-") as directory:
        for index, module in enumerate(modules, 1):
            remaining = suite_timeout - (time.monotonic() - started)
            if remaining <= 0:
                failures.append("Whole-suite deadline exceeded; modules remain untested")
                break
            limit = min(module_timeout, remaining)
            print(f"\n[{index}/{len(modules)}] {module} (isolated process)", file=sys.stderr, flush=True)
            report = Path(directory) / f"{index}.json"
            command = [sys.executable, "-X", "utf8", str(Path(__file__).resolve()),
                       "--worker", module, "--report", str(report), "--module-timeout", str(limit)]
            try:
                result = subprocess.run(command, timeout=limit)
            except subprocess.TimeoutExpired:
                failures.append(f"{module}: timed out after {limit:.1f}s")
                print(failures[-1], file=sys.stderr, flush=True)
                # A suite-limited wait consumes the remaining budget even if
                # Windows reports its timeout a few milliseconds early. Do not
                # start another worker with that unusable fragment of time.
                if remaining <= module_timeout:
                    failures.append("Whole-suite deadline exceeded; modules remain untested")
                    break
                continue
            completed += 1
            if not report.is_file():
                failures.append(f"{module}: exited {result.returncode} without a test result (crash or timeout)")
                continue
            summary = json.loads(report.read_text("utf-8"))
            for key in totals:
                totals[key] += summary[key]
            if result.returncode or not summary["successful"]:
                failures.append(f"{module}: test failures (exit {result.returncode})")
    print("\n" + "-" * 70, file=sys.stderr)
    print(f"Ran {totals['tests']} tests across {completed}/{len(modules)} isolated modules "
          f"in {time.monotonic()-started:.3f}s", file=sys.stderr)
    if failures or not totals["tests"] or completed != len(modules):
        print("FAILED", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print(f"OK (skipped={totals['skipped']})" if totals["skipped"] else "OK", file=sys.stderr)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", help=argparse.SUPPRESS)
    parser.add_argument("--report", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--module-timeout", type=float, default=MODULE_TIMEOUT)
    parser.add_argument("--suite-timeout", type=float, default=SUITE_TIMEOUT)
    args = parser.parse_args(argv)
    if args.module_timeout <= 0 or args.suite_timeout <= 0:
        parser.error("Test timeouts must be positive")
    if args.worker:
        if args.report is None:
            parser.error("Worker result path is required")
        return worker(args.worker, args.report, args.module_timeout)
    return run(module_timeout=args.module_timeout, suite_timeout=args.suite_timeout)


if __name__ == "__main__":
    with windows_test_job():
        raise SystemExit(main())
