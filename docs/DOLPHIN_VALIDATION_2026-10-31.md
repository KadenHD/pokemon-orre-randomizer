# Validation Dolphin du 31 octobre 2026

Les contrôles fonctionnels ci-dessous distinguent les actions réellement jouées,
les équipes comparées en mémoire et les préparations privées. Ils ne constituent
pas une partie intégrale du scénario ni une mesure de son équilibrage.

## Images et référence de comparaison

Les valeurs attendues ont été relues dans les **deux ISO effectivement lancées** :
FST, archives FSYS, REL et DOL. Les propres relocations et compteurs du
REL confirment les tables. Les rapports de randomisation précédents ne servent
pas de référence pour ces comparaisons.

| Image de test locale | SHA-256 | Usage |
| --- | --- | --- |
| `recommended.iso` | `648cc8c0744c87fce40a7d4dbdd3f6f95f8df29bc48415ee33507cb5d1894b35` | Nouvelle partie et création native des starters |
| `gameplay-check.iso` | `c15ee8d12d6e0351cd60778f78193eaef9b485a77b9f345f3b0f00cf08427e5e` | Purification, CT, évolution, boutique, coffre et combats de boss |

Le second essai active les contraintes spécifiques aux obscurs des boss et la
randomisation des stocks de boutique testés. Ces empreintes identifient les images
locales ; aucune image n'est incluse dans la distribution.

## Contrôles fonctionnels accomplis

| Fonction | Action et résultat observés | Contrôle retenu |
| --- | --- | --- |
| Starters d'histoire | Une nouvelle partie crée Hypocéan niveau 26, EXP 17 576, et Élektek niveau 25, EXP 15 625. | Les deux espèces, niveaux, EXP et quatre capacités concordent avec le DOL/REL final de l'image recommandée ; les quatre autres emplacements sont vides. Aucun Pokémon n'est injecté à l'exécution. |
| Purification | Au Sanctuaire sacré, l'Onix préparé niveau 39 passe de jauge 0/ruban national 0 à jauge −100/ruban 1. | Espèce 95, EXP 59 319, capacités et identifiant obscur 19 restent conservés. Le drapeau natif de purification vaut 1 après l'action. L'animation n'a pas été retenue ; la transition est prouvée par les états avant/après et l'absence d'écriture dans le Pokémon. |
| CT05 | La poche CT affiche Tunnel ; Onix est indiqué « Apte ». Le joueur remplace Charge par Tunnel et la CT est consommée. | La capture après apprentissage contient `[91,20,106,88]`, contre `[33,20,106,88]` avant ; espèce 95, niveau 39 et EXP 59 319 sont inchangés. L'image finale associe réellement CT05 à Tunnel 91. |
| Évolution accessible | Un Super Bonbon fait passer Onix de 39 à 40. La scène native d'évolution affiche Onix, puis la confirmation Steelix. | Espèce 208, niveau 40, EXP 64 000 ; les quatre capacités `[91,20,106,88]` sont conservées. Le Super Bonbon est consommé. Aucun échange ni objet tenu n'est nécessaire pour cette règle d'évolution au niveau 40. |
| Boutique randomisée | À Pyrite, Précision+ coûte 950 ; un achat fait passer la quantité possédée de 0 à 1 et l'argent de 99 999 à 99 049. | Le stock visible concorde avec la boutique 5 de l'ISO finale. Un seul emplacement ordinaire change ; les autres octets communs du sac sont identiques. Aucune écriture d'inventaire ou d'argent n'est effectuée par l'outil RAM. |
| Coffre randomisé | Le coffre 1 de Phénacit annonce puis donne trois Défense+. | Objet 76, quantité 0→3, drapeau 152 : 0→1. Argent 99 149 inchangé, autres objets inchangés. Salle 3 et coordonnées du coffre environ `(-153.04,32.99,84.22)` concordent avec le REL final. Aucun objet ni drapeau de coffre n'est injecté. |
| Capture d'un obscur | Cochignon obscur niveau 35 de Boulédisco apparaît avec son aura violette, est capturé avec la Master Ball, puis le combat se termine par une victoire et le retour au dialogue de Billy. | Le PC passe de 14 à 15 Pokémon : une case vide reçoit Cochignon 221, groupe obscur 19, jauge 10 000, Ball 1 et capacités `[8,173,133,124]`. Les quatorze Pokémon déjà stockés restent identiques octet par octet. Master Ball 1→0 et drapeau de capture 2144 : 0→1. Aucun Pokémon n'est injecté dans l'équipe ou le PC. |

Pour CT05 et le Super Bonbon, les consommations ont été confirmées pendant
l'interaction dans l'interface. Les captures binaires retenues pour ce cas sont
celles du Pokémon, pas des captures du sac après chaque consommation. Pour
l'achat et le coffre, les quantités et l'argent sont aussi vérifiés par des
captures du sac avant/après. Les capacités après évolution sont Tunnel 91,
Étreinte 20, Armure 106 et Jet-Pierres 88.

Le message générique de la relique après la purification ne signale pas un
blocage : le drapeau d'accès 1067 était déjà à 1 et Onix purifié n'est plus compté
par le jeu parmi les candidats à purifier. Aucun changement de quête n'a été
nécessaire.

## Sept équipes de boss vérifiées

Le combat 164 de Boulédisco, dresseur 162, a été construit par le moteur natif.
Les cinq Pokémon présents concordent avec l'image finale, y compris leurs
niveaux, quatre capacités stockées et identifiants obscurs : Scarhino 30,
Arcanin 31, Chartor 29, Magnéton 28 et Cochignon obscur 35. Le sixième emplacement
est vide. La comparaison accepte l'ordre effectif du moteur et exige une
correspondance complète et unique pour chaque Pokémon. Le premier tour a été
effectivement joué et capturé à l'écran. Deux tours d'attaques, puis le tour de
capture, la victoire et le retour à l'histoire ont été observés pour ce combat.

| Boss | Combat → dresseur | Obscur tiré dans cette ISO | Contrôle en jeu |
| --- | --- | --- | --- |
| Boulédisco | `164 → 162` | Cochignon | 5 Pokémon exacts, premier menu, attaques, capture et victoire |
| Dakim | `213 → 211` | Electhor | 5 Pokémon exacts et premier menu |
| Vénus | `328 → 326` | Raikou | 5 Pokémon exacts et premier menu |
| Teck | `405 → 403` | Artikodin | 5 Pokémon exacts et premier menu |
| Helgonza | `427 → 425` | Cerfrousse | 5 Pokémon exacts et premier menu |
| Jakylla | `439 → 437` | Drattak | 6 Pokémon exacts et premier menu |
| Nosfrat | `441 → 439` | Dracolosse | 6 Pokémon exacts et premier menu |

Les **37 Pokémon présents et cinq emplacements vides** correspondent aux données
de l'ISO. Chaque espèce, niveau, groupe obscur et ensemble de quatre capacités
stockées est comparé, y compris dans la réserve. Les sept obscurs ont une jauge
positive. Les identifiants des six derniers dresseurs ont aussi été lus dans les
structures natives. Six rechargements du même point de reprise, créé pour cette
ISO exacte, ont permis ces essais indépendants ; aucune équipe ennemie n'a été
injectée. Des captures d'écran attestent les sept premiers menus de combat.

Les capacités stockées dans les structures de combat ont été comparées ; cela
ne prouve pas l'exécution de chacune d'elles. Les substitutions temporaires du
moteur, notamment Charge Noire chez un obscur, demandent une observation propre.
La capture et la victoire sont établies pour Boulédisco. Les six autres essais
s'arrêtent au premier menu : ils ne prouvent ni leur victoire complète, ni la
capture de chacun de leurs obscurs, ni leur accès par toute la progression du
scénario.

## Préparation privée et actions réellement testées

Les starters proviennent d'une nouvelle partie à carte vide. Les autres cas
utilisent des **copies** d'une carte existante, préparées avant le lancement.
La fixture Onix contient un Onix 39 prêt à purifier, ses capacités initiales,
une CT05 et un Super Bonbon. Elle ne contient ni Steelix, ni Tunnel appris, ni
résultat de purification déjà appliqué à cette cible.

Pour accélérer les vérifications, les préparations suivantes sont explicites :

- Warps natifs vers les scènes utiles et ajustements de position/orientation du
  personnage. Le coffre utilise quatre caches de position cohérents ; un
  déplacement dépassant la cible a nécessité un second placement.
- Argent 99 999 dans la fixture avant le boot. Après l'achat vérifié, deux
  Antidotes sont vendus par l'interface native pour 50 chacun : une place se
  libère dans les vingt emplacements ordinaires et l'argent atteint 99 149 avant
  le coffre.
- Équipe existante portée au niveau 80 et préparée purifiée pour les essais
  de boss. Cette équipe facilite le contrôle du combat et n'en mesure pas la
  difficulté normale.
- Point de reprise privé avant un dialogue de combat. À l'entrée naturelle du
  lancement de combat, seul son identifiant est substitué pour demander au
  moteur de construire l'équipe de boss depuis l'ISO. Aucune équipe ennemie
  n'est injectée.
- Remise à zéro du seul drapeau de capture 2144 du groupe obscur 19, déjà capturé
  dans la copie source, afin de permettre sa réapparition pour l'essai. Cette
  écriture prépare une rencontre ; elle n'est pas une capture réussie. Les six
  autres groupes étaient observés non capturés au point de reprise.

Les journaux séparent ces préparations des actions dans l'interface :
purification, apprentissage, gain de niveau, évolution, achat, ouverture du
coffre, déroulement du combat et capture. Les cartes, états de reprise, captures
RAM, outils de sauvegarde et références de recherche restent privés sous
`build/` ou `analysis/`, exclus des archives publiques. Aucun nom, chemin
personnel, sauvegarde, extrait binaire de ROM ou code tiers de ces outils n'est publié
avec ce rapport.

## Dolphin et conservation des originaux

Les essais instrumentés utilisent Dolphin 2609a et son protocole GDB. Une copie
**privée** de l'émulateur change un seul octet du délai de polling `select`
de 20 µs à 0, pour éviter le coût du délai Windows pendant les essais GDB. Cette
adaptation concerne l'émulateur de QA, pas les données du jeu. L'exécutable
officiel source du projet reste intact et la copie modifiée ne sera pas
distribuée. Le comportement du polling et du serveur est documenté dans les
[sources officielles épinglées](https://github.com/dolphin-emu/dolphin/blob/409881c34357d0f105fd473167d15ab0bd9c1628/Source/Core/Core/PowerPC/GDBStub.cpp)
et dans la [recherche sur le dispositif de QA](reverse-engineering/DOLPHIN_RUNTIME_FIXTURES.md).

Le moniteur lance un profil isolé, relève le véritable code natif de fermeture
et compare les empreintes avant/après des fichiers protégés et de tout le
profil personnel. Les contraintes, corrections du lanceur et limites de
l'environnement sont décrites dans
[l'audit d'isolation](reverse-engineering/DOLPHIN_VALIDATION_ISOLATION.md).

Les sessions terminées `baseline-empty-run`, `random-story-host-run`,
`random-story-fast-run`, `onix-gameplay-run`, `bosses-gameplay-run` et
`final-official-gameplay-run` ont toutes un **code natif 0** et conservent les
**46 fichiers** du profil personnel suivis, ainsi que les images et exécutables
protégés de chaque session. L'essai diagnostique abandonné dans AppContainer est
consigné séparément ; son arrêt forcé n'est pas compté comme fermeture normale.

Après la fermeture de la session instrumentée, la copie privée de Dolphin a été
remplacée par son exemplaire officiel conservé, SHA-256
`17b01a8629d865378a45e58d5fcebf9dcc3f7919c719130a4ffdd1ca2b27b635`.
Les profils privés ont `GDBPort=-1`, socket vide, mode débogage désactivé et
codes de triche désactivés. Les quatre anciens ports GDB contrôlés sont fermés.
Les configurations privées précédentes et la copie de diagnostic sont archivées
localement pour rendre cette remise en état réversible.

Le dernier essai utilise cet **émulateur officiel sans correctif et sans GDB** :
démarrage à froid de `gameplay-check.iso`, écran titre, chargement par l'interface
du point de reprise créé pour cette même ISO, puis lancement ordinaire du combat
de Billy sans substitution d'identifiant. Le premier menu affiche Kirlia 29 et
Bekipan 30. La fenêtre est ensuite fermée normalement, code natif 0. Ce dernier
contrôle est un test de démarrage et de combat jusqu'au menu, sans tour complet.

L'audit global après cette fermeture compare les images sources, les **2 011
fichiers de `game/`**, les **2 691 fichiers de l'installation Dolphin originale**
et les **46 fichiers du profil personnel** au manifeste de début de cette passe :
**aucune différence**. Aucun fichier personnel n'est restauré ou remplacé. Les
variations historiques de Qt.ini et SRAM de la première passe restent décrites
dans [le suivi v0.5](DESKTOP_V05.md) ; l'audit présent ne les réattribue pas.

## Provenance des preuves

Les noms ci-dessous identifient des rapports privés, non distribués. Leurs
empreintes permettent de distinguer les états de preuve sans publier leur
contenu ou les données personnelles qu'ils protègent.

| Référence privée | SHA-256 |
| --- | --- |
| `expected-gameplay.json`, lecture des deux ISO | `24b01ba7d5cc9a4cf0c7209b323876e1b8deb539425523af4c5e6f3a93d2bc20` |
| `story-starters-runtime-validation.json` | `128e5440526b57121bf1d5775e3c33fbb143043fa2c35d14f7176793a1e44192` |
| `purification-runtime-validation.json` | `a4e89ae91c04f286ccca698edf677f56bf785c3f333d60ae1b7eb72fb0436126` |
| `tm-evolution-runtime-validation.json` | `b1427f04972e10af7e84c2382b38a134dfde91fd0e480c8cb13680aabd739888` |
| `shop-runtime-validation.json` | `133e028a0e3200cddbe1cbe3fddc9b126c9ffb4c9a7bb1d8be971ec697b8d7e0` |
| `chest-runtime-validation.json` | `12b415b4dac60ae86bd77cff7d2ab79b7511f9155535cdb3a8aa4b8d728dfb91` |
| `boss-164-roster-runtime-validation.json` | `2c09e22a052f64238d78a3415ee00c056afe031e100d0d348b9c463fdbe8c6f2` |
| `boss-runtime-suite-validation.json`, sept cas et audit final | `a78f6670fdfa056d012aada486fc5cea540f446143061387c8d3dd95a9e9c2be` |
| `capture-runtime-validation.json` | `0d4544cbe0a29e9202a74fea978809d3b20272c806b701cc42b103e70454eb3d` |
| `final-audit-after-cleanup.json` | `da101096e81934ca71d818004e0ef064a338f871382120405978c382fd505e4f` |
| `final-official-gameplay-run.json` | `7bedfed72a3d28c14d5fa0ca09f85c00dacceb441f75254f9c5f772e0f0b4cba` |
| `final-audit-after-official-run.json` | `774d81a998a6d5f3699f1b84aec8f0acd17c4b5db20f35867de68114ed429feb` |
| `final-official-runtime-validation.json` | `8dca4874411b1ec1ce4402f23d84b643d5b498853e6d41e572162598db1c0fcc` |

Ces contrôles ne couvrent pas une progression complète du scénario, tous les
événements spéciaux, l'exécution de toutes les capacités, la capture des six
autres obscurs de boss, l'équilibrage d'une partie ordinaire ou une console
physique. Aucun défaut des données du randomizer n'a été reproduit dans les cas
testés. Les corrections livrées concernent l'isolation et le suivi du lanceur de
validation, avec neuf tests dédiés, et la documentation des preuves et limites.
