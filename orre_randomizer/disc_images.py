"""In-process, lossless GameCube image conversion; no external executables."""
from __future__ import annotations

import ctypes
from functools import lru_cache
from pathlib import Path
import sys
import time

FORMATS = ("ISO", "GCM", "RVZ")
SUFFIXES = tuple("." + value.lower() for value in FORMATS)
RAW_SUFFIXES = (".iso", ".gcm")
BACKEND = "nod-2.0.0-alpha.11-481f50d7"
_callback_type = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_uint64, ctypes.c_uint64)


class DiscError(Exception):
    pass


class DiscCancelled(DiscError):
    pass


def library_path():
    filename = "orre_disc.dll" if sys.platform == "win32" else (
        "liborre_disc.dylib" if sys.platform == "darwin" else "liborre_disc.so")
    return Path(__file__).resolve().parent / "_native" / filename


@lru_cache(maxsize=1)
def library():
    """CDLL releases the GIL while the worker calls the native converter."""
    try:
        codec = ctypes.CDLL(str(library_path()))
        codec.orre_disc_abi_version.restype = ctypes.c_uint32
        if codec.orre_disc_abi_version() != 1:
            raise DiscError("Unsupported disc converter ABI")
        codec.orre_disc_convert.argtypes = [ctypes.c_char_p, ctypes.c_char_p,
            ctypes.c_int, _callback_type, ctypes.c_void_p, ctypes.c_size_t]
        codec.orre_disc_convert.restype = ctypes.c_int
        return codec
    except (OSError, AttributeError) as error:
        raise DiscError("The integrated disc converter is missing or incompatible") from error


def convert(source: Path, destination: Path, cancel, progress=None):
    """Create one new output, cooperatively cancelling and deleting partial data."""
    source, destination = Path(source).resolve(), Path(destination).absolute()
    if source.suffix.lower() not in SUFFIXES or destination.suffix.lower() not in SUFFIXES:
        raise DiscError("Unsupported disc format")
    callback_errors = []
    last_progress = 0.0

    def update(done, total):
        nonlocal last_progress
        try:
            if cancel.is_set():
                return 1
            now = time.monotonic()
            if progress and (done == total or now - last_progress >= 0.05):
                progress(done, total)
                last_progress = now
            return int(cancel.is_set())
        except BaseException as error:
            callback_errors.append(error)
            return 1

    callback = _callback_type(update)
    error = ctypes.create_string_buffer(4096)
    result = library().orre_disc_convert(str(source).encode("utf-8"),
        str(destination).encode("utf-8"), int(destination.suffix.lower() == ".rvz"),
        callback, error, len(error))
    if callback_errors:
        raise callback_errors[0]
    if result == 1:
        raise DiscCancelled("Disc conversion cancelled")
    if result:
        raise DiscError(error.value.decode("utf-8", errors="replace") or "Disc conversion failed")
