# Colosseum format and structure references

Consulted October 30, 2026. Static study: no execution of the game, no modification of `game/`.
Community schemes are used to formulate and verify assumptions about this dump. They do not replace
its validation.

## Identity observed locally

Direct Header Reading: `game/sys/boot.bin` contient `GC6P01`, revision 0. `main.dol` contains the
point of entry `0x80003154` and its SHA-256 is
`a788176a45eb88dbd227246a7205ab9856bc79f3cca7e4a0f5376cf466664df5`.

`common.fsys` bears the FSYS signature, 28 members and a declared size equal to its actual size, 944
672 bytes. The first member header is to `0x290`, its contents to `0xB60`, with LZSS signature,
stored size 813 413 bytes and decompressed size declared 2,210 420 bytes. These values are local
observations. The semantics of internal tables require further analysis.

## DOL and REL

The official Dolphin player declares 7 sections of code, 11 sections of data, their offsets,
addresses and sizes, then BSS and entry point. The file does not contain the original function
names. Source: [Dolphin
DolReader.h](https://github.com/dolphin-emu/dolphin/blob/master/Source/Core/Core/Boot/DolReader.h),
license indicated `GPL-2.0-or-later`.

The decomp-toolkit parser describes the REL relocation sections and commands: `201` accumulates a
displacement, `202` changes the current section and resets its position to zero, `203` completes the
list. Imports name the target module. The zero module refers to the DOL. A REL address therefore
requires a section, base and a relocation, and should not be treated as a fixed RAM address. Source:
[decomp-toolkit rel.rs](https://github.com/encounter/decomp-toolkit/blob/main/src/util/rel.rs),
Apache-2.0 project. Exact version not fixed here.

## FSYS and LZSS

The StarsMmd code displays the following fields: FSYS `+0x08` groupe, `+0x0C` nombre de membres,
`+0x20` taille, `+0x40` pointer to the list of headers. In each member header: `+0x00` identifier,
`+0x04` position of data, `+0x08` decompressed size, `+0x14` size stored, `+0x1C` full name, if any,
`+0x24` short name. The prefix LZSS measures `0x10` bytes, with sizes to `+4` and `+8`. Fixed
primary source:
[XGFsys.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/file%20formats/XGFsys.swift).

LZSS uses a circular window of 4096 bytes filled with zeros, initial writing position `0xFEE`. The
bits of the flag are consumed at least significant to the most significant: 1 means literal, 0
reference. For two bytes `a,b`, reference position = `a | ((b >> 4) << 8)` and length = `(b & 15) +
3`. The copy can overlap. Source:
[XGLZSS.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/file%20formats/XGLZSS.swift),
which assigns its port to QuickBMS/Luigi Auriemma.

The Pokemon-XD-Code repository indicates a GPL-2.0 license. No third-party code has been copied into
the project by this search.

## Index of common_rel symbols

In the historical tool, symbols are numbered by first occurrence of a separate target in the Type 1
to 13 relocation commands, from the offset `u32@0x24`, to the first command 203. Target = offset
from the beginning of the section + addend. This is a tool convention, not an explicitly stored
index. Source:
[XGRelocationTable.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/file%20formats/XGRelocationTable.swift).

| Table candidate | Symbol index | Counter index |
| --- | ---: | ---: |
| Trainers | 44 | 45 |
| Pokémon of the trainers | 48 | 49 |
| Moves | 62 | 63 |
| Species statistics | 68 | 69 |
| Shadow Pokémon | 80 | 81 |

`CMRelIndexes.swift` announces US indexes and explicitly adapts EU: script 98, first text table 99.
The other correspondences above remain to be corroborated with PAL data. Source:
[CMRelIndexes.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/CMRelIndexes.swift).

## French text: PAL observation

The Community player indicates a u16 to `+4` counter, a header of `0x10` bytes and then 8 bytes
entries: ID u32 masked by `0xFFFFF`, offset u32 relative to the beginning of the table. Characters
are u16 big-endian units completed by `0000`. The marker `FFFF` introduces a special u8 code
followed by a variable number of bytes. A UTF-16 decoder is only suitable for simple names but not
for all dialogs. Source:
[XGStringTable.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/file%20formats/XGStringTable.swift).

On the local decompressed member `analysis/generated/extracted/common/000.bin`, the name of the
internal species 1 refers to ID 1001. Reading the five tables gives.

| Symbol index | Offset in common_rel | Entries | ID 1001 observed | Capacity name 1 observed | Language identified |
| --- | --- | ---: | --- | --- | --- |
| 99 | `0x5A448` | 2018 | BULBASAUR | POUND | English |
| 100 | `0x6698C` | 2018 | BISASAM | PFUND | German |
| 101 | `0x732B0` | 2018 | BULBIZARRE | ECRAS'FACE | French |
| 102 | `0x7FE8C` | 2018 | BULBASAUR | BOTTA | Italian |
| 103 | `0x8CB98` | 2018 | BULBASAUR | DESTRUCTOR | Spanish |

The identification of the French table with symbol 101 is therefore based on its local content, and
not on the US convention where 101 designates the script. The names of the capacities 1 and 15
distinguish tables whose name Bulbasaur is identical. The shapes observed for capacity 15 are CUT,
ZERSCHNEIDER, COUPE, TAGLIO and CORTE respectively.

## Candidate schemes for the randomizer

The offsets below are relative to a record, the multibyte integers are big-endian. They come from
sources. This page does not claim that all fields have been validated locally.

Species, size `0x11C` : national number u16 `+0x10`, text identifier u32 `+0x18`, types u8
`+0x30/+0x31`, talents u8 `+0x32/+0x33`, articles held u16 `+0x70/+0x72`,
HP/Attack/Defense/Sp. Atk/Sp. Def/Speed u8 at offsets `0x85/87/89/8B/8D/8F`. Developments at `+0x9C`,
capacity by level `+0xBA`. Source :
[CMPokemonStats.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/enumerable/CMPokemonStats.swift).

An evolution measures 6 bytes: u8 method `+0`, u16 condition `+2`, u16 target species `+4`, five
inputs. One capacity per level measures 4 bytes: u8 level `+0`, u16 capacity `+2`, 19 inputs.
Sources:
[XGEvolution.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/XGEvolution.swift)
and
[XGLevelUpMove.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/XGLevelUpMove.swift).

Dresser, size `0x34`: class u8 `+3`, first index Pokémon u16 `+4`, IA u16 `+6`, text of name u32
`+8`, model u8 `+0x13`, u16 objects since `+0x14`. The tool reads six consecutive Pokémon locations.
Source:
[CMTrainer.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/enumerable/CMTrainer.swift).

Pokémon of trainer, size `0x50` : talent/genre/nature/dark ID u8 `+0/+1/+2/+3`, level u8 `+4`,
species u16 `+0xA`, objet u16 `+0x12`, name u32 `+0x14`, capacity u16 `+0x36/+0x3E/+0x46/+0x4E`.
Separate dark entrance, size `0x38` : capture u8 `+0`, species u16 `+2`, first trainer u16 `+4`,
alternative trainer u16 `+6`, jauge u16 `+8`, ID u8 `+0xB`. Changing an obscure species implies
checking the consistency between these tables.
[CMTrainerPokemon.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/enumerable/CMTrainerPokemon.swift).

Capacity, size `0x38` : PP u8 `+1`, type u8 `+2`, precision u8 `+4`, puissance u8 `+0x17`, effect u16
`+0x1A`, name u32 `+0x20`. The category to field `+0x1F` is described as an addition per hack for
Colosseum: do not present it as a demonstrated vanilla mechanics. Source:
[XGMove.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/enumerable/XGMove.swift).

## PAL symbols and current tools

The
[GC6P01.map](https://github.com/StarsMmd/Colo-XD-PBR-symbol-maps/blob/93d5da920e7f03b8854b79963d94739ec66abd1d/GC6P01.map)
card contains candidates for borders and community names. RAM examples: `__start 0x80003154`,
`memcpy 0x800054F4`, `zz_set_current_language 0x800056C8`, `zz_get_current_language 0x800056D0`,
`DVDReadAsyncPrio 0x800A8968`. README explains the provenance by comparison and indicates that the
old `annotated` files are obsolete. Names are not original proven symbols for this dump. No explicit
license verified for these cards.

[GoD-Tool](https://github.com/StarsMmd/GoD-Tool) describes its successor GODDESS and its support
FSYS/LZSS, DOL and disk reconstruction. Its page also distinguishes REL operations present but
disabled. The simple name of an order does not prove its availability. License displayed GPL-3.0. No
tools installed or executed here.

## Limitations and follow-up

The NTSC-U references, including the Colosseum GC6E01 decompilation projects, do not fix the PAL
offsets. Before writing: check meters, section limits, species/capacity identities, cross references
and consistency of dark entries. The romaji names of the archives and their presence do not prove
the use for execution or the completeness of a mechanics. A reconstruction and then a test under
Dolphin remains necessary to validate a future patch.
