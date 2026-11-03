# Items held: PAL combat list verified

Static analysis of October 31, 2026, without writing in the game or running Dolphin. The IDs and
names below were read in the original data, without resuming from memory a numbering of another
version.

## Source and verification

- DOL PAL : SHA-256 `a788176a45eb88dbd227246a7205ab9856bc79f3cca7e4a0f5376cf466664df5`.
- `common.rel` : SHA-256 `ee2677af555dc59626f978e743235831a76cb23bae93f3fdd1060d808f749d0b`.
- Primary schema: [CMItem.swift, commit
  f2d6c4a](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/enumerable/CMItem.swift).
  The PAL table is in the DOL at `0x3ADDA0`, with a step of `0x28` and 397 entries. Fields used:
  pocket `+0x00`, indicator preventing holding `+0x01`, object effect held `+0x0B`, name ID `+0x10`,
  parameter `+0x1B`.
- Resolution of names corroborated by
  [CMItems.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/enums/CMItems.swift):
  the ID read in the DOL refers to the texts of `common.rel`.
- Candidate IDs only come from populated locations actually referenced by the original teams. Each
  selected item has a valid UK/FR name, a non-zero holding effect, a zero holding indicator and a 2
  or 3 pocket.
- Reproducible local detail: `analysis/generated/v03-references/held-items-local.json`.

## Recommended list for generic combat objects

44 ID .

```python
(133, 134, 135, 136, 137, 138, 139, 140, 141, 142,
 168, 169, 170, 171, 172, 179, 180, 183, 185, 186, 187, 188,
 196, 198, 199, 200, 203, 204, 205, 206, 207, 208, 209, 210,
 211, 212, 213, 214, 215, 216, 217, 219, 220, 221)
```

| ID | UK name observed | Observed FR name | Effect brut |
| --- | --- | --- | ---: |
| 133 | CHERI BERRY | BAIE CERIZ | 2 |
| 134 | CHESTO BERRY | BAIE MARON | 3 |
| 135 | PECHA BERRY | BAIE PECHA | 4 |
| 136 | RAWST BERRY | BAIE FRAIVE | 5 |
| 137 | ASPEAR BERRY | BAIE WILLIA | 6 |
| 138 | LEPPA BERRY | BAIE MEPO | 7 |
| 139 | ORAN BERRY | BAIE ORAN | 1 |
| 140 | PERSIM BERRY | BAIE KIKA | 8 |
| 141 | LUM BERRY | BAIE PRINE | 9 |
| 142 | SITRUS BERRY | BAIE SITRUS | 1 |
| 168 | LIECHI BERRY | BAIE LICHII | 15 |
| 169 | GANLON BERRY | BAIE LINGAN | 16 |
| 170 | SALAC BERRY | BAIE SAILAK | 17 |
| 171 | PETAYA BERRY | BAIE PITAYE | 18 |
| 172 | APICOT BERRY | BAIE ABRIKO | 19 |
| 179 | BRIGHTPOWDER | POUDRECLAIRE | 22 |
| 180 | WHITE HERB | HERBEBLANCHE | 23 |
| 183 | QUICK CLAW | VIVE GRIFFE | 26 |
| 185 | MENTAL HERB | HERBE MENTAL | 28 |
| 186 | CHOICE BAND | BAND. CHOICE | 29 |
| 187 | KING'S ROCK | ROCHE ROYALE | 30 |
| 188 | SILVERPOWDER | POUDRE ARG. | 31 |
| 196 | FOCUS BAND | BANDEAU | 39 |
| 198 | SCOPE LENS | LENTILSCOPE | 41 |
| 199 | METAL COAT | PEAU METAL | 42 |
| 200 | LEFTOVERS | RESTES | 43 |
| 203 | SOFT SAND | SABLE DOUX | 46 |
| 204 | HARD STONE | PIERRE DURE | 47 |
| 205 | MIRACLE SEED | GRAIN MIRACL | 48 |
| 206 | BLACKGLASSES | LUNET.NOIRES | 49 |
| 207 | BLACK BELT | CEINT.NOIRE | 50 |
| 208 | MAGNET | AIMANT | 51 |
| 209 | MYSTIC WATER | EAU MYSTIQUE | 52 |
| 210 | SHARP BEAK | BEC POINTU | 53 |
| 211 | POISON BARB | PIC VENIN | 54 |
| 212 | NEVERMELTICE | GLACETERNEL | 55 |
| 213 | SPELL TAG | RUNE SORT | 56 |
| 214 | TWISTEDSPOON | CUILLERTORDU | 57 |
| 215 | CHARCOAL | CHARBON | 58 |
| 216 | DRAGON FANG | CROC DRAGON | 59 |
| 217 | SILK SCARF | MOUCH. SOIE | 60 |
| 219 | SHELL BELL | GRELOT COQUE | 62 |
| 220 | SEA INCENSE | ENCENS MER | 52 |
| 221 | LAX INCENSE | ENCENS DOUX | 22 |

Metal Coat and King’s Rock have a non-zero combat effect: their other use in an evolution does not
justify classifying them as objects of evolution alone. Conversely, do not automatically include an
ID simply because it is acceptable in the field of operation.

## Exclusions and limitations

- `0` and `0xFFFF` are not objects to be pulled. Preserve the special marker `0xFFFF` until its
  semantics are established for each context.
- `110` Pepite and `254..258` scarves have a zero holding effect: excluded.
- `181` Macho Bracelet is not a generic combat bonus: excluded from the useful preset.
- `191` Soul Dew, `192` Deep Sea Tooth, `193` Deep Sea Scale and `202` Light Ball are linked to
  specific species: excluded from a circulation without compatibility by species.
- `143..147` taste/nature berries may cause confusion: excluded from the preset without verification
  of nature.

This list is a design selection from observed fields and names. A non-zero effect shows neither that
each object is optimal for each Pokémon, nor the execution of each effect. To promise tactical
compatibility, also filter the type bonuses according to the attacks and the Choice Strip according
to the offensive capabilities. Combat testing remains necessary. No object table is modified by this
search.
