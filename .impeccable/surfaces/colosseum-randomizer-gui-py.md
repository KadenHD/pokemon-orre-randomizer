---
version: 1
slug: "colosseum-randomizer-gui-py"
primary_target: "orre_randomizer/gui.py"
related_targets: ["orre_randomizer/ui_theme.py", "orre_randomizer/ui_workspace.py"]
---

# Surface : orre_randomizer/gui.py

Mode: Operate. The composition C takes over a compact assistant close to the original Colosseum
menus. Approved composition: `.impeccable/mocks/c-assistant-compact.png`.

Route: original ROM → Settings → Create. Simple by default, advanced on demand, without changing the
settings when you switch. The three presets correspond to Options.recommended(), Options() and
Options.none(). A different profile is reported as custom. FR/EN/DE/ES/IT/JA and system language
remain available for processing.

The approved 0.12 refinement retains the graphic world and separates Configuration and Overview of
Pokémon. The Seed and Profiles menu remain common. The content is centered and limited to 1,200 px.
Only active content scrolls through the Settings step.

| Engagement visible | Implementation |
|---|---|
| Short header, title and language | Title RANDOMIZER in QLabel next to the Pokémon Colosseum logo. Native QComboBox language |
| Headband of the three stages at the top | Three QPushButton checkables. Active cyan step, returns without loss of input |
| A main green panel with silver frame and cut corners | QWidget/QPainter. Semantic Qt content, no rastered text |
| Three starting points in the same group | Pokémon + moves, Pokémon only, identical copy. Comparable descriptions and common details folded by default |
| Seed and Common Profiles | QLineEdit, New Seed and Profiles menu with import/export. No value loss or valid preview at change of view |
| Advanced categories adapted to space | The 15 categories and 74 controls, including 56 booleans. 192 px column if the window is at least 900 px and all categories hold height, if not compact selector. Active choice retained at resize or change of language |
| Shinies | Customization unchecked by default. Rate from 0 to 100% to four decimal places and link to the seed visible but disabled without customization. Link checked by default. Permanent help for 0 and 100%. Poké Poké pictogram Star ball on line |
| Common Real Overview | Calculate the explicit preview, animated bar and cancellation. Status ✓ Updated view in the row of tabs after result, infobulle detail, Update preview after modification. Names FR/EN/DE/ES/IT/JA, available levels and portraits 42 × 42 read in the ROM |
| Three tabs of Pokémon | Starters · 2, Shadow Pokémon · 48 and Gifts · 4. Two portraits of starters and flat lists comparing Pokémon from origin to With this seed. Result shared without recalculation at tab change |
| Readable search and scrolling | Search by name or number in the six languages. Shiny filter when status is known, meter of the range visible among the filtered results and status without result. List occupying the available height, bar of 15 px contrasted. Scroll on a field without focus transmitted to the parent form |
| Poké Balls indigo background | Actual texture title.fsys/menu_042 exported once and loaded |
| Foot with Return and Continue/Create | Persistent action visible at 680 × 540. Explicit keyboard, focus and deactivated state. Help related to configuration, new part or event conditions according to view |
| Output, progression and result | Step 3, ISO/RVZ format, separate destination, cancellation, folder and report |

The labels invented by the generator are not taken up. The controller buttons are not shortcuts of
the application. The logo 96 × 32 remains a small badge of its useful size. The main title is text.
The local construction uses the images and sounds exported from the game.

Check points: source absent/incompatible. Language and fashion changes without losing
paths/feed/options. Step-by-step return. Progress/cancellation. Corrupted pack with sober fold.
Rendered small window. Object names in the five ROM languages and limited stone correction.
Originals preserved.

Confirmed additions: Independent music and sounds buttons, activated at the first launch if
available, stored choice. Independent image/cursor/SFX/music pack. No ROM reading to start the
interface, no cache to start. Comparable presets sub-labelled. When the customization of shinies and
the link are active, a line under the starters announces "Shiny status set by the seed." before the
calculation at intermediate rates. The preview uses the engine decisions for a new part: authentic
normal or Shiny portraits of the ROM, translated text words "Shiny" and "nonchromatic", including
below 100%. The same species may carry different status according to the encounter. The rate does
not impose a quota. At 0 and 100%, the existing messages announce respectively the absence or
guarantee of Shiny starters. Without link, the status remains in play at intermediate rates and the
legend indicates it. Change the customization, link or invalid rate the old preview. The profiles
0.5 to 0.10.1 keep the link disabled at limport.

The production calculation does not create any ROMs. Changing the ROM, the seed or the rules removes
the outdated lines and invites to update. Event gifts are labelled. The foot of the Gifts tab
reminds them of their requirements for obtaining. If access is enabled, the label instead displays
the localized name of[Eagun] and the chosen threshold. Both thresholds and levels depend on the
access box, with descriptions in the six languages and invalidation of the preview after
modification. Originals and backups remain preserved. No choice of direction remains open. Future
controls cover the small and large window, the six languages, calculation/cancellation states,
filters and preservation of values.
