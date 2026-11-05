# Interface and game languages

Both workspaces support **English, French, German, Spanish, Italian and Japanese**,
including before a ROM is selected. **System** uses the first recognized system
language; variants such as `es-MX`, `de-CH` and `fr-CA` use the corresponding
catalog. If none matches, the interface uses English. A manual choice is saved
and can be returned to System.

Changes apply immediately to navigation, labels, help, errors, progress, previews,
Pokémon sheets and journals. Paths, seeds, profiles and active work are preserved.
Interface language never participates in a seeded draw. Native file dialogs
retain system behavior, with application-supplied titles and filters translated.

## In-game language

The selector does not translate the ROM. Both games support the six revision-0
originals listed in [compatibility](COMPATIBILITY.md). European games provide
English, French, German, Spanish and Italian text banks; USA uses English and
Japan uses Japanese. Patched text uses those banks independently of the interface.

Colosseum's optional stone-name correction adds readable spaces where appropriate,
without splitting German compound words or replacing native Japanese names.
XD retains its own native stone names. Colosseum purification-reward dialogue
and XD trade/tutorial replacements follow the game's language. An unchanged
copy leaves original text intact.

| Language | Sun | Moon | Fire | Thunder | Water | Leaf |
| --- | --- | --- | --- | --- | --- | --- |
| French | Pierre Soleil | Pierre Lune | Pierre Feu | Pierre Foudre | Pierre Eau | Pierre Plante |
| English | Sun Stone | Moon Stone | Fire Stone | Thunder Stone | Water Stone | Leaf Stone |
| German | Sonnenstein | Mondstein | Feuerstein | Donnerstein | Wasserstein | Blattstein |
| Spanish | Piedra Solar | Piedra Lunar | Piedra Fuego | Piedra Trueno | Piedra Agua | Piedra Hoja |
| Italian | Pietra Solare | Pietra Lunare | Pietra Focaia | Pietra Tuono | Pietra Idrica | Pietra Foglia |

Fallback interface names cover languages absent from the ROM, as documented in
the [third-party notices](../THIRD_PARTY_NOTICES.md). Game properties are read
from the patched ROM rather than a modern online Pokédex.

Tests cover catalog completeness, format parameters, locale resolution, saved
preferences and switching during active work. Windows diagnostics cover both
games, six languages and two sizes; see [validation](VALIDATION.md).
