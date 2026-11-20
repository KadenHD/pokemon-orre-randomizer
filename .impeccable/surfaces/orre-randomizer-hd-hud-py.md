---
version: 1
slug: "orre-randomizer-hd-hud-py"
primary_target: "orre_randomizer/hd_hud.py"
related_targets: ["orre_randomizer/hd_text_vectors.py","orre_randomizer/hd_text_runtime.py","orre_randomizer/hd_menu_atlases.py","orre_randomizer/play_folders.py"]
---

# Surface: In-game HD menus and generated lettering

Mode: Operate. Preserve the original Colosseum and XD menus rather than applying
the desktop application's palette or redesigning the games. Original game
captures, native atlas layouts and verified community HD artwork are the visual
authority. Keep the V5 typography the user selected: common shape proportions,
original advances and encoded line breaks.

The supported language matrix is Europe revision0 (English, French, German,
Spanish and Italian), USA revision0 (English) and Japan revision0 (Japanese).
Do not substitute an English label for a localized one. Keep type/status labels,
controller glyphs, digits, sprite boundaries, colors and alpha coherent with
their original context. Diacritics and Japanese marks must remain readable.

Desktop controls stay accessible, translated Qt text. In-game lettering and
labels embedded in menu textures use separate authenticated external HD
replacements. Original mode retains native artwork, and the source ROM and
prerecorded movies remain unchanged. Missing donors are explicit coverage gaps;
inventories do not establish that a resource was shown in a real playthrough.

Record every new menu recipe's native identity, donor provenance and unchanged
pixel regions. Rebuild versioned caches after a recipe changes. Inspect native
and HD screenshots from owned, muted Dolphin sessions with copied cards. Cover
the affected languages and six regional executables, distinguishing source
validation from actual displayed screens. Retain failures and known limits.
Read small labels from unscaled crops of authenticated captures. Compare their
pixels before treating a misleading whole-screen preview as a rendering defect.
Inspect words inside icon and illustration resources too; their initial
classification must not hide localized menu labels. Preserve authentic brand
art when no qualified HD source exists, and record that gap explicitly.
Check the actual texture sampler as well as source pixels: the HD-only local
profile uses linear filtering to avoid native point-sampling stair steps on x4
captions. Original mode restores native filtering. Test sprite boundaries in
the emulator rather than inferring their appearance from the source atlas.

Small menu geometry retains each native sprite canvas, circular silhouette,
transparent cutout and translucent panel. New SVG artwork uses measured paths
and analytic gradients, with a separately pinned recipe and x4 PNG. Treat Qt's
one-step opacity quantization separately from an accidental opaque fill. Keep
source qualification distinct from proof that a sprite appeared in a replay.
Treat the resource kind as part of coverage: the normal Genius Sonority intro
is a THP movie. Its separate white-background UI sprite does not replace that
movie; a registered x4 drawing does not establish where the sprite is used.

Measure adjacent atlas captions within separate native text bands. An accent
from the next heading must not enlarge the previous word's bounds. Retain a
transparent sampling gutter at sprite boundaries and verify it with the actual
linear-filter profile. Inspect the captionless donor itself for leftover ink;
correct label bounds alone cannot erase remnants in that background. Preserve
legitimate accents when testing the clear sampling rows.
Startup health notices retain the original wording and
line layout in each playable locale; indexed RGB565 resources need explicit
identities alongside the usual RGB5A3 banks.

Stock weather/Deoxys material replacements share the exact reviewed PNG hashes
used for the paired portrait captures. Keep their regional native texture keys
and Original-mode materials intact. A prepared cache proves exact asset delivery;
it does not prove a weather transformation was observed in a battle replay.

Colosseum Options retains its native striped background. Clean only the
qualified two-pixel rectangles in y200..255; preserve every donor RGBA pixel
outside that band. Do not erase the original stripe design to hide compressed
alpha artifacts.
