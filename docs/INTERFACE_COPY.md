# Interface text

The tool is intended for players who choose their ROM and settings. Texts should explain the effect
of an option or the next action.

The three choices of Simple mode are starting points, not custom settings.

| French | English | Japanese | Scope |
| --- | --- | --- | --- |
| Pokémon + moves | Pokémon + moves | ポケモン＋わざ | Pokémon of near power, abilities and learnings, TM, chests and shops |
| Pokémon only | Pokémon only | ポケモンのみ | Pokémon replaced without balancing. Capabilities, learnings and TM preserved |
| Unchanged copy | Unchanged copy | そのままコピー | Game data unchanged, ISO/RVZ conversion possible |

The descriptions specify the Pokémon involved and the aids common to the two randomized modes:
evolutions, sale of stones and different families of Shadow Pokémon. The text "Custom settings" appears
when the options differ from the three predefined choices. It indicates how to view them in Advanced
and select a predefined choice replaces them. The values of the three sets of options are unchanged.

"View the starters" is an explicit action to reveal the print. Before the calculation, the legend
names the original portraits. After the calculation, it confirms the correspondence with the seed
and the settings. An amendment replaces the result with the originals with an invitation to
recalculate. A change of language translates the result already calculated without restarting the
print. The Japanese names of the 386 species come from the PokéAPI data set, under its license held
in `licenses/pokeapi.txt`. The selection and the print are in `licenses/pokeapi-names.json`. The
French and English names and the portraits are read in the selected ROM. No external service is
called during the preview.

| French | English | Usage |
| --- | --- | --- |
| Original ROM | Original ROM | File selected by the player, always kept |
| New ROM | New ROM | File created by tool |
| Settings | Settings | Choices that determine the party |
| Profil | Profile | File containing the seed and settings |
| Moves | Moves | Use the term Pokémon, including for offensive capability |
| Abilities | Abilities | Not to be confused with capabilities |
| Pokémon offered | Gift Pokémon | Pokémon received as a gift or reward |
| Family of evolution | Evolution family | Species linked by evolution |

- The buttons name the action: "Create ROM", "Open Report".
- The boxes describe their effect: "Replace Umbreon", "Keep the care in store".
- The aids explain the behaviour of the present. They retain the useful limits: level 40, stone
  prices, threshold of statistics, etc.
- The entry entries are in one or two sentences and do not repeat the list of options.
- An error indicates what blocks and how to resume. Internal details do not replace this
  explanation.
- Avoid slogans, repetitions and internal terms such as "identified routine", "native bytes" or
  "markers" in the current course.
- The settings names, translation parameters, profile values, and seed are distinct. A reformulation
  does not change the hashes.

The French wording is in `options.py` and `gui.py`The English and Japanese catalogues are in
`locales/en.py` and `locales/ja.py`. Any changes must remain consistent in all three languages and
retain the meaning of the options.

In Japanese: for abilities, for talents, for basic statistics, and for Shadow Pokémon, according to
[official Japanese presentation](https://www.pokemon.co.jp/game/other/colosseum/). The purification
is [リライブ](https://www.nintendo.co.jp/ngc/gxxj/snatch/index.html). File names, seeds, settings
identifiers and formatting fields are kept literally. Japanese texts use system fonts with folding
on Yu Gothic UI, Meiryo and Noto Without CJK JP. No proprietary font file is distributed with the
application.
