"""Require successful independent main-branch CI for the release's exact commit.

Reusable tests inside a tag/package workflow do not satisfy this gate. Only a
push run of tests.yml on main may authorize publication. No writes are made to
GitHub, and authentication comes exclusively from GH_TOKEN.
"""
from __future__ import annotations

import argparse
import json
import os
import queue
import re
import sys
import threading
import time
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener


WAIT_SECONDS = 120
MAX_WAIT_SECONDS = 40 * 60
POLL_SECONDS = 10
REQUEST_SECONDS = 10
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
PENDING = frozenset(("queued", "in_progress", "requested", "waiting", "pending"))
WORKFLOW_PATH = ".github/workflows/tests.yml"


class GateError(RuntimeError):
    """A bounded, sanitized refusal to publish."""


def parse_wait_seconds(value: str) -> int:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,4}", value):
        raise argparse.ArgumentTypeError(f"Expected an integer main CI wait from 1 to {MAX_WAIT_SECONDS} seconds.")
    result = int(value)
    if not 1 <= result <= MAX_WAIT_SECONDS:
        raise argparse.ArgumentTypeError(f"Expected an integer main CI wait from 1 to {MAX_WAIT_SECONDS} seconds.")
    return result


def validate_inputs(repository: str, sha: str) -> tuple[str, str]:
    if (not isinstance(repository, str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", repository)):
        raise GateError("Expected a GitHub owner/repository name.")
    if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-fA-F]{40}", sha):
        raise GateError("Expected the checked-out commit's full 40-character SHA.")
    return repository, sha.lower()


def latest_main_run(payload: dict, repository: str, sha: str) -> dict | None:
    if (not isinstance(payload, dict) or not isinstance(payload.get("workflow_runs"), list)
            or type(payload.get("total_count")) is not int or payload["total_count"] < 0
            or payload["total_count"] > 100 or len(payload["workflow_runs"]) > payload["total_count"]):
        raise GateError("Invalid or incomplete GitHub Actions workflow listing.")
    matches = []
    for run in payload["workflow_runs"]:
        if not isinstance(run, dict):
            raise GateError("Invalid GitHub Actions workflow run.")
        if (run.get("event") != "push" or run.get("head_branch") != "main"
                or run.get("head_sha") != sha
                or not isinstance(run.get("path"), str)
                or run["path"].split("@", 1)[0] != WORKFLOW_PATH):
            continue
        if (not isinstance(run.get("repository"), dict)
                or not isinstance(run["repository"].get("full_name"), str)
                or run["repository"]["full_name"].lower() != repository.lower()
                or type(run.get("id")) is not int or run["id"] <= 0
                or type(run.get("run_attempt")) is not int or run["run_attempt"] <= 0):
            raise GateError("Invalid identity for the matching main CI run.")
        matches.append(run)
    # GitHub run IDs increase for new push runs; a rerun keeps its ID and
    # increments run_attempt. Never accept an older success over a newer run.
    return max(matches, key=lambda r: (r["id"], r["run_attempt"])) if matches else None


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None  # Never forward the token to a redirected endpoint.


def _fetch_json(url: str, token: str, timeout: float) -> dict:
    request = Request(url, headers={"Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + token, "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "OrreRandomizer-release-CI-gate"})
    try:
        with build_opener(_NoRedirect()).open(request, timeout=timeout) as response:
            if response.status != 200 or response.geturl() != url:
                raise GateError("Unexpected GitHub Actions API response.")
            body = response.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES:
            raise GateError("GitHub Actions response exceeded its size limit.")
        return json.loads(body)
    except GateError:
        raise
    except Exception:
        # HTTP bodies, request headers and library exception strings may contain
        # credentials or unexpected server text. Never copy them to CI logs.
        raise GateError("Cannot read the independent main CI result from GitHub.") from None


def fetch_runs(repository: str, sha: str, token: str, *, timeout: float) -> dict:
    query = urlencode({"branch": "main", "event": "push", "head_sha": sha,
                       "per_page": 100, "exclude_pull_requests": "true"})
    url = f"https://api.github.com/repos/{repository}/actions/workflows/tests.yml/runs?{query}"
    result = queue.Queue(maxsize=1)

    def read():
        try:
            result.put((True, _fetch_json(url, token, timeout)))
        except Exception:
            result.put((False, None))

    # Socket timeouts do not bound DNS resolution or a trickling response.
    # A daemon reader gives the caller an actual wall-clock request deadline;
    # the short-lived gate exits on failure without waiting for that reader.
    threading.Thread(target=read, name="main-ci-api", daemon=True).start()
    try:
        successful, payload = result.get(timeout=timeout)
    except queue.Empty:
        raise GateError("GitHub Actions request exceeded its deadline.") from None
    if not successful:
        raise GateError("Cannot read the independent main CI result from GitHub.")
    return payload


def require_main_success(repository: str, sha: str, token: str, *,
                         fetch=fetch_runs, clock=time.monotonic, sleep=time.sleep,
                         wait_seconds: int = WAIT_SECONDS) -> dict:
    repository, sha = validate_inputs(repository, sha)
    if type(wait_seconds) is not int or not 1 <= wait_seconds <= MAX_WAIT_SECONDS:
        raise GateError(f"The main CI wait must be an integer from 1 to {MAX_WAIT_SECONDS} seconds.")
    if (not isinstance(token, str) or not token or len(token) > 4096
            or any(character.isspace() for character in token)):
        raise GateError("GH_TOKEN is required for the release CI check.")
    deadline = clock() + wait_seconds
    while True:
        remaining = deadline - clock()
        if remaining <= 0:
            raise GateError(f"Independent main CI did not finish within {wait_seconds} seconds.")
        payload = fetch(repository, sha, token, timeout=min(REQUEST_SECONDS, remaining))
        if clock() >= deadline:
            raise GateError(f"Independent main CI did not finish within {wait_seconds} seconds.")
        run = latest_main_run(payload, repository, sha)
        if run is None:
            raise GateError("No independent tests.yml push run on main exists for this exact commit.")
        if run.get("status") == "completed":
            if run.get("conclusion") != "success":
                raise GateError("The latest independent main CI run did not succeed; publication is blocked.")
            return {"sha": sha, "run_id": run["id"], "run_attempt": run["run_attempt"]}
        if run.get("status") not in PENDING:
            raise GateError("Unknown independent main CI state; publication is blocked.")
        sleep(min(POLL_SECONDS, max(0, deadline - clock())))


def main(arguments=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--sha", required=True, help="git rev-parse HEAD from the immutable checkout")
    parser.add_argument("--wait-seconds", type=parse_wait_seconds, default=WAIT_SECONDS,
                        help=f"Bounded main CI wait (1..{MAX_WAIT_SECONDS} seconds); default: 120")
    args, unknown = parser.parse_known_args(arguments)
    try:
        if unknown:
            raise GateError("Unsupported release CI check arguments.")
        result = require_main_success(args.repository, args.sha, os.environ.get("GH_TOKEN"),
                                      wait_seconds=args.wait_seconds)
    except GateError as error:
        print("Release blocked: " + str(error), file=sys.stderr)
        return 1
    print(f"Independent main CI run {result['run_id']} (attempt {result['run_attempt']}) "
          f"succeeded for {result['sha']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
