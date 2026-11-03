# Ressources et intégrité de l'extraction

Analyse statique du 30 octobre 2026. Le script `scripts/survey_assets.py` lit les fichiers sans les modifier et sans lancer le jeu. Les identifiants `ASSET-*` ci-dessous désignent des constats locaux reproductibles, pas des Evidence REA.

## Résultat vérifié

**Les 2 011 fichiers de `game/` sont identiques octet par octet aux plages correspondantes de l'ISO locale fournie.** Le contrôle porte sur 712 453 188 octets : les 2 006 fichiers du système de fichiers du disque et les cinq fichiers de `sys/`. Il ne compare pas les zones inutilisées du disque avec un autre exemplaire et n'établit aucune authenticité externe de l'ISO.

Commande de reproduction depuis la racine du projet :

```powershell
python scripts/survey_assets.py --game game --iso 'Pokemon Colosseum (Europe) (En,Fr,De,Es,It).iso'
```

Le résultat JSON doit contenir `all_ranges_byte_identical: true`, aucune entrée dans `mismatches`, et les identités suivantes pour reproduire cette analyse.

| Source | SHA-256 |
|---|---|
| ISO locale, 1 459 978 240 octets | `1e3b4aa806ac3367cca13496f7701137e9437e7bac0101f75b9b137633a10aa9` |
| `game/sys/boot.bin` | `466709a5575548e3f6abe74d21f89e2fa9e4ed119df75b91bc49fc546116e192` |
| `game/sys/fst.bin` | `6da386f1db41c37489bf7fb959a2c7009ea87edf7c9606d19c1f1fb9e8e418be` |
| `game/files/opening.bnr` | `e673c2fae370f3586f367f1d9b38a5719b06fef152ddb1c43cb9019fa8d2f1b4` |

## Observations

### ASSET-001 — Identité du disque

Dans `sys/boot.bin`, les six octets à `0x00` sont `47 43 36 50 30 31`, soit **`GC6P01`**. Le numéro de disque à `0x06` et la révision à `0x07` valent zéro. Le titre ASCII à `0x20` est `Pokemon Colosseum`. La signature à `0x1C` est `C2 33 9F 3D`.

Les mots big-endian de l'en-tête donnent :

| Position dans `boot.bin` | Valeur | Interprétation utilisée par le contrôle |
|---|---:|---|
| `0x420` | 125 952 (`0x1EC00`) | Position du DOL dans l'ISO |
| `0x424` | 4 222 720 (`0x406F00`) | Position de la FST dans l'ISO |
| `0x428` | 69 251 | Taille de la FST |

Le mot à `0x18` dans `bi2.bin` vaut `2`. L'identifiant contenant `P`, les variantes de ressources et le nom de l'ISO concordent avec une édition européenne ; cette qualification est une interprétation de ces champs, distincte de leurs valeurs observées.

### ASSET-002 — Exhaustivité et contenu de l'extraction

La FST contient 2 009 entrées de 12 octets : une racine, deux répertoires (`movie`, entrée 202 ; `sound`, entrée 791) et 2 006 fichiers. La table de noms commence à `0x5E2C` (24 108 octets). Tous les chemins attendus sont présents dans `game/files/`, sans fichier supplémentaire et avec les tailles attendues.

Le contrôle indépendant lit directement l'en-tête et la FST de l'ISO, puis compare chaque fichier avec sa plage, par blocs d'au plus 1 Mio. Les cinq fichiers de `sys/` sont également comparés : `boot.bin` à `0`, `bi2.bin` à `0x440`, `apploader.img` à `0x2440`, puis `main.dol` et `fst.bin` aux positions de l'en-tête. Les tailles attendues sont calculées depuis l'ISO : tailles fixes pour boot et bi2, champs de taille de l'apploader, dernière fin de section pour le DOL et champ de taille FST. Elles ne sont pas reprises depuis les fichiers extraits. Résultat : **2 011 correspondances exactes, zéro divergence**. La sortie complète est conservée dans `analysis/generated/assets-survey.json`.

Une vérification sur une petite ISO synthétique confirme la détection d'un octet de payload modifié et de fichiers DOL, apploader ou FST tronqués.

La première plage de fichier de la FST commence à l'octet 751 816 640 ; la dernière se termine à 1 459 978 240. Ce décalage important est une propriété des positions du disque ; les fichiers extraits représentent environ 712 Mo, contre 1,46 Go pour l'image disque.

### ASSET-003 — Répartition des fichiers

| Répertoire | Fichiers | Octets |
|---|---:|---:|
| `game/files/`, directement | 1 994 | 415 723 917 |
| `game/files/movie/` | 5 | 283 026 032 |
| `game/files/sound/` | 7 | 9 411 648 |
| `game/sys/` | 5 | 4 291 591 |
| **Total** | **2 011** | **712 453 188** |

Les extensions observées sont : 1 981 `.fsys`, 14 `.bin`, 7 `.samp`, 5 `.thp`, puis un `.bnr`, un `.dol`, un `.img` et un `.toc`.

Les 1 981 `.fsys` commencent tous par les quatre octets ASCII **`FSYS`**. Par convention de nom, 1 185 ont le préfixe `wzx_` et 527 le préfixe `pkx_`. Les 269 autres couvrent notamment les familles `D1_`, `D2_`, `D4_`, `M1_` à `M4_`, `S1_`, `S2_`, les menus et des archives comme `common.fsys`, `people_archive.fsys`, `prog.fsys` ou `world_map.fsys`. Ces noms orientent les recherches mais ne démontrent pas à eux seuls le rôle du contenu.

Exemples de ressources importantes par taille : `people_archive.fsys` contient 18 069 472 octets, `chara_big.fsys` 5 802 944 et `poke_face.fsys` 4 824 000. Aucun de ces conteneurs n'est décompressé par ce script ; l'analyse FSYS détaillée est menée séparément.

### ASSET-004 — Variantes de langue

La recherche bornée aux suffixes de nom `_fr`, `_ge`, `_it`, `_sp` identifie **13 groupes complets**, chacun accompagné d'une archive sans suffixe : `cb_menu`, `field_common`, `fight_common`, `pcbox_menu`, `pcbox_pocket_menu`, `pcbox_poke_box`, `pda_menu`, `pocket_menu`, `pokechg_menu`, `title`, `toolbattle_menu`, `topmenu`, `waza_menu`.

Cela représente 65 archives sur cette convention de nom. Il existe aussi d'autres noms évoquant des langues, notamment dans la famille `wzx_` ; le nombre 65 n'est donc pas un inventaire exhaustif de tous les contenus localisés. La présence d'une variante ne démontre pas que tous ses textes ont été traduits ni qu'un écran donné la charge à l'exécution.

`opening.bnr` commence par `BNR2` et mesure 8 096 octets. Ses six enregistrements de texte de 320 octets, aux positions `0x1820`, `0x1960`, `0x1AA0`, `0x1BE0`, `0x1D20`, `0x1E60`, sont strictement identiques. Le bandeau du disque n'apporte donc pas ici six traductions distinctes.

### ASSET-005 — Vidéos

Les cinq fichiers vidéo commencent par `54 48 50 00` (`THP\0`) et portent le mot de version `0x00011000`. Le flottant big-endian à `0x10` vaut environ 29,97 ; le mot à `0x14` donne les nombres d'images ci-dessous.

| Fichier dans `files/movie/` | Octets | Images déclarées |
|---|---:|---:|
| `autodemo01.thp` | 101 534 896 | 2 700 |
| `gs_logo.thp` | 2 375 888 | 130 |
| `openingdemo.thp` | 64 046 624 | 1 926 |
| `staffroll.thp` | 113 114 768 | 5 250 |
| `tpc.thp` | 1 953 856 | 75 |

Ce sont des valeurs d'en-tête ; aucun décodage ni visionnage ne vérifie la durée effective ou le contenu audiovisuel.

## Portée et suite utile

L'intégrité de l'extraction par rapport à l'ISO locale est établie. Les ressources sont accessibles pour les analyses FSYS, REL et DOL. Les rôles exacts des familles `pkx_` et `wzx_`, les tables de gameplay, le chargement des variantes de langue et les liens entre scripts de scènes et données restent à démontrer par analyse du contenu ou observation du jeu.
