# Cadeaux d’Adelbert USA et Japon — validation Dolphin de la v0.14.0

Les deux cadeaux ont été obtenus dans les versions USA et japonaise, puis
retrouvés après une sauvegarde dans le jeu et un redémarrage complet de Dolphin.
Adelbert refuse ensuite de les donner une seconde fois. Ce suivi complète la
[validation régionale](REGIONAL_COMPATIBILITY_2026-11-03.md) et les
[essais PAL précédents](PURIFICATION_GIFTS_FOLLOWUP_2026-11-02.md).

## Résultats observés

Les essais utilisent les ISO produites par le moteur v0.14.0, avec la seed
`regional-validation-1`, le préréglage recommandé et un taux chromatique de
25 % lié à la seed. Les seuils restent à 10 et 25 purifications, les niveaux
à 30 et 45. Les deux cadeaux tirés sont ordinaires dans cette configuration.

| Contrôle | USA, `GC6E01` | Japon, `GC6J01` |
| --- | --- | --- |
| Cadeau de Pikachu | Zigzaton, niveau 30 | Zigzaton, niveau 30 |
| Cadeau de Celebi | Vacilys, niveau 45 | Vacilys, niveau 45 |
| Espèce, niveau, expérience, quatre capacités et statut chromatique | Conformes à l’aperçu | Conformes à l’aperçu |
| Cinq dialogues dans le moteur du jeu | Anglais, lisibles | Japonais, caractères et retours à la ligne corrects |
| Sauvegarde par le PC du jeu | Réussie | Réussie |
| Chargement par « Continuer » dans un nouveau processus | Réussi | Réussi |
| Nouvelle conversation avec Adelbert après chargement | Aucun nouveau cadeau | Aucun nouveau cadeau |
| ROM originales et profil Dolphin personnel | Inchangés | Inchangés |

Les deux dons passent par le script et les routines natifs du jeu. L’équipe
étant pleine, chaque Pokémon est ajouté au PC. Les enregistrements complets de
312 octets sont capturés à leur insertion, sans substitution de Pokémon,
de résultat d’appel ni d’indicateur de réception.

Après acquisition, après chargement et après la nouvelle conversation, les
96 emplacements de l’équipe et du PC sont relus : chaque cadeau figure une
seule fois, avec les mêmes 312 octets. Les deux indicateurs persistants restent
actifs. Le point d’observation de la routine de don reste installé pendant le
chargement et la conversation finale ; il n’est jamais atteint dans ces étapes.

Les cartes fermées passent les contrôles de la carte GameCube, du commentaire
et de la bannière natifs, des trois emplacements de sauvegarde et de leur
chiffrement. Le dernier emplacement passe du compteur 13 à 16 ; les deux anciens
restent aux compteurs 14 et 15. Dans chaque région, la carte après le dernier
redémarrage est identique à celle écrite par la sauvegarde native.

## Préparation des essais et limites

Des cartes de test ont été préparées à partir d’une copie fermée de la carte QA
PAL, avec 25 purifications et les six conditions de scénario déjà remplies.
Les anciens cadeaux de test et leurs indicateurs ont été retirés avant les dons.
L’identifiant régional, la langue et les métadonnées de carte sont adaptés à
chaque version. Les déplacements de test utilisent des raccourcis de porte
déclarés pour rejoindre la Relique et le PC. Ces essais ne rejouent donc pas les
25 purifications ni toute la progression du scénario.

L’essai USA utilise un état instantané intermédiaire pour reprendre la navigation
après les acquisitions réelles. Le contrôle final de persistance, dans les deux
régions, se fait dans un profil neuf contenant uniquement la carte sauvegardée
et les réglages nécessaires : aucun état instantané ni SRAM n’y est importé.

Les messages « équipe et PC pleins » et de rappel des seuils ont été vérifiés
visuellement en sélectionnant leur identifiant de texte lors d’une conversation
après réception des deux cadeaux. Cela valide leur rendu, sans prétendre avoir
rejoué ces deux situations de capacité ou de progression dans chaque région.
Les messages d’offre, de succès et de cadeaux déjà reçus sont observés sur leurs
branches réelles.

Une anomalie de préparation concernait le checksum du commentaire et de la
bannière de la première carte QA américaine. Le jeu l’a corrigé au chargement ;
les données chiffrées de sauvegarde sont restées identiques à cette étape.
La fabrication des cartes QA a ensuite été corrigée et la carte japonaise a été
contrôlée avant son premier démarrage. Cette correction concerne les fichiers
de test privés, sans changement du moteur ni des ISO de la v0.14.0.

La copie privée de Dolphin 2609a et son correctif d’entrée hôte restent ceux du
harnais précédent. Un premier lancement USA a bloqué avant le démarrage du jeu ;
il a été arrêté, avec conservation des sources vérifiée. Les cinq sessions
retenues se ferment normalement avec un code nul. Aucune installation Dolphin,
ROM, carte mémoire ou preuve contenant les données du jeu n’est distribuée.

Une partie complète, une console physique et un second PC Windows restent hors
de ce périmètre. Les démarrages des trois régions, la matrice de configurations
et la création ISO/RVZ sont couverts par le rapport régional précédent.

## Traçabilité

Les preuves privées sont conservées dans `build/regional-gifts-2026-11-03/` :
contrats natifs et journaux d’observation, captures des dialogues, enregistrements
des dons, cartes de test et contrôles après fermeture. Chaque région possède
un fichier `runtime/<région>/completed-validation.json` qui vérifie les dons,
les sauvegardes, le rechargement, les captures et la conservation des originaux.
Le bilan commun et les empreintes finales sont dans `completed-validation.json`.

Les rapports de surveillance comparent tous les fichiers du profil Dolphin
personnel et les trois RVZ originales avant et après chaque session. Les
exécutables de l’application restent identiques ; seuls les documents et les
archives qui les accompagnent sont actualisés pour intégrer ce suivi.
