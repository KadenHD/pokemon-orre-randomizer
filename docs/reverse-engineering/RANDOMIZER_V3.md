# Randomizer v3: unique Shadow Pokémon families and accessible evolutions

PAL version GC6P01 revision 0, 30 October 2026. Algorithm
`unique-shadow-families-accessible-evolutions-v3`.

The v3 responds to two rules: the 48 identifiers of Shadow Pokémon must belong to 48 different
families of evolution, and the evolutions must be achievable in Colosseum. It always allows the
forms already evolved in the hashes.

## Jouer

Launch `jouer-randomizer-histoire.ps1` at the root. It opens ISO
`build/randomizer-v3/colosseum-pal-randomizer-v3.iso` with the separate profile
`build/randomizer-v3/play-user`, prepared without importing the original memory card.

Starting a **new part**. Changing ISO does not transform starters and Pokémon already captured in an
existing backup. The `dolphin-user` profile is used only for testing with a backup copy. The
launcher uses `play-user` to play.

The rules of the trainers and gifts of the v2 remain in force, including the six special
routines identified. For this seed: Smeargle level 26 and Slowbro level 25 at the start. External
events are not activated.

## Uniqueity of dark families

Families are calculated from the complete graph of the evolutions of the original `common.rel`: 386
species, 184 links, 202 related components. Branches are part of the same family, including Eevee,
Tyrogue, Wurmple and Nincada.

The v2 gave only 43 distinct families. The v3 keeps the smallest obscure identifier of each family,
reserves all families already retained and then removes only the five collisions, in the order of
the identifiers. The SHA-256 draw uses the seed and the key `shadow-family-v3:{identifiant}`. It
uses neither the time nor the overall state of the Python generator.

| Dark ID removed | Collision v2 | Replacement v3 |
| --- | --- | --- |
| 5 | Pidgey / Pidgeot | Vibrava |
| 31 | Gulpin / Swalot | Aerodactyl |
| 35 | Grimer / Muk | Porygon2 |
| 42 | Venonat repeated | Shroomish |
| 57 | Electabuzz repeated | Manectric |

The nine occurrences of these five groups in the blockers are synchronized with the table of the
Shadow Pokémon. The uniqueness relates to **48 groupes capturables**: the repeated encounters of the
same identifier retain the same species. The ordinary Pokémon of the blockers and the six gifts do
not change in relation to the v2.

## Developments made accessible

The 184 destinations and all branches are kept. Only 15 methods and conditions change, i.e. 30
effective bytes in the evolution data.

| Species | Developments | New condition |
| --- | --- | --- |
| Kadabra | Alakazam | Level 40 |
| Machoke | Machamp | Level 40 |
| Graveler | Golem | Level 40 |
| Haunter | Gengar | Level 40 |
| Onix | Steelix | Level 40 |
| Seadra | Kingdra | Level 40 |
| Scyther | Scizor | Level 40 |
| Porygon | Porygon2 | Level 40 |
| Poliwhirl | Politoed | Sun Stone |
| Slowpoke | Slowking | Water Stone |
| Clamperl | Huntail | Water Stone |
| Clamperl | Gorebyss | Moon Stone |
| Eevee | Espeon | Sun Stone |
| Eevee | Umbreon | Moon Stone |
| Feebas | Milotic | Level 40 |

The evolutions at level 40 are triggered by a level gain from 40 onwards, including if the Pokémon
is obtained above this threshold. Purification of the dark remains necessary. The native rules of
simple happiness, statistics of Tyrogue, personality of Wurmple and the special mechanism of Nincada
remain unchanged.

Examination of the PAL engine confirmed that the day/night methods of Eevee do not result in an
evolution. The engine also retains the last compatible branch: replacing all branches of a species
by the same level would remove choices. Separate stones therefore retain access to each destination.
Poliwrath remains accessible by Water Stone and Slowbro at level 37.

## Stones in store

The Sun, Moon, Fire, Lightning, Water and Plant stones are added to the purchase catalogues 3 and 5,
corresponding to Phenac City and Pyrite Town. Their price is **2,100** each. Only the original price
zero of the Moon Stone requires a change in `main.dol`. The other five prices are already 2,100.

The five archives `pocket_menu.fsys`, `pocket_menu_fr.fsys`, `pocket_menu_ge.fsys`,
`pocket_menu_it.fsys` and `pocket_menu_sp.fsys` are being modified. The REL catalogue occupies 109
of its 122 entries, without changing its size or relocations. The initial stocks remain available.
The three lists 0 to 2 are reordered to share their suffixes, without winning or losing any item.
The other nine lists remain identical. The types of dialogue and currency do not change. The other
eleven members of each archive are unchanged after decompression.

The first trial targeted lists 0 to 2, misinterpreted as buying menus. The actual test of Pyrite
Town detected the absence of stones in its catalogue. The correction targets the purchasing menus of
type 0. A regression check explicitly checks the stock of Pyrite Town and the absence of stones
added to lists 0 to 2. The test ISO is kept under `build/randomizer-v3-before-shop-fix/`.

## Reconstruction reproductible

```powershell
python scripts/randomize_accessible.py --source-iso 'Pokemon Colosseum (Europe) (En,Fr,De,Es,It).iso' --seed exemple-v3 --output-dir build/randomizer-v3
python scripts/randomize_accessible.py --verify-only --output-dir build/randomizer-v3
python -m unittest discover -s tests -v
```

The reconstruction always starts from the verified originals. `common.fsys` and the five store
archives are placed in the free space before the disk files. The six FST entries are updated. The
old copies remain in ISO. All bytes outside the allowed ranges are compared to the ISO source.

| Product file | SHA-256 |
| --- | --- |
| ISO v3 | `e37dae3666fae8323cb9f9c55c679c170053c96430d0d22fe2c6057e3aeea941` |
| `common.rel` v3 | `0dd207d42d07b483fa5fa745a22d244846af845a4bd8866b11c02432bb6d2360` |
| `main.dol` v3 | `381add7c69294f0ebd54d7019c195cc6bc9717db2f51f49cb6dee5a76ac33363` |
| REL of shops, common to the five languages | `322c09fe916c3dc5ac3f1c5e87c019639a09761bda6b92d6cb2df7ab3d346986` |

ISO size: 1,459,978,240 bytes. DolphinTool: successful verification, no problems reported, CRC32
`4540a9cd`, SHA-1 `37496b7c3607b871713fce6e52081ffbb44d1a44`.

## Verifications and limitations

The **43 tests** pass. They cover branched families, deterministic drawing and JSON stability,
shared obscure occurrences, preservation of ordinary and special hashes, rules of evolution, the
five languages and stocks of other shops. A second reading of the reconstructed ISO confirms the 48
families, the 15 rules, the payloads and the absence of modification outside the planned ranges.

The test under **Dolphin 2609a** normally started the final ISO, loaded the memory card copied with
"Continue", then joined the store of Pyrite Town. The six stones are visible to 2,100. The purchase
of one Moon Stone was made: quantity 0 → 1 and balance 8,015 → 5,915. The original bag being full,
the two Super Potions of the copy were first sold to release a location. No change was made to the
original backup.

A fast state from the first test was discarded for final validation, as it would restore the old RAM
catalog. The final captures come from the normal route from the memory card on the corrected ISO.

- [The six stones at 2,100](../../build/randomizer-v3/evidence/02-six-stones-at-2100.jpg).
- [Moon Stone prior to
  purchase](../../build/randomizer-v3/evidence/05-moon-stone-free-slot-before.jpg).
- [Moon Stone received and balance
  debited](../../build/randomizer-v3/evidence/06-moon-stone-purchase-success.jpg).
- [Validation summary](randomizer-v3-validation.json).

Dolphin test evidence and integrity checks are recorded in `randomizer-v3-validation.json` and
`build/randomizer-v3/evidence/`. The full progression of the scenario, balancing and triggering of
each branch of evolution remain to be validated. Phenac City and the other four languages are
checked in the data. Their interface has not been searched. The binary controls are not presented as
a complete part.

The `game/` files, the source ISO, the old ISO and the original Dolphin profile are kept. Test and
game backups are isolated.

## Sources of Formats and PAL Evidence

Offsets and hashes are checked on this PAL dump. Community sources are used to interpret structures.
They do not replace this regional verification.

- [Evolution methods of
  Pokemon-XD-Code](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/enums/XGEvolutionMethods.swift).
- [Structure of an
  evolution](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/XGEvolution.swift).
- [Structure and price of
  objects](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/enumerable/CMItem.swift).
- [Symbols of REL
  tables](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/file%20formats/XGRelocationTable.swift).
- [Engine decompilation, US
  substantiation](https://github.com/dougchansan/pkmn-colosseum/blob/ad02df4900c623d16d02b9a8ddd9c53ea0cd3db2/src/game/pokemon_range_80128524.c).
  The PAL dispatch was independently checked at RAM `0x8012C87C` / DOL offset `0x12987C`, with its
  RAM jump table `0x803B0510` / file `0x3AD510`.
