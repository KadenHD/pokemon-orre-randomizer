# Exclusions et équipes des dresseurs — 0.9

Les nouveaux réglages sont dans **Avancé** et restent désactivés par défaut.

| Réglage | Effet |
| --- | --- |
| Pokémon autorisés → Pokémon exclus | Retire les espèces cochées de tous les tirages de remplacement. Recherche par nom ou numéro national. |
| Pokémon autorisés → Types d’origine exclus | Retire les espèces ayant un des types cochés dans le jeu d’origine, même en double type. |
| Dresseurs → Types des équipes non obscures | Sans thème, un type commun au hasard, ou un type commun d’origine si possible. |
| Dresseurs → Adversaires non obscurs au stade final | À partir du niveau choisi, utilise une espèce qui n’évolue plus. |

Les exclusions concernent les dresseurs, les obscurs, les starters et les cadeaux
remplacés. Elles ne retirent pas les Pokémon explicitement conservés et
n’interdisent pas automatiquement les autres membres d’une famille.
Les noms des listes suivent la langue de l’interface ; les numéros restent les
mêmes. Cochez pour exclure. Les actions de groupe ne concernent que les résultats
visibles de la recherche. **Annuler** conserve la sélection précédente.

Les thèmes ne s’appliquent qu’aux Pokémon non obscurs dont le remplacement est
activé. Le mode d’origine cherche un type partagé par les membres non obscurs
initiaux. Si ce type n’existe pas ou ne permet pas de respecter les contraintes,
un autre thème admissible est choisi. Le thème utilise les types finaux, après
leur éventuelle randomisation. Les exclusions restent fondées sur les types
d’origine. Un obscur n’est jamais changé pour s’adapter au thème.

Le stade final utilise le niveau après le multiplicateur général et le bonus
des boss. Le seuil est indépendant des niveaux d’évolution habituels. Sans
remplacement aléatoire des espèces, seules les évolutions finales descendantes
du Pokémon sont admises ; les Pokémon déjà au stade final sont conservés.
Avec le remplacement aléatoire, les candidats au-dessus du seuil sont les
formes finales autorisées, y compris les espèces sans évolution.

Les enregistrements d’équipe partagés sont traités ensemble et ne sont pas
dupliqués. La diversité des familles des boss est prise en compte dans
l’attribution. L’équilibrage de puissance est une préférence ; les exclusions,
le thème et le stade demandé restent obligatoires. Un ensemble impossible
provoque une erreur récupérable avant publication de la ROM.

Les capacités sont recalculées lors d’un changement supplémentaire d’espèce
uniquement si leur randomisation est activée. Les marqueurs spéciaux, niveaux,
IV, EV, objets, pointeurs d’équipe et identifiants obscurs sont conservés par
cette étape. Les options séparées qui modifient niveaux, IV, EV ou objets
s’exécutent avant elle.

Les profils 0.5 à 0.8 sont vérifiés avec leur empreinte originale puis migrés
avec ces nouveaux réglages vides ou désactivés. Le moteur courant est
`trainer-policies-and-exclusions-v10`, et les tirages des préréglages 0.8 sont
conservés. Les profils actuels exigent les 66 champs et valident les listes
d’identifiants. Le rapport de création contient `summary.trainer_policies`
avec thèmes, groupes partagés, espèces finales, niveaux et capacités.

La CLI expose `--trainer-theme-mode none|random|preserve`,
`--trainer-force-evolved` / `--no-trainer-force-evolved`,
`--trainer-evolution-level 40`, `--excluded-species 25,133` et
`--excluded-types 10,17`. Les espèces utilisent les numéros nationaux ; les
types utilisent les identifiants natifs de Colosseum :

| ID | Type | ID | Type |
| --- | --- | --- | --- |
| 0 | Normal | 10 | Feu |
| 1 | Combat | 11 | Eau |
| 2 | Vol | 12 | Plante |
| 3 | Poison | 13 | Électrik |
| 4 | Sol | 14 | Psy |
| 5 | Roche | 15 | Glace |
| 6 | Insecte | 16 | Dragon |
| 7 | Spectre | 17 | Ténèbres |
| 8 | Acier | 9 | Invalide, refusé |

Validation locale : tests de masques binaires et de contraintes sur fixtures,
composition sur les données PAL, matrice de seeds reproductibles, comparaison
des données produites aux sources archivées 0.8 et contrôles Qt dans six langues.
Ces contrôles techniques ne certifient pas une partie complète ni son équilibrage.
