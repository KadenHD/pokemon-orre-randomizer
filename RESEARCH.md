# Pokémon Colosseum : analyse du dump PAL

Cartographie statique reproductible de l'extraction locale `game/`, réalisée le 30 octobre 2026. Version observée : **GC6P01, révision 0**.

Pour recréer une partie avec le moteur v3, utiliser la procédure du [rapport v3](docs/reverse-engineering/RANDOMIZER_V3.md) et démarrer une nouvelle sauvegarde.

- [Résultats, offsets et limites](docs/reverse-engineering/REPORT.md)
- [Intégrité de l'extraction et ressources](docs/reverse-engineering/assets.md)
- [Sources primaires et schémas communautaires](docs/reverse-engineering/community-formats.md)
- [Résumé de référence vérifié](docs/reverse-engineering/baseline.json)
- [Reconstruction ISO et essais réels sous Dolphin](docs/reverse-engineering/ROUNDTRIP.md)
- [Patch témoin : un Donphan de Basile remplacé par Pikachu](docs/reverse-engineering/WITNESS_PATCH.md)
- [Randomizer des dresseurs v1 : seed, règles et test Dolphin](docs/reverse-engineering/RANDOMIZER_V1.md)
- [Randomizer histoire v2 : starters, dons et vérifications](docs/reverse-engineering/RANDOMIZER_STORY_V2.md)
- [Randomizer v3 : familles obscures uniques et évolutions accessibles](docs/reverse-engineering/RANDOMIZER_V3.md)
- [Application v0.5 : profils, starters, obscurs de boss et validation](docs/DESKTOP_V05.md)

Python 3.12 et bibliothèque standard uniquement, sans installation de dépendances. Depuis la racine du projet :

```powershell
python scripts/analyze_game.py --extract-common
python scripts/inspect_tables.py
python scripts/survey_assets.py --game game --iso 'Pokemon Colosseum (Europe) (En,Fr,De,Es,It).iso'
python -m unittest discover -s tests -v
```

Les scripts lisent les fichiers originaux sans les modifier. Les deux premiers écrivent leurs résultats dans `analysis/generated/` : inventaires SHA-256, sections DOL/REL, membres FSYS, puis tables JSON nommées en français et en anglais. `--extract-common` écrit aussi les 28 membres décompressés de `common.fsys` dans ce répertoire local. Le troisième affiche un compte rendu JSON et compare l'extraction à l'ISO locale lorsque celle-ci est fournie.

Le lecteur de tables refuse un `common.rel` différent de celui validé : les offsets d'une autre région ou d'un jeu déjà modifié demandent une nouvelle vérification. Les nombres d'enregistrements incluent les entrées nulles, réservées et éventuellement inutilisées.

Une ISO séparée a maintenant été reconstruite après recompression de `common.fsys`, avec identité des données décompressées vérifiée. Le démarrage, le chargement d'une sauvegarde copiée, un déplacement et un tour de combat interactif ont été validés sous Dolphin 2609a. L'ISO produite est `build/roundtrip/colosseum-pal-roundtrip.iso` ; les preuves et les limites sont dans le rapport de reconstruction.

Pour relancer l'ISO avec son profil de test isolé :

```powershell
.\scripts\start_dolphin_test.ps1
```

Un patch témoin séparé remplace uniquement le Donphan niveau 50 de Basile par Pikachu, avec son nom par défaut. Les capacités et les autres données de cet enregistrement sont conservées. Le script `scripts/patch_trainer.py` refuse les versions inconnues et les enregistrements partagés entre dresseurs ; son vérificateur contrôle l'ISO produite et les originaux. Les commandes de construction et de lancement sont dans le rapport du patch témoin.

Le premier randomizer est disponible dans `scripts/randomize_trainers.py`. L’ISO de validation couvre 3 355 Pokémon chez 817 dresseurs, y compris les 48 groupes obscurs synchronisés. Les espèces et noms changent ; les autres données sont conservées, avec repli sur le premier talent si nécessaire. La même seed et la même version reproduisent les mêmes tables et la même archive. Les règles, limites et commandes sont dans le rapport du randomizer.

La progression complète du scénario et l'équilibrage restent à valider. Les dumps, l'émulateur, les ISO et profils de test sont exclus par `.gitignore`.

La v2 ajoute les six routines PAL identifiées : Noctali, Mentali, Posipi, Ho-Oh, Celebi et Pikachu événementiel. Pour cette seed, les deux starters deviennent Queulorior niveau 26 et Flagadoss niveau 25 ; leur EXP est adaptée. Les équipes de dresseurs de la v1 restent identiques. Les routines événementielles sont modifiées sans activer les événements ; les distributions externes ne sont pas incluses.

La v3 conserve ces starters et dons, corrige les cinq collisions de familles parmi les obscurs et rend accessibles les 15 évolutions bloquées par les échanges, le jour/la nuit ou la beauté. Les évolutions par échange deviennent des évolutions au niveau 40 ; les branches concurrentes utilisent des pierres différentes. Les six pierres sont ajoutées aux boutiques de Phénacit et de Pyrite pour 2 100 chacune. Les originaux et les anciennes ISO sont conservés.
