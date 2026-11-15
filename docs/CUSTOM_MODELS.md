# Adding a model or appearance variant

Treat an added appearance as a set of resources for one specimen. Adding a
battle model alone does not cover field scenes, portraits or the DNA lab.
Use this procedure for every new model, including recolors of an existing one.

## Resource contract

| Use | Required resource and format |
| --- | --- |
| Battle and Pokémon summary | Native PKX for each supported game; preserve its skeleton, material bindings and animation schedules. |
| Field actors and story scenes | Native DAT derived from the same appearance. Check the skeleton, motion mapping, scene scale, position and facing. |
| Colosseum portraits | 42x42 RGBA, opaque square, black interior for the added Shadow Lugia appearance. |
| XD portraits | 42x42 RGBA, transparent corners and a circular frame. Contain the complete face inside the circle. |
| App previews and sheets | The selected game's portrait format, including both normal and shiny variants. |
| Colosseum DNA keypad | Separate 64x64 RGBA artwork showing the whole body, with a transparent margin and matching colors. |
| Colosseum DNA hologram | The specimen's 3D model and identity, with the game's original hologram lighting and tint. |

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
3. Format added portraits with `model_artwork.format_model_portrait`. Its default
   XD fit preserves all four source corners inside a circle. A larger fit is
   allowed only after checking the actual silhouette against a native mask.
   Shadow Lugia uses its audited 36px artwork and native alpha mask. Its UI and
   native texture encoder share this function. Colosseum keeps the square input.
4. Capture or author whole-body artwork separately, with provenance and a visual
   check of the complete silhouette. Use `model_artwork.validate_model_body`
   before DNA composition. It rejects face-sized images, empty bodies and clipped
   edges, but dimensions alone cannot prove that an image contains the whole body.
   Missing body artwork must fail validation, never fall back to a face.
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

## Validation before release

- Test normal and shiny portraits in both games' previews, sheets and native
  menus. Check transparent corners in XD, opaque corners in Colosseum, native
  dimensions and no cropped anatomy. Include a species-independent formatter
  test so another added model cannot inherit a Lugia-only exception.
- Check body artwork separately from faces. Verify both variants, their source
  hashes and the DNA keypad's complete silhouette. Keep the hologram's native tint.
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
