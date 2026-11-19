# Reproducing the additional form portraits

These portraits render the original form meshes with HD materials. The native
42×84 portraits are identity and framing references; their RGB pixels are never
enlarged into an HD portrait. Runtime use does not alter a ROM or save.

Install the offline tool dependencies with `pip install -e ".[artwork]"`.
The input games and HD packs must be supplied separately. No private QA memory
card, savestate, Windows profile path or bundled disc image is required.

The checked release environment is Python 3.12.2, Pillow 13.0.0 and NumPy 2.2.6.
The original material inputs were generated with Pillow 11.2.1. Explicit
horizontal-then-vertical UV-mask filtering reproduces their exact pixels under 13;
automatic pass selection on tall images otherwise changes intermediate rounding.
All 43 authored materials, 27 normalized exact-pack donors and 9 atlas compositions
were checked for identical SHA-256 and RGBA across both environments. The tools
record their actual versions in receipts. FreeType 2.14.3 is used only for review
board labels; material and portrait pixels do not use text rendering.

## 1. Rebuild and check the materials

Run `scripts/build_extra_portrait_materials.py --help`. Pass the two original
game ISO paths, the two installed pinned pack directories, and an empty output
directory. It extracts only the selected model members and verifies the PKX,
DAT and donor-file hashes in `hd_extra_portrait_catalog.py`.

The form sources are:

| Portrait member | Original game | Normal model archive | Shiny model archive |
| --- | --- | --- | --- |
| face385f, Sunny | Colosseum | pkx_powalen_f.fsys | Same Gen3 weather mesh and palette |
| face385w, Rainy | Colosseum | pkx_powalen_w.fsys | Same Gen3 weather mesh and palette |
| face385i, Snowy | Colosseum | pkx_powalen_i.fsys | Same Gen3 weather mesh and palette |
| face410atk | XD | pkx_deoxys_atk.fsys | pkx_deoxys_atk_c.fsys |
| face410def | XD | pkx_deoxys_def.fsys | pkx_deoxys_def_c.fsys |
| face410sp | XD | pkx_deoxys_sp.fsys | pkx_deoxys_sp_c.fsys |

Sunny and Defense have exact independent pack materials. The other forms also
use the deterministic authored material recipes shipped in
`scripts/extra_portrait_materials/`. The authoring receipt records the source
pack, exact physical file hash, target key, construction and final PNG hash.
Constant colours, vector UV boundaries and analytic lighting are described as
such; they are not claimed to add painted source detail. The optional NumPy
dependency belongs to authoring tools, not the application runtime.

## 2. Reach an original model viewer without the private QA card

Use an isolated Dolphin user directory and a copy of a personally supplied
Colosseum save with access to the native laboratory Pokémon analyzer. Any save
with an analyzable Lugia works after the resource choice below is matched. The
species name/PID may still say Lugia: the viewer resource is an explicit QA
substitution, not evidence of gameplay form selection.

Make one disposable copy of a Colosseum disc image. Never use the original ISO
as an output, and do not hardlink the writable copy. Extract its native Lugia
PKX as the Colosseum animation-header template. Extract the desired form member
from the original source archive by its catalogued PKX SHA-256. For an XD model,
`engine.postgame_lugia_model.convert_xd_model(form_pkx, lugia_template)` ports
the outer animation header while preserving the complete form DAT. A Colosseum
weather model can be used directly.

In **the disposable copy only**, replace the Lugia resource which the chosen
save actually displays. Ordinary, never-shadow Lugia uses the original
`lugia` member of `pkx_lugia.fsys`. A generated QA disc may instead route the
normal/shiny custom resources `0x7df31e00` / `0x7df41e00`; those are viewer aliases,
not dependencies of the released portraits. Use `_disc_files`, `_raw_member`
and `parse_fsys` to locate exact members, `repack_fsys` to replace them, and
`update_staged_disc(copy, read_executable(copy), replacements)` to preserve the
copy's existing executable. Do not copy a stock DOL over a generated disc.

Cold boot this copy with native textures, internal resolution 1, no texture/video
dumps, and no prior movie or savestate. Open the native analyzer normally. Verify
that the loaded DAT matches the requested catalogued form before saving a fresh
local state. No historical Lugia state qualifies a different form.

## 3. Qualify the model and replay the declared pose

The public registry stores the original PKX/DAT identities, complete material
inventory, joint count, frozen matrix hash and declared camera recipe. Its
`pose_recipes` contain matrices and SRT bytes indexed by **original DAT source
descriptor offsets**, never process addresses. Normal and shiny use identical
matrices, camera and crop; they retain their separate original materials.

Find the actual loaded model through the native analyzer/resource manager or
Dolphin debugger symbols. For the PAL Colosseum viewer used by these captures,
the analyzer pointer is at `0x804c7ac0`, its sequence at `+0x168`, the active model
ID at sequence `+8`, resource-table pointer at `0x804c810c` and count at
`0x804c8110`. The HSD wrapper resource has type `0x4e20` and the active model ID;
its data pointer is at `+0x20`. These addresses describe this revision only.
Re-qualify them for another executable; do not transpose them to XD or another
region. The PKX's DAT data starts after the PKX header and DAT header.

For exact identity, copy the complete live DAT, subtract its runtime data base
from every pointer listed in its relocation table, and normalize any relocated
export/import symbol offsets. The normalized DAT SHA must equal the original
catalogue. Verify the whole source JObj parent/child/sibling tree and all expected
descriptors before accepting a pose or writing transforms.

Replay each recorded matrix on the matching live JObj, set `USER_DEF_MTX`
(`0x00800000`) and clear `MTX_DIRTY` (`0x40`). In the qualified HSD layout, the
source descriptor pointer is at `+0x84`, SRT at `+0x1c` (40 bytes), flags at
`+0x14` and the 3×4 matrix at `+0x44` (48 bytes). Re-read the complete matrix set
after rendering and verify its SHA in ascending source-descriptor order.
Control-wrapper animation/quaternion modes must not be enabled.

If a debugger or external helper is used, it must operate only on the exact
instance it started, with PID/creation-time/executable identity checks. A brief
atomic suspension must always resume in `finally`. No game card, ISO or unrelated
Dolphin process is a matrix-write target.

The native analyzer camera is kept unchanged. The receipts explicitly state
`cobj_readback_captured: false`: this is a declared scene/camera recipe, not an
invented CObj memory capture. The retained joint matrices and visual framing
review fix the pose. Do not add an arbitrary image flip, non-uniform stretch or
per-variant fit to compensate for a different pose.

## 4. Capture actual HD pixels

Reload the newly qualified state into an isolated muted renderer with the same
disposable disc. Enable only that form's complete material set under its exact
native Dolphin texture names. Decode the pinned DDS sources through `hd_images`
when PNG normalization is needed; authored targets come from step 1. Verify all
file hashes against the material receipt before boot.

Use these Dolphin settings in the QA user directory:

```ini
[DSP]
Backend = No Audio Output
Volume = 0
Muted = True
```

Also pass the corresponding `Dolphin.DSP.*` overrides on the command line.
Graphics settings are `HiresTextures=True`, `CacheHiresTextures=False`,
`InternalResolution=4`, `DumpEFBTarget=True`, `EFBScaledCopy=True`,
`DisableCopyToVRAM=False`, `EFBToTextureEnable=False` and
`DeferEFBCopies=False`. The original 256×256 RAM render target remains enabled;
its scaled GPU EFB dump is the actual 1024×1024 RGBA source. Do not use a 256×256
RAM read enlarged to 1024 as an HD source.

Advance native render frames before freezing the final pose: custom texture
loading is asynchronous. Repeat the exact frozen matrices and capture until
the selected ROI has three consecutive identical RGBA hashes. A1024 image alone
does not prove that HD materials finished loading. Keep these stability receipts,
the uncropped GPU sources and protected-input hashes outside application assets.

For each form, retain normal and shiny raw images, exact source identities,
material hashes, pose matrix hash, declared camera, and **one shared square crop**.
The registry names the final crop and pose recipe. Gen3 weather palettes are
shared; do not invent a special shiny weather colour scheme.

## 5. Compose, review and register

Run `scripts/compose_extra_portraits.py --help` with each pair of real raw GPU
images and their SHA-256 values, its shared crop, the original 42×84 atlas guide,
the exact native texture key, and target game. The crop must be at least 168²;
only premultiplied reduction to 168² is allowed. There is no fit, stretch or native
RGB enlargement. Colosseum uses an opaque square. XD reconstructs the native
disk `(21,21), radius22.5` using 64 coverage samples per HD pixel; filtering an
enlarged binary mask would introduce edge ringing. Fully transparent output
pixels have zero RGB. Both variants share the identical frame geometry.

Review every target against the original pose/framing, verify eye, silhouette,
normal/shiny identity and all materials, then assemble the nine-entry
`extra-portraits.json` with the retained capture receipts and reproduction rules.
Its application loader checks every source/model/material/PNG identity, pose and
crop again. `review_only` must stay true until review is complete.

`scripts/register_extra_portraits.py SOURCE --check-only` validates the reviewed
nine-atlas set without writing application assets. Registration without that flag
adds the nine PNGs and registry to game-asset provenance while preserving font
and other asset entries. Keep all personal save/profile/process data in private
evidence, never in this public registry.
