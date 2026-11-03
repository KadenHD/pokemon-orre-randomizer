# Analyse de Pokémon Colosseum PAL

Analyse du 30 octobre 2026, sur les fichiers fournis localement. **Les conteneurs et les principales tables de gameplay sont maintenant lisibles et exportables.** Cela fournit une base vérifiée pour développer un randomizer. Le code complet du jeu n'a pas été décompilé et aucun patch n'a été testé en jeu.

Mise à jour : une reconstruction sans changement des données et un essai réel sous Dolphin ont depuis été réalisés. Leur méthode, résultats et captures figurent dans [ROUNDTRIP.md](ROUNDTRIP.md). Les mentions « non vérifié » ci-dessous décrivent l'état à l'issue de cette première cartographie.

## Identité et intégrité

Le disque déclare `GC6P01`, titre `Pokemon Colosseum`, révision 0. Son exécutable DOL PowerPC est reconnu par REA avec un point d'entrée RAM `0x80003154`.

| Artefact | Taille | SHA-256 |
|---|---:|---|
| ISO locale | 1 459 978 240 | `1e3b4aa806ac3367cca13496f7701137e9437e7bac0101f75b9b137633a10aa9` |
| `game/sys/main.dol` | 4 096 576 | `a788176a45eb88dbd227246a7205ab9856bc79f3cca7e4a0f5376cf466664df5` |
| `common_rel`, décompressé | 2 210 420 | `ee2677af555dc59626f978e743235831a76cb23bae93f3fdd1060d808f749d0b` |

Les 2 006 fichiers de la FST et les cinq fichiers système ont été comparés octet par octet aux plages correspondantes de l'ISO : **2 011 correspondances, 712 453 188 octets contrôlés, aucune divergence**. Ce résultat établit l'égalité avec cette ISO locale ; il ne certifie pas une origine externe. Preuve : `ASSET-002`, détaillée dans [assets.md](assets.md).

## Organisation reconstruite

```text
ISO / game/
  sys/main.dol       programme principal PowerPC, sections mappées en RAM
  sys/fst.bin        chemins, positions disque et tailles des fichiers
  files/*.fsys       1 981 archives, 6 863 membres
    common.fsys     28 membres dont common_rel
      common_rel    module REL v3, id 125, code + données + relocations
        tables      espèces, capacités, dresseurs, équipes, obscurs
        textes      15 tables repérées, cinq langues
  files/movie/      cinq vidéos à signature THP
  files/sound/      sept fichiers .samp, contenu non décodé
```

Les **6 683 membres LZSS et 180 membres sans compression** ont leurs limites et tailles contrôlées. Les en-têtes FSYS/LZSS sont cohérents dans les 1 981 archives. Les 28 membres de `common.fsys` ont été effectivement décompressés, avec consommation exacte de chaque flux et contrôle de sa taille de sortie. Les autres flux LZSS n'ont pas été intégralement décompressés.

Le DOL comporte deux sections de code et six sections de données non vides. Les coordonnées RAM du DOL sont distinctes des offsets dans le fichier. Le REL est chargé et relogé séparément : les offsets des tables ci-dessous ne sont **pas** des adresses RAM.

## Tables identifiées et contrôlées

Offsets dans le membre `common_rel` **décompressé**, exclusivement pour le SHA-256 ci-dessus. Chaque emplacement a été obtenu à partir des relocations du module et de la convention d'index documentée par l'outil communautaire, puis contrôlé localement. Le parseur ne cherche pas ces tables par un offset PAL codé en dur.

| Table | Offset fichier | Enregistrements | Taille par entrée | Export local |
|---|---:|---:|---:|---|
| Dresseurs | `0x15DEEC` | 820 | `0x34` | `tables/trainers.json` |
| Pokémon des dresseurs | `0x16AE44` | 5 510 | `0x50` | `tables/trainer_pokemon.json` |
| Capacités | `0x1EB38C` | 358 | `0x38` | `tables/moves.json` |
| Espèces | `0x1F05CC` | 413 | `0x11C` | `tables/species.json` |
| Pokémon obscurs | `0x2125A0` | 97 | `0x38` | `tables/shadow.json` |

Les exports se trouvent sous `analysis/generated/`. Les compteurs proviennent de mots du REL, et les tailles restent dans leur section. Les références d'espèces, de capacités, d'évolutions, de capacités par niveau, d'équipes et de dresseurs sont dans les limites attendues. Les 108 enregistrements de Pokémon de dresseur portant un ID obscur concordent tous avec l'espèce de l'entrée obscure associée. Ces contrôles sont structurels ; ils n'établissent pas que chaque ligne est utilisée dans une partie.

La table des espèces contient **386 numéros nationaux distincts entre 1 et 386**, sans doublon, ainsi que 27 entrées dont le numéro national est nul. Les noms simples sont décodés pour ces 386 espèces. Il y a **48 entrées obscures avec une espèce non nulle** ; le compteur brut 97 ne doit donc pas être présenté comme 97 captures disponibles.

Trente enregistrements de Pokémon de dresseur contiennent `0xFFFF` dans au moins un champ de capacité. Cette valeur est conservée comme marqueur brut, séparément des indices ordinaires. Sa signification à l'exécution reste inconnue ; elle ne doit pas être remplacée automatiquement par un numéro de capacité.

### Identifiants internes et français

La table française principale est au symbole communautaire 101, offset **`0x732B0`**, et contient 2 018 entrées. L'en-tête porte les octets `FR`. Les tables voisines portent `UK`, `GE`, `IT`, `SP`. Les noms simples sont lus en UTF-16 big-endian ; les dialogues et textes contenant des codes de contrôle ne sont pas interprétés comme de simples chaînes.

Exemples effectivement décodés :

| Index espèce interne | Numéro national | Nom français | PV / Att / Déf / AttSpé / DéfSpé / Vit |
|---:|---:|---|---|
| 1 | 1 | BULBIZARRE | 45 / 49 / 49 / 65 / 65 / 45 |
| 25 | 25 | PIKACHU | 35 / 55 / 30 / 50 / 40 / 90 |
| 196 | 196 | MENTALI | 65 / 65 / 60 / 130 / 95 / 110 |
| 197 | 197 | NOCTALI | 95 / 65 / 110 / 60 / 130 / 65 |
| 277 | 252 | ARCKO | 40 / 45 / 35 / 65 / 55 / 70 |

**Un numéro du Pokédex ne doit pas être utilisé directement comme index interne.** Par exemple l'index interne 252 est une entrée vide, tandis qu'Arcko, numéro national 252, est à l'index interne 277. Le futur randomizer devra construire sa liste d'espèces admissibles depuis les enregistrements vérifiés.

## Registre des preuves

Les identifiants `LOCAL-*` et `ASSET-*` sont des références de ce projet, pas des Evidence IDs attribués par REA.

| Référence | Nature et périmètre | Résultat / limite |
|---|---|---|
| `ASSET-001/002` | En-têtes + FST + comparaison de toutes les plages ISO | Identité et extraction concordantes |
| `LOCAL-STRUCTURE-001` | Tous les fichiers extraits, SHA-256, parseurs DOL/FSYS/REL | Inventaire complet de ce périmètre ; décompression limitée à common |
| `LOCAL-TABLES-001` | `common_rel` exact, schémas primaires + bornes + références + textes | Cinq tables exportées ; sémantique corroborée statiquement |
| `LOCAL-REA-001` | `open_binary(format=gamecube-dol)`, puis `binary_overview` | Identité reconnue ; analyse profonde indisponible |

Fichiers de preuve locaux : `analysis/generated/manifest.json`, `fsys.json`, `dol.json`, `common-rel.json`, `rel-symbols.json`, `summary.json`, `tables-summary.json`, `assets-survey.json`, `rea-run.json`. Un résumé durable des résultats est conservé dans [baseline.json](baseline.json). Les sources primaires, leurs versions et les limites de leur interprétation sont dans [community-formats.md](community-formats.md).

REA 6.8.0 est connecté. Son appel d'inventaire profond a retourné `capability_unavailable` : Ghidra n'est pas configuré et le fournisseur REA Ghidra sous Windows n'admet pas le format GameCube DOL. Hopper est indisponible sur Windows ; IDA et Kuna ne sont pas configurés et leurs routes REA n'admettent pas ce DOL. Installer Ghidra seul sous Windows ne suffirait donc pas à débloquer cette route. Aucun outil ni réglage MCP n'a été installé ou modifié. L'export de ledger REA contient zéro Evidence record ; l'identité et l'erreur de cette session sont conservées séparément dans `rea-run.json`. La session native a été fermée.

## Validation et état de l'investigation

Douze tests sur des petites fixtures indépendantes passent : LZSS avec références chevauchantes, fenêtre initiale nulle et bouclage, troncatures et dépassements ; limites FSYS ; sections/entrée DOL ; imports et callbacks REL ; noms et codes de contrôle. Les scripts ont aussi été exécutés sur le dump complet. Cela vérifie les lecteurs et la cohérence des données, sans remplacer un test du jeu.

| Question initiale | État |
|---|---|
| Quelle version et l'extraction correspond-elle à l'ISO ? | Répondu |
| Comment sont organisés les conteneurs et leur compression ? | Répondu pour l'inventaire ; décompression complète de common |
| Où sont les principales données pour un randomizer ? | Répondu pour les cinq tables ci-dessus, évolutions et capacités par niveau incluses |
| Peut-on relier indices et noms français ? | Répondu pour les noms simples exportés |
| Quelles fonctions du code exécutent les mécaniques ? | Partiel : chargement DOL/REL cartographié, corps de fonctions non décompilés |
| Un jeu modifié peut-il être reconstruit et joué ? | Non vérifié : aucun patch ni reconstruction effectué |

La suite technique consiste à construire un patch déterministe sur une copie, maintenir les références entre équipes et obscurs, préserver les entrées réservées, réencoder les FSYS puis reconstruire un disque. Les starters et scripts de scénario, les contraintes de progression et le comportement réel sous Dolphin devront être vérifiés séparément. Une analyse du code pourra utiliser un environnement Ghidra/POSIX compatible avec la route DOL de REA ou un outil PowerPC adapté, en conservant ces identités de fichiers.
