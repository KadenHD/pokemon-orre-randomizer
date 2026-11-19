# Portable Bingo portrait reproduction

This reproduces the eleven approved model compositions from user-supplied game
and texture-pack data. It contains no PKX/DAT, ROM, emulator state, save or
third-party addon. It does not depend on a private `.blend` or personal profile.
The included small layers are newly authored procedural backgrounds and vector
frames. They are pinned by SHA, separately from the real Pokémon materials.

Required inputs:

- This project, Python3.12.2, Pillow13.0.0 and PySide6 6.11.2.
- European XD revision0 ISO, opened read-only. All eleven source archive,
  PKX and DAT hashes are verified; no ISO copy is made.
- Installed XD1.0 texture pack by mikeyX, either its standard root containing
  `Textures`, or that texture directory. Exact source PNG and decoded PNG
  hashes are checked for112 inventoried material descriptor pairs. The normal
  clips actually request103 unique pairs, all true x4, with zero missing donors.
- Blender5.2.3 and Blender HAL DAT Model Addon3.1.0, provided separately from
  https://github.com/StarsMmd/Blender-Addon-Gamecube-Models. All addon Python
  sources are SHA-checked before any graphical process. The addon declares
  GPL-3.0-or-later and is not included or installed by this tool.

CPU-only preparation, the default:

```text
python reproduce_bingo.py --project-root REPO --iso SOURCE.iso --xd-pack XD_PACK --addon HSD_ADDON --work NEW_WORK_DIR
```

This creates only the eleven small source PKX copies, exact donor subset,
authored layers, recipe and `prepared-inputs.json`. Existing output directories
are refused. This real CPU preflight passed on the approved sources.

During an assigned graphical QA slot, explicitly render the prepared inputs:

```text
python reproduce_bingo.py --project-root REPO --iso SOURCE.iso --xd-pack XD_PACK --addon HSD_ADDON --blender BLENDER_EXECUTABLE --work PREPARED_WORK_DIR --render-prepared
```

Alternatively add `--render --blender BLENDER_EXECUTABLE` to the first command.
Only one owned background Blender is started, with factory startup, automatic
script loading disabled, isolated writable paths and a180-second ceiling.
Timeout kills and waits for that owned child. No Dolphin or application window
is controlled, no audio is rendered, and no personal profile is modified.

The recipe imports native Idle clips, fixes the recorded frame (15 for
Sudowoodo,0 for the other ten), camera and lighting, renders actual90-square
source-material images, then switches only image bindings to the pinned x4
donors and renders360-square images. Pose matrices and the multiset of visible
world geometry/UV bytes must match the approved receipts exactly. Material
changes must preserve them. Hidden collision helpers are excluded because
they do not contribute to either image. Arbitrary Blender object numbering
does not participate in the comparison.

Final output is the3960x360 replacement PNG under its original990x90 texture
key. Reconstructed procedural backgrounds are composited behind the actors,
then the analytic clipping aperture and frame are applied. No native bitmap
or Pokémon silhouette is enlarged to create HD art. Fully transparent RGB is
zeroed. GPU PNG bytes can differ between graphics drivers, so reproduction
checks geometric/source identity rather than promising identical raster bytes.

The reviewed PNGs came from the tested paired source-import builder. The
portable fresh-import graphical command is supplied for reproduction and was
not rerun after the final artwork freeze; its CPU preflight is recorded.
`frame-authoring-reference.py` and `ambience-authoring-reference.py` preserve
the original CPU artwork study, including its project-relative study inputs.
They are reference sources, not dependencies of this portable command.

Limits stay explicit: original Bingo CGI cameras, arena identities and lighting
were not recovered. Camera composition was calibrated to the original guides.
Blender fixed-function shading and gloss differ from the original CGI. Missing
vertex-color channels use white, and zero-area source primitives are omitted.
The backgrounds are newly composed procedural art, not source scene donors.
The original90-square Bingo strip remains a guide, separate from these new
source-material model renders. Root approved the eleven new compositions with
these limits; a Dolphin menu witness is a separate runtime validation.

Game assets retain their original rights. The real HD material pack is by
mikeyX: https://forums.dolphin-emu.org/Thread-pokemon-xg-xd-hd-texture-pack-v1-0
and the original author archive is pinned in `bingo-recipe.json`. No global
redistribution license is inferred for the source ROM or the upstream pack.
