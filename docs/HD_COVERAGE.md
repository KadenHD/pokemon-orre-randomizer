# HD coverage and limitations

HD mode replaces textures while retaining the native meshes, animations and
game logic. It is optional. A sharp HUD frame does not imply that every label,
dialogue, portrait or screen has a high-resolution replacement.

The isolated HD profile uses 3x internal resolution and linear texture filtering.
Original mode restores native resolution and filtering. Neither setting changes
the source ROM or the user's regular Dolphin profile.

## Verified scope

The November 18, 2026 audit reads the six original revision-0 regional discs,
without modifying them. Its expanded menu-resource inventory contains 3,383
member/texture references and 616 unique texture identities from selected
menu, common, title, P-AD, battle and bonus archive families. It also inventories
527 Colosseum and 602 XD PKX model resources on the European discs. Those model
resources include people and technical objects, not just Pokemon.

This is a static inventory, supplemented by separate native and HD Dolphin
replays. It is not a full playthrough of every screen in every language. Shared
keys occur in several archives and regions. The baseline below counts unique
keys before Orre's registered additions, rather than percentages of visible UI.

| Game / region | Playable languages | Menu-resource keys | In the game's pack | Only in its required companion |
| --- | --- | ---: | ---: | ---: |
| Colosseum Europe | English, French, German, Italian, Spanish | 255 | 209 | 0 |
| Colosseum USA | English | 151 | 124 | 0 |
| Colosseum Japan | Japanese | 150 | 98 | 0 |
| XD Europe | English, French, German, Italian, Spanish | 326 | 149 | 24 |
| XD USA | English | 265 | 154 | 24 |
| XD Japan | Japanese | 233 | 131 | 26 |

These are verified physical pack-key matches, not runtime or visual-quality
certificates. Across all regions, 359 of the 616 identities have an exact key
in either pinned pack. Orre's localized derivatives and reconstructed menu
artwork are additional routes, recorded in the bundled catalogue and prepared
cache. A resource without a match is not necessarily visible in normal play.
Inactive regional tables, card-reader content and debug controls are classified
separately. Files for inactive locales do not add playable language support.
The expanded inventory includes texture references embedded in menu DAT
resources; it excludes generated glyph-page caches and prerecorded video.
The visual review also checks words inside resources initially classified as
icons or illustrations, including the Japanese main menu, START and VS sprites.
An archive or category name alone does not establish that it contains no text.

The extended November 19 pass registered 228 menu atlases. Its preparation of
all six regional variants produced 328 PNGs, each compared against its approved
or pinned reference. The November 20 addition brings the catalogue to 229
recipes: a reviewed vector reconstruction of the Genius Sonority wordmark,
under its identical native texture key in all six regional discs. This is the
separate white-background UI resource, not the normal startup movie. Its actual
UI use has not yet been established. No identified player-menu label atlas
remains unmatched in the selected inventory. This is source coverage, not a
replay of every menu.
Thirty-seven other identities in the original 616-key sample still lack a
qualified replacement: model materials, illustrations and photographs, icons
or geometry, effects and debug controls. The wider archive pass also adds five
European XD health-notice pages outside that sample. It identifies other
stock-material gaps, described separately below.

## Wider archive inventory

The follow-up reads every non-movie FSYS archive in the six existing generated
revision-0 QA images. It inspects bounded flat GX textures, HSD model DATs and
PKX models, retaining duplicate archive references separately from unique keys.
These are QA-image inventories, not original-disc or visible-screen completion
percentages. Other native resource kinds and runtime-generated textures retain
their separate qualification requirements.

| QA game / region | Non-movie archives read | Parsed unique texture keys | No exact key in the prepared overlays or either pack |
| --- | ---: | ---: | ---: |
| Colosseum Europe | 1,981 | 6,248 | 253 |
| Colosseum USA | 1,852 | 6,144 | 254 |
| Colosseum Japan | 1,852 | 6,144 | 260 |
| XD Europe | 2,583 | 6,708 | 360 |
| XD USA | 2,512 | 6,631 | 347 |
| XD Japan | 2,475 | 6,604 | 353 |

These existing QA-image inventories are reconciled against the current validated
overlay caches, retaining the pinned-pack matches. The 15 weather-material keys
per Colosseum region and 43 weather/Deoxys keys per XD region are now covered;
no previously registered overlay key was lost. This reconciliation adds no
new claim about which stock forms appeared in gameplay.

The counts include stock trainers, auxiliary models, maps, effects and inactive
resources. A missing exact key is a triage candidate: optional mipmap-name
aliases and dynamic contracts need separate inspection. Presence of a file
alone establishes neither visibility nor artistic quality. All selected-layout
members parse after accounting for RGB565 as well as RGB5A3 palette banks.
Movies are excluded, and the six QA-image hashes remain unchanged.

## Corrections

- **Castform battle portraits:** new randomized ROMs select the portrait from
  the currently loaded battle model in both games. Ordinary specimens retain
  their retail resources. Shiny specimens select separate authored models and
  portraits using the modern weather-form colors. The
  normal/shiny atlas row follows the specimen's native face selection. The
  loader requests a missing texture asynchronously and keeps the original
  portrait visible until it is ready. Forecast remains on Castform and is
  excluded from other species' randomized abilities. Weather suppression and
  the return to normal use the loaded model, rather than assuming that global
  weather always determines a Pokemon's appearance.
  The HD Sunny Form portrait uses a wider crop from the same GPU render, with
  the visible model at 80% of its previous size. Normal and shiny cells use the
  same crop; native frames and image orientation remain unchanged.
  Every added native material and portrait has an exact-key x4 counterpart.
  Native/HD preparation validates decoded native RGBA and source-paint hashes;
  an unknown or missing route blocks HD readiness. The stock 43-material and
  nine-retail-portrait catalogues retain their identities.
- **Colosseum Options stripes:** the five European layouts, USA and Japan
  retain their native two-pixel stripe geometry without the compressed HD
  donor's ragged alpha edges. Each derivative keeps every donor RGBA pixel
  outside the native y200..255 band unchanged.
- **European XD notices:** all five original health-notice pages have x4
  vector replacements. Each retains its own original wording, line positions,
  warning symbol and historical printed URL. The CI4/RGB565 native identities
  are recorded explicitly; these pages were outside the earlier menu filter.
- **European XD sheet headings:** native ink measurements now exclude the
  accent from the adjacent heading. A clear row separates the Status and Info
  sprites, preventing the former heading from appearing above the latter
  with linear filtering. Remaining title pixels are also removed from the
  shared captionless donor above Status. The five languages retain their
  original UV layout, accents and genuine HD frame pixels.
- **Additional menu geometry:** seven original identities now have measured
  x4 vector replacements: Colosseum's battle-menu separator and tall storage
  frame, plus XD's unknown-species marker, battle-panel mask, hologram sheen,
  name-entry computer symbol and simulator indicator. Native sprite canvases,
  transparent holes and translucent panels are retained. The sheen is a new
  analytic gradient, not an enlarged native texture. These are source-qualified
  derivatives; preparation does not establish that every sprite is visible in
  the replayed routes.
- **Genius Sonority wordmark:** a new x4 vector reconstruction retains the
  retail white canvas, navy color, lettering silhouettes, spacing and curved
  divider. Its complete paths reproduce offline without a native bitmap or
  system font. The native member and decoded-image identities match all six
  regional discs. This is the separate white-background UI sprite, identified
  as element `0x03A7` in XD. Its actual use remains unproven; it is not declared
  unused. The normal Genius Sonority startup sequence is a 640x480 THP movie
  and remains original. This vector is reviewed authored artwork, not a newly
  discovered official source or upstream pack donor.
- **Missing shared materials:** the launcher can use exact missing keys from
  an already-required companion pack. The game pack wins over its companion;
  custom overlays win over both. Source installations are unchanged and old
  views remain available to running games.
- **European XD HP/level artwork:** five localized atlases use the actual XD
  HD donor, with vector labels matching English, French, German, Italian and
  Spanish. Only two label regions change; gauge pixels and alpha elsewhere
  remain identical to the donor. These files are checked with the immutable
  custom cache. See [sources and credits](HD_SOURCES.md#localized-xd-status-atlases).
- **Japanese Colosseum atlas equivalents:** two native RGBA8 keys have
  pixel-exact RGB5A3 equivalents in the pinned pack. Their proven donors can
  be registered under the native keys after checking the original format's
  quantization. These are registered derivatives, outside the exact-key counts
  in the table; they do not imply coverage of every Japanese screen.
- **Generated text:** new game folders retain authenticated native glyph pages.
  HD mode draws vector lettering from a pinned, openly licensed font while
  preserving the game's advances, baselines, colors and dialogue layout.
  Original mode draws native glyphs. The pages are captured during creation;
  switching graphics later does not require the source ROM. This is adapted
  typography rather than an enlargement of the original bitmap alphabet.
  See [font sources](HD_SOURCES.md#vector-lettering-for-generated-text).
- **Localized menu artwork:** registered native identities cover type/status
  badges, P-AD and PC captions, XD Pokémon sheets and battle controls. Layouts
  retain their own translated labels and sprite cells; Japanese sheets use
  their separate dimensions. Existing HD frames, gauges and icons are kept
  outside the changed regions. Missing simple shapes use recorded vector
  geometry, with the source and derivative roles kept distinct.
- **XD VS illustrations:** separately recreated scenes use real character
  meshes and authentic GameCube/GBA photographs. They keep the original image
  windows and regional labels. They are composed artwork, not replacements
  found unchanged in the upstream pack.
- **Link-mode hardware:** controller, handheld and console sprites use verified
  pack artwork, scaled uniformly inside each native sprite cell. The Japanese
  connection layout retains its different positions and extra cable. XD's
  small console symbol uses the real front-facing HD console from the link
  menu; its perspective differs from the original tiny isometric illustration.
- **XD Bingo artwork:** the eleven pre-rendered portraits are separately
  reconstructed from the game models with exact pinned x4 material donors.
  Native-material and HD renders share pose, camera and visible geometry.
  Frames and backgrounds are newly authored, and their lighting differs from
  the original CGI. A recorded European HD replay displays the card-selection
  menu and type chart, wins one duel and returns to the grid with its EP result.
  This does not qualify a complete card or its final result screen. Type charts
  retain their regional layouts and checked Generation III effectiveness values.
- **Player-selection artwork:** Colosseum's player portraits are reconstructed
  from the actual Wes and GBA protagonist models. Native and x4 renders share
  framing and geometry; Red and Leaf use recorded shoulder poses. The layouts
  retain each region's player order, hardware and labels. A shared analytic
  lower-edge fade blends the portraits into both large and small sprite cells.
  These renders differ from the original CGI. Wes uses verified HD materials;
  the four GBA protagonists retain their native material maps where no exact
  HD donor is available.

## Remaining limits

| Element | When the limit applies | Current behavior |
| --- | --- | --- |
| Other localized UI atlases | When a screen uses a key absent from both selected packs and the registered derivatives | Uses the original texture. Only registered identities are replaced; adding one atlas does not cover unrelated screens. |
| Separate Genius Sonority UI sprite | The white-background resource is present on all six discs but its actual UI use remains unproven | Its matching key has a reviewed x4 vector drawing. This does not replace the normal startup logo, which is an unchanged 640x480 THP movie. |
| Western XD end cards | Localized game logos have no qualified x4 counterpart in the selected sources | Keeps the original localized artwork and lettering. These static end cards are separate from the unchanged movie files. |
| Unqualified bonus, card-reader and debug screens | Their resource exists on disc but its playable route or exact sprite usage has not been established | Uses only registered replacements; other keys remain native. Finding or uploading an atlas does not prove that every cell is displayed. |
| Generated text in older game folders | The ROM was created before the static glyph-page bridge | Retains native text. Recreate a game folder with the same source, seed and complete settings to add the bridge; updating the launcher cannot rewrite an existing ROM. |
| Imported names outside the resident alphabet | Japanese characters in a European or USA game | Uses native glyph fallback. The regional Latin corpus is deliberately bounded to preserve game memory. |
| Unusual adjacent Latin accents | Narrow accented letters repeated together, especially foreign names on Japanese fonts | The game's original advances are retained; some accent marks can touch. The shared proportions do not replace the game's spacing with the donor font's own advances. |
| Egg and auxiliary portraits | When the UI requests an image outside the registered species/form routes | Retains native art. The audit identified an egg atlas and a Bulbasaur-like placeholder, but did not establish their runtime use. |
| Castform portraits in older or unchanged ROMs | A ROM predates the live HUD patch, or was created with no randomization or gameplay changes | Keeps the native portrait behavior. Updating the launcher alone does not add the patch; create a new randomized ROM to install it. |
| Unmapped stock materials | Their exact texture identity has no verified donor | Retains native art. An unused resource in the inventory does not establish a visible, Pokemon-wide HD gap. |
| Spinda hologram face | Direct ROM launch, an unavailable companion, or an older folder without the native bridge | Retains the native 128x128 face. New Europe, USA and Japan revision-0 Colosseum folders support a 512x512 face through the Windows launcher. |
| Prerecorded movies | Opening and other video files | Keeps the original video. Texture packs do not increase its resolution. |
| Geometry, animation and HQ audio | All HD mode usage | These packs add no polygons, replacement animation or high-quality audio banks. |
| Direct ROM launch | Opening an ISO, RVZ or GCM outside the configured launcher | Native custom models remain in the ROM; external HD files require Dolphin's matching texture profile. |

Newly authored custom assets follow a stricter rule: missing required HD donors
block HD preparation with a diagnostic instead of silently substituting a
filtered native enlargement. Original mode remains available without packs.

Castform's three weather portraits in each game and Deoxys's three extra-form
portraits in XD have reviewed normal/shiny renders, common poses and paired
crops. Their exact native keys and immutable artwork hashes are checked at
preparation. Original mode retains the source portraits. The authoring tools
also record the rendering and material versions; no native portrait RGB is
enlarged into the x4 artwork. Retail Gen3 weather atlases retain their original
shared palette. Newly created randomized ROMs add separate rare resources with
modern colors, preserving the ordinary materials and per-specimen identity.
The same 43 reviewed material PNGs cover the stock
weather models in both games and the additional Deoxys forms in XD, under
their observed regional native keys. This changes neither native meshes nor
animation and does not add forms absent from a game's native mechanics.

Spinda's dynamic face is enabled for Europe, USA and Japan revision-0 Colosseum
on Windows. Checks cover two saved PIDs, exact GPU output, native fallback and
a restart within the same Dolphin process. The native five-map material chain,
shiny palette handling and blue filter are retained. Europe and USA use two
fenced texture banks (1 MiB); Japan uses a compact single bank (512 KiB),
released by the native GPU fence before the host writes another face. The host
cache is bounded to eight faces (4 MiB).

The Japanese combined creation now loads with the generated-text bridge and
HD materials together. Its two successive saved samples display the correct
shiny and ordinary appearances, different PIDs and exact 512x512 GPU textures.
Stopping and restarting the companion restores the same second face. The native
registry also retires old entries when a face allocation reuses a pixel pointer,
preventing the previous sample's pattern from being selected again.

Older Europe/USA folders retain their original wrapper contract. Recreate a
game folder to install the new native registry fix or the Japanese bridge;
updating the application alone does not rewrite an existing ROM.

## Runtime qualification

Clean European English replays of both games boot actual `create_game_folder`
outputs in Original and HD modes. Party and summary menus display Pokemon
names, ability descriptions, locations and statistics in both modes. The
original 512-pixel glyph pages match the captured native bytes, and their
2048-pixel HD replacements match the immutable cache. Native hit counters
advance without glyph fallback in the observed screens.

All six revision-0 regional discs also pass offline font capture and HD page
generation with no missing registered codes. That source check alone does not
qualify regional gameplay, memory pressure or every translated message. The
Japanese corpus occupies more pages and requires its own runtime qualification.
The investigated Colosseum Japan fallback draws are U+3000 ideographic spaces
with zero height. They advance the cursor without drawing a visible quad;
they do not indicate missing HD kanji. The corrected laboratory replay recorded
2,410 such draws and no native fallback quad with nonzero geometry. Diagnostics
retain the raw counter and report these two geometry classes separately. A
nonzero-geometry fallback is a candidate for inspection, not proof that a
visible character is missing. This witness does not qualify every message.

New capture also includes structurally valid font banks containing fewer than
20 glyphs. These supply regional Pokédollar and punctuation variants. Existing
authenticated glyph guides remain readable with their recorded coverage;
adding these native identities requires recreating the game folder. Updating
the launcher alone does not add a new bridge to an older ROM.

Additional current-bridge replays cover the Japanese P-AD, mail and bag in both
games, plus French XD. Their field loads and menu routes were inspected from
actual screenshots. Colosseum Japan recorded 16,538 native fallback calls,
all with zero-area geometry, and no nonzero-area fallback; XD Japan and French
XD recorded none. This qualifies those observed routes and captured text,
rather than every static label or translated screen. Later catalogue additions
are checked separately from these replay checkpoints.

The current Japanese XD PDA artwork has its own later replay: the main menu,
mailbox header, envelope and bag were inspected with the registered replacements
loaded. The observed generated-text draws again had no native fallback. This
qualifies those displayed routes, including the newly authored static captions.

The English XD VS menu has also been checked in Dolphin with the recreated
character illustrations, authentic GameCube controller and Game Boy Advance
photos, and localized menu atlas. The [captured screen](images/hd-xd-vs.png)
comes from the actual prepared game folder, rather than an artwork mockup.
The isolated linear-filter profile has also been replayed on the Japanese
Colosseum main menu and the English XD VS and team-selection menus. Unscaled
captures confirm smoother static lettering without a replacement ROM texture
or a change to the regular Dolphin profile.
The English XD replay also reaches active moves after the native trainer and
send-out dialogue. HP/level frames, type badges, ability and item labels, START
and controller symbols were inspected together with the selected move list.

French XD Quick Battle also reaches the battle HUD with localized PV/level,
J1/ORDI badges, type labels, abilities and active moves. Small labels were
checked in unscaled capture crops, alongside a separate Original-mode replay.
This is an observed battle/menu witness, not a replay of every battle type.

These checks use private Dolphin profiles, copied QA cards and **No Audio
Output**, with input hashes checked afterwards. They do not certify every
battle, scene, region or language.

The November 19 extension adds these observed HD routes:

| Edition | Captured screens |
| --- | --- |
| Colosseum USA / English | Party, summary, stats, P-AD, Snag List, mail and bag |
| XD USA / English | Party, summary, stats, P-AD, Snag List, mail and bag |
| Colosseum Japan / Japanese | Party, summary, stats, P-AD, Snag List, mail and bag |
| XD Japan / Japanese | P-AD, Snag List, mail and bag; party and summary repeated after the nurse's scripted movement |
| Both European games / German, Spanish, Italian | Party, summary, stats, P-AD, Snag List, mail and bag |
| XD Europe / English | Native startup sequence and the new health-notice replacement |

No load freeze or visible missing generated glyph was observed on these routes.
The Colosseum Japanese replay recorded 3,952 native calls with zero-area
geometry and no nonzero-area fallback. Other listed replays recorded none.
These counters describe the captured text, not every line on each disc.
Early USA load-confirmation and Japanese nurse-lock captures are diagnostics;
only their successful subsequent menu replays qualify the party screens.

The final European XD background cleanup has separate French and Spanish
summary replays. Full-size captures retain the title accents without the old
strips of lettering above the heading. All five European recipes also pass
rendered gutter and unchanged-frame checks. A final English XD Quick Battle
reaches active moves with the new translucent command mask, localized badges,
HP/level labels, ability and item labels and controller symbols displayed.

Read-only host-process memory sampling on the Japanese XD party route recorded
a peak working set of 1.32 GiB and peak sampled private bytes of 1.64 GiB.
These are Dolphin process measurements, not GameCube heap or GPU-memory bounds.
All six QA-image hashes and the source-card hashes remain unchanged. The
original movie archives are neither replaced nor re-encoded.

Castform's live HUD patch has separate European Dolphin replays in both games,
using artificial weather teams on copied QA cards. HD captures show sun, rain
and hail portraits matching the loaded models in Colosseum singles and XD
doubles. Original-mode captures also show the changing native artwork. The XD
replay returns from a weather form to the normal model and all four normal HUD
portraits after Sandstorm. The Colosseum replay captures its normal model during
that reset, before the opponent changes the weather again.
The patch retains native draw arguments and HUD orientation. Colosseum mirrors
the player's portrait as in the original renderer; HD texture orientation is
unchanged. The portrait artwork board shows the registered texture orientation;
the renderer still applies each side's original UVs.

All six revision-0 executables pass guarded offline installation, including
composition with the Shadow Lugia portrait hooks. Executed PowerPC-wrapper
tests cover normal/shiny atlas selection, loading already in progress, missing
textures, invalid battle pointers and fallback to the original draw call.
These checks do not replace regional gameplay replays. The earlier retail-only
replays preceded the additional modern shiny weather colors. The copied source
cards and input images remain unchanged, and
the original opening videos are retained.

The new weather artwork has a separate source-qualified European Colosseum
viewer replay for each form in native and HD paint. Original meshes, cameras
and frozen joint poses are retained. The shiny portrait cells come from actual
GPU renders, not a recolored finished bitmap. Native eyes still blink; the
static Snowy portrait uses its captured open-eye frame. Those viewer aliases
qualify artwork, separately from the native battle resource/cache selection.

The appended portraits retain each game's native frame. Colosseum uses its
RGBA8 atlas. XD uses RGB5A3 within its fixed 8,032-byte face-cache slot, with
zero padding through the native copy boundary. Its original normal cell and
both circular alpha masks remain exact; the new shiny cell rounds to the
native color precision. The HD portrait keeps the full-color x4 render.

Separate European story-battle replays now qualify all three modern shiny
weather forms in both games, in Original and HD modes. Each copied party has
one normal and one shiny Castform together. Read-only native-cache inspection
confirms distinct model resources for every pair and exact source DATs after
relocation is removed. Original-mode GPU dumps match all six registered face
atlases pixel for pixel. The corrected XD captures retain both complete
circular cells, with no truncated or missing shiny portrait.

The HD replays also let hail expire: the normal Castform returns to gray and
the shiny one to pink, with matching normal-form portraits. Colosseum then
changes back to sunshine without losing either specimen's identity. These
checks preserve the native PIDs, original meshes and animations. They use
muted isolated Dolphin profiles and copied QA cards; they do not certify every
regional battle or modify existing user ROMs and saves.
