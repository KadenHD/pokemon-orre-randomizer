# Languages of the interface and game

The tool offers the six original languages of Pokémon Colosseum: French, English, German, Spanish,
Italian and Japanese. They are all accessible in the selector, even before loading a ROM.

On startup, **System** follows the first language recognized in the system preferences. A regional
variant such as `es-MX`, `de-CH` or `fr-CA` uses the corresponding catalogue. If no language is
recognized, the tool uses English. The manual choice is recorded and can be returned to **System**.

The change applies immediately to pages, options, aids, errors, progress and file dialogs. Paths,
seed and profiles remain intact. It does not change the settings or the result of randomization. L的
preview keeps its result and displays the names in the new language, including Japanese names. The
numbers of the national Pokédex are also used for searching. The sheets and HTML log follow the
language of the tool.

## Language in the game

The tool selector does not translate the ROM. The engine accepts **Colossium Europe `GC6P01`, USA
`GC6E01` and Japan `GC6J01`, revision 0**, in ISO or RVZ format, with control of the full footprint
of each image. The interface retains its six languages regardless of the region of the ROM.

The five European banks are kept. The European game displays the names of stones in the language
chosen in the game, regardless of the tool.

| Language of the game | Soleil | Lune | Feu | Foudre | Eau | Plante |
| --- | --- | --- | --- | --- | --- | --- |
| French | Pierre Soleil | Pierre Lune | Pierre Feu | Pierre Foudre | Pierre Eau | Pierre Plante |
| English | Sun Stone | Moon Stone | Fire Stone | Thunder Stone | Water Stone | Leaf Stone |
| German | Sonnenstein | Mondstein | Feuerstein | Donnerstein | Wasserstein | Blattstein |
| Spanish | Piedra Solar | Piedra Lunar | Piedra Fuego | Piedra Trueno | Piedra Agua | Piedra Hoja |
| Italian | Pietra Solare | Pietra Lunare | Pietra Focaia | Pietra Tuono | Pietra Idrica | Pietra Foglia |

The option **Add spaces to stone names** corrects eleven PAL words and a US wording without
replacing native translations. The US ROM retains English. The Japanese ROM retains its Japanese
names, without any patching. The German compound words remain in one word. One **Unchanged copy**
leaves all original texts unchanged.

## Verification

The tests check the keys, formatting fields and choices of all options, the detection of regional
variants, the persistence of choice and the preservation of the form and preview. The diagnosis of
the executable runs through 48 states: six languages, two window sizes and four pages or modes. It
also checks the loading of Qt translations of the dialogs.

The local validation of November 1, 2026 checks the fourteen settings categories and the Simple mode
in the six languages, at 1040 × 800 and 680 × 540, i.e. 180 states without horizontal overflow
detected. It reads the 30 stone names in the ROM banks. For the `98205757d6a5da47` Seed, the ISO and
RVZ previews correspond to the result of the previous version and the fingerprints of the sources
remain the same. These controls do not constitute a complete part under Dolphin. No profile or
personal backup is opened.

Local reports are stored in `build/languages-2026-11-01/` and excluded from distributions. The
engine files are identical to those in the previous version. Only localized names are added to the
report metadata.

The regional validations and the fact sheets/newspapers added since this test are described in
[notes v0.15](DESKTOP_V15.md). The search, the reset of a category and the summary of v0.16 are
followed in [notes v0.16](DESKTOP_V16.md), with their own validation results.
