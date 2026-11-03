"""Compare full real archives using the reference and Rust codecs, byte for byte."""
import hashlib
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from colosseum_randomizer import native_codec
from colosseum_randomizer.engine.rebuild_iso import repack_fsys
from colosseum_randomizer.engine.shop_stones import ARCHIVE_NAMES


def main():
    if native_codec.library() is None:
        raise SystemExit("Build the Rust codec first")
    results = []
    for name in ("common.fsys", *ARCHIVE_NAMES):
        source = (ROOT / "game/files" / name).read_bytes()
        started = time.perf_counter()
        with patch.object(native_codec, "library", return_value=None):
            reference, _ = repack_fsys(source)
        python_seconds = time.perf_counter() - started
        started = time.perf_counter()
        accelerated, _ = repack_fsys(source)
        rust_seconds = time.perf_counter() - started
        if reference != accelerated:
            raise RuntimeError("Native archive bytes differ: " + name)
        results.append({"archive": name, "python_seconds": round(python_seconds, 4),
                        "rust_seconds": round(rust_seconds, 4),
                        "byte_identical": True, "sha256": hashlib.sha256(accelerated).hexdigest()})
    before = sum(row["python_seconds"] for row in results)
    after = sum(row["rust_seconds"] for row in results)
    report = {"archives": results, "python_total_seconds": round(before, 4),
              "rust_total_seconds": round(after, 4), "archive_speedup": round(before / after, 2)}
    (ROOT / "build/codec-benchmark.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
