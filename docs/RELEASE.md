# Construire et vérifier une distribution

Deux constructions sont séparées. L’édition locale dans `dist/` embarque le pack
exporté du jeu. L’édition publique dans `dist/public/` contient le même moteur,
les mêmes profils et les cadres dessinés par l’application, sans images ni sons
du jeu. Elle démarre sans ROM ; les commandes audio indisponibles sont désactivées.
Le pack local n’est pas suivi par Git et n’est pas lu par le build public.

L’icône d’application Éclipse appartient à `assets/app/` et accompagne les deux
éditions. Le master PNG et le générateur Qt sont fournis avec les sources ; seul
le fichier ICO et sa provenance sont nécessaires à l’exécutable. Le contrôle des
archives autorise ces fichiers précis et continue de refuser le pack du jeu dans
l’édition publique. `python scripts/build_app_icon.py` régénère les neuf tailles.

## Construction

Depuis les sources, avec Python 3.12+, Rust/MSVC et les dépendances installées :

```powershell
python -m pip install -r requirements-build.txt
python scripts/fetch_qt_notices.py
python scripts/build_desktop.py --edition public
python scripts/verify_release.py --edition public
python scripts/smoke_desktop.py --edition public --report build/public-smoke.json
```

Omettre `--edition public` pour la construction locale avec son pack vérifié.
`--source-only` produit uniquement les sources ; le build public fonctionne aussi
sans pack présent sur le disque. Les ZIP existants sont refusés : les conserver
dans un autre dossier avant une reconstruction. Le dossier EXE généré peut être
reconstruit, sans modifier les ROM, `game/` ou les sauvegardes.

L’audit contrôle les empreintes, le CRC ZIP, les chemins et l’absence de ROM,
sauvegarde ou Dolphin. L’audit public refuse aussi les ressources du jeu. Le ZIP
Windows contient les sources de l’application, les notices et les sources Qt.

## Diagnostic de l’exécutable

Le diagnostic utilise les vrais widgets Qt et un fichier de préférences temporaire.
Il ne lit aucune ROM et n’utilise pas les préférences personnelles. Il vérifie le
codec Rust contre la référence Python, les ressources présentes et 48 états du
parcours : six langues, 1040 × 800/680 × 540, ROM/réglages simples/avancés/création.
Il contrôle aussi 24 dialogues d’exclusion (espèces/types, six langues, deux tailles),
avec leurs listes, sélections et actions de validation.

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
& .\OrreRandomizer.exe --diagnostics .\diagnostics.json --screenshots
```

Choisir un nouveau rapport dans un dossier accessible. L’exécution se termine avec
un code nul si les contrôles passent. `smoke_desktop.py` va plus loin : il extrait
le ZIP dans un nouveau chemin avec espaces et accents, enlève Python et les outils
du PATH, change le répertoire de travail et isole AppData/Temp avant de lancer ce
diagnostic. Les captures et le rapport restent dans `build/`.

Ce test local ne remplace pas une autre installation Windows : les bibliothèques
du système restent celles du PC de test. Le workflow manuel `package.yml` prépare
ce même contrôle sur un runner Windows hébergé, sans ROM ni pack local.
Lancer **Package Windows release** à la main pour obtenir les artefacts de test.

Pour publier, vérifier que `pyproject.toml` et `colosseum_randomizer/__init__.py`
portent la même version, puis pousser un tag Git `v<version>` sur le commit voulu.
Le workflow vérifie le tag et publie le ZIP Windows avec `OrreRandomizer.exe`,
le ZIP source et `SHA256SUMS.json` après les tests de l’édition publique.

```powershell
git tag -a v0.20.0 -m "Pokémon Orre Randomizer 0.20.0"
git push origin v0.20.0
```

L’aperçu des starters utilise `build_patches` et ses valeurs finales, sans publier
de nouvelle ROM. Ses tests sans ROM couvrent la conservation de l’entrée, les
erreurs, la conversion temporaire, les résultats tardifs, l’annulation et le
changement de langue. Une validation locale séparée compare espèces et niveaux
aux instructions DOL finales pour les trois modes, un starter conservé, les
types/statistiques randomisés et les formes de base ; elle compare aussi ISO/RVZ.
Les portraits de résultat sont décodés depuis la ROM fournie, dans les deux éditions.

## Vérification locale du moteur et de l’audio

```powershell
python -m unittest discover -s tests -v
python scripts/validate_seed_matrix.py original.iso build/seed-matrix.json
python scripts/validate_audio_pack.py build/audio-levels.json
```

La matrice exige l’empreinte PAL vierge. Elle reconstruit deux fois les patches de
douze configurations, sans créer d’ISO, puis relit le REL/DOL final : espèces,
filtres, 48 groupes obscurs, alias, capacités ordinaires, marqueurs spéciaux,
familles, EXP des starters et noms des pierres. Elle vérifie la conservation de
la source. Les configurations comprennent une copie, les trois générations,
les règles de boss et les propriétés avancées.

Le contrôle audio mesure le PCM16 : taille, durée, crêtes, saturation et raccord
de boucle. Il ne revendique pas une écoute humaine. L’essai natif local du thème
pendant plus d’une durée complète est conservé dans le dossier privé de QA.

## Validation du jeu

Les essais Dolphin déjà effectués sont détaillés dans
[le rapport fonctionnel](DOLPHIN_VALIDATION_2026-10-31.md). La matrice statique ne
prouve ni une partie complète du scénario, ni l’équilibrage sur plusieurs parties.
Les nouveaux noms sont vérifiés dans les cinq banques de textes ; leur affichage
dans chaque menu du jeu reste un contrôle visuel distinct.

Avant de qualifier une release stable, conserver un relevé d’essai sur un second
Windows et d’une progression ordinaire jusqu’à la fin. Mentionner les fonctions
vérifiées et les limites restantes dans les notes de version.
