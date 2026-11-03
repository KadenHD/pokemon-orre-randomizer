# Historique

## 0.20.0

- Pokémon Orre Randomizer s’ouvre sur le choix du jeu. Colosseum donne accès au parcours existant et XD est indiqué comme à venir.
- Les distributions Windows utilisent `OrreRandomizer.exe` et le nom de dépôt `pokemon-orre-randomizer`. Le workflow GitHub prépare les ZIP vérifiés et leurs empreintes à chaque tag de version.

## 0.19.0

- L’aperçu affiche les starters, obscurs et cadeaux qui partagent une famille dans l’onglet Doublons, quand le tirage final en contient.
- Le menu Profils permet de reprendre la seed et les réglages depuis un rapport de création et de comparer la ROM sélectionnée à celle du rapport.

## 0.18.4

- La croix d’effacement est centrée dans les champs de recherche.

## 0.18.3

- Après un aperçu, la création réutilise les modifications calculées si les empreintes de la ROM, la seed et les réglages correspondent. La ROM produite est toujours vérifiée intégralement.

## 0.18.2

- La Poké Ball de sélection est alignée avec les libellés des étapes et des préréglages, avec un espace supplémentaire avant le texte.

## 0.18.1

- La flèche du menu Profils est alignée avec son libellé.

## 0.18.0

- Les préréglages randomisés cherchent des familles d’évolution différentes entre starters, obscurs et cadeaux. Les exclusions, choix manuels et contraintes strictes gardent la priorité. Le rapport de création indique les doublons restants.
- Les anciens profils conservent leur tirage. La nouvelle préférence est désactivée à leur import.

## 0.17.4

- L’aperçu des starters, des obscurs et des cadeaux affiche les noms avec une majuscule initiale. Une petite étoile rouge en exposant indique les Pokémon chromatiques.

## 0.17.3

- Les noms des Pokémon commencent par une majuscule dans les fiches. L’étoile chromatique apparaît en exposant.

## 0.17.2

- Une étoile rouge après le nom signale les Pokémon chromatiques dans leur fiche.

## 0.17.1

- L’onglet Évolutions montre les portraits et les conditions de chaque étape, y compris pour les familles à plusieurs branches. Les portraits proviennent de la ROM et reprennent le statut chromatique lorsqu’il est connu.

## 0.17.0

- Les deux préréglages randomisés activent les chromatiques à 5 % par rencontre, avec un résultat fixé par la seed. Leurs descriptions s’affichent directement sous le mode choisi.
- L’aperçu montre les rencontres d’origine et marque d’un « ? » les espèces qui restent à tirer. Les portraits et noms défilent pendant le calcul, puis la liste affiche le tirage final. La recherche par nom ou numéro reste disponible.
- Les fiches adoptent les cadres du jeu, avec un portrait, des barres de statistiques et des onglets pour le résumé, les capacités et les évolutions.
- Le menu Profils rejoint la langue et les commandes audio. L’étape Créer regroupe le récapitulatif sous Réglages appliqués et affiche un champ DolphinTool pour une sortie RVZ. Le chemin est partagé avec l’étape ROM.
- Les profils 0.16.0 et 0.16.1 conservent leurs réglages et leurs tirages à l’import.

## 0.16.1

- Un clic sur une ligne des onglets Obscurs ou Cadeaux ouvre la fiche du Pokémon obtenu. Au clavier, la touche Entrée ouvre la ligne sélectionnée.
- Le filtre distingue « Tous les Pokémon », « Chromatiques uniquement » et « Non chromatiques uniquement ». Il apparaît lorsque l’aperçu connaît le statut chromatique.
- L’aperçu rappelle les taux d’origine pour les starters et les obscurs capturés. Les profils v0.16.0 restent importables.

## 0.16.0

- Recherche des réglages en mode Avancé dans les libellés, aides, catégories et choix traduits, avec normalisation des accents et synonymes usuels. Un résultat rejoint le champ sans modifier sa valeur.
- Remise à zéro de la catégorie courante vers les valeurs du préréglage **Pokémon + capacités**, sans modifier la seed, les chemins ni les autres catégories.
- Récapitulatif des règles effectives à l’étape Créer, avec choix manuels, taux et facteurs actifs, sans révéler les tirages aléatoires. Le volet détaillé défile à l’ouverture pour rendre ses premières lignes visibles.
- Message d’annulation raccourci ; documentation de contribution mise à jour pour les 82 paramètres et les six langues.
- Import strict des profils v0.15 : mêmes 82 champs et mêmes valeurs, sans migration de tirage. Le moteur `details-and-progression-v15` et le schéma de profil 1 restent inchangés.

Les [notes v0.16](docs/DESKTOP_V16.md) consignent 449 tests, la régression binaire
v0.15 dans les trois régions et 336 états de diagnostic des deux exécutables.
Les 15 étapes Dolphin réussies sur Europe, USA et Japon couvrent la marche
avec plancher à zéro, la libération unique de réserve, la purification finale,
l’EXP ×2 normale avec montée de niveau et l’EXP ×2 mise en réserve. Les trois
sessions se ferment normalement. Les contrôles d’empreinte confirment
l’intégrité des ROM originales et des sauvegardes personnelles.

## 0.15.0

- Fiches des Pokémon dans l’aperçu : propriétés finales de la ROM, capacités connues, apprentissages, CT et chaîne d’évolution, dans les six langues. Les talents affichés sont les possibilités de l’espèce ; le talent individuel reste attribué par le jeu.
- Choix manuel du premier et du second starter, par nom ou numéro national ; un seul peut aussi être fixé. Le choix remplace les filtres de stade, de famille à trois stades et de puissance individuelle, tout en conservant les exclusions, générations, légendaires et règles du duo.
- Difficulté progressive facultative : trois multiplicateurs pour les niveaux d’origine 1–35, 36–50 et 51–100, appliqués avant les bonus des boss et le contrôle des formes finales.
- EXP des combats réglable de ×0,25 à ×5 et diminution de la jauge obscure de ×1 à ×10 ; ×1 par défaut. Patchs natifs qualifiés et composés séparément sur les trois régions. La purification finale à la Relique reste nécessaire.
- Journal HTML local créé à côté de la ROM, avec sections repliées pour les spoilers. Langue de l’interface, ou `--journal-language` en CLI ; aucun chemin source/destination ni ressource externe dans ce journal.
- Vérification des réglages avant création via le moteur de l’aperçu, avec erreurs récupérables sans publier de ROM.
- Réutilisation d’une décompression RVZ temporaire par fenêtre pour les aperçus successifs, avec empreintes revalidées et nettoyage à la fermeture, au changement de source/outil ou après erreur.
- Annulation coopérative pendant la recompression LZSS Rust et Python ; sortie identique sans annulation. Ancien ABI du codec conservé.
- 82 paramètres, dont 57 booléens, dans les quinze catégories. Import strict des profils v0.14 avec les nouveaux réglages neutres ; comparaison complète des patchs avec le moteur v0.14 archivé réussie dans les trois régions.
- Documentation corrigée : les préréglages randomisés proposent des starters de base à trois stades par défaut ; l’annulation n’attend plus la fin d’un membre LZSS.

Moteur : `details-and-progression-v15`. Les contrôles des données réelles couvrent
18 configurations et 36 constructions répétées. Dans Dolphin Europe, EXP ×2
produit un gain réel de 1 346 au lieu de 673 dans la réserve d’un obscur ; le
refus natif d’un autre obscur encore trop fermé est conservé. Jauge ×3 confirme
6 650 → 6 500 et 800 → 575 sur deux diminutions de combat. Originaux et profil
Dolphin personnel restent inchangés après fermeture normale. Ces nouveaux
parcours QOL n’ont pas été joués sur USA/Japon ; montée de niveau, purification
finale, marche et plancher de jauge à zéro restent sans observation ici.
Ces contrôles ne certifient pas une partie complète.

[Fonctionnement, validation et limites v0.15](docs/DESKTOP_V15.md).

## 0.14.0

- Prise en charge des ROM Europe `GC6P01`, USA `GC6E01` et Japon `GC6J01`, révision 0, au format ISO ou RVZ. Identification stricte par en-tête et SHA-256 complet ; les sources restent intactes.
- Tables de dresseurs, obscurs, Pokémon, objets, boutiques et CT adaptées à chaque région. Noms natifs anglais USA et japonais conservés ; les noms de l’aperçu restent disponibles dans les six langues de l’outil.
- Patchs natifs des starters, capacités des cadeaux, niveaux et chromatiques adaptés aux trois exécutables, avec leurs propres adresses et allocations mémoire.
- Cadeaux d’Adelbert disponibles dans les trois versions, avec dialogues japonais natifs en plus des textes PAL et USA. Les conditions de scénario et de réception sont conservées.
- Profils v0.13 importés sans changer les réglages, y compris les cadeaux et les chromatiques liés à la seed. Nouveaux profils utilisables sur les trois versions ; le rapport de création identifie la ROM exacte.
- Régression PAL : l’ISO du précédent essai v0.13 est reproduite à l’identique. Matrice technique de 54 configurations sur les trois régions, avec 108 constructions répétées et neuf aperçus comparés aux octets finaux.
- Validation Dolphin des cadeaux USA et Japon : deux dons natifs conformes à l’aperçu, cinq dialogues lisibles, sauvegarde par le jeu, rechargement sans état instantané et refus d’un second don. ROM originales et profil Dolphin personnel inchangés.

Moteur : `regional-purification-gifts-v14`. Ces contrôles techniques ne certifient
pas trois parties complètes du scénario.

[Validation régionale et limites](docs/REGIONAL_COMPATIBILITY_2026-11-03.md).
[Suivi des cadeaux USA et Japon](docs/REGIONAL_GIFTS_DOLPHIN_2026-11-03.md).

## 0.13.0

- Cadeaux événementiels accessibles auprès d’Adelbert près de la Relique Sacrée : cadeau de Pikachu après 10 purifications au niveau 30, cadeau de Celebi après 25 purifications au niveau 45. Seuils et niveaux configurables séparément ; chaque cadeau est limité à une réception par sauvegarde.
- Accès activé dans les deux préréglages randomisés et désactivé dans Copie à l’identique. Il devient disponible après toutes les scènes d’introduction à la purification, y compris le suivi dans la maison après Skrub, même avec un seuil de zéro. L’apparition d’Adelbert reste exclusive entre sa maison et le sanctuaire.
- Espèces et statuts chromatiques des deux cadeaux suivent les réglages et la seed. L’aperçu indique le donneur localisé et le nombre de purifications requis ; les quatre valeurs numériques sont désactivées lorsque l’accès l’est.
- Dialogues ajoutés dans les cinq langues de la ROM européenne, selon la langue du jeu. Réglages, aides et aperçus dans les six langues de l’interface, indépendamment de cette sélection.
- Profils 0.5 à 0.12 importés avec l’accès désactivé pour conserver leurs tirages et conditions précédentes. Les profils 0.11 et 0.12 conservent le choix de statuts chromatiques liés à la seed.
- 74 paramètres, dont 56 booléens, dans les quinze catégories existantes. Moteur : `purification-gifts-v13`.

Validation et limites de l’essai :
[`docs/PURIFICATION_GIFTS_VALIDATION_2026-11-02.md`](docs/PURIFICATION_GIFTS_VALIDATION_2026-11-02.md).

## 0.12.0

- Réglages séparés en Configuration et Aperçu des Pokémon, avec seed commune et menu Profils toujours accessibles.
- Aperçu organisé en trois onglets : deux starters, 48 obscurs et quatre cadeaux. Recherche par nom ou numéro, filtre chromatique lorsque le statut est connu et compteur des lignes visibles.
- Listes agrandies sur toute la hauteur disponible ; fin des zones de défilement imbriquées dans l’étape Réglages. Barres de défilement plus larges et contrastées.
- Catégories avancées dans une barre latérale quand l’espace le permet, ou dans un sélecteur compact. Largeur de lecture limitée à 1 200 px et détails des modes repliés par défaut.
- Molette sur un champ numérique ou une liste sans focus transmise au formulaire pour éviter les changements involontaires.
- Six langues conservées, avec navigation entre vues sans perte de seed, de règles ni d’aperçu valide. Profils 0.11 importés sans changer les tirages ; moteur `seeded-shiny-status-v12` inchangé.
- Références Qt des catégories et de la barre de défilement conservées explicitement pour fiabiliser les réouvertures successives de la fenêtre.

## 0.11.0

- Option « Lier les chromatiques à la seed », cochée par défaut lorsque la personnalisation des shinies est activée. La seed fixe le statut de chaque starter, cadeau, obscur et emplacement de dresseur ; le taux reste une probabilité sans quota imposé.
- Aperçu exact des statuts pour une nouvelle partie, même en dessous de 100 %, avec portraits normaux/chromatiques authentiques et mentions textuelles dans les six langues. Deux rencontres de la même espèce peuvent avoir des statuts différents.
- Annonce du mode lié à la seed avant le calcul ; case et taux dépendants de la personnalisation. Modifier la liaison invalide l’aperçu précédent.
- Nature, genre, PID complet, IV et autres tirages du jeu restent natifs. Les Pokémon déjà générés conservent leur statut ; les anciens PID obscurs restent réutilisés.
- Décocher la liaison conserve le tirage en jeu. Les profils 0.5 à 0.10.1 sont migrés avec cette option désactivée ; compatibilité binaire du mode v11 vérifiée à 0, 25 et 100 %, avec et sans correctif de capacités des cadeaux.
- 69 paramètres, dont 55 booléens, dans les quinze catégories existantes. Composition C et parcours de l’interface conservés.

Moteur : `seeded-shiny-status-v12`. Les vérifications automatisées ne constituent
pas une validation Dolphin ni une partie complète du scénario.
La validation CPU contrôlée sous Dolphin est décrite dans
[`docs/SEEDED_SHINIES_VALIDATION_2026-11-02.md`](docs/SEEDED_SHINIES_VALIDATION_2026-11-02.md).

## 0.10.1

- Aperçu dépliable des 48 Pokémon obscurs et des quatre cadeaux identifiés, avec leurs portraits, les espèces d’origine et les noms dans les six langues.
- À 100 % avec la personnalisation activée, l’interface annonce les starters chromatiques garantis avant le calcul. Les taux intermédiaires restent tirés en jeu.
- L’aperçu utilise les résultats finaux du moteur, sans créer de ROM. Les cadeaux événementiels sont signalés et ne sont pas débloqués par cet aperçu.
- Les profils 0.10.0 et les tirages du moteur restent compatibles.
- Boutons des sélecteurs d’exclusions conservés explicitement pour éviter une anomalie de wrappers Qt lors d’ouvertures successives. Entrée dans la recherche ne valide pas la fenêtre.

## 0.10.0

- Catégorie Chromatiques : case « Personnaliser les shinies » et taux de 0 à 100 %, avec quatre décimales. Désactivée par défaut : comportement d’origine. 0 % : aucun ; 100 % : tous les nouveaux Pokémon concernés.
- Tirage réel à la génération pour les dresseurs, obscurs, deux starters et quatre cadeaux/événements identifiés. Le générateur natif conserve ses contraintes de nature et de sexe et le test shiny de troisième génération.
- Alignement du propriétaire des obscurs pour conserver le statut à la capture et à la purification. Les PID déjà enregistrés sont réutilisés ; aucun nouveau tirage sur une ancienne rencontre.
- À 100 %, l’aperçu montre les portraits chromatiques présents dans la ROM. Aux taux intermédiaires, il précise que le statut sera tiré en jeu, indépendamment de la seed du randomizer.
- Réglages, explications et aperçus dans les six langues. Profils 0.5 à 0.9 importés avec l’option désactivée, sans changer leurs octets de jeu.

Moteur : `native-shiny-generation-v11`.

## 0.9.0

- Exclusions par espèce et par type d’origine : listes avec recherche, numéros nationaux et noms dans les six langues ; cochée signifie exclue. Tous les remplacements appliquent ces filtres, y compris les starters, cadeaux et 48 obscurs.
- Thèmes des équipes non obscures : un type commun au hasard, ou un type d’origine partagé lorsqu’il est possible. Les équipes partageant des enregistrements sont traitées ensemble ; les obscurs gardent leurs espèces et leurs réapparitions.
- Formes finales des adversaires non obscurs à partir d’un niveau choisi. Le niveau après bonus des boss est utilisé. Sans randomisation des espèces, évolution dans la famille d’origine ; sinon, tirage parmi les formes finales autorisées.
- Combinaison des thèmes, exclusions, formes finales et diversité des boss sans relâcher les exclusions. Ajustement des capacités uniquement lorsqu’il est activé, avec conservation des marqueurs spéciaux.
- Nouveaux réglages désactivés par défaut ; import des profils 0.5 à 0.8 avec vérification de leur empreinte et conservation des tirages. Sauvegarde des exclusions dans les profils ; arguments CLI correspondants.

Moteur : `trainer-policies-and-exclusions-v10`. Les préréglages 0.8 restent identiques.

## 0.8.0

- Starters : choix du stade (tous, base, première évolution, finale) et filtre indépendant pour les familles à trois stades. Les deux configurations randomisées utilisent par défaut les formes de base de ces familles.
- Le nombre de stades vient des chaînes d’évolution de Colosseum, avec prise en compte des bébés et des embranchements. Un Pokémon conservé n’est pas contraint par ces filtres.
- Avec le filtre à trois stades et l’équilibrage, une base est comparée à Évoli plutôt qu’aux statistiques de Noctali ou Mentali. Les contraintes de puissance entre les deux starters, de types et de familles restent appliquées.
- Import des profils 0.5 à 0.7 après vérification de leur empreinte ; ancien choix de formes de base converti, nouveau filtre désactivé, tirages conservés. L’ancien argument CLI `--starter-base-forms` reste accepté.
- Paramètres, aides et messages disponibles dans les six langues. Le mode Copie à l’identique reste inchangé.

Moteur : `starter-evolution-stages-v9`. Les nouveaux réglages par défaut changent
les starters. Les anciens profils conservent les mêmes octets de jeu.

## 0.7.0

- Aperçu des starters : chargement animé, annulation visible et état « Aperçu à jour » à la place du bouton après calcul. Actualisation après changement de seed, de ROM ou de réglages ; aucun recalcul pour une configuration déjà affichée. États traduits dans les six langues.

- Interface disponible dans les six langues originales de Colosseum : français, anglais, allemand, espagnol, italien et japonais, indépendamment de la ROM chargée. Détection du système, choix manuel mémorisé et traductions des descriptions, erreurs et dialogues.
- Aperçu des starters nommé dans les six langues. Noms des pierres dans la langue choisie dans le jeu, indépendamment de celle de l’outil.

- Icône d’application Éclipse (choix B), intégrée à l’exécutable et aux fenêtres Qt, disponible dans les deux éditions sans ROM.

- Titre d’en-tête raccourci en RANDOMIZER à côté du logo Pokémon Colosseum.

- Assistant en trois étapes, modes Simple et Avancé, interface française et anglaise.
- Interface japonaise complète, détection du système, choix mémorisé et polices adaptées aux caractères japonais.
- Pictogrammes cohérents pour les quatorze catégories de réglages, sans portraits de Pokémon utilisés comme symboles arbitraires.
- Pack local autonome : images, portraits, curseur, trois sons et thème du titre.
- Lecture musicale indépendante des sons de menu, compatible avec les chemins longs.
- Musique activée par défaut comme les sons, avec conservation du choix de la désactiver.
- Choix du mode Simple renommés et expliqués dans les six langues : Pokémon + capacités, Pokémon seuls, Copie à l’identique ; aides communes et réglages personnalisés explicités, sans changer les options appliquées.
- Aperçu des starters pour la seed et les options courantes, via le moteur de création : noms FR/EN/DE/ES/IT/JA, portraits lus dans la ROM et niveaux ; ISO/RVZ, calcul annulable, rejet des résultats périmés et aucune ROM publiée par l’aperçu.
- Espacement de onze noms de pierres en conservant les cinq langues natives.
- Import des anciens profils avec conservation exacte de leurs tirages.
- Démarrage préservé en l’absence du pack ou de métadonnées valides.
- Champ de conversion affiché uniquement pour une source RVZ ; demande de DolphinTool à la création d’une sortie RVZ depuis une ISO si nécessaire.
- Format de sortie proposé identique à celui de la ROM d’entrée, avec changement manuel conservé lors des retours entre étapes.
- Distribution publique séparée, sans images ni sons du jeu ; pack local conservé.
- Diagnostic hors ligne de l’exécutable et contrôle après extraction avec un PATH minimal.
- Matrice de seeds et réglages, mesures PCM et vérification des archives.

Le moteur reste `native-text-and-boss-rules-v8`. Les corrections de distribution
et de démarrage ne changent pas les données produites pour une même configuration.
