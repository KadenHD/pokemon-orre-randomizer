# Fairy reference data

`catalog.json` is a small, version-pinned selection from
[PokeAPI/pokeapi](https://github.com/PokeAPI/pokeapi/tree/de6760be38b60a3024f1d9054330ff265f0dc619)
at commit `de6760be38b60a3024f1d9054330ff265f0dc619`.

The gameplay reference is **Brilliant Diamond / Shining Pearl**, version group
23. Its ordinary battle and level-up data covers all 386 base species present
in the GameCube games. The selected data contains 18 modern Fairy species
typings, the three existing moves that became Fairy, seven new move definitions,
and 223 exact learning-method records for those ten moves. Names and move
descriptions are provided in English, French, German, Spanish, Italian and
Japanese. The desktop sheets use the reference game's full flavor text with
whitespace normalized. Native game menus use separately authored concise prose
from `fairy_message_layout.py`, measured with the original glyph advances and
wrapped for their distinct move-summary and Bag panels. These menu summaries
do not replace the reference descriptions in this dataset.

Species numbers are **National Dex IDs**, not GameCube internal species IDs.
Type and move numbers in the JSON are **PokeAPI canonical IDs**. The production
installer must supply its qualified native allocation. PokeAPI effect IDs are
also canonical metadata; they must never be written as native effect IDs.

The natural-learning transform retains all original moves and original levels.
It merges Fairy additions, ignores duplicate additions, and fails rather than
truncating a learnset that needs more than 19 native records. The selected data
fits all six original regional tables: 114 additional level-up records across
64 species per game, without overflowing a native row. Evolution-only level-0
records are exposed separately for Togetic and Gardevoir. A level-0 record is
never written over the native learnset end marker. These events have separate,
legitimate level-1 records in the reference data; they are not synthesized.

The dataset distinguishes real reference-game **machine compatibility** from
broader **learnability** through level-up or egg moves. Most of the seven new
TMs are authored additions rather than existing BDSP machines. Choosing broader
learnability as their compatibility is an explicit game-design policy, not an
official TM list.

The catalog includes source URLs, SHA-256 values and extraction coverage. The
large source CSVs are filtered and are not bundled. Type-affinity entries cover
only pairs involving Fairy; this does not silently modernize other generation
III matchups or define a Shadow-type damage policy. Native effects, targets,
flags, animations, item actions and memory layout need their own qualifications.

PokéAPI data is distributed under its BSD 3-clause terms. Keep
`LICENSE-PokeAPI.txt` with redistributed data. Pokémon names and game flavor
text retain their original rights. This reference data is separate from the
project's MIT-authored code and implies no endorsement by its contributors.

`transfer-messages.json` is separate from the PokeAPI dataset. It records the
six original XD transfer-refusal messages, their source archive identities and
native message bytes. Colosseum uses the message body without XD's speaker or
color prefix; Japanese furigana and the original message controls are retained.
This small game-text extract remains the property of its original rights
holders. It is used only when a Pokémon knows an added move that a generation
III GBA game cannot represent. Ordinary transfers keep their native rules.
