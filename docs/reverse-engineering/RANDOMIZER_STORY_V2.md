# Randomizer histoire v2 : dresseurs, starters et dons identifiés

Cette version du **30 octobre 2026** étend le randomizer aux six routines de création de starters et cadeaux identifiées dans le programme PAL **GC6P01, révision 0**. À seed identique, elle reproduit les tirages de dresseurs de la v1.

Pour jouer à cette version, utiliser **`jouer-randomizer-histoire.ps1`** à la racine du projet. Ce lanceur ouvre explicitement la nouvelle ISO avec son profil isolé, sans utiliser la carte mémoire habituelle.

- ISO : `build/randomizer-story-v2/colosseum-pal-randomizer-story.iso`
- Taille : **1 459 978 240 octets**.
- SHA-256 : `1e1dea04cb1bac4e4c82abf4301843934d11430782927d97342e92bfb86d0686`
- Script : `scripts/randomize_story.py`
- Journaux : `randomizer-manifest.json` pour les dresseurs, `specials-manifest.json` pour les starters/dons, dans le répertoire de construction.
- Vérification : `build/randomizer-story-v2/story-verification.json`
- Captures : `build/randomizer-story-v2/evidence/`
- Résumé durable des contrôles : [story-v2-validation.json](story-v2-validation.json)

## Résultat de la seed

| Emplacement d'origine | Remplacement | Niveau conservé | Statut de la routine |
|---|---|---:|---|
| Noctali | **Queulorior** | **26** | Starter |
| Mentali | **Flagadoss** | **25** | Starter |
| Posipi | Arbok | 13 | Don du scénario |
| Ho-Oh | Artikodin | 70 | Récompense |
| Celebi | Hypocéan | 10 | Routine événementielle présente en PAL, accès non démontré |
| Pikachu | Qwilfish | 10 | Routine événementielle présente en PAL, accès non démontré |

Les **3 355 Pokémon de dresseurs chez 817 dresseurs**, dont les **48 groupes obscurs**, restent identiques à ceux produits par la même seed en v1. Le REL et l'archive `common.fsys` entière ont les mêmes octets que la v1. Les règles de niveaux, capacités, talents et alias obscurs sont décrites dans [le rapport v1](RANDOMIZER_V1.md).

## Modifications du programme

Le script refuse tout DOL différent du SHA-256 original `a788176a45eb88dbd227246a7205ab9856bc79f3cca7e4a0f5376cf466664df5`. Il vérifie les instructions PowerPC `li r4, espèce`, `li r5, niveau` et l'appel au constructeur local `0x80128238`, puis ne remplace que les immédiats d'espèce et les deux immédiats d'EXP des starters.

| Routine | Base dans main.dol | Champ espèce u16 |
|---|---:|---:|
| Noctali | `0x131E1C` | `0x131E1E` |
| Mentali | `0x131CF4` | `0x131CF6` |
| Posipi | `0x131BF4` | `0x131BF6` |
| Ho-Oh | `0x131B10` | `0x131B12` |
| Celebi | `0x1318E0` | `0x1318E2` |
| Pikachu | `0x1319F0` | `0x1319F2` |

Les starters réécrivent leur EXP après création. À `base + 0x92`, cette EXP est recalculée au **seuil du niveau conservé**, selon le groupe de croissance de la nouvelle espèce : Queulorior reçoit **14 060 EXP** au niveau 26 ; Flagadoss **15 625 EXP** au niveau 25. La progression partielle vers le niveau suivant est remise à zéro. Les quatre autres routines laissent le constructeur calculer l'EXP.

Le constructeur initialise le nom depuis la nouvelle espèce. Les appels et les instructions de capacités/objets/nature restent inchangés. Les capacités imposées par les routines peuvent donc rester celles de l'espèce remplacée, comme pour les Pokémon de dresseurs.

Pour cette seed, **11 octets de main.dol** changent. Son SHA-256 devient `6330e041a5f13fb63a65d308a3a8d45e47c99b462d4e396be8eba3869b93b485`. Le DOL original n'est jamais ouvert en écriture ; sa version modifiée est également conservée dans le répertoire de construction.

La vérification de l'ISO autorise seulement les octets DOL effectivement différents, les huit octets FST de `common.fsys` et la nouvelle archive. Les **1 459 018 413 autres octets** restent identiques à l'ISO source. Le DOL entier doit aussi être égal au résultat recalculé depuis la seed ; aucun masque ne permet de cacher d'autres modifications de code.

## Reproductibilité et contrôles

La version globale est **`trainers-and-gifts-v2`**. Elle réutilise le tirage SHA-256 v1 avec les clés distinctes `special:umbreon`, `special:espeon`, `special:plusle`, `special:ho-oh`, `special:celebi-event`, `special:pikachu-event`. Le pool reste celui des 386 espèces réelles, en excluant l'espèce d'origine de chaque routine. La seed ne fixe pas l'IA, le PID ni les dégâts pendant les parties.

Les **30 tests** passent, incluant les six groupes de croissance, les seuils 25/26, la répétabilité, le rejet d'un mauvais DOL ou d'instructions inattendues, le rejet d'une modification des niveaux/capacités/code et la création d'un profil sans importer de sauvegarde.

`DolphinTool verify` termine avec le code **0**, `Problems Found: No`, CRC32 `c5c5e4ac`, SHA-1 `c5a194b99377b36f9b82ecef565058b7b47a1a44`. Il émet également `Error creating key`, comme lors des contrôles précédents.

## Test réel d'une nouvelle partie

L'ISO a été lancée avec **Dolphin 2609a, JIT64 SC, Direct3D 12, DSP HLE**, cheats désactivés, dans `build/randomizer-story-v2/dolphin-user`. Ce profil a été créé avec `--empty-card`, sans importer la carte mémoire ni le SRAM habituels. Le jeu a confirmé l'absence de fichier, créé son fichier sur la nouvelle carte, puis démarré une nouvelle partie nommée **MICHAEL**.

Après l'introduction, le menu Pokémon du scénario montre effectivement les deux remplacements. Les fiches affichent leurs modèles animés et les informations suivantes :

| Starter obtenu | Niveau | PV | Type | Talent | EXP | EXP jusqu'au niveau suivant |
|---|---:|---:|---|---|---:|---:|
| Queulorior | 26 | 71/71 | Normal | Tempo Perso | **14 060** | **1 686** |
| Flagadoss | 25 | 86/86 | Eau / Psy | Tempo Perso | **15 625** | **1 951** |

Ces valeurs confirment que les niveaux et les courbes d'EXP restent cohérents après remplacement. L'émulateur a été fermé proprement avec le code de sortie **0**. Aucun combat de cette nouvelle partie ni obtention effective d'un cadeau tardif n'a été utilisé comme preuve.

| Preuve | Capture dans evidence/ |
|---|---|
| Carte de test vide, aucun fichier importé | `01-fresh-memory-card.png` |
| Deux starters reçus dans l'équipe du scénario | `02-new-story-starter-team.png` |
| Modèle, statistiques et EXP de Queulorior | `03-queulorior-summary-exp.png` |
| Modèle, statistiques et EXP de Flagadoss | `04-flagadoss-summary-exp.png` |

Le profil habituel a été inventorié avant cette session. Une tentative de contrôle avec le manifeste historique v1 a signalé quatre fichiers de configuration/SRAM déjà différents lors de la préparation v2. Le contrôle de conservation de cette extension se rapporte au manifeste v2 ; les anciens manifestes restent conservés. Une vérification de compatibilité sur l'ISO v1 avec la référence de profil actuelle passe dans `build/regression-v1-current-baseline/`.

Après fermeture de Dolphin, la vérification complète confirme que **l'ISO source, les 2 011 fichiers de `game/` et les 20 fichiers existants du profil habituel inventoriés avant cet essai sont inchangés**. Le REL, l'archive FSYS et le DOL ont été reproduits depuis la seed et comparés aux octets de l'ISO finale. Les trois ISO précédentes conservent leurs SHA-256 respectifs. Le résumé durable contient les résultats détaillés et les hashes des quatre captures.

## Périmètre et limites

Les routines Celebi/Pikachu existent dans le DOL PAL ; les modifier **n'active pas** ces événements. Leurs conditions d'accès ne sont pas modifiées. Les cadeaux tardifs et les événements demandent encore des essais spécifiques.

Les distributions externes Jirachi/Bonus Disc et e-Reader ne sont pas traitées par ces six routines. Jirachi reste une espèce possible dans le pool de tirage. Les 33 emplacements peuplés non référencés de la table des dresseurs restent conservés ; l'un d'eux est niveau zéro et sans capacité. Un constructeur constant d'Arcko niveau 1, au rôle non établi, est également conservé.

Les anciennes sauvegardes ne sont pas converties : les Pokémon déjà créés restent ceux de la sauvegarde. Les cinématiques préenregistrées, images fixes et dialogues ne sont pas réécrits. Cette version ne constitue pas une validation d'un parcours complet, des captures/purifications ou de toutes les récompenses.

## Construire et lancer

Depuis la racine du projet :

```powershell
.\jouer-randomizer-histoire.ps1
```

Pour une autre seed, choisir un répertoire de sortie inexistant :

```powershell
python scripts/randomize_story.py --source-iso 'Pokemon Colosseum (Europe) (En,Fr,De,Es,It).iso' --seed 'ma-seed' --output-dir build/histoire-ma-seed
python scripts/prepare_dolphin_test.py --output build/histoire-ma-seed/dolphin-user --empty-card
.\scripts\start_dolphin_test.ps1 -Iso build/histoire-ma-seed/colosseum-pal-randomizer-story.iso -UserDirectory build/histoire-ma-seed/dolphin-user
python scripts/randomize_story.py --verify-only --output-dir build/histoire-ma-seed
```

`--empty-card` crée un profil neuf sans importer les anciennes cartes ou le SRAM. Les originaux sont inventoriés pour le contrôle final. Le mode de copie utilisé par les essais précédents reste le comportement par défaut sans cette option.

## Sources primaires

- [XGDemoStarterPokemon.swift, commit f2d6c4a](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/enumerable/XGDemoStarterPokemon.swift) : routines Colosseum et EXP des starters.
- [CMGiftPokemon.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/enumerable/CMGiftPokemon.swift) et [CMGiftPokemonManager.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/managers/CMGiftPokemonManager.swift) : quatre dons et ensemble des six routines.
- [XGExpRate.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/enums/XGExpRate.swift) et [CMPokemonStats.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/enumerable/CMPokemonStats.swift) : croissance et octet de groupe à `species + 0x00`.
- [Dispatcher des six dons dans la décompilation NTSC-U](https://github.com/dougchansan/pkmn-colosseum/blob/ad02df4900c623d16d02b9a8ddd9c53ea0cd3db2/src/game/field_range_801CA7EC.c#L349) : corroboration des rôles ; les offsets utilisés proviennent du DOL PAL vérifié.
