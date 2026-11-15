"""Select an integrity-checked update from this project's stable releases."""
from __future__ import annotations

from dataclasses import dataclass
import re

from . import REPOSITORY_NAME

REPOSITORY = f"KadenHD/{REPOSITORY_NAME}"
LATEST_RELEASE_API = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
MAX_PACKAGE_BYTES = 1024 * 1024 * 1024
_VERSION = re.compile(r"v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
                      r"(?:-([0-9A-Za-z.-]+))?(?:\+([0-9A-Za-z.-]+))?\Z")


def _version_key(value):
    if not isinstance(value, str) or len(value) > 100:
        return None
    # Older desktop previews used Python-style rc suffixes.
    if re.fullmatch(r"v?[0-9]+\.[0-9]+\.[0-9]+rc[0-9]+", value):
        value = re.sub(r"rc([0-9]+)$", r"-rc.\1", value)
    match = _VERSION.fullmatch(value)
    if not match:
        return None
    major, minor, patch, prerelease, metadata = match.groups()
    for identifiers in (prerelease, metadata):
        if identifiers is not None and any(not part for part in identifiers.split(".")):
            return None
    identifiers = prerelease.split(".") if prerelease else []
    if any(part.isdigit() and len(part) > 1 and part.startswith("0") for part in identifiers):
        return None
    parts = tuple((0, int(part)) if part.isdigit() else (1, part) for part in identifiers)
    return int(major), int(minor), int(patch), not bool(prerelease), parts


@dataclass(frozen=True)
class ReleaseUpdate:
    version: str
    download_url: str
    size: int = 0
    sha256: str = ""
    kind: str = "installer"


def allowed_download(update: ReleaseUpdate) -> bool:
    """Only exact release assets in this project's HTTPS GitHub namespace."""
    if not isinstance(update, ReleaseUpdate) or not isinstance(update.download_url, str):
        return False
    version = _version_key(update.version)
    if version is None or not version[3] or "+" in update.version or update.version.startswith("v"):
        return False
    prefix = f"/{REPOSITORY}/releases/download/v{update.version}/"
    if update.kind not in ("installer", "portable"):
        return False
    suffix = "-setup.exe" if update.kind == "installer" else ".zip"
    name = f"{REPOSITORY_NAME}-{update.version}-windows-x64{suffix}"
    return (update.download_url == "https://github.com" + prefix + name
            and type(update.size) is int and 0 < update.size <= MAX_PACKAGE_BYTES
            and isinstance(update.sha256, str)
            and re.fullmatch(r"[0-9a-f]{64}", update.sha256) is not None)


def release_update(payload, current_version: str, kind="installer") -> ReleaseUpdate | None:
    """Return a newer stable Windows download, otherwise remain silent."""
    current = _version_key(current_version)
    if current is None or not isinstance(payload, dict):
        return None
    if payload.get("draft") is not False or payload.get("prerelease") is not False:
        return None
    tag = payload.get("tag_name")
    remote = _version_key(tag)
    if (remote is None or not remote[3] or remote <= current or not tag.startswith("v")
            or "+" in tag):
        return None
    version = tag[1:]
    assets = payload.get("assets")
    if not isinstance(assets, list):
        return None
    suffix = "-setup.exe" if kind == "installer" else ".zip"
    expected_names = (f"{REPOSITORY_NAME}-{version}-windows-x64{suffix}",)
    for name in expected_names:
        for asset in assets:
            if not isinstance(asset, dict) or asset.get("name") != name or asset.get("state") != "uploaded":
                continue
            url = asset.get("browser_download_url")
            digest = asset.get("digest", "")
            if isinstance(url, str) and isinstance(digest, str) and digest.startswith("sha256:"):
                update = ReleaseUpdate(version, url, asset.get("size"), digest[7:], kind)
                if allowed_download(update):
                    return update
    return None
