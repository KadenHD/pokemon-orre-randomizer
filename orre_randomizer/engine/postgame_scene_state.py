"""A dedicated native save field for the optional Lugia mission.

Retail has 3593 flag definitions. Appending one two-bit field uses bits6414/6415
in the existing group3 save buffer, alongside its last retail boolean.
No retail descriptor, bit position, saved-data size or Shadow counter changes.
"""
from __future__ import annotations

import hashlib
import struct

from .analyze_game import FormatError, u32
from .rel_regions import region_for_rel

INTRO_STATE_FLAG = 3593
PHASE_UNAVAILABLE = 0
PHASE_AVAILABLE = 1
PHASE_INTRODUCED = 2
FLAG_GROUP = 3
FLAG_BIT = 6414
FLAG_WIDTH = 2
FLAG_BUFFER_WORDS = 384
FLAG_DESCRIPTOR = struct.pack(">BBBBHh", 0xC2, 0, 0, 0, FLAG_BIT, -1)
_DESCRIPTOR_HASHES = {
    "GC6P01": "6f1474f5f67483479a9fb09073b489b08c280a32adad8a43a56f9d3649e20dbd",
    "GC6E01": "6f1474f5f67483479a9fb09073b489b08c280a32adad8a43a56f9d3649e20dbd",
    "GC6J01": "0a3a729e87dc0b4b1bf8445bc5de69d8156f90d772f62b0eccb9dc120a202440",
}


def flag_table_extension(original: bytes, symbols: dict[int, dict]) -> tuple[tuple, dict]:
    """Qualify the original table before its existing REL extension clones it."""
    game_id = region_for_rel(original).game_id
    count = u32(original, symbols[55]["offset"])
    table = original[symbols[54]["offset"]:symbols[54]["offset"] + count * 8]
    digest = hashlib.sha256(table).hexdigest()
    if count != INTRO_STATE_FLAG or digest != _DESCRIPTOR_HASHES[game_id]:
        raise FormatError("unexpected native flag allocation for the Lugia introduction")
    used_bits = sum(min(32, max(1, table[i] & 63)) for i in range(0, len(table), 8)
                    if table[i] >> 6 == FLAG_GROUP)
    words_before, words_after = (used_bits + 31) // 32, (used_bits + FLAG_WIDTH + 31) // 32
    if used_bits != FLAG_BIT or words_before != words_after or words_after >= FLAG_BUFFER_WORDS:
        raise FormatError("Lugia introduction flag exceeds native saved flag storage")
    addition = ("scene_flags", 54, 55, 8, count, FLAG_DESCRIPTOR)
    return addition, {
        "flag_id": INTRO_STATE_FLAG, "group": FLAG_GROUP, "width": FLAG_WIDTH,
        "descriptor": FLAG_DESCRIPTOR.hex(), "original_descriptor_count": count,
        "descriptor_count": count + 1, "original_descriptors_sha256": digest,
        "original_descriptors_preserved": True, "bit_position": FLAG_BIT,
        "bits_before": used_bits, "bits_after": used_bits + FLAG_WIDTH,
        "used_words_before": words_before, "used_words_after": words_after,
        "allocated_words": FLAG_BUFFER_WORDS, "save_layout_unchanged": True,
        "capture_and_purification_flags_unchanged": True,
        "phases": {"unavailable": PHASE_UNAVAILABLE, "mail_received": PHASE_AVAILABLE,
                   "introduced": PHASE_INTRODUCED},
    }
