"""Run every test module in a fresh, bounded process.

Qt owns process-wide native state. Isolating modules prevents earlier GUI tests
from retaining wrappers, threads or queued deletes in later modules. The same
runner works in the checkout and in an extracted source release.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from dataclasses import dataclass
import faulthandler
import json
import math
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
# Leave headroom for the complete Qt matrix on slower Windows runners.
# Each module keeps its separate 120-second limit and crash watchdog.
SUITE_TIMEOUT = 15 * 60


def default_jobs() -> int:
    """Keep Qt/image workers modest on small machines and shared CI hosts."""
    jobs = min(2, os.cpu_count() or 1)
    try:
        if sys.platform == "win32":
            import ctypes

            class MemoryStatus(ctypes.Structure):
                _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong),
                            *[(name, ctypes.c_ulonglong) for name in
                              ("total_physical", "available_physical", "total_page",
                               "available_page", "total_virtual", "available_virtual", "extended")]]

            status = MemoryStatus()
            status.length = ctypes.sizeof(status)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return 1
            available = status.available_physical
        else:
            available = os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
        if available < 2 * 1024 ** 3:
            return 1
    except (AttributeError, OSError, ValueError):
        return 1
    return jobs


@dataclass
class RunningModule:
    index: int
    name: str
    process: subprocess.Popen
    report: Path
    log: Path
    stream: object
    started: float
    limit: float
    suite_limited: bool
    progress: str = ""


def show_progress(module: RunningModule, *, force: bool = False) -> None:
    """Expose active test names even if an outer source-audit timeout kills us."""
    with module.log.open("rb") as stream:
        stream.seek(0, os.SEEK_END)
        stream.seek(max(0, stream.tell() - 1024))
        lines = stream.read().decode("utf-8", errors="replace").splitlines()
    if lines and " ... " in lines[-1] and (force or lines[-1] != module.progress):
        module.progress = lines[-1]
        print(f"Running {module.name}: {module.progress[:500]}", file=sys.stderr, flush=True)


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


def run(*, module_timeout: float = MODULE_TIMEOUT, suite_timeout: float = SUITE_TIMEOUT,
        jobs: int | None = None, timings: Path | None = None,
        module_names: list[str] | None = None) -> int:
    modules = sorted(path.name for path in Path("tests").glob("test*.py") if path.is_file())
    available_modules = len(modules)
    if module_names is not None:
        if not module_names:
            raise ValueError("Select at least one test module")
        if any(not isinstance(name, str) or Path(name).name != name or "/" in name or "\\" in name
               or not name.startswith("test") or not name.endswith(".py") for name in module_names):
            raise ValueError("Test modules must be test*.py filenames without a directory")
        if len(set(module_names)) != len(module_names):
            raise ValueError("Duplicate test module selection")
        missing = sorted(set(module_names) - set(modules))
        if missing:
            raise ValueError("Test module not found: " + ", ".join(missing))
        modules = sorted(module_names)
        print(f"Selected {len(modules)}/{available_modules} test modules explicitly.", file=sys.stderr, flush=True)
    if not modules:
        print("No test modules found in the current directory.", file=sys.stderr)
        return 1
    started = time.monotonic()
    jobs = min(len(modules), default_jobs() if jobs is None else jobs)
    if jobs < 1:
        raise ValueError("Test jobs must be positive")
    totals = {"tests": 0, "skipped": 0, "failures": 0, "errors": 0}
    completed = 0
    failures = []
    records = [{"module": name, "status": "not_started", "seconds": 0.0} for name in modules]
    running = []
    next_module = 0
    next_output = 0
    deadline_exhausted = False
    progress_at = started
    print(f"Running {len(modules)} isolated test modules with {jobs} workers.", file=sys.stderr, flush=True)
    with tempfile.TemporaryDirectory(prefix="orre-test-results-") as directory:
        try:
            while running or next_module < len(modules):
                output_written = False
                now = time.monotonic()
                if now - started >= suite_timeout:
                    deadline_exhausted = True
                for module in running[:]:
                    returncode = module.process.poll()
                    timed_out = returncode is None and (deadline_exhausted or now - module.started >= module.limit)
                    if returncode is None and not timed_out:
                        continue
                    if timed_out:
                        module.process.kill()
                        module.process.wait()
                        failures.append(f"{module.name}: timed out after {module.limit:.1f}s")
                    else:
                        completed += 1
                    module.stream.close()
                    running.remove(module)
                    record = records[module.index]
                    record.update(seconds=round(time.monotonic() - module.started, 3),
                                  status="timed_out" if timed_out else "crashed")
                    if not timed_out and module.report.is_file():
                        try:
                            summary = json.loads(module.report.read_text("utf-8"))
                            if (any(type(summary[key]) is not int or summary[key] < 0 for key in totals)
                                    or type(summary["successful"]) is not bool):
                                raise ValueError("invalid result counts")
                        except (OSError, ValueError, KeyError, TypeError) as error:
                            failures.append(f"{module.name}: invalid test result ({error})")
                        else:
                            for key in totals:
                                totals[key] += summary[key]
                            record.update(status="passed" if returncode == 0 and summary["successful"] else "failed",
                                          **{key: summary[key] for key in totals})
                            if record["status"] == "failed":
                                failures.append(f"{module.name}: test failures (exit {returncode})")
                    elif not timed_out:
                        failures.append(f"{module.name}: exited {returncode} without a test result (crash or timeout)")
                    # Watchdogs may exit a little before a suite-limited wait.
                    # Do not launch more tests into that expired budget.
                    if module.suite_limited and record["status"] in {"timed_out", "crashed"}:
                        deadline_exhausted = True
                # Logs are printed in discovery order, never interleaved by Qt
                # workers. Live progress above/below still identifies a hang.
                while next_output < next_module and records[next_output]["status"] != "running":
                    name = modules[next_output]
                    print(f"\n[{next_output + 1}/{len(modules)}] {name} (isolated process)",
                          file=sys.stderr, flush=True)
                    print((Path(directory) / f"{next_output}.log").read_text("utf-8", errors="replace"),
                          end="", file=sys.stderr, flush=True)
                    output_written = True
                    next_output += 1
                while not deadline_exhausted and len(running) < jobs and next_module < len(modules):
                    launched = time.monotonic()
                    remaining = suite_timeout - (launched - started)
                    if remaining <= 0:
                        deadline_exhausted = True
                        break
                    index = next_module
                    name = modules[index]
                    limit = min(module_timeout, remaining)
                    report = Path(directory) / f"{index}.json"
                    log = Path(directory) / f"{index}.log"
                    command = [sys.executable, "-X", "utf8", str(Path(__file__).resolve()),
                               "--worker", name, "--report", str(report), "--module-timeout", str(limit)]
                    stream = log.open("wb")
                    try:
                        process = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT)
                    except BaseException:
                        stream.close()
                        raise
                    running.append(RunningModule(index, name, process, report, log, stream,
                                                 launched, limit, remaining <= module_timeout))
                    records[index]["status"] = "running"
                    next_module += 1
                    print(f"Starting [{index + 1}/{len(modules)}] {name}", file=sys.stderr, flush=True)
                if deadline_exhausted and not running:
                    break
                if output_written or time.monotonic() >= progress_at:
                    for module in running:
                        show_progress(module, force=output_written)
                    progress_at = time.monotonic() + .5
                if running:
                    time.sleep(.02)
        finally:
            # Also join every worker on Ctrl-C, logging errors or launch errors;
            # closing a Windows job on normal return must not orphan children.
            for module in running:
                if module.process.poll() is None:
                    module.process.kill()
                module.process.wait()
                module.stream.close()
    if deadline_exhausted:
        failures.append("Whole-suite deadline exceeded; modules remain untested")
    if not totals["tests"]:
        failures.append("No tests completed with a valid result")
    failures.sort()
    duration = time.monotonic() - started
    if timings is not None:
        timings.parent.mkdir(parents=True, exist_ok=True)
        timings.write_text(json.dumps({"jobs": jobs, "seconds": round(duration, 3), "totals": totals,
            "selection": "explicit" if module_names is not None else "all", "available_modules": available_modules,
            "completed": completed, "modules": records, "failures": failures}, indent=2) + "\n", encoding="utf-8")
    print("\n" + "-" * 70, file=sys.stderr)
    print(f"Ran {totals['tests']} tests across {completed}/{len(modules)} isolated modules "
          f"in {duration:.3f}s ({jobs} workers)", file=sys.stderr)
    print("Slowest modules:", file=sys.stderr)
    for record in sorted(records, key=lambda item: (-item["seconds"], item["module"]))[:10]:
        print(f"- {record['module']}: {record['seconds']:.3f}s ({record['status']})", file=sys.stderr)
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
    parser.add_argument("--jobs", type=int, default=None,
                        help="Concurrent isolated modules (default: at most 2, limited by CPU and memory)")
    parser.add_argument("--timings", type=Path, help="Write module timings and completeness as JSON")
    parser.add_argument("--module", dest="module_names", action="append", metavar="TEST_MODULE",
                        help="Run only this test*.py module; repeat for multiple modules (default: every module)")
    args = parser.parse_args(argv)
    if not all(math.isfinite(value) and value > 0 for value in (args.module_timeout, args.suite_timeout)):
        parser.error("Test timeouts must be positive")
    if args.jobs is not None and args.jobs <= 0:
        parser.error("Test jobs must be positive")
    if args.worker:
        if args.report is None:
            parser.error("Worker result path is required")
        return worker(args.worker, args.report, args.module_timeout)
    try:
        return run(module_timeout=args.module_timeout, suite_timeout=args.suite_timeout,
                   jobs=args.jobs, timings=args.timings, module_names=args.module_names)
    except ValueError as error:
        parser.error(str(error))


if __name__ == "__main__":
    with windows_test_job():
        raise SystemExit(main())
