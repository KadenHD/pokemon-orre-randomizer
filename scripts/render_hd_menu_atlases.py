"""Reproduce registered menu artwork from explicit installed HD pack roots.

Install the application's regular runtime dependencies and run this script with
the release Python/Qt versions recorded by the emitted receipt. Supply your own
installed, pinned pack directories; no ROM, save, emulator, system font, hidden
native PNG, or network request is needed. Captured font outlines and analytic
geometry are distributed as reviewed recipes in assets/game/menu-atlases.

The catalogue records each exact native Dolphin key, original member/RGBA hash,
native canvas and caption/geometry bounds. Image-backed recipes additionally pin
the genuine x4 donor's SHA and dimensions. Analytic-only recipes declare their
flat palette, ellipses/rectangles and boolean construction; they do not enlarge a
native bitmap. To revise typography, build_hd_menu_vectors.py captures outlines
from explicit pinned fonts; update the catalogue's vectors_sha256 and provenance
after content review. Never substitute a guessed language caption or unknown key.

Example: python scripts/render_hd_menu_atlases.py --game-id GXXP01
  --xd-pack /path/to/xd-1.0 --output /new/overlays --receipt /new/report.json
Outputs retain exact Dolphin names. Existing different pixels are rejected.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from PySide6.QtCore import qVersion
    from PySide6.QtGui import QGuiApplication
    from orre_randomizer.hd_hud import prepare_hud_overlays
    from orre_randomizer.hd_menu_catalog import SUPPORTED
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-id", required=True, choices=sorted(SUPPORTED))
    parser.add_argument("--colosseum-pack", type=Path)
    parser.add_argument("--xd-pack", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    if args.receipt.exists() or args.receipt.is_symlink():
        parser.error("Use a new receipt path; earlier validation evidence is preserved")
    app = QGuiApplication.instance() or QGuiApplication([])
    roots = {key: value for key, value in (("colosseum", args.colosseum_pack),
                                         ("xd", args.xd_pack)) if value is not None}
    report = prepare_hud_overlays(args.game_id, roots, args.output)
    # Omit local input paths from the portable artwork provenance.
    report["reproduction_environment"] = {"python": platform.python_version(), "qt": qVersion()}
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    with args.receipt.open("x", encoding="utf8") as output:
        json.dump(report, output, ensure_ascii=False, indent=2)
        output.write("\n")
    print(f"Reproduced {len(report['files'])} menu/HUD overlays; runtime qualification remains separate")


if __name__ == "__main__":
    main()
