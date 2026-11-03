# Application v0.5 : profils, starters et obscurs des boss

Version du 31 octobre 2026. Moteur `starter-shadow-boss-rules-v7`.
59 paramètres, dont 51 booléens, dans les quatorze catégories natives.

## Profils partageables

Importer ou exporter près du champ seed fonctionne sans sélectionner de ROM.
Le JSON contient toutes les règles, la seed exacte, les versions application et
moteur, le format de profil et l’identité publique de la ROM compatible. Aucun
chemin de ROM, sortie, Dolphin ou sauvegarde n’est enregistré. Les chemins du
formulaire ne changent pas à l’import ; le fichier entier est vérifié avant de
modifier le formulaire. Une limite de 64 Ko, des types stricts et le rejet des
clés inconnues, absentes ou répétées protègent des fichiers incorrects.

L’empreinte SHA-256 du contenu détecte une modification accidentelle. Ce n’est
pas une signature d’authenticité. Les profils d’une autre version sont refusés
avec une explication ; aucune migration silencieuse ne change les tirages.
Un export refuse un fichier existant. La CLI accepte `--profile ma-partie.json` ;
les options explicitement indiquées et `--seed` peuvent le surcharger.

## Duo de starters

Quatre cases s’appliquent aux espèces de départ randomisées :

- `starter_balance_pair` : écart de total de statistiques au plus égal à
  `max(50, 20 % du plus faible)`, à partir des statistiques finales.
- `starter_distinct_families` : familles d’évolution différentes.
- `starter_complementary_types` : aucun type partagé, à partir des types finaux.
  Il ne s’agit pas d’une garantie de couverture de tous les types adverses.
- `starter_base_forms` : aucune préévolution dans le graphe natif. Les espèces
  sans évolution sont admissibles, y compris les légendaires autorisés.

Les filtres de génération/légendaires et la préférence de puissance globale
restent respectés. Un partenaire dont la randomisation est désactivée ne change
pas et sert de contrainte au second. Si aucun couple n’est possible, la création
échoue avec une explication et aucune sortie. Les couples admissibles sont
énumérés, puis un couple est choisi uniformément avec la seed ; aucune limite
arbitraire de tentatives ne peut rejeter un couple pourtant possible.

Les niveaux 26/25 et les instructions restent conservés ; les deux EXP suivent
le groupe de croissance final. Les attaques sont choisies après les espèces.
Les autres dons gardent leur tirage indépendant. Ces quatre nouvelles cases
restent désactivées dans les valeurs de base CLI, pour préserver les anciens
usages ; les trois premières sont activées par « Règles recommandées ».

## Pokémon obscurs des boss

Les sept chefs déjà identifiés utilisent sept groupes obscurs distincts :
19, 21, 23, 34, 38, 43 et 44, dans 16 apparitions de leurs variantes.

- `boss_shadow_legendary_mode` : filtres globaux, conserver le statut légendaire
  d’origine, ou exclure les légendaires/fabuleux de ces sept groupes.
- `boss_shadow_power_mode` : suivre la préférence globale, imposer une fenêtre
  stricte de `±max(50, 20 % du total natif remplacé)`, ou ignorer cette préférence
  chez les boss. Les autres filtres restent appliqués dans les trois modes.
- `boss_shadow_min_bst` : minimum de total **natif**, avant toute redistribution
  optionnelle des statistiques. Zéro signifie aucun minimum.

Les 48 familles sont attribuées simultanément par matching lorsque l’unicité
est activée. Une famille utile à un boss ne peut donc pas être consommée sans
possibilité de réaffectation par un tirage ordinaire précédent. Les contraintes
strictes ne sont jamais assouplies. Un repli de préférence globale de puissance
nécessaire pour l’unicité est consigné dans le rapport.

Les filtres globaux restent prioritaires : conserver un légendaire tout en les
interdisant produit une erreur explicite. Les niveaux, identifiants obscurs,
taux de capture, nombre de Pokémon et scripts ne changent pas. Les réglages de
niveaux/capture existants restent indépendants. Toutes les apparitions d’un même
obscur reçoivent la même espèce. Les deux options de renforcement/variété des
compagnons non obscurs s’appliquent ensuite sans toucher à ces tirages.

Par défaut, ces trois réglages spécifiques sont neutres : le fonctionnement des
obscurs de la v0.4 est conservé. Ils s’ignorent si les obscurs ne sont pas randomisés.

## Validation technique

196 tests Python et trois tests Rust réussis. Les tests ajoutés couvrent les profils et leur import
transactionnel dans le formulaire, l’EXP et les attaques après sélection du duo,
les propriétés finales, les filtres stricts, un matching avec réaffectation, les
sept groupes de boss et leurs alias, l’unicité des 48 familles et les octets
autorisés. Neuf tests du moniteur Dolphin vérifient aussi l'isolation des chemins,
le suivi des fichiers personnels et l'enregistrement du code natif du processus.
Les sources originales restent lues sans écriture.

La seed de validation figure dans le rapport de test local.

| Essai | Résultat |
| --- | --- |
| Preset recommandé depuis ISO | 10,80 s ; ISO `648cc8c0744c87fce40a7d4dbdd3f6f95f8df29bc48415ee33507cb5d1894b35` |
| Import du profil et reconstruction | 11,56 s ; même ISO |
| Import dans l’exécutable Windows, puis création à 100 % | 10,62 s ; même ISO |
| Tous changements désactivés | 7,97 s ; ISO strictement identique à l’originale |
| RVZ → RVZ, boss statut légendaire conservé, puissance proche, minimum 450 et starters de base | 24,12 s ; retour ISO vérifié `e3bf0206a25701bd17a04d8f51fb1b96b6560bbab373a82949a94566dad21adc` |

Le duo recommandé attendu est Hypocéan niveau 26, BST 440, EXP 17 576, et Élektek
niveau 25, BST 490, EXP 15 625. Les types ne se recoupent pas ; l’écart 50 est
inférieur à la tolérance 88. Ces valeurs proviennent des données finales.

Les rapports et captures de QA restent dans `build/v05-qa/` et
`build/dolphin-validation/`, hors distribution.
La vérification technique ne certifie pas un scénario intégralement joué.
Les observations Dolphin sont consignées séparément des valeurs attendues.

La procédure de publication vérifie l'intégrité des archives et l'absence de
ROM, sauvegarde ou émulateur. Elle lance les tests depuis une archive source
extraite sans le dump du jeu ; les cas exigeant les données locales ou un codec
compilé sont alors ignorés. Le résultat propre aux archives reconstruites est
consigné après exécution de `scripts/verify_release.py`.

## Première passe Dolphin et conservation : historique

Lors de la première passe, deux démarrages à froid ont été effectués dans des
profils sous `build/v05-qa/` :
une carte vide pour l’ISO recommandée, puis une copie de la carte personnelle pour
`gameplay-check.iso`. Cette dernière active les règles obscures de boss et retire
la protection des soins vendus, afin de préparer un contrôle de boutique.
Le chargement de la copie et les déplacements depuis le PC, à l’extérieur et vers le pont ont
été observés. Les captures sont dans `evidence/`. Aucun état RAM d’une ancienne
ISO n’a été chargé.

À ce stade initial, les nouveaux starters, achats, collecte de coffre,
purification suivie d'une CT et combats des sept boss n'avaient pas encore été
vérifiés en jeu. Leurs données avaient seulement été contrôlées automatiquement.
Le premier lanceur Dolphin s’est terminé avec le code 0 ; le second a retourné 1
après fermeture, sans diagnostic visible et avec un journal vide. La cause de ce
statut de fermeture n’est pas établie ; ce contrôle ne vaut pas validation d’une
session complète. Le randomizer ne lance pas Dolphin dans le parcours utilisateur.

Après les essais, les ISO/RVZ sources, les 2 011 fichiers de `game/` et la carte
mémoire personnelle `MemoryCardA.EUR.raw` ont conservé leurs empreintes. Une
instance Dolphin personnelle était déjà ouverte avant les tests. Parmi ses
20 fichiers inventoriés, `Config/Qt.ini` et `GC/SRAM.raw` ont changé pendant la
session ; cette passe n’établit pas l’auteur de ces deux écritures. Leur état
courant n’a pas été remplacé pour tenter une restauration. La carte mémoire de
jeu personnelle reste identique à la copie initiale. Les manifestes détaillés
restent locaux et ne sont pas distribués. Ces observations historiques ne sont
pas remplacées par les essais suivants et aucune restauration n'est revendiquée.

## Suivi fonctionnel du 31 octobre 2026

Le [rapport Dolphin daté](DOLPHIN_VALIDATION_2026-10-31.md) distingue désormais
les valeurs attendues, les préparations privées et les actions natives observées.
Une nouvelle partie crée effectivement les starters Hypocéan 26 et Élektek 25.
Dans une copie préparée, Onix 39 est purifié, apprend Tunnel par CT05 puis évolue
en Steelix au niveau 40 après un Super Bonbon. L'apprentissage, l'évolution et
les quatre capacités conservées sont vérifiés en mémoire et à l'écran.

L'achat de Précision+ à Pyrite débite exactement 950 et ajoute un exemplaire.
Le coffre testé donne trois Défense+ et active son drapeau natif. Une véritable
capture de Cochignon obscur niveau 35, groupe 19, ajoute un Pokémon dans une
case PC vide : occupation 14→15, Master Ball 1→0, drapeau de capture 2144 : 0→1.
Les Pokémon déjà présents dans le PC restent identiques. Ces résultats ne
proviennent pas d'une injection des récompenses ou du Pokémon capturé.

Le rapport daté fait référence pour le statut des sept équipes de boss, des
fermetures Dolphin et du contrôle final de conservation. Il décrit l'équipe de
test au niveau 80, les accès accélérés aux scènes, la remise à zéro préalable
d'un drapeau de capture sur une copie et la séparation entre l'émulateur officiel
et sa copie privée de diagnostic. Ces essais ne certifient pas une partie
complète, l'équilibrage normal ou le fonctionnement sur console physique.

## Recherche des formats

- [Champs et sélection des starters](reverse-engineering/V05_STARTERS_RESEARCH.md)
- [Inventaire et règles des obscurs de boss](reverse-engineering/V05_SHADOW_BOSS_RESEARCH.md)
