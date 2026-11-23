---
version: 1
slug: "run-management"
primary_target: "orre_randomizer/ui_run_tools.py"
related_targets: ["orre_randomizer/ui_home.py", "orre_randomizer/ui_play.py", "orre_randomizer/gui.py", "orre_randomizer/ui_game_folder.py", "orre_randomizer/ui_theme.py", "orre_randomizer/run_library.py", "orre_randomizer/save_backups.py", "orre_randomizer/storage.py", "orre_randomizer/challenges.py", "orre_randomizer/play_i18n.py", "orre_randomizer/ui_support_report.py", "orre_randomizer/support_report.py", "orre_randomizer/support_i18n.py"]
---

# Surface: Local runs, memory-card history, storage and challenge codes

Mode: Operate. Extend the existing native Qt menus. Preserve the root DESIGN.md
palettes, type hierarchy, angular frame and game-themed launcher. Product behavior
and limitations are recorded in PRODUCT.md and docs/RUN_MANAGEMENT.md.

## Direction contract

- **THESIS:** Manage existing runs without moving ROMs or exposing spoilers.
- **OWN-WORLD:** Incumbent neutral charcoal, silver angular frames and native Qt text.
- **STORY:** Find a run, protect cards, review cache deletion, or share rules.
- **FIRST VIEWPORT:** Fixed heading, explanations and footer around bounded native tables or one code editor.
- **FORM:** Precise extensions of incumbent Home and the per-ROM launcher, with background file work.

## Entry points and bounds

Home's secondary utilities use two centered rows: HD packs / My games / Storage,
then Import a challenge / Update a launcher. Below 800 px each row stacks
vertically inside Home's existing scroll body; the two game choices remain the
main actions.
The normal 1,040 × 800 px Home keeps both utility rows and its credit visible
without a scrollbar; the game choices can shrink to preserve that viewport.
Profiles offers share/import challenge actions for either game. The launcher's
saves section provides history and the automatic-before-play checkbox beside
the existing save-folder action. Keep the normal launcher footer unchanged.

Library and storage are fixed at 1,000 × 720 px; backup history at 900 × 600 px;
challenge import/share at 860 × 560 px. Shared dialogs use the neutral palette
and frame even from a Colosseum or XD launcher. They have no mobile variant or
whole-page scrollbar. Native data viewports absorb overflowing content.

## My games

Use a heading and one short explanation, followed by search and Add a game.
The bounded five-column table shows folder name, game, seed, launcher version
and availability. Select one complete row; show folder, backup and forget-reference
actions below it, with Play in the footer and Close opposite. Double-click also
opens the selected valid launcher. Search matches the displayed name, game,
seed or version without adding spoiler data.

Display an empty-state invitation when no entries exist. Keep missing entries
visible and forgettable, with launch, folder and history actions disabled.
Elide long paths in the location line and retain the full path in its tooltip;
table cells also expose complete values. Removing a reference does not delete
its game folder. Adding selects a specific game.json; the tool does not scan drives.

## Memory-card history

Keep the five-snapshot / 256 MiB limit and save-state exclusion above a three-column
date, origin and size table. Manual copy, Restore selected and Close stay outside
the table. Disable restore with no snapshot selected. Before restoration, confirm
that current cards are preserved first; retain the explicit idle/emulator-close
explanation and display failures as status text. A manual copy with no raw card
tells the user to save in the game before a card can be copied.

The launcher defaults automatic raw-card backups on and retains an explicit
per-run opt-out. Use MenuCheckBox so the checked state contains a visible mark
within the incumbent game theme. Do not imply that emulator save states are
included or that viewing history changes the original ROM.

## Storage

Begin with scan scope and unique-data/free-space totals. A bounded category table
separates the inventory from a second table of eligible old texture views. The
inventory categories include ROMs, cards/save states, backups, packs, runtimes,
views, music and retained downloads; these are not all cleanup targets.

Keep the hard-link explanation and preservation note visible. Logical category
sizes can overlap; estimated reclaimable bytes are distinct from unique data.
Offer only completed, unreferenced texture views older than 24 hours for cleanup.
No candidate begins checked. Native table indicators use CacheCheckDelegate's
silver outline and actual check mark so unchecked, selected and checked remain
distinct. Reuse the shared table tokens; do not inherit a game's accent here.

Scan and Delete selected caches stay in the footer. Disable cleanup until a row
is checked. The confirmation names the candidate count; the operation rechecks
references, activity and paths. ROMs, saves, packs, runtimes, downloads and music
are outside cleanup. Keep cancellation cooperative between candidates and report
the resulting count; cancellation does not undo earlier deletions.

## Challenge codes

Place the exact-seed/settings/engine explanation above one native plain-text
editor. Export is read-only with Copy code; import is editable with Import
challenge. Keep the same-ROM requirement and absence of local paths visible.
The ORRE1 code contains no roster preview or other new content. Inline validation
reports malformed, incompatible or oversized codes before any controls change.
Copy success appears in the status line. A successful import opens the matching
game and restores the seed and options while requesting the original ROM.
Existing JSON profiles keep their separate behavior.

## Diagnostic export

Both games' Profiles menus offer Export diagnostic without adding a Home utility.
The neutral 860 x 620 px dialog first names what is included and excluded, then
offers last-failed-attempt/current-settings context and an optional seed. Its
read-only native JSON viewport shows the exact serialized document, wraps long
values and has no horizontal scrollbar. Save diagnostic and Close stay outside
the viewport. The seed checkbox uses the shared visible check-mark control with
the neutral panel ink. Sensitive-looking or invalid seeds are omitted, visibly
explained, and cannot be included inadvertently.

Preserve the failed request's seed/options rather than pairing a stale error
with newly edited controls. Normalized error codes replace raw exception text;
only verified identity from a successful operation on the same selected source
may appear. No ROM reading, scanning, uploads or automatic sharing occurs.
Save through the shared background-file task and retain exclusive publication,
inline success/failure, keyboard access and the six-language layout contract.
Wait for running creation, preview and report-check workers before opening.
Pause pending automatic-preview/report timers throughout the modal lifetime,
including its nested event loop, then resume normal scheduling after close.

## Shared states and languages

Use the existing section/body/note roles and six-language catalogs. Dialog labels
are owned locally rather than registered as retained parent translation bindings.
Headings, scope notes, statuses and footer actions remain native accessible text.
Tables are non-editable, single-row selection, stretched columns, no horizontal
scroll, row numbers, alternating fills or grid; fine row separators retain density.

File operations show status and an indeterminate bar immediately, disable the
work panel and footer, and restore their prior enabled states afterward. Window
close or Escape requests cancellation and defers destruction until the worker
finishes. The disabled footer Close action is not the cancellation affordance.
Keep errors in the status area, with details available in its tooltip. Empty,
busy, failed and completed states must remain truthful to actual local data.

## Evidence and limits

Source authority: ui_run_tools.py, ui_support_report.py and their Home, Profiles
and launcher integrations.
Real Qt demonstration captures are in build/run-management-qa/round2, including
English and Japanese tools, French history and the XD launcher. Source remains
authoritative for checkbox states and the two-row Home utility layout. Preserve
the established type ramp and game accents rather than deriving new global
tokens from demonstration data or advisory detection heuristics.
This surface record does not establish a mobile layout, full-run gameplay
validation or new game content. Engine validation is recorded separately in
docs/VALIDATION.md.
