# Pokémon sheets and the HTML journal

In either game, click a starter, Shadow Pokémon or gift once to open its sheet.
The sheet describes the final configured encounter: types, possible abilities,
base stats, initial moves, learnsets, compatible TMs and evolution routes.
Names use initial capitals; a small red superscript star marks a known shiny.

Known encounters load automatically from a selected original ROM. This partial
read never prepares the complete patch plan or selects unknown replacements.
Click **Calculate preview** to draw randomized encounters. Both paths use the
same property transforms and encounter readers as ROM creation.

Retained species and their evolution families keep native properties by default;
**Advanced > Allowed Pokémon > Randomize preserved Pokémon’s properties** opts
them into the selected rules. Shiny settings and accessible evolution routes
still apply. Shared TM permutations preserve the original compatible move set,
not the old TM numbers. Properties are shared by every copy of the species.

Poké Spot encounter levels vary. Their sheets show the resulting level-up
learnset and TM compatibility, without claiming to know the four active moves
of a future wild encounter. Possible abilities are fixed for the species;
individual encounters can choose between them, as in the original game.

## Evolutions

Routes and conditions come from the final patched data. The sheet does not infer
them from a modern Pokédex or an option checkbox. Each branch includes source
and target portraits. Known shiny encounters use shiny portraits throughout.
Shadow Pokémon must first be purified where the game requires it.

For example, Colosseum's trade-with-item adaptation shows Onix → Steelix by
leveling from level 40. Without adaptation, it shows the native Metal Coat trade
requirement. Gastly → Haunter at level 25 → Gengar at level 40 appears when trade
evolutions are adapted. Consult the actual sheet for the selected game's rules.

Possible abilities are not a prediction of the ability, IVs, nature, gender or
full PID that the game will generate. Unknown special markers retain their
identifier instead of being mislabeled as ordinary moves or abilities.

## Languages and data

Sheets and journals support all six interface languages. Native ROM name banks
are used where available; offline fallback catalogs supply the remaining names.
Their provenance is in the [third-party notices](../THIRD_PARTY_NOTICES.md).
Stats, move properties, evolutions and TM compatibility come from the configured
game data. Displaying a sheet makes no network request.

## HTML journal

Creation writes an `.iso.html` or `.rvz.html` file beside the new image. It uses
the same final snapshot and does not redraw encounters. Collapsible sections
keep spoilers closed until opened. Contents reflect each game's roster,
including XD trades/Poké Spots and Colosseum purification gifts where applicable.

The journal identifies the seed, version, game and hashes. It omits personal
paths and contains no scripts or external resource loads. Text is escaped.
The CLI supports `--journal-language fr|en|de|es|it|ja`, defaulting to French.
Existing journal paths are never overwritten.

Known seeded shiny decisions are shown. XD's wild Poké Spot rows describe
intermediate rates as a new roll for each encounter; the journal cannot predict
those future rolls. Gift entries retain their obtainability conditions.
Tests cover final-data reads, evolution branches, all six languages, escaped
content, offline output, path privacy and overwrite refusal.
