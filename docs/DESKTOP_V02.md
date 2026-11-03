# Application v0.2 : règles indépendantes et accélération Rust

Version du 30 octobre 2026, Windows x64. Le moteur de sélection devient
`selective-story-rules-v4` ; le preset recommandé conserve exactement les données
de la v3 pour la même seed.

## Les seize booléens

| Groupe | Paramètres indépendants |
| --- | --- |
| Dresseurs | `randomize_trainers`, `randomize_shadows`, `unique_shadows` |
| Starters | `starter_umbreon`, `starter_espeon` |
| Dons et récompenses | `gift_plusle`, `gift_hooh`, `event_celebi`, `event_pikachu` |
| Évolutions | `evolve_trade`, `evolve_trade_items`, `evolve_coquiperl`, `evolve_day_night`, `evolve_beauty` |
| Boutiques | `stones_phenac`, `stones_pyrite` |

Les seize sont activés par défaut. Les deux presets restaurent les recommandations
ou désactivent tout. L'option de familles uniques se désactive si les obscurs ne
sont pas randomisés. Chaque routine de starter/don a sa propre seed dérivée ;
désactiver un Pokémon ne change pas les tirages des autres.

Les catégories d'évolution modifient respectivement 4, 6, 2, 2 et 1 routes, en
conservant les cibles et le graphe des familles. Un paramétrage qui active les
nouvelles évolutions par pierre sans proposer de boutique est refusé avant de
commencer, pour préserver leur accessibilité. Le stock original est conservé et
chaque boutique peut être activée indépendamment. Le prix de la Pierre Lune est
ajusté à 2 100 lorsque des pierres sont proposées.

En CLI : `--starter-umbreon` / `--no-starter-umbreon`, et de même pour chaque
paramètre, avec des tirets à la place des underscores. Les anciens raccourcis
`--keep-specials`, `--keep-evolutions` et `--allow-shadow-family-duplicates` restent
acceptés. Les rapports JSON conservent les seize valeurs effectives.

## Performance mesurée

Le profilage d'une archive a attribué presque tout le temps aux codecs LZSS. Le
module Rust implémente donc l'encodage et le décodage ; l'interface reste Qt et
l'orchestration Python. Il ne dépend d'aucune crate externe et se construit hors
ligne. Le codec Python de référence reste disponible sans Rust.

Mesure locale séquentielle de la reconstruction des six archives originales,
incluant décodage, encodage et contrôles :

| Traitement | Python | Rust |
| --- | ---: | ---: |
| Six archives | 23,234 s | 0,568 s |
| Gain sur cette étape | | ×40,91 |

Les six archives produites sont identiques octet pour octet entre les deux
implémentations. Les temps sont des observations sur ce poste ; le gain ne
s'applique pas aux copies disque, hashes ou conversions DolphinTool.

Création ISO complète avec la seed historique de test et toutes les règles activées :

| Étape | Temps |
| --- | ---: |
| Validation de la source | 0,922 s |
| Transformations et archives | 1,812 s |
| Copie et écriture des patches | 1,281 s |
| Vérification intégrale de l'ISO | 1,953 s |
| Dernier contrôle de la source | 0,969 s |
| Total observé | 6,94 s |

SHA-256 de sortie : `e37dae3666fae8323cb9f9c55c679c170053c96430d0d22fe2c6057e3aeea941`.
Il correspond exactement à l'ISO v3 déjà testée sous Dolphin. La source est intacte.
Les mesures sont reproductibles avec `scripts/benchmark_codec.py` (dump local
requis) et les temps par étape apparaissent désormais dans chaque rapport.

## Validation

72 tests Python et 3 tests Rust passent. Les tests croisent le code Python et Rust,
incluant les références chevauchantes, les tours du tampon de 4 Kio, les données
aléatoires et les flux malformés. Les tests de règles vérifient séparément les six
starters/dons, les cinq catégories d'évolution, dresseurs/obscurs et les deux boutiques.
Le preset vide conserve exactement les données originales ; le preset recommandé
reproduit la v3.

Essais complets supplémentaires : copie ISO avec toutes les règles désactivées
identique à l'original ; création RVZ personnalisée avec vérification de son
retour vers ISO, uniquement 108 apparitions obscures changées, 11 routes adaptées
et pierres à Pyrite seule. Depuis l'EXE, décocher Noctali tout en gardant Mentali
activé a produit une ISO en 6,97 s ; lecture du DOL de sortie : Noctali d'origine
(197), second starter Flagadoss (80). Le rapport conserve bien les seize booléens
et confirme le codec Rust et la source intacte. Les cinq tests Qt passent aussi
après adaptation de la taille initiale à l'écran.

Les originaux, les anciennes ISO et les anciens ZIP de version sont conservés.
Le périmètre PAL GC6P01 révision 0 et les limites de validation du scénario restent
ceux de la v0.1. Aucun dump, ressource du jeu, émulateur ou sauvegarde n'est distribué.
