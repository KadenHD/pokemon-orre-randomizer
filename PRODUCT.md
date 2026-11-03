# Pokémon Orre Randomizer

<!-- impeccable:product-schema 1 -->

## Platform

Desktop. Application Python/Qt native, Windows en premier ; le moteur ne dépend pas de Windows.
Le catalogue de plateformes du skill ne couvre pas Qt desktop : les conventions du système
et les contrôles Qt gouvernent cette surface, sans transposer une page web dans une fenêtre.

## Users

Les joueurs qui possèdent une image vierge de Pokémon Colosseum et veulent créer leur propre
partie randomisée, sans extraire le jeu ni utiliser des commandes.

## Product Purpose

Choisir un jeu à l’accueil, puis une ISO ou RVZ, une seed, les règles et une destination.
Produire une nouvelle image vérifiée avec son rapport de reproduction. Colosseum est
disponible. XD est prévu.

## Capabilities and Constraints

- ROM GC6P01 Europe, GC6E01 USA et GC6J01 Japon, révision 0, chacune identifiée par empreinte complète. Formats ISO et RVZ.
- Pokémon des dresseurs, starters et dons identifiés ; familles distinctes entre starters, obscurs et dons lorsque les règles le permettent, et évolutions accessibles.
- 83 paramètres, dont 58 booléens, dans quinze catégories ; trois points de départ : Pokémon + capacités, Pokémon seuls, Copie à l’identique.
- Starters par défaut en forme de base d’une famille à trois stades ; choix avancé du stade et filtre indépendant. Profils 0.5 à 0.8 migrés sans changer leurs tirages.
- Choix manuel de zéro, un ou deux starters par nom ou numéro national du Pokédex, dans une liste recherchable. Le choix manuel prime sur le stade, la famille à trois stades et la puissance individuelle, mais respecte les exclusions, générations, légendaires et contraintes du duo. Un remplacement désactivé conserve le starter d’origine et ignore ce choix.
- Exclusions explicites par espèce et type d’origine, avec sélection recherchable et noms dans les six langues ; s’appliquent à tous les remplacements.
- Thèmes des équipes non obscures et formes finales à partir d’un niveau choisi ; options désactivées par défaut, obscurs conservés. Le niveau après bonus des boss est utilisé et les équipes partageant des enregistrements sont traitées ensemble.
- Étape Réglages divisée en Configuration et Aperçu des Pokémon, avec seed commune et menu Profils dans l’en-tête. Simple et Avancé conservent les mêmes options ; les catégories avancées passent d’une colonne à un sélecteur quand l’espace manque. Une seule zone de contenu défile dans la vue active, avec navigation persistante et protection contre les changements de valeurs involontaires à la molette.
- Recherche des réglages en Avancé sur les libellés, aides, catégories et choix dans la langue courante, sans accents et avec synonymes usuels. Le choix d’un résultat rejoint le champ et son focus sans modifier les options.
- Remise à zéro de la catégorie courante uniquement, vers la référence nommée **Pokémon + capacités** (préréglage de bureau). Seed, chemins, autres catégories et profils importés restent distincts de cette référence.
- Récapitulatif de création fondé sur les règles effectives : choix manuels, contraintes, taux et facteurs réellement actifs ; les valeurs mémorisées mais désactivées ne sont pas annoncées comme appliquées. Aucun tirage aléatoire n’est révélé dans ce résumé.
- Aperçu des deux starters, des 48 obscurs et des quatre dons par le moteur de création : noms FR/EN/DE/ES/IT/JA, niveaux disponibles et portraits de la ROM, sans publier d’ISO ; calcul explicite, chargement animé et annulable, résultat partagé entre trois onglets, état « Aperçu à jour », actualisation après changement de ROM, de seed ou d’options. Les listes comparent les noms d’origine aux remplacements, avec recherche et compteur. Un « ? » précède le calcul des espèces inconnues et une roulette visuelle accompagne le calcul. Les cadeaux événementiels restent soumis à leurs conditions d’obtention.
- Fiches accessibles depuis les starters et rencontres de l’aperçu : types, talents possibles, statistiques, capacités connues, apprentissages, CT et chaîne d’évolution complète d’après les octets finaux de la ROM. Texte et noms dans les six langues, sans modifier la langue du jeu ni annoncer le talent individuel comme déterminé.
- Cache de session pour l’aperçu RVZ : une seule ISO décompressée temporaire par fenêtre, réutilisée après contrôle des empreintes source/ISO/outil. Invalidation au changement de source/outil, après erreur et à la fermeture ; aucun cache de jeu persistant.
- Journal HTML produit à côté de chaque ROM, sections repliées pour les spoilers : starters, obscurs, cadeaux, dresseurs, évolutions et CT. Langue de l’interface ou choix CLI parmi les six langues, français par défaut en CLI. Lecture hors ligne sans script ou ressource externe ; les chemins source/destination du rapport technique ne sont pas repris. Aucun des trois fichiers de sortie existants n’est remplacé.
- Profils JSON partageables sans ROM ni chemins personnels, importés avec validation de version et d’empreinte. La v0.13.0 importe les profils antérieurs avec l’accès aux cadeaux événementiels désactivé pour préserver leurs données ; les profils 0.11 et 0.12 conservent aussi la liaison des chromatiques à la seed.
- Cadeaux événementiels accessibles auprès d’Adelbert à la Relique Sacrée : seuils par défaut de 10 et 25 obscurs purifiés, niveaux 30 et 45, tous réglables. Option activée dans les deux modes randomisés. Les scènes d’introduction à la purification doivent être entièrement terminées ; sa présence devient exclusive entre maison et sanctuaire, avec une seule remise par cadeau et sauvegarde. Les cinq dialogues suivent la langue du jeu PAL, USA ou japonais ; l’interface conserve ses six langues.
- Taux shiny personnalisé de 0 à 100 %, à 5 % par défaut dans les deux préréglages randomisés du bureau. L’option « Lier les chromatiques à la seed », cochée par défaut et dépendante de cette personnalisation, fixe le statut par starter, cadeau, ID obscur ou emplacement de dresseur. L’aperçu montre les statuts exacts pour une nouvelle partie, même aux taux intermédiaires, avec les portraits authentiques et une étoile rouge pour les Pokémon chromatiques. Une même espèce peut avoir des statuts différents selon la rencontre. Le taux exprime une probabilité, sans quota sur les résultats.
- Décocher la liaison conserve le tirage en jeu au taux choisi. Les profils 0.5 à 0.10.1 sont migrés avec cette liaison désactivée pour préserver leurs sorties. Nature, genre, PID complet et IV restent natifs ; les anciens PID obscurs sont réutilisés et les Pokémon déjà générés ne sont pas retirés au sort. Le résultat prévisualisé suppose une nouvelle partie.
- Duo de starters contraint par familles, types, puissance et formes de base ; règles indépendantes des obscurs de boss, avec attribution globale des 48 familles.
- Difficulté progressive facultative par niveaux d’origine 1–35, 36–50 et 51–100, de ×0,5 à ×2 pour chaque plage. Elle remplace le multiplicateur global, précède les bonus des boss et le contrôle du stade final ; elle ne correspond pas à des chapitres et ne modifie pas les niveaux des starters/cadeaux.
- EXP des combats ×0,25 à ×5, par pas de 0,25 ; diminution de la jauge obscure ×1 à ×10. Les deux restent à ×1 par défaut. Le traitement natif conserve l’EXP initiale et la purification finale à la Relique ; les contrats et l’état de validation à l’exécution sont distincts dans les notes v0.15.
- Attaques et apprentissages, talents, statistiques, types, objets tenus, filtres d’espèces,
  niveaux et capture configurables séparément, avec protections des données spéciales.
- CT et compatibilités, coffres, six stocks ordinaires et équipes de sept chefs
  identifiés ; conservation des CS, clés et pierres. Les règles de boss non obscurs préservent le tirage obscur.
- Codec LZSS accéléré en Rust dans l'exécutable ; même sortie que la référence Python. Annulation coopérative pendant la recompression dans les deux chemins, contexte propre à la tâche et ABI précédent conservé.
- Traitement local. Aucun serveur, compte ou transfert de ROM.
- Interface en français, anglais, allemand, espagnol, italien ou japonais selon la langue du système, avec choix
  manuel mémorisé et changement immédiat sans modifier la partie configurée.
- ISO traité directement. DolphinTool externe est nécessaire pour convertir les RVZ. Le champ apparaît à l’entrée ou à la sortie selon le format et partage le chemin.
- Aucune ROM ni installation Dolphin n’entre dans les distributions locales.
- L'utilisateur a choisi explicitement l'application de bureau et souhaite un projet open source.
- L'interface et le rapport distinguent validation technique et partie complète jouée.

- Direction choisie : menus originaux de Colosseum, composition C (assistant compact).
- L’édition locale embarque un pack d’images, d’icônes et de sons exporté de la ROM.
  L’interface démarre sans ROM ni cache.
- Musique du titre et sons des menus ont des commandes indépendantes, activées au
  premier lancement si disponibles. Les choix restent mémorisés et ne modifient pas les profils.
- Les noms compacts de onze pierres peuvent être espacés, avec les cinq traductions
  natives conservées ; les anciens profils gardent la correction désactivée.

## Operating Context

Session occasionnelle, sur ordinateur : une fenêtre redimensionnable, des sélecteurs de fichiers
natifs, une progression lisible, une annulation et des erreurs récupérables. La source ne doit
jamais devenir une destination. Une sortie existante ne doit pas être remplacée.

## Evidence on Hand

La v0.16 est un lot de navigation, de documentation et de validation. Elle conserve
le moteur `details-and-progression-v15`, les 82 champs et le schéma de profil 1.
Les profils v0.15 sont reconnus séparément et importés sans modifier leurs valeurs.
Un vrai export v0.15 archivé, comprenant les huit réglages récents non neutres,
est utilisé pour contrôler cette compatibilité. Les six configurations comparées
dans trois régions et les trois images combinées restent identiques à la v0.15 ;
449 tests et 336 états de diagnostic des deux exécutables sont contrôlés.
Les 15 étapes Dolphin sur Europe, USA et Japon confirment la marche avec
plancher à zéro, la libération unique de réserve, la purification finale,
l’EXP normale ×2 avec montée de niveau et l’EXP obscure ×2 mise en réserve.
Les trois sessions se ferment normalement. Les ROM originales et les
sauvegardes personnelles passent le contrôle d’empreinte. Les cartes préparées,
les statistiques héritées et le raccourci de porte délimitent ce parcours
ciblé. [Détails de validation v0.16](docs/DESKTOP_V16.md)

La v0.15 utilise le moteur `details-and-progression-v15`. La matrice sur les trois
ROM réelles couvre 18 configurations et 36 constructions répétées ; elle vérifie
les starters manuels, filtres, niveaux, bonus des boss, composition EXP/jauge,
386 fiches, 108 variantes obscures et six langues de journal par région. Le mode
copie n’ajoute aucun patch ; les nouveaux réglages neutres reproduisent exactement
les patchs du moteur v0.14 archivé dans les trois régions. Une décompression RVZ
réelle est réutilisée puis supprimée ; une annulation native pendant compression
est observée en 0,094 s. Originaux et profil Dolphin personnel restent inchangés.
Dolphin Europe confirme EXP ×2 : gain natif 673 devenu 1 346, réellement ajouté
à la réserve de Tortank, et refus conservé pour Lanturn encore trop obscur.
Jauge ×3 confirme les diminutions 6 650 → 6 500 et 800 → 575 en combat. Les deux
essais se ferment normalement, sans changer les originaux ni le profil personnel.
Ces nouveaux parcours QOL USA/Japon restent qualifiés par les contrats et la
matrice, sans observation en jeu dans cet essai. Aucune montée de niveau,
purification finale, diminution par la marche ou branche du plancher à zéro n’y
a été observée. La préparation des cartes de test et les limites figurent dans
`docs/DESKTOP_V15.md` ; la matrice technique ne constitue pas une partie complète.

Moteur v3 et tests locaux ; reconstruction ISO testée sous Dolphin, achat d'une Pierre Lune
vérifié. Les évolutions et l'intégralité du scénario n'ont pas toutes été jouées individuellement.
La v0.3 compte 111 tests Python et trois tests Rust réussis ; son exécutable crée une ISO
identique à celle des sources. Un démarrage à froid dans une nouvelle partie Dolphin confirme
les deux starters, leur niveau et leurs capacités. Le combat et les dons tardifs de cette
version restent à contrôler manuellement.
La v0.4 ajoute les CT, coffres, stocks et boss : 147 tests Python et trois tests Rust
réussis, ISO reproductible identique entre sources et exécutable, RVZ vérifiée après
redécompression. Dolphin confirme les noms et descriptions des CT sur une copie de
sauvegarde ; les achats, coffres et combats de boss restent à parcourir dans cette version.
La v0.5 ajoute les profils, le duo de starters et les règles d’obscurs de boss :
187 tests Python et trois Rust passent. L’import dans l’exécutable reproduit
exactement l’ISO des sources. Dolphin démarre les images et charge une copie de
carte mémoire ; les nouveaux parcours de combat et d’acquisition restent ouverts.
Les détails de conservation et de fermeture Dolphin figurent dans `docs/DESKTOP_V05.md`.

La v0.11.0 utilise le moteur `seeded-shiny-status-v12`. Les tests automatisés
contrôlent les décisions par seed, les tables natives, les aperçus mixtes et les
traductions. Six comparaisons du mode sans liaison, à 0, 25 et 100 %, avec et sans
correctif de capacités des cadeaux, conservent les octets du moteur v11. Ces
contrôles ne constituent pas une validation Dolphin de cette évolution ni une
partie complète du scénario.

## Product Principles

- Une seed et les mêmes règles reproduisent les mêmes données.
- Les actions nomment leur effet et le fichier concerné.
- Les erreurs expliquent comment reprendre.
- Les données du jeu et les sauvegardes restent chez l'utilisateur.
- Le parcours natif de sélection, configuration et création prime sur la décoration.

