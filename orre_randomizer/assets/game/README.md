# Game interface pack

Images, cursor, menu sounds and music exported from verified European Colosseum
game data, plus the original English XD banner. The larger home-screen logos
use unchanged transparent English PNGs from Bulbagarden Archives, each 1280 pixels
wide; their original URLs and hashes are in `interface/home-logos.json`.
The small disc banners remain as fallbacks and workspace-header artwork.
Both release editions include
this pack so the interface works before a ROM is selected, without downloading
media at startup. The selected ROM is used only to create a new game.

Qt draws the controls and frames; application text remains accessible and
translatable. Game names, images and audio are separate from the code's MIT
license. Exact sources, transformations and file hashes are recorded in
`provenance.json` and the per-asset metadata.

This pack contains no ROM, save, scenario data or Dolphin installation.
