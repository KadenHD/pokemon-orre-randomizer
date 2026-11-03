# Compatibilité Europe, USA et Japon — version 0.14.0

La version 0.14 accepte les trois ROM Colosseum révision 0 identifiées dans le
[README](../README.md#compatibilité). Elle conserve les mêmes options dans les
trois régions, avec des dispositions de données et des adresses natives propres
à chaque exécutable. Les fichiers originaux restent en lecture seule ; chaque
création produit une image et un rapport séparés.

## Identification et adaptation

L’en-tête sélectionne une région candidate. Le SHA-256 de l’ISO entière, après
décompression d’une RVZ, doit ensuite correspondre exactement à cette région.
Changer un identifiant dans un en-tête ne suffit pas à autoriser un patch.
Les exécutables DOL, les données `common.rel` et les archives des cadeaux et
boutiques possèdent également leurs propres empreintes et contrôles de contenu.
Un mélange de composants de régions différentes est refusé.

| Version | Identifiant | Taille du DOL original | Langues du jeu |
| --- | --- | ---: | --- |
| Europe | `GC6P01` | 4 096 576 octets | Anglais, français, allemand, italien, espagnol |
| USA | `GC6E01` | 3 779 808 octets | Anglais |
| Japon | `GC6J01` | 3 699 680 octets | Japonais |

Les tables partagent les mêmes schémas et comptes : 820 dresseurs, 5 510
enregistrements de Pokémon de dresseur, 413 lignes d’espèces dont les 386 espèces
réelles, 358 capacités et 97 lignes de métadonnées obscures. Leurs positions et
banques de noms diffèrent. Les banques USA portent le tag natif `US` ; les banques
japonaises utilisent leurs en-têtes natifs et des chaînes UTF-16BE.

Les six routines de starters et cadeaux, les constructeurs, les capacités de
départ, les tables d’objets et de CT, les générateurs de PID et les variables
de joueur/mémoire ont été identifiés dans chaque exécutable. Les instructions
et cibles de branchement attendues sont vérifiées avant modification. La
variable SDK `arenaLo` japonaise utilise notamment un déplacement différent ;
les allocations des nouveaux patchs suivent chaque version.

Les régions USA et Japon possèdent une seule archive de boutique, contre cinq
pour PAL. Les patchs ne cherchent donc plus à créer des variantes de langue
absentes. Les noms japonais des pierres restent natifs ; le correctif
d’espacement concerne onze libellés PAL et un libellé USA, sans changement
nécessaire au Japon.

## Cadeaux d’Adelbert et langues

Le script original de la Relique est identique dans les trois régions. Les
quelques différences du script de maison japonais se trouvent hors des zones
modifiées. Les conditions de scénario, identifiants natifs des cadeaux et
indicateurs persistants sont conservés. Les membres non ciblés des archives
restent identiques.

Les cinq nouveaux dialogues suivent la langue native du jeu : cinq traductions
en Europe, anglais aux USA, japonais au Japon. Le japonais utilise de véritables
chaînes UTF-16BE, les contrôles natifs et la typographie pleine chasse. L’interface
de l’outil garde ses six langues, indépendamment de la ROM. Les noms manquants
dans une ROM monolingue proviennent du catalogue traduit déjà fourni avec l’outil
pour l’aperçu ; les noms écrits dans le jeu restent ceux de sa propre banque.

Les validations détaillées des cadeaux PAL, dont sauvegarde et rechargement,
restent décrites dans le [suivi précédent](PURIFICATION_GIFTS_FOLLOWUP_2026-11-02.md).
Les essais USA et japonais ont ensuite validé les deux acquisitions natives,
le rendu des cinq dialogues, une sauvegarde dans le jeu et un rechargement dans
un nouveau processus, suivi du refus d’un second don. La préparation des cartes
QA et les limites des deux contrôles de texte sont détaillées dans le
[suivi Dolphin des cadeaux régionaux](REGIONAL_GIFTS_DOLPHIN_2026-11-03.md).

## Contrôles du moteur et des images

La suite source exécute 386 tests : 384 réussissent et deux sont ignorés. Les
tests régionaux contrôlent notamment les instructions PowerPC des patchs, le
retour des appels natifs et la conservation des registres, les noms japonais,
les boutiques, les exclusions, les CT, les boss et les migrations de profils.
Les trois tests du codec Rust réussissent également.

La matrice de données réelles couvre 18 configurations par région, soit 54 cas
et 108 constructions répétées des patchs. Elle relit les octets finaux et vérifie :

- les 3 355 emplacements de dresseurs référencés et remplis ;
- les 48 familles obscures distinctes lorsque cette règle est active ;
- les stades des starters, filtres de génération, règles des boss et modes avancés ;
- les objets, boutiques, six pierres et noms dans chaque banque native ;
- les décisions chromatiques liées à la seed à 25 % et 100 %, leurs tables
  finales de 5 510 emplacements de dresseurs et 97 lignes obscures ;
- les seuils personnalisés de cadeaux 0/48 et leurs niveaux 17/88 ;
- neuf appels réels de l’aperçu, chacun avec les 54 portraits et les résultats
  des deux starters, quatre cadeaux et 48 obscurs comparés aux données finales.

Les trois RVZ fournies ont ensuite suivi la chaîne de création complète vers
ISO puis RVZ. La redécompression de chaque sortie RVZ retrouve exactement
l’ISO attendue. Le mode copie sur les trois ISO restitue leur SHA-256 original.
Chaque source est réhachée après traitement et reste inchangée.

La régression PAL reproduit à l’identique l’ISO de l’essai v0.13, seed
`purification-rewards-1`, taux chromatique 25 %, au SHA-256
`da8e0d6883231b9d1cb5578895ca469db600de4894a86c0d97c2c960a22121a7`.
Dix-huit compositions DOL ont aussi des octets et rapports identiques aux
sources v0.13 archivées.

## Démarrages dans Dolphin

Les trois images ont été démarrées séparément avec des profils et cartes
mémoire neufs, sans importer de sauvegarde ni de SRAM personnels. Le menu natif,
la saisie du nom, la confirmation de nouvelle partie et le début de
l’introduction ont été parcourus dans chaque région.

Seed : `regional-validation-1`. Les données de l’équipe ont été lues après la
génération et l’attribution natives du propriétaire, sans substitution de
Pokémon, de PID, de script ni de savestate.

| Région | Taux testé | Premier starter | Second starter | Statuts observés dans l’équipe |
| --- | --- | --- | --- | --- |
| Europe | 25 %, liés à la seed | Wattouat, niveau 26 | Kaiminus, niveau 25 | Deux ordinaires, conformes à l’aperçu |
| USA | 25 %, liés à la seed | Wattouat, niveau 26 | Kaiminus, niveau 25 | Deux ordinaires, conformes à l’aperçu |
| Japon | 100 %, liés à la seed | Wattouat, niveau 26 | Kaiminus, niveau 25 | Deux chromatiques, conformes à l’aperçu |

Les espèces, niveaux, expérience et quatre capacités correspondent dans les
six enregistrements. Les statuts chromatiques sont calculés à partir de leurs
PID et identifiants de propriétaire définitifs. Les enregistrements temporaires
observés avant transfert ne suffisent pas à ce dernier contrôle : le jeu leur
attribue encore leur propriétaire après la routine de génération.

Au Japon, l’introduction a également été poursuivie jusqu’au contrôle du
personnage devant le train. Le menu Pokémon affiche les deux starters, leurs
noms japonais, niveaux et portraits chromatiques. Les trois sessions retenues
se ferment normalement avec un code de retour nul. Les empreintes des trois
RVZ originales et de tous les fichiers du profil Dolphin personnel, dont la
carte mémoire et la SRAM, restent identiques avant et après les essais.

Le harnais utilise la copie privée Dolphin 2609a déjà employée par les essais
précédents, avec son correctif d’entrée hôte et des profils isolés. Cette copie
ne fait pas partie de la distribution. Deux premières tentatives de lancement
PAL ont bloqué avant l’initialisation du débogueur ; elles ont été arrêtées et
leur conservation des originaux et du profil personnel a été vérifiée. Les
profils suivants activent la journalisation ; les essais USA/Japon désactivent
le backend SDL DirectInput des joysticks pour éviter un blocage documenté de
l’hôte, tout en conservant le clavier et la manette de test de Dolphin.

Ces essais valident les démarrages et les équipes de nouvelles parties. Ils
ne constituent pas trois parties complètes, ni une répétition de chaque
évolution, achat, capture et combat tardif dans chaque région. Le test sur un
autre PC Windows reste une vérification de distribution distincte.

## Application et reproduction

Les exécutables Windows local et public utilisent le même moteur. Chacun passe
156 états de diagnostic Qt dans les six langues, les deux tailles de fenêtre,
les réglages, les aperçus et les dialogues d’exclusion. Les archives sont
extraites dans un nouveau chemin avec espaces et accents pour le test de
démarrage ; le codec Rust et les ressources de l’édition sont vérifiés.
L’édition publique ne contient ni ROM, ni sauvegarde, ni Dolphin, ni le pack
d’images et de sons du jeu. Les archives de versions précédentes sont conservées.

Les profils v0.13 gardent toutes leurs options, y compris les cadeaux et les
chromatiques. Les nouveaux profils sont des configurations utilisables sur les
trois régions. Le rapport d’une création conserve l’identifiant régional et les
empreintes exactes : une reproduction binaire demande la même ROM, seed,
configuration et version du moteur.

Les preuves contenant des données du jeu restent privées dans
`build/region-compat-2026-11-02/` : inventaires, qualifications REL/DOL,
`matrix/`, `creation-validation.json`, captures et observations `runtime/`.
Elles ne sont pas embarquées dans les sources ou exécutables distribués.
