# Premier randomizer des Pokémon de dresseurs

Version réalisée le **30 octobre 2026** pour le dump **GC6P01 PAL, révision 0**. Le moteur construit une nouvelle ISO à partir des données originales et de la seed choisie.

- ISO : `build/randomizer-v1/colosseum-pal-randomized.iso`
- Taille : **1 459 978 240 octets**.
- SHA-256 : `576e362ed037d8c1889683f6a72b5a83eee815d9346c07c3dad4e7a836ba0440`
- Script : `scripts/randomize_trainers.py`
- Journal exhaustif : `build/randomizer-v1/randomizer-manifest.json`
- Vérification de l'ISO : `build/randomizer-v1/randomizer-verification.json`
- Preuves du test : `build/randomizer-v1/evidence/`
- Résumé durable : [randomizer-validation.json](randomizer-validation.json)

## Règles de cette version

Le randomizer remplace l'espèce de **3 355 emplacements peuplés référencés par la table des dresseurs**, chez **817 des 820 dresseurs**. Chaque emplacement sélectionné reçoit une espèce différente de son espèce initiale, tirée uniformément parmi les **386 espèces réelles**. Les indices internes valides sont `1..251` et `277..411` ; les entrées réservées, nulles et l'œuf sont exclus.

Les emplacements partagés par plusieurs dresseurs sont traités une seule fois. Les **108 emplacements de Pokémon obscurs** sont regroupés par leurs **48 identifiants obscurs** : un seul tirage par identifiant, propagé à tous les combats et à l'espèce de la table obscure associée. Les identifiants, compteurs, références de dresseurs et autres champs de cette table sont conservés. Plusieurs identifiants obscurs peuvent recevoir la même espèce : il n'y a pas de contrainte d'unicité.

Le nom affiché est actualisé avec le nom par défaut de la nouvelle espèce. Le script refuse un nom personnalisé ou une version inconnue du REL. Les niveaux, capacités, objets, nature, sexe, EV et IV sont conservés. Le sélecteur de talent est conservé, sauf **410 replis `1 → 0`** lorsque la nouvelle espèce ne possède pas de deuxième talent. Le marqueur de talent aléatoire `FF` reste intact.

La version conserve les **2 122 emplacements vides**, les **33 emplacements peuplés non référencés par les dresseurs**, les starters et cadeaux du DOL, les textes et les scripts de scénario. Les capacités restent celles des Pokémon remplacés : elles peuvent être étrangères au répertoire habituel de la nouvelle espèce. Les équipes ne sont pas équilibrées par puissance, type ou stade d'évolution.

## Reproductibilité

L'algorithme est identifié par **`trainer-species-sha256-v1`**. Il utilise SHA-256 avec rejet du surplus avant réduction modulo, sans dépendre du générateur aléatoire de Python, de l'heure ou de l'ordre d'itération des dictionnaires.

L'entrée du hash est la concaténation suivante : identifiant de version ASCII, octet nul, longueur de seed sur deux octets big endian, seed UTF-8 exacte, octet nul, clé ASCII, octet nul, compteur sur quatre octets big endian. La clé est `slot:INDEX` pour un Pokémon ordinaire ou `shadow:ID` pour un groupe obscur. Le compteur commence à zéro. Le pool est trié par indice interne et l'espèce d'origine est exclue. Les seeds contiennent de 1 à 256 octets UTF-8 ; espaces, casse et accents font partie de la seed.

La même seed, le même dump et la même version reproduisent les mêmes données. La seed ne fixe pas le tirage des adversaires, l'IA ou les dégâts du jeu lors des parties : elle fixe le contenu de l'ISO.

Le build calcule deux fois le REL à partir de l'original. Le vérificateur recalcule ensuite le REL et l'archive FSYS depuis la seed, et les compare octet par octet aux données relues dans l'ISO finale. Toutes les autres plages de l'ISO sont comparées intégralement à l'image source.

## Contrôles statiques

Le REL de sortie a le SHA-256 `de232598f23440f9be97d71fce14e7cbe8998c1b26474eef2034d66ba3b13bcc`. **10 568 octets** changent, exclusivement dans les champs d'espèce, de nom, les replis de talent nécessaires et les 48 champs d'espèce des métadonnées obscures. Les **27 autres membres** de `common.fsys` sont identiques après décompression.

L'archive reconstruite mesure **959 808 octets** et est placée à `0x418000`. L'image ne diffère de l'originale que dans sa plage `[4 292 608, 5 252 416)` et les huit octets FST `[4 222 988, 4 222 996)`. Les **1 459 018 424 autres octets** sont identiques.

`DolphinTool verify` termine avec le code **0**, `Problems Found: No`, CRC32 `5b328d93` et SHA-1 `7bdc606df9a91aa8cfba2c39fa25362efe3a0017`. Il émet aussi `Error creating key`, comme lors des essais précédents.

Les **25 tests** couvrent les lecteurs, l'encodeur, le patch témoin et le randomizer : vecteurs de seed figés, même seed/même résultat, seeds différentes, alias obscurs, emplacements partagés, cases vides et non référencées, talents et rejet de modifications supplémentaires.

Les formats reposent sur [l'analyse locale et ses sources primaires](community-formats.md), notamment [CMTrainerPokemon.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/enumerable/CMTrainerPokemon.swift), [CMPokemonStats.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/enumerable/CMPokemonStats.swift) et [le générateur de Pokémon de la décompilation US](https://github.com/wastelandgunner/pkmn-colosseum/blob/20fb9460b2259bf17631a5777fc080d918291d65/src/game/pokemon_range_8011F5FC.c). Les offsets utilisés sont vérifiés sur notre REL PAL ; les adresses de la version US ne sont pas transposées.

## Test sous Dolphin

La nouvelle ISO a été lancée explicitement avec **Dolphin 2609a, JIT64 SC, Direct3D 12, DSP HLE**, cheats désactivés, dans le profil `build/randomizer-v1/dolphin-user`. La carte mémoire EUR et le SRAM y sont copiés. Aucun état provenant d'une ancienne ISO n'a été chargé. Les entrées interactives passent par la manette TAS de Dolphin, via le contrôle de l'interface Windows.

Le scénario est **Combat rapide → Double → Très fort**, au Colisée de Phénacit. Le jeu a attribué l'équipe de **Simone (766)** au joueur **MICHAEL**, face à **Basile (771)**. Les douze espèces affichées correspondent exactement au manifeste de cette seed :

| Équipe | Espèces d'origine, dans l'ordre | Espèces randomisées observées |
|---|---|---|
| Simone, prêtée au joueur | Méganium, Typhlosion, Aligatueur, Mentali, Noctali, Ursaring | Tarinor, Mystherbe, Foretress, Hoothoot, Airmure, Delcatty |
| Basile, ordinateur | Suicune, Raikou, Entei, Galeking, Donphan, Drattak | Électrode, Séviper, Férosinge, Kadabra, Saquedeneu, Roigada |

Foretress, Tarinor, Mystherbe et Airmure ont été sélectionnés. Le combat charge les modèles de Foretress et Tarinor face à Saquedeneu et Électrode. Les quatre Pokémon sont niveau 50 ; leurs PV initiaux affichés sont respectivement **135, 90, 125 et 120**. Le menu de Foretress affiche bien Pouv.Antique, Séisme, Casse-Brique et Retour, conservés depuis l'enregistrement d'Aligatueur.

| Preuve | Capture dans evidence/ |
|---|---|
| Écran titre français | `01-french-title.png` |
| Carte mémoire copiée chargée | `02-copied-memory-card-loaded.png` |
| Six espèces de l'équipe de Simone | `03-randomized-player-team.png` |
| Douze espèces des deux équipes | `04-randomized-both-teams.png` |
| Quatre modèles chargés et PV initiaux | `05-randomized-battle-models.png` |
| Capacités héritées de Foretress | `06-preserved-moves.png` |
| Retour au menu du tour suivant et PV modifiés | `07-turn-resolution.png` |
| Pouv.Antique passé de 5 à 4 PP | `08-post-turn-pp-consumed.png` |

Un tour a été joué en commandant **Pouv.Antique de Foretress sur Saquedeneu** et **Plaquage de Tarinor sur Électrode**. Le jeu est revenu au menu d'attaque, sans blocage. Les PV constatés après ce tour sont Foretress **117/135**, Tarinor **51/90**, Saquedeneu **104/125**, Électrode **30/120**. Pouv.Antique affiche ensuite **4/5 PP**. Les variations de PV sont celles du tour complet ; elles ne sont pas attribuées isolément à une seule capacité.

Dolphin a ensuite été fermé proprement avec le code de sortie **0**. Le test couvre ce tour interactif, sans combat complet ni parcours du scénario.

## Préservation après le test

La vérification complète exécutée après fermeture de Dolphin confirme que **l'ISO source, les 2 011 fichiers de `game/` et les 20 fichiers existants du profil Dolphin habituel contrôlés par le manifeste sont inchangés**. Les cartes mémoire originales restent dans le profil habituel ; les écritures de session et caches appartiennent au nouveau profil sous `build/`.

Le REL et l'archive FSYS recalculés depuis la seed sont identiques à ceux relus dans l'ISO. Les hashes des deux résultats précédents, ISO sans changement et patch témoin Pikachu, ont aussi été revérifiés et sont inchangés. Le détail de ces contrôles et les hashes des huit captures sont enregistrés dans le résumé durable.

## Limites de validation

La cohérence des 48 groupes obscurs est contrôlée statiquement dans l'ISO. Leur capture, réapparition après échec, purification et évolution ne sont pas validées par cet essai de Combat rapide. Les anciennes captures ne sont pas migrées, les dialogues nommant l'espèce d'origine ne sont pas réécrits et tous les éventuels cas particuliers des scripts/DOL n'ont pas été exclus. Une progression complète du scénario reste nécessaire avant de considérer cette version comme validée pour une partie entière.

Pas de test sur console physique, d'écriture de sauvegarde en jeu, d'évaluation audio ou de mesure de performances.

## Construire une autre seed

Depuis la racine du projet, choisir un répertoire de sortie inexistant :

```powershell
python scripts/randomize_trainers.py --source-iso 'Pokemon Colosseum (Europe) (En,Fr,De,Es,It).iso' --seed 'ma-seed' --output-dir build/randomizer-ma-seed
python scripts/prepare_dolphin_test.py --output build/randomizer-ma-seed/dolphin-user
.\scripts\start_dolphin_test.ps1 -Iso build/randomizer-ma-seed/colosseum-pal-randomized.iso -UserDirectory build/randomizer-ma-seed/dolphin-user
python scripts/randomize_trainers.py --verify-only --output-dir build/randomizer-ma-seed
```

Pour lancer l'ISO déjà produite :

```powershell
.\scripts\start_dolphin_test.ps1 -Iso build/randomizer-v1/colosseum-pal-randomized.iso -UserDirectory build/randomizer-v1/dolphin-user
```

La préparation copie la carte mémoire et le SRAM dans le profil isolé. Les captures déjà présentes dans une ancienne sauvegarde ne sont pas converties : commencer une nouvelle partie dans ce profil pour jouer le scénario randomisé. Ne pas charger un état Dolphin provenant d'une autre ISO, qui pourrait restaurer les anciennes tables en mémoire.
