# Pokémon and HTML Log

The sheets describe the final data of the configured part: types, talents, basic statistics, initial
skills, learnings, TM compatible and branches of evolution. They are calculated after the rules of
Pokémon, boss, levels, abilities, TM and names.

## Evolutions

The methods are reread in the final REL. The display does not deduce an evolution of the original
species or a simple check box. With the adaptation of the exchanges with object, the onix record
indicates a level rise from level 40. Without this adaptation, it displays the exchange with Metal
Coat and indicates that this condition requires an adaptation to be accessible in Colosseum.

All the following branches are included. With the adapted evolutions, Gastly] indicates Gastly →
Haunter at level 25, then Haunter → Gengar at level 40. A required stone bears its name in the
display language. Shadow Pokémon recall that they must be purified before they can evolve.

Talents are presented as possibilities: the sheet does not claim to predict the talent actually
chosen by the game, the IVs, the genre, the nature or the complete PID. Native rules depending on
the personality remain reported as such. Unknown abilities or special markers retain their
identifier instead of being assigned to an ordinary ability.

## Languages and origin of names

The display is available in French, English, German, Spanish, Italian and Japanese. The native names
of the ROM are used when it has the requested language. For the other languages of the US and
Japanese ROMs, the interface names use the BSD catalogues of
[PokeAPI](https://github.com/PokeAPI/pokeapi): species, types, 354 ordinary abilities, 77 talents
and 12 objects of evolution.

These catalogues only provide names. Power, precision, PPs, statistics, types, permissible talents,
compatibilitys and conditions of evolution come from the final bytes of the game. Modern names of
the replica catalogue do not change the texts or mechanics of the ROM.

`licenses/pokeapi-details.json` keeps the URLs, SHA-256 fingerprints of the three source CSVs, their
selection and the hash of the product module. The `scripts/generate_detail_names.py` script
reconstructs the module from these locally provided CSVs. No download takes place during the use of
the application. The license is kept in `licenses/pokeapi.txt`.

## Journal

The HTML log can be viewed offline in a browser. Its sections start closed: settings, starters,
Shadow Pokémon, gifts, trainers, evolutions and TM. Open a section reveals its content. The following
sections remain closed. The journal takes the same final snapshot as the cards, without pulling the
Pokémon a second time.

Seed, version, identity of the game and its fingerprints are displayed. The personal paths of the
creation report are not included. Seed, name or setting texts are eluded as text, even if they
contain tags. The file does not board script, game image, resource or network request. A content
policy prohibits external loadings.

The Shiny status is announced only when it is known: rate of 0 or 100%, or decision related to the
seed. With an intermediate rate without connection, the newspaper indicates that the status will be
decided at stake.Eagun remain displayed for the relevant gifts.

## Verification

The tests cover the reading of the final bytes despite different origin values, the conditions of
evolution, the prior purification, successive branches, the six languages, the compatibility TM, the
absence of modifications of instant and the refusal of invalid references. The journal is controlled
for its spoilers closed, its escaped texts, the absence of personal path and external resource, and
the refusal to crush an existing file.

The sheets do not constitute an observation in play of each evolution or a prediction of all native
hashes. They describe the final data of the new part and distinguish the properties still decided by
the game.
