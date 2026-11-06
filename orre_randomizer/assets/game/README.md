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
Both release editions include
this pack so the interface works before a ROM is selected, without downloading
media at startup. The selected ROM is used only to create a new game.

Qt draws the controls and frames; application text remains accessible and
translatable. Game names, images and audio are separate from the code's MIT
license. Exact sources, transformations and file hashes are recorded in
`provenance.json` and the per-asset metadata.

This pack contains no ROM, save, scenario data or Dolphin installation.
