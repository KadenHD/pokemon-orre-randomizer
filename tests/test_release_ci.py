"""Publication must follow the independent main run, not merely tag tests."""
from contextlib import redirect_stderr
import io
import json
import os
from pathlib import Path
import re
import threading
import time
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from scripts import check_release_ci as gate


REPOSITORY = "KadenHD/pokemon-orre-randomizer"
SHA = "0123456789abcdef0123456789abcdef01234567"


def run(**changes):
    # The fields used here are the actual Actions workflow-run response shape.
    result = {"id": 44605914167, "event": "push", "head_branch": "main",
        "head_sha": SHA, "path": ".github/workflows/tests.yml", "run_attempt": 1,
        "status": "completed", "conclusion": "success",
        "repository": {"full_name": REPOSITORY}}
    result.update(changes)
    return result


def listing(*runs):
    return {"total_count": len(runs), "workflow_runs": list(runs)}


class Clock:
    def __init__(self):
        self.now = 0
        self.sleeps = []

    def read(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class ReleaseGateTests(unittest.TestCase):
    def check(self, payload):
        return gate.require_main_success(REPOSITORY, SHA, "fixture-token",
                                         fetch=Mock(return_value=payload))

    def test_latest_matching_main_run_and_latest_attempt_are_required(self):
        payload = listing(run(id=100, run_attempt=9),
            run(id=101, run_attempt=1, conclusion="failure"),
            run(id=101, run_attempt=2, path=".github/workflows/tests.yml@main"),
            run(id=102, head_branch="development", conclusion="failure"),
            run(id=103, head_sha="f" * 40, conclusion="failure"))
        self.assertEqual(self.check(payload), {"sha": SHA, "run_id": 101, "run_attempt": 2})

    def test_newer_main_failure_blocks_an_older_success(self):
        with self.assertRaisesRegex(gate.GateError, "did not succeed"):
            self.check(listing(run(id=100), run(id=101, conclusion="failure")))

    def test_tag_reusable_pull_request_and_other_commit_runs_cannot_authorize_release(self):
        irrelevant = [run(head_branch="v2.0.4"), run(event="workflow_call"),
            run(event="pull_request"), run(path=".github/workflows/package.yml"),
            run(head_sha="f" * 40), run(head_branch="feature")]
        with self.assertRaisesRegex(gate.GateError, "No independent"):
            self.check(listing(*irrelevant))
        with self.assertRaisesRegex(gate.GateError, "No independent"):
            self.check(listing())

    def test_pending_main_can_complete_within_the_bounded_wait(self):
        clock = Clock()
        replies = iter((listing(run(status="queued", conclusion=None)),
                        listing(run(status="in_progress", conclusion=None)), listing(run())))
        timeouts = []

        def fetch(*args, timeout):
            timeouts.append(timeout)
            clock.now += 1
            return next(replies)

        result = gate.require_main_success(REPOSITORY, SHA, "fixture-token", fetch=fetch,
                                           clock=clock.read, sleep=clock.sleep)
        self.assertEqual(result["run_id"], 44605914167)
        self.assertEqual(clock.sleeps, [10, 10])
        self.assertTrue(all(0 < value <= 10 for value in timeouts))
        self.assertLess(clock.now, 120)

    def test_pending_main_never_waits_beyond_120_seconds(self):
        clock = Clock()
        fetch = Mock(return_value=listing(run(status="in_progress", conclusion=None)))
        with self.assertRaisesRegex(gate.GateError, "within 120"):
            gate.require_main_success(REPOSITORY, SHA, "fixture-token", fetch=fetch,
                                      clock=clock.read, sleep=clock.sleep)
        self.assertEqual(clock.now, 120)
        self.assertLessEqual(fetch.call_count, 12)

    def test_parallel_release_gate_can_wait_for_slow_main_without_extending_requests(self):
        clock = Clock()
        calls = []

        def fetch(*args, timeout):
            calls.append(timeout)
            return listing(run(status="in_progress", conclusion=None)) if clock.now < 170 else listing(run())

        result = gate.require_main_success(REPOSITORY, SHA, "fixture-token", fetch=fetch,
            clock=clock.read, sleep=clock.sleep, wait_seconds=1500)
        self.assertEqual(result["sha"], SHA)
        self.assertEqual(clock.now, 170)
        self.assertTrue(all(0 < timeout <= 10 for timeout in calls))

    def test_long_gate_remains_bounded_and_a_main_failure_stops_immediately(self):
        clock = Clock()
        with self.assertRaisesRegex(gate.GateError, "within 1500"):
            gate.require_main_success(REPOSITORY, SHA, "fixture-token",
                fetch=Mock(return_value=listing(run(status="queued", conclusion=None))),
                clock=clock.read, sleep=clock.sleep, wait_seconds=1500)
        self.assertEqual(clock.now, 1500)
        for conclusion in ("failure", "cancelled", "timed_out"):
            clock = Clock()
            with self.subTest(conclusion=conclusion), self.assertRaisesRegex(gate.GateError, "did not succeed"):
                gate.require_main_success(REPOSITORY, SHA, "fixture-token",
                    fetch=Mock(return_value=listing(run(conclusion=conclusion))),
                    clock=clock.read, sleep=clock.sleep, wait_seconds=1500)
            self.assertEqual(clock.sleeps, [])

    def test_invalid_wait_budgets_are_refused_without_network_or_token_exposure(self):
        secret = "fixture-secret-never-log-this"
        for budget in (0, -1, 1501, True, 1.5, None, secret):
            network = Mock()
            with self.subTest(budget=budget), self.assertRaises(gate.GateError) as caught:
                gate.require_main_success(REPOSITORY, SHA, secret, fetch=network, wait_seconds=budget)
            network.assert_not_called()
            self.assertNotIn(secret, str(caught.exception))
        for budget in ("0", "1501", "-1", "1.5", secret):
            output = io.StringIO()
            with self.subTest(cli=budget), redirect_stderr(output), \
                    patch.object(gate, "fetch_runs") as network, self.assertRaises(SystemExit):
                gate.main(["--repository", REPOSITORY, "--sha", SHA, "--wait-seconds", budget])
            network.assert_not_called()
            self.assertNotIn(secret, output.getvalue())

    def test_cli_passes_explicit_parallel_budget_and_default_recheck_is_120(self):
        for extra, expected in (([], 120), (["--wait-seconds", "1500"], 1500)):
            with self.subTest(extra=extra), patch.dict(os.environ, {"GH_TOKEN": "fixture-token"}), \
                    patch.object(gate, "require_main_success", return_value={"run_id": 1, "run_attempt": 1, "sha": SHA}) as check:
                self.assertEqual(gate.main(["--repository", REPOSITORY, "--sha", SHA, *extra]), 0)
            self.assertEqual(check.call_args.kwargs["wait_seconds"], expected)

    def test_malformed_or_ambiguous_matching_metadata_fails_closed(self):
        for payload in ({}, {"total_count": 101, "workflow_runs": []},
                        listing(run(run_attempt=0)), listing(run(repository={})),
                        listing(run(status="unexpected")), listing(run(conclusion="cancelled"))):
            with self.subTest(payload=payload), self.assertRaises(gate.GateError):
                self.check(payload)

    def test_transport_is_fixed_authenticated_bounded_and_does_not_follow_redirects(self):
        url = "https://api.github.com/repos/example/repo/actions/workflows/tests.yml/runs"
        response = Mock(status=200)
        response.geturl.return_value = url
        response.read.return_value = json.dumps(listing(run())).encode()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        opener = Mock()
        opener.open.return_value = response
        with patch.object(gate, "build_opener", return_value=opener):
            self.assertEqual(gate._fetch_json(url, "fixture-token", 3), listing(run()))
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, url)
        self.assertEqual(request.get_header("Authorization"), "Bearer fixture-token")
        self.assertEqual(opener.open.call_args.kwargs["timeout"], 3)
        self.assertIsNone(gate._NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.invalid"))
        with patch.object(gate, "_fetch_json", return_value=listing(run())) as request_json:
            self.assertEqual(gate.fetch_runs(REPOSITORY, SHA, "fixture-token", timeout=1), listing(run()))
        parsed = urlsplit(request_json.call_args.args[0])
        self.assertEqual((parsed.scheme, parsed.netloc), ("https", "api.github.com"))
        self.assertEqual(parsed.path, f"/repos/{REPOSITORY}/actions/workflows/tests.yml/runs")
        self.assertEqual(parse_qs(parsed.query)["head_sha"], [SHA])
        self.assertEqual(parse_qs(parsed.query)["branch"], ["main"])
        self.assertEqual(parse_qs(parsed.query)["event"], ["push"])

    def test_stalled_network_has_an_actual_wall_clock_deadline(self):
        release = threading.Event()

        def stalled(*args):
            release.wait(2)
            return listing(run())

        started = time.monotonic()
        try:
            with patch.object(gate, "_fetch_json", side_effect=stalled), \
                 self.assertRaisesRegex(gate.GateError, "deadline"):
                gate.fetch_runs(REPOSITORY, SHA, "fixture-token", timeout=.02)
        finally:
            release.set()
        self.assertLess(time.monotonic() - started, 2)

    def test_invalid_cli_identity_and_network_errors_do_not_expose_credentials(self):
        secret = "fixture-secret-that-must-not-be-logged"
        for repository, sha in (("https://other.invalid/token", SHA), (REPOSITORY, secret)):
            output = io.StringIO()
            with patch.dict(os.environ, {"GH_TOKEN": secret}), redirect_stderr(output), \
                 patch.object(gate, "fetch_runs") as network:
                self.assertEqual(gate.main(["--repository", repository, "--sha", sha]), 1)
                network.assert_not_called()
            self.assertNotIn(secret, output.getvalue())
        with patch.object(gate, "build_opener", side_effect=OSError(secret)), \
             self.assertRaises(gate.GateError) as caught:
            gate._fetch_json("https://api.github.com/", secret, 1)
        self.assertNotIn(secret, str(caught.exception))


class ReleaseWorkflowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.tests = (root / ".github/workflows/tests.yml").read_text("utf-8")
        cls.package = (root / ".github/workflows/package.yml").read_text("utf-8")
        cls.builder = (root / "scripts/build_desktop.py").read_text("utf-8")

    def job(self, name):
        match = re.search(r"^  " + re.escape(name) + r":\n(.*?)(?=^  [\w-]+:|\Z)", self.package, re.M | re.S)
        self.assertIsNotNone(match, name)
        return match.group(1)

    def test_independent_main_keeps_full_native_and_extracted_source_tests_on_both_hosts(self):
        self.assertIn("os: [ubuntu-latest, windows-latest]", self.tests)
        for command in ("python scripts/build_native.py", "python -X utf8 scripts/run_tests.py",
                        "python scripts/build_desktop.py --edition public --source-only",
                        "python scripts/verify_release.py --edition public"):
            self.assertIn("- run: " + command, self.tests)
        self.assertNotIn("uses: ./.github/workflows/tests.yml", self.package)

    def test_publication_requires_parallel_main_gate_and_rechecks_latest_exact_sha(self):
        main = self.job("main-ci")
        publish = self.job("publish")
        self.assertIn("needs: [main-ci, windows]", publish)
        self.assertIn("github.event_name == 'push' && github.ref_type == 'tag'", main)
        self.assertIn("timeout-minutes: 30", main)
        self.assertIn("actions: read", main)
        self.assertIn('--sha "$release_sha" --wait-seconds 1500', main)
        self.assertIn('release_sha="$(git rev-parse HEAD)"', main)
        self.assertIn('python3 scripts/check_release_ci.py --sha "$release_sha"\n', publish)
        self.assertNotIn("--wait-seconds", publish)
        self.assertLess(publish.index("Require independent main CI"), publish.index("Publish Windows installer"))

    def test_package_keeps_source_audit_frozen_diagnostic_and_clean_installer_without_double_native_build(self):
        windows = self.job("windows")
        self.assertNotIn("- run: python scripts/build_native.py", windows)
        self.assertIn('str(ROOT / "scripts/build_native.py")', self.builder)
        for command in ("python scripts/build_desktop.py --edition public",
                        "python scripts/smoke_desktop.py --edition public --report build/public-windows-smoke.json",
                        "./scripts/build_installer.ps1 -SmokeTest"):
            self.assertIn(command, windows)
        self.assertIn("dist/public/*-setup.exe", windows)
        self.assertIn("dist/public/*.zip", windows)


if __name__ == "__main__":
    unittest.main()
