# Application v0.3: Part parameters

The engine `advanced-gameplay-rules-v5` adds 26 parameters to the 16 previous rules: 42 parameters
in total, including 38 booleans, one mode choice and three numerical values. The application remains
local and retains the source ROM.

## Configuration

| Category | Settings |
| --- | --- |
| Trainers | Common species, dark, unique Shadow Pokémon families |
| Starters and gifts | Umbreon, Espeon, Plusle, Ho-Oh, Celebi, Independent Pikachu |
| Moves | Attacks on trainers, starters, gifts. Level learning. Coherent/chaos mode. Offensive and same type guarantees. Duplicates. Exclusions Destruction/Explosion and K.O. in one stroke |
| Allowed species | Generations I/II/III. Legendary/fabulous. Comparable power |
| Abilities | Randomization. Family consistency |
| Base stats | Redistribution. Retention of total origin |
| Types | Randomization. Family consistency |
| Held items | Replace objects present. Useful selection in combat |
| Difficulty and capture | Levels ×0.5–2. Capture ×0.25–5. Minimum 0–255 |
| Evolutions | The five accessible categories of the v0.2 |
| Shops | Stones at Phenac City and Pyrite Town separately |

The recommended preset activates species, the four randomizations of capabilities in coherent mode,
replacements of comparable power, protections, accessible evolutions and shops. Types, talents,
statistics and objects remain deactivated. Multipliers remain at 1 and the minimum capture at 0.
"Everything deactivates" also gives digital values to their neutral value. The LTC retains the old
changes by default. Its new options are explicit, for example `--randomize-learnsets
--randomize-starter-moves`.

## Rules and protections

- Each draw uses SHA-256 with the seed and a stable key. Options and versions are saved in the JSON
  report. No system RNG decides the data of the game.
- The coherent mode adapts power to the level and prefers a second attack corresponding to offensive
  statistics. The physical/special separation is that of generation III, determined by the type.
- The four attacks can be drawn separately from the species. The warranties use the final types
  after randomization. The learning levels and reserved bytes remain intact. The windows of four
  learnings retain an offensive attack of the same type if this protection is activated.
- Black load and special markers are protected: the 30 records of trainers that contain them retain
  their entire block of capabilities. The other records only change the identifiers of attacks.
- Filters are never released silently. The 48 dark groups remain synchronized and their families
  remain distinct when requested. An impossible combination produces a recoverable error.
- As soon as a species filter or comparable power is active, Shedinja is excluded from replacements
  to avoid combat blockages related to Mystik Guard. The historical selection without these settings
  remains compatible with v0.2 and can shoot Shedinja. Its native properties and its basic PV remain
  protected. Mystik Guard is not attributed to other species.
- The statistics are limited to 1–255. Without conserving the total, the total drawn is between 250
  and 680. Talents are drawn in the native catalogue, with one or two locations depending on the
  species.
- The objects are replaced only in the already occupied locations, in a catalogue observed among the
  opponents. The markers remain intact. The Choosing Strip is not chosen without physical attack
  inflicting damage.
- The levels remain between 1 and 100. Starters and gifts keep their level. The capture changes
  the 48 active groups and remains between 1 and 255.

## Gifts attacks and disk image

Gifts normally calculate their attacks since the global learnings. A small PowerPC routine calls
the native constructor and then its four skill sets. It allows to regulate the attacks of a gift
without changing the other Pokémon of its kind. When only the learnings are randomized, it retains
on the contrary the native attacks appropriate to the species of the gift.

The added code section makes 544 bytes for the four gifts and its memory arena protection. The
extended DOL is placed in a free space of ISO and its boot pointer is adapted. The original FST and
DOL remain at their original location. The instructions signatures, branches and modification ranges
are verified before any output.

## Local validation

111 Python tests pass, including Qt controls, numerical limits, consistent/chaos hashes, final
types, 48 families, levels/captures, reserved fields and the independence of gifts. A small
PowerPC interpreter tests the calls of the four sets, the manufacturer return, the registers and the
protection of the arena. These tests do not replace the actual obtaining of late gifts in a
complete part.

ISO with the recommended preset and the historical test seed.

```
source  1e3b4aa806ac3367cca13496f7701137e9437e7bac0101f75b9b137633a10aa9
sortie  425f1d846db101bfceaed6f941c05890eaa34cd27c5cf0fed0732830e84c7ebd
```

The 1,459,978,240 bytes of ISO are checked against the source and the only replacements expected.
The hash source is recalculated at the end of the processing. Local construction observed: about 10
seconds with the Rust codec. The new ISO starts cold under Dolphin 2609a, with an isolated profile,
a blank memory card and without an old fast state. The backups of the usual profile are not loaded
in this test.

The two starters were opened in a new game: Gardevoir at level 26 (Extrasensory, Thunder Shock, Reflect, and Aurora Beam) and Tangela at level 25 (Needle Arm, Thief, Magic Coat, and Bubble Beam). The names,
levels, four attacks and PP displayed correspond to the report. The EXP of the first starter is
21,970, expected threshold for its growth group at level 26.

A second construction accurately reproduces the recommended ISO SHA-256. The changeless preset
reproduces exactly the SHA-256 of the source. A RVZ → RVZ route was also executed with randomized
types, talents, statistics, objects and attacks, generation III alone without legendary, levels
×1,25 capture ×2 and minimum 100. The ISO resulting from its recompression corresponds to the ISO
verified before compression ([`97805312f1f72eb6db29654b310ef4f7da5e039c24e22177da922a1bab3ea6cd`].
The 2,011 extracted files and the 20 inventoried files of the original Dolphin profile retain all
their SHA-256 fingerprints.

The Windows 0.3 executable started without a terminal and created its own ISO with the recommended
preset in 10.02 seconds. Its SHA-256 is identical to the source version and the window displays 100%
success. The Capabilities and Difficulty/Capture pages have been visually controlled. The archives
pass the integrity and lack of data checks of the game. The sources extracted without ROM run 111
tests successfully, 29 of which are ignored due to lack of local data.

The local evidence and reports files remain in `build/v03-qa/` and `build/v03-default.iso.json`, out
of distribution. The full scenario, all late gifts, balancing and other computers remain to be
validated. The current manual control checks the start-up, the EXP and the starters attacks. A
complete fight with these new attacks remains to be played.
