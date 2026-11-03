# Proof-of-concept patch: Donphan becomes Pikachu

On October 30, 2026, a separate ISO was produced for **GC6P01 PAL, Revision 0**. Only one Pokémon
was replaced: **the fifth Basil Pokémon, Donphan level 50, becomes Pikachu level 50**. Its default
name ID is also replaced to display "PIKACHU".

## Product files

- ISO : `build/witness-pikachu/colosseum-pal-witness-pikachu.iso`
- Taille : **1 459 978 240 octets**.
- SHA-256 : `b4f2f70830b2139264f7a7d9d1f872fb4a4df081cfdfd75c6daaa85db844f2b9`
- Plan of the patch: `build/witness-pikachu/witness-patch.json`
- Data and Original Control: `build/witness-pikachu/witness-verification.json`
- Captures and events: `build/witness-pikachu/evidence/`
- Sustainable Summary of Audits: [witness-validation.json](witness-validation.json)

## Accurate change

The trainer **771**, named BASILE in French, refers to the team starting with the recording
**1568**. The index slot **4**, the recording **1572**, is not referenced by any other compiler of
the table. The script refuses shared records, Shadow Pokémon, custom nicknames and all `common.rel`
different from the original validated dump.

| Field of common.rel | Offset | Before | After |
|---|---:|---:|---:|
| Species, integer 16 bits big endian | `0x18998E` | 232, Donphan | 25, Pikachu |
| Default name, integer 32 bit big endian | `0x189998` | 1232 | 1025 |

These two fields lead **two bytes actually different** to the decimal offsets 1,612,175 and
1,612,187. The other 78 bytes of the 80 bytes recording are identical. Level, abilities, object
held, talent selector, gender, nature, EV and IV are preserved. Pikachu thus voluntarily keeps the
abilities of this Donphan: **Earthquake, Damocles, Pouv.Antique and Abri**. This witness checks the
replacement of the species. He does not seek to produce a balanced team or conform to the abilities
normally learned.

The SHA-256 of `common.rel` decompressed goes from
`ee2677af555dc59626f978e743235831a76cb23bae93f3fdd1060d808f749d0b` to
`89a3b269bb32620fdecc52d7c47396f736cb3e72ba8b78b6f759610464ea3690`. **27 other members** of
`common.fsys` are identical after decompression.

The reconstruction uses [the validated method without changing data](ROUNDTRIP.md). The recompressed
archive of 959 200 bytes is placed at `0x418000`. Only its new disk range and the eight bytes of its
offset and its size in the FST may differ from the source ISO. **1 459 019 032 other bytes** are
compared in full.

Control `DolphinTool verify` ends with code 0 and `Problems Found: No`: CRC32 `dd31d889`, SHA-1
`d51193babb015bb4f34102a423b839ea57b9e4fb`. It also emits the diagnosis `Error creating key`,
already observed during the first check.

## Test on Dolphin

The patched ISO has been explicitly launched with **Dolphin 2609a, JIT64 SC, Direct3D 12, DSP HLE**,
without cheats, and the profile `build/witness-pikachu/dolphin-user`. The EUR memory card and SRAM
come from copies. The entries were made with Dolphin's TAS controller window, by controlling the
Windows interface.

The scenario uses **Quick fight → Double → Very strong**. This mode draws a team for the player
separately and one for the computer. After opponents Curtis, Simone, Jess and Mélina, the game
attributed **Basil team to player MICHAEL** to Melina. The evidence in battle is therefore about
this team lent to the player, not about a fight against the Basil character. No random draw table or
seed has been changed.

| Monitoring | Observation | Capture in evidence/ |
|---|---|---|
| Modified team | Suicune, Raikou, Entei, Aggron, **Pikachu**, Salamence. Pikachu femelle level 50 | `02-patched-team-preview.png` |
| Chargement en combat | Pikachu 3D model, correct name and icon, **95/95 PV** | `03-pikachu-battle-model.png` |
| Capacity retained | Earthquake, Damocles, Pouv.Antique, Abri. Command Pouv.Antique selectable | `04-pikachu-preserved-moves.png` |
| Interactive resolution | Puv.Antique controlled against Ninjask, then Laser Ice Suicune against Swellow. Pikachu is placed K.O. during resolution and the replacement menu works | `05-turn-resolution.png` |
| Turn over | Raikou replaces Pikachu. Swellow is K.O. then replaced by Ninetales. Back to the attack menu | `06-after-replacement.png`, `07-post-turn-command-menu.png` |

Pikachu is placed K.O. during this turn. The execution of Pouv.Antique has not been observed. Its
attack animation has therefore not been validated. The replacement of species, its display, its
loading in combat and access to its commands have been observed. The abilities are voluntarily
inherited from the original Donphan, which does not represent a balance of the team.

## Preservation and limitations

Dolphin was closed cleanly, with an output code **0**. The complete check after closing confirms
that **ISO source, 2,011 extracted files and 20 existing files from the usual Dolphin profile
verified by the manifest are unchanged**. The reconstructed ISO without patch of the first test also
retains its SHA-256 `3b4edc03c00f56f029d8cf47b9acbfda32f5f329a9cc9e7d3f8e603af9fc41a7`.

**19 tests** pass: binary drives, LZSS, FSYS re-encoding, targeted replacement and rejection of
additional changes. The verifier also re-reads the final ISO data and confirms that only one Pokémon
record and only two authorized fields have changed.

The test covers an interactive turn and the return to the controls, without full combat, full
course, physical console test, backup writing in play, audio evaluation or performance measurement.

## Reproduire

From the root of the project, choose a new output directory.

```powershell
python scripts/patch_trainer.py --source-iso 'Pokemon Colosseum (Europe) (En,Fr,De,Es,It).iso' --output-dir build/witness-pikachu-2
python scripts/prepare_dolphin_test.py --output build/witness-pikachu-2/dolphin-user
.\scripts\start_dolphin_test.ps1 -Iso build/witness-pikachu-2/colosseum-pal-witness-pikachu.iso -UserDirectory build/witness-pikachu-2/dolphin-user
python scripts/patch_trainer.py --verify-only --output-dir build/witness-pikachu-2
python -m unittest discover -s tests -v
```

The script refuses to overwrite an existing building directory. It reads the original ISO and
extraction, then writes all the results under `build/`. The preparation copies the memory card and
SRAM in an isolated test profile. Status backups created with this ISO must be used with the same
ISO: an earlier state from ISO without patch could restore the old data in memory.
