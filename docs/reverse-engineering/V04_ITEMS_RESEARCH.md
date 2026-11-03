# Found objects and shops: PAL perimeter v0.4

Research on **October 31, 2026**, read-only on originals. No engine, option, screen, disk or Dolphin
profile modified. The only files produced are this note and references under
`analysis/generated/v04-item-references/`.

The conclusions distinguish the observed bytes, the interpretations of primary tools and the
remaining behaviors to be observed. The directly exploitable perimeter is **the table of objects
placed**, then **six catalogues of selected shops**. This does not cover all the rewards of script
scripts.

## Identities and evidence retained

| Source originale | SHA-256 |
|---|---|
| `game/sys/main.dol` | `a788176a45eb88dbd227246a7205ab9856bc79f3cca7e4a0f5376cf466664df5` |
| Decompressed member `common_rel` | `ee2677af555dc59626f978e743235831a76cb23bae93f3fdd1060d808f749d0b` |
| Decompressed member `pocket_menu` of the five languages | `524ad778c3618d0c675e69f6a6bd6fab2e4e929d5a2e6981c1a8c25a555f9f20` |

`analysis/generated/v04-item-references/local-inventory.json` lists **397 item records**, **74
placements**, **14 catalogues**, the five FSYS/REL identities and capacity tests. SHA-256:
`2ff796026fdd369ddc832065d14641e13358466c24c56fc6d5086338d9e19224`.

`source-manifest.json` keeps the local Git and SHA-256 URLs, commits, identities of nine primary
snapshots. Swift sources are frozen at the commit `f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0` of
Pokemon-XD-Code. The two native sources NTSC-U at the commit
`ad02df4900c623d16d02b9a8ddd9c53ea0cd3db2` of pkmn-colosseum. These copies are search documents, not
the code embedded in the engine.

## Objects placed: localized structure without search by pattern

[CMRelIndexes.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/CMRelIndexes.swift)
names the community symbols **60 = TreasureBoxData**, **61 = NumberTreasureBoxes**. Their resolution
through the relocation stream of the original PAL gives.

| Element | Offset in `common.rel` | Value |
|---|---:|---:|
| Table start, symbol 60 | `0x1EAB74` | — |
| Compteur u32, symbole 61 | `0x219298` | 74 |
| Recording size | — | `0x1C` |
| Fin exclusive | `0x1EB38C` | Exactly the following symbol |

The structure is corroborated by
[XGTreasure.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/enumerable/XGTreasure.swift)
and
[TreasureTable.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/struct%20tables/TreasureTable.swift).

| Offset relatif | Encodage | Field |
|---:|---|---|
| `+0x00` | u8 | Model |
| `+0x01` | u8 | Quantity |
| `+0x02` | u16 BE | Angle |
| `+0x04` | u16 BE | Identifier de salle |
| `+0x06` | u16 BE | Reception flag |
| `+0x08` | u16 BE | Unknown field |
| `+0x0A` | u16 BE | Filling declared by the tool |
| `+0x0C` | u32 BE | Identifier d'objet brut |
| `+0x0E` | u16 BE | Low part of this identifier |
| `+0x10/+0x14/+0x18` | float BE | X/Y/Z coordinates |

**PAL observation: 74 parts high to `+0x0C` are null.** A patch limited to u16 to `+0x0E` is enough
here. Quantity, model, angle, room, flag, other fields, coordinates and table size must remain the
same. Indices are preserved: they can be referenced by scripts and backups.

### Gross identifier and object index are not always equal

The table of objects is in the DOL to `0x3ADDA0`, **397 records of `0x28` bytes each**. Pocket fields
`+0`, prix u16 `+6`, name u32 `+0x10` and description u32 `+0x14` viennent de
[CMItem.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/enumerable/CMItem.swift),
already retained in `v03-references/`.

[CMItems.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/enums/CMItems.swift)
subtracts **151** from the gross values verifying `397 < raw < 0x250` The observations confirm,
inter alia.

- `500 → 349`: Prison key, pocket 5.
- `537 → 386`: Flute of Time, **poche 2 mais prix nul**.
- `543/544/545 → 392/393/394`: the three perfumes, pocket 6.

It is necessary to normalize **before** filter objects. Preserving the raw identifiers of the
protected entries: the reverse `scriptIndex` of the tool starts at index 350, while the Key of the
observed prison is 349. Do not deduce a universal reverse conversion at this border.

### Inventory and protections directly verified

The 74 placements include **61 nonzero identifiers** and **13 empty slots**: indices `0,
62..73`. Active entries are divided into 35 pocket objects 2, 16 pocket items 5, five lots of Balls
and five TM.

| Protection | Investment indices |
|---|---|
| Key objects, pocket 5 | `2,3,8,19,26,27,28,29,30,40,41,44,45,46,47,54` |
| Flutes of Time, no price | `4,61` |
| Lots de Balls | `6,11,36,37,43` |
| Empty slots | `0,62..73` |

Investments 2 and 3 share **the flag 153 and the Key of the crude prison 500**. It is the only
active shared flag observed. Do not treat these lines as two independent rewards.

With these protections, **38 placements** remain candidates, corresponding to 29 separate object
IDs. The five TM found are objects **314,333,334,335,337**, named CT26, CT45, CT46, CT47 and CT49.
No object 93..98 is placed in this original table. Nevertheless preserve their guaranteed
availability in store when the option of accessible evolutions is active.

An option that retains care can protect **18 placements** whose names are observed as potions, total
care, recalls, ethers and elixirs: `1,5,7,9,10,12,13,22,23,25,32,34,38,49,50,51,52,55`. The IDs
concerned are `19..25,34..37`. This selection is a product policy based on names and uses, not an
additional category stored in the investment table.

### Limit: Rewards and Rewrite at Execution

The table does not contain **no Master Ball (ID 1)**: therefore, changing its lines does not cover a
possible scenario reset.
[CMScriptBuiltInFunctions.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/scripts/Colosseum/CMScriptBuiltInFunctions.swift)
separately describes the standard function **119, `playerReceiveItem(item, quantity)`**.

The [decompiled native code
`floorEventChangeTresure`](https://github.com/dougchansan/pkmn-colosseum/blob/ad02df4900c623d16d02b9a8ddd9c53ea0cd3db2/src/game/floor_event_exact_80115CB4.c)
also rewrites the object word and the quantity of a line at execution. These sources show distinct
mechanisms. The PAL callers and the corresponding CMS constants have not been inventoried here. The
honest range is "table objects", without announcing all the rewards of PNJ or tournaments.

To expand this perimeter, request a typed proof: CMS/REL archive and member, binary identity,
decoded standard instruction or call, object argument and quantity, and then observation or trace of
attribution. An isolated hexadecimal occurrence of an ID is not proof of attribution.

## Shops: five archives, one table

All variants have **12 membres**. The member **0**, named `pocket_menu`, has the identifier FSYS
`0x03711C00`. Its REL is **module 2, version 3, imports `[2,0]`**, size **1,672 bytes**, SHA-256
identical in all five languages. The other eleven members must be preserved after decompression.

| File in `game/files/` | Groupe FSYS |
|---|---:|
| `pocket_menu.fsys` | 20 |
| `pocket_menu_fr.fsys` | 2021 |
| `pocket_menu_ge.fsys` | 2020 |
| `pocket_menu_it.fsys` | 2022 |
| `pocket_menu_sp.fsys` | 2023 |

The pocket symbols **2/3** provide the list of objects and its counter. **4/5** the descriptors and
their counter, according to
[CMRelIndexes.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/CMRelIndexes.swift).

- Physical list: **122 u16 BE to `0x2AC`**, end `0x3A0`. Zero ends each stock.
- Descripteurs : **14 × 4 bytes to `0x3A0`**, fin `0x3D8`. structure `u8 type, u8 subtype, u16
  start_index`.
- Only the list and the beginning clues require writing. Counters, headers, sections, imports and
  relocations remain unchanged.

### Types: Do not confuse dialogue with operation

[XGPokemart.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/enumerable/XGPokemart.swift)
calls the types of dialogue `0 pokemart, 1 vendingMachine, 2 shop, 3 herbShop`. Subtypes are `0
shop, 1 vendingMachine, 2 bonusDiscCoupons, 3 brokenCoupons, 4 pokeCoupons`.

**These fields alone do not explicitly code "purchase" or "sale".** The lists 0–2 are therefore
referred to below by their gross values. Their exclusion from the reprint remains a perimeter rule.
The purchases of menus 3 and 5 have been the subject of previous tests, recorded in
`RANDOMIZER_V3.md`.

### Accurate inventory of the 14 original descriptors

| Index | Type/subtype | Start | Gross stock, in order |
|---:|---|---:|---|
| 0 | 2/0 | 0 | `14,15,16,17,18` |
| 1 | 2/0 | 6 | `14,15,16,17,18,3,4,23` |
| 2 | 2/0 | 15 | `14,15,16,17,18,23,3,4,2,6,8,10` |
| 3 | 0/0 | 28 | `13,22,14,15,16,17,18,23` |
| 4 | 0/0 | 37 | `73,74,75,76,77,78,79` |
| 5 | 0/0 | 45 | `21,22,23,24,14,15,16,17,18` |
| 6 | 0/0 | 55 | `21,22,23,24,63,64,65,66,67,70,543,544,545` |
| 7 | 0/0 | 69 | `19,20,21,23,24,298,302,303,304,305,308,313,321,326` |
| 8 | 3/0 | 84 | `30,31,32,33` |
| 9 | 0/0 | 89 | `298,302,303,304,305,308,313,321,326` |
| 10 | 1/1 | 99 | `26,27,28` |
| 11 | 2/2 | 103 | `301,312,317,323,320,169,170,171,172,200,185,196,180,183,179,187,198,186` |
| 12 | 1/3 | 103 | Same list as 11 |
| 13 | 0/4 | 103 | Same list as 11 |

The intended drawing perimeter is **3,4,5,6,7,9**. Preserving 0–2, herbalist 8, distributor 10 and
coupon catalogues 11..13 in the state received by the new pass. Protecting in particular the raw
perfumes **543..545** pocket 6, even if their price is positive. The three coupon catalogues
physically share the beginning 103: a blind substitution in the physical list would change all their
aliases.

### Allocation: measures and strategy without expansion

A global bijection, applied to the same eligible IDs in all the targeted menus, retains suffix
sharing between 7 and 9. Then reassemble the **14 listes logiques**. Indices can change, while the
IDs, order and types of non-target menus remain identical to the input state of the pass.

Measurements with the current packer, replacing globally 34 IDs targeted with separate artificial
IDs `1000+n`, absent from the protected menus. These IDs are only a **capacity probe**, never a pool
of objects to inject into the game.

| Entry State | Packing before mapping | After disjointed bijection | Move |
|---|---:|---:|---:|
| Original REL, without stones | 106 | **112** | 122 |
| REL current after `patch_rel(stones)` | 109 | **109** | 122 |

The actual variants and the classification of the objects must always be checked before publication.
This measure does not replace the final check `used <= 122` for each option and seed.

If a future contract also requires the lists 0–2 in **their original order**: add the
stones at the end of the two menus 3/5 takes 124 entries and exceeds the allocation. **Prefix** the
stones on menu 5, and prefix or suffix them to 3, restores the shared suffix of the list 0 and keeps
in **118 entries**, without reordering any original stock. No expansion or shift of REL section is
necessary for this variant.

## Controls to be applied when integrating

- Check the original fingerprints and symbols terminals before any changes.
- Objects placed: whitelist of the only u16 objects selected. Protect the 13 voids, 16 keys, two
  Flutes of Time and five lots of Balls. Quantities and flags remain the same.
- Shops: prices and pockets are evaluated after normalisation of the ID. Preserve Balls, guaranteed
  stones, keys, perfumes and objects at zero price according to the contract chosen.
- All non-target menus keep their logical lists, types and currencies. The three coupon catalogues
  remain the same.
- The five reconstructed shop RELs are identical. The other eleven members of each archive remain
  identical after decompression.
- Check in the final ISO for actually written payloads and FST/DOL ranges, then observe at least one
  catalog and pick-up. This search does not run any game scenarios.
