# Références de formats et structures Colosseum

Consultées le 30 octobre 2026. Étude statique : aucune exécution du jeu, aucune modification de `game/`. Les schémas communautaires servent à formuler et vérifier des hypothèses sur ce dump ; ils ne remplacent pas sa validation.

## Identité observée localement

Lecture directe des en-têtes : `game/sys/boot.bin` contient `GC6P01`, révision 0. `main.dol` contient le point d'entrée `0x80003154` et son SHA-256 est `a788176a45eb88dbd227246a7205ab9856bc79f3cca7e4a0f5376cf466664df5`.

`common.fsys` porte la signature FSYS, 28 membres et une taille déclarée égale à sa taille réelle, 944 672 octets. Le premier en-tête de membre est à `0x290`, son contenu à `0xB60`, avec signature LZSS, taille stockée 813 413 octets et taille décompressée déclarée 2 210 420 octets. Ces valeurs sont des observations locales ; la sémantique des tables internes demande une analyse supplémentaire.

## DOL et REL

Le lecteur officiel Dolphin déclare 7 sections de code, 11 sections de données, leurs offsets, adresses et tailles, puis BSS et point d'entrée. Le fichier ne contient pas les noms originaux de fonctions. Source : [Dolphin DolReader.h](https://github.com/dolphin-emu/dolphin/blob/master/Source/Core/Core/Boot/DolReader.h), licence indiquée `GPL-2.0-or-later`.

Le parseur de decomp-toolkit décrit les sections et commandes de relocation REL : `201` accumule un déplacement, `202` change la section courante et remet sa position à zéro, `203` termine la liste. Les imports nomment le module cible ; le module zéro désigne le DOL. Une adresse REL requiert donc une section, une base et une relocation, et ne doit pas être traitée comme une adresse RAM fixe. Source : [decomp-toolkit rel.rs](https://github.com/encounter/decomp-toolkit/blob/main/src/util/rel.rs), projet Apache-2.0 ; version exacte non figée ici.

## FSYS et LZSS

Le code de StarsMmd expose les champs suivants : FSYS `+0x08` groupe, `+0x0C` nombre de membres, `+0x20` taille, `+0x40` pointeur vers la liste des en-têtes. Dans chaque en-tête de membre : `+0x00` identifiant, `+0x04` position des données, `+0x08` taille décompressée, `+0x14` taille stockée, `+0x1C` nom complet éventuel, `+0x24` nom court. Le préfixe LZSS mesure `0x10` octets, avec tailles à `+4` et `+8`. Source primaire figée : [XGFsys.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/file%20formats/XGFsys.swift).

LZSS utilise une fenêtre circulaire de 4096 octets remplie de zéros, position d'écriture initiale `0xFEE`. Les bits du drapeau sont consommés du moins significatif au plus significatif : 1 signifie littéral, 0 référence. Pour deux octets `a,b`, position de référence = `a | ((b >> 4) << 8)` et longueur = `(b & 15) + 3`. La copie peut se chevaucher. Source : [XGLZSS.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/file%20formats/XGLZSS.swift), qui attribue son port à QuickBMS/Luigi Auriemma.

Le dépôt Pokemon-XD-Code indique une licence GPL-2.0. Aucun code tiers n'a été copié dans le projet par cette recherche.

## Index des symboles de common_rel

Dans l'outil historique, les symboles sont numérotés par première occurrence d'une cible distincte dans les commandes de relocation de types 1 à 13, à partir de l'offset `u32@0x24`, jusqu'à la première commande 203. Cible = offset du début de section + addend. Il s'agit d'une convention de l'outil, pas d'un index explicitement stocké. Source : [XGRelocationTable.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/file%20formats/XGRelocationTable.swift).

| Table candidate | Index du symbole | Index du compteur |
| --- | ---: | ---: |
| Dresseurs | 44 | 45 |
| Pokémon des dresseurs | 48 | 49 |
| Capacités | 62 | 63 |
| Statistiques des espèces | 68 | 69 |
| Pokémon obscurs | 80 | 81 |

`CMRelIndexes.swift` annonce des index US et adapte explicitement EU : script 98, première table de textes 99. Les autres correspondances ci-dessus restent à corroborer sur les données PAL. Source : [CMRelIndexes.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/CMRelIndexes.swift).

## Textes français : observation PAL

Le lecteur communautaire indique un compteur u16 à `+4`, un en-tête de `0x10` octets puis des entrées de 8 octets : ID u32 masqué par `0xFFFFF`, offset u32 relatif au début de la table. Les caractères sont des unités u16 big-endian terminées par `0000`. Le marqueur `FFFF` introduit un code spécial u8 suivi d'un nombre variable d'octets ; un décodeur UTF-16 seul convient aux noms simples mais pas à l'ensemble des dialogues. Source : [XGStringTable.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/file%20formats/XGStringTable.swift).

Sur le membre décompressé local `analysis/generated/extracted/common/000.bin`, le nom de l'espèce interne 1 référence l'ID 1001. La lecture des cinq tables donne :

| Index du symbole | Offset dans common_rel | Entrées | ID 1001 observé | Nom de capacité 1 observé | Langue identifiée |
| --- | --- | ---: | --- | --- | --- |
| 99 | `0x5A448` | 2018 | BULBASAUR | POUND | Anglais |
| 100 | `0x6698C` | 2018 | BISASAM | PFUND | Allemand |
| 101 | `0x732B0` | 2018 | BULBIZARRE | ECRAS'FACE | Français |
| 102 | `0x7FE8C` | 2018 | BULBASAUR | BOTTA | Italien |
| 103 | `0x8CB98` | 2018 | BULBASAUR | DESTRUCTOR | Espagnol |

L'identification de la table française au symbole 101 repose donc sur son contenu local, et non sur la convention US où 101 désigne le script. Les noms des capacités 1 et 15 distinguent les tables dont le nom de Bulbizarre est identique ; les formes observées pour la capacité 15 sont respectivement CUT, ZERSCHNEIDER, COUPE, TAGLIO et CORTE.

## Schémas candidats pour le randomizer

Les offsets ci-dessous sont relatifs à un enregistrement, les entiers multioctets sont big-endian. Ils proviennent des sources ; cette page ne prétend pas que tous les champs ont été validés localement.

Espèce, taille `0x11C` : numéro national u16 `+0x10`, identifiant de texte u32 `+0x18`, types u8 `+0x30/+0x31`, talents u8 `+0x32/+0x33`, objets tenus u16 `+0x70/+0x72`, statistiques PV/Att/Déf/AttSpé/DéfSpé/Vitesse u8 aux offsets `0x85/87/89/8B/8D/8F`. Évolutions à `+0x9C`, capacités par niveau à `+0xBA`. Source : [CMPokemonStats.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/enumerable/CMPokemonStats.swift).

Une évolution mesure 6 octets : méthode u8 `+0`, condition u16 `+2`, espèce cible u16 `+4`, cinq entrées. Une capacité par niveau mesure 4 octets : niveau u8 `+0`, capacité u16 `+2`, dix-neuf entrées. Sources : [XGEvolution.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/XGEvolution.swift) et [XGLevelUpMove.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/XGLevelUpMove.swift).

Dresseur, taille `0x34` : classe u8 `+3`, premier index Pokémon u16 `+4`, IA u16 `+6`, texte du nom u32 `+8`, modèle u8 `+0x13`, objets u16 depuis `+0x14`. L'outil lit six emplacements Pokémon consécutifs. Source : [CMTrainer.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/enumerable/CMTrainer.swift).

Pokémon de dresseur, taille `0x50` : talent/genre/nature/ID obscur u8 `+0/+1/+2/+3`, niveau u8 `+4`, espèce u16 `+0xA`, objet u16 `+0x12`, nom u32 `+0x14`, capacités u16 `+0x36/+0x3E/+0x46/+0x4E`. Entrée obscur séparée, taille `0x38` : capture u8 `+0`, espèce u16 `+2`, premier dresseur u16 `+4`, dresseur alternatif u16 `+6`, jauge u16 `+8`, ID u8 `+0xB`. Modifier une espèce obscure implique de vérifier la cohérence entre ces tables. Source : [CMTrainerPokemon.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/enumerable/CMTrainerPokemon.swift).

Capacité, taille `0x38` : PP u8 `+1`, type u8 `+2`, précision u8 `+4`, puissance u8 `+0x17`, effet u16 `+0x1A`, nom u32 `+0x20`. Le champ catégorie à `+0x1F` est décrit comme un ajout par hack pour Colosseum : ne pas le présenter comme une mécanique vanilla démontrée. Source : [XGMove.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/enumerable/XGMove.swift).

## Symboles PAL et outils actuels

La carte [GC6P01.map](https://github.com/StarsMmd/Colo-XD-PBR-symbol-maps/blob/93d5da920e7f03b8854b79963d94739ec66abd1d/GC6P01.map) contient des candidats de frontières et noms communautaires. Exemples RAM : `__start 0x80003154`, `memcpy 0x800054F4`, `zz_set_current_language 0x800056C8`, `zz_get_current_language 0x800056D0`, `DVDReadAsyncPrio 0x800A8968`. Le README explique la provenance par comparaison et signale que les anciens fichiers `annotated` sont obsolètes. Les noms ne sont pas des symboles originaux prouvés pour ce dump. Aucune licence explicite vérifiée pour ces cartes.

[GoD-Tool](https://github.com/StarsMmd/GoD-Tool) décrit son successeur GODDESS et son support FSYS/LZSS, DOL et reconstruction de disque. Sa page distingue aussi des opérations REL présentes mais désactivées. Le simple nom d'une commande ne prouve donc pas sa disponibilité. Licence affichée GPL-3.0 ; aucun outil installé ou exécuté ici.

## Limites et suites

Les références NTSC-U, dont les projets de décompilation Colosseum GC6E01, ne fixent pas les offsets PAL. Avant écriture : vérifier compteurs, limites de sections, identités d'espèces/capacités, références croisées et cohérence des entrées obscures. Les noms romaji des archives et leur présence ne prouvent ni l'usage à l'exécution ni la complétude d'une mécanique. Une reconstruction puis un test sous Dolphin restent nécessaires pour valider un futur patch.
