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
