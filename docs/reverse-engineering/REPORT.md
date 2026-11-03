# Analysis of Pokémon Colosseum PAL

Analysis of October 30, 2026, on the files provided locally. **Containers and main gameplay tables
are now legible and exportable.** This provides a verified basis to develop a randomizer. The
complete game code has not been decompiled and no patch has been tested in play.

Updating: A constant reconstruction of the data and a real trial under Dolphin have since been
carried out. Their method, results and captures can be found in [ROUNDTRIP.md](ROUNDTRIP.md). The
"unverified" statements below describe the state at the end of this first mapping.

## Identity and integrity

The disc declares `GC6P01`, titre `Pokemon Colosseum`, revision 0. Its executable DOL PowerPC is
recognized by REA with an RAM input point `0x80003154`.

| Artefact | Size | SHA-256 |
|---|---:|---|
| Local ISO | 1 459 978 240 | `1e3b4aa806ac3367cca13496f7701137e9437e7bac0101f75b9b137633a10aa9` |
| `game/sys/main.dol` | 4 096 576 | `a788176a45eb88dbd227246a7205ab9856bc79f3cca7e4a0f5376cf466664df5` |
| `common_rel`, decompressed | 2 210 420 | `ee2677af555dc59626f978e743235831a76cb23bae93f3fdd1060d808f749d0b` |

The 2,006 files of the FST and the five system files were compared byte byte byte with the
corresponding ISO ranges: **2,011 matches, 712 453 188 bytes controlled, no divergence**. This
result establishes equality with this local ISO. It does not certify an external origin. Evidence:
`ASSET-002`, detailed in [assets.md](assets.md).

## Organisation reconstruite

```text
ISO / game/
  sys/main.dol       programme principal PowerPC, sections mappées en RAM
  sys/fst.bin        chemins, positions disque et tailles des fichiers
  files/*.fsys       1 981 archives, 6 863 membres
    common.fsys     28 membres dont common_rel
      common_rel    module REL v3, id 125, code + données + relocations
        tables      espèces, capacités, dresseurs, équipes, obscurs
        textes      15 tables repérées, cinq langues
  files/movie/      cinq vidéos à signature THP
  files/sound/      sept fichiers .samp, contenu non décodé
```

The **6,683 LZSS members and 180 members without compression** have their limits and sizes
controlled. FSYS/LZSS headers are consistent in the 1,981 archives. The 28 members of `common.fsys`
were effectively decompressed, with exact consumption of each stream and control of its output size.
The other LZSS streams were not fully decompressed.

The DOL has two code sections and six non-empty data sections. The RAM coordinates of the DOL are
distinct from the offsets in the file. The REL is loaded and re-located separately: the offsets of
the tables below are **pas** from the RAM addresses.

## Tables identified and controlled

Offsets in the member `common_rel` **decompressed**, exclusively for the SHA-256 above. Each
location was obtained from the relocations of the module and the index convention documented by the
community tool, then controlled locally. The parser does not search for these tables by a hardcoded
PAL offset.

| Table | Offset file | Enregistrements | Size per entry | Export local |
|---|---:|---:|---:|---|
| Trainers | `0x15DEEC` | 820 | `0x34` | `tables/trainers.json` |
| Pokémon of the trainers | `0x16AE44` | 5 510 | `0x50` | `tables/trainer_pokemon.json` |
| Moves | `0x1EB38C` | 358 | `0x38` | `tables/moves.json` |
| Species | `0x1F05CC` | 413 | `0x11C` | `tables/species.json` |
| Shadow Pokémon | `0x2125A0` | 97 | `0x38` | `tables/shadow.json` |

Exports can be found under `analysis/generated/`. Meters come from REL words, and sizes remain in
their section. References to species, abilities, evolutions, capabilities per level, teams and
trainers are within the limits expected. The 108 records of Pokémon of a trainer with a dark ID are
all consistent with the species of the associated dark entry. These controls are structural. They do
not establish that each line is used in a part.

The table of species contains **386 separate national numbers between 1 and 386**, without
duplicates, as well as 27 entries whose national number is null. The simple names are decoded for
these 386 species. There is **48 dark entries with a non-zero species**. Therefore, the gross
counter 97 should not be presented as 97 available catches.

Thirty records of Pokémon of trainer contain `0xFFFF` in at least one capacity field. This value is
kept as a raw marker, separately from ordinary indices. Its significance to execution remains
unknown. It must not be replaced automatically by a capacity number.

### Internal and French identifiers

The main French table is with community symbol 101, offset **`0x732B0`**, and contains 2,018
entries. The header bears the bytes `FR`. The nearby tables carry `UK`, `GE`, `IT`, `SP`. Simple
names are read in UTF-16 big-endian. Dialogues and texts containing control codes are not
interpreted as mere strings.

Examples actually decoded.

| Internal Species Index | National number | French name | HP / Attack / Defense / Sp. Atk / Sp. Def / Speed |
|---:|---:|---|---|
| 1 | 1 | BULBIZARRE | 45 / 49 / 49 / 65 / 65 / 45 |
| 25 | 25 | PIKACHU | 35 / 55 / 30 / 50 / 40 / 90 |
| 196 | 196 | MENTALI | 65 / 65 / 60 / 130 / 95 / 110 |
| 197 | 197 | NOCTALI | 95 / 65 / 110 / 60 / 130 / 65 |
| 277 | 252 | ARCKO | 40 / 45 / 35 / 65 / 55 / 70 |

**A Pokédex number should not be used directly as an internal index.** For example, the internal
index 252 is an empty entry, whileTreecko, national number 252, is at internal index 277. The future
randomizer will have to build its list of eligible species since the verified records.

## Register of evidence

`LOCAL-*` and `ASSET-*` identifiers are references to this project, not evidence IDs assigned by
REA.

| Reference | Nature and perimeter | Result / limit |
|---|---|---|
| `ASSET-001/002` | Headers + FST + comparison of all ISO ranges | Consistency of identity and extraction |
| `LOCAL-STRUCTURE-001` | All extracted files, SHA-256, DOL/FSYS/REL parsers | Complete inventory of this perimeter. Decompression limited to common |
| `LOCAL-TABLES-001` | `common_rel` exact, primary diagrams + terminals + references + texts | Five tables exported. Statically corroborated semantics |
| `LOCAL-REA-001` | `open_binary(format=gamecube-dol)`, then `binary_overview` | Recognized identity. Deep analysis unavailable |

Local evidence files: `analysis/generated/manifest.json`, `fsys.json`, `dol.json`,
`common-rel.json`, `rel-symbols.json`, `summary.json`, `tables-summary.json`, `assets-survey.json`,
`rea-run.json`. A lasting summary of the results is kept in [baseline.json](baseline.json)The
primary sources, their versions and the limits of their interpretation are in
[community-formats.md](community-formats.md).

REA 6.8.0 is connected. Its deep inventory call returned `capability_unavailable`: Ghidra is not
configured and the REA Ghidra provider on Windows does not admit the GameCube DOL format. Hopper is
unavailable on Windows. IDA and Kuna are not configured and their REA routes do not admit this DOL.
Installing Ghidra alone under Windows would not be enough to unlock this route. No MCP tools or
settings have been installed or modified. The export of ledger REA contains zero evidence record.
The identity and error of this session are kept separately in `rea-run.json`. The native session has
been closed.

## Validation and state of the investigation

Twelve tests on small independent fixtures pass: LZSS with overlapping references, zero initial
window and closure, truncations and exceedances. FSYS limits. DOL sections/entry. REL imports and
callbacks. Name and control codes. The scripts were also executed on the full dump. This checks the
drive and data consistency, without replacing a game test.

| Question initiale | State |
|---|---|
| Which version and the extraction match ISO? | Answered |
| How are containers organized and their compression? | Responded for inventory. Full common decompression |
| Where are the main data for a randomizer? | Responded for the five tables above, including evolutions and capacities by level |
| Can we link clues and French names? | Responded for exported single names |
| What functions of the code perform the mechanics? | Part: DOL/REL load mapped, non-decompiled function bodies |
| Can a modified game be rebuilt and played? | Not verified: no patch or reconstruction performed |

The technical suite consists of building a deterministic patch on a copy, keeping references between
teams and dark, preserving reserved entries, reencode FSYS and then reconstructing a disk. Scenario
starters and scripts, progression constraints and actual behavior under Dolphin will have to be
checked separately. A code analysis will be able to use a Ghidra/POSIX environment compatible with
the REA DOL route or a suitable PowerPC tool, keeping these file identities.
