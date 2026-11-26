"""Register a reviewed complete Deoxys native/HD set with backups and rollback.

The input directory contains the 24 approved PNGs, six unmodified XD PKXs and
their reviewed deoxys-assets.json. This tool does not generate a missing model,
upscale native pixels into HD art or grant visual approval to unreviewed captures.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import struct
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from orre_randomizer.deoxys_assets import VERSION, asset_manifest, artwork_png, xd_models
from orre_randomizer.deoxys_resources import FORMS, FORM_MEMBERS
from orre_randomizer.hd_extra_portrait_catalog import MODEL_IDENTITIES
from orre_randomizer.engine.dna_artwork import outline_dna_body
from orre_randomizer.artwork import _png_pixels
from scripts.release_media import game_asset_name_allowed

CATALOG = 'deoxys-assets.json'
PREFIX = 'models/deoxys/'
MAX_METADATA = 1024 * 1024
SHA = re.compile(r'[0-9a-f]{64}\Z')


def _digest(payload):
    return hashlib.sha256(payload).hexdigest()


def _directory(path, *, exists=True):
    path = Path(path).absolute()
    for part in (path, *path.parents):
        if part.is_symlink() or part.is_junction():
            raise ValueError('Linked registration paths are refused')
    if exists and not path.is_dir():
        raise ValueError('Registration directory is missing')
    return path.resolve()


def _read(path, limit):
    if path.is_symlink() or path.is_junction() or not path.is_file() or not 0 < path.stat().st_size <= limit:
        raise ValueError('Invalid registration input file')
    return path.read_bytes()


def _public_metadata(payload):
    text = payload.decode('utf-8')
    if (re.search(r'[A-Za-z]:[\\/]', text) or
            any(key in text for key in ('"private_pid"', '"source_card"', '"profile_path"', '"source_iso_path"')) or
            re.search(r'"[^"\n]*":\s*"/(?:Users|home|tmp)/', text)):
        raise ValueError('Private capture paths or process details cannot enter the registry')


def checked_inputs(source, pack_root):
    """Resolve and validate every input before creating a publication directory."""
    source, pack_root = _directory(source), _directory(pack_root)
    raw = _read(source / CATALOG, MAX_METADATA)
    _public_metadata(raw)
    _, manifest = asset_manifest(source)
    if manifest.get('art_approved_by_root') is not True:
        raise ValueError('Deoxys artwork requires completed visual review')
    dependencies = manifest.get('source_catalogs')
    if (not isinstance(dependencies, dict) or set(dependencies) != {
            'models/extra-portraits/extra-portraits.json', 'form-materials/catalog.json'}):
        raise ValueError('Missing original form-artwork and material provenance')
    for relative, digest in dependencies.items():
        if (not SHA.fullmatch(digest or '') or PurePosixPath(relative).is_absolute()
                or PureWindowsPath(relative).drive or '..' in PurePosixPath(relative).parts):
            raise ValueError('Invalid Deoxys source catalog identity')
        if _digest(_read(pack_root / relative, 16 * MAX_METADATA)) != digest:
            raise ValueError('Deoxys source catalog changed since artwork review')
    poses = manifest.get('pose_recipes')
    if not isinstance(poses, dict) or set(poses) != {f'{form}/{role}' for form in FORMS for role in ('head', 'body')}:
        raise ValueError('Deoxys capture pose recipes are incomplete')
    for pose in poses.values():
        joints = pose.get('joints_by_original_dat_offset')
        if (not isinstance(joints, dict) or len(joints) != pose.get('matrix_count')
                or not 1 <= len(joints) <= 512):
            raise ValueError('Invalid Deoxys source joint recipe')
        rows = []
        for key, joint in sorted(joints.items(), key=lambda row: int(row[0], 16)):
            if not re.fullmatch(r'0x[0-9a-f]+', key) or not 0 <= int(key, 16) < 0x1000000:
                raise ValueError('A Deoxys pose contains a runtime rather than source descriptor')
            matrix, srt = bytes.fromhex(joint['matrix']), bytes.fromhex(joint['srt'])
            if (len(matrix) != 48 or len(srt) != 40
                    or any(not abs(value) < 100000 for value in struct.unpack('>22f', srt + matrix))):
                raise ValueError('Invalid Deoxys captured joint transform')
            rows.append(matrix)
        if _digest(b''.join(rows)) != pose.get('pose_signature_sha256'):
            raise ValueError('Deoxys frozen pose identity changed')
    # The loader checks all six against the original XD byte identities.
    xd_models(source)
    files = {}
    for form in FORMS:
        for shiny in (False, True):
            variant = 'shiny' if shiny else 'normal'
            for role in ('head', 'body'):
                for hd in (False, True):
                    name = f'{role}-{form}-{variant}-{"hd" if hd else "native"}.png'
                    payload = artwork_png(form, shiny=shiny, hd=hd, role=role, directory=source)
                    row = manifest['files'][name]
                    capture = row.get('capture')
                    if (not isinstance(capture, dict) or capture.get('source_dimensions') != [1024, 1024]
                            or capture.get('native_render_target') != [256, 256]
                            or capture.get('internal_resolution') != 4
                            or capture.get('hires_textures') is not hd
                            or capture.get('three_identical_gpu_frames') is not True
                            or capture.get('normal_shiny_same_pose_and_crop') is not True
                            or any(not SHA.fullmatch(capture.get(key, '')) for key in (
                                'source_capture_sha256', 'source_model_sha256', 'source_dat_sha256',
                                'pose_signature_sha256', 'renderer_sha256'))):
                        raise ValueError('Incomplete Deoxys GPU capture provenance')
                    model = manifest['files'][f'xd-{form}-{variant}.pkx']
                    identity = MODEL_IDENTITIES[FORM_MEMBERS[form]][shiny]
                    if (capture['source_model_sha256'] != model['sha256']
                            or capture['source_dat_sha256'] != identity['dat_sha256']
                            or capture['pose_signature_sha256'] != poses[f'{form}/{role}']['pose_signature_sha256']):
                        raise ValueError('Deoxys artwork and original model identities differ')
                    if role == 'body':
                        side = 256 if hd else 64
                        outlined = outline_dna_body(_png_pixels(payload, (side, side)), side)
                        if any(outlined[(y * side + x) * 4 + 3] for y in range(side) for x in range(side)
                               if x in (0, side - 1) or y in (0, side - 1)):
                            raise ValueError('Deoxys DNA contour would clip the frame')
                    files[name] = payload
            name = f'xd-{form}-{variant}.pkx'
            files[name] = _read(source / name, 8 * MAX_METADATA)
    if set(files) != set(manifest['files']) or len(files) != 30:
        raise ValueError('The complete Deoxys native/HD set is required')
    for relative in [PREFIX + name for name in files] + [PREFIX + CATALOG]:
        if not game_asset_name_allowed(relative):
            raise ValueError('A Deoxys file is absent from the release allowlist')
    files[CATALOG] = raw
    return pack_root, manifest, files


def _atomic_write(path, payload):
    temporary = path.with_name('.' + path.name + '-' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('xb') as stream:
            stream.write(payload)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def register(source, pack_root, *, check_only=False, backup_root=None):
    pack_root, manifest, files = checked_inputs(source, pack_root)
    provenance_path = pack_root / 'provenance.json'
    previous_bytes = _read(provenance_path, 16 * MAX_METADATA)
    previous = json.loads(previous_bytes)
    if not isinstance(previous.get('files'), dict):
        raise ValueError('The interface pack provenance is invalid')
    target = pack_root / 'models/deoxys'
    if target.is_symlink() or target.is_junction():
        raise ValueError('Linked registration targets are refused')
    if target.exists():
        _directory(target)
        if any(not path.is_file() or path.is_symlink() or path.is_junction()
               or path.name not in files for path in target.iterdir()):
            raise ValueError('Unrecognized existing files in the Deoxys asset directory')
    updated = copy.deepcopy(previous)
    for name, payload in files.items():
        updated['files'][PREFIX + name] = {'bytes': len(payload), 'sha256': _digest(payload)}
    updated['deoxys_assets_metadata'] = PREFIX + CATALOG
    for key, record in previous['files'].items():
        if not key.startswith(PREFIX):
            assert updated['files'][key] == record
    encoded = (json.dumps(updated, indent=2, ensure_ascii=False) + '\n').encode('utf-8')
    result = {'version': VERSION, 'files': 30, 'pngs': 24, 'original_xd_models': 6,
              'catalog_sha256': _digest(files[CATALOG]), 'check_only': check_only,
              'existing_unrelated_records_preserved': True}
    if check_only:
        return result
    if (previous_bytes == encoded and target.is_dir() and
            all((target / name).read_bytes() == payload for name, payload in files.items())):
        return {**result, 'already_registered': True}
    backup_parent = _directory(backup_root or ROOT / 'build/deoxys-asset-registration', exists=False)
    if backup_parent == pack_root or backup_parent.is_relative_to(pack_root):
        raise ValueError('Registration backups must stay outside the interface pack')
    backup_parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    backup = backup_parent / stamp
    backup.mkdir()
    staged = backup / 'staged'
    staged.mkdir()
    for name, payload in files.items():
        (staged / name).write_bytes(payload)
    (backup / 'provenance-before.json').write_bytes(previous_bytes)
    old_hashes = {p.name: _digest(p.read_bytes()) for p in target.iterdir()} if target.exists() else {}
    receipt = {**result, 'status': 'prepared', 'before_provenance_sha256': _digest(previous_bytes),
               'previous_asset_hashes': old_hashes, 'new_asset_hashes': {n: _digest(p) for n, p in files.items()},
               'target': 'models/deoxys', 'target_and_backup_paths_checked': True}
    (backup / 'registration.json').write_text(json.dumps(receipt, indent=2), 'utf-8')
    # A concurrent curator must not lose a provenance update or an asset edit.
    if provenance_path.read_bytes() != previous_bytes or (target.exists() and
            {p.name: _digest(p.read_bytes()) for p in target.iterdir()} != old_hashes):
        raise ValueError('The interface pack changed during registration')
    target.parent.mkdir(parents=True, exist_ok=True)
    assert target.absolute() == pack_root / 'models/deoxys'
    assert target.parent.resolve().is_relative_to(pack_root) and backup.resolve().is_relative_to(backup_parent)
    moved_previous = installed = False
    try:
        if target.exists():
            os.replace(target, backup / 'previous-assets')
            moved_previous = True
        os.replace(staged, target)
        installed = True
        _atomic_write(provenance_path, encoded)
        # Verify the published bytes using the same runtime loader as the app.
        checked_inputs(target, pack_root)
        assert provenance_path.read_bytes() == encoded
    except BaseException:
        if installed and target.exists():
            os.replace(target, backup / 'rejected-new-assets')
        if moved_previous:
            os.replace(backup / 'previous-assets', target)
        if provenance_path.read_bytes() != previous_bytes:
            _atomic_write(provenance_path, previous_bytes)
        receipt['status'] = 'rolled-back'
        (backup / 'registration.json').write_text(json.dumps(receipt, indent=2), 'utf-8')
        raise
    receipt['status'] = 'registered'
    receipt['after_provenance_sha256'] = _digest(encoded)
    (backup / 'registration.json').write_text(json.dumps(receipt, indent=2), 'utf-8')
    return {**result, 'backup_directory': str(backup), 'registered': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path, help='Reviewed complete PNG/PKX directory and its deoxys-assets.json')
    parser.add_argument('--pack-root', type=Path, default=ROOT / 'orre_randomizer/assets/game')
    parser.add_argument('--backup-root', type=Path)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    print(json.dumps(register(args.source, args.pack_root, check_only=args.check_only,
                              backup_root=args.backup_root), indent=2))


if __name__ == '__main__':
    main()
