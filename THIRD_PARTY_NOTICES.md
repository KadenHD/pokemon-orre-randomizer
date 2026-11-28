# Third-party software

The project's own source code is licensed under MIT (see LICENSE). That license
does not cover Nintendo game software, user-supplied images, or third-party libraries.
No ROM, saved game or Dolphin executable is included. The bundled interface pack
contains exported game images and audio, as described below. The public and local
editions include that verified pack. Its provenance and rights are separate
from the application's MIT license.

The **Eclipse** application icon in `orre_randomizer/assets/app/` is original
abstract artwork generated with the built-in image_gen tool and selected for this
project. It is included under the project's MIT license. Its master PNG, ICO,
prompt and file hashes accompany the sources; it is not extracted from a game.
The approved Orre wordmark uses the same original icon and is included under the
same license. Its transparent PNG, generation prompt and hash are recorded in
`orre_randomizer/assets/app/logo.json`.

## Independent music renderer and external HD packs

### Controller photograph

`orre_randomizer/assets/app/controller.png` is the standard indigo GameCube
controller photographed by Evan-Amos, with background removal by Alphathon.
Source: [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:GameCube_controller.png).
It is included unchanged under [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/),
independently of the application's MIT license. Qt scales it proportionally at
display time. Its source URL, authors, license and SHA-256 are recorded in
`controller.json`. No endorsement by its authors or Nintendo is implied.

### Music renderer and texture sources

The optional native music renderer uses the CC0-1.0
[AxioDL MusyX reimplementation](https://github.com/AxioDL/musyx), pinned to
commit `717404d77c17a95dd101bbe737d0f9549ab600e6`. The adapter, exact build inputs,
patches and provenance are in `native/music/`, `scripts/build_music.py` and
`licenses/music/`. The source archive is verified before building. No original
game music banks are shipped with this renderer; supported banks are extracted
locally from a verified user-supplied ROM into its shared cache. Original game
audio remains subject to its respective rights.

Optional texture packs come from their original community authors:
[Colosseum HD Pack V2, credited to Sephie](https://www.reddit.com/r/DolphinEmulator/comments/sxzxi2/)
and [Pokémon XG/XD HD Texture Pack v1.0 by mikeyX](https://forums.dolphin-emu.org/Thread-pokemon-xg-xd-hd-texture-pack-v1-0).
The application pins exact author archives and hashes in `orre_randomizer/hd_packs.py`.
See [HD sources](docs/HD_SOURCES.md) for credits, archive selection and storage.
Their authorship, game artwork rights and distribution terms are independent
of this project's MIT license. No complete HD pack or Dolphin executable is
bundled in the Orre application. Generated custom x4 overlays do not transfer
ownership of the underlying game assets. See [game-folder storage and texture
priority](docs/GAME_FOLDERS.md).

The localized XD HP/level atlases and registered menu derivatives use mikeyX's **Pokemon XD UI SVGs
V1.0** and the pinned XD pack. The vector source archive has SHA-256
`c575a04cb5044a41df620e92557cd6bd5d72fb9c3ad4e726dacf972def262616`.
The original [license](licenses/hd/mikeyX-ui-license.txt) and
[README](licenses/hd/mikeyX-ui-readme.txt) are preserved. This artwork is
CC BY-NC-SA 4.0, with the author's exception for inclusion in Pokemon
hacks/mods/patches; its NonCommercial restriction remains in effect. The
localized labels change the original English lettering, using captured
Bahnschrift outlines matching the SVG typography. No font file is bundled.
The derived artwork is separate from this project's MIT-licensed code.

Additional localized type/status badges and timer captions retain native
regional identities and measured atlas rectangles. Their Japanese outlines use
the pinned Noto Sans JP/OFL donor described below. Geometric additions without
an HD donor are separately authored vectors based on measured native guides;
they are not credited as pixels from an upstream PNG. The menu catalogue and
prepared cache retain these distinctions and the donor hashes. See
[menu artwork sources](docs/HD_SOURCES.md#localized-menu-artwork).

The recreated XD VS illustrations use original game character meshes, recorded
poses and separately credited material maps. Their photographic components
retain their own terms: the GameCube controller photo is credited above under
CC BY-SA 3.0; the
[Game Boy Advance photo by Evan-Amos](https://commons.wikimedia.org/wiki/File:Nintendo-Game-Boy-Advance-Purple-FL.png)
was released into the public domain through the Vanamo project. The photos are
proportionally reduced and composed with the actors; the GBA is also rotated.
Cable extensions are separate artwork. Source identities, credits and changes
are recorded in `menu-atlases/vs-scenes.json`. The game meshes and material maps
remain separate from the MIT code license.

The recreated XD Bingo portraits likewise retain the original Pokémon mesh
rights and mikeyX's HD material credits. Their backgrounds and vector frames
are separately authored layers. Recorded sources, changes and rendering limits
accompany `menu-atlases/bingo-scenes.json` and the
[portable authoring guide](scripts/bingo_menu_artwork/README.md). These
compositions do not relicense the source games or upstream texture pack.

Pillow 13.0.0 decodes PNG and DDS source textures when preparing custom HD
overlays. Its MIT-CMU license and bundled dependency notices are preserved in
`licenses/images/Pillow-LICENSE.txt`. The application restricts this reader to
PNG and DDS; original compressed pack textures remain unchanged on disk.
Source: [Pillow](https://github.com/python-pillow/Pillow/tree/13.0.0).

The bundled `models/dark-lugia-body-x4.png` and shiny counterpart are whole-body
renders of the original game mesh with materials derived from the pinned XD
HD pack. Their model identity, HD donor hashes and capture method are recorded
in `models/hd-fullbody-manifest.json`. These derivative images remain separate
from the code's MIT license, as do their native-resolution counterparts.
The matching `models/dark-lugia-head-x4.png` and shiny head are crops of those
same pack-textured GPU captures; their parent hashes and crop are in that manifest.

The Legendary and Mythical Shadow appearance archive contains material patches,
portraits, Colosseum DNA artwork and recolored maps derived from the pinned HD
packs credited above. The patch verifies the matching game model before applying
the materials. The underlying artwork remains separate from the MIT code license.

## Qt for Python / Qt / Shiboken

The desktop application uses unmodified PySide6 Essentials and Shiboken 6.11.2,
including QtCore, QtGui and QtWidgets, under the LGPL version 3 option. Qt libraries
are dynamically loaded from the `_internal` directory in the Windows distribution.
You may replace them with compatible modified builds and rebuild this application
from the accompanying source archive. No restriction is imposed on reverse
engineering for debugging modifications to those libraries.

License texts and upstream notices are in `licenses/`. Upstream source and build
instructions for the corresponding versions are available at:

- https://code.qt.io/cgit/pyside/pyside-setup.git/?h=v6.11.2
- https://code.qt.io/cgit/qt/qtbase.git/?h=v6.11.2
- https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.11.2-src/
- https://download.qt.io/archive/qt/6.11/6.11.2/submodules/
- https://doc.qt.io/qtforpython-6/building_from_source/index.html

The `third-party-sources` directory contains the corresponding unmodified QtBase,
QtSvg and PySide/Shiboken source archives for 6.11.2. Their upstream URLs and
SHA-256 hashes are recorded in `licenses/qt/upstream-manifest.json`. Keep these
sources and all upstream notices with a published binary distribution.
Public releases include this verified interface pack; its contents remain separate
from the MIT license of the application code.
Official licensing reference: https://www.qt.io/development/open-source-lgpl-obligations

## Windows installer

The Windows setup EXE is built with [Inno Setup 6.7.3](https://github.com/jrsoftware/issrc/releases/tag/is-6_7_3)
by Jordan Russell and Martijn Laan. The installer extracts the same application
files, replaceable Qt libraries, corresponding sources, and notices as the portable ZIP.

## Python and PyInstaller

Python 3.12 is distributed under the PSF license and its included notices
(`licenses/Python-LICENSE.txt`). PyInstaller 6.22.3 uses the GPL with its bootloader
exception, reproduced in `licenses/PyInstaller-COPYING.txt`; that exception permits
building an application under its own license.

## Pokémon, type, move, ability and evolution-item names

The French, English, German, Spanish, Italian and Japanese names for national
species #1–386, plus the 17 Generation III type names, are selected from the PokéAPI
data repository: https://github.com/PokeAPI/pokeapi/blob/master/data/v2/csv/pokemon_species_names.csv
The copyright notice, redistribution conditions and disclaimer are reproduced
in `licenses/pokeapi.txt`. The downloaded source hash and selection are recorded
in `licenses/pokeapi-names.json`. No API request is made by the application.

The v0.15 detail sheets and offline HTML journal also include presentation-name
fallbacks for Generation III moves #1–354, abilities #1–77 and twelve evolution
items, in the same six languages. The source tables are:

- https://github.com/PokeAPI/pokeapi/blob/master/data/v2/csv/move_names.csv
- https://github.com/PokeAPI/pokeapi/blob/master/data/v2/csv/ability_names.csv
- https://github.com/PokeAPI/pokeapi/blob/master/data/v2/csv/item_names.csv

These selections are stored in `orre_randomizer/locales/detail_names.py`.
Their source SHA-256 hashes, language IDs, item-ID mapping and generated-file hash
are recorded in `licenses/pokeapi-details.json`. They use the same BSD 3-Clause
terms and copyright notice reproduced in `licenses/pokeapi.txt`; retain that file
and both provenance manifests with source and binary distributions.

The fallback catalogs supply display names only. Species properties, move
properties, evolution methods, conditions, learnsets and TM compatibility are
read from the final patched ROM rather than taken from a modern online Pokédex.
Available native ROM name banks are used by the corresponding readers before
fallback names. No ROM bytes, portraits or audio are part of these name catalogs,
and using the sheets or journal does not contact PokéAPI.

## Rust codec

The optional LZSS codec in `native/` is this project's MIT code, with no third-party
Rust crates. The bundled DLL is built using Rust 1.93.1 and includes parts of the
Rust standard library. Upstream copyright and license notices are preserved in
`licenses/rust/`. Its source and build instructions accompany this project.

## Integrated disc converter

`native/disc/` links [nod](https://github.com/encounter/nod), version
2.0.0-alpha.11, at revision `481f50d76078ca602d4858d53778c24eed7d79ee`.
nod is dual-licensed MIT OR Apache-2.0; this distribution uses the MIT option.
The library reads ISO/GCM/RVZ and writes lossless RVZ with Zstandard compression.
It is compiled into `orre_disc.dll` with its compression dependencies linked
statically. It contains no game data and is separate from Dolphin.

The pinned dependency versions and upstream sources are recorded in
`native/disc/Cargo.lock`. Copyright notices and license texts for the compiled
Rust crates and bundled compression sources accompany the application in
`licenses/disc/`, with a machine-readable dependency inventory. The build collects
these from the exact dependency sources used on the target platform.

## Format research

The binary formats were implemented in this project from local observations.
Community references, including Pokemon-XD-Code, are linked in the research
documentation. Their code and game data are not copied into release archives.

Pokémon, Nintendo and their associated names belong to their respective owners.
This project is independent and is not an official Nintendo product.

## Game interface pack

`orre_randomizer/assets/game/` contains images and audio exported from the user-supplied Colosseum
ROM and the English XD logo exported from the supplied XD disc. These game resources are not covered by the MIT license
of the application code. Their hashes, source identifiers and transformations are
recorded in `orre_randomizer/assets/game/provenance.json`. No ROM, BIOS or saved game is included.

The Pokémon sheets use localized type badges extracted from the original
Colosseum and XD games. The source archives, texture locations and hashes are
recorded in the [type badge manifest](orre_randomizer/assets/game/types/manifest.json).
The sheets also display original ability descriptions from the six game language
banks. The [ability catalog](orre_randomizer/assets/game/text/ability-descriptions.json)
records the source archive and member hashes.
The [move catalog](orre_randomizer/assets/game/text/move-descriptions.json)
records the original descriptions and their message banks, including the texts
specific to each game's Shadow moves.

The optional Colosseum postgame event uses XD's original Shadow Lugia model.
This is also a game resource, separate from the code's MIT license.
The PKX container and animation scheduling metadata are adapted for Colosseum
while retaining the original mesh, textures and DAT animation tracks. A custom
shiny variant swaps the original body and belly material colors and darkens
the belly texture. Native and x4 portraits use separate GPU head renders with
the model's normal or shiny materials, matched poses and game-specific frames.
Their capture identities and transformations are recorded in the
[portrait manifest](orre_randomizer/assets/game/models/portrait-variants.json).
These modified game resources
remain separate from the application's MIT license.
The verified disc hashes, resource identifiers,
conversion and output hashes are recorded in the
[model manifest](orre_randomizer/assets/game/models/manifest.json).
The local export script requires both original game images; neither image,
their archives nor their executables are distributed.

Additional Castform and Deoxys form portraits use the original model geometry
with pack-derived or separately authored x4 materials. Their normal and shiny
renders, framing, material sources and hashes are recorded in
`orre_randomizer/assets/game/models/extra-portraits/extra-portraits.json`.

The Deoxys forms imported into Colosseum retain XD's original standard/rare
meshes, skeletons and DAT animation tracks. Their container adapters and
separately rendered native/x4 head and whole-body images are recorded in
[`deoxys-assets.json`](orre_randomizer/assets/game/models/deoxys/deoxys-assets.json).
The x4 material recipes use the pinned XD HD pack credited above. These
game-derived resources remain outside the source code's MIT license.
The authoring and composition scripts are included with the application source.
These rendered game assets remain separate from the code's MIT license.

The home screen additionally uses the original transparent English game logos
hosted by Bulbagarden Archives, copied without pixel changes:

- [Pokémon Colosseum logo](https://archives.bulbagarden.net/wiki/File:Pok%C3%A9mon_Colosseum_logo.png)
- [Pokémon XD: Gale of Darkness logo](https://archives.bulbagarden.net/wiki/File:Pok%C3%A9mon_XD_logo_English.png)

These logos remain the property of their respective owners and are separate
from the application's MIT license. Retrieval date, source URLs, dimensions and
SHA-256 hashes are recorded in `orre_randomizer/assets/game/interface/home-logos.json`.
They are bundled for offline display; the application does not contact these sites.

The interface music includes native renders of the Colosseum and XD title themes
and Colosseum's Pyrite Town theme. The corresponding game sources, capture
intervals, transformations and file hashes are recorded in the
[music asset metadata](orre_randomizer/assets/game/music/).

## Fairy reference data and badge artwork

The optional Fairy rules use a selected dataset from
[PokeAPI/pokeapi](https://github.com/PokeAPI/pokeapi/tree/de6760be38b60a3024f1d9054330ff265f0dc619),
pinned to commit `de6760be38b60a3024f1d9054330ff265f0dc619`. Its
[BSD 3-clause license](orre_randomizer/assets/rules/fairy/LICENSE-PokeAPI.txt),
source identities and extraction policy accompany the bundled dataset in
[`assets/rules/fairy`](orre_randomizer/assets/rules/fairy/README.md).
The reference is Brilliant Diamond / Shining Pearl; no external data is fetched
when generating a game. Names and game descriptions retain their original rights.
The separate `transfer-messages.json` records six original XD refusal messages
used to keep unsupported new moves out of GBA transfers. That game text remains
outside the PokeAPI BSD license and the project's MIT code license.

The six-language Fairy badges are newly authored vector artwork following each
game's original badge layout. Native and x4 images are rendered independently,
using the Noto Sans JP font and its SIL Open Font License. Their source recipe,
font identity, dimensions and image hashes are recorded in
[`fairy-badges.json`](orre_randomizer/assets/game/types/fairy-badges.json).

## HD text typography

The optional HD text renderer uses Noto Sans JP by Google and Adobe, distributed
under the SIL Open Font License 1.1. The font and its unmodified license are
bundled in `orre_randomizer/assets/game/fonts/`. The original game's character
advances, baselines and message layout are retained; the HD lettering uses
adapted vector typography. It is separate from the application's MIT license.
The exact upstream revision and file hashes are recorded in
`orre_randomizer/hd_text_vectors.py` and the interface asset provenance.

## Widescreen camera recipes

The launcher camera hooks are adapted from Ralf's Colosseum widescreen codes
and the corresponding XD recipe distributed in Dolphin's
[GameSettings](https://github.com/dolphin-emu/dolphin/tree/master/Data/Sys/GameSettings).
Orre ports the checked instruction sequence to the other supported revision-0
regions and adds a separate 2D-proportion correction. Reversible patches use
retail read-only constants inside the isolated profile; they do not change
the ROM. Dolphin and its source remain under their respective licenses.
