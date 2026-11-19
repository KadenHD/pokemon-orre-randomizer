# Portable reproduction of the two approved VS scenes

This recipe takes user-supplied source data. It contains no DAT/PKX files,
texture-pack images, third-party addon, save or emulator state. It has no
dependency on a private `.blend` or a machine-specific path. Source assets are
opened read-only; only the chosen new work directory is written.

Required:

- Project Python environment with Pillow 13 and PySide6.
- Verified European XD revision 0 source ISO. Its exact `people_archive.fsys`
  hash and six model hashes are checked against `scene-recipe.json`.
- The two pinned installed texture packs (a standard pack root containing
  `Textures` is accepted, or the texture directory itself).
- Blender 5.2.3 and Blender HAL DAT Model Addon 3.1.0, supplied separately from
  https://github.com/StarsMmd/Blender-Addon-Gamecube-Models. The external addon
  declares GPL-3.0-or-later. No addon is installed or copied into the app.
- The source controller photo already included as
  `orre_randomizer/assets/app/controller.png` (SHA pinned in the recipe).
- The exact official Wikimedia GBA photo, 960 px PNG, SHA-256
  `67bfde0165b6daa1edc9b1a9efd36756fffdd584c8969b421682a7473d791789`:
  https://thumb.wikimedia.org/wikipedia/commons/thumb/0/0b/Nintendo-Game-Boy-Advance-Purple-FL.png/960px-Nintendo-Game-Boy-Advance-Purple-FL.png

Example (replace input paths; no paths are inferred from a personal profile):

```text
python reproduce_vs.py --project-root REPO --iso SOURCE.iso --xd-pack XD_PACK --colosseum-pack COLO_PACK --addon HSD_ADDON --blender BLENDER_EXECUTABLE --controller-photo CONTROLLER.png --gba-photo GBA.png --work NEW_WORK_DIR --prepare-only
```

This first pass uses CPU only. It verifies the archive/models/photos and exact
HD donors, and extracts six DATs plus the small required donor subset into the
work directory. No ISO copy or emulator process is created.

For the graphical pass, run the same command with `--render-prepared` replacing
`--prepare-only`, during an assigned QA GPU slot. Omitting both switches does
the complete operation into a new directory. Only background Blender children
are started, with factory startup, auto-execution disabled, isolated writable
paths, a 180-second ceiling per child and explicit termination on timeout.
No user Blender profile, startup file or application window is controlled.

The posing stage rebuilds the six genuine source meshes,
UVs, exact material donor links, camera and recorded FK poses from the source.
Subsequent renders contain only those actors and procedural backgrounds.
Hardware photographs are then alpha-composited with no tint or screen edits:
the controller uses scale 4/25; GBA uses scale 0.36 and a rigid rotation of
17 degrees. Added cable segments are recorded separately.

Final files are the four `*-authentic-review.png` RGBA images, each 864 x 472,
and the two `authentic-*-provenance.json` records. The approved published
artwork hashes are pinned in the bundled `menu-atlases/vs-scenes.json`. Render arithmetic
can vary across graphics drivers; this recipe records source/model/UV/pose
identity and does not promise byte-exact GPU output on every machine.

Credits stay distinct: controller photo by Evan-Amos and Alphathon under
CC BY-SA 3.0; GBA photo by Evan-Amos under the copyright holder's explicit
public-domain dedication. Changes are proportional reduction/rigid rotation
and composition, with separately declared cables. Game actors and upstream
HD materials retain their own source rights. Three GBA actors still use
native material maps; these outputs are not labeled wholly HD-material based.
