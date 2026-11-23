---
version: 1
slug: "game-folders-launcher"
primary_target: "orre_randomizer/ui_play.py"
related_targets: ["orre_randomizer/ui_game_folder.py", "orre_randomizer/ui_play_controls.py", "orre_randomizer/ui_home.py", "orre_randomizer/ui_launcher_update.py", "orre_randomizer/gui.py", "orre_randomizer/xd_ui.py", "orre_randomizer/ui_theme.py", "orre_randomizer/play_i18n.py"]
---

# Surface: Game-folder creation, shared HD manager and launcher

Mode: Operate. Extend the established native Qt system with the three approved
creation, shared-pack and per-game-launcher compositions. Keep Colosseum's
green/cyan identity, XD's warm charcoal/red identity and the neutral silver
shared-resource surface. The root DESIGN.md records the reusable visual system.

## Direction contract

- **THESIS:** One game folder reopens independently with its own saves and shared assets.
- **OWN-WORLD:** Original logos, angular menu frames, native text and the incumbent palettes.
- **STORY:** Create the folder, locate Dolphin, choose format/graphics, then reopen Launcher.exe to play.
- **FIRST VIEWPORT:** Visible short choices and one fixed primary action; the launcher and pack manager keep their main content on one fixed page with no page scrolling.
- **FORM:** The user-approved three mockups; an extension of the existing world, not a new navigation or visual identity.

## Creation

Keep ROM → Settings → Create. The folder workflow shows destination, visible
ISO/GCM/RVZ choices, Dolphin selection and Original/HD buttons beside a filename
sidebar with file/folder icons. ROM-only creation remains available. The sidebar
becomes a compact note below 820 px of form width. Applied settings retains the
existing disclosure and generation progress/log behavior.

## Shared packs

The neutral manager groups each game's logo, pinned version, download/installed
sizes, readiness and Install/Reinstall. Keep details and the pack source
accessible before downloading. Progress, cancellation and Done stay distinct.
The same versions can serve multiple game folders; installations and status
must come from the actual selected cache. Changing the shared path does not
claim to move existing files. Its fixed 1,000 × 800 px window keeps the two pack
rows grouped horizontally, with no horizontal or vertical page scrollbar.
Download URLs and hashes open in a separate fixed 900 × 480 px details dialog;
they do not expand the main page.
All shared tooltips, popup menus, detail fields, selections and native fallback
surfaces use neutral charcoal/silver, including when opened from either game.
Immediately show preparation and progress when Install starts. Cancel remains
available while installation and path controls are disabled. A close request
cancels cooperatively, waits for worker cleanup, then closes; it must not leave
an unstarted worker or apply the old close request to the next installation.
Remove bindings to destroyed dialogs. Closing and reopening the manager must
remain safe before and after changing the interface language.

## Optional launcher updates

Home places Update a launcher with Packs HD, My games, Storage and Import a
challenge, using the same neutral utility-button treatment. Two centered rows
group Packs HD / My games / Storage, then Import a challenge / Update a launcher;
each row stacks vertically below 800 px to avoid horizontal overflow.
At the normal 1,040 × 800 px window size, the game choices yield enough height
for both utility rows and the author credit without vertical scrolling. Retain
their flexible height rather than adding a second page or hiding actions.
Selecting `game.json` opens a fixed
760 × 400 px dialog with the neutral angular frame, current/new versions,
preservation and backup explanations, Close and an explicit Update action.
Keep all six languages on one page without scrolling. Elide long folder names
in the summary; retain the complete path in the tooltip and accessible name.

App updates do not silently replace existing launchers. This separate action
requires compatible pinned packs and refuses downgrades. It changes only
`Launcher.exe`/`Launcher`, `launcher-runtime.txt` and `launcher-version.json`.
Retain the previous control files under `LauncherBackups/`; do not change the
ROM, saves, settings, `game.json`, textures or pack pins. Previous shared
runtimes remain available.

Preparation runs off the interface thread. Show progress, disable duplicate
updates and retain cancellation. Closing the dialog or its parent window
cancels and waits for worker cleanup before closing. Show a clear completed
or failed state. An already current launcher keeps Update disabled. An active
game must be closed before
the update can proceed.

## Launcher

Use the same header, frame, order and wording for both game themes. The header
shows game identity, folder name, seed and language. Graphics and HD readiness
lead. Below that, audio/speed/shortcuts sit beside input controls and saves.
Show the unchanged reference GameCube photograph without claiming device
detection. Preserve the complete silhouette and aspect ratio with smooth
scaling; never stretch or crop it. Attribution and provenance accompany the
asset. Keep the normal footer to Open folder and Play, using the authored ivory
outline-folder and gold-triangle icons rather than system icons. Keep the
larger action treatment and stronger identity/page headings from the approved
composition. Show the Dolphin recovery chooser only when the saved executable
is unavailable; do not add a permanent path row to the settings panel.
The fixed 1,100 × 800 px window keeps both settings columns side by side, with
direct contents and no horizontal or vertical page scrollbar.

Short choices remain visible: Original/HD, corrected 16:9/original 4:3,
100%/200%/300% acceleration target and Keyboard/Controller. Every game starts
at 100%. Hold Tab for the chosen target, Shift+Tab for 50%, or Ctrl+Tab to
toggle acceleration. All three shortcuts use framed key labels. Retain a
fixed page without scrolling; display sits above controls beside audio.
The saves group also offers backup history and an explicit automatic-before-play
checkbox, using the same checkmark-painted control as other game settings.
The footer remains Open folder / Play. The neutral history dialog, local library,
storage inventory and challenge-code flow are routed through
[`run-management.md`](run-management.md); their additions do not change the
launcher's fixed two-column composition.
Unavailable independent-music states retain truthful help. The option is enabled
for the verified Windows/Europe revision-0 configuration and checked renderer
recipe; unsupported configurations leave it disabled and unchecked. No visual treatment claims
every audio scene or emulator version is certified.

All user-facing labels use the six-language catalogs. Generated filenames stay
in English. Paths/seeds shown in documentation are demonstration data, while
pack readiness must be grounded in actual installation state. Tests and captures
use private muted preferences and copied profiles; no original ROM or save is
part of interface maintenance.
