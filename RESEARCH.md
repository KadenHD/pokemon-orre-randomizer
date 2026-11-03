# Pokémon Colosseum: analysis of the PAL dump

Reproducible static mapping of local extraction `game/`, carried out on October 30, 2026. Observed
version: **GC6P01, revision 0**.

To recreate a game with the v3 engine, use the [v3 report](docs/reverse-engineering/RANDOMIZER_V3.md) procedure and start a new save.

- [Results, offsets and limits](docs/reverse-engineering/REPORT.md)
- [Extraction integrity and resources](docs/reverse-engineering/assets.md)
- [Primary sources and community format references](docs/reverse-engineering/community-formats.md)
- [Audited Reference Summary](docs/reverse-engineering/baseline.json)
- [ISO reconstruction and actual Dolphin testing](docs/reverse-engineering/ROUNDTRIP.md)
- [Proof-of-concept patch: a Basil Donphan replaced by Pikachu](docs/reverse-engineering/WITNESS_PATCH.md)
- [Randomizer of trainers v1: seed, rules and Dolphin
  test](docs/reverse-engineering/RANDOMIZER_V1.md)
- [Story randomizer v2: starters, gifts and
  audits](docs/reverse-engineering/RANDOMIZER_STORY_V2.md)
- [Randomizer v3: unique Shadow Pokémon families and accessible
  evolutions](docs/reverse-engineering/RANDOMIZER_V3.md)
- [Application v0.5: profiles, starters, boss Shadow Pokémon and validation](docs/DESKTOP_V05.md)

Python 3.12 and standard library only, without installation of dependencies. From the project root.

```powershell
python scripts/analyze_game.py --extract-common
python scripts/inspect_tables.py
python scripts/survey_assets.py --game game --iso 'Pokemon Colosseum (Europe) (En,Fr,De,Es,It).iso'
python -m unittest discover -s tests -v
```

The scripts read the original files without modifying them. The first two write their results in
`analysis/generated/`: SHA-256 inventories, sections DOL/REL, FSYS members, then JSON tables named
in English and French. `--extract-common` also writes the 28 decompressed members of `common.fsys`
in this local directory. The third displays a JSON report and compares the extraction to the local
ISO when provided.

The table reader refuses a different `common.rel` than the validated one: offsets from another
region or from an already modified game require a new check. Record numbers include null, reserved
and possibly unused entries.

A separate ISO has now been rebuilt after recompression of `common.fsys`, with verified decompressed
data identity. The start-up, loading of a copied backup, an interactive displacement and a combat
tower have been validated under Dolphin 2609a. The ISO produced is
`build/roundtrip/colosseum-pal-roundtrip.iso`. The proofs and limits are in the reconstruction
report.

To restart ISO with its isolated test profile.

```powershell
.\scripts\start_dolphin_test.ps1
```

A separate cookie patch replaces only the Donphan level 50 of Basil by Pikachu, with its default
name. The capabilities and other data of this record are retained. The `scripts/patch_trainer.py`
script refuses unknown versions and records shared between trainers. Its verifier controls the
produced ISO and the originals. The construction and launch controls are in the report of the
control patch.

The first randomizer is available in `scripts/randomize_trainers.py`. The validation ISO covers
3,355 Pokémon in 817 trainers, including the 48 synchronised dark groups. Species and names change.
The other data are kept, with the first talent folded if necessary. The same seed and the same
version reproduce the same tables and archive. Rules, limits and commands are in the report of the
randomizer.

The full progression of the scenario and balancing remain to be validated. Dumps, emulators, ISOs
and test profiles are excluded by `.gitignore`.

The v2 adds the six PAL routines identified: Umbreon, Espeon, Plusle, Ho-Oh, Celebi, and Pikachu
eventiel. For this seed, the two starters become Smeargle level 26 and Slowbro level 25. Their EXP
is adapted. The teams of trainers of the v1 remain identical. Event routines are modified without
enabling events. External distributions are not included.

The v3 keeps these starters and gifts, corrects the five family collisions among the dark and makes
accessible the 15 evolutions blocked by exchanges, day/night or beauty. The evolutions by exchange
become evolutions at level 40. The competing branches use different stones. The six stones are added
to the shops of Phenac City and Pyrite Town for 2,100 each. The originals and the old ISOs are
preserved.
