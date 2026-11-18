"""Register audited pack-textured GPU body captures without changing native art."""
import argparse
import copy
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from orre_randomizer.artwork import _png, _png_pixels
from orre_randomizer.hd_packs import PACKS


def _legacy_register(source, pack_root, *, include_heads=False, check_only=False):
    source, pack_root = Path(source).resolve(), Path(pack_root).resolve()
    models = pack_root / "models"
    manifest = json.loads((pack_root / "provenance.json").read_text("utf-8"))
    captured = json.loads((source / "hd-fullbody-manifest.json").read_text("utf-8"))
    native = json.loads((models / "fullbody-manifest.json").read_text("utf-8"))
    pack = PACKS["xd"]
    captured_source = captured.get("source", {})
    model = captured.get("source_model", captured_source.get("model"))
    if captured.get("hd_pack", captured_source.get("pack")) != pack.key or model != native["source_model"]:
        raise ValueError("HD and native model provenance differ")
    from orre_randomizer.hd_overlays import _complete_lugia_hd_capture
    _complete_lugia_hd_capture({"source": captured_source})
    result = {"schema": 1, "kind": "native-mesh-render-with-pack-hd-textures",
        "dimensions": [256, 256], "native_dimensions": [64, 64],
        "source": {"pack": pack.key, "archives": [p.sha256 for p in pack.parts],
                   "model": model, "hd_art_revision": captured_source["hd_art_revision"],
                   "material_recipes": captured_source.get("material_recipes", [])},
        "capture": captured["capture"], "conversion": captured["conversion"],
        "rights": "Game-derived geometry and upstream HD textures; separate from MIT. See THIRD_PARTY_NOTICES.md.",
        "files": {}}
    coverage = captured.get("source", {}).get("hd_material_coverage")
    if coverage is not None:
        result["source"]["hd_material_coverage"] = coverage
    evidence = captured.get("material_runtime_ab", {})
    if evidence:
        proof = Path(evidence["proof"]).read_bytes()
        if (not evidence.get("same_native_counter_and_silhouette_bounds") or
                not evidence.get("all_pairs_have_different_rendered_material_pixels") or
                type(evidence.get("pairs")) is not int or evidence["pairs"] < 1):
            raise ValueError("HD material runtime comparison is incomplete")
        result["material_runtime_ab"] = {
            "method": "Same native pose and counters with custom textures disabled/enabled",
            "report_sha256": hashlib.sha256(proof).hexdigest(),
            "pairs": evidence["pairs"], "same_silhouette_bounds": True,
            "different_rendered_material_pixels": True}
    silhouettes = []
    for shiny, name in enumerate(("dark-lugia-body-x4.png", "dark-lugia-shiny-body-x4.png")):
        entry = captured["files"][name]
        payload = (source / name).read_bytes()
        if (entry["shiny"] is not bool(shiny) or entry["source_dimensions"] != [1024, 1024]
                or len(payload) != entry["bytes"] or hashlib.sha256(payload).hexdigest() != entry["sha256"]):
            raise ValueError("HD body capture identity differs")
        pixels = _png_pixels(payload, (256, 256))
        alpha = pixels[3::4]
        if not any(alpha) or any(alpha[y*256+x] for y in range(256) for x in range(256)
                                if x in (0,255) or y in (0,255)):
            raise ValueError("HD body is empty or clipped")
        silhouettes.append(alpha)
        donors = entry["donor_source_records"]
        if not donors or any(item["hd_source"]["pack"] != pack.key for item in donors):
            raise ValueError("HD body is not based on the pinned HD pack")
        result["files"][name] = {"shiny": bool(shiny), "bytes": len(payload),
            "sha256": entry["sha256"], "source_capture_sha256": entry["source_capture_sha256"],
            "source_dimensions": [1024,1024], "source_alpha_bbox": entry["source_alpha_bbox"],
            "fitted_dimensions": entry["fitted_dimensions"], "materials": donors}
    if silhouettes[0] != silhouettes[1]:
        raise ValueError("Normal and shiny HD silhouettes differ")
    head_payloads = {}
    if include_heads:
        from PIL import Image
        for shiny, name in enumerate(("dark-lugia-head-x4.png", "dark-lugia-shiny-head-x4.png")):
            candidate = name.replace("-x4.png", "-candidate-168.png")
            entry = captured["optional_head_candidates"][candidate]
            payload = (source / "head-candidates" / candidate).read_bytes()
            body = result["files"]["dark-lugia-shiny-body-x4.png" if shiny else "dark-lugia-body-x4.png"]
            crop = entry["source_roi"]
            if (hashlib.sha256(payload).hexdigest() != entry["sha256"]
                    or entry["dimensions"] != [168, 168]
                    or entry["source_capture_sha256"] != body["source_capture_sha256"]
                    or len(crop) != 4 or not all(type(n) is int for n in crop)
                    or not (0 <= crop[0] < crop[2] <= 1024 and 0 <= crop[1] < crop[3] <= 1024)
                    or min(crop[2] - crop[0], crop[3] - crop[1]) < 168):
                raise ValueError("HD head capture identity or crop differs")
            with Image.open(io.BytesIO(payload), formats=("PNG",)) as image:
                if image.size != (168, 168):
                    raise ValueError("Unexpected HD head dimensions")
                pixels = image.convert("RGBA").tobytes()
            head_payloads[name] = _png((168, 168), pixels)
            result["files"][name] = {"shiny": bool(shiny), "bytes": len(head_payloads[name]),
                "sha256": hashlib.sha256(head_payloads[name]).hexdigest(), "dimensions": [168, 168],
                "native_dimensions": [42, 42], "source_capture_sha256": entry["source_capture_sha256"],
                "source_crop_box": crop, "source_dimensions": [1024, 1024],
                "conversion": "Audited GPU head crop, reduced from 192 to 168 pixels; no native bitmap enlargement"}
    text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if re.search(r"[A-Za-z]:[\\/]", text) or "private_pid" in text:
        raise ValueError("Private capture details cannot enter the public manifest")
    if check_only:
        return result
    # All validation precedes publication; native PNGs are never written here.
    for name in result["files"]:
        if name in head_payloads:
            (models / name).write_bytes(head_payloads[name])
        else:
            shutil.copyfile(source / name, models / name)
    (models / "hd-fullbody-manifest.json").write_text(text, encoding="utf-8", newline="\n")
    provenance = pack_root / "provenance.json"
    for name in (*result["files"], "hd-fullbody-manifest.json"):
        data = (models / name).read_bytes()
        manifest["files"]["models/" + name] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    provenance.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return result


_NATIVE = ("dark-lugia-body.png", "dark-lugia-shiny-body.png")
_HD = ("dark-lugia-body-x4.png", "dark-lugia-shiny-body-x4.png")
_MATERIAL_FIELDS = ("pack", "archives", "model", "hd_art_revision", "material_recipes", "hd_material_coverage")


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _json(data):
    return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _canonical_sha(data):
    return _sha(json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def _read(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("Registration inputs must be regular files")
    return path.read_bytes()


def _public(value):
    if isinstance(value, str) and (re.match(r"^[A-Za-z]:[\\/]", value) or value.startswith(("/", "\\\\"))):
        raise ValueError("Private paths cannot enter public body metadata")
    if isinstance(value, dict):
        if set(value) & {"private_pid", "source_card", "profile_path", "input_iso", "creation_time", "pid"}:
            raise ValueError("Private process details cannot enter public body metadata")
        for item in value.values():
            _public(item)
    elif isinstance(value, list):
        for item in value:
            _public(item)


def _hash(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _vector(value, length, *, integers=False):
    return (isinstance(value, list) and len(value) == length
            and all(type(v) in ((int,) if integers else (int, float)) and math.isfinite(v) for v in value))


def _asset(folder, name, record, size, shiny):
    payload = _read(folder / name)
    if record.get("shiny") is not shiny or record.get("bytes") != len(payload) or record.get("sha256") != _sha(payload):
        raise ValueError("Body PNG identity differs: " + name)
    pixels = _png_pixels(payload, (size, size))
    alpha = pixels[3::4]
    if (not any(alpha) or any(alpha[y * size + x] for y in range(size) for x in range(size)
                              if x in (0, size - 1) or y in (0, size - 1))
            or any(any(pixels[at:at + 3]) for at in range(0, len(pixels), 4) if not pixels[at + 3])):
        raise ValueError("Body PNG is empty, clipped or has hidden transparent RGB: " + name)
    if record.get("alpha_sha256", _sha(alpha)) != _sha(alpha):
        raise ValueError("Body silhouette hash differs: " + name)
    return payload, pixels


def _common(native, hd):
    common = native.get("common_capture")
    if not isinstance(common, dict) or common != hd.get("common_capture"):
        raise ValueError("Native/HD common capture contracts differ")
    if (common.get("schema") != 1 or common.get("matrix_count") != 86
            or not _hash(common.get("pose_signature_sha256"))
            or not isinstance(common.get("camera"), dict) or not common["camera"]
            or common.get("native_source_dimensions") != [256, 256]
            or common.get("hd_source_dimensions") != [1024, 1024]):
        raise ValueError("Incomplete pose/camera contract")
    roi, fit, padding = (common.get(key) for key in ("roi_normalized", "fitted_dimensions_native", "padding_native"))
    if (not _vector(roi, 4) or not 0 <= roi[0] < roi[2] <= 1 or not 0 <= roi[1] < roi[3] <= 1
            or not _vector(fit, 2, integers=True) or not _vector(padding, 2, integers=True)
            or any(f <= 0 or p < 1 or p + f >= 64 for f, p in zip(fit, padding))):
        raise ValueError("Invalid shared ROI, fit or padding")
    if set(common.get("captures", {})) != {"native-normal", "native-shiny", "hd-normal", "hd-shiny"}:
        raise ValueError("Four independent source captures are required")
    return common


def _capture_assets(native_source, hd_source, native, hd, common, capture_root):
    """Bind manifests and outputs to real raw/probe/matrix receipts before writes."""
    from PIL import Image
    pose_payload = _read(capture_root / "body-fixed-pose.json")
    pose = json.loads(pose_payload)
    joints = pose.get("joints", {})
    matrices = b"".join(bytes.fromhex(row["matrix"]) for _, row in sorted(joints.items(), key=lambda row: int(row[0], 16)))
    if (len(joints) != 86 or _sha(matrices) != common["pose_signature_sha256"]
            or common.get("canonical_pose_sha256") != _sha(pose_payload)):
        raise ValueError("Canonical86-matrix packet differs")
    payloads, decoded, raw_images = {}, {}, {}
    for mode, folder, manifest, size, names in (("native", native_source, native, 64, _NATIVE), ("hd", hd_source, hd, 256, _HD)):
        raw_size, factor = (256, 1) if mode == "native" else (1024, 4)
        for shiny, name in zip((False, True), names):
            label = mode + ("-shiny" if shiny else "-normal")
            entry = manifest["files"][name]
            capture = common["captures"][label]
            roi = [v * raw_size for v in common["roi_normalized"]]
            fit = [v * factor for v in common["fitted_dimensions_native"]]
            placement = [v * factor for v in common["padding_native"]]
            if (entry.get("source_dimensions") != [raw_size, raw_size]
                    or entry.get("source_roi") != roi or entry.get("fitted_dimensions") != fit
                    or entry.get("placement") != placement
                    or entry.get("pose_signature_sha256") != common["pose_signature_sha256"]
                    or entry.get("source_capture_sha256") != capture.get("raw_sha256")
                    or capture.get("dimensions") != [raw_size, raw_size]
                    or capture.get("pose_signature_sha256") != common["pose_signature_sha256"]
                    or capture.get("matrix_count") != 86 or capture.get("source_mode") != mode
                    or capture.get("shiny") is not shiny):
                raise ValueError("Body capture/ROI/fit/pose linkage differs: " + label)
            job = capture_root / label
            raw_payload = _read(job / "evidence/body-final-raw.png")
            proof_payload = _read(job / "body-probe.json")
            proof = json.loads(proof_payload)
            report = json.loads(_read(job / "report.json"))
            if (_sha(raw_payload) != capture.get("raw_sha256") or _sha(proof_payload) != capture.get("probe_receipt_sha256")
                    or proof.get("status") != "complete" or proof.get("mode") != label or proof.get("shiny") is not shiny
                    or proof.get("frame_sha256") != _sha(raw_payload) or proof.get("pose_signature_sha256") != _sha(matrices)
                    or proof.get("matrix_count") != 86
                    or proof.get("final_root_matrix") != joints["0xc288"]["matrix"]
                    or proof.get("final_control_matrix") != joints["0xc2c8"]["matrix"]
                    or report.get("status") != "finished" or report.get("protected_changes")
                    or report.get("protected_before") != report.get("protected_after")
                    or proof.get("pid") != report.get("pid") or proof.get("creation_time") != report.get("creation_time")
                    or report.get("hires_enabled") is not (mode == "hd")):
                raise ValueError("Actual GPU capture receipt differs: " + label)
            with Image.open(io.BytesIO(raw_payload), formats=("PNG",)) as image:
                if image.size != (raw_size, raw_size):
                    raise ValueError("Raw GPU dimensions differ")
                image = image.convert("RGBA")
            if (_sha(image.tobytes()) != capture.get("rgba_sha256")
                    or _sha(image.getchannel("A").tobytes()) != capture.get("alpha_sha256")
                    or list(image.getchannel("A").getbbox()) != capture.get("source_alpha_bbox")):
                raise ValueError("Decoded GPU pixels/silhouette differ")
            payload, pixels = _asset(folder, name, entry, size, shiny)
            fitted = image.convert("RGBa").resize(tuple(fit), Image.Resampling.BOX, box=tuple(roi)).convert("RGBA")
            expected = Image.new("RGBA", (size, size)); expected.paste(fitted, tuple(placement))
            if expected.tobytes() != pixels:
                raise ValueError("Body PNG differs from raw shared-fit reduction (recolor/flip/stroke): " + name)
            payloads["models/" + name], decoded[name], raw_images[label] = payload, pixels, image
    for names in (_NATIVE, _HD):
        if decoded[names[0]][3::4] != decoded[names[1]][3::4]:
            raise ValueError("Normal/shiny body alpha differs at a shared resolution")
    for shiny in (False, True):
        suffix = "-shiny" if shiny else "-normal"
        native_alpha = raw_images["native" + suffix].getchannel("A").tobytes()
        hd_alpha = raw_images["hd" + suffix].getchannel("A").resize((256, 256), Image.Resampling.BOX).tobytes()
        a, b = {i for i, v in enumerate(native_alpha) if v >= 128}, {i for i, v in enumerate(hd_alpha) if v >= 128}
        iou = len(a & b) / len(a | b)
        recorded = common["camera"].get("native_hd_silhouette_iou_threshold128")
        if iou < .98 or recorded is None or abs(iou - recorded) > .000001:
            raise ValueError("Raw native/HD projection silhouettes disagree")
    return payloads


def _publish_pair(pack_root, updates, protected, backup_dir):
    """Back up first, then stage all bytes and roll back every touched file on I/O failure."""
    backup = Path(backup_dir) if backup_dir is not None else ROOT / "build/hd-body-registration-backups" / uuid.uuid4().hex
    backup = backup.resolve()
    if backup.exists() or backup.is_relative_to(pack_root):
        raise ValueError("A new private backup directory outside the asset pack is required")
    for relative, payload in protected.items():
        if _read(pack_root / relative) != payload:
            raise ValueError("Installed resources changed during validation")
    backup.mkdir(parents=True, exist_ok=False)
    for relative, payload in protected.items():
        target = backup / relative; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(payload)
    (backup / "registration-backup.json").write_bytes(_json({"files": {key: {"bytes": len(value), "sha256": _sha(value)} for key, value in protected.items()}}))
    staged, touched = {}, []
    try:
        for relative, payload in updates.items():
            target = pack_root / relative
            temporary = target.with_name(target.name + ".pending-" + uuid.uuid4().hex)
            temporary.write_bytes(payload); staged[relative] = temporary
        for relative in updates:
            os.replace(staged[relative], pack_root / relative)
            touched.append(relative)
    except BaseException as error:
        rollback_errors = []
        for relative in reversed(touched):
            try:
                target = pack_root / relative
                temporary = target.with_name(target.name + ".rollback-" + uuid.uuid4().hex)
                temporary.write_bytes(protected[relative]); os.replace(temporary, target)
            except OSError as rollback_error:
                rollback_errors.append(str(rollback_error))
        if rollback_errors:
            raise RuntimeError("Publication failed; restore the private backup: " + str(backup)) from error
        raise
    finally:
        for temporary in staged.values():
            if temporary.exists():
                temporary.unlink()
    return str(backup)


def register_paired(hd_source, native_source, pack_root, *, capture_root=None, backup_dir=None, check_only=False):
    """Validate four captures and safely replace body art without changing portrait pixels."""
    hd_source, native_source, pack_root = (Path(p).resolve() for p in (hd_source, native_source, pack_root))
    models = pack_root / "models"
    native = json.loads(_read(native_source / "fullbody-manifest.json"))
    captured = json.loads(_read(hd_source / "hd-fullbody-manifest.json"))
    old_native_payload = _read(models / "fullbody-manifest.json")
    old_hd_payload = _read(models / "hd-fullbody-manifest.json")
    old_native, old_hd = json.loads(old_native_payload), json.loads(old_hd_payload)
    if (type(native.get("review_only")) is not bool or type(captured.get("review_only")) is not bool
            or not check_only and (native["review_only"] or captured["review_only"])):
        raise ValueError("Both body sets require explicit visual review before publication")
    if (native.get("dimensions") != [64, 64] or captured.get("dimensions") != [256, 256]
            or captured.get("native_dimensions") != [64, 64]
            or set(native.get("files", {})) != set(_NATIVE) or set(captured.get("files", {})) != set(_HD)
            or native.get("source_model") != old_native.get("source_model")
            or native.get("source_model") != old_hd.get("source", {}).get("model")):
        raise ValueError("Paired body dimensions, filenames or model lineage differ")
    contract = {key: old_hd["source"][key] for key in _MATERIAL_FIELDS}
    if any(captured.get("source", {}).get(key) != value for key, value in contract.items()):
        raise ValueError("Model, material recipes or coverage changed; portrait parent cannot be rebased")
    from orre_randomizer.hd_overlays import _complete_lugia_hd_capture
    _complete_lugia_hd_capture(captured)
    if (contract["pack"] != PACKS["xd"].key or contract["archives"] != [part.sha256 for part in PACKS["xd"].parts]):
        raise ValueError("Body materials are not the pinned source pack")
    common = _common(native, captured)
    if common.get("source_material_parent_sha256") != _sha(old_hd_payload):
        raise ValueError("Body captures were not staged against the installed material parent")
    capture_root = Path(capture_root).resolve() if capture_root is not None else hd_source.parent
    updates = _capture_assets(native_source, hd_source, native, captured, common, capture_root)
    result = copy.deepcopy(old_hd)
    result.update(capture=captured["capture"], conversion=captured["conversion"], common_capture=copy.deepcopy(common),
                  same_pose_alpha_byte_identical=True, review_only=captured["review_only"])
    for name in _HD:
        result["files"][name] = copy.deepcopy(captured["files"][name])
        result["files"][name]["materials"] = result["files"][name].pop("donor_source_records")
    native_payload = _json(native)
    result["paired_native"] = {"manifest_sha256": _sha(native_payload), "common_capture_sha256": _canonical_sha(common),
        "files": {name: {"sha256": native["files"][name]["sha256"],
                         "source_capture_sha256": native["files"][name]["source_capture_sha256"]} for name in _NATIVE}}
    result["retained_material_capture_evidence"] = {
        "previous_manifest_sha256": _sha(old_hd_payload),
        "material_contract_sha256": _canonical_sha(contract),
        "scope": "Only body pose/capture/placement changed; material recipes, coverage and model remain identical. Earlier material and head capture receipts remain evidence for those unchanged inputs.",
        "previous_capture": old_hd.get("capture"), "previous_conversion": old_hd.get("conversion")}
    hd_payload = _json(result)
    updates["models/fullbody-manifest.json"], updates["models/hd-fullbody-manifest.json"] = native_payload, hd_payload
    protected = {name: _read(pack_root / name) for name in updates}
    portrait_path = models / "portrait-variants.json"
    portrait_rebase = None
    if portrait_path.exists():
        from orre_randomizer.model_portraits import registered_portrait, portrait_filename
        payload = _read(portrait_path); portrait = json.loads(payload)
        expected = {portrait_filename(game, shiny, scale) for game in ("colosseum", "xd") for shiny in (False, True) for scale in (1, 4)}
        if (set(portrait.get("files", {})) != expected
                or portrait.get("source", {}).get("hd", {}).get("material_manifest_sha256") != _sha(old_hd_payload)):
            raise ValueError("Installed portrait registry has an unverified parent or incomplete files")
        for game in ("colosseum", "xd"):
            for shiny in (False, True):
                for scale in (1, 4):
                    name = portrait_filename(game, shiny, scale)
                    protected["models/" + name] = registered_portrait(models, game=game, shiny=shiny, scale=scale)
                    if protected["models/" + name] is None:
                        raise ValueError("Missing installed portrait")
        rebased = copy.deepcopy(portrait)
        rebased["source"]["hd"]["material_manifest_sha256"] = _sha(hd_payload)
        updates["models/portrait-variants.json"] = _json(rebased)
        protected["models/portrait-variants.json"] = payload
        portrait_rebase = {"previous_material_parent_sha256": _sha(old_hd_payload), "new_material_parent_sha256": _sha(hd_payload),
                           "protected_pngs": 8, "all_head_capture_fields_unchanged": True}
    for name in result["files"]:
        if name not in _HD:
            protected.setdefault("models/" + name, _read(models / name))
    provenance_payload = _read(pack_root / "provenance.json")
    provenance = json.loads(provenance_payload)
    for relative, payload in updates.items():
        provenance["files"][relative] = {"bytes": len(payload), "sha256": _sha(payload)}
    provenance["shadow_lugia_body_metadata"] = "models/fullbody-manifest.json"
    updates["provenance.json"] = _json(provenance)
    protected["provenance.json"] = provenance_payload
    for data in (native, result, provenance):
        _public(data)
    if portrait_rebase:
        _public(rebased)
    summary = {"native": native, "hd": result, "updated_files": list(updates),
        "portrait_parent_rebase": portrait_rebase, "review_only": native["review_only"] or captured["review_only"],
        "backup": None, "check_only": check_only}
    if not check_only:
        summary["backup"] = _publish_pair(pack_root, updates, protected, backup_dir)
    return summary


def register(source, pack_root, *, include_heads=False, check_only=False, native_source=None, capture_root=None, backup_dir=None):
    if native_source is not None:
        if include_heads:
            raise ValueError("Paired body registration cannot replace head assets")
        return register_paired(source, native_source, pack_root, capture_root=capture_root, backup_dir=backup_dir, check_only=check_only)
    if (Path(pack_root) / "models/portrait-variants.json").exists():
        raise ValueError("Registered portraits require paired native/HD registration and a verified parent rebase")
    return _legacy_register(source, pack_root, include_heads=include_heads, check_only=check_only)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--pack-root", type=Path, default=ROOT/"orre_randomizer/assets/game")
    parser.add_argument("--include-heads", action="store_true", help="Also register the audited GPU head crops")
    parser.add_argument("--native-source", type=Path, help="Register a matched native64/HD256 body pair")
    parser.add_argument("--capture-root", type=Path, help="Private four-raw/probe folder, defaultHD-source parent")
    parser.add_argument("--backup-dir", type=Path, help="New private backup directory used before publication")
    parser.add_argument("--check-only", action="store_true")
    arguments = parser.parse_args()
    result = register(arguments.source, arguments.pack_root, include_heads=arguments.include_heads,
                      native_source=arguments.native_source, capture_root=arguments.capture_root,
                      backup_dir=arguments.backup_dir, check_only=arguments.check_only)
    if arguments.native_source:
        print(json.dumps({"check_only": result["check_only"], "review_only": result["review_only"],
                          "updated_files": result["updated_files"], "portrait_parent_rebase": result["portrait_parent_rebase"],
                          "backup": result["backup"]}, indent=2))
    else:
        print("Validated" if arguments.check_only else "Registered", len(result["files"]), "HD model artwork assets.")


if __name__ == "__main__":
    main()
