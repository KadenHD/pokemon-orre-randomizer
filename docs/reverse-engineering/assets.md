# Resources and integrity of extraction

Static analysis of October 30, 2026. The script `scripts/survey_assets.py` reads the files without
modifying them and without starting the game. The identifiers `ASSET-*` below refer to reproducible
local findings, not REA evidence.

## Audited result

**The 2,011 files of `game/` are identical byte per byte to the corresponding ranges of the local
ISO provided.** The control covers 712,453,188 bytes: the 2,006 files of the disk file system and
the five files of `sys/`. It does not compare unused areas of the disk with another copy and does
not establish any external authenticity of ISO.

Reproduction command from the project root.

```powershell
python scripts/survey_assets.py --game game --iso 'Pokemon Colosseum (Europe) (En,Fr,De,Es,It).iso'
```

The JSON result must contain `all_ranges_byte_identical: true`, no entry in `mismatches`, and the
following identities to reproduce this analysis.

| Source | SHA-256 |
|---|---|
| ISO local, 1,459,978,240 bytes | `1e3b4aa806ac3367cca13496f7701137e9437e7bac0101f75b9b137633a10aa9` |
| `game/sys/boot.bin` | `466709a5575548e3f6abe74d21f89e2fa9e4ed119df75b91bc49fc546116e192` |
| `game/sys/fst.bin` | `6da386f1db41c37489bf7fb959a2c7009ea87edf7c9606d19c1f1fb9e8e418be` |
| `game/files/opening.bnr` | `e673c2fae370f3586f367f1d9b38a5719b06fef152ddb1c43cb9019fa8d2f1b4` |

## Observations

### ASSET-001 — Disc identity

In `sys/boot.bin`, the six bytes to `0x00` are `47 43 36 50 30 31`, **`GC6P01`**. The disk number to
`0x06` and the revision to `0x07` are worth zero. The ASCII title to `0x20` is `Pokemon Colosseum`.
The signature to `0x1C` is `C2 33 9F 3D`.

The big-endian words of the header give.

| Position in `boot.bin` | Value | Interpretation used by the control |
|---|---:|---|
| `0x420` | 125,952 (`0x1EC00`) | Position of DOL in ISO |
| `0x424` | 4,222,720 (`0x406F00`) | Position of the FST in ISO |
| `0x428` | 69,251 | FST size |

The word to `0x18` in `bi2.bin` is `2`. The identifier containing `P`, the resource variants and the
ISO name are consistent with a European edition. This qualification is an interpretation of these
fields, distinct from their observed values.

### ASSET-002 — Exhaustivity and content of extraction

The FST contains 2,009 entries of 12 bytes: one root, two directories ([`movie`], entry 202.
`sound`, entry 791) and 2,006 files. The name table starts at `0x5E2C` (24,108 bytes). All expected
paths are present in `game/files/`, without additional file and with expected sizes.

The independent control reads directly the ISO header and FST, then compares each file with its
range, in blocks of not more than 1 Mio. `sys/` are also compared: `boot.bin` to `0`, `bi2.bin` to
`0x440`, `apploader.img` to `0x2440`, then `main.dol` and `fst.bin` The expected sizes are
calculated from ISO: fixed sizes for boot and bi2, apploader size fields, last end of section for
DOL and FST size field. They are not repeated from the extracted files. Result: **2,011 exact
matches, zero divergence**. The complete output is kept in `analysis/generated/assets-survey.json`.

A small synthetic ISO check confirms the detection of a modified payload byte and of truncated DOL,
apploader or FST files.

The first file range of the FST starts on byte 751 816 640. The last one ends at 1,459,978 240. This
important shift is a property of the disk positions. The extracted files represent about 712 MB,
compared to 1.46 GB for the disk image.

### ASSET-003 — Distribution of files

| Directory | Files | Bytes |
|---|---:|---:|
| `game/files/`, direct children | 1,994 | 415,723,917 |
| `game/files/movie/` | 5 | 283,026,032 |
| `game/files/sound/` | 7 | 9,411,648 |
| `game/sys/` | 5 | 4,291,591 |
| **Total** | **2,011** | **712,453,188** |

The observed extensions are: 1,981 `.fsys`, 14 `.bin`, 7 `.samp`, 5 `.thp`, then one `.bnr`, one
`.dol`, one `.img` and one `.toc`.

The 1,981 `.fsys` all start with the four bytes ASCII **`FSYS`**. By name convention, 1,185 have the
prefix `wzx_` and 527 the prefix `pkx_`. The other 269 cover families `D1_`, `D2_`, `D4_`, `M1_` to
`M4_`, `S1_`, `S2_`, menus and archives such as `common.fsys`, `people_archive.fsys`, `prog.fsys`]
or `world_map.fsys`. These names guide the searches but do not show the role of content alone.

Large archives include `people_archive.fsys` at 18,069,472 bytes,
`chara_big.fsys` 5,802,944 and `poke_face.fsys` 4,824,000. None of these containers is decompressed
by this script. The detailed FSYS analysis is conducted separately.

### ASSET-004 — Variantes de langue

The search limited to the suffixes of name `_fr`, `_ge`, `_it`, `_sp` identifies **13 groupes
complets**, each with an archive without suffix: `cb_menu`, `field_common`, `fight_common`,
`pcbox_menu`, `pcbox_pocket_menu`, `pcbox_poke_box`, `pda_menu`, `pocket_menu`, `pokechg_menu`,
`title`, `toolbattle_menu`, `topmenu`, `waza_menu`.

This represents 65 archives on this name convention. There are also other names evoking languages,
especially in the family `wzx_`. The number 65 is therefore not an exhaustive inventory of all
localized content. The presence of a variant does not show that all its texts have been translated
or that a screen gives the load to the execution.

`opening.bnr` begins with `BNR2` and measures 8,096 bytes. Its six 320 bytes text recordings, at
positions `0x1820`, `0x1960`, `0x1AA0`, `0x1BE0`, `0x1D20`, `0x1E60`, are strictly identical. The
disk strip does not bring here six separate translations.

### Asset-005 — Videos

The five video files start with `54 48 50 00`] (`THP\0`) and carry the word version `0x00011000`.
The big-endian floating at `0x10` is about 29.97. The word to `0x14` gives the number of images
below.

| File in `files/movie/` | Bytes | Images declared |
|---|---:|---:|
| `autodemo01.thp` | 101,534,896 | 2,700 |
| `gs_logo.thp` | 2,375,888 | 130 |
| `openingdemo.thp` | 64,046,624 | 1,926 |
| `staffroll.thp` | 113,114,768 | 5,250 |
| `tpc.thp` | 1,953,856 | 75 |

These are header values. No decoding or viewing checks the actual duration or audiovisual content.

## Scope and useful follow-up

The integrity of the extraction from the local ISO is established. Resources are available for FSYS,
REL and DOL analyses. The exact roles of the `pkx_` and `wzx_` families, gameplay tables, loading of
language variants, and links between scenes and data scripts remain to be demonstrated by content
analysis or game observation.
