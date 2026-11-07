"""Create a fresh Dolphin test profile, copying saves without modifying originals."""

import argparse
import json
import os
from pathlib import Path
import shutil

from .analyze_game import write_json
from .survey_assets import sha256


def prepare(output: Path, source_profile: Path, *, copy_saves: bool = True) -> dict:
    output, source_profile = output.resolve(), source_profile.resolve()
    if output.exists():
        raise FileExistsError("test profile already exists; choose a fresh output path")
    if source_profile == output or source_profile in output.parents or output in source_profile.parents:
        raise ValueError("test and source profiles must be disjoint")
    originals = []
    for directory in ("Config", "GC", "GameSettings", "StateSaves"):
        selected = source_profile / directory
        if selected.exists():
            originals.extend({"path": str(p), "size": p.stat().st_size, "sha256": sha256(p)}
                             for p in sorted(selected.rglob("*")) if p.is_file())
    (output / "Config").mkdir(parents=True)
    (output / "GC").mkdir()
    copied = []
    for relative in ("GC/MemoryCardA.EUR.raw", "GC/SRAM.raw"):
        source = source_profile / relative
        if copy_saves and source.is_file():
            target = output / relative
            shutil.copyfile(source, target)
            copied.append({"source": str(source), "copy": str(target), "sha256_before": sha256(source)})
    card_config = f"MemcardAPath = {(output / 'GC/MemoryCardA.EUR.raw').as_posix()}\n"
    # A separate profile has no inherited cheats, game patches or controllers.
    dolphin_ini = ("[Core]\nGFXBackend = D3D12\nEnableCheats = False\nSelectedLanguage = 2\n"
                   "SIDevice0 = 6\nSIDevice1 = 0\nSIDevice2 = 0\nSIDevice3 = 0\n"
                   "SkipIPL = True\nSlotA = 1\nSlotB = 255\n" + card_config +
                   "[Display]\nFullscreen = False\nRenderToMain = True\n"
                   "[Interface]\nConfirmStop = False\n"
                   "[DSP]\nVolume = 0\nMute = True\n"
                   "[Analytics]\nPermissionAsked = True\n")
    (output / "Config/Dolphin.ini").write_text(dolphin_ini, encoding="utf-8")
    pad_ini = ("[GCPad1]\nDevice = DInput/0/Keyboard Mouse\nButtons/A = X\nButtons/B = Z\n"
               "Buttons/X = C\nButtons/Y = V\nButtons/Z = F\nButtons/Start = RETURN\n"
               "Main Stick/Up = W\nMain Stick/Down = S\nMain Stick/Left = A\nMain Stick/Right = D\n"
               "D-Pad/Up = UP\nD-Pad/Down = DOWN\nD-Pad/Left = LEFT\nD-Pad/Right = RIGHT\n"
               "Triggers/L = Q\nTriggers/R = E\n")
    (output / "Config/GCPadNew.ini").write_text(pad_ini, encoding="utf-8")
    result = {"source_profile": str(source_profile), "isolated_profile": str(output),
              "source_originals": originals, "copied_save_files": copied,
              "save_mode": "copied originals" if copy_saves else "fresh empty card, no originals imported",
              "cheats_enabled": False, "language": "French",
              "keyboard": {"A": "X", "B": "Z", "Start": "Return", "stick": "WASD", "dpad": "arrows"}}
    write_json(output.parent / (output.name + "-preparation.json"), result)
    print(json.dumps({k: v for k, v in result.items() if k != "source_originals"}, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("build/roundtrip/dolphin-user"))
    parser.add_argument("--source-profile", type=Path, default=Path(os.environ["APPDATA"]) / "Dolphin Emulator")
    parser.add_argument("--empty-card", action="store_true", help="fresh story game without importing original saves/SRAM")
    args = parser.parse_args()
    prepare(args.output, args.source_profile, copy_saves=not args.empty_card)
