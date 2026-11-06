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
`licenses/rust/`. Its source and offline build instructions accompany this project.

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
