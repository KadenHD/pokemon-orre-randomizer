# Unchanged data reconstruction and Dolphin test

On October 30, 2026, a separate ISO was reconstructed and tested with **Dolphin 2609a, JIT64 SC,
Direct3D 12 and DSP HLE**. The game data is stored: the 28 members of `common.fsys` were actually
recompressed and checked after decompression. All the other files are identical byte by byte. The
start, the loading of a copied backup, the displacement and an interactive battle tower were
observed.

## Available outcome

- ISO : `build/roundtrip/colosseum-pal-roundtrip.iso`
- Size matches the source image at **1,459,978,240 bytes**.
- SHA-256 : `3b4edc03c00f56f029d8cf47b9acbfda32f5f329a9cc9e7d3f8e603af9fc41a7`
- Build report `build/roundtrip/rebuild-report.json`
- Post-test verification: `build/roundtrip/final-integrity.json`
- Captures and Timed Events: `build/roundtrip/evidence/`
- Sustainable Summary: [roundtrip-validation.json](roundtrip-validation.json)

Recompression and new offsets change the bytes of the ISO container, hence its hash. It is not a
binary copy identical to the source image.

## Method of reconstruction

`scripts/rebuild_iso.py` reads the entries without opening them in writing, then refuses to continue
if the extraction does not match the source ISO. He also refuses to replace an existing output
directory.

The LZSS compressor is deterministic: 4 Kio window, 3 to 18 byte references and allowed overlapping
copy. The tests check in particular the zero, repetitive, random data, the circular window and the
limit cases. Each recoded stream is redecorated and compared to the original bytes before being
incorporated into the archive. Unknown headers, FSYS identifiers and names are kept. Positions and
sizes are updated, with 32 byte member alignment and 32 byte FSYS footer.

The archive changes from **944,672 to 959,200 bytes** to the disk offset `0x418000`, aligned with 32
Kio, in the space preceding the FST files and after all system areas. Its old copy remains intact in
ISO. The order of the files, the names and indices of the FST are kept. Only the eight bytes
containing the offset and the size of `common.fsys` change.

The source image serves as a template to keep the unreferenced areas of the disk. All referenced
files are then written from the extraction, replacing only `common.fsys` with the recoded archive. A
validation of all payloads and system files precedes the publication of the final `.iso` file.

An independent check confirms that **1,459,019,032 bytes**, outside the only two ranges allowed
below, are strictly identical to the source image.

| Plage | Start included | Fin exclue | Size |
|---|---:|---:|---:|
| Offset and Common Size in FST | 4,222,988 | 4,222,996 | 8 |
| New archive common.fsys | 4,292,608 | 5,251,808 | 959,200 |

The official auditor was executed.

```powershell
.\Dolphin-x64\DolphinTool.exe verify -u build/roundtrip/tool-user -i build/roundtrip/colosseum-pal-roundtrip.iso
```

Result: output code 0, `Problems Found: No`, CRC32 `62a55c7e`, SHA-1
`8d4593390676f1037670d923b43a789e5b456c9a`. The program also emitted `Error creating key`. No disk
problems were reported. This control does not check all the mechanics of the game.

## Real tests

The emulator was launched with `-u build/roundtrip/dolphin-user`] and `-e` explicitly pointing to
the reconstructed ISO. The EUR memory card and SRAM were **copied** in this new profile. Cheats were
disabled. No setting or patch per game of the usual profile was imported.

The interactive inputs were controlled with Dolphin's TAS controller window, via Windows interface
control. No gameplay code was injected and no automatic demo was used as evidence of interactive
combat.

| Test | Observation | Capture in evidence/ |
|---|---|---|
| Starting | Title screen in English | `01-title.png` |
| Memory card | Successful loading message | `02-memory-card-loaded.png` |
| Continue | Backup copy loaded, then back into the world | `03-save-loaded-in-world.png` |
| Movement | The character and camera respond to the stick | `04-world-movement.png` |
| Software Reset | Back to the title screen, after a black transition | `05-soft-reset-title.png` |
| Interactive preparation | Fast fight, double, strong opponent, selection of four Pokémon | `06-interactive-battle-start.png` |
| Arena and controls | Colosseum of Phenac City, accessible attack menu | `07-battle-arena.png` |
| Capacity and damage | Burner foot chosen for Blaziken. Donphan goes from 150 to 67 PV, then uses Pouv.Antique | `08-turn-resolution.png` |
| Turn over | Back to the attack menu, Donphan at 67/150 PV and Blaziken at 101/140 PV | `09-post-turn-state.png` |

For the observed turn, Swampert received the Curse and Blaziken Burner Foot command, targeting
Donphan. The return to the controls of the next turn establishes that the turn came to an end. The
emulator was then closed cleanly, with an output code 0.

## Preservation and limitations

After Dolphin's closure, the source ISO SHA-256 and the **2,011 extracted files** the same. **20
existing files** the usual profile included in the control — configuration, GC/memory card and
possible settings or states — are also unchanged. Session changes and caches belong to the test
profile under `build/`.

The sixteen reader and reencoding tests pass. Format sources are [primary sources already
identified](community-formats.md), supplemented by [GoD-Tool FSYS
rebuilder](https://github.com/StarsMmd/GoD-Tool/blob/c39f0100a4b81819a5d7552af81b7adaaf7f3f8c/GoD%20Tool%20Package/Sources/Shared/Core/Engines/GeniusSonority/File%20Formats/FSYSArchive.swift),
[DirectoryBlob de
Dolphin](https://github.com/dolphin-emu/dolphin/blob/master/Source/Core/DiscIO/DirectoryBlob.cpp)
and [the launch arguments
Dolphin](https://github.com/dolphin-emu/dolphin/blob/master/Source/Core/UICommon/CommandLineParse.cpp).

The validation covers these specific scenarios: it does not constitute a complete game path, a
validation on physical GameCube, a backup writing test in play or a validation of a future
randomizer. Audio has not been evaluated and no performance measurement has been performed.

## Reproduire

From the root of the project, choosing an **new** output directory.

```powershell
python scripts/rebuild_iso.py --source-iso 'Pokemon Colosseum (Europe) (En,Fr,De,Es,It).iso' --output-dir build/roundtrip-2
python scripts/prepare_dolphin_test.py --output build/roundtrip-2/dolphin-user
.\scripts\start_dolphin_test.ps1 -Iso build/roundtrip-2/colosseum-pal-roundtrip.iso -UserDirectory build/roundtrip-2/dolphin-user
python scripts/verify_roundtrip.py --build-dir build/roundtrip-2
python -m unittest discover -s tests -v
```

The original memory card is copied during preparation. The tests write in the test profile. To
reopen the already produced result, simply launch `.\scripts\start_dolphin_test.ps1`.
