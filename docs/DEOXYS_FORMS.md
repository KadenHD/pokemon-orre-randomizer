# Deoxys forms

Available in v2.1.4 and later. Create a new randomized ROM to include these
changes; updating the desktop application does not patch an existing ROM.

Colosseum can use all four Deoxys forms. Attack, Defense and Speed use XD's
original meshes, skeletons and animation tracks. XD keeps its existing form
resources. Both games support standard and shiny appearances in Original and
HD play folders. Colosseum's imported HD materials require the pinned XD pack.
XD's Purify Chamber keeps its native animated 2D sprites; this feature does
not add x4 replacements for those animations. Prerecorded videos stay original.

The randomizer chooses each newly drawn Deoxys's initial form from the seed.
The encounter preview, battle and capture use the same choice. Keeping a native
Deoxys also keeps its native initial behavior; this does not change the species
pool or enable legendary Pokémon in the default presets.

## Change form in-game

Open the field Bag, select **METEORITE**, choose **USE**, select a party Deoxys
and choose **NORMAL FORME**, **ATTACK FORME**, **DEFENSE FORME** or **SPEED FORME**.
Cancel leaves it unchanged. The Meteorite can be reused and also works on
Shadow Deoxys.

The item is added when the field Bag opens if it is missing and an ordinary
item slot is free. It uses no Key Item slot or story flag. If the Items pocket
is full, free a slot and reopen the Bag. The item cannot be sold, given to a
Pokémon or discarded. It cannot be used in battle.

A form change preserves the PID, original trainer, shiny status, nickname,
nature, IVs, EVs, level, experience, moves, held item and Shadow progress. It
updates the form's derived battle stats without healing the Pokémon. The form
is stored with the Pokémon through party/PC movement, saving and purification.

| Form | HP | Attack | Defense | Sp. Atk | Sp. Def | Speed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Normal | 50 | 150 | 50 | 150 | 50 | 150 |
| Attack | 50 | 180 | 20 | 180 | 20 | 150 |
| Defense | 50 | 70 | 160 | 70 | 160 | 90 |
| Speed | 50 | 95 | 90 | 95 | 90 | 180 |

The four forms share the game's Deoxys learnset and TM rules. Advanced stat
randomization also produces form-specific stats, keeping their HP and total
base stats equal so repeatedly changing form cannot restore HP.

## Stored identity and displays

The saved form is independent of the PID. A tagged reserved halfword stores
the form in a native Pokémon record; species 410 stays Deoxys rather than
becoming a substitute species. Readers ignore unmarked and foreign records.

Temporary Snag List and DNA displays resolve a captured specimen by exact
Shadow ID and PID in the party, PC, Day Care or XD's Purify Chamber before
falling back to its initial form.
The Purify Chamber selects the matching native animated sprite for the saved
form and palette, using XD's existing resources.
XD's original shiny Normal Forme portrait is brown/orange, while its shiny 3D
model is yellow. This original palette difference is preserved; changing form
does not change whether Deoxys is shiny.
The DNA keypad keeps its native puzzle keys and composes each appearance
independently, including all four forms and both palettes. HD uses separately
rendered x4 artwork rather than an enlarged native bitmap.

The Meteorite's name, description, messages and form menu follow the playable
language: English, French, German, Italian, Spanish or Japanese. Its private
message banks do not replace an existing game's dialogue. Native item and
Pokémon names and the form choices use the games' uppercase convention in
alphabetic languages. The form popup measures its translated choices before
opening, and the short description uses the native line-break control.

Preservation through a connected external GBA game is not established. This
feature does not promise form retention after exporting a Pokémon to another
game or storage system outside these two randomized ROMs.
