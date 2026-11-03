"""Optional local Rust codec; the standard-library reference remains available."""
import ctypes
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path
import struct
import sys


class CodecCancelled(Exception):
    """Compression stopped cooperatively before publishing its result."""


_cancel_event = ContextVar("colosseum_codec_cancel_event", default=None)
_cancel_callback_type = ctypes.CFUNCTYPE(ctypes.c_int)


@contextmanager
def cancellation_scope(cancel):
    """Bind cancellation to this task/thread without changing codec callers."""
    token = _cancel_event.set(cancel)
    try:
        compression_checkpoint()
        yield
    finally:
        _cancel_event.reset(token)


def compression_checkpoint():
    cancel = _cancel_event.get()
    if cancel is not None and cancel.is_set():
        raise CodecCancelled()


@lru_cache(maxsize=1)
def library():
    filename = "colosseum_lzss.dll" if sys.platform == "win32" else (
        "libcolosseum_lzss.dylib" if sys.platform == "darwin" else "libcolosseum_lzss.so")
    path = Path(__file__).resolve().parent / "_native" / filename
    if not path.is_file():
        return None
    codec = ctypes.CDLL(str(path))
    codec.colosseum_codec_version.restype = ctypes.c_uint32
    if codec.colosseum_codec_version() != 1:
        raise RuntimeError("Unsupported native codec ABI")
    for name in ("colosseum_compress", "colosseum_decompress"):
        function = getattr(codec, name)
        function.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t]
        function.restype = ctypes.c_ssize_t
    if hasattr(codec, "colosseum_compress_cancellable"):
        codec.colosseum_compress_cancellable.argtypes = [ctypes.c_char_p, ctypes.c_size_t,
            ctypes.c_void_p, ctypes.c_size_t, _cancel_callback_type]
        codec.colosseum_compress_cancellable.restype = ctypes.c_ssize_t
    return codec


def compress(data: bytes) -> bytes | None:
    compression_checkpoint()
    cancel = _cancel_event.get()
    codec = library()
    if codec is None:
        return None
    # Old DLLs still support the reference encoder. Use that cancellable path
    # rather than entering an uninterruptible old native call for a live task.
    if cancel is not None and not hasattr(codec, "colosseum_compress_cancellable"):
        return None
    capacity = 16 + len(data) + (len(data) + 7) // 8
    output = ctypes.create_string_buffer(capacity)
    if cancel is None:
        size = codec.colosseum_compress(data, len(data), output, capacity)
    else:
        callback = _cancel_callback_type(lambda: int(cancel.is_set()))
        size = codec.colosseum_compress_cancellable(data, len(data), output, capacity, callback)
        if size == -2:
            raise CodecCancelled()
    if size < 16 or size > capacity:
        raise ValueError("Native LZSS encoder rejected its output buffer")
    compression_checkpoint()
    return output.raw[:size]


def decompress(data: bytes, max_output: int) -> bytes | None:
    codec = library()
    if codec is None:
        return None
    if len(data) < 16 or data[:4] != b"LZSS":
        raise ValueError("Invalid LZSS header")
    expected, stored = struct.unpack_from(">II", data, 4)
    if expected > max_output or stored != len(data):
        raise ValueError("Invalid LZSS sizes or output bound")
    output = ctypes.create_string_buffer(max(expected, 1))
    size = codec.colosseum_decompress(data, len(data), output, expected)
    if size != expected:
        raise ValueError("Invalid or truncated LZSS stream")
    return output.raw[:size]


def backend() -> str:
    return "rust-lzss-v1" if library() is not None else "python-lzss-v1"
