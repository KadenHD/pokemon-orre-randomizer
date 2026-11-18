"""Read-only verification of the two release-pinned HD archives over HTTPS.

Without --full-sha256 this checks headers and byte ranges, not complete archive
integrity. No download is stored, application setting changed or object uploaded.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import urllib.request
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orre_randomizer.hd_packs import PACKS, PackStore
from scripts.prepare_hd_hosting import _base_url


def _response(source, method="GET", headers=None):
    request = urllib.request.Request(source, method=method,
        headers={"User-Agent": "Pokemon-Orre-Randomizer-Origin-Check",
                 "Accept-Encoding": "identity", **(headers or {})})
    response = urllib.request.urlopen(request, timeout=30)
    if urlsplit(response.geturl()).scheme != "https":
        response.close()
        raise ValueError("HD origin redirected away from HTTPS")
    if response.headers.get("Content-Encoding", "identity").lower() != "identity":
        response.close()
        raise ValueError("HD origin changed the archive content encoding")
    return response


def _verify_asset(url, size, sha256, *, full_sha256=False, zip_header=True, combined=None):
    with _response(url, "HEAD") as response:
        if response.status != 200 or response.headers.get("Content-Length") != str(size):
            raise ValueError("HEAD size differs from the pinned asset")
        cache_control = response.headers.get("Cache-Control", "")
    ranges = []
    length = min(64, size)
    for first, last in ((0, length - 1), (size - length, size - 1)):
        expected = f"bytes {first}-{last}/{size}"
        with _response(url, headers={"Range": f"bytes={first}-{last}"}) as response:
            if response.status != 206 or response.headers.get("Content-Range") != expected:
                raise ValueError("Byte-range response does not match the requested interval")
            data = response.read(length + 1)
            if len(data) != length:
                raise ValueError("Byte-range payload has an unexpected length")
            if zip_header and first == 0 and not data.startswith(b"PK\x03\x04"):
                raise ValueError("Response is not the original ZIP archive")
        ranges.append(expected)
    checked_hash = None
    if full_sha256:
        count, digest = 0, hashlib.sha256()
        with _response(url) as response:
            if response.status != 200:
                raise ValueError("Full asset response is not HTTP 200")
            while chunk := response.read(4 * 1024**2):
                count += len(chunk)
                if count > size:
                    raise ValueError("Response exceeds the pinned asset size")
                digest.update(chunk)
                if combined is not None:
                    combined.update(chunk)
        if count != size or digest.hexdigest() != sha256:
            raise ValueError("Complete asset SHA-256 or size differs")
        checked_hash = digest.hexdigest()
    return {"url": url, "size": size, "expected_sha256": sha256,
        "verified_sha256": checked_hash, "range_checks": ranges, "cache_control": cache_control}


def verify_origin(base_url: str, *, full_sha256=False) -> dict:
    source = _base_url(base_url)
    if source is None:
        raise ValueError("An explicit HTTPS origin is required")
    store = PackStore(source=source)
    results = []
    for game in ("colosseum", "xd"):
        pack = PACKS[game]
        for part in pack.parts:
            result = _verify_asset(store.archive_source(pack, part), part.size, part.sha256,
                                   full_sha256=full_sha256)
            results.append({"game": game, "version": pack.version, **result})
    return {"schema": 1, "origin": source, "read_only": True,
        "full_integrity_verified": bool(full_sha256), "archives": results,
        "local_archives_written": False, "production_config_changed": False}


def verify_github_manifest(manifest: dict, *, full_sha256=False) -> dict:
    repository = manifest.get("repository", manifest.get("proposed_repository", ""))
    tag = manifest.get("tag", manifest.get("proposed_tag", ""))
    if (not isinstance(repository, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository)
            or not isinstance(tag, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", tag)):
        raise ValueError("Manifest needs a fixed GitHub repository and release tag")
    base = f"https://github.com/{repository}/releases/download/{tag}/"
    archives, assets = manifest.get("archives", []), manifest.get("assets", [])
    if len(archives) != 2 or {r["game"] for r in archives} != {"colosseum", "xd"}:
        raise ValueError("Manifest must describe both original archives")
    by_name = {a["name"]: a for a in assets}
    if len(by_name) != len(assets):
        raise ValueError("Manifest contains duplicate asset names")
    checked, used = [], set()
    for archive in archives:
        pack = PACKS[archive["game"]]
        part = pack.parts[0]
        if (archive["version"], archive["size"], archive["sha256"]) != (pack.version, part.size, part.sha256):
            raise ValueError("Manifest does not match the pinned original archive")
        cursor, combined, results = 0, hashlib.sha256(), []
        for name in archive["assets"]:
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name) or name in used:
                raise ValueError("Invalid or repeated transport asset")
            asset = by_name[name]
            if (asset["game"] != pack.game or asset["offset"] != cursor
                    or type(asset["size"]) is not int or not 0 < asset["size"] < 2 * 1024**3
                    or not re.fullmatch(r"[a-f0-9]{64}", asset["sha256"])):
                raise ValueError("Invalid transport boundaries or checksum")
            used.add(name)
            results.append(_verify_asset(base + name, asset["size"], asset["sha256"],
                full_sha256=full_sha256, zip_header=cursor == 0, combined=combined))
            cursor += asset["size"]
        if cursor != part.size:
            raise ValueError("Fragments do not cover the complete original archive")
        if full_sha256 and combined.hexdigest() != part.sha256:
            raise ValueError("Reassembled original archive SHA-256 differs")
        checked.append({"game": pack.game, "version": pack.version, "assets": results,
            "verified_archive_sha256": combined.hexdigest() if full_sha256 else None})
    if used != set(by_name):
        raise ValueError("Manifest includes unreferenced transport assets")
    return {"schema": 1, "repository": repository, "tag": tag, "read_only": True,
        "full_integrity_verified": bool(full_sha256), "archives": checked,
        "local_archives_written": False, "production_config_changed": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--base-url")
    source.add_argument("--github-manifest", type=Path)
    parser.add_argument("--full-sha256", action="store_true",
        help="Read all archive bytes without storing them (about 4.02 GB for the current catalog)")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    result = (verify_github_manifest(json.loads(args.github_manifest.read_text("utf-8")),
                                   full_sha256=args.full_sha256) if args.github_manifest
              else verify_origin(args.base_url, full_sha256=args.full_sha256))
    payload = json.dumps(result, indent=2) + "\n"
    if args.report:
        with args.report.open("x", encoding="utf-8") as output:
            output.write(payload)
    else:
        print(payload, end="")


if __name__ == "__main__":
    main()
