# Couple de starters — PAL GC6P01

Contrôle statique et transformations en mémoire du 31 octobre 2026. Cette passe
réutilise les deux appels du constructeur déjà identifiés pour les starters.
Elle ne change ni conditions d'obtention, niveaux, graphe d'évolution, scripts,
ni taille du DOL. Elle ne constitue pas une observation sous Dolphin.

## Identité et champs

- `game/sys/main.dol` : SHA-256
  `a788176a45eb88dbd227246a7205ab9856bc79f3cca7e4a0f5376cf466664df5`.
- `game/files/common.fsys`, membre `common_rel` : SHA-256
  `ee2677af555dc59626f978e743235831a76cb23bae93f3fdd1060d808f749d0b`.
- Appel Noctali à l'offset fichier DOL `0x131E1C` ; appel Mentali à
  `0x131CF4`. Espèce : immédiat `li r4` à `+2`. Niveau : instruction entière
  `li r5` à `+4`, conservée. EXP : immédiat `li r7` à `+0x92`.
- Espèces initiales internes 197 et 196, niveaux respectifs 26 et 25, EXP
  natives 19055 et 16372. Les signatures d'instruction sont vérifiées avant
  toute écriture. Le wrapper valide les empreintes exactes originales ; le
  cœur à tables explicites permet les tests synthétiques.
- Les propriétés d'espèces viennent du même parseur `species_catalog` que les
  règles globales. Les familles et racines sont calculées depuis les cinq
  arcs d'évolution natifs par espèce (`+0x9C`, pas 6 octets), sans confondre
  index internes et numéros nationaux. L'inventaire PAL contient **202 racines**.

## Règles

Les quatre contrôles sont indépendants. Ils ne déclenchent pas la randomisation
d'un starter dont la case d'espèce est désactivée.

- `starter_balance_pair` : écart entre les deux totaux de statistiques de base
  au plus égal à `max(50, plus_petit_total // 5)`. Les BST sont ceux du REL
  final, y compris si un nouveau total a été tiré par la règle de statistiques.
- `starter_distinct_families` : familles d'évolution différentes ; toutes les
  branches natives d'une même famille comptent ensemble.
- `starter_complementary_types` : aucun type partagé, d'après les types du REL
  final. Le nom décrit la variété de couverture, pas une garantie de victoire,
  de résistances complémentaires ou de synergie stratégique.
- `starter_base_forms` : seuls les remplacements sans arc d'évolution entrant
  sont admissibles. Les bébés comptent : Pichu est une racine, Pikachu ne l'est
  pas. Les espèces sans évolution sont aussi des racines, y compris les
  légendaires autorisés. Cette règle ne force pas un partenaire conservé à
  régresser.

Les filtres de génération et de légendaires restent stricts. Munja est exclu
des nouveaux tirages. L'espèce originale du starter remplacé est exclue.

Si `balance_species` est actif, les exclusions précédentes sont appliquées
d'abord, puis le moteur conserve les candidats dont le BST **final** est à
`max(50, BST_original // 5)` du BST **original** de la rencontre. Comme le filtre
global existant, l'absence de candidat dans cette fenêtre retient uniquement
les BST admissibles les plus proches. Elle ne réintroduit aucune génération,
espèce légendaire ou forme évoluée exclue. La contrainte d'équilibre **entre les
deux starters** reste ensuite stricte, sans repli.

Le moteur énumère les couples ordonnés admissibles et tire uniformément parmi
eux par SHA-256 avec rejet, domaine `starter-pair-sha256-v1`, seed UTF-8 exacte.
Il ne tente pas un nombre limité de paires et ne relâche pas silencieusement
une contrainte. Un ensemble vide produit une erreur indiquant les filtres à
reconsidérer. Si un seul starter est randomisé, l'autre espèce courante
contraint le choix mais ses octets restent intacts.

Pour chaque starter remplacé, l'EXP est recalculée au seuil du niveau conservé
selon le groupe de croissance de l'espèce choisie. L'immédiat doit rester
représentable par `li` signé. Aucun octet hors des deux espèces et deux EXP
autorisées n'est écrit ; les modifications antérieures du DOL sont conservées.

## Composition

`apply_starter_rules(original_dol, current_dol, original_rel, rel, seed, options)`
renvoie le DOL et un rapport `applied`, `rules`, `pair`, `valid_pair_count` et
les différences/tolérances BST. Le moteur s'appelle au début du traitement DOL
avancé, après les propriétés finales d'espèces du REL. Lorsqu'il s'applique,
le tirage filtré individuel historique des deux starters doit être sauté.
Les capacités de départ sont ensuite calculées à partir des espèces finales,
avec les règles d'attaques déjà existantes. Les dons restent indépendants.

Sans contrainte active, le DOL courant est rendu inchangé et la sélection
historique continue. Si les deux starters sont conservés, aucun tirage, aucune
contrainte de couple et aucune réécriture d'EXP n'est appliquée.

## Contrôles

`python -m unittest tests.test_starter_rules -v` : **10 tests réussis**, dont
un contrôle optionnel sur les fichiers PAL locaux. Les tests vérifient seed,
masque d'écriture, EXP et niveaux, partenaire fixe, formes de base et bébés,
filtres de génération/légendaires/Munja, types et statistiques finales,
composition avec la fenêtre BST individuelle, erreurs sans solution, formes
de données et signatures invalides.

Essai direct du helper avec la seed historique de test, les règles recommandées et
propriétés d'origine : **21 259 couples admissibles** ; Hypocéan (interne et
national 117), niveau 26, BST 440, EXP 17576 ; Élektek (125), niveau 25,
BST 490, EXP 15625. Écart 50, tolérance 88, types Eau et Électrik.
Cet essai ne préjuge pas d'une autre version du moteur ou de règles différentes.

Un second essai du helper avec types et statistiques randomisés, sans
conservation des totaux, lit bien les propriétés finales : couple interne
361/350 (nationaux 355/298), BST 503/456, types Insecte/Plante, écart 47 pour
une tolérance de 91. Les noms/paramètres d'une partie complète restent ceux du
rapport final produit par le service, et non d'un tirage intermédiaire.

Ces contrôles établissent les octets et les règles de sélection. La puissance
réelle dépend aussi des capacités, talents et rencontres ; un BST comparable
ne certifie pas l'équilibrage d'une partie. Aucun combat, acquisition de
starter ou parcours complet n'est revendiqué par cette passe isolée.
