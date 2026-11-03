# Règles des Pokémon obscurs des boss — v0.5

Contrôles statiques locaux du 31 octobre 2026 sur le `common_rel` PAL GC6P01
original, SHA-256 `ee2677af555dc59626f978e743235831a76cb23bae93f3fdd1060d808f749d0b`.
Cette passe réutilise les parseurs, schémas et identités vérifiés de
[l’enquête v0.4 sur les boss](V04_BOSS_RESEARCH.md). Aucun fichier original,
script de scénario ou état Dolphin n’est modifié par ce moteur.

## Inventaire observé

Les 32 variantes des sept chefs identifiés contiennent 16 apparitions obscures,
regroupées sous seulement sept identifiants globaux. Le moteur recalcule ces
groupes depuis `boss_inventory` et les octets originaux, sans heuristique de
niveau ou de puissance.

| Chef | ID obscur | Espèce originale | Apparitions dans l’inventaire des boss |
| --- | ---: | --- | ---: |
| Bouledisco | 19 | Simularbre, national 185 | 3 |
| Dakim | 21 | Entei, national 244 | 3 |
| Vénus | 23 | Suicune, national 245 | 3 |
| Teck | 34 | Raikou, national 243 | 3 |
| Helgonza | 38 | Airmure, national 227 | 2 |
| Jakylla | 43 | Métalosse, national 376 | 1 |
| Nosfrat | 44 | Tyranocif, national 248 | 1 |

Une apparition figurant en table ne prouve pas qu’une variante soit accessible
à un moment donné du scénario. Les règles suivent le groupe obscur dans toutes
ses apparitions, y compris hors de cette liste de boss. Aucun nouveau groupe
obscur ni combat n’est créé.

## Choix de conception et contrat

`apply_shadow_boss_rules(original, current, seed, options, tables=None)` valide
l’empreinte de l’original et les sept identités de boss, puis appelle le cœur
pur `apply_shadow_boss_tables`. Il doit s’exécuter avant les changements de
types, talents, statistiques et capacités, à la place du tirage ordinaire des
espèces obscures lorsque ses règles spécifiques sont actives. Les Pokémon
ordinaires des dresseurs restent entièrement tels que fournis dans `current`.

- `boss_shadow_legendary_mode`: `any` suit les autorisations générales ;
  `preserve` conserve le statut légendaire ou non légendaire du groupe original ;
  `exclude` interdit les légendaires et fabuleux chez ces sept groupes seulement.
- `boss_shadow_power_mode`: `global` suit `balance_species` ; `similar` impose
  strictement un écart au total original d’au plus `max(50, 20 % du total)` ;
  `free` désactive seulement la préférence de puissance chez les sept groupes.
- `boss_shadow_min_bst`: total natif minimal des espèces des sept groupes,
  entre 0 et 780 ; 0 ajoute aucune limite. Les espèces originales des trois
  premières générations culminent sous cette borne de saisie. Une valeur trop
  haute produit une erreur claire, elle n’est pas réduite implicitement.

Les totaux utilisés sont les statistiques **natives**, avant leur éventuelle
redistribution. Si un autre réglage change les totaux eux-mêmes, ce minimum ne
promet pas un minimum des statistiques finales. Cette portée figure dans le
rapport `bst_scope` et doit être annoncée dans l’interface.

Les exclusions générales de générations et de légendaires restent strictes.
Ainsi, conserver les boss légendaires tout en interdisant globalement tous les
légendaires est une configuration impossible, signalée par une erreur. Munja
est exclu des nouveaux tirages, et l’espèce originale de chaque groupe n’est
pas son propre remplacement.

Avec `unique_shadows`, le moteur résout simultanément les 48 groupes par
appariement biparti entre groupes et familles d’évolution. Il cherche d’abord
un appariement complet respectant les préférences de puissance. Si nécessaire,
il reprend sur les ensembles de candidats satisfaisant toutes les exclusions
strictes ; seuls les préférences du mode `global` peuvent alors sortir de leur
fenêtre ou de leur choix le plus proche. Chaque repli est inscrit dans
`power_preference_fallback_ids` et dans la ligne du groupe concerné.

Le mode `similar`, le minimum natif, les générations et le statut légendaire
ne sont jamais assouplis pour obtenir 48 familles. Si aucun appariement complet
n’existe, la génération échoue avec un message qui décrit les contraintes à
modifier. Aucune ISO partiellement validée n’est produite par ce moteur.

L’ordre des familles, des groupes et le choix de l’espèce d’une famille suivent
la seed UTF-8 exacte et des domaines SHA-256 versionnés, indépendamment de
l’ordre des dictionnaires ou de la liste d’inventaire. Une espèce est choisie
dans chaque famille attribuée, puis écrite dans la métadonnée obscur et tous
les enregistrements de dresseur qui partagent cet identifiant.

Les seules modifications autorisées sont l’espèce u16 de la métadonnée, et
l’espèce u16, l’identifiant de nom u32 et le sélecteur de talent du Pokémon de
dresseur. Le niveau, taux de capture, identifiant obscur, capacités, objets,
IV/EV, drapeaux et tous les autres octets fournis restent intacts.

Les valeurs spécifiques par défaut (`any`, `global`, 0) conservent exactement
le tirage v0.4. Désactiver `randomize_shadows` rend ces règles inactives.
Le renforcement et la diversité non obscure des boss s’exécutent ensuite,
comme auparavant, sans retoucher les obscurs sélectionnés ici.

## Validation de cette passe

`python -m unittest tests.test_shadow_boss_rules -v` : **14 tests réussis**,
dont trois utilisant le dump PAL local. Ils couvrent les sept groupes et
48 familles distinctes, légendaires, générations, seuils natifs, puissance
stricte, replis globaux déclarés, appariement complet, impossibilité expliquée,
reproductibilité, synchronisation de tous les alias et whitelist des octets.

Ces résultats valident les données produites et les invariants. Ils ne sont
pas des combats observés sous Dolphin et ne garantissent pas l’équilibrage
ressenti. La validation de l’intégration et de l’ISO appartient à la passe
principale v0.5, pas à ce sous-module isolé.
