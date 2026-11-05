---
name: Pokémon Orre Randomizer
description: Shared native Qt layouts with Colosseum, XD and neutral home themes.
colors:
  forest-panel: "#082b24"
  indigo-background: "#181b3b"
  field-ink: "#0b1c20"
  text-ivory: "#f2f6f1"
  text-mint: "#c1d8cf"
  silver-frame: "#b6ccc4"
  cyan-state: "#71e2e6"
  teal-selected: "#125359"
  button-face: "#172c33"
  field-edge: "#829e98"
  action-gold: "#efd574"
  action-face: "#173e38"
  action-hover: "#245d4f"
typography:
  display:
    fontFamily: "Segoe UI"
    fontSize: "27px"
    fontWeight: 700
  headline:
    fontFamily: "Segoe UI"
    fontSize: "23px"
    fontWeight: 650
  body:
    fontFamily: "Segoe UI"
    fontSize: "14px"
  note:
    fontFamily: "Segoe UI"
    fontSize: "13px"
rounded:
  control: "4px"
spacing:
  compact: "8px"
  group: "12px"
  page: "16px"
  outer: "24px"
components:
  button:
    backgroundColor: "{colors.button-face}"
    textColor: "{colors.text-ivory}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "4px 12px"
  button-primary:
    backgroundColor: "{colors.action-face}"
    textColor: "{colors.text-ivory}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "3px 17px"
  button-primary-hover:
    backgroundColor: "{colors.action-hover}"
    textColor: "{colors.text-ivory}"
  input:
    backgroundColor: "{colors.field-ink}"
    textColor: "{colors.text-ivory}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "5px 8px"
  selection:
    backgroundColor: "{colors.teal-selected}"
    textColor: "{colors.text-ivory}"
  menu-panel:
    backgroundColor: "{colors.forest-panel}"
    textColor: "{colors.text-ivory}"
---

# Design System: Pokémon Orre Randomizer

## Overview

**Creative North Star: "The menus of Colosseum"**

The system takes over the green panels, the silver frames with cut angles and the cyan selection of
the original game. The indigo background and the small portraits give the context. The fields and
buttons remain readable Qt controls.

The images and audio belong to the embedded interface package. The appearance does not depend on a
selected ROM, download or user cache. The system font, native selectors and accessible control names
remain the convention of the desktop application.

**Key Characteristics:**

- Green forest panels on an indigo background drawn from the game.
- Angular silver frames, without added shadow.
- Selection and cyan focus. Main action bordered with pale gold.
- Small authentic portraits and texts rendered by Qt.
- Independent audio controls, activated at the first launch if available, with stored choice.

## Colors

The green occupies the work surface. The indigo bears the background image. The accents express a
state or an action, with the values of the frontmatter.

### Primary

- **State Cyan**: keyboard focus, button selection and active category.
- **Selection scarf**: background of checked checks and selected lines.

### Secondary

- **Or d’action**: contour of the main action. Its focus remains cyan.

### Neutral

- **Green forest**: central panel and pallet of windows and Qt children.
- **Indigo de fond**: backset and support of the title texture.
- **Field ink**: seizures, boxes and progression.
- **Text**: wording and current content.
- **Text mint**: notes and secondary descriptions.
- **Argent de cadre**: external contour of the cut-angle panel.
- **Button face** and **edge of the fields**: checks available at rest.

**The State Rule.** The cyan indicates the focus or selection. It accompanies a check mark, button
state, cursor or position. No critical information rests solely on the color.

## Typography

**Display Font:** Segoe UI on Windows. No serif font of the system on other platforms. No game font
is embedded.

**Body Font:** the same family as the titles. Real sizes and fat are defined in the frontmatter.
Controls inherit the application font.

### Hierarchy

- **Display**: the name of the tool in the header, with a return to the authorized line.
- **Headline** : titre de la zone de travail courante.
- **Body**: buttons, fields, categories and boxes.
- **Note**: sub-labelled presets, aids and legends.

**The Native Text Rule.** Useful texts remain Qt widgets, translated and exposed to assistive
technologies. Images do not replace labels, descriptions or commands.

## Layout

The window uses a compact header, horizontal navigation, a dominant work panel and actions anchored
under this panel. The preferred dimensions are limited by the screen. The minimum implemented is 680
× 540. The content areas scroll and the main actions remain outside.

The external margins are 24 px horizontally and 18 px vertically. The groups are separated by 12 px.
The frame reserves 8 px around the pages. These add 16 px horizontally and 12 px vertically. The
content of the pages is centered and limited to 1,200 px wide. The fixed rows of the settings and
preview are spaced by 6 px to reserve the height of the active content.

In Japanese, the controls use Yu Gothic UI, Meiryo or Noto Without CJK JP according to the installed
fonts. The name of the app keeps Segoe UI. The sizes, colors and states remain those of the theme.
The Japanese text returns to the line.

The settings separate Configuration and Pokémon Preview. The Seed and Profiles menu remain in a
common row, above the content of each view. Changing view keeps the rules and the valid result.
Common preset details are folded by default.

In advance, the categories occupy a 192 px column when the window is at least 900 px wide and the
fifteen categories stand in height. Otherwise, a compact selector replaces the column. The active
choice and values are retained. The active form scrolls without scrolling including the step.

The preview has its own result area, with no fixed maximum height. The starters' portraits accompany
the names and levels. The dark ones and the gifts occupy a native list. The Back/Continue foot
remains outside these areas and remains visible in the small window of 680 × 540.

## Elevation & Depth

The depth comes from the tones and the two contours of the panel. The texture of the game is
darkened before drawing the controls. The implementation does not add any shadow or decorative blur.
The changes of state are immediate.

**The Frame Rule.** The silver frame belongs to the work panel. The fields, lists and buttons keep
their strokes sharper to preserve the hierarchy.

## Shapes

The panel is an eight-top polygon: 11 px cut outer corners, 2 px outer contour and finer internal
contour, 5 px offset. The fields and buttons use small rounded corners. The steps are jointed and
square.

The portraits remain small: original pixels of 42 × 42, centered in a 48 × 48 position. The logo of
96 × 32 is a badge in the header. The main name of the tool remains text.

## Components

### Buttons

- **Repos**: dark face, fine silver line and ivory text.
- **Principal**: green face, 2 px gold border and reinforced fat.
- **Survol**: clarification of face and contour.
- **Focus and selection**: cyan border of 2 px, with padding compensation.
- **Off**: face, border and attenuated text. The command remains recognizable.
- **Preset**: buttons aligned with a short sub-label to compare choices.

### Inputs / Fields

The fields are dark, with a fine line and a minimum height of content of 24 px. The focus thickens
the line and compensates for the padding. The width of the content does not jump. The boxes display
a drawn check mark, in addition to the cyan background.

The wheel does not change a number or list of choices without focus: it is transmitted to the parent
scrolling area when it exists. A field with focus retains its native modification behavior.

### Encounter Preview

The Pokémon Preview view contains three Qt tabs: Starters · 2, Shadow Pokémon · 48 and Gifts · 4. "Compute
Overview" explicitly launches the common engine for all three groups. The tab change reuses the
valid result. During the calculation, an animated bar, an explanation and cancellation remain
available. After calculation, the check mark and "Update Preview" replace the command in the tab
row. The detail of the result remains accessible by its tooltips.

The native list presents two columns named "Pokémon d'originale" and "With this Seed", under a dark
header. Each tab presents a flat list. Each row combines the original name with the replacement,
with its small portrait of ROM (42 × 42) and its level when it is available. Names, columns and tabs
are translated into all six languages. The selection retains the existing one. No new accent is
added.

The search accepts the names in the six languages and the Pokédex numbers. A status filter is
available when the Shiny result is known. The counter indicates the range of lines visible among the
filtered results. An empty search for results the announcement explicitly. The list only scrolls,
with a bar of 15 px and a clear handle of at least 44 px.

Changing the ROM, seed or rules removes the old lines and invites to update. Event gifts indicate
the localized donor and the purification threshold when their access is activated. Otherwise, they
keep the mention of external event. The foot recalls the active conditions in the Gifts tab. In
other groups, it specifies the scope "new part" and the absence of created ROM.

### Dependent Settings

A box can activate the digital field that follows it. The field remains visible and retains its
value when the box is unchecked. Its text and contour are attenuated by the native deactivated
state. The help remains legible under both controls.

In "Shiny Pokémon", the box "Customize shinies" precedes the box "Linking the Shiny to the seed",
then the percentage rate of 0 to 100, displayed with four decimal places. Customization is unchecked
at the first launch. The proposed rate of 1% and the link remain visible but inactive. The link is
checked by default and retains its value when it is disabled. A permanent note explains the two
extremes. The texts remain localized, with the decimal separator of the chosen language.

With the active customization and binding, the line visible before the calculation announces "Shiny
status fixed by the seed." at intermediate rates. The preview uses the exact decisions of the engine
for a new part: each starter, obscure and gift receives his or her authentic normal or Shiny
portrait. The name also bears the translated mention "Shiny" or "non-Shiny". The color of the
portrait is therefore not the only information. The same species can appear in both forms according
to the encounter. The legend specifies the scope "new part" and does not promise any minimum number
of Shiny ones.

Without a link, the caption keeps the explanation of the draw in play at intermediate rates and uses
ordinary portraits. The 0 and 100% specific messages remain visible before calculation when
customization is enabled. Change the rate, customization or link removes the outdated results in
both views. Names and status remain legible if a portrait cannot be decoded. These states take back
the frames, colors and actions of the existing C composition.

### Exclusion Selectors

A setting line combines a summary ("No exclusion" or a number) with "Choose...". The dialog keeps
the dark fields, Qt texts and the green list of the existing system. The title and help precede the
search. The counter and OK / Cancel buttons remain below the scrolling list.

A check mark always means "excluded". Its dark mark on cyan background takes over the settings,
without replacing the accessible state of native control. The search accepts localized names and
numbers. Group actions only concern visible results. OK applies the selection. Cancel closes the
dialog without changing the setting value.

### Navigation

The application icon is **Clip**. The two black/gold and lilac/red crescents form a common
silhouette. The master PNG and ICO 16–256 px are in `assets/app/`, regardless of the game pack. It
is used for executable, windows and local shortcut.

The steps are checkable buttons aligned without spacing. The active step combines the root, cyan
contour and Poké Ball cursor. The categories use a native list with discrete separators and a cyan
selection. The fifteen categories have semantic pictograms with a 20 px line, mint at rest and cyan
in selection: team, gift, flash, disk TM, crown, filter, talent, graphic, label, hand holding an
object, safe, capture and level, tree of evolution, shop, Poké Star ball for Shiny Pokémon. These
icons are designed by the application and remain available without the pack of the game. The active
line remains in the visible part of the list after a resizing or a language change. The compact
selector represents the same category.

The tabs take back the dark faces of the buttons and the root bottom for the selection, underlined
in cyan. Their padding is 6 px vertically and 13 px horizontally. The Profiles menu uses the same
colors and combines import and export without adding a permanent row of commands.

### Panel Menu

The panel is drawn by `QPainter`, with its accessible Qt children. Scrolling pages retain a
transparent background to stay in the same green surface. The background of the title, logo and
portraits come from the validated local pack.

### Audio Controls

"Music" and "Sounds" are two checkable buttons in the header. Their checked state uses the same cyan
selection as other commands. Preferences are stored independently of the game settings. The music
and browsing channels are separated. An unavailable audio output does not block the creation.

## Do's and Gift'ts

In "Starters and Gifts", access to event gifts commands four fields: two purification thresholds and
two reception levels. The values remain stored but disabled without this option. The descriptions
specify that the introduction scenes must be completed, even with a zero threshold. The game
dialogues follow the five PAL languages, regardless of the six languages of the interface. The
preview retains the same species and status as the engine.

### Do:

- **Do** keep the real small visuals of the package and their proportions.
- **Do** reserve the cyan to the interactive states and the gold to the contour of the main action.
- **Do** keep the translated text, keyboard focus and accessible control names.
- **Do** scroll the active content and keep the navigation actions visible on a small window.

### Gift't:

- **Gift't** re-establish the old blue palette or remove the resources from the game of the chosen
  system.
- **Gift't** enlarge portraits until they become the dominant element of the work area.
- **Gift't** Raster wording or transform model captures into a clickable interface.
- **Gift't** make the visual and audible start depend on a first ROM or cache to be filled.

## Theme scope

Both games use the same wizard and Pokémon-sheet templates. The color values
above describe the Colosseum baseline; `ui_theme.py` defines XD and neutral-home
variants. The shared layout is specified in `ui_workspace.py`. Changing a theme
must not remove audio, profiles, previews or navigation from either game.
