# Pokémon chromatiques

Depuis la v0.11.0, le moteur `seeded-shiny-status-v12` propose deux façons de
choisir le statut chromatique, indépendamment de la randomisation des espèces.

| Paramètre | Valeur initiale | Effet |
| --- | --- | --- |
| `custom_shinies` — Personnaliser les shinies | Désactivé | Active le taux personnalisé et déverrouille les starters et cadeaux concernés. Décoché, aucun octet lié aux shinies n’est modifié. |
| `seeded_shinies` — Lier les chromatiques à la seed | Activé | Fixe les statuts à partir de la seed. Sans effet lorsque la personnalisation est désactivée. Décoché, conserve le tirage en jeu. |
| `shiny_chance_percent` — Taux de shinies (%) | 1 % | Probabilité par rencontre ; quatre décimales dans l’interface. 0 % interdit les nouveaux shinies concernés ; 100 % les garantit. |

Le taux et la liaison restent visibles mais désactivés tant que
`custom_shinies` est décoché. Modifier l’un de ces paramètres invalide l’aperçu.
Les deux préréglages randomisés de l’application de bureau activent la
personnalisation à 5 % et lient le résultat à la seed. Le tableau décrit
les valeurs du moteur et de la CLI avant application d’un préréglage de bureau.

## Mode lié à la seed et aperçu

Lorsque la personnalisation et la liaison sont actives, la seed détermine un
statut par starter, cadeau, ID obscur ou emplacement de Pokémon de dresseur.
Un obscur garde la même décision lors de ses réapparitions. Deux rencontres de
la même espèce peuvent avoir des statuts différents : la clé dépend de la
rencontre, et non de l’espèce.

L’aperçu des deux starters, des 48 obscurs du scénario et des quatre cadeaux
identifiés lit les décisions du moteur de création, sans refaire de tirage.
Il affiche les statuts exacts pour une **nouvelle partie**, même à un taux
intermédiaire, avec une étoile rouge pour les Pokémon chromatiques et la face
correspondante de `poke_face.fsys`. Une même espèce peut donc demander les deux
faces dans un même aperçu. Les lectures sont dédupliquées par espèce et statut,
puis réparties en lots d’au plus 64 espèces. Aucun portrait n’est recoloré.

Le pourcentage décrit une probabilité par clé, sans quota sur l’aperçu. Par
exemple, 1 % ne garantit pas la présence d’un chromatique parmi les 54 Pokémon affichés.
Une fois la seed et le taux choisis, les décisions sont fixes. Augmenter le taux
pour la même seed conserve les chromatiques déjà sélectionnés et peut en ajouter.

La seed fixe seulement le choix du mode natif « jamais shiny » ou « toujours
shiny ». La nature, le genre, le PID complet et les IV restent générés par le jeu.
Le RNG du jeu et son état ne sont pas figés par le randomizer : la reproductibilité
du statut ne rend pas toute la partie déterministe.

## Tirage en jeu et anciens profils

Décocher `seeded_shinies` conserve le mode de la v0.10 : le générateur aléatoire
du jeu décide du statut lors de la génération, au taux demandé. La seed du
randomizer ne prédit alors pas ce tirage. L’aperçu utilise les faces ordinaires
aux taux intermédiaires et indique que le statut sera tiré en jeu. À 0 et 100 %,
il peut annoncer respectivement l’absence ou la garantie de chromatiques.

Les profils 0.5 à 0.10.1 sont vérifiés avant migration et reçoivent
`seeded_shinies=False` pour conserver les sorties antérieures. Les profils
antérieurs à 0.10 conservent aussi `custom_shinies=False`. Les nouveaux profils
incluent les trois paramètres. Le mode sans liaison conserve les octets v11 :
six comparaisons à 0, 25 et 100 %, avec et sans correctif des capacités de cadeaux,
ont vérifié cette compatibilité.

## Portée

Les appels couverts sont ceux des équipes de dresseurs, des Pokémon obscurs,
de Noctali et Mentali et des dons de Posipi, Ho-Oh, Celebi et Pikachu identifiés
dans la version PAL prise en charge. Leur espèce peut rester d’origine : le taux
n’exige pas la randomisation des espèces. Les événements tardifs ne sont pas
tous accessibles normalement dans cette ROM ; la présence d’un appel identifié
ne garantit pas que son événement soit jouable.

Les anciens PID d’obscurs déjà générés sont réutilisés comme dans le jeu d’origine.
Les Pokémon purifiés et ceux déjà présents dans une sauvegarde ne sont pas
retirés au sort. Changer la ROM ou les réglages ne remplace pas ces Pokémon.
L’aperçu suppose donc une nouvelle partie ; il ne décrit pas rétroactivement une
sauvegarde existante. L’application ne modifie pas les fichiers de sauvegarde.

## Implantation PAL

Le patch exige le DOL d’origine dont le SHA-256 est
`a788176a45eb88dbd227246a7205ab9856bc79f3cca7e4a0f5376cf466664df5`.
Il vérifie les instructions d’origine avant chaque modification et ajoute une
section de code exécutable réservée au-delà des données et de la pile du jeu.
Cette section partage la réservation des correctifs de capacités des cadeaux ;
sa limite basse d’arène est agrandie pour éviter son écrasement.

Le générateur de PID natif est à `0x80128584`. Un wrapper choisit une seule fois
le mode natif « jamais shiny » ou « toujours shiny », puis laisse la fonction
respecter ses contraintes de nature et de sexe. Le corps de cette fonction et
le test canonique `(PIDhaut ^ PIDbas ^ SID ^ TID) < 8` restent inchangés.
Le corps du générateur aléatoire natif reste également inchangé.

### Décisions versionnées et tables natives

Le tirage lié à la seed utilise SHA-256 avec le domaine
`seeded-shiny-status-v1`. Son entrée est la concaténation de ce domaine ASCII,
d’un octet nul, de la longueur de la seed UTF-8 sur deux octets big-endian,
des octets UTF-8 exacts de la seed, d’un octet nul et de la clé ASCII. Les quatre
premiers octets du digest, interprétés en entier big-endian, sont comparés au
seuil du pourcentage. Les espaces de la seed ne sont pas retirés.

Le seuil est `arrondi_au_plus_proche(pourcentage × 2^32 / 100)`, les égalités
étant arrondies vers le haut. Les extrêmes valent exactement 0 et `2^32`.
Un résultat strictement inférieur au seuil donne le statut chromatique. Le
rapport conserve le taux demandé et le taux effectif associé au seuil entier.

Les clés sont `special:umbreon`, `special:espeon`, `special:plusle`,
`special:ho-oh`, `special:celebi-event`, `special:pikachu-event`, ainsi que
`trainer:<index>` et `shadow:<id>`. Le DOL contient deux tables d’un octet par
entrée : 5 510 emplacements de dresseur (indices 0 à 5 509) et 97 entrées d’ID
obscur (0 à 96). L’ID 0 représente l’absence d’obscur. Ces 97 entrées internes
ne correspondent pas à 97 obscurs accessibles : l’aperçu porte sur les 48
groupes obscurs du scénario. Les six appels spéciaux utilisent chacun une
décision constante.

Un trampoline à `0x801FE83C` conserve l’index natif dans le mot inutilisé à
`pile + 0x48` du cadre de son appelant. Le wrapper masque l’index de dresseur
sur 16 bits, vérifie les bornes puis lit la table correspondante ; un index
hors limites prend le mode non chromatique sans lecture hors table. Les décisions
et empreintes des tables figurent dans `shinies.seeded_decisions` et
`shinies.status_tables` du rapport. L’aperçu lit directement les décisions
`specials` et `shadows`.

### Mode historique sans liaison

Aux taux intermédiaires sans liaison, deux appels au RNG natif `0x800E42A4`
forment un tirage de 32 bits comparé au même seuil. Les taux 0 et 100 n’ajoutent
pas ce tirage intermédiaire. Ce chemin correspond au patch
`native-shiny-generation-v1` du moteur `native-shiny-generation-v11` des versions
0.10.0 et 0.10.1 ; le patch lié à la seed porte la version
`seeded-shiny-status-v1`.

Les sept appels détournés sont `0x80134940`, `0x80134A50`, `0x80134B70`,
`0x80134C5C`, `0x80134D54`, `0x80134E7C` et `0x801FEC98`.
Pour les obscurs, le PID est généré avec les identifiants du joueur.
Un correctif à la sortie du réglage du propriétaire (`0x8012811C`) aligne le
SID/TID complet des obscurs non purifiés sur ces mêmes identifiants, sans modifier
leur PID. Il exclut les enregistrements déjà purifiés (`purification = -100`).
La réutilisation native des anciens PID et les routines de capture restent en place.

## Sources et vérification

Les adresses et instructions ont été vérifiées directement dans le DOL local
avec un désassemblage PowerPC big-endian. REA a identifié le fichier et son
empreinte ; aucun décompilateur DOL utilisable n’était disponible dans ce
backend Windows. Les premiers repères provenaient de références publiques,
dont [les notes de rétro-ingénierie Colosseum](https://github.com/alexandria-p/pokemon-colosseum-modding/blob/main/Claude%20Assets/handoffs/2026-09-05_0020_code-set-complete.md)
et [les définitions de données de GoD](https://github.com/PekanMmd/Pokemon-XD-Code/tree/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0).
Le code du patch a été écrit à partir des instructions observées ; aucune
implantation tierce du patch n’a été copiée.

Les tests automatisés contrôlent les seuils, les branches, la conservation des
registres, les identifiants du propriétaire, le masque exact des écritures,
la composition avec les correctifs de cadeaux et les octets laissés intacts.
Ils couvrent aussi les décisions par seed, la monotonie des seuils, les index
natifs et leurs bornes, la migration des profils, les portraits mixtes d’une même
espèce et l’invalidation des résultats après modification de la liaison.
Ces vérifications automatisées ne constituent pas une validation Dolphin du
mode lié à la seed ni une partie complète du scénario.

Les fichiers de preuve historiques et les ISO de test de la v0.10 sont privés dans
`build/shinies-2026-11-01/` et ne font pas partie des distributions.
Les documents de validation de la v0.10 restent des constats de cette version ;
ils ne valident pas les nouveaux hooks du moteur v12.

La [validation du 2 novembre 2026](SEEDED_SHINIES_VALIDATION_2026-11-02.md)
consigne deux démarrages Dolphin avec appels natifs contrôlés : 81 emplacements
par démarrage, les 48 groupes obscurs, les six routines de starters et cadeaux
et la branche de réutilisation d’un PID obscur. Les statuts restent identiques
après des appels RNG supplémentaires ; ce sont des fixtures CPU sans partie jouée.
