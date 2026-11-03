# Reconstruction sans changement des données et test Dolphin

Le 30 octobre 2026, une ISO séparée a été reconstruite et testée avec **Dolphin 2609a, JIT64 SC, Direct3D 12 et DSP HLE**. Les données du jeu sont conservées : les 28 membres de `common.fsys` ont été réellement recompressés et vérifiés après décompression ; tous les autres fichiers sont identiques octet par octet. Le démarrage, le chargement d'une sauvegarde copiée, le déplacement et un tour de combat interactif ont été observés.

## Résultat disponible

- ISO : `build/roundtrip/colosseum-pal-roundtrip.iso`
- Taille : **1 459 978 240 octets**, comme l'image source.
- SHA-256 : `3b4edc03c00f56f029d8cf47b9acbfda32f5f329a9cc9e7d3f8e603af9fc41a7`
- Rapport de construction : `build/roundtrip/rebuild-report.json`
- Vérification après les essais : `build/roundtrip/final-integrity.json`
- Captures et événements horodatés : `build/roundtrip/evidence/`
- Résumé durable : [roundtrip-validation.json](roundtrip-validation.json)

La recompression et les nouveaux offsets modifient les octets du conteneur ISO, donc son hash. Il ne s'agit pas d'une copie binaire identique à l'image source.

## Méthode de reconstruction

`scripts/rebuild_iso.py` lit les entrées sans les ouvrir en écriture, puis refuse de poursuivre si l'extraction ne correspond pas à l'ISO source. Il refuse aussi de remplacer un répertoire de sortie existant.

Le compresseur LZSS est déterministe : fenêtre de 4 Kio, références de 3 à 18 octets et copie chevauchante autorisée. Les tests vérifient notamment les données nulles, répétitives, aléatoires, la fenêtre circulaire et les cas limites. Chaque flux réencodé est redécodé et comparé aux octets d'origine avant incorporation dans l'archive. Les en-têtes inconnus, identifiants et noms FSYS sont conservés ; les positions et tailles sont mises à jour, avec alignement des membres à 32 octets et footer FSYS de 32 octets.

L'archive passe de **944 672 à 959 200 octets**. Elle est placée à l'offset disque `0x418000`, aligné sur 32 Kio, dans l'espace précédant les fichiers de la FST et après toutes les zones système. Son ancienne copie reste intacte dans l'ISO. L'ordre des fichiers, les noms et les indices de la FST sont conservés ; seuls les huit octets contenant l'offset et la taille de `common.fsys` changent.

L'image source sert de modèle pour conserver les zones non référencées du disque. Tous les fichiers référencés sont ensuite écrits depuis l'extraction, en remplaçant uniquement `common.fsys` par l'archive réencodée. Une validation de tous les payloads et fichiers système précède la publication du fichier `.iso` final.

Une vérification indépendante confirme que **1 459 019 032 octets**, hors les deux seules plages autorisées ci-dessous, sont strictement identiques à l'image source :

| Plage | Début inclus | Fin exclue | Taille |
|---|---:|---:|---:|
| Offset et taille de common dans la FST | 4 222 988 | 4 222 996 | 8 |
| Nouvelle archive common.fsys | 4 292 608 | 5 251 808 | 959 200 |

Le vérificateur officiel a été exécuté :

```powershell
.\Dolphin-x64\DolphinTool.exe verify -u build/roundtrip/tool-user -i build/roundtrip/colosseum-pal-roundtrip.iso
```

Résultat : code de sortie 0, `Problems Found: No`, CRC32 `62a55c7e`, SHA-1 `8d4593390676f1037670d923b43a789e5b456c9a`. Le programme a également émis `Error creating key` ; aucun problème de disque n'a été rapporté. Ce contrôle ne vérifie pas l'ensemble des mécaniques du jeu.

## Essais réels

L'émulateur a été lancé avec `-u build/roundtrip/dolphin-user` et `-e` pointant explicitement vers l'ISO reconstruite. La carte mémoire EUR et le SRAM ont été **copiés** dans ce nouveau profil. Les cheats étaient désactivés ; aucun réglage ou patch par jeu du profil habituel n'a été importé.

Les entrées interactives ont été pilotées avec la fenêtre de manette TAS de Dolphin, via le contrôle d'interface Windows. Aucun code de gameplay n'a été injecté et aucune démo automatique n'a été utilisée comme preuve de combat interactif.

| Essai | Observation | Capture dans evidence/ |
|---|---|---|
| Démarrage | Écran titre en français | `01-title.png` |
| Carte mémoire | Message de chargement réussi | `02-memory-card-loaded.png` |
| Continuer | Copie de sauvegarde chargée, puis retour dans le monde | `03-save-loaded-in-world.png` |
| Déplacement | Le personnage et la caméra répondent au stick | `04-world-movement.png` |
| Réinitialisation logicielle | Retour à l'écran titre, après une transition noire | `05-soft-reset-title.png` |
| Préparation interactive | Combat rapide, double, adversaire très fort, sélection de quatre Pokémon | `06-interactive-battle-start.png` |
| Arène et commandes | Colisée de Phénacit, menu d'attaque accessible | `07-battle-arena.png` |
| Capacités et dégâts | Pied Brûleur choisi pour Braségali ; Donphan passe de 150 à 67 PV, puis utilise Pouv.Antique | `08-turn-resolution.png` |
| Tour terminé | Retour au menu d'attaque, Donphan à 67/150 PV et Braségali à 101/140 PV | `09-post-turn-state.png` |

Pour le tour observé, Laggron a reçu la commande Malédiction et Braségali Pied Brûleur, ciblant Donphan. Le retour aux commandes du tour suivant établit que le tour est arrivé à son terme. L'émulateur a ensuite été fermé proprement, avec un code de sortie 0.

## Préservation et limites

Après fermeture de Dolphin, les SHA-256 de l'ISO source et des **2 011 fichiers extraits** sont inchangés. Les **20 fichiers existants** du profil habituel inclus dans le contrôle — configuration, GC/carte mémoire et éventuels réglages ou états — sont également inchangés. Les modifications de session et caches appartiennent au profil de test sous `build/`.

Les seize tests de lecteurs et de réencodage passent. Les sources de formats sont [les sources primaires déjà recensées](community-formats.md), complétées par [le reconstructeur FSYS de GoD-Tool](https://github.com/StarsMmd/GoD-Tool/blob/c39f0100a4b81819a5d7552af81b7adaaf7f3f8c/GoD%20Tool%20Package/Sources/Shared/Core/Engines/GeniusSonority/File%20Formats/FSYSArchive.swift), [DirectoryBlob de Dolphin](https://github.com/dolphin-emu/dolphin/blob/master/Source/Core/DiscIO/DirectoryBlob.cpp) et [les arguments de lancement Dolphin](https://github.com/dolphin-emu/dolphin/blob/master/Source/Core/UICommon/CommandLineParse.cpp).

La validation couvre ces scénarios précis : elle ne constitue pas un parcours complet du jeu, une validation sur GameCube physique, un test d'écriture de sauvegarde en jeu ou une validation d'un futur randomizer. L'audio n'a pas fait l'objet d'une évaluation et aucune mesure de performances n'a été réalisée.

## Reproduire

Depuis la racine du projet, en choisissant un **nouveau** répertoire de sortie :

```powershell
python scripts/rebuild_iso.py --source-iso 'Pokemon Colosseum (Europe) (En,Fr,De,Es,It).iso' --output-dir build/roundtrip-2
python scripts/prepare_dolphin_test.py --output build/roundtrip-2/dolphin-user
.\scripts\start_dolphin_test.ps1 -Iso build/roundtrip-2/colosseum-pal-roundtrip.iso -UserDirectory build/roundtrip-2/dolphin-user
python scripts/verify_roundtrip.py --build-dir build/roundtrip-2
python -m unittest discover -s tests -v
```

La carte mémoire originale est copiée lors de la préparation ; les essais écrivent dans le profil de test. Pour rouvrir le résultat déjà produit, lancer simplement `.\scripts\start_dolphin_test.ps1`.
