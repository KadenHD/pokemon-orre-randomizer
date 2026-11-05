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
  xd-background: "#1d1112"
  xd-panel: "#24191a"
  xd-field: "#181314"
  xd-text: "#fff4e6"
  xd-selection: "#66302a"
  xd-focus: "#ffad93"
  xd-action: "#ffc772"
  home-background-start: "#090a0b"
  home-background-middle: "#191a1c"
  home-background-end: "#34363a"
  home-control: "#202327"
  home-selected: "#30343a"
  home-focus: "#cbd0d8"
typography:
  display:
    fontFamily: "Segoe UI"
    fontSize: "27px"
    fontWeight: 700
  headline:
    fontFamily: "Segoe UI"
    fontSize: "23px"
    fontWeight: 650
  subheading:
    fontFamily: "Segoe UI"
    fontSize: "16px"
    fontWeight: 600
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
  menu-panel-xd:
    backgroundColor: "{colors.xd-panel}"
    textColor: "{colors.xd-text}"
  button-home:
    backgroundColor: "{colors.home-control}"
    textColor: "{colors.text-ivory}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
---

# Design System: Pokémon Orre Randomizer

## Overview

**Creative North Star: "The menus of Colosseum"**

The desktop interface keeps the original menu character: angular frames, dark
panels, small Pokémon portraits and a visible selection cursor. Native Qt fields,
buttons and lists handle the work. The Colosseum palette is the baseline; XD uses
the same composition with charcoal, red and gold. The game-selection screen uses
a neutral black-to-gray background and neutral header controls.

The bundled interface pack supplies logos, background artwork, music and menu
sounds before a ROM is selected. Content stays readable without an available
audio device. System fonts and accessible Qt controls remain the desktop convention.

**Key Characteristics:**

- One shared three-step wizard and Pokémon-sheet template for both games.
- Colosseum green/indigo and XD charcoal/red themes, with neutral home controls.
- Cut-corner frames and tonal surfaces without decorative shadows.
- Small authentic portraits beside localized, accessible text.
- Persistent navigation, visible scrolling and explicit loading states.
- Shared wording and behavior across all six interface languages.

## Colors

The frontmatter records observed values from `ui_theme.py`. The Colosseum tokens
describe the baseline controls; the `xd-*` and `home-*` tokens describe the theme
changes. The complete XD substitutions remain in `xd_stylesheet()`.

### Primary

- **Cyan state / teal selection:** focus, checked controls and the active view in Colosseum.
- **Warm focus / red selection:** the same states in XD.
- **Neutral silver focus:** home header controls, independent of either game's palette.

### Secondary

- **Action gold:** the primary action's border, adapted to each game.

### Neutral

- **Forest panel / indigo background:** Colosseum work surface and surrounding artwork.
- **Charcoal panel / dark red background:** XD work surface and angular background bands.
- **Black-to-gray background:** the home screen's diagonal gradient.
- **Ivory text / tinted secondary text:** common hierarchy with game-specific tints.
- **Field ink / silver frame:** recessed inputs and the outer work panel.

**The Theme Rule.** A theme changes the palette and artwork, not the shared
controls, wording or workflow. Native game differences keep their own accurate help.

## Typography

Segoe UI is the Windows baseline. Other platforms use an available system
sans-serif font. Japanese uses Yu Gothic UI, Meiryo, Noto Sans CJK JP or Noto Sans
JP; the app title retains Segoe UI. No proprietary font is bundled.

The observed hierarchy is display, section heading, subheading, body and note.
The frontmatter records their sizes and weights. Names use an initial capital;
known shiny Pokémon have a small raised red star beside the name. Accessible
descriptions retain the status in words.

**The Native Text Rule.** Useful text remains localized Qt content. Artwork does
not replace labels, help, search, progress or keyboard focus.

## Layout

The header contains the logo/title, music, sounds, profiles and language. Home
offers Colosseum and XD. Each game follows **ROM → Settings → Create** with the
same persistent navigation outside the scrolling content.

The minimum window is 680 × 540. Diagnostics also exercise 1040 × 800. Outer
margins are 24 px horizontally and 18 px vertically. The main panel reserves
8 px around pages; page margins are 16 px horizontally and 12 px vertically.
Content is bounded to 1,200 px. Fixed settings/preview rows use 6 px spacing.

Settings separates Configuration and Pokémon preview, keeping the seed above
both views. Simple/Advanced switches preserve values. Advanced categories use
a 192 px sidebar only when the window is at least 900 px wide and every category
fits vertically; otherwise a compact selector replaces it. The selected form
scrolls independently of the footer.

Encounter lists fill the remaining height. Their vertical scrollbar is 15 px
wide with a handle of at least 44 px. Only active content scrolls; navigation
actions stay visible. Japanese and long translated help wrap instead of
requiring a larger window.

## Elevation & Depth

Depth comes from darker fields, tonal panels and two angular outlines. The app
adds no decorative shadows or blur. The Colosseum artwork is darkened behind
controls; XD uses painted angular bands; home uses a neutral gradient.

**The Frame Rule.** The double frame belongs to the work panel. Controls use
finer borders so the panel, content and current action remain distinct.

## Shapes

The work panel is an eight-sided polygon: outer corners cut by 11 px, a 2 px
outer contour, and a finer inset outline at 5 px. Controls use a 4 px radius.
Step buttons have square corners and no gaps. Pokémon portraits are 42 × 42 px
inside 48 × 48 px slots. Preserve logo proportions and the existing Poké Ball
cursor spacing.

## Components

### Buttons and inputs

Secondary buttons use a dark face and a fine border; hover lightens both.
Checked/focused controls use the theme's state border. The primary action has
a gold border. Disabled controls retain their label and saved value with reduced
emphasis. Focus-border changes compensate padding to avoid layout movement.
The search field's clear button keeps its compact native geometry.

### Navigation and shared copy

The active step combines position, checked state and the Poké Ball cursor.
Category icons describe functions rather than arbitrary Pokémon. Profiles stays
beside language and audio; import/export does not add permanent form rows.
Use `workspace_copy.py`, `workspace_i18n.py` and shared option metadata for common
labels and help. Follow `docs/INTERFACE_PARITY.md` and `docs/INTERFACE_COPY.md`.

**The Shared Template Rule.** Common controls have the same order, words and
behavior in both games. Do not create a separate XD synonym or omit a shared
feature to fit its theme.

### Presets and dependent controls

The three presets are **Pokémon + moves**, **Pokémon only** and **Unchanged copy**.
Their explanations appear directly below the choices. Custom values are identified
and remain available in Advanced. Both randomizing presets use the same common
balance policy and a seeded 5% shiny rate for supported encounters. Imported
profiles retain their saved values. XD's native exceptions remain explicit.

Dependent controls stay visible and retain their values when disabled. Shiny
customization enables the rate; Colosseum also offers seeded/in-game draws, while
XD has a separate Shadow unlock. Wild Poké Spots keep their native rate.

### Encounter preview

Colosseum shows two starters, 48 Shadows and four gifts. XD shows one starter,
83 Shadows, seven gifts and nine Poké Spot slots. Both use **Calculate preview**,
**Update preview**, **Cancel preview**, **Try again** and **Preview up to date**
for the same states. The original and replacement columns use shared labels.

Before calculation, known original species appear on the left and unknown
replacements use question marks. Retained/manual species may already be named.
Search works before and after calculation using names in all six languages and
National Pokédex numbers. The counter reports the visible range or no results.

During calculation, a cosmetic cycle updates eligible portraits/names every
115 ms. It does not determine the draw. Progress, loading text and cancellation
remain available while the production engine works off the interface thread.
Changes invalidate stale results and open sheets. Ready results reuse the same
seeded decisions; a duplicate-family tab appears when needed.

### Pokémon sheets and creation

A single click opens the shared Pokémon sheet: Summary, Moves and Evolutions.
Evolution routes show portraits and actual final requirements. Known shiny
status selects matching evolution portraits. The red star replaces repeated
shiny/non-shiny labels beside individual names.

Create shows **Applied settings**, grouped by category with values and units.
Inactive remembered values are omitted. RVZ output exposes its DolphinTool field
and shares the path selected in ROM. Both games provide progress, cancellation,
a stage log and links to the output folder, JSON report and offline journal.

### Home and audio

Home keeps neutral music/sound/language controls and game-specific selection
tiles. Both music and menu sounds start enabled when available and remember
independent preferences. Audio availability never blocks randomization.

## Do's and Don'ts

### Do:

- **Do** reuse shared Qt templates, copy and option metadata for both games.
- **Do** retain each game's logo, palette and bundled interface media.
- **Do** keep localized text, keyboard focus and accessible control names.
- **Do** keep navigation visible and scrolling confined to the active content.
- **Do** distinguish pending, loading, cancelled, failed and current previews.

### Don't:

- **Don't** change shared wording or behavior merely because the theme changes.
- **Don't** present a cosmetic loading sample as a final seeded result.
- **Don't** show a known species or shiny status when the preview cannot establish it.
- **Don't** make the visual/audio startup depend on selecting a ROM or downloading a cache.
- **Don't** replace native controls with rasterized text or distribute proprietary fonts.
