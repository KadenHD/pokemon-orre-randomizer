# Pokémon Orre Randomizer

<!-- impeccable:product-schema 1 -->

## Platform and users

A native Python/Qt desktop app, Windows first, for players with an unmodified
Colosseum or XD image. It creates a separate randomized image locally without
requiring extraction or command-line tools. Rust accelerates the shared codec;
the Python fallback remains available. Version 2 can create a game folder with
a small launcher and an isolated Dolphin profile. Existing personal emulator
saves are never imported, moved or edited implicitly.

## Primary workflow

Choose a game, then **ROM → Settings → Create**. Both workspaces share layout,
navigation, profiles, language/audio controls, preview tables and Pokémon sheets.
Game-specific themes use their own logos and media; home uses neutral colors.
One main action per step, visible progress and recoverable errors take priority.

## Defaults and advanced controls

The two randomizing modes share family diversity, all starter evolution stages,
random abilities and a seeded 5% shiny chance for supported encounters. Species
draws have no power or starter-pair type matching. Pokémon + moves also draws
moves, TM compatibility and eligible items without type, power or value matching.
Pokémon-only preserves moves, TMs and items while retaining evolution access.
XD Shadow shinies use the chosen rate with an optional unlock, enabled in both
presets. Wild Poké Spots use a separate 5% roll for every new encounter by default,
with the same appearance on the field, in battle and after capture. Legendary
and Mythical species are excluded from replacement draws in both presets;
fixed legendary encounters remain. Shadow Lugia, full-Pokédex
Poké Spots and tutorial/Hordel controls have their own rules. Imports preserve
saved values. Detailed behavior belongs in the [user guide](docs/USER_GUIDE.md).

Advanced settings use stable field identifiers and metadata, searchable in all
six interface languages. Switching views does not reset settings. Preview and
creation use the same patch plan off the interface thread. Creation verifies
the result and writes a portable-settings report and offline journal.

## Game folders and shared resources

Create a new folder with `Game/game.iso`, `.gcm` or `.rvz`, `Launcher.exe`,
`game.json`, `DolphinUser/`, `Textures/` and `README.txt`. ROM-only creation stays
available. Detect Dolphin or select it manually; Dolphin is not bundled.
The launcher reopens the party independently of the randomizer, retaining its
graphics, speed, controls and saves. Generated filenames stay in English.

The neutral HD manager installs one pinned, hash-verified pack per game/version.
Game folders reuse it and retain their recorded runtime and pack after updates.
HD sources are original community releases by their authors, recorded with
exact archive hashes and credits. Retrieve packs automatically from the approved
HTTPS origin or distribution folder, without asking players to select ZIPs.
Prepare both packs for private storage together;
production hosting requires a separate proposal and the user's approval.
Rebuild custom materials and body artwork whenever a pinned source changes.
Custom x4 textures derive from actual pinned-pack donors and override matching
HD names. Native meshes remain in the ROM. Missing newly authored HD assets
block HD preparation; unchanged stock omissions retain stock behavior. HD does
not add polygons or HQ audio.

The launcher shares the incumbent Colosseum/XD layout and uses their respective
themes. It offers 100%/200% base speed, hold Tab for 200%, Shift+Tab for 50%,
keyboard/XInput presets and native Dolphin remapping. Speed shortcuts require
the owned game window to have focus. The experimental independent-music option
is disabled until final combined-output validation passes. Its implementation
is limited to verified Europe revision-0 images on Windows.
It keeps gameplay music at normal speed; effects/cries and prerecorded movies
follow game speed. Native audio is the fallback when the helper cannot follow.
Do not describe this option as validated for every scene, region or emulator.

Custom shiny rates for supported starters, gifts and trainer/Shadow encounters
use the seed; the retired Colosseum unlink flag is normalized after profile verification.
XD wild Poké Spots roll separately for each new encounter. Disabling a shiny
customization option retains native behavior for its encounter scope.

Shadow Lugia uses XD's dark model in both games, including randomized Shadow
slots, with a white/black shiny variant and matching portraits. A shared advanced
option retains that appearance after purification. It is disabled by default,
changes appearance only and never affects a Lugia without Shadow provenance.

Common wording and behavior follow the [interface parity contract](docs/INTERFACE_PARITY.md).
Both games show pending rosters, multilingual encounter search, loading states,
single-click sheets and effective-settings summaries. Native mechanics retain
their own accurate explanations within the shared workflow.
Colosseum's Events tab previews its optional postgame Nascour battle and all
six team members. The original 48 Shadow encounters stay separate from the
bonus Lugia; its entry is added to the native Snag List after discovery.

## Product constraints

Validate the entire original image and preserve source files and saves. Never
overwrite existing outputs. Explain impossible filters and best-effort family
fallbacks. Keep interface language independent of ROM text. Distinguish tested
scenarios from full-playthrough claims; see [validation](docs/VALIDATION.md).

Windows builds offer an in-place update on Home for newer stable releases.
A user click downloads, verifies and applies the official installed or portable
package, then restarts the app. A centered progress view temporarily replaces
game selection and locks all other controls and file drops. Downloads can be
cancelled; cancellation or errors restore the previous control states and home
view. Preserve user files and preferences throughout the update.

The [README](README.md) presents the public product; [DESIGN.md](DESIGN.md)
records interface conventions. Application code, original branding and the
verified game-media pack have separate provenance and licensing scopes.
