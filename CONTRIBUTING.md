# Contribuer

Contributeur initial du projet : [KadenHD](https://github.com/KadenHD).

Python 3.12 ou plus récent. Le code de l'application est sous licence MIT.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[build]"
python -m unittest discover -s tests -v
python -m colosseum_randomizer
```

Le moteur est dans `colosseum_randomizer/engine`, l'orchestration ISO/RVZ dans
`service.py`, l'interface Qt dans `gui.py`. Les anciens scripts restent utilisables
et délèguent au même moteur. La CLI et l'interface utilisent la même fonction
`service.randomize`, sans dépendre d'un dump extrait ni d'un profil Dolphin.

Les tests de formats et de sécurité fonctionnent sans ROM. Les intégrations qui
ont besoin d’un dump ou d’une image régionale locale déclarent ce prérequis et
sont explicitement ignorées quand il manque. Ne pas
ajouter de ROM, données extraites, sauvegarde, capture du jeu ou émulateur au dépôt.
Un signalement doit contenir la version, les options et les empreintes, sans image
du jeu ni chemins personnels ; relire le rapport avant de le partager.

Pour une nouvelle région/révision, documenter ses empreintes et vérifier ses
structures indépendamment avant d'ajouter un profil. Ne jamais désactiver le
contrôle d'empreinte pour accepter une image inconnue.

La seed est une chaîne UTF-8 exacte, sensible aux espaces et à la casse. Une
modification de l'algorithme qui change les tirages doit changer sa version et
préserver une preuve de reproduction. Les évolutions doivent conserver le graphe
des familles ; les alias d'un Pokémon obscur doivent rester synchronisés.

## Traductions de l'interface

Les [conventions de rédaction](docs/INTERFACE_COPY.md) fixent le vocabulaire et
le ton des libellés, aides et messages.

`i18n.py` résout les langues système et rend les messages, sans Qt ni état global
du moteur. L’interface comporte six langues : français, anglais, allemand,
espagnol, italien et japonais. Le français sert de clé source dans les libellés
et les métadonnées d’`Options` ; les cinq fichiers `locales/en.py`, `de.py`, `es.py`,
`it.py` et `ja.py` fournissent les autres catalogues. Les **83 paramètres, dont
58 booléens, dans quinze catégories** utilisent des identifiants stables.
`feature_i18n.py` complète les messages et options des ajouts récents ;
`detail_texts.py` fournit les textes des fiches et du journal dans les six langues.
`settings_i18n.py` et `settings_presentation.py` portent les textes et la logique
de présentation de recherche/récapitulatif, sans dépendre du moteur de tirage.
Les noms de repli de `locales/selection_names.py` et `locales/detail_names.py`
ont leur provenance et leur licence dans `licenses/pokeapi-*.json` et
`licenses/pokeapi.txt`. Les propriétés du jeu restent lues dans la ROM finale.
Les chemins, seeds et valeurs de configuration ne sont jamais traduits.
Les paramètres dynamiques utilisent `Message(template, **parameters)` ; un
paramètre qui est lui-même un libellé traduisible doit être un `Message` imbriqué.
Conserver exactement les noms et formats des paramètres entre les traductions.

Une évolution de navigation, de recherche ou de récapitulatif ne doit pas modifier
`Options`, les tirages ou `ENGINE_VERSION`. Une hausse de version de l’application
doit conserver l’import strict des profils de la version précédente : contrôler
d’abord leur version, leurs champs et leur empreinte, puis conserver leurs valeurs.
Vérifier aussi la remise à zéro d’une seule catégorie et l’affichage des règles
effectives avec les mêmes options dans les six langues.

Pour ajouter une langue, créer son catalogue, l'enregistrer dans `CATALOGS` et
`LANGUAGES`, et définir sa locale Qt dans l'interface. Les tests vérifient la
couverture des libellés et aides, les paramètres de formatage, la détection, la
mémorisation et le changement pendant une création. Les traductions sont incluses
hors ligne dans les sources et l'exécutable. Les sélecteurs de fichiers natifs
gardent les contrôles fournis par le système ; leurs titres et filtres sont
fournis dans la langue choisie par l'application.

## Construire les archives

Le build Windows accéléré demande Rust et un linker MSVC compatible. Le crate
`native/` n'a aucune dépendance externe ; ses tests et sa compilation fonctionnent
hors ligne. L'utilisation des sources Python sans accélération ne demande pas Rust.

```powershell
python -m pip install -r requirements-build.txt
python scripts/build_native.py
python scripts/fetch_qt_notices.py
python scripts/build_desktop.py
```

Le build Windows produit un dossier avec EXE et DLL remplaçables, un ZIP Windows,
un ZIP des sources et leurs SHA-256 dans `dist/`. La sélection des sources est une
liste positive ; aucun dossier `game`, `build` ou `Dolphin-x64` n'est inclus.
Sur une autre plateforme : `python scripts/build_desktop.py --source-only`.
Pour l’édition publique : ajouter `--edition public`. Cette édition n’ouvre pas
le pack local et l’exclut des sources comme de l’exécutable ; elle est produite
séparément dans `dist/public/`. Voir [les commandes de validation](docs/RELEASE.md).
Pour reconstruire une version existante, déplacer d'abord les anciens ZIP : ils
ne sont pas écrasés. Le build local ne publie aucun fichier sur Internet.

Avant publication : vérifier les archives, joindre les sources exactes des
bibliothèques Qt distribuées et leurs notices (THIRD_PARTY_NOTICES.md), et tester
l'archive décompressée sur une machine Windows sans Python.
