"""Per-encounter personality seeds for Spinda in the Orre games."""

from hashlib import sha256


SPINDA = 308  # Generation III internal species index.


def spinda_pid_seed(seed: str, encounter: str) -> int:
    digest = sha256(b"orre-spinda-pid-v1\0" + seed.encode("utf-8")
                    + b"\0" + encounter.encode("ascii")).digest()
    return int.from_bytes(digest[:4], "big")
