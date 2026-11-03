# Cadeaux de purification — 2 novembre 2026

La [validation complémentaire](PURIFICATION_GIFTS_FOLLOWUP_2026-11-02.md)
termine les essais de sauvegarde/rechargement, de conservation des scènes et
de rendu des dialogues dans les cinq langues PAL. Le présent document conserve
le périmètre et les limites de la première session.

La version 0.13.0 rend les deux cadeaux événementiels accessibles auprès
d’Adelbert, à la Relique Sacrée. Par défaut, le cadeau de Pikachu demande
10 purifications au niveau 30 et celui de Celebi 25 au niveau 45. Les espèces
et les statuts chromatiques suivent le tirage du randomizer. Les quatre valeurs
numériques se règlent séparément dans « Starters et cadeaux ».

## Progression et conservation du scénario

L’accès attend les six indicateurs persistants `3527, 2582, 1067, 2860, 3531,
2875`. Ils couvrent la défaite face à Skrub et toutes les scènes de suivi dans
la maison, jusqu’à la dernière indication vers le Mont Bataille. Un seuil de
zéro ne contourne pas cette condition.

Le patch réutilise l’acteur Adelbert déjà présent dans le sanctuaire. Après la
séquence complète, il y devient visible et interactif, tandis que son acteur
habituel dans la maison est masqué. Avant cela, les scènes et conversations
d’origine restent disponibles. Les autres acteurs et le déroulement des scènes
ne sont pas réécrits. Les tests couvrent les 64 combinaisons de ces six indicateurs.

Les 48 indicateurs natifs de purification sont additionnés. Les cadeaux utilisent
la fonction native 217 avec les identifiants 5 et 6, ainsi que les indicateurs
de réception persistants 2740 et 2737. Une interaction remet au plus un cadeau.
La réception est marquée seulement après un succès : emplacement 0 à 5 dans
l’équipe, ou retour -1 pour le PC. Le retour -2, équipe et PC pleins, laisse
le cadeau disponible pour une autre visite.

## Langues et compatibilité

Cinq nouveaux textes sont ajoutés dans chacune des banques française, anglaise,
allemande, espagnole et italienne du sanctuaire. Le jeu choisit sa propre banque ;
la langue de l’interface du randomizer est indépendante. Les anciennes allocations
de texte, leurs alias et leurs contrôles natifs sont conservés octet par octet.

L’option est active dans les deux préréglages randomisés et inactive dans
« Copie à l’identique ». Les profils 0.5 à 0.12 l’importent désactivée après
validation de leur signature d’origine. L’ISO du précédent tirage v0.11 est
reproduite exactement avec cette option désactivée, au SHA-256
`e8696b3c7fbb235ed8535e32e8bd9ea0e1309a33dfd69bf5e563f99859031372`.

## Vérifications

La suite source exécute 365 tests, dont 363 réussis et deux ignorés. Le modèle
de remise couvre 785 cas, avec seuils, indicateurs de réception, progression et
capacité. Les tests d’intégration vérifient les archives originales strictement
identifiées, les modifications autorisées et la conservation des autres membres.
Les niveaux de génération et de rencontre sont modifiés ensemble et les capacités
de départ utilisent le niveau final. Vingt-quatre rendus Qt couvrent les cadeaux
et réglages dans les six langues de l’outil, à deux tailles de fenêtre.

Un essai CPU distinct dans Dolphin exécute 19 cas avec le CMS exact de l’ISO et
l’interpréteur natif. Les 19 réussissent : chaque indicateur de progression
manquant bloque la remise, les seuils sont respectés, une équipe pleine envoie
le cadeau au PC, et une équipe avec les 90 cases du PC pleines produit le retour
-2 sans valider la réception. Trois conversations successives donnent le premier
cadeau dans l’emplacement 0, le second dans l’emplacement 1, puis aucun cadeau.
Le contexte joueur synthétique est initialisé par le jeu et les CK3 passent son
validateur. Seules les fonctions d’affichage et de mouvement sont interceptées
dans ce harnais CPU ; les fonctions de génération, d’acquisition et d’écriture
des indicateurs restent natives. Cette couverture de logique est distincte de
l’interaction rendue décrite ci-dessous.

L’ISO privée `rewards-seeded-25.iso`, seed `purification-rewards-1`, est reconstruite
et vérifiée intégralement, au SHA-256
`da8e0d6883231b9d1cb5578895ca469db600de4894a86c0d97c2c960a22121a7`.
Le taux chromatique est de 25 %, avec statuts liés à la seed.

Dans Dolphin, une copie de sauvegarde a chargé le véritable sanctuaire et son
script de production. Adelbert apparaît près de la Relique. L’interaction native
affiche les seuils, propose les cadeaux, confirme leur réception puis refuse
de les redonner. Les compteurs de purification sont préparés en RAM dans cette
copie de travail ; 25 purifications n’ont pas été jouées pour cet essai.

| Cadeau | Résultat prévu et observé | Destination native |
| --- | --- | --- |
| Pikachu | Écrapince, niveau 30, ordinaire | PC, retour -1 |
| Celebi | Donphan, niveau 45, ordinaire | PC, retour -1 |

Des points d’observation lisent les deux CK3 de 312 octets à l’entrée de la vraie
routine d’ajout à l’équipe ou au PC. Ils ne remplacent ni génération ni acquisition.
Espèce, niveau, niveau de rencontre et statut chromatique correspondent à l’aperçu.
Les deux indicateurs de réception passent de zéro à un. Les indicateurs natifs de
mouvement confirment que les commandes sont libérées après la conversation.

Le processus Dolphin se ferme normalement avec le code zéro. Son moniteur confirme
les empreintes inchangées des originaux protégés et du profil Dolphin personnel.
Les captures, journaux et enregistrements restent privés dans
`build/purification-rewards-2026-11-02/` et ne sont pas distribués.

Cette vérification ne constitue pas une partie complète du scénario. Le masquage
dans la maison et les six conditions de progression ont une couverture statique ;
le cycle sauvegarde/rechargement de ces nouveaux cadeaux n’a pas été joué dans
cette session. Les essais de repositionnement après dialogue ont rencontré un
retour des caches de transformation du personnage ; aucun contournement n’a été
ajouté au patch de production pour cette préparation de test.
