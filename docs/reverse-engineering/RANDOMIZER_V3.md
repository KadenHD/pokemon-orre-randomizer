# Randomizer v3 : familles obscures uniques et évolutions accessibles

Version PAL GC6P01 révision 0, 30 octobre 2026. Algorithme `unique-shadow-families-accessible-evolutions-v3`.

La v3 répond à deux règles : les 48 identifiants de Pokémon obscurs doivent appartenir à 48 familles d'évolution différentes, et les évolutions doivent être réalisables dans Colosseum. Elle autorise toujours les formes déjà évoluées dans les tirages.

## Jouer

Lancer `jouer-randomizer-histoire.ps1` à la racine. Il ouvre l'ISO `build/randomizer-v3/colosseum-pal-randomizer-v3.iso` avec le profil séparé `build/randomizer-v3/play-user`, préparé sans importer la carte mémoire d'origine.

Commencer une **nouvelle partie**. Changer d'ISO ne transforme pas les starters et les Pokémon déjà capturés dans une sauvegarde existante. Le profil `dolphin-user` sert uniquement aux essais avec une copie de sauvegarde ; le lanceur utilise `play-user` pour jouer.

Les règles des dresseurs et dons de la v2 restent en vigueur, y compris les six routines spéciales identifiées. Pour cette seed : Queulorior niveau 26 et Flagadoss niveau 25 au départ. Les événements externes ne sont pas activés.

## Unicité des familles obscures

Les familles sont calculées depuis le graphe complet des évolutions du `common.rel` original : 386 espèces, 184 liens, 202 composantes connexes. Les embranchements font partie d'une même famille, notamment Évoli, Debugant, Chenipotte et Ningale.

La v2 donnait seulement 43 familles distinctes. La v3 conserve le plus petit identifiant obscur de chaque famille, réserve toutes les familles déjà retenues puis retire uniquement les cinq collisions, dans l'ordre des identifiants. Le tirage SHA-256 utilise la seed et la clé `shadow-family-v3:{identifiant}`. Il n'utilise ni l'heure ni l'état global du générateur Python.

| Identifiant obscur retiré | Collision v2 | Remplacement v3 |
| --- | --- | --- |
| 5 | Roucool / Roucarnage | Vibraninf |
| 31 | Gloupti / Avaltout | Ptéra |
| 35 | Tadmorv / Grotadmorv | Porygon2 |
| 42 | Mimitoss répété | Balignon |
| 57 | Élektek répété | Élecsprint |

Les neuf occurrences de ces cinq groupes chez les dresseurs sont synchronisées avec la table des obscurs. L'unicité porte sur les **48 groupes capturables** : les rencontres répétées d'un même identifiant conservent la même espèce. Les Pokémon ordinaires des dresseurs et les six dons ne changent pas par rapport à la v2.

## Évolutions rendues accessibles

Les 184 destinations et tous les embranchements sont conservés. Seules 15 méthodes et conditions changent, soit 30 octets effectifs dans les données d'évolution.

| Espèce | Évolution | Nouvelle condition |
| --- | --- | --- |
| Kadabra | Alakazam | Niveau 40 |
| Machopeur | Mackogneur | Niveau 40 |
| Gravalanch | Grolem | Niveau 40 |
| Spectrum | Ectoplasma | Niveau 40 |
| Onix | Steelix | Niveau 40 |
| Hypocéan | Hyporoi | Niveau 40 |
| Insécateur | Cizayox | Niveau 40 |
| Porygon | Porygon2 | Niveau 40 |
| Têtarte | Tarpaud | Pierre Soleil |
| Ramoloss | Roigada | Pierre Eau |
| Coquiperl | Serpang | Pierre Eau |
| Coquiperl | Rosabyss | Pierre Lune |
| Évoli | Mentali | Pierre Soleil |
| Évoli | Noctali | Pierre Lune |
| Barpau | Milobellus | Niveau 40 |

Les évolutions au niveau 40 se déclenchent lors d'un gain de niveau à partir de 40, y compris si le Pokémon est obtenu au-dessus de ce seuil. La purification des obscurs reste nécessaire. Les règles natives de bonheur simple, de statistiques de Debugant, de personnalité de Chenipotte et le mécanisme spécial de Ningale restent inchangés.

L'examen du moteur PAL a confirmé que les méthodes jour/nuit d'Évoli n'aboutissent pas à une évolution. Le moteur retient également la dernière branche compatible : remplacer toutes les branches d'une espèce par le même niveau supprimerait des choix. Des pierres distinctes conservent donc l'accès à chaque destination. Tartard reste accessible par Pierre Eau et Flagadoss au niveau 37.

## Pierres en boutique

Les pierres Soleil, Lune, Feu, Foudre, Eau et Plante sont ajoutées aux catalogues d'achat 3 et 5, correspondant à Phénacit et Pyrite. Leur prix est de **2 100** chacune. Seul le prix initial nul de la Pierre Lune nécessite une modification dans `main.dol` ; les cinq autres prix sont déjà de 2 100.

Les cinq archives `pocket_menu.fsys`, `pocket_menu_fr.fsys`, `pocket_menu_ge.fsys`, `pocket_menu_it.fsys` et `pocket_menu_sp.fsys` sont modifiées. Le catalogue REL occupe 109 de ses 122 entrées, sans changer sa taille ni ses relocations. Les stocks initiaux restent disponibles. Les trois listes 0 à 2 sont réordonnées pour partager leurs suffixes, sans gagner ni perdre d'article ; les neuf autres listes restent identiques. Les types de dialogue et devises ne changent pas. Les onze autres membres de chaque archive sont inchangés après décompression.

Le premier essai ciblait les listes 0 à 2, interprétées à tort comme des menus d'achat. Le test réel de Pyrite a détecté l'absence des pierres dans son catalogue. La correction cible les menus d'achat de type 0 ; un contrôle de régression vérifie explicitement le stock de Pyrite et l'absence de pierres ajoutées aux listes 0 à 2. L'ISO d'essai est conservée sous `build/randomizer-v3-before-shop-fix/`.

## Reconstruction reproductible

```powershell
python scripts/randomize_accessible.py --source-iso 'Pokemon Colosseum (Europe) (En,Fr,De,Es,It).iso' --seed exemple-v3 --output-dir build/randomizer-v3
python scripts/randomize_accessible.py --verify-only --output-dir build/randomizer-v3
python -m unittest discover -s tests -v
```

La reconstruction part toujours des originaux vérifiés. `common.fsys` et les cinq archives de boutiques sont replacés dans l'espace libre précédant les fichiers du disque ; les six entrées FST sont actualisées. Les anciennes copies restent dans l'ISO. Tous les octets hors des plages autorisées sont comparés à l'ISO source.

| Fichier produit | SHA-256 |
| --- | --- |
| ISO v3 | `e37dae3666fae8323cb9f9c55c679c170053c96430d0d22fe2c6057e3aeea941` |
| `common.rel` v3 | `0dd207d42d07b483fa5fa745a22d244846af845a4bd8866b11c02432bb6d2360` |
| `main.dol` v3 | `381add7c69294f0ebd54d7019c195cc6bc9717db2f51f49cb6dee5a76ac33363` |
| REL de boutiques, commun aux cinq langues | `322c09fe916c3dc5ac3f1c5e87c019639a09761bda6b92d6cb2df7ab3d346986` |

Taille ISO : 1 459 978 240 octets. DolphinTool : vérification réussie, aucun problème signalé, CRC32 `4540a9cd`, SHA-1 `37496b7c3607b871713fce6e52081ffbb44d1a44`.

## Vérifications et limites

Les **43 tests** passent. Ils couvrent les familles ramifiées, le tirage déterministe et sa stabilité JSON, les occurrences obscures partagées, la conservation des tirages ordinaires et spéciaux, les règles d'évolution, les cinq langues et les stocks des autres boutiques. Une seconde lecture de l'ISO reconstruite confirme les 48 familles, les 15 règles, les charges utiles et l'absence de modification hors des plages prévues.

Le test sous **Dolphin 2609a** a démarré normalement l'ISO finale, chargé la carte mémoire copiée avec « Continuer », puis rejoint le magasin de Pyrite. Les six pierres sont visibles à 2 100. L'achat d'une Pierre Lune a été effectué : quantité 0 → 1 et solde 8 015 → 5 915. Le sac initial étant plein, les deux Super Potions de la copie ont d'abord été vendues pour libérer un emplacement. Aucun changement n'a été apporté à la sauvegarde d'origine.

Un état rapide provenant du premier essai a été écarté pour la validation finale, car il restaurait l'ancien catalogue en RAM. Les captures finales proviennent du parcours normal depuis la carte mémoire sur l'ISO corrigée.

- [Les six pierres à 2 100](../../build/randomizer-v3/evidence/02-six-stones-at-2100.jpg).
- [Pierre Lune avant l'achat](../../build/randomizer-v3/evidence/05-moon-stone-free-slot-before.jpg).
- [Pierre Lune reçue et solde débité](../../build/randomizer-v3/evidence/06-moon-stone-purchase-success.jpg).
- [Résumé de validation](randomizer-v3-validation.json).

Les preuves de test Dolphin et les contrôles d'intégrité sont consignés dans `randomizer-v3-validation.json` et `build/randomizer-v3/evidence/`. La progression intégrale du scénario, l'équilibrage et le déclenchement en jeu de chaque branche d'évolution restent à valider. Phénacit et les quatre autres langues sont contrôlés dans les données ; leur interface n'a pas été parcourue. Les contrôles binaires ne sont pas présentés comme une partie complète.

Les fichiers `game/`, l'ISO source, les anciennes ISO et le profil Dolphin d'origine sont conservés. Les sauvegardes de test et de jeu sont isolées.

## Sources de formats et preuve PAL

Les offsets et empreintes sont vérifiés sur ce dump PAL. Les sources communautaires servent à interpréter les structures ; elles ne remplacent pas cette vérification régionale.

- [Méthodes d'évolution de Pokemon-XD-Code](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/enums/XGEvolutionMethods.swift).
- [Structure d'une évolution](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/XGEvolution.swift).
- [Structure et prix des objets](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/enumerable/CMItem.swift).
- [Symboles des tables REL](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/file%20formats/XGRelocationTable.swift).
- [Décompilation du moteur, corroboration US](https://github.com/dougchansan/pkmn-colosseum/blob/ad02df4900c623d16d02b9a8ddd9c53ea0cd3db2/src/game/pokemon_range_80128524.c). Le dispatch PAL a été vérifié indépendamment à l'adresse RAM `0x8012C87C` / offset DOL `0x12987C`, avec sa table de sauts RAM `0x803B0510` / fichier `0x3AD510`.
