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

The completed November 19 pass registers 211 menu atlases. Preparation of all
six regional variants produces 297 PNGs, each compared against its approved
or pinned reference. No identified player-menu label atlas remains unmatched
in this selected inventory. This is source coverage, not a replay of every
menu. Forty-five other identities still lack a qualified replacement: model
materials, illustrations and photographs, icons or geometry, effects, debug
controls and the Genius Sonority startup wordmark. Their remaining limits are
listed below.

## Corrections

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
  the original CGI. The registered strip is source-qualified; its full Bingo
  gameplay route has not been replayed under Dolphin. Type charts retain their
  regional layouts and checked Generation III effectiveness values.
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
| Genius Sonority startup wordmark | No verified x4 donor is available in either pinned pack | Keeps the original logo. A smaller web image does not establish an HD replacement. |
| Unqualified bonus, card-reader and debug screens | Their resource exists on disc but its playable route or exact sprite usage has not been established | Uses only registered replacements; other keys remain native. Finding or uploading an atlas does not prove that every cell is displayed. |
| Generated text in older game folders | The ROM was created before the static glyph-page bridge | Retains native text. Recreate a game folder with the same source, seed and complete settings to add the bridge; updating the launcher cannot rewrite an existing ROM. |
| Imported names outside the resident alphabet | Japanese characters in a European or USA game | Uses native glyph fallback. The regional Latin corpus is deliberately bounded to preserve game memory. |
| Unusual adjacent Latin accents | Narrow accented letters repeated together, especially foreign names on Japanese fonts | The game's original advances are retained; some accent marks can touch. The shared proportions do not replace the game's spacing with the donor font's own advances. |
| Extra-form 3D materials | A weather or Deoxys form uses a material absent from the upstream packs | Keeps the pack's existing 3D coverage. The nine new portrait atlases are separate rendered artwork, not a stock 3D texture expansion. |
| Egg and auxiliary portraits | When the UI requests an image outside the registered species/form routes | Retains native art. The audit identified an egg atlas and a Bulbasaur-like placeholder, but did not establish their runtime use. |
| Unmapped stock materials | Their exact texture identity has no verified donor | Retains native art. An unused resource in the inventory does not establish a visible, Pokemon-wide HD gap. |
| Spinda hologram face | Japanese Colosseum, direct ROM launch, or an unavailable companion | Retains the native 128x128 face. The Windows launcher can provide a 512x512 face on qualified Europe/USA revision-0 folders; the separate HD body and spot diagram remain available on Japan. |
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
enlarged into the x4 artwork. Gen3 weather forms retain their shared native
normal/shiny colors.

Spinda's dynamic face is enabled only for Europe/USA revision-0 Colosseum on
Windows. Checks cover two saved PIDs, exact GPU output, native fallback and a
restart within the same Dolphin process. The native five-map material chain,
shiny palette handling and blue filter are retained. Two fenced texture banks
reserve 1 MiB in the game; the host cache is bounded to eight faces (4 MiB).

The Japanese combined fixture froze during loading even with its face hooks
restored to native instructions while retaining that reservation. A new real
creation without the face reservation passes the same saved route. Japan is
therefore excluded from both hook installation and companion activation; its
face stays native. A donor lookup or plausible image does not qualify an adapter.

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
