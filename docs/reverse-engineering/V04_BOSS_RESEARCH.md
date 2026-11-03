# Chefs identifiés et règles prudentes — PAL GC6P01

Observation statique du 31 octobre 2026. Les transformations travaillent sur des copies en mémoire ; aucun fichier original, pointeur d'équipe ni script n'est modifié.

## Sources et identité

- `game/files/common.fsys`, membre `common_rel` : SHA-256 `ee2677af555dc59626f978e743235831a76cb23bae93f3fdd1060d808f749d0b`.
- Tables obtenues avec `randomize_trainers.layout` et les auto-relocations du REL, contrôlées dans les bornes des sections : dresseurs `0x15DEEC`, 820 lignes de `0x34` ; Pokémon de dresseurs `0x16AE44`, 5 510 lignes de `0x50` ; espèces `0x1F05CC`, 413 lignes de `0x11C` ; obscurs `0x2125A0`, 97 lignes de `0x38`.
- Les noms FR/UK sont décodés des répertoires de chaînes du même REL. Chaque chef est vérifié simultanément par index, classe, identifiant du nom, chaînes FR/UK et premier index de son équipe. Aucune détection à partir du niveau.
- Schéma communautaire primaire épinglé : [CMTrainerPokemon.swift, commit f2d6c4af](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/enumerable/CMTrainerPokemon.swift), copie locale `analysis/generated/v03-references/CMTrainerPokemon.swift`, SHA-256 `a0c5ae733e17ccf9fe63b2bf355302b8850ec0d1f82af29edc139e678bb1f010`. Cette source précise les six IV à `+0x1C…+0x21` et les six EV aux octets `+0x23,+0x25,+0x27,+0x29,+0x2B,+0x2D`. Les octets intercalaires restent intacts.
- REA 6.8.0 : état consulté en lecture seule ; aucune session binaire active. Cette passe exploite le schéma conservé et les octets exacts via les parseurs locaux existants. Elle ne constitue pas une observation d'exécution.

Les offsets ci-dessus sont des offsets **fichier REL**, pas des adresses mémoire.

## Inventaire explicite

Chaque paire est `index dresseur → premier index Pokémon`. Le moteur inscrit l'offset exact et les références de chaque slot dans `boss_inventory`.

| Chef FR / UK | Classe / nom ID | Variantes épinglées | Slots peuplés | Slots obscurs |
|---|---:|---|---:|---:|
| BOULEDISCO / MIROR B. | 4 / 4285 | 162→2478, 163→3991, 164→3998, 165→4831, 166→4838, 793→5412 | 29 | 3 |
| DAKIM / DAKIM | 4 / 4195 | 211→2555, 212→4005, 213→4012, 214→4866, 215→4873, 795→5300 | 29 | 3 |
| VENUS / VENUS | 4 / 4113 | 326→2674, 327→4019, 328→4026, 329→4901, 330→4908, 796→5426 | 29 | 3 |
| TECK / EIN | 4 / 4269 | 403→2814, 404→4033, 405→4040, 406→4936, 407→4943, 807→5293 | 29 | 3 |
| HELGONZA / GONZAP | 23 / 4266 | 425→4047, 426→5209, 427→5216, 811→5328 | 21 | 2 |
| JAKYLLA / NASCOUR | 5 / 4167 | 437→4110, 438→4117 | 12 | 1 |
| NOSFRAT / EVICE | 6 / 4326 | 439→4124, 440→4131 | 12 | 1 |
| **Total** | | **7 personnages, 32 enregistrements** | **161** | **16** |

Les six emplacements fixes par équipe donnent 192 emplacements, dont 31 vides. Les 161 emplacements peuplés ont chacun une seule référence depuis les 820 lignes dresseur originales ; les 145 non-obscurs sont donc modifiables sans changer un autre dresseur. Ce constat est recalculé, pas seulement supposé par l'allowlist.

Les obscurs observés ici portent les IDs 19, 21, 23, 34, 38, 43 et 44, répétés dans leurs variantes. Leur espèce appartient aussi à la table globale des obscurs. Leurs six IV valent `0xFF` dans ces lignes ; les non-obscurs de cet inventaire ont six IV et six EV nuls. `0xFF` n'est jamais remplacé par une valeur littérale 31.

Les groupes identifient les principaux chefs de l'histoire et leurs variantes présentes en table. La présence d'une variante en table, y compris une variante sans obscur, ne prouve ni son état de scénario ni son accessibilité dans une sauvegarde. Aucune réécriture des conditions de scénario n'est tentée.

## Contrat de transformation

`apply_boss_rules(original, current, seed, options, tables=None) -> (bytes, summary)` s'appelle **après** `apply_rel_rules`, avant `apply_dol_rules` et le rapport final. Les deux options sont indépendantes et désactivées par défaut.

### `boss_stronger`

Pour les seuls slots non-obscurs admissibles :

- Niveau courant multiplié par 1,1, arrondi à l'entier le plus proche et plafonné à 100. Il se compose donc avec le multiplicateur global déjà appliqué ; il n'est pas calculé une seconde fois depuis le niveau original.
- IV littéraux entre 0 et 31 portés au minimum à 20. Chaque IV supérieur reste supérieur ; les sentinelles et autres octets hors plage restent intacts.
- EV portés au minimum à 64 par statistique uniquement si le total proposé est au plus 510. Sinon tous les EV du slot restent tels quels et le rapport explique le refus. Aucune valeur existante n'est diminuée. Les données originales inventoriées donnent un total de 384 après cette règle.

Ce sont des paramètres de difficulté explicites, pas une prétention à reconstruire une intention originale du jeu. Les obscurs conservent leurs niveaux et IV/EV courants : renforcer un chef ne renforce pas le Pokémon que le joueur doit capturer.

### `boss_team_variety`

Le moteur conserve les familles distinctes déjà présentes. Il remplace seulement un doublon de famille dans un slot non-obscur modifiable. Les familles des obscurs et des autres slots protégés sont réservées d'abord ; les familles des slots restant dans l'équipe ne servent jamais de nouveau tirage.

Le pool conserve les générations et légendaires autorisés, ainsi que l'équilibrage BST éventuel depuis l'espèce originale du slot. Les exclusions sont appliquées avant l'équilibrage ; le repli BST utilise seulement des candidats autorisés. Munja n'est pas ajouté par cette règle. Si aucun candidat n'est disponible, le doublon reste présent et `unresolved_team_duplicates` en donne le dresseur, le slot et la raison. Aucun filtre n'est désactivé implicitement.

L'espèce, son identifiant de nom et, si nécessaire, un sélecteur de seconde aptitude devenu indisponible sont actualisés. L'aptitude et les types sont lus depuis le catalogue **courant final**, qui inclut une éventuelle randomisation globale des propriétés. Si `randomize_trainer_moves` est actif, les seuls slots dont l'espèce est remplacée reçoivent un nouveau tirage avec les mêmes garanties offensives/STAB, anti-doublons et exclusions que les autres dresseurs. Si cette option est inactive, leurs capacités restent inchangées.

Le tirage utilise SHA-256, la seed UTF-8 exacte et une clé versionnée incluant le dresseur et le slot. Il est indépendant de l'ordre de la liste fournie. L'application depuis le même `current` produit les mêmes octets ; appliquer une seconde fois le renforcement sur une sortie déjà renforcée n'est pas une opération idempotente.

### Protections

Un slot obscur, partagé avec un autre dresseur ou contenant un marqueur de capacité `0xFFFF`/hors catalogue est entièrement préservé par ces deux règles. Aucun slot vide n'est rempli. Le nombre d'emplacements et leur ordre sont inchangés. Le moteur refuse toute modification hors des offsets autorisés des seuls slots admissibles.

La table globale des obscurs ne reçoit aucune écriture. Les 48 espèces et familles distinctes produites par la règle d'unicité précédente restent donc telles quelles. L'option ne change ni évolutions, boutiques, objets tenus, scripts, conditions de scénario, compteur de purification, IA ou références de combat. Les thèmes de type ne sont pas proposés dans cette passe.

## Validation et limites

`python -m unittest tests.test_boss_rules` : **10 tests réussis**. Sept tests synthétiques vérifient l'identité options inactives, les bornes et masques d'IV/EV/niveaux, le refus d'un plancher EV qui dépasserait 510, le partage des slots, les exclusions de générations impossibles, les marqueurs, ainsi que l'utilisation des types finaux pour le STAB. Trois tests locaux optionnels inspectent le vrai REL et sa composition avec les règles avancées.

Sur le REL original, les deux options modifient 145 slots non-obscurs, dont **12 changements d'espèce** qui éliminent les doublons de familles des variantes de Bouledisco. Les 16 slots obscurs restent intégralement identiques. La composition testée active aussi types/aptitudes/stats/capacités randomisés, génération 3 seule, légendaires interdits, équilibrage BST et niveaux globaux ×2 : les 48 familles obscures, les bornes de niveaux et les garanties STAB sont conservées. Les six octets précédant chacun des IDs de capacité restent intacts.

Ces contrôles établissent les données produites et leurs invariants. Ils ne prouvent pas la difficulté ressentie, le choix des attaques par l'IA ni l'accessibilité de chaque variante en partie. Aucun démarrage Dolphin ou combat de chef n'a été réalisé par cette passe isolée.
