# Version 0.15 : fiches, starters choisis et progression

La v0.15 ajoute des fiches Pokémon, un journal HTML, le choix manuel des starters,
une courbe de niveaux et deux réglages de rythme de jeu. Les aperçus RVZ réutilisent
leur décompression et la recompression devient annulable dans les codecs Rust
et Python. Les trois ROM révision 0 Europe, USA et Japon restent identifiées
par leur empreinte complète.

Moteur : `details-and-progression-v15`. Les **82 paramètres, dont 57 booléens**,
restent répartis dans les quinze catégories. Les nouvelles règles de jeu sont
neutres par défaut : starters tirés par la seed, courbe désactivée, EXP et
purification à ×1.

## Choisir les starters

Dans **Avancé → Starters et cadeaux**, **Premier starter** et **Second starter**
proposent une liste recherchable par nom ou numéro national du Pokédex.
**Tirage avec la seed** conserve le tirage habituel. Il est possible de fixer
les deux starters ou d’en fixer un seul et de tirer son partenaire.

Le choix manuel est prioritaire sur le stade, le filtre de familles à trois
stades et la comparaison de puissance avec le Pokémon remplacé. Il ne contourne
pas les exclusions par espèce/type, les générations, le filtre légendaire ni
les contraintes du duo : familles différentes, absence de type commun et
puissance proche entre les deux Pokémon. Si ces règles ne permettent pas le
choix, l’outil indique ce qu’il faut corriger ; il ne les désactive pas tout seul.
Munja reste exclu de la sélection pour conserver la protection existante.

Décocher **Remplacer Noctali** ou **Remplacer Mentali** conserve le starter
d’origine ; son sélecteur manuel n’a alors aucun effet. Les niveaux de départ
restent 26 et 25, avec l’expérience initiale adaptée à l’espèce choisie.

Dans les deux préréglages randomisés, les starters tirés par la seed restent par
défaut des formes de base de familles à trois stades. Ces deux filtres sont
indépendants et peuvent être modifiés.

## Fiches et vérification des réglages

Les boutons **Détails** des starters et des rencontres de l’aperçu ouvrent une
fiche dans la langue de l’outil. Elle contient :

- les types, talents possibles et statistiques de base finaux ;
- les capacités connues pour la rencontre lorsque leur liste est déterminée ;
- les apprentissages par niveau et les CT compatibles ;
- la chaîne d’évolution complète, avec les conditions inscrites dans cette ROM.

Ces données proviennent des octets finaux, après randomisation et corrections
d’évolution. Elles ne sont pas déduites d’un Pokédex moderne. Par exemple,
Spectrum indique une montée de niveau à partir de 40 lorsque l’adaptation des
échanges simples est activée ; une évolution conservée par échange est signalée
comme indisponible directement dans Colosseum. Un obscur doit être purifié avant
d’évoluer. Les talents affichés sont les possibilités de l’espèce ; le jeu
détermine encore le talent individuel.

Les noms restent disponibles en français, anglais, allemand, espagnol, italien
et japonais. Les lecteurs utilisent les banques natives disponibles et des noms
de repli pour les langues absentes d’une ROM monolingue. La provenance de ces
catalogues figure dans les [notices tierces](../THIRD_PARTY_NOTICES.md).

**Vérifier les réglages** lance le moteur utilisé par l’aperçu et la création,
sans publier de ROM. Les incompatibilités de filtres, de stades ou de couple sont
présentées avec les corrections possibles. Une vérification réussie correspond
à la ROM, la seed et les options courantes ; tout changement l’invalide.

## Difficulté progressive

Dans **Niveaux et capture**, la courbe facultative remplace le multiplicateur
global par trois valeurs, chacune de ×0,5 à ×2 :

| Plage | Niveau de la rencontre dans le jeu d’origine |
| --- | --- |
| Début | 1 à 35 |
| Milieu | 36 à 50 |
| Fin | 51 à 100 |

La plage est choisie avant toute modification de niveau. Elle n’est donc pas
recalculée lorsqu’un Pokémon passe de 35 à 39, par exemple. Ces catégories ne
représentent pas des chapitres ou des villes. Le résultat est arrondi à l’entier
le plus proche et borné entre 1 et 100.

L’ordre est **courbe → bonus des boss → choix du stade final**. Les obscurs
reçoivent la modification générale de niveau, mais restent exclus du bonus des
boss et du filtre de stade final. Les starters et cadeaux gardent leurs réglages
de niveau propres. Désactiver la courbe rétablit le multiplicateur global ; ses
trois valeurs peuvent rester mémorisées sans être appliquées.

## EXP et jauge obscure

**Expérience gagnée ×** va de ×0,25 à ×5, avec un pas de 0,25 dans l’interface.
Le gain de combat est modifié après les bonus natifs, avec arrondi à l’entier
le plus proche et un minimum de 1 pour un gain positif. Le réglage concerne aussi
l’EXP mise en réserve pour un obscur lorsque le jeu l’autorise ; elle n’est pas
remultipliée à sa libération. L’EXP initiale et les Super Bonbons conservent leur
traitement d’origine.

**Vitesse de purification ×** va de ×1 à ×10. Elle multiplie les diminutions
de la jauge calculées par le jeu, avec son plancher à zéro. Les augmentations
restent normales. La nature et les objets gardent leurs effets natifs avant ce
facteur. La purification finale à la Relique et les conditions de scénario
restent nécessaires.

Les deux valeurs sont **×1 par défaut**. À ×1, aucun code QOL supplémentaire
n’est ajouté. Les fonctions et instructions sont qualifiées séparément dans les
trois exécutables ; un DOL inconnu ou une instruction inattendue sont refusés.
Le code ajouté partage la réservation protégée des patchs de capacités des
cadeaux et de chromatiques.

Les [contrats natifs et contrôles PowerPC](QOL_NATIVE_2026-11-03.md) décrivent
la qualification, les registres et les limites. **Dolphin Europe confirme un
gain de combat de 673 devenu 1 346 avec EXP ×2**, réellement ajouté à la réserve
de Tortank (12 313 → 13 659). Lanturn reçoit le même gain calculé, puis le jeu
refuse normalement sa mise en réserve tant que sa jauge est trop élevée.
Avec jauge ×3, les diminutions natives −0,5 et −0,75 deviennent −1,5 et −2,25 :
les jauges passent respectivement de 6 650 à 6 500 et de 800 à 575.

Ces témoins proviennent d’un combat réel sur une carte de test distincte ; les
captures n’écrivent ni EXP, ni jauge, ni résultat de combat. La progression
synthétique de la fixture, sa correction de cohérence et les raccourcis de
navigation gardés sont déclarés dans les notes natives. Les originaux et le
profil Dolphin personnel restent inchangés après fermeture normale des deux
essais. **Les nouveaux parcours QOL USA/Japon restent qualifiés par les contrats
et la matrice, sans observation en jeu dans cet essai.** Aucune montée de niveau,
purification finale, diminution par la marche ou branche du plancher à zéro n’a
été observée ici. La matrice ci-dessous reste une vérification des données.

## Journal HTML

Chaque création produit trois fichiers séparés :

| Fichier | Contenu |
| --- | --- |
| `partie.iso` ou `partie.rvz` | Nouvelle image de jeu |
| `partie.iso.json` ou `partie.rvz.json` | Rapport technique et reproduction |
| `partie.iso.html` ou `partie.rvz.html` | Journal lisible, hors ligne |

Le journal regroupe starters, obscurs, cadeaux, équipes des dresseurs, évolutions
et CT. Les sections sont initialement repliées pour éviter les spoilers.
**Ouvrir le journal** est disponible après la création. Son contenu décrit une
nouvelle partie avec cette configuration ; il ne lit pas une sauvegarde existante.

L’application choisit la langue courante de l’interface. La CLI propose
`--journal-language fr|en|de|es|it|ja`, avec `fr` par défaut. Ce choix ne modifie
pas la langue du jeu. Le HTML est autonome, sans script, image ni ressource
externe ; les chemins source et destination du rapport technique n’y sont pas
repris. Les textes sont échappés et une politique de contenu limite les
ressources actives.

La création refuse un nom d’ISO/RVZ, de JSON ou de HTML déjà utilisé. Les fichiers
sont publiés sans écrasement et un échec de publication retire les sorties
intermédiaires de cette création.

## Aperçus RVZ et annulation

Une fenêtre conserve au maximum une décompression RVZ dans un dossier temporaire
privé, avec son profil DolphinTool isolé. Changer la seed ou les options réutilise
cette ISO ; les empreintes de la source, de l’outil et de l’ISO sont revalidées.
Les horodatages seuls ne prouvent jamais l’identité des fichiers. L’ISO est
également relue après le calcul pour rejeter une modification survenue pendant
l’aperçu.

Changer la source ou l’outil, rencontrer une erreur, ou fermer la fenêtre libère
le cache. Un calcul actif garde sa lecture jusqu’à son arrêt, puis le nettoyage
a lieu. Aucun cache de jeu persistant n’est installé. Prévoir environ 1,5 Gio sur
le volume temporaire du système pour un aperçu RVZ.

Le codec Rust vérifie l’annulation par blocs d’environ 16 Kio ; la référence Python
possède aussi ses points d’arrêt. Une compression interrompue ne renvoie pas de
résultat partiel. Le contexte est propre à la tâche, l’ancien ABI est conservé
et un ancien DLL peut utiliser le repli Python annulable. Les conversions
DolphinTool déjà surveillées restent arrêtées par leur propriétaire en cas
d’annulation.

L’essai réel d’une RVZ USA mesure 4,328 s pour la première préparation et 2,250 s
pour la lecture suivante, avec une seule conversion, les mêmes octets ISO et
suppression du cache à la fermeture. Ces temps ne couvrent pas le calcul complet
de l’aperçu. Une annulation envoyée pendant la compression native de 8 Mio revient
en 0,094 s depuis le début de l’appel ; la recompression suivante reste identique
à Python. Ce sont des mesures locales, sans engagement de durée sur un autre PC.

## Profils et validation des données réelles

Les profils v0.14 sont importés avec les huit nouveaux réglages neutres. Leur
empreinte est contrôlée avant migration. Un ancien profil contenant des champs
v0.15 ou inconnus est refusé, même s’il a été réempreinté ; aucun champ n’est
silencieusement ignoré. Le réexport utilise le format courant complet.

La matrice privée couvre six configurations par région, soit **18 cas et
36 constructions répétées** : réglages recommandés, deux starters manuels,
un starter manuel, courbe avec boss, EXP/jauge seuls et combinaison des ajouts
avec types, talents, statistiques et chromatiques randomisés.

Les contrôles relisent les octets finaux et vérifient, dans chaque région :

- 386 fiches, 184 arêtes d’évolution et 3 947 apprentissages ;
- 3 355 enregistrements de dresseurs, 48 groupes obscurs et leurs 108 variantes ;
- les 398 rencontres du premier palier, 2 185 du deuxième, 772 du troisième et
  145 bonus de boss dans le cas combiné ;
- les deux starters manuels, leur dérogation au filtre de stade, et le refus
  d’une espèce manuelle explicitement exclue ;
- la composition des nouveaux blocs EXP/jauge avec les autres patchs, et
  l’identité de tout le REL lorsque seuls les deux réglages QOL sont ajoutés ;
- les six langues des journaux, leurs sections fermées et l’absence de chemins
  source/destination ou de ressources actives externes.

Trois ISO combinées ont été créées et vérifiées intégralement. Avec les nouveaux
réglages neutres, la comparaison des offsets, tailles et octets de chaque patch
avec le moteur v0.14 archivé est identique dans les trois régions. Le mode copie
produit zéro patch. Un contrôle complémentaire vérifie 2 508 formes finales
non obscures par région, dont cinq emplacements qui franchissent le seuil
uniquement après le bonus de boss.

Les tests de migration comprennent un profil réellement exporté par les sources
v0.14 archivées. Les tests croisés du codec, l’annulation native/Python, les
changements de contenu malgré une taille/date identique, la corruption du cache,
les erreurs et les lecteurs concurrents sont également contrôlés.

Ces essais ne constituent pas une partie complète ni une validation de
l’équilibrage, d’une console physique ou d’un second PC. Les essais régionaux
et cadeaux précédents restent décrits dans la
[validation v0.14](REGIONAL_COMPATIBILITY_2026-11-03.md).

Les preuves contenant des données du jeu restent privées dans
`build/v15-validation/` : `matrix-result.json`, `extra-checks.json`, trois ISO,
rapports et journaux. Le contrôle cache/codec est dans
`build/v15-pipeline-validation/real-cache-and-codec-validation.json`.
Les témoins natifs Europe, leurs CK3 avant/après, les cartes de test, les
moniteurs de conservation et l’agrégat de portée explicite restent dans
`build/v15-runtime/` ; le bilan est `result.json`. Les cartes USA/Japon préparées
avec les seuls PV observés après une guérison native Europe sont des données de
test hors ligne, sans prétendre à une guérison jouée sur ces deux régions.
Les empreintes des six sources ISO/RVZ et des 46 fichiers du profil Dolphin
personnel restent identiques. Ces fichiers de preuve ne sont pas distribués.

## Validation des exécutables Windows

Les deux éditions figées passent **312 états Qt au total** : 156 par édition,
dans les six langues et aux tailles 1040×800 et 680×540. Ces diagnostics couvrent
le parcours, les réglages, les exclusions et les aperçus de présentation. Les
binaires et le codec contrôlés correspondent aux fichiers de la distribution.

L’exécutable local a ensuite été utilisé dans sa fenêtre normale avec la ROM
USA, la seed `a0b4009878a88547` et les starters manuels Ectoplasma/Steelix. Le
diagnostic a d’abord signalé un couple impossible ; choisir ce duo admissible
a permis de calculer l’aperçu, d’ouvrir la fiche française puis de créer une ISO
séparée avec son JSON et son journal HTML. Une relecture indépendante compare
l’intégralité de l’ISO aux sept patchs recalculés, ainsi que les fiches aux REL
et DOL réellement extraits de cette ISO. Les espèces et niveaux obtenus sont
Ectoplasma 26 et Steelix 25. Le journal français correspond au rapport ; son
rendu dans les six langues garde les sections fermées et ne reprend aucun
chemin personnel. La ROM source et la RVZ USA originale restent inchangées.

Les deux dossiers temporaires privés sont vides après fermeture de
l’application, sans cache d’aperçu ni sortie intermédiaire orphelins. Les
captures de la fenêtre et le contrôle binaire sont conservés dans
`build/v15-runtime/ui/`, avec le bilan `frozen-creation-validation.json` ; les
312 états sont consignés dans `build/v15-frozen/staging-validation.json`.
Cette création utilise EXP et purification à ×1 et la courbe désactivée : elle
complète les essais distincts de ces réglages sans constituer une partie
complète ni un test sur un autre PC.

## CLI

```powershell
python -m colosseum_randomizer.cli original.iso duo.iso --seed ma-seed --starter-umbreon-species 94 --starter-espeon-species 208 --journal-language en
python -m colosseum_randomizer.cli original.iso rythme.iso --seed ma-seed --progressive-levels --early-level-multiplier 0.9 --mid-level-multiplier 1.1 --late-level-multiplier 1.25 --experience-multiplier 2 --purification-multiplier 3
```

Les numéros des starters sont ceux du Pokédex national, et non les indices
internes du jeu. Les deux exemples créent des fichiers séparés et ne touchent
pas aux sauvegardes.
