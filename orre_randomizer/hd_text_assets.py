"""Offline capture/preparation contract for the GSmsg vector-text bridge.

TextPages contains player-ROM native references, not external donor imagery.
Switching to HD later needs those small references and the bundled OFL font;
it never reopens the original ROM or a running emulator.
"""
from __future__ import annotations

import hashlib
from io import BytesIO
import json
from pathlib import Path
import re

from .engine.analyze_game import FormatError
from .hd_text import CONTRACT, CORPUS_POLICY
from .hd_text_runtime import BRIDGE_CONTRACT, native_text_pages
from .hd_text_vectors import LICENSE_SHA256, SOURCE, render_vector_pages

MANIFEST = "TextPages/plan.json"


def _json(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode("ascii")


def native_text_contract() -> dict:
    """Immutable page layout and runtime semantics, independent of HD artwork."""
    return {"contract": CONTRACT, "bridge_contract": BRIDGE_CONTRACT,
            "native_corpus_policy": CORPUS_POLICY,
            "native_glyph_draw_policy": "space-is-an-advance-v1"}


def text_recipe() -> dict:
    """Canonical HD cache input; changing artwork never invalidates native pages."""
    from .hd_text_symbols import _RECIPES
    return native_text_contract() | {"vector": dict(SOURCE),
            "symbol_recipes_sha256": hashlib.sha256(_json(_RECIPES)).hexdigest()}


def _write_new_files(root: Path, entries: dict[str, bytes]):
    root = Path(root)
    if root.is_symlink():
        raise FormatError("Text asset destination cannot be a symbolic link")
    root = root.resolve()
    targets = []
    for relative, payload in entries.items():
        path = root / relative
        if (Path(relative).is_absolute() or ".." in Path(relative).parts
                or any(parent.is_symlink() for parent in (path, *path.parents) if parent != root.parent)
                or not path.resolve().is_relative_to(root)):
            raise FormatError("Text asset path leaves its destination")
        if path.exists() and (not path.is_file() or path.read_bytes() != payload):
            raise FormatError("Conflicting text asset already exists")
        targets.append((path, payload))
    for path, payload in targets:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            with path.open("xb") as stream:
                stream.write(payload)


def capture_text_assets(dol: bytes, plan: dict, destination: Path, *, cancel=None) -> dict:
    """Persist validated DOL-owned pages under a separate, bounded directory."""
    pages = native_text_pages(dol, plan)
    if not 1 <= len(pages) <= 128:
        raise FormatError("Unexpected number of native text pages")
    payloads, references = {}, []
    for index, page in enumerate(pages):
        _checkpoint(cancel)
        sha = hashlib.sha256(page).hexdigest()
        relative = f"TextPages/{sha}.bin"
        payloads[relative] = page
        references.append({"index": index, "file": relative, "sha256": sha, "bytes": len(page)})
    manifest = {"version": 2, "native_contract": native_text_contract(),
                "recipe": text_recipe(), "plan": plan, "references": references}
    payloads[MANIFEST] = _json(manifest)
    _write_new_files(destination, payloads)
    result = {"contract": BRIDGE_CONTRACT, "game_id": plan["game_id"], "manifest": MANIFEST,
            "auxiliary_files": {key: hashlib.sha256(value).hexdigest() for key, value in payloads.items()},
            "pages": len(pages), "glyphs": len(plan["glyphs"]),
            "source_iso_needed_for_hd": False, "runtime_validated": False}
    if "counter_layout" in plan:
        result["counter_layout"] = plan["counter_layout"]
    return result


def prepare_text_overlays(native_directory: Path, destination: Path, *,
                          font_file: Path | None = None, license_file: Path | None = None,
                          cancel=None) -> dict:
    """Generate genuine4× vector pages from persisted native metrics and guides."""
    from .hd_overlays import dolphin_texture_name
    source = Path(native_directory).resolve()
    destination = Path(destination)
    if destination.is_symlink():
        raise FormatError("Text HD output cannot be a symbolic link")
    destination = destination.resolve()
    if destination == source or (source in destination.parents and not destination.is_relative_to(source / "HD")):
        raise FormatError("Text HD output cannot replace its native guides")
    manifest_path = source / MANIFEST
    if manifest_path.is_symlink() or manifest_path.stat().st_size > 16 * 1024 * 1024:
        raise FormatError("Invalid native text manifest")
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes.decode("ascii"))
    historical_recipe = manifest.get("recipe")
    if not isinstance(historical_recipe, dict) or manifest.get("version") not in (1, 2):
        raise FormatError("Unsupported native text capture contract")
    expected_native = native_text_contract()
    # Version1 recorded the entire HD recipe. Only its native sub-contract is
    # authoritative for pages; font and symbol revisions are historical facts.
    recorded_native = (manifest.get("native_contract") if manifest["version"] == 2 else
                       {key: historical_recipe.get(key) for key in expected_native})
    legacy_native = expected_native | {"native_corpus_policy": "regional-native-message-alphabet-v1"}
    if recorded_native not in (expected_native, legacy_native):
        raise FormatError("Native text contract requires regeneration")
    plan = manifest.get("plan", {})
    if plan.get("contract") != CONTRACT or plan.get("bridge_contract") != BRIDGE_CONTRACT:
        raise FormatError("Native text plan differs from its capture contract")
    references = manifest.get("references", ())
    if not 1 <= len(references) <= 128:
        raise FormatError("Invalid native text page directory")
    pages = []
    for index, row in enumerate(references):
        _checkpoint(cancel)
        if (row.get("index") != index or not re.fullmatch(r"TextPages/[0-9a-f]{64}\.bin", row.get("file", ""))
                or row.get("bytes") != 131200):
            raise FormatError("Invalid native text reference")
        path = source / row["file"]
        if path.is_symlink() or path.stat().st_size != row["bytes"]:
            raise FormatError("Native text reference was replaced")
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != row["sha256"]:
            raise FormatError("Native text reference checksum differs")
        pages.append(data)
    assets = Path(__file__).resolve().parent / "assets" / "game" / "fonts"
    font_file = Path(font_file) if font_file is not None else assets / "NotoSansJP.ttf"
    license_file = Path(license_file) if license_file is not None else assets / "OFL-NotoSansJP.txt"
    images, report = render_vector_pages(pages, plan, font_file, license_file, cancel=cancel)
    if not report["hd_ready"]:
        if report.get("requires_native_canvas_update"):
            raise FormatError("The captured glyph canvas clips the common typography; create a new game folder")
        raise FormatError("The vector donor does not cover every registered native text glyph")
    payloads, records = {}, []
    for index, (page, image) in enumerate(zip(pages, images, strict=True)):
        _checkpoint(cancel)
        key = dolphin_texture_name(512, 512, 0, page[128:]) + ".png"
        encoded = BytesIO()
        image.save(encoded, format="PNG", optimize=False)
        payload = encoded.getvalue()
        payloads[key] = payload
        records.append({"file": key, "sha256": hashlib.sha256(payload).hexdigest(),
            "role": "gsmsg_vector_page", "native_dimensions": [512, 512], "dimensions": [2048, 2048],
            "native_page_sha256": references[index]["sha256"], "source": dict(SOURCE),
            "native_metrics_unchanged": True, "native_raster_used_for_HD_art": False})
    # Root cache entries stay texture PNGs; legal/recipe metadata is explicitly auxiliary.
    aux = {"TextSources/OFL-NotoSansJP.txt": license_file.read_bytes(),
           "TextSources/recipe.json": _json(text_recipe()),
           "TextSources/native-guides.json": _json({
               "native_contract": recorded_native,
               "capture_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
               "historical_capture_recipe": historical_recipe})}
    if hashlib.sha256(aux["TextSources/OFL-NotoSansJP.txt"]).hexdigest() != LICENSE_SHA256:
        raise FormatError("The vector donor license changed")
    _write_new_files(destination, payloads | aux)
    return {"version": 1, "game_id": manifest["plan"]["game_id"], **report,
            "files": {key: hashlib.sha256(data).hexdigest() for key, data in payloads.items()},
            "auxiliary_files": {key: hashlib.sha256(data).hexdigest() for key, data in aux.items()},
            "assets": records, "required_packs": [], "source_iso_needed": False,
            "native_contract": recorded_native,
            "legacy_native_coverage": recorded_native != expected_native,
            "coverage_scope": "captured native glyphs only; newer corpus additions require a new native bridge",
            "historical_hd_recipe_changed": historical_recipe != text_recipe(),
            "runtime_validated": False}


def _checkpoint(cancel):
    if cancel is not None and cancel.is_set():
        raise InterruptedError("Text texture generation cancelled")
