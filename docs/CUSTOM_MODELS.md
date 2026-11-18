# Adding a model or appearance variant

Treat an added appearance as a set of resources for one specimen. Adding a
battle model alone does not cover field scenes, portraits or the DNA lab.
Use this procedure for every new model, including recolors of an existing one.

The bundled Shadow Lugia uses XD001's original animation data. Colosseum adapts
the container and its 17 scheduling slots to native timing/flags; it retains
XD's skeleton and DAT tracks. Normal and shiny Shadow Lugia have identical
scheduling data in both games: only materials and the belly texture are changed.
The read-only original-model audit reproduces the bundled Colosseum conversion.
This establishes data preservation, not a new visual playthrough of every move.

## Resource contract

| Use | Required resource and format |
| --- | --- |
| Battle and Pokémon summary | Native PKX for each supported game; preserve its skeleton, material bindings and animation schedules. |
| Field actors and story scenes | Native DAT derived from the same appearance. Check the skeleton, motion mapping, scene scale, position and facing. |
| Colosseum portraits | 42x42 RGBA, opaque square; the added Shadow Lugia portraits have a violet background. |
| XD portraits | 42x42 RGBA, transparent corners and the native circular frame. Preserve the original crop and Shadow Lugia's violet background; do not shrink the head into a smaller inset. |
| App previews and sheets | The selected game's portrait format, including both normal and shiny variants. |
| Colosseum DNA keypad | Separate 64x64 RGBA artwork showing the whole body, with a transparent margin and matching colors. |
| Colosseum DNA hologram | The specimen's 3D model and identity, with the game's original hologram lighting and tint. |

Version 2 requires a second, x4 visual set for every added appearance. Native
resources are based on the original game; HD resources are based on the pinned
HD packs. The two sets share the geometry, animation tracks and specimen
identity, but their raster artwork is prepared separately.

| Native resource | HD counterpart |
| --- | --- |
| Battle and field material maps | Real pack textures, with any custom recolor or retouch applied to those HD sources. |
| 42x42 square/circular portraits | 168x168 portraits, with the same game-specific crop, pose and framing. |
| 64x64 DNA body artwork | Separate 256x256 whole-body artwork rendered or authored from the HD materials. |
| Runtime appearance or form switch | Registered HD keys or a checked runtime adapter for every supported state. |

Do not count a filtered native bitmap as the HD version. Record each upstream
pack version, texture key, source hash and custom transform. Where the pack
only supplies x2, record that source scale and the x4 conversion. Missing new
HD artwork blocks HD readiness; it must not silently substitute the native
bitmap. Every material of an added custom model needs an HD route, including
maps whose native bytes did not change. Unmodified retail species missing
upstream are a separate case and retain stock behavior.

Keep these resources distinct. A face enlarged to 64x64 is not whole-body
artwork. A blue hologram is not a reason to substitute the ordinary model for
an added Shadow appearance. XD has no equivalent of Colosseum's DNA lab.

## Implementation

1. Record the source game, archive, member, decoded hash and conversion in the
   model's manifest. Keep original resources intact and append new resource IDs.
   Include each shipped file in the interface pack's provenance allowlist.
2. Derive normal and shiny variants from the same geometry. Keep one specimen's
   PID, owner, form and Shadow provenance throughout the rendering paths. Do
   not roll another shiny result for a portrait or a field actor. Resolve the
   purification display option separately; a never-Shadow specimen stays ordinary.
3. Match the original game's portrait crop and frame. The shared
   `model_artwork.format_model_portrait` supports square/circular conversion;
   check its artwork size against the reference rather than blindly using the
   default containment fit. Portraits should fill their frame without a smaller
   rectangular image floating inside the circular background.
   Shadow Lugia's replacement square/circular portraits use its actual model
   materials, including the fully red eye, at both resolutions. Its interface
   and native face writers read the same accepted images through
   `model_portraits`. Keep the violet background in both normal and custom
   shiny variants. Reject candidates until their visual review passes.
4. Capture or author whole-body artwork separately, with provenance and a visual
   check of the complete silhouette. Use `model_artwork.validate_model_body`
   before DNA composition. It rejects face-sized images, empty bodies and clipped
   edges, but dimensions alone cannot prove that an image contains the whole body.
   Missing body artwork must fail validation, never fall back to a face.
   Capture native and HD bodies from the same frozen joint matrices and camera,
   with one normalized crop and placement. Record both source renders; do not
   compensate for a different pose with a mirrored or stretched bitmap. The DNA
   keypad uses colored bodies with a black contour. Retail body images already
   include this ink. For new transparent GPU renders, apply
   `engine/dna_artwork.outline_dna_body` at composition time: one native pixel
   or four HD pixels before placement. Keep this treatment out of head portraits
   and 3D model textures, and preserve opaque body colors.
   Use the shared custom DNA placement rectangle for both resolutions. Its
   120px native area keeps the keypad's bevel intact; frame the full body up to
   60px inside the 64px source canvas, leaving room for the ink. Check that
   duplicate numbers do not cover any part of the silhouette. Retail placement
   remains unchanged.
5. Convert field models through the shared actor conversion in
   `engine/plusle_actor.py`. Use the correct game's container and motion layout.
   Verify the requested walk, idle, turn and departure clips actually exist;
   an idle fallback must not be described as a walking animation. Test large
   silhouettes in the scene instead of applying an arbitrary species-wide scale.
6. Route every relevant battle, summary, Snag List, purification, field and
   scripted scene request to that same appearance. Register the game-specific
   loaders and runtime selectors explicitly. Image formatting cannot discover
   native script references, install a new model automatically or create missing
   animations. Keep original opening videos unchanged.

Shadow Lugia is the current reference: `resources.shadow_lugia_portrait`,
`engine/shadow_lugia_body.py`, `engine/postgame_lugia_model.py` and
`xd_shadow_lugia_model.py`. The last two share their checked model sources with
the corresponding field actor adapters.

For HD, `hd_overlays.capture_native_assets` records native references and donor
recipes before the source ISO is released. `prepare_hd_overlays` resolves those
recipes against the pinned packs and reports missing resources. Use
`scripts/register_hd_model_bodies.py` with `--native-source` to register a paired
native/HD body set. `--check-only` validates the four raw GPU captures, shared
joint matrices, crop, placement, PNG integrity and unchanged material sources
before publication. Publication backs up the replaced files and rolls back on
failure. Existing head PNGs and their capture records stay intact; only their
material-parent registry hash is updated after verifying unchanged materials.
It does not create a missing HD material, invent an animation, or certify a scene.
The replacement portraits instead require native/HD head renders that match
the intended full-tile framing. Keep their manifest separate from whole-body captures:
`portrait-variants.json` records the eight game/variant/resolution images.
Original Shadow Lugia extractions remain unchanged as references.
Use `scripts/register_model_portraits.py` to validate and register the eight
reviewed portraits. It checks the source material registry, dimensions, hashes,
game-specific alpha, native XD palette limit and public metadata before writing
any image. `--check-only` performs the same checks without changing the pack.
Shadow Lugia registration requires revision-2 captures with all five battle
materials covered. Two use exact pack donors; three are authored from those
HD palettes. Its three field models include the separate belly and eye-layer
transfers in `hd_lugia_field.py`. Native geometry, animations and textures remain
unchanged. Partial captures cannot satisfy the HD contract.

Spinda's DNA keypad diagram has a separate runtime adapter in
`engine/dna_spinda_hd.py`. Its four layers each depend on one PID byte, so the
native bank covers arbitrary saved identities without enumerating every full
PID. The same resolved record selects the normal or shiny body and spot palette.
`engine/spinda_diagram.py` preserves the original linear-address placement,
including horizontal carry and out-of-range row checks. Invisible texture IDs
retain identical transparent RGBA values to avoid filtering artifacts.
`hd_spinda_diagram.py` draws an authored ellipse with paint from the actual HD
Spinda material; it does not enlarge the native spot bitmap. The case uses a
separate, immutable atlas so changing a specimen cannot invalidate its UI key.
The original hologram's generated 128x128 face remains a native texture and must
not be described as a registered HD face.
See the [Spinda DNA adapter](reverse-engineering/SPINDA_DNA_HD.md) for its layout,
source bindings and validation boundaries.

## Validation before release

- Test normal and shiny portraits in both games' previews, sheets and native
  menus. Check transparent corners in XD, opaque corners in Colosseum, native
  dimensions and the intended reference crop. Include a species-independent formatter
  test so another added model cannot inherit a Lugia-only exception.
- Check body artwork separately from faces. Verify both variants, their source
  hashes and the DNA keypad's complete silhouette. Keep the hologram's native tint.
- Align every GX image buffer to 32 bytes after inserting material descriptors.
  Test several custom entries together: a descriptor block can misalign the
  next image even when the first entry renders correctly.
- Check both Original and HD. Compare the same saved specimen and animation,
  including normal/shiny materials, both portrait shapes and whole-body DNA
  art. Verify the output uses actual pack donors and does not fall back to an
  enlarged native image for a newly authored asset. Test runtime mutations
  after capture and purification, not just the initial static image.
- Verify battle, capture, menu, Snag List, purification, post-purification and
  ordinary-specimen behavior using the same saved identity.
- Verify each affected field actor and scene, including movement, facing,
  clipping and leaving/re-entering the area. Check forms and other PID-dependent
  details where applicable.
- Run the affected tests through `scripts/run_tests.py` in isolated processes.
  Shadow Lugia currently has dedicated formatter, face, body, DNA, field actor,
  model selector and regional-hook tests.
- Then check affected native paths under Dolphin in a separate muted instance,
  with copied saves and test ROMs. Record the game, region, seed, expected
  appearance and evidence. Automated pixel and selector tests do not replace
  playing a changed scene. Do not touch a user's active game.

When only the app portrait format changes, recheck the actual Qt list and sheet
and confirm native generated textures remain byte-for-byte identical. Do not
rebuild a user's ROM to change an app thumbnail.
