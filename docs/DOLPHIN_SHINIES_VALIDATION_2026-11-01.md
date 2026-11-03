# Validation des shinies sous Dolphin — 1 novembre 2026

État intermédiaire : la chaîne capture, retrait du PC, purification, sauvegarde
du jeu et rechargement à froid est observée sur une même cible. Le cadeau natif
Posipi randomisé est également reçu et sauvegardé. Les essais Ho-Oh et de
réapparition restent en cours ; ce document ne les compte pas comme réussis.
Le moteur de production v0.10 n'a pas changé pendant cette validation.

## Images et critère retenu

Les essais utilisent les ISO produites avec la seed `shiny-native-validation` :

| Image privée | SHA-256 |
|---|---|
| `build/shinies-2026-11-01/shinies-100.iso` | `7521dcf9ba13247a6f1cffa1178e28d34ad6ce584da4c49b09e76a0e53384efa` |
| `build/shinies-2026-11-01/shinies-0.iso` | `cf0490109c35e46c5210d7072b2a0992132a77ea5eba30f9ed1a981ba0c7efa9` |

Le contrôle d'identité relit le PID et les deux identifiants OT dans les CK3,
puis applique le test natif canonique `(PIDhi ^ PIDlo ^ SID ^ TID) < 8`.
La palette et les effets visibles sont vérifiés séparément. Les identifiants
complets, cartes, captures RAM et journaux détaillés restent privés sous `build/`.

## Actions réellement observées

| Cas | Résultat établi | Preuves privées principales |
|---|---|---|
| Starters à 100 % | Nouvelle partie sur carte vide ; portraits et modèles 3D d'Hypotrempe et Abra observés dans leurs résumés. | `starter-100-visual.json`, `starter-100-horsea-summary.jpg`, `starter-100-abra-summary.jpg` |
| Bornes des starters | Au démarrage à froid, les deux starters natifs ont un XOR de 2 et 3 à 100 %, et de 60 615 et 60 243 à 0 %. Les autres emplacements sont vides. Le cas 0 % est une lecture RAM, sans validation visuelle. | `build/shinies-2026-11-01/runtime/starter-runtime-validation.json` |
| Rencontre et capture | Arcanin obscur niveau 40, groupe 21, construit pour le combat de Dakim ; modèle doré et effet d'entrée visibles. Capture native à la Master Ball, puis réception automatique au PC : 14 → 15 Pokémon. Les quatorze anciens CK3 restent identiques octet par octet. | `target-snag-identity.json`, `existing-pc-after-snag.json`, `shadow-100-arcanine-entry.jpg`, `shadow-100-arcanine-pc.jpg` |
| Retrait du PC | Retrait par l'interface vers le premier emplacement de l'équipe. Le CK3 complet de 312 octets reste identique à celui reçu après la capture. | `target-capture-pc-purification-identity.json`, `target-after-pc-withdrawal.bin` |
| Purification | Après préparation de la jauge décrite ci-dessous, interaction native avec la Relique. Le message d'ouverture de conscience est visible ; jauge −100, ruban national 1 et drapeau natif de purification 1282 à 1. PID et identifiants OT conservés, XOR 6. | `acquisition-rsp.jsonl`, `target-capture-pc-purification-identity.json`, `shadow-100-arcanine-purification.jpg` |
| Sauvegarde et rechargement | Sauvegarde par le jeu sur la carte privée, fermeture normale, nouveau démarrage de l'ISO et « Continuer » depuis le titre, sans savestate. La cible purifiée est retrouvée avec son identité et ses 312 octets strictement identiques. Son modèle doré est encore visible. | `purified-card-before-cold-load.json`, `target-card-coldload-identity.json`, `arcanine-purified-coldload-summary.jpg` |
| Cadeau Posipi randomisé | Scène native de Doking au club de Pyrite : le don produit un Malosse shiny niveau 13, reçu au PC avec l'OT fixe attendu du cadeau et un XOR de 6. Les quinze anciens CK3 du PC restent identiques. La sauvegarde du jeu contient ensuite le CK3 exact du nouveau cadeau. | `plusle-native-gift-identity.json`, `plusle-native-gift-card.json`, `plusle-gift-shiny-houndour-pc.jpg`, `plusle-native-game-save-complete.jpg` |

Sauf chemin complet indiqué, les preuves du tableau sont sous
`build/shiny-validation-final-2026-11-01/`.

Le CK3 après capture et après retrait du PC partage le SHA-256
`4d06f1be447cec8969a1204489a1fa8b3647f99d184f48d6c192208f1bbdbc05`.
Après purification, le CK3 de la carte sauvegardée et celui relu après
redémarrage partagent le SHA-256
`8d6a48eff988e19f90030fbaa858c15aca5f61a93bc431dba3982907fb7efae5`.
Le parseur confirme les checksums des trois slots de la carte et leur
déchiffrement/rechiffrement exact. Le constat de persistance repose aussi sur
la lecture RAM du véritable rechargement, au-delà de cette vérification de carte.

La racine joueur est redéréférencée après chaque boot. Pour le rechargement
retenu, elle vaut `0x80455B00`, donc l'équipe commence à `0x80455BA0`.
`stale-root-address-diagnostic.bin`, obtenu par erreur à une ancienne adresse,
est explicitement exclu des preuves de rechargement.

Pour le cadeau, le point d'arrêt est atteint naturellement dans `std217(3)` à
`0x801CF11C`, depuis l'interpréteur de script ; le retour −1 correspond à la
réception au PC lorsque l'équipe est pleine. Aucune écriture de PID ou d'OT
n'est effectuée pour ce don. Le nouveau CK3 partage le SHA-256
`9fc5f58590956df7bde732fca8fa8625a0ac3b9812a6ae6815663033a7ae4071`
entre la capture RAM et la carte sauvegardée, conservée sous
`plusle-native-saved.raw`. Le précédent cadeau déjà présent dans la copie,
devenu Polichombr non shiny, est conservé sans modification. Le nouveau Malosse
n'a pas encore été rechargé depuis cette carte après un autre démarrage à froid.

Le modèle shiny de Malosse est visible dans le PC. Les dialogues de la scène
continuent toutefois à nommer POSIPI et à annoncer son transfert : les textes
et acteurs narratifs n'ont pas été réécrits pour l'espèce randomisée. Cette
limite cosmétique ne doit pas être confondue avec l'identité réellement reçue.

## Préparations privées et portée

La carte de départ est une copie de `boss-party-v2.raw`, avec équipe déjà portée
au niveau 80 et Master Ball. Le groupe obscur 21 était inédit dans cette source.
Des transitions natives, warps et placements du personnage accélèrent l'accès
aux scènes. À l'entrée naturelle du combat de Billy, l'argument du combat 13
est remplacé par 213 ; le moteur construit ensuite les véritables données de
Dakim depuis l'ISO. Cela ne valide pas l'accès à Dakim par toute la progression
du scénario ni l'équilibrage d'une équipe normale.

Après la capture et le retrait du PC, le seul champ Pokémon préparé est la jauge,
abaissée de 13 000 à 0 pour rendre la cible immédiatement purifiable. La
comparaison des deux CK3 confirme que seuls des octets du champ `+0xDC..+0xDF`
changent. PID, OT et toutes les autres données sont conservés. Cette préparation
ne démontre pas une diminution naturelle de la jauge ; la purification qui suit
est bien exécutée par le jeu. Aucun Pokémon purifié n'est injecté pour prouver
la sauvegarde ou le rechargement.

Pour rejouer le cadeau Posipi sur cette copie, seul le drapeau de scène 1047
est préparé de 1 à 0 après validation des descripteurs et des signatures natives ;
1046 reste à 1 et les bits voisins sont préservés. Le plan privé
`plusle-flag-fixture-plan.json` est corroboré par les lectures, l'écriture et sa
relecture dans `acquisition-cold-rsp.jsonl`. La scène du club est ensuite jouée
par l'interface, et 1047 est observé revenu à 1 avant la sortie. Ce reset est une
fixture de progression, pas un parcours neuf jusqu'à l'événement.

## Mesure du taux par appels natifs contrôlés

`build/shiny-validation-final-2026-11-01/statistics/statistics-summary.json`
consigne des exécutions sur le vrai CPU Dolphin des wrappers de production,
du générateur PID et du RNG PAL natifs. Le harnais fournit des CK3 synthétiques,
une boucle PowerPC en RAM privée et des appels contrôlés ; il ne simule ni
rencontres jouées ni événements de cadeaux.

| Taux demandé | Mode cadeau | Mode dresseur | Mode obscur |
|---|---:|---:|---:|
| 1 % — 50 000 appels par mode | 508 / 50 000 | 520 / 50 000 | 499 / 50 000 |
| 0 % — 1 000 appels par mode | 0 / 1 000 | 0 / 1 000 | 0 / 1 000 |
| 100 % — 1 000 appels par mode | 1 000 / 1 000 | 1 000 / 1 000 | 1 000 / 1 000 |

À 1 %, le total est de 1 527 shinies sur 150 000 PID, soit **1,018 %** ;
l'intervalle de Wilson nominal à 95 % est `[0,9684 % ; 1,0701 %]`.
Ce repère ne démontre pas que le PRNG déterministe est une suite IID. Les
contraintes nature/genre valent −1 dans ce harnais ; leurs combinaisons ne sont
pas couvertes par cette mesure. Les arrêts ciblés de ces processus de diagnostic
ne comptent pas comme des fermetures normales de Dolphin.

## Isolation, lanceur et clôture restant ouverte

Les essais instrumentés utilisent Dolphin 2609a et une copie privée avec le
correctif de polling GDB déjà documenté dans
`docs/reverse-engineering/DOLPHIN_RUNTIME_FIXTURES.md`. Cette adaptation de QA
ne change pas le jeu et n'est pas distribuée. Aucun ancien savestate Dolphin
n'est utilisé pour établir la chaîne de persistance de la nouvelle ISO.

`acquisition-100-host2-run.json` consigne une fermeture normale, code natif 0,
après la sauvegarde purifiée ; les fichiers protégés et les **46 fichiers** du
profil personnel suivis sont inchangés. `acquisition-cold-run.json`, qui contient
le rechargement puis le cadeau Posipi et sa sauvegarde, est également terminé
avec le code natif 0 et ces mêmes contrôles de conservation réussis sur les
46 fichiers personnels. La première session visuelle
`visual-100-run.json` finit aussi avec le code 0, mais son inventaire personnel
vide ne constitue pas une preuve de conservation du profil réel.

Deux défauts du lanceur QA sont corrigés : absence d'`APPDATA` désormais refusée
sans chemin personnel explicite, et publication JSON atomique avec réessai borné
face aux verrous temporaires de lecteurs Windows. Les **17 tests dédiés** du
lanceur passent. Ces corrections concernent le dispositif de validation ; elles
ne modifient pas les règles shiny du moteur v0.10.

L'audit global final et le nettoyage des configurations GDB restent à consigner
après les autres essais. Ho-Oh, la conservation d'identité lors d'une réapparition
et le rechargement à froid du nouveau Malosse restent hors des résultats acquis.
Cette passe ne couvre pas une partie complète, toutes les espèces, tous les
événements ou une console physique.
