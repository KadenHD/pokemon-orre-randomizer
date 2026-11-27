# Game folders, HD packs and the launcher

Version 2 can create a folder for each run. The ROM remains a normal ISO, GCM
or RVZ that can also be opened directly in Dolphin. `Launcher.exe` starts that
ROM with its own profile and selected graphics, controls and speed.

## Create and reopen a run

1. Select Colosseum or XD, supply an unmodified supported ROM, then choose your
   seed and randomization settings as usual.
2. In Create, leave **Create a game folder with a launcher** checked. Give the
   new folder a name inside an existing parent folder. Existing folders are
   refused so nothing is overwritten.
3. Select your Dolphin executable. Orre checks common install locations and
   your previous selection; manual selection is always available.
4. Choose ISO, GCM or RVZ, then Original or HD graphics. Create the folder.
5. Open its `Launcher.exe` and click Play. The randomizer can be closed.

To create a standalone ROM instead, turn off the folder option. RVZ conversion
is built in for both workflows; no DolphinTool path is required.

## What is stored where

```text
Colosseum-My-Run/
  Launcher.exe
  launcher-runtime.txt
  launcher-version.json       # present after an explicit launcher update
  game.json
  README.txt
  LauncherBackups/            # previous launcher files, after an update
  Game/
    game.iso                 # or game.gcm / game.rvz
    game.iso.json            # creation report
    game.iso.html            # offline journal
  DolphinUser/
    Config/
    GC/                      # this run's memory card
    StateSaves/
    Logs/
  Textures/                  # native references and custom HD recipes
    NativeReferences/
    HD/                      # prepared x4 assets, when HD is enabled
```

The tiny launcher references a shared Orre runtime, copied from the installed
application. Dolphin and texture packs are shared rather than copied into
every run. By default shared files live under
`%LOCALAPPDATA%/OrreRandomizer/Shared/`:

| Directory | Contents |
| --- | --- |
| `Runtimes/` | Immutable Orre runtime used by each launcher |
| `TexturePacks/` | One installed pack per game/version |
| `TextureViews/` | Merged texture views, hard-linked to the shared pack |
| `AudioBanks/` | Verified original music resources extracted locally |
| `Downloads/` | Resumable archives; removed after successful installation |

Keep each game folder together. Moving it to another PC also requires the
matching shared runtime/resources and a working Dolphin path. It is not a
self-contained emulator distribution. Do not delete older shared versions
while game folders still reference them. Changing the shared directory chooses
a different cache; it does not move an existing cache or music banks for you.
Opening a folder from Home retains its verified cached runtime. If a runtime
for the current Orre version is missing, reopening repairs the launcher. For a
missing older runtime, reinstall that release instead of silently changing the
party's pack version.

## Update an existing launcher

Updating the randomizer itself does not silently update existing runs. On
Home, choose **Update a launcher...**, select the run's `game.json`, review the
version change and click **Update launcher**. Close that run's launcher and
Dolphin session first. Preparation runs in the background and can be cancelled;
closing the dialog or app waits for the worker to finish.

An update replaces only `Launcher.exe`, `launcher-runtime.txt` and
`launcher-version.json`. The ROM, `game.json`, cards, save states, controls,
graphics settings, texture references and pack pins remain byte-identical.
The separate version receipt records the new launcher without changing the
ROM's creation version. A failure during publication restores the previous
control files. Each attempt retains a checksum-recorded backup under
`LauncherBackups/`; the previous shared runtime is also retained.

The selected Orre release must support the run's exact pinned pack versions.
Incompatible pins and downgrades are refused. This action does not download
new packs or migrate a run to different artwork. Opening the run later uses
the explicitly selected runtime; simply opening an older run retains its
previous version.

Updating the randomizer does not silently replace the launcher in existing
game folders. New folders created with v2.0.5 use the revised shortcuts and
display controls; older folders keep their original runtime and pack pins.

## Saves and controls

The next launcher adds automatic card backups and a restore history. Home's
**My games** and **Storage** tools reference existing folders and account for
shared files without duplicating the ROM. See [run management](RUN_MANAGEMENT.md)
for retention, recovery, cleanup scope and challenge codes.

New folders begin with a separate memory card. Orre never silently imports,
moves or modifies your usual Dolphin saves. New game folders also refuse
profile junctions or linked memory cards pointing outside their own profile.
Only one launcher may open a given folder at a time.

To use an existing save, close Dolphin and make an explicit backup first. Copy
the appropriate memory card into this run's `DolphinUser/GC/`; do not move the
original. The save must match the game/region and the randomized run. Old save
states can restore data from an earlier ROM, so prefer normal in-game saves.

Keyboard defaults use arrows to move; X/Z are A/B, S/A are X/Y, Q/W are L/R,
D is Z, Enter is Start, and I/J/K/L control the C-stick. The controller preset
uses the first XInput gamepad. Other controllers can be configured manually.
**Configure controls…** opens Dolphin with this run's profile: open Controllers
there, change the mapping, then close Dolphin before returning to the launcher.
Custom mappings persist until you switch presets.

The game always starts at 100%. The 100%/200%/300% selector sets only the
fast-forward target. Hold **Tab** to use that target, or press **Ctrl + Tab**
to toggle it on and off. Holding **Shift + Tab** overrides either mode with
50%; releasing it restores the previous mode. Releasing a modifier before Tab
does not accidentally trigger another fast hold. Losing focus cancels the
toggle and pauses this run; returning restores 100% before accepting a new hold.
These controls never poll keys belonging to another foreground process.

Stock Dolphin has speed-up/down shortcuts in fixed 10% increments and no
desktop hotkey for an arbitrary fixed multiplier. The launcher still uses its
local speed-only controller; reaching a target takes a short transition rather
than an instantaneous jump. Dolphin's on-screen messages are disabled only in
this isolated profile to suppress the intermediate speed notices. This also
hides its other OSD notices. Native keyboard shortcuts and gamepad mappings
remain available.

Both display choices start in **borderless fullscreen** at the desktop
resolution. **16:9** widens the 3D projection and adjusts the orthographic
projection to preserve the proportions of 2D elements. **4:3** keeps the native
projection with side bars on a wider monitor. The generic widescreen hack and
cropping are disabled. Neither choice edits the ROM or replaces its movies.
Changes take effect on the next launch, not during a running game.
After changing the aspect ratio, start from the game's memory-card save.
A Dolphin state recorded in the other mode can restore cached menu geometry
from that mode.
The camera hook follows Ralf's codes distributed in Dolphin's
[GameSettings](https://github.com/dolphin-emu/dolphin/tree/master/Data/Sys/GameSettings);
regional addresses and the separate 2D correction are checked against the six
supported revision-0 executables. Additional corrections cover selected
fullscreen clears, fades and full-width backgrounds, including tiled and
overscan panels. Their geometry is adjusted separately from portraits, text
and other bounded UI elements. Colosseum's 3D menu backdrops use a correction
limited to their checked menu cameras, retaining the original artwork and
native text proportions.

Current Dolphin checks cover selected European revision-0 load/menu and
summary screens. The six-region instruction checks do not establish equivalent
runtime coverage. They do not certify every camera, transition or scene in
either complete game. Native 4:3 remains available.

Both display modes retain the profile's existing cheat preference. The
launcher adds no cheat-setting override. Global Dolphin settings are unchanged.

The launcher and pack manager use fixed windows with no page scrolling. Short
choices stay visible as buttons. Download details open separately. The existing
wizard and long Pokémon lists keep their own vertical scrolling; horizontal
panning is disabled.

## Shared HD packs

Install packs through **HD packs** on Home, or **Manage HD packs** in Create
and the launcher. Each Orre release records fixed upstream downloads and
hashes. It never silently follows an upstream latest release. Existing game
folders retain their runtime and pack version after an Orre update.

Installation shows preparation followed by download and extraction progress.
**Cancel** interrupts the current operation; closing the manager cancels and
waits for cleanup before closing. Interrupted downloads can resume when you
return. Installation and path controls become available again after completion,
cancellation or an error.

| Game | Pinned version | Download | Installed textures |
| --- | --- | ---: | ---: |
| Colosseum | HD Pack V2 / 2.00 | 0.72 GB | 7,032 DDS |
| XD | XG/XD HD v1.0 | 3.30 GB | 8,582 PNG |

Packs come from the original community authors, [Sephie and mikeyX](HD_SOURCES.md).
Exact author links, SHA-256 hashes and explicit duplicate selections are
recorded in `orre_randomizer/hd_packs.py`. **Install** retrieves the pinned ZIP
automatically from the release's approved source, then verifies its size and
SHA-256 before extraction. GitHub transport reconstructs XD's ZIP from its
two fragments; the player does not join or select any files. Whole ZIPs from
a distribution folder remain supported. HTTP downloads can resume inside a
fragment. The frozen [HD release](https://github.com/KadenHD/pokemon-orre-hd-packs/releases/tag/packs-2026-11-18)
supplies the verified assets without a paid service or domain. Repair publishes
a new installation without changing the textures used by an already running
game. Original graphics are available without downloading a pack.

Allow room for the download and extracted pack during installation. Successful
archives are deleted. Texture views use hard links on the shared cache volume;
they do not duplicate a whole pack per seed. Use a filesystem supporting hard
links, such as NTFS on Windows. HD uses 3x internal resolution, linear texture
filtering and on-demand replacement textures rather than preloading the complete
pack into RAM. Original mode restores native resolution and filtering in the
same isolated profile.

Texture priority is **custom overlays > game pack > already-required companion
packs**. A companion fills only missing Dolphin texture identities, including
PNG/DDS and mipmap filename aliases. It does not replace the game pack's version
of an existing texture or trigger a download of an otherwise unused pack.
Repairing either contributing pack creates a new view; running games retain
their earlier files.

European XD also prepares localized HD HP/level atlases for English, French,
German, Italian and Spanish. These derive from the pinned XD artwork and
[mikeyX's vector sources](HD_SOURCES.md#localized-xd-status-atlases). They are
verified and published with the custom overlay cache. This does not make every
menu or generated line of dialogue HD; see [coverage and limitations](HD_COVERAGE.md).

Custom meshes, field models and shiny palettes remain in the generated ROM.
Each game folder records their native references and HD recipes while that
ROM is being created. Later HD preparation uses those references and the
pinned packs; it does not need the original ROM again.

Custom x4 materials and portraits are derived from the actual HD pack textures,
with the matching colors, alpha and game-specific framing. Colosseum portraits
are square; XD portraits are round. DNA uses separate whole-body artwork.
Shadow Lugia's HD body images are captures of its mesh rendered with the HD
materials, including its shiny variant. The mesh and animations stay native.

XD's HD mode requires both pinned packs, even before a game folder is created:
XD supplies the textures, while Colosseum supplies HD portraits for base Pokemon
species and Unown forms, adapted to XD's round frame. **Install** on the XD row
installs the missing packs together, without downloading an installed version
again. A partial installation is marked **Incomplete**; HD creation and launch
require both packs. If installation is interrupted, retrying keeps the completed
pack and installs only what is missing. Original mode requires neither pack.
Nine separately rendered x4 atlases cover Castform's three weather forms in
each game and Deoxys's three extra forms in XD. They retain the native frame
and paired normal/shiny pose. Castform's weather forms share their original
Gen3 colors. These are portrait additions; the upstream packs still determine
stock extra-form 3D material coverage. Shadow Lugia has separate normal/shiny
portraits in both resolutions, with a square violet background in Colosseum
and a round violet background in XD. DNA artwork shows its whole body.
The source, transform and hashes are recorded for the generated assets. A
filtered enlargement of a native bitmap does not satisfy this HD contract.

A custom model imported from the other game can require both packs. In
particular, Colosseum's added Shadow Lugia uses XD's HD material sources.
The launcher lists missing dependencies before preparing these visuals.
Preparation is cancellable and publishes a cache only when every required
custom asset is covered. A missing custom donor leaves Original mode available;
it does not silently pass off an enlarged native image as HD. Unchanged stock
textures absent from the upstream pack retain the game's normal behavior.
Sources can be PNG or DDS. When a donor requires scale conversion, its actual
source dimensions and conversion to x4 are explicitly recorded. Colosseum's DNA keypad uses independent
cells so normal, shiny, Shadow and purified Lugia appearances can change without
freezing neighboring images. This path has passed native and HD Dolphin checks.
Spinda's DNA diagram follows the analyzed specimen's saved PID and shiny status.
Original and HD modes keep its body colors and spot diagram together, including
older saves with a different PID. HD spot artwork uses paint from the pinned
pack's Spinda material, with the original rules determining each spot's position.
On Windows, newly created European and USA revision-0 Colosseum folders can also
use a 512x512 hologram face while HD mode is active. A separate launcher companion
reads the specimen's actual PID, fills an inactive texture bank and lets the
native renderer publish it after a GPU fence. The five native material maps,
shiny palette handling and blue hologram filter remain in use. The companion
works independently of the music option. If it stops, the game returns to its
native 128x128 face.

Japanese Colosseum keeps that native face: the additional static face memory
reservation failed its loading check, so new Japanese folders do not install
those hooks or reserve their banks. Its HD body and spot diagram remain separate
and available. Opening a ROM directly without the launcher also uses the native
face.

Shadow Lugia has x4 counterparts for all five battle materials: two actual pack
textures and three authored reflection/mouth maps using those HD palettes.
Its three field models also have complete material routes. The cinematic belly
uses the matching HD battle material with a checked UV/color transfer; the two
separate eye layers are reconstructed from the actual HD eye atlas while
preserving the field models' opaque alpha and separate socket/iris geometry.
These are recorded as authored derivatives, not byte-identical upstream maps.

Normal and shiny bodies and heads are new GPU captures with all five HD
materials enabled. Square/circular portraits and whole-body DNA artwork retain
their separate formats. Partial captures are rejected, and the launcher rebuilds
older prepared caches without changing the ROM or native assets.
The DNA body pair uses the same frozen pose, normalized crop and placement in
both resolutions. New body renders receive the keypad's black contour during
composition; retail bodies retain their existing outline. This does not add
outlines to battle models or portraits.
When native body artwork changes, recreate the game folder from the same source,
seed and settings to update the ROM's native artwork as well. HD preparation
rejects an older custom DNA body rather than pairing it with a different HD pose.

These packs change textures, not polygon counts or the opening movie. They
contain no HQ audio replacement. The music-speed feature below uses the
original game's audio resources.

## Updating generated artwork

Installing a new application version does not rewrite an existing game's ROM.
Recreate the game folder from the same original image, seed and complete profile
to adopt additions that change native artwork or runtime hooks. Existing folders
retain their own ROM, saves and versioned launcher runtime.

Use a copy of the memory-card save when moving to the rebuilt folder, then boot
the game normally. Save states contain the previous executable and its memory
layout; they are not a substitute for a memory-card save across rebuilt ROMs.

## Music and game speed

**Keep music at 100%** is checked by default for newly created, supported game
folders. A missing setting uses the same supported default. Your explicit
choice is saved for that game and remains unchanged when reopening the launcher.
Temporary renderer unavailability does not erase that preference.
Existing folders adopt this behavior when their launcher runtime is explicitly
updated; updating the application alone retains their earlier runtime.

The option is available on Windows for verified Europe revision-0 images and
the checked renderer recipe, with the game's music bridge present.
Other regions, revisions or a renderer with a different recipe leave the option
disabled and use Dolphin's native audio. A saved setting cannot enable an
unsupported capability or reduce native audio volume while it is unavailable.
Other regions can still use the launcher, HD and speed settings with native
audio.

When enabled, a local companion renders the original gameplay music at normal
speed while Dolphin runs at the selected game speed. Sound effects and cries
follow the game. Prerecorded movie picture and complete soundtrack stay
together at game speed, including 200%, as requested. Real-time scenes use
the gameplay music path.

The companion checks the process it launched, its mailbox and the active audio
device. Missing/unsupported states, device changes, stale control data or
helper errors restore native playback. The game keeps running. Diagnostic
messages are stored in that run's `DolphinUser/Logs/launcher.log`.
Backward save-state recovery is bounded; arbitrary forward states, resets,
long sessions, all soundtracks and other Dolphin versions are not certified.
See [native music implementation and validation](reverse-engineering/NATIVE_MUSIC_HOST.md).
