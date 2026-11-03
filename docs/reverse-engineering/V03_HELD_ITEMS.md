# Objets tenus : liste de combat PAL vérifiée

Analyse statique du 31 octobre 2026, sans écriture dans le jeu ni exécution Dolphin.
Les ID et noms ci-dessous ont été lus dans les données originales, sans reprendre
de mémoire une numérotation d'une autre version.

## Provenance et vérification

- DOL PAL : SHA-256 `a788176a45eb88dbd227246a7205ab9856bc79f3cca7e4a0f5376cf466664df5`.
- `common.rel` : SHA-256 `ee2677af555dc59626f978e743235831a76cb23bae93f3fdd1060d808f749d0b`.
- Schéma primaire épinglé : [CMItem.swift, commit f2d6c4a](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/enumerable/CMItem.swift).
  La table PAL est dans le DOL à `0x3ADDA0`, avec un pas de `0x28` et 397 entrées.
  Champs utilisés : poche `+0x00`, indicateur empêchant de tenir `+0x01`, effet
  d'objet tenu `+0x0B`, ID du nom `+0x10`, paramètre `+0x1B`.
- Résolution des noms corroborée par [CMItems.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/enums/CMItems.swift) : l'ID lu dans le DOL référence les textes de `common.rel`.
- Les ID candidats proviennent seulement d'emplacements peuplés effectivement
  référencés par les équipes d'origine. Chaque objet retenu a un nom UK/FR valide,
  un effet de tenue non nul, un indicateur de tenue à zéro et une poche 2 ou 3.
- Détail local reproductible : `analysis/generated/v03-references/held-items-local.json`.

## Liste recommandée pour des objets de combat génériques

44 ID :

```python
(133, 134, 135, 136, 137, 138, 139, 140, 141, 142,
 168, 169, 170, 171, 172, 179, 180, 183, 185, 186, 187, 188,
 196, 198, 199, 200, 203, 204, 205, 206, 207, 208, 209, 210,
 211, 212, 213, 214, 215, 216, 217, 219, 220, 221)
```

| ID | Nom UK observé | Nom FR observé | Effet brut |
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
| 186 | CHOICE BAND | BAND. CHOIX | 29 |
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

Peau Métal et Roche Royale ont un effet de combat non nul : leur autre usage
dans une évolution ne justifie pas de les classer comme objets d'évolution seuls.
À l'inverse, ne pas inclure automatiquement un ID simplement parce qu'il est
acceptable dans le champ de tenue.

## Exclusions et limites

- `0` et `0xFFFF` ne sont pas des objets à tirer ; préserver le marqueur spécial
  `0xFFFF` tant que sa sémantique n'est pas établie pour chaque contexte.
- `110` Pépite et `254..258` foulards ont un effet de tenue nul : exclus.
- `181` Bracelet Macho n'est pas un bonus de combat générique : exclu du preset utile.
- `191` Rosée Âme, `192` Dent Océan, `193` Écailleocéan et `202` Ballelumière sont
  liés à des espèces précises : exclus d'un tirage sans compatibilité par espèce.
- `143..147` baies à goût/nature peuvent apporter de la confusion : exclues du
  preset sans vérification de nature.

Cette liste est une sélection de conception à partir de champs et noms observés.
Un effet non nul ne démontre ni que chaque objet est optimal pour chaque Pokémon,
ni l'exécution de chaque effet. Pour promettre une compatibilité tactique, filtrer
aussi les bonus de type selon les attaques et le Bandeau Choix selon les capacités
offensives. Les essais de combat restent nécessaires ; aucune table d'objet n'est
modifiée par cette recherche.
