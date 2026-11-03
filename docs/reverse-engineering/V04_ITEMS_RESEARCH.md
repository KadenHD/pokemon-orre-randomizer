# Objets trouvés et boutiques : périmètre PAL v0.4

Recherche du **31 octobre 2026**, en lecture seule sur les originaux. Aucun moteur, option, écran, disque ou profil Dolphin modifié. Les seuls fichiers produits sont cette note et les références sous `analysis/generated/v04-item-references/`.

Les conclusions distinguent les octets observés, les interprétations des outils primaires et les comportements restant à observer. Le périmètre directement exploitable est **la table des objets placés**, puis **six catalogues de boutiques sélectionnés**. Cela ne couvre pas toutes les récompenses des scripts de scénario.

## Identités et preuves conservées

| Source originale | SHA-256 |
|---|---|
| `game/sys/main.dol` | `a788176a45eb88dbd227246a7205ab9856bc79f3cca7e4a0f5376cf466664df5` |
| Membre décompressé `common_rel` | `ee2677af555dc59626f978e743235831a76cb23bae93f3fdd1060d808f749d0b` |
| Membre décompressé `pocket_menu` des cinq langues | `524ad778c3618d0c675e69f6a6bd6fab2e4e929d5a2e6981c1a8c25a555f9f20` |

`analysis/generated/v04-item-references/local-inventory.json` conserve les **397 fiches d'objet**, les **74 placements**, les **14 catalogues**, les cinq identités FSYS/REL et les essais de capacité. SHA-256 : `2ff796026fdd369ddc832065d14641e13358466c24c56fc6d5086338d9e19224`.

`source-manifest.json` conserve les URL, commits, identités Git et SHA-256 locaux de neuf instantanés primaires. Les sources Swift sont figées au commit `f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0` de Pokemon-XD-Code ; les deux sources natives NTSC-U au commit `ad02df4900c623d16d02b9a8ddd9c53ea0cd3db2` de pkmn-colosseum. Ces copies sont des documents de recherche, pas du code intégré au moteur.

## Objets placés : structure localisée sans recherche par motif

[CMRelIndexes.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/CMRelIndexes.swift) nomme les symboles communautaires **60 = TreasureBoxData**, **61 = NumberTreasureBoxes**. Leur résolution par le flux de relocations de l'original PAL donne :

| Élément | Offset dans `common.rel` | Valeur |
|---|---:|---:|
| Début de table, symbole 60 | `0x1EAB74` | — |
| Compteur u32, symbole 61 | `0x219298` | 74 |
| Taille d'enregistrement | — | `0x1C` |
| Fin exclusive | `0x1EB38C` | Exactement le symbole suivant |

La structure est corroborée par [XGTreasure.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/enumerable/XGTreasure.swift) et [TreasureTable.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/struct%20tables/TreasureTable.swift).

| Offset relatif | Encodage | Champ |
|---:|---|---|
| `+0x00` | u8 | Modèle |
| `+0x01` | u8 | Quantité |
| `+0x02` | u16 BE | Angle |
| `+0x04` | u16 BE | Identifiant de salle |
| `+0x06` | u16 BE | Drapeau de réception |
| `+0x08` | u16 BE | Champ inconnu |
| `+0x0A` | u16 BE | Remplissage déclaré par l'outil |
| `+0x0C` | u32 BE | Identifiant d'objet brut |
| `+0x0E` | u16 BE | Partie basse de cet identifiant |
| `+0x10/+0x14/+0x18` | float BE | Coordonnées X/Y/Z |

**Observation PAL : les 74 parties hautes à `+0x0C` sont nulles.** Un patch limité au u16 à `+0x0E` suffit ici. Quantité, modèle, angle, salle, drapeau, autres champs, coordonnées et taille de table doivent rester identiques. Les indices sont préservés : ils peuvent être référencés par les scripts et les sauvegardes.

### Identifiant brut et index d'objet ne sont pas toujours égaux

La table des objets est dans le DOL à `0x3ADDA0`, **397 fiches de `0x28` octets**. Les champs poche `+0`, prix u16 `+6`, nom u32 `+0x10` et description u32 `+0x14` viennent de [CMItem.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/enumerable/CMItem.swift), déjà conservé dans `v03-references/`.

[CMItems.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/enums/CMItems.swift) soustrait **151** aux valeurs brutes vérifiant `397 < raw < 0x250`. Les observations confirment notamment :

- `500 → 349` : Clé de la prison, poche 5 ;
- `537 → 386` : Flûte du Temps, **poche 2 mais prix nul** ;
- `543/544/545 → 392/393/394` : les trois parfums, poche 6.

Il faut normaliser **avant** de filtrer les objets. Préserver les identifiants bruts des entrées protégées : l'inverse `scriptIndex` de l'outil commence à l'index 350, alors que la Clé de la prison observée est 349. Ne pas déduire une conversion inverse universelle à cette frontière.

### Inventaire et protections directement vérifiés

Les 74 placements comprennent **61 identifiants non nuls** et **13 emplacements vides** : indices `0, 62..73`. Les entrées actives se répartissent en 35 objets de poche 2, 16 de poche 5, cinq lots de Balls et cinq CT.

| Protection | Indices des placements |
|---|---|
| Objets clés, poche 5 | `2,3,8,19,26,27,28,29,30,40,41,44,45,46,47,54` |
| Flûtes du Temps, prix nul | `4,61` |
| Lots de Balls | `6,11,36,37,43` |
| Emplacements vides | `0,62..73` |

Les placements 2 et 3 partagent **le drapeau 153 et la Clé de la prison brute 500**. C'est le seul drapeau actif partagé observé ; ne pas traiter ces lignes comme deux récompenses indépendantes.

Avec ces protections, **38 placements** restent candidats, correspondant à 29 ID d'objet distincts. Les cinq CT trouvées sont les objets **314,333,334,335,337**, nommés CT26, CT45, CT46, CT47 et CT49. Aucun objet 93..98 n'est placé dans cette table d'origine ; préserver néanmoins leur disponibilité garantie en boutique lorsque l'option d'évolutions accessibles est active.

Une option conservant les soins peut protéger les **18 placements** dont les noms observés sont les potions, soins totaux, rappels, éthers et élixirs : `1,5,7,9,10,12,13,22,23,25,32,34,38,49,50,51,52,55`. Les ID concernés sont `19..25,34..37`. Cette sélection est une politique de produit à partir des noms et usages, pas une catégorie supplémentaire stockée dans la table des placements.

### Limite : récompenses et réécriture à l'exécution

La table ne contient **aucune Master Ball (ID 1)** : modifier ses lignes ne couvre donc pas une éventuelle remise par scénario. [CMScriptBuiltInFunctions.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/scripts/Colosseum/CMScriptBuiltInFunctions.swift) décrit séparément la fonction standard **119, `playerReceiveItem(item, quantity)`**.

Le [code natif décompilé `floorEventChangeTresure`](https://github.com/dougchansan/pkmn-colosseum/blob/ad02df4900c623d16d02b9a8ddd9c53ea0cd3db2/src/game/floor_event_exact_80115CB4.c) réécrit aussi le mot d'objet et la quantité d'une ligne à l'exécution. Ces sources montrent des mécanismes distincts ; les appelants PAL et les constantes CMS correspondantes n'ont pas été inventoriés ici. La portée honnête est « objets placés de la table », sans annoncer toutes les récompenses de PNJ ou de tournois.

Pour élargir ce périmètre, demander une preuve typée : archive et membre CMS/REL, identité du binaire, instruction ou appel standard décodé, argument d'objet et quantité, puis observation ou trace de l'attribution. Une occurrence hexadécimale isolée d'un ID n'est pas une preuve d'attribution.

## Boutiques : cinq archives, une même table

Toutes les variantes comportent **12 membres**. Le membre **0**, nommé `pocket_menu`, a l'identifiant FSYS `0x03711C00` ; son REL est **module 2, version 3, imports `[2,0]`**, taille **1 672 octets**, SHA-256 identique dans les cinq langues. Les onze autres membres doivent être préservés après décompression.

| Fichier dans `game/files/` | Groupe FSYS |
|---|---:|
| `pocket_menu.fsys` | 20 |
| `pocket_menu_fr.fsys` | 2021 |
| `pocket_menu_ge.fsys` | 2020 |
| `pocket_menu_it.fsys` | 2022 |
| `pocket_menu_sp.fsys` | 2023 |

Les symboles de poche **2/3** fournissent la liste d'objets et son compteur ; **4/5** les descripteurs et leur compteur, selon [CMRelIndexes.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/CMRelIndexes.swift).

- Liste physique : **122 u16 BE à `0x2AC`**, fin `0x3A0` ; zéro termine chaque stock.
- Descripteurs : **14 × 4 octets à `0x3A0`**, fin `0x3D8` ; structure `u8 type, u8 subtype, u16 start_index`.
- Seuls la liste et les indices de début nécessitent une écriture ; compteurs, en-têtes, sections, imports et relocations restent inchangés.

### Types : ne pas confondre dialogue et opération

[XGPokemart.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/enumerable/XGPokemart.swift) nomme les types de dialogue `0 pokemart, 1 vendingMachine, 2 shop, 3 herbShop`. Les sous-types sont `0 shop, 1 vendingMachine, 2 bonusDiscCoupons, 3 brokenCoupons, 4 pokeCoupons`.

**Ces champs seuls ne codent pas explicitement « achat » ou « vente ».** Les listes 0..2 sont donc désignées ci-dessous par leurs valeurs brutes ; leur exclusion du nouveau tirage reste une règle de périmètre. Les achats des menus 3 et 5 ont fait l'objet d'essais précédents, consignés dans `RANDOMIZER_V3.md`.

### Inventaire exact des 14 descripteurs originaux

| Index | Type/sous-type | Début | Stock brut, dans l'ordre |
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
| 12 | 1/3 | 103 | Même liste que 11 |
| 13 | 0/4 | 103 | Même liste que 11 |

Le périmètre de tirage envisagé est **3,4,5,6,7,9**. Préserver 0..2, l'herboriste 8, le distributeur 10 et les catalogues à coupons 11..13 à l'état reçu par la nouvelle passe. Protéger en particulier les parfums bruts **543..545** de poche 6, même si leur prix est positif. Les trois catalogues à coupons partagent physiquement le début 103 : une substitution aveugle dans la liste physique modifierait tous leurs alias.

### Allocation : mesures et stratégie sans agrandissement

Une bijection globale, appliquée aux mêmes ID éligibles dans tous les menus ciblés, conserve le partage de suffixe entre 7 et 9. Réassembler ensuite les **14 listes logiques** ; les indices peuvent changer, tandis que les ID, l'ordre et les types des menus non ciblés restent identiques à l'état d'entrée de la passe.

Mesures avec le packer actuel, en remplaçant globalement 34 ID ciblés par des ID artificiels distincts `1000+n`, absents des menus protégés. Ces ID sont uniquement une **sonde de capacité**, jamais un pool d'objets à injecter dans le jeu.

| État d'entrée | Packing avant mapping | Après bijection disjointe | Capacité |
|---|---:|---:|---:|
| REL original, sans pierres | 106 | **112** | 122 |
| REL courant après `patch_rel(stones)` | 109 | **109** | 122 |

Les variantes réelles et la classification des objets doivent toujours être vérifiées avant publication. Cette mesure ne remplace pas le contrôle final `used <= 122` pour chaque option et seed.

Si un futur contrat exige aussi les listes 0..2 dans leur ordre **strictement original** : ajouter les pierres en fin des deux menus 3/5 prend 124 entrées et dépasse l'allocation. **Préfixer** les pierres au menu 5, et les préfixer ou suffixer au 3, restaure le suffixe partagé de la liste 0 et tient en **118 entrées**, sans réordonner aucun stock original. Aucun agrandissement ou déplacement de section REL n'est nécessaire pour cette variante.

## Contrôles à appliquer lors de l'intégration

- Vérifier les empreintes originales et les bornes des symboles avant toute modification.
- Objets placés : whitelist des seuls u16 d'objet sélectionnés ; protéger les 13 vides, 16 clés, deux Flûtes du Temps et cinq lots de Balls. Quantités et drapeaux restent identiques.
- Boutiques : prix et poches sont évalués après normalisation de l'ID ; préserver Balls, pierres garanties, clés, parfums et objets à prix nul selon le contrat retenu.
- Tous les menus non ciblés conservent leurs listes logiques, types et devises ; les trois catalogues à coupons restent identiques entre eux.
- Les cinq REL de boutique reconstruits sont identiques ; les onze autres membres de chaque archive restent identiques après décompression.
- Vérifier dans l'ISO finale les charges utiles et les plages FST/DOL réellement écrites, puis observer au moins un catalogue et un ramassage. La présente recherche n'exécute aucun scénario de jeu.
