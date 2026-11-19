# HD texture sources

The application uses original author archives. They are optional external
resources, separate from this project's source license and interface pack.
The links below document provenance. The free download service uses a fixed
GitHub Release, with automatic transport-fragment assembly for XD's large ZIP.
An approved HTTPS mirror or distribution folder can still provide whole ZIPs.

| Game | Author credit | Version | Archive bytes | Selected textures |
| --- | --- | --- | ---: | ---: |
| Colosseum | Sephie (archive manifest); published by u/Bun-bun45 | V2 / 2.00 | 722,522,130 | 7,032 DDS |
| XD | mikeyX | XG/XD v1.0, PNG Texture Pack | 3,295,188,617 | 8,582 PNG |

## Original releases

- Colosseum: [author announcement](https://www.reddit.com/r/DolphinEmulator/comments/sxzxi2/),
  [original Drive archive](https://drive.google.com/file/d/1FwGSM1TJfIrAKNfy7BTrTF850JccSwkt/view).
  SHA-256: `4cac6314d8b3fed18743dc0db844b64651c3845668037912d8ed216053af0e33`.
  The archive credits Sephie; the announcement account is recorded separately.
- XD: [author thread](https://forums.dolphin-emu.org/Thread-pokemon-xg-xd-hd-texture-pack-v1-0),
  [original MEGA archive](https://mega.nz/folder/kA4WFZ7D#cd66IQr-2AM_PeYd8hFd3Q/file/QZgmWYIZ).
  Select **Pokemon XD-XG HD V1.0 PNG Texture Pack.zip**, not the Resource Pack.
  SHA-256: `56bbf26551f26b7bdb1d0d7d4a6eb7073cf4f8fef72130648bd97abde8851cf2`.

The installed selection occupies 1,609,063,880 bytes for Colosseum and
3,296,572,631 bytes for XD. Colosseum retains the author's GPU-compressed DDS
textures. Pillow decodes a source only when a custom asset requires it.

## Deterministic installation

Both archives are verified before extraction. Only Dolphin `tex1_` PNG/DDS
files are installed. Paths, file sizes and texture identities are checked;
unlisted collisions fail installation rather than silently choosing a file.
Players click **Install**; there is no ZIP import step. GitHub transport assets
remain below the service's 2 GiB per-file limit: the original Colosseum ZIP and
two binary XD fragments. Each fragment and the reassembled original XD ZIP are
verified. A fixed release tag keeps existing game folders on their selected pack.
Whole-archive mirrors and distribution folders retain the
`packs/{game}/{version}/{sha256-prefix}.zip` layout. HTTP downloads resume and
folder sources are read without modifying their archives.

Colosseum has nine duplicate names with different contents. The exact excluded
archive paths are pinned in `Pack.excluded_paths`. The selection retains the
higher-resolution character/tower texture, usable effect alpha, transparent
Pokémon artwork and a single explicit world/material/title variant for equal
sizes. These equal-size choices are application decisions, not claims about
the author's intended priority. Four DDS filenames with an extra processing annotation do not match Dolphin keys and are also ignored. The original ZIP remains unchanged.

XD's duplicate-named ` - Copy.png` is not a valid Dolphin replacement name and
is ignored, along with PSDs, notes and folders. Its valid texture names are unique.
Pack versions do not establish full coverage of every region or language.
Unchanged stock omissions retain the game's native texture; missing newly
authored custom donors block HD preparation.

Shadow Lugia's five battle materials have x4 coverage: two exact pack donors
and three authored reflection/mouth maps derived from their high-resolution
palettes. The three cinematic field models also have complete material routes.
The belly transfer uses a verified shared UV layout and fixed color calibration;
the socket and iris layers are reconstructed from the actual HD eye atlas.
Their source hashes, geometry checks, calibration and alpha policy accompany
the generated assets. These derivatives are labelled as authored resources,
not exact upstream field replacements. Native bitmaps are not enlarged.

Body and head artwork was recaptured with the complete material set, including
the shiny variant. The model manifest records each source and the native mesh.
The source ZIPs remain unchanged; custom images are generated separately.

## Localized XD status atlases

European XD has distinct native HP/level texture identities in each of its
five languages. A missing French atlas cannot use an English donor unchanged:
that would display HP/Lv. instead of PV/N. The adapter keeps the original
1032x80 XD HD atlas outside two label rectangles and redraws those labels
with vector outlines matching the source typography. It produces HP/Lv.,
PV/N., KP/Lv., PS/L. and PS/Nv. for verified revision-0 European identities.
It does not apply these mappings to USA or Japanese identities.

The source is **Pokemon XD UI SVGs V1.0** by mikeyX:
[author's vector archive](https://mega.nz/file/gB4GBSSJ#vj7DVhNCdm_MzSLu5KCn3ZdTsPH6wffX0cMolCPfFhY),
SHA-256 `c575a04cb5044a41df620e92557cd6bd5d72fb9c3ad4e726dacf972def262616`.
Its [license](../licenses/hd/mikeyX-ui-license.txt) and
[README](../licenses/hd/mikeyX-ui-readme.txt) are retained unchanged. Derived
artwork remains credited under CC BY-NC-SA 4.0 with the author's Pokemon-mod
exception, separate from Orre's code license. No native raster is enlarged.
The vector README excludes VS-mode UI from that source; it does not establish
the coverage of every texture in the complete HD pack.

## Localized menu artwork

Regional options, copyright, battle controls and PC layouts keep their own
native cells rather than borrowing another region's entire atlas. The
extension-disc and Poké Coupon resources also retain their original Japanese
captions. Their gold frames use recorded vector geometry; the pointer, currency
icon and PRESS START artwork come from verified Colosseum HD donors. These
bonus resources are source-qualified, without claiming their gameplay routes
have been replayed.

The [regional menu authoring tool](../scripts/build_hd_solo_menu_backgrounds.py)
replays the recorded compositions from authenticated ingredients and captured
font outlines. Its output does not depend on enlarging a native bitmap guide.

Additional registered type/status badges and timer labels use the native
regional atlas identities and measured sprite rectangles. Latin lettering uses
captured outlines matching the author's Bahnschrift typography; Japanese
lettering uses the pinned Noto Sans JP donor. The original labels, abbreviations
and the Generation III `???` type are retained. An English donor does not
replace a localized caption unchanged.

Where an authentic HD frame exists, its pixels outside the registered caption
regions remain unchanged. Simple geometry without a donor, such as Colosseum's
P-AD emblem, is redrawn as vectors from measured native circles and line widths.
These are authored derivatives, identified separately from upstream HD pixels.
No enlarged native raster is used as replacement lettering or vector artwork.

The catalogue records native member and decoded-image hashes, applicable game
IDs, donor hashes, vector data and renderer revision. Preparation authenticates
the data and publishes these files with the other immutable custom overlays.
The same source and artwork credits accompany the prepared cache. Registered
derivatives do not establish that every screen has an HD replacement; see
[coverage and limitations](HD_COVERAGE.md).

The recreated XD VS illustrations combine the game's real character meshes
with authentic hardware photographs. The GameCube controller photograph is
by Evan-Amos, with background removal by Alphathon, under CC BY-SA 3.0. The
[Game Boy Advance photograph](https://commons.wikimedia.org/wiki/File:Nintendo-Game-Boy-Advance-Purple-FL.png)
is by Evan-Amos, released into the public domain through the Vanamo project.
Photographs keep their proportions and colors. The character renders use
recorded poses and verified material donors; three GBA-scene characters retain
their native material maps. These are newly composed illustrations, rather
than a claim that the upstream packs contain those HD scenes.

The sources, transforms and artwork hashes are recorded in
`menu-atlases/vs-scenes.json`. The [reproduction guide](../scripts/vs_menu_artwork/README.md)
uses separately supplied game data, texture packs and Blender tools. No model
importer, source disc or emulator state is bundled with the application.

The eleven new XD Bingo portraits use the original Pokémon meshes and Idle
poses with pinned materials from mikeyX's XD pack. Their paired native/HD
renders keep identical visible geometry, UV coordinates, joint matrices,
camera and lights. Procedural backgrounds and vector frames are separate
authored layers; the original CGI lighting and cameras were not recovered.
The [Bingo reproduction guide](../scripts/bingo_menu_artwork/README.md) records
the required inputs, source checks and rendering limits. Its small authored
layers are included for reproduction; source models, pack textures and the
external Blender importer are not.

The authoring tools can also reproduce registered Japanese Colosseum HUD and
XD sheet backgrounds from their pinned donors. The recipes retain their own
regional layouts, including Japan's separate sheet dimensions. Source archives
are read without modification; generated replacements live in the party's
versioned HD cache.

## Pokemon portraits

The pinned Colosseum archive contains x4 portraits for all 386 base species,
including their shiny frames and all 28 Unown forms. Some native textures have
two facing directions: these use four cells in an 84x84 atlas rather than
two cells in a 42x84 atlas. The pinned XD archive does not replace the retail
Pokemon face atlases.

Orre can use the Colosseum portraits as donors for XD. The adapter matches
species and form using verified native texture identities, keeps both shiny
frames and fits the art to XD's circular frame. It records the donor's file,
hash and scale; it does not rename files blindly or replace a missing form
with another Pokemon. Castform's weather forms and Deoxys's extra XD forms
have no matching donor in this selection. Nine separately rendered x4 atlases
cover these forms: three Castform weather forms in each game and three Deoxys
forms in XD. They use the actual models and authored HD materials, paired
normal/shiny poses and crops, and the native square or circular frame. Gen3
Castform weather forms retain their original shared normal/shiny colors.
Original mode keeps the native portraits. The
[capture procedure](../scripts/EXTRA_PORTRAIT_CAPTURE.md) and authoring tools
record the source hashes, poses, material recipes and framing; these portrait
renders do not expand the upstream packs' stock 3D material coverage.
XD's HD mode requires the pinned Colosseum pack as well as XD's own pack.
The manager installs missing dependencies together; creation and launch check
both packs even when an older folder has no recorded portrait dependencies.
Both installations are shared across game folders and pinned in new manifests.

Custom Shadow Lugia portraits use separate native/HD head renders with the
actual model materials and fully red eye texture. All four captures replay
the same 86 joint matrices and use the same normalized close-up crop. Their
framing fills the native tile, with violet backgrounds: square in Colosseum
and circular in XD. The native XD shiny portrait merges seven near-identical
background shades to fit its 256-color palette; every foreground pixel,
including antialiasing, remains unchanged. The source hashes, crop, pose and
palette adjustment are recorded in `models/portrait-variants.json`.

The model, portrait and Snag List keep the same saved shiny identity. The DNA
keypad continues to use separate whole-body art, never the head portrait.

## Vector lettering for generated text

The text preparation pipeline uses **Noto Sans JP**, by Google and Adobe,
under the SIL Open Font License 1.1. Its exact upstream revision, font hash,
license hash and drawing recipe are pinned in `hd_text_vectors.py`. The font
and its unmodified license are bundled for offline preparation.

This is adapted vector typography, rather than an enlargement of the game's
glyph bitmaps. Each style uses one horizontal scale, calibrated against the
native A-Z, a-z and digit advances, with the font's side bearings centered in
each original character cell. CJK styles use common full-width proportions.
Letters are never stretched separately to fill their cells. Letter heights,
accents and descenders use a common vertical grid for each style. Transparent
draw margins prevent clipping without changing character advances, text
measurement, alignment or encoded line breaks. The original message layout remains
authoritative. Game-specific symbols use explicit recipes keyed by their
original shapes; an unsupported convention is never replaced with a missing
character box. The native U+FF04 variants use the game's double-stroke
Pokédollar symbol rather than a Unicode dollar sign. Small regional font banks
are included when their complete structure and source bytes validate. Spaces
retain the native advance-only path, including Japanese U+3000.

Regional preparation keeps the captured Latin alphabet and UI symbols resident
on European/USA images. Imported characters outside that corpus retain native
rendering. Japanese images have their own corpus and memory qualification.
The font and recipe credits accompany generated HD text caches. See
[coverage and runtime qualification](HD_COVERAGE.md) for the enabled scope;
successful offline generation alone does not establish correct in-game drawing.

## Versioned storage and downloads

`scripts/prepare_hd_hosting.py` verifies both original ZIPs and stages a single
versioned upload tree with a SHA-256 manifest. This is private preparation;
it does not upload anything or configure a production service. Archives are
kept outside Git and application releases. Both packs total 4,017,710,747 bytes
before HTTP overhead.

The approved [free GitHub hosting](HD_HOSTING_PROPOSAL.md) serves both packs from
a separate, fixed release, with no domain or paid subscription. Its public assets
were checked byte for byte before the application download URLs were enabled.
The read-only `scripts/verify_hd_origin.py` checks HTTP transport and complete
archive identities; `scripts/prepare_hd_github.py` prepares future release assets
without publishing them.

Author credits and distribution terms remain attached to their sources.
The XD author licenses separately linked UI vectors under CC BY-NC-SA 4.0 and
lists several ESRGAN model credits; those statements do not establish a blanket
license to redistribute the complete texture ZIP. Neither archive is relicensed
under this project's MIT license. Public mirroring needs appropriate permissions.
