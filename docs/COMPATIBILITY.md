# Supported original discs

Both games accept ISO or RVZ. Every supported decoded ISO is 1,459,978,240 bytes.
The header selects a candidate; the complete ISO SHA-256 must match before any
patch. Executables and archives have further content checks. All entries are
**revision 0**. Modified images, unknown revisions and incomplete dumps are rejected.

| Game | Region | Disc ID | Original ISO SHA-256 |
| --- | --- | --- | --- |
| Colosseum | Europe | `GC6P01` | `1e3b4aa806ac3367cca13496f7701137e9437e7bac0101f75b9b137633a10aa9` |
| Colosseum | USA | `GC6E01` | `78c4074429fa598b97bfac296bf8e0f7e93f5cb6d8679f8d2653ca902820f6c5` |
| Colosseum | Japan | `GC6J01` | `17c284ab2592083b91d33229ea03384ccdd397eab5db5d3a6ddf5b1f9685368f` |
| XD | Europe | `GXXP01` | `1cc438ed60e542991b8f1abea4617e67880f2568aceb513602051ca6f310e8c1` |
| XD | USA | `GXXE01` | `806a962155560d191435f7ba670bfb3471404c04f3494ad1a02d833508bf482f` |
| XD | Japan | `GXXJ01` | `4a77d6d25292bc97ba18502296415d9297e7138d61e19e2512d0a26d57f90ae2` |

RVZ is decoded with DolphinTool before validation. ISO-only processing does not
need it. Output format is independent of input format. Sources and existing saves
are preserved.

## Languages and profiles

European originals support English, French, German, Spanish and Italian; US
originals use English and Japanese originals use Japanese. The six-language
interface does not translate the ROM. Patched stone names, trade requests and
reward dialogue use the ROM's available text banks. Unchanged copies preserve text.

Profiles belong to one game but are portable across its supported regions.
Exact reproduction requires the same original, seed, options and engine version.
Imports restore recorded values rather than applying current preset defaults.
RC1 and RC2 profiles remain accepted in v1.0.0. Earlier migrations are documented
in the changelog and historical notes.

In v1.2.0, XD profiles from engines v3–v7 retain their native Shadow shiny lock.
The new Shadow unlock is disabled during import, preserving their previous
draws and saved rate. Selecting a current randomizing preset enables it at 5%.

In v1.1.0, XD profiles from engines v3–v6 retain the original three-species
Poké Spot shuffle. The new full-Pokédex option is disabled during import and
can be explicitly enabled, or selected through either current desktop preset.

The six originals have independently identified layouts and guarded patch plans.
That does not imply complete playthroughs of every route, region and seed.
See [validation scope](VALIDATION.md) for static, automated and native evidence.
