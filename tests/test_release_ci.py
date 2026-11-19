"""Publication must follow the independent main run, not merely tag tests."""
from contextlib import redirect_stderr
import io
import json
import os
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


if __name__ == "__main__":
    unittest.main()
