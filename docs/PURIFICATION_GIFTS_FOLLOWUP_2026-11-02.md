# Cadeaux de purification : validation complémentaire du 2 novembre 2026

Les trois vérifications complémentaires sont terminées dans Dolphin :
sauvegarde/rechargement des deux cadeaux, conservation des scènes d’Adelbert
et affichage des cinq nouveaux messages dans les cinq langues PAL. Aucune
anomalie du patch n’a été constatée dans ce périmètre. Les préparations de test
et leurs limites sont décrites ci-dessous.

Ce suivi complète [la validation initiale](PURIFICATION_GIFTS_VALIDATION_2026-11-02.md).
Il utilise la même ISO PAL `GC6P01`, version 0.13.0, seed
`purification-rewards-1`, taux chromatique 25 % lié à la seed. Son SHA-256 est
`da8e0d6883231b9d1cb5578895ca469db600de4894a86c0d97c2c960a22121a7`.

| Vérification | État |
| --- | --- |
| Sauvegarde native, nouveau processus, chargement et absence de second cadeau | Validée dans ce parcours |
| Skrub, scènes de suivi et présence unique d’Adelbert après leur fin | Validée dans ce parcours français |
| Rendu des cinq messages en français, anglais, allemand, espagnol et italien | 25 affichages contrôlés visuellement dans Dolphin |

## Sauvegarde et absence de doublon après rechargement

Les deux cadeaux ont été obtenus par les conversations normales d’Adelbert.
Le jeu a appelé sa fonction native 217 avec les identifiants 5 et 6, puis les a
envoyés au PC, l’équipe étant pleine. Les enregistrements générés correspondent
au tirage attendu : Écrapince niveau 30 et Donphan niveau 45, tous deux ordinaires.
Ni la fonction native, ni son retour, ni les Pokémon reçus n’ont été substitués.

La sauvegarde a ensuite été effectuée depuis le PC, avec les confirmations
rendues par le jeu. Après fermeture du processus, la carte copiée contient les
compteurs `13,14,15`, contre `13,14,12` avant cette sauvegarde : le slot le plus
récent est passé de 14 à 15. Ses checksums sont valides et son chiffrement se
reconstitue exactement. Les reçus 2740 et 2737 valent 1. Chaque cadeau apparaît
une seule fois et ses 312 octets correspondent exactement à l’enregistrement
capturé pendant l’acquisition native.

Un nouveau processus Dolphin a chargé cette même carte par « Continuer » puis
confirmation, sans savestate. La lecture de ses 96 emplacements — six dans
l’équipe et 90 dans le PC — retrouve chacun des deux cadeaux une seule fois,
dans les mêmes cases du PC, toujours identique octet par octet. Les deux reçus
et les six conditions de scénario sont conservés.

Une nouvelle interaction normale avec Adelbert affiche ensuite le message
« cadeaux déjà reçus » (`0xF0004`). Le point d’observation de la fonction 217,
actif pendant cette interaction, ne constate aucun nouvel appel d’acquisition.
Ce test couvre donc la persistance sur carte et le refus d’une seconde remise
après un véritable redémarrage du jeu.

## Skrub et fin complète des scènes

La véritable introduction du sanctuaire a été jouée, avec le duel automatique 525
entre Adelbert et Skrub. Dans cette exécution, Adelbert perd ; le scénario lance
ensuite le combat joueur 198, gagné en jouant ses commandes. Aucun résultat de
combat, PV, équipe ou indicateur de progression n’a été écrit pour le gagner.
Le test ne démontre pas une défaite forcée d’Adelbert pour toutes les seeds.

Les conversations de la maison, la visite à Fernand, la tablette, le courrier
et les dernières directions vers le Mont Bataille ont ensuite exécuté leurs
véritables scripts. Les six conditions `3527,2582,1067,2860,3531,2875` sont
arrivées à 1 par ces scripts et par le gestionnaire natif du courrier.

Adelbert reste présent pendant les scènes qui l’utilisent. Après une vraie
sortie puis rentrée dans la maison, son acteur y est caché et inactif ; Oliphie
reste visible. Au chargement suivant du sanctuaire, un seul acteur d’Adelbert
est présent, près de la Relique Sacrée. Le déplacement du donneur attend donc
la fin des scènes dans ce parcours.

## Dialogues dans les cinq langues PAL

Les cinq messages ajoutés ont chacun été affichés dans Dolphin en français,
anglais, allemand, italien et espagnol, sur la même ISO de production.

| Message | Français | Anglais | Allemand | Italien | Espagnol |
| --- | --- | --- | --- | --- | --- |
| Proposition d’un cadeau | Validé | Validé | Validé | Validé | Validé |
| Confirmation de réception | Validé | Validé | Validé | Validé | Validé |
| Équipe et PC pleins | Validé | Validé | Validé | Validé | Validé |
| Seuils de 10 et 25 purifications | Validé | Validé | Validé | Validé | Validé |
| Deux cadeaux déjà reçus | Validé | Validé | Validé | Validé | Validé |

Chaque capture a été inspectée individuellement : texte complet, sauts de ligne,
accents, caractères particuliers et absence de débordement. Le message des
seuils tient sur trois lignes dans chaque langue ; les autres tiennent sur deux.

La langue est préparée uniquement dans l’octet de configuration de la copie
en mémoire. Une vraie sortie de la Relique vers la grotte, puis un retour,
laisse le moteur décharger l’ancienne banque et charger la nouvelle. La
variable globale de langue n’est jamais écrite directement. L’ordre observé
est français, anglais, allemand, italien, espagnol ; une dernière sortie
restaure le français et sa banque active avant fermeture.

Pour vérifier les textes sans remettre les cadeaux, le test arrête un véritable
appel de dialogue d’Adelbert dans la branche « déjà reçus ». Seul l’identifiant
du message est remplacé pour les quatre premiers textes ; le cinquième est
affiché sans substitution. Les reçus, l’inventaire, les conditions de scénario,
le résultat de réception et les scripts ne changent pas. C’est une vérification
du rendu des banques de traduction, pas une nouvelle acquisition ni un test
de PC plein dans chacune des langues. La logique de capacité dispose des
essais natifs distincts décrits dans la validation initiale.

Les 25 observations gardent les deux reçus à 1. Aucun appel d’acquisition 217
n’est observé pendant la session de rechargement. Une dernière lecture des
96 emplacements retrouve chaque cadeau exactement une fois, avec les mêmes
312 octets qu’avant les essais de langue. Ces essais ne couvrent pas cinq
démarrages indépendants ni la sélection automatique de langue au démarrage.

## Préparation du test et limites

Ce parcours part d’une sauvegarde de test préparée, pas d’une nouvelle partie :

- La copie source était déjà après Skrub. Treize indicateurs de cette séquence
  ont été remis à zéro dans une nouvelle carte :
  `1064,1065,1066,1067,1068,1070,3527,2582,2860,3531,2875,2810,3551`.
  Son contexte de chargement a été placé sur l’entrée native du sanctuaire
  `(39,37,0)`, avec checksums recalculés. Les sources sont restées intactes.
- Le courrier 0 était déjà reçu et lu dans cette ancienne partie. Son bit
  « déjà lu » a dû être remis à zéro sur la copie, car le jeu n’applique ses
  effets qu’à la première lecture non lue. La nouvelle ouverture du vrai P★AD
  a ensuite posé 3531 nativement. Ce n’était pas une écriture directe de 3531.
  Ce test ne valide pas une première livraison depuis une boîte de courrier vide.
- Les déplacements longs ont été raccourcis lors de vraies transitions de
  porte arrêtées dans le moteur. Le parcours du scénario utilise trois de ces
  raccourcis ; d’autres rejoignent le PC et le sanctuaire pour le contrôle de
  persistance. Les scènes, interactions et déplacements locaux restent ceux
  du jeu. Aucune coordonnée d’acteur n’a été injectée pour les franchir.
- Le compteur de 25 purifications a été préparé sur la copie QA. Les 25
  purifications n’ont pas été jouées. L’acquisition, les reçus, la sauvegarde
  et le rechargement ont ensuite utilisé les routines normales du jeu.

Ces préparations limitent la portée de l’essai : elles vérifient les scènes et
la persistance depuis des préconditions définies, sans remplacer une partie
complète commencée de zéro. Aucun contournement de ces préconditions n’a été
ajouté au patch de production.

Les originaux, cartes et profils personnels ne sont pas les destinations du
test. Les deux processus Dolphin sont fermés normalement, avec le code zéro.
Leurs moniteurs confirment que les fichiers protégés et le profil personnel
gardent leurs empreintes. Aucun changement de langue n’a été sauvegardé : la
carte QA finale est identique octet par octet à sa copie fermée après la
sauvegarde native des deux cadeaux, au SHA-256
`04b7238d6fe4e382581d6e3b582c5d7be0fd3e902ae8f7b741109255769b3f9c`.
La validation complémentaire n’a modifié ni le patch de production, ni l’ISO,
ni les exécutables distribués.

## Éléments de preuve privés

Les cartes, captures, journaux et identités des Pokémon restent sous
`build/purification-followup-2026-11-02/` et ne sont pas distribués avec l’outil.

| Preuve | Ce qu’elle établit |
| --- | --- |
| `STORY_RUNTIME_FOLLOWUP.md` et checkpoints de `persist-fr/` | Progression jouée, préparation déclarée, vraie rentrée maison et présence au sanctuaire |
| `native-research/closed-current-validation.json` | Carte après sauvegarde native : compteur 15, checksums, reçus et cadeaux uniques |
| `persist-fr/monitor.json` | Fin du premier processus et conservation des fichiers protégés |
| `persist-fr/monitor-reload.json` et `after-real-reload.json` | Nouveau processus, chargement normal, fermeture avec code zéro et fichiers protégés inchangés |
| `persist-fr/live-gifts-after-reload.json` | Recherche des deux CK 3 exacts parmi les 96 emplacements après chargement |
| `persist-fr/bridge-reload.jsonl`, notamment l’observation du message `0xF0004` | Conversation après rechargement et absence de nouvel appel 217 |
| Captures 17 à 21 de `persist-fr/evidence/` | Confirmations de sauvegarde, retour en jeu après chargement et refus de seconde remise |
| `persist-fr/translation-cases/` et captures `evidence/locale-<langue>-<0..4>.jpg` | 25 messages réellement affichés, langue active et substitution visuelle déclarée |
| `persist-fr/live-gifts-after-translations.json` et `final-runtime-after-translations.json` | Cadeaux toujours uniques, conditions conservées et français restauré |
| `visual-validation-final.json` | Empreintes des 25 captures, audit des mutations, carte QA inchangée et conservation finale |

Le rapport de carte fermée précède le nouveau processus : sa réserve initiale
sur le rechargement est levée par les observations runtime suivantes. Les
cartes de langue préparées hors ligne n’ont pas servi de preuve visuelle ;
les captures et observations de la session rechargée apportent cette preuve.
L’agrégateur contrôle les fichiers, empreintes et invariants ; l’appréciation
du rendu provient de l’inspection des captures, pas d’une assertion OCR.
