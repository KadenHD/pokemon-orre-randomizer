"""Read level-zero community textures without changing their source files."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from functools import lru_cache
import io
import os
from pathlib import Path
import re
import struct

from PIL import Image
from PySide6.QtGui import QImage


@dataclass(frozen=True)
class LoadedTexture:
    image: QImage
    metadata: dict


@lru_cache(maxsize=8)
def _texture_index(directory: str, modified_ns: int):
    index: dict[str, list[Path]] = {}
    with os.scandir(directory) as entries:
        for entry in entries:
            path = Path(entry.path)
            if path.suffix.lower() in {".png", ".dds"} and entry.is_file(follow_symlinks=False):
                index.setdefault(path.stem.lower(), []).append(path)
    return index


def resolve_texture(root: Path, logical_name: str) -> Path:
    """Resolve PNG/DDS and Dolphin's optional mipmap marker, deterministically."""
    if Path(logical_name).name != logical_name or not re.fullmatch(
            r"tex1_[a-zA-Z0-9_]+\.(?:png|dds)", logical_name, re.IGNORECASE):
        raise ValueError("Invalid texture name")
    stem = Path(logical_name).stem.lower()
    alternate = re.sub(r"^(tex1_\d+x\d+)_m_", r"\1_", stem)
    if alternate == stem:
        alternate = re.sub(r"^(tex1_\d+x\d+)_", r"\1_m_", stem)
    root = Path(root).resolve()
    index = _texture_index(str(root), root.stat().st_mtime_ns)
    for identity in (stem, alternate):
        matches = index.get(identity, ())
        if len(matches) > 1:
            raise ValueError("Ambiguous HD texture: " + logical_name)
        if matches:
            return matches[0]
    raise FileNotFoundError(logical_name)


def load_texture(path: Path, *, expected_native_size: tuple[int, int] | None = None,
                 max_scale: int = 8) -> LoadedTexture:
    """Decode PNG or BCn DDS, retaining physical-file provenance and scale."""
    path = Path(path)
    if path.is_symlink() or path.suffix.lower() not in {".png", ".dds"}:
        raise ValueError("Unsupported HD texture")
    with path.open("rb") as incoming:
        payload = incoming.read(64 * 1024**2 + 1)
    if len(payload) > 64 * 1024**2:
        raise ValueError("HD texture exceeds the file-size limit")
    mip_levels = 1
    if path.suffix.lower() == ".dds":
        if len(payload) < 128 or payload[:4] != b"DDS " or struct.unpack_from("<I", payload, 4)[0] != 124:
            raise ValueError("Invalid DDS header")
        mip_levels = max(1, struct.unpack_from("<I", payload, 28)[0])
    with Image.open(io.BytesIO(payload), formats=("PNG", "DDS")) as source:
        width, height = source.size
        if width < 1 or height < 1 or width > 8192 or height > 8192 or width * height > 8192**2:
            raise ValueError("HD texture exceeds the decoded-size limit")
        scale = None
        if expected_native_size is not None:
            native_width, native_height = expected_native_size
            if (native_width < 1 or native_height < 1 or width % native_width
                    or height % native_height or width // native_width != height // native_height
                    or not 1 <= width // native_width <= max_scale):
                raise ValueError("HD texture dimensions do not match its native reference")
            scale = width // native_width
        rgba = source.convert("RGBA")
        image = QImage(rgba.tobytes(), width, height, width * 4,
                       QImage.Format.Format_RGBA8888).copy()
        image_format = source.format
    if image.isNull():
        raise ValueError("Cannot decode HD texture")
    return LoadedTexture(image, {"physical_file": path.name,
        "sha256": hashlib.sha256(payload).hexdigest(), "width": width, "height": height,
        "source_scale": scale, "format": image_format, "mip_levels": mip_levels})
