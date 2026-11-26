# Game interface pack

Images, cursor, menu sounds and music exported from verified European Colosseum
game data, plus the original English XD banner. The larger home-screen logos
use unchanged transparent English PNGs from Bulbagarden Archives, each 1280 pixels
wide; their original URLs and hashes are in `interface/home-logos.json`.
The small disc banners remain as fallbacks and workspace-header artwork.
Home plays the Colosseum Pyrite Town theme. The two workspaces play their own
title-screen themes. The music files were rendered from the European game data
and are level matched for the interface. Track provenance is stored under `music/`.
The Pokémon sheets use the original type badges in all six interface languages.
The texture sources and extraction details are recorded in `types/manifest.json`.
The catalogs under `text/` contain the original localized ability and move help
texts, with sources and game-specific overrides. The app draws the Shadow badge.
The optional Colosseum bonus event uses XD's original Shadow Lugia model and
portrait from `models/`. Its PKX container and scheduling metadata are adapted;
the mesh, textures and DAT animation tracks are preserved. Source hashes and the conversion are in
`models/manifest.json`, with a reproducible local export script in `scripts/`.
The custom shiny Shadow Lugia swaps the original body and belly material colors
to a white body and dark belly, with the belly's grayscale map shaded to match.
Its red eyes, other textures, mesh and animations stay intact. The matching
face icon is derived from the original `face249dark` frame, matching its white
head, neck and lower jaw, charcoal eye mask and original red iris;
both the transformation and resulting hashes are recorded in that manifest.
The tool uses separate 42px Dark Lugia tiles with a black matte. A boundary-
connected mask removes the baked violet backdrop while retaining the head,
red eyes and mouth. Colosseum's native HUD/menu uses the same square matte.
XD retains its native circular alpha mask, with black only inside that circle;
the complete normal or shiny head is fitted to 36px with 3px padding so it stays
inside the round frame. Original source portraits remain intact, as does the
native outer Shadow-status frame.
The Colosseum DNA keypad uses the games' transparent whole-body images from
`poke_body.fsys`, including their shiny variants and Unown letters. Shadow
Lugia has no retail whole-body icon, so its two extra images are fitted from
the native 3D renderer before the analyzer's blue tint. They use the original
dark model and the custom white-body/dark-belly model, with no recoloring of
an ordinary Lugia image. Sources, complete-silhouette bounds and hashes are in
`models/fullbody-manifest.json`; the fitting script is
`scripts/export_shadow_lugia_bodies.py`. The analyzer's original blue effect
remains unchanged in the game.
Deoxys's Attack, Defense and Speed forms use XD's original standard and rare
PKX models. Their Colosseum containers preserve the geometry and DAT animation
tracks. Native and x4 head/full-body images are separate GPU renders with
reviewed matching framing; the extra DNA bodies receive the game's black
outline during composition. The x4 materials use the pinned XD pack and
reviewed form-material recipes. Sources, poses, hashes and transformations
are recorded in `models/deoxys/deoxys-assets.json`. These game-derived assets
are separate from the code's MIT license.
Both release editions include
this pack so the interface works before a ROM is selected, without downloading
media at startup. The selected ROM is used only to create a new game.

Qt draws the controls and frames; application text remains accessible and
translatable. Game names, images and audio are separate from the code's MIT
license. Exact sources, transformations and file hashes are recorded in
`provenance.json` and the per-asset metadata.

This pack contains no ROM, save, scenario data or Dolphin installation.

The added Fairy type has six localized badge designs for each game. Colosseum
uses its original large capsule layout; XD also has a separate small battle
badge. Native and x4 images are rendered independently from vector geometry and
Noto Sans JP lettering, without enlarging a native bitmap. Their recipe, source
font hash, exact dimensions and image hashes are in `types/fairy-badges.json`.
Original type badges, including their native abbreviations, are unchanged.
