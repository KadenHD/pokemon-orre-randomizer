# Préparation de fixtures et contrôles RAM sous Dolphin 2609a

Cette recherche du 31 octobre 2026 ne change aucune ISO ni sauvegarde originale.
Les transformations de RAM décrites ici préparent des conditions de test dans
une instance Dolphin isolée. Elles ne prouvent pas qu'un événement de scénario
normal est accessible ; les observations en jeu doivent être consignées à part.

## Client privé et protocole

`build/dolphin-validation/tools/dolphin_rsp.py` est un client RSP de diagnostic,
hors distribution. Il ne lance pas Dolphin. Il se connecte uniquement à
`127.0.0.1`, vérifie `GC6P01` en RAM et garde la connexion pendant tout le boot.
Une console JSON ligne par ligne permet les lectures, interruptions, points
d'arrêt et écritures de fixture. Toute écriture mémoire exige la valeur attendue
avant modification et une relecture identique après. Les adresses sont limitées
au MEM1 GameCube mis en cache, `0x80000000..0x817FFFFF`.

Les sources officielles du tag 2609a, commit
`409881c34357d0f105fd473167d15ab0bd9c1628`, établissent que :

- `[General] GDBPort` active le serveur TCP également sous Windows. Seul le
  transport par socket Unix est exclu sous Windows. Le CPU démarre suspendu.
- Le serveur accepte une connexion pour le boot. Il écoute sur toutes les
  interfaces ; il faut réserver cette configuration au profil de QA temporaire.
- `m`/`M` lisent/écrivent la mémoire ; `p`/`P` lisent/écrivent un registre.
  Le client n'utilise pas les commandes groupées `g`/`G` : `g` n'expose que les
  32 GPR et `G` lit le buffer depuis son caractère de commande.
- Les registres 0..31 sont les GPR, 32..63 les valeurs PS0 des FPR, 64 le PC,
  65 le MSR, 66 le CR, 67 le LR, 68 le CTR, 69 le XER et 70 le FPSCR.
  Une capture de ces registres n'est pas un état complet de l'émulateur : PS1,
  mémoire, MMU et ordonnanceur ne sont pas couverts.

Le binaire local contient les chaînes `GDBPort`, `Waiting for gdb to connect`
et `GDBStubUpdate`. Ce constat statique indique que le support est compilé ;
la connexion et les lectures RAM doivent encore être observées dans le journal
du cas exécuté.

Sources : [configuration](https://github.com/dolphin-emu/dolphin/blob/409881c34357d0f105fd473167d15ab0bd9c1628/Source/Core/Core/Config/MainSettings.cpp),
[démarrage](https://github.com/dolphin-emu/dolphin/blob/409881c34357d0f105fd473167d15ab0bd9c1628/Source/Core/Core/Core.cpp),
[protocole](https://github.com/dolphin-emu/dolphin/blob/409881c34357d0f105fd473167d15ab0bd9c1628/Source/Core/Core/PowerPC/GDBStub.cpp).

### Réponse supplémentaire après Ctrl-C

Une interruption a révélé un décalage d'une réponse dans le premier client.
Après le paquet `T05`, la lecture d'un registre recevait un paquet vide, puis
chaque lecture recevait la réponse précédente. Un drainage et deux lectures PC
identiques ont rétabli l'alignement avant toute écriture mémoire.

La source 2609a explique ce comportement : `ReadCommand` appelle `SendSignal`
pour Ctrl-C ; cette fonction remplace le buffer partagé et sa longueur.
`ProcessCommands` interprète ensuite le caractère `$` de cette réponse comme
une commande inconnue et envoie une réponse vide. Le client corrigé consomme ce
paquet supplémentaire immédiatement après un Ctrl-C réellement envoyé. Une
arrivée sur point d'arrêt naturel n'ajoute pas ce drainage. Un test de régression
vérifie que les registres ne peuvent plus se décaler ainsi.

Ne pas reconnecter un second client pour essayer de récupérer un protocole
désynchronisé. Ne pas envoyer d'écriture tant que deux lectures indépendantes
du PC et une signature mémoire ne correspondent pas au contexte attendu.

Le parseur distingue aussi les erreurs RSP exactes `Ehh` des données hexadécimales
commençant par `E`. Une capture mémoire dont le premier mot était `EC220...`
avait été refusée à tort ; le paquet restait entièrement consommé, sans décalage
de protocole. La correction et sa régression sont présentes dans le client pour
les processus suivants. Un client JSONL déjà lancé n'offre pas de rechargement de
module à chaud ; il faut terminer le boot normalement avant de le remplacer.

### Polling Windows et activation des breakpoints JIT

La source 2609a programme `GDBStubUpdate` toutes les 100 000 cycles émulés.
Chaque passage appelle `ProcessCommands(false)`, puis `IsDataAvailable`, qui
attend avec `select` et un timeout de **20 microsecondes** même lorsque le CPU
a repris après `c`. Ce polling ne se fait pas à chaque instruction. Sur cet
hôte Windows, une mesure indépendante sur une socket UDP privée, sans
connexion à Dolphin, donne environ **15,3 ms** pour `select(20 µs)`, contre
**1,7 µs** pour `select(0)`. Les 100 échantillons de chaque mode sont dans
`build/dolphin-validation/gdb-select-poll-cost.json`. Cela explique un coût
potentiel de plusieurs dizaines de secondes par seconde émulée ; ce calcul
reste une estimation, pas une mesure de la vitesse du jeu.

Un correctif de l'émulateur réservé à la QA est préparé sous
`build/dolphin-validation/patched/Dolphin.exe`. L'original portable et
`Dolphin-x64/Dolphin.exe` restent identiques à leur empreinte officielle lors
de cette préparation. Le script refuse toute autre empreinte, vérifie l'unicité
de l'instruction, puis change un seul octet à l'offset `0x3BFE15`, `14 → 00`.
L'instruction à `0x1403C0A0F` devient `mov dword ptr [rbp+0x2CC],0`. L'appel
qui suit vise l'import `WS2_32.dll`, ordinal 18 (`select`), et sa branche
d'erreur référence la chaîne `select failed`. Les en-têtes PE et le checksum
optionnel original absent (`0`) sont préservés. Un test statique vérifie ces
propriétés et refuse de repatcher la sortie. Le rapport est
`build/dolphin-validation/dolphin-gdb-poll-fix.json`.

Ce binaire Dolphin modifié sous GPL-2.0-or-later reste privé et hors des
distributions du randomizer. Sa nouvelle empreinte est
`baa731a95136d50ddfe4b16e9449f66b565027f74e705e7708e531d07b49ba8e`.
La préparation n'établit pas son fonctionnement : le boot suivant doit
constater le gain de vitesse et l'arrêt sur breakpoint. La vérification de
l'ISO livrée inclut aussi un lancement avec l'émulateur officiel sans GDB.

Les breakpoints JIT64 sont conditionnés par `IsDebuggingEnabled()`, qui exige
`[Interface] DebugModeEnabled = True` et l'absence de mode hardcore. Le simple
`[General] GDBPort` n'active pas cette option. Ajouter un breakpoint via RSP
invalide le cache JIT, mais ne change pas cette configuration. Le JIT64 convient
donc aux tests, à condition d'activer le débogage avant le boot ; passer en
Interpreter n'élimine pas le coût du polling. L'option
`[Interface] PauseOnFocusLost` a pour valeur par défaut `False`.

Sources : [JIT64](https://github.com/dolphin-emu/dolphin/blob/409881c34357d0f105fd473167d15ab0bd9c1628/Source/Core/Core/PowerPC/Jit64/Jit.cpp),
[configuration](https://github.com/dolphin-emu/dolphin/blob/409881c34357d0f105fd473167d15ab0bd9c1628/Source/Core/Core/Config/MainSettings.cpp),
[sémantique Windows de select](https://learn.microsoft.com/en-us/windows/win32/api/winsock2/nf-winsock2-select).

## Identité PAL et structures Pokémon

DOL original : SHA-256
`a788176a45eb88dbd227246a7205ab9856bc79f3cca7e4a0f5376cf466664df5`.
REL original : SHA-256
`ee2677af555dc59626f978e743235831a76cb23bae93f3fdd1060d808f749d0b`.

Les instructions du DOL confirment le format CK3 utilisé pour les captures des
starters et les fixtures de sauvegarde :

| Propriété | Offset objet | Corroboration native PAL |
| --- | --- | --- |
| Espèce interne | `+0x00`, u16 | setter `0x80121FCC`, appelé par sélecteur `0x6E` |
| EXP | `+0x5C`, u32 | setter `0x80121E74`, sélecteur `0x79` |
| Niveau | `+0x60`, u8 | setter `0x80121E24`, sélecteur `0x7A` |
| Quatre capacités | `+0x78`, pas 4 | helper `0x8012323C`, calcul final `+0x78 + slot*4` pour un non-obscur |
| Identifiant obscur | `+0xD8`, u16 | lu dans le même helper |
| Jauge de purification | `+0xDC`, i32 | même helper, comparaison signée avec zéro |

Dans les routines de création des starters, `SP+8` contient l'objet de 312 octets
après initialisation. Aux adresses `0x80134DB4` (Mentali) et `0x80134EDC`
(Noctali), `r4` pointe déjà vers cet objet, avant son ajout à l'équipe. La copie
du premier se fait par un appel à `0x80134DC0`. Lire l'objet avant cette copie
permet de vérifier les données réellement construites, sans les réécrire.

Après création des starters, la racine joueur se lit en u32 big endian à
`0x804C8268` (`r13-0x5A58`), getter `0x8012CFD8`. L'appel natif
`0x8012E7A8(0,3,index)` retrouve le dresseur à `racine+0x70` via
`0x8012CFA0`, puis le Pokémon à `dresseur+0x30+index*0x138` via
`0x8012EE34`. L'équipe active est donc constituée de six CK3 contigus à
`racine+0xA0`. Le u32 précédent, à `racine+0x9C` (getter `0x8012EE68`),
est utilisé comme identifiant de dresseur par les constructeurs : ce n'est
**pas un nombre de membres**. Une première hypothèse de compteur a été
rejetée à la lecture runtime ; les emplacements vides se vérifient par leur
espèce nulle. Vérifier que la racine et toute la plage restent en MEM1 avant
lecture. Cette chaîne permet de lire l'équipe sans chercher des copies
temporaires dans un dump de toute la RAM.

Les noms communautaires de la carte GC6P01 servent à orienter la recherche ; les
instructions et les champs ci-dessus ont été lus dans le DOL exact.

## Combats de boss

La table des combats est au symbole REL 50, offset `0x1D6824`, avec 566 entrées
PAL de `0x48` octets. Sa fin correspond exactement au symbole 52. Les quatre
participants commencent à `+0x28`, avec un pas de 8 : identifiant dresseur u16,
puis contrôleur u32 à `+4`. La structure communautaire Colosseum nécessite donc
de prendre en compte les 16 octets PAL supplémentaires avant les participants.

| Chef | Identifiant combat | Identifiant dresseur |
| --- | --- | --- |
| Bouledisco | 164 | 162 |
| Dakim | 213 | 211 |
| Vénus | 328 | 326 |
| Teck | 405 | 403 |
| Helgonza | 427 | 425 |
| Jakylla | 439 | 437 |
| Nosfrat | 441 | 439 |

Le dispatcher natif des fonctions de script se trouve dans le DOL à
`0x320508`, avec un pas de 12 octets. Son entrée 102 pointe sur `0x80212538`.
Cette fonction prend l'identifiant de combat dans `r3` et lit les vraies tables
de l'image chargée.

Une fixture peut intercepter l'entrée de cette fonction lors d'un combat NPC
déclenché normalement, vérifier la valeur de `r3`, puis remplacer seulement cet
argument par l'un des identifiants ci-dessus. L'affichage et le combat emploient
alors les vrais enregistrements du boss, sans patch de ROM. Cette méthode ne
valide pas les dialogues ou drapeaux du scénario entourant la rencontre normale.
Une nouvelle partie évite que les obscurs soient déjà capturés dans la sauvegarde.

Source de structure : [CMBattle](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/enumerable/CMBattle.swift),
[définition des tables](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/struct%20tables/Battles.swift).

## Changements de salle

Le bootstrap fixe `r13 = 0x804CDCC0`. Le getter de salle `0x80102A80`
lit un pointeur à `0x804C8178`, déréférence son premier mot puis lit l'identifiant
de salle à `+8` de ce second objet. Les pointeurs doivent rester dans MEM1.

La fonction de script 95, `0x801170CC`, prend `r3 = salle` et `r4 = entrée`.
Elle écrit la structure à `0x804557F8` : salle précédente u32 à `+0`, suivante
u32 à `+4`, activation u8 à `+8`, entrée u32 à `+0xC`, puis appelle le moteur de
transition `0x80102AA0`. Préférer un point d'arrêt sur une transition naturelle,
plutôt qu'un saut arbitraire du PC dans une fonction avec un contexte inconnu.

Identifiants corroborés par la table PAL et le catalogue primaire :

- `0x01` : extérieur de la Station Service ; `0x02` : intérieur.
- `0x03` : extérieur de Phénacit ; `0x09` : boutique de Phénacit.
- `0x0F` : extérieur de Pyrite ; `0x16` : boutique de Pyrite.
- `0x27` : sanctuaire de Samaragd ; `0x385` : une variante de ce sanctuaire.

Ne pas confondre les identifiants hexadécimaux avec le décimal : la salle 27
décimale est `0x1B`, pas `0x27`.

Source : [XGRoom](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/enumerable/XGRoom.swift),
[catalogue des salles](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/JSON/Colosseum/Room%20IDs.json).

## Drapeaux : préparation masquée de coffre et d'obscur

Le getter de drapeau PAL est `0x80194A14`, son setter `0x80194AD0`. Leurs
instructions décodent les champs de la manière suivante :

1. Pointeur de descriptions u32 à `0x804C643C`, entrée de 8 octets par ID.
2. L'octet initial contient le groupe dans ses deux bits hauts et la largeur
   dans ses six bits bas. Le décalage en bits est le u16 de l'entrée à `+4`.
3. Pointeur des groupes u32 à `0x804C638C`. Le pointeur des données du groupe
   est le u32 à `tableGroupes + groupe*8 + 4`.
4. Le mot se trouve à `base + 4*(décalage>>5)`. Les mots sont big endian, avec
   numérotation des bits depuis le bit faible. Un champ peut occuper deux mots.

Le client privé vérifie les signatures intégrales du début des deux fonctions
et `r13` avant de proposer `flag` ou `set_flag`. Les écritures sont limitées aux
drapeaux de trois coffres et aux sept booléens de capture des boss identifiés. Elles
préservent les bits voisins et exigent la valeur attendue avant modification.
Cela prépare une fixture sans appel CPU injecté ni supposition sur un offset SAV.

Le coffre de table n°1 est en salle `0x03`, Phénacit, drapeau 152, position
`(-153.04, 32.99, 84.22)`. Le n°7 est en salle 27 décimale (`0x1B`), drapeau
158 ; le n°42 est en salle 38 décimale (`0x26`), drapeau 193. Une remise à zéro
se fait avant de recharger la salle, puis la collecte reste une action du joueur.

Le script 243 pointe sur `0x801F2EF0`. Il retrouve les métadonnées obscures via
le pointeur à `0x804C640C`, avec un pas de `0x38`. Les u16 à `+0xC` et `+0x1C`
de chaque entrée sont des **identifiants de drapeaux**, pas des états à écraser
directement. La fonction met le premier à 1 et le second à son argument `r4`.

| Groupe obscur | Drapeau vu | Drapeau état |
| --- | --- | --- |
| 19 | 1184 | 2374 |
| 21 | 1186 | 2376 |
| 23 | 1188 | 2378 |
| 34 | 1199 | 2389 |
| 38 | 1203 | 2393 |
| 43 | 1208 | 2398 |
| 44 | 1209 | 2399 |

### Capture et purification indépendantes de l'état de rencontre

Le champ `+0x1C` ne suffit pas à décider si un Pokémon obscur a été capturé.
Son getter `0x801F2E88` lit un entier signé de huit bits. Le seul appel natif
direct au setter, à `0x801D69C0`, augmente cet entier lorsqu'une valeur fournie
par une table d'événements est plus grande. Aucune énumération globale
`0=inconnu, 1=vu, 2=capturé, 3=purifié` n'a été établie. Le client laisse cet
état en lecture seule.

La capture est un **booléen distinct**, dont l'identifiant est stocké à
`metadata+0x12`. Le getter `0x801F3344` lit ce drapeau et le setter
`0x801F33A8` l'écrit. À `0x8008CECC`, la construction d'un Pokémon de dresseur
lit ce getter avec l'identifiant obscur de l'enregistrement à `+2` et saute
l'initialisation si le résultat vaut 1. Le chemin d'acquisition à `0x802187A8`
appelle `0x80127454` avec `r4=1` ; cette routine met le drapeau `+0x16` à 1,
puis celui de capture `+0x12` à 1. La purification est un troisième booléen,
stocké à `metadata+0x14`, getter `0x801F34E8`, setter `0x801F354C`. La routine
de purification l'écrit à 1 à `0x80263554`, après avoir lu l'identifiant obscur
du Pokémon.

| Groupe | Capture `+0x12` | Purification `+0x14` | Rencontre `+0x16` |
| --- | --- | --- | --- |
| 19 | 2144 | 1280 | 1376 |
| 21 | 2146 | 1282 | 1378 |
| 23 | 2148 | 1284 | 1380 |
| 34 | 2159 | 1295 | 1391 |
| 38 | 2163 | 1299 | 1395 |
| 43 | 2168 | 1304 | 1400 |
| 44 | 2169 | 1305 | 1401 |

La commande `{"op":"shadow","id":19}` lit les cinq drapeaux séparés et
conserve leurs valeurs brutes. Elle vérifie les identifiants de la ligne PAL
corroborée. Pour préparer une copie où le boss 19 est de nouveau disponible,
`{"op":"set_flag","id":2144,"value":0,"expected":1}` remet uniquement
le booléen de capture à zéro, avant la construction du combat. Cela ne recrée
ni le parcours normal ni une sauvegarde cohérente à conserver : c'est une
fixture RAM privée, à abandonner après le test. Une relecture et une observation
du véritable combat restent nécessaires. Les drapeaux de purification, de vue
et de progression ne sont pas réécrits.

Les plages d'instructions et les lignes REL originales sont conservées dans
`analysis/generated/dolphin-runtime-references/pal-shadow-native-instructions.json`.

Les sources et leurs empreintes sont conservées localement dans
`analysis/generated/dolphin-runtime-references/manifest.json`. Les onze tests
privés du client couvrent les bornes MEM1, les préconditions, les relectures,
les paquets fragmentés, les registres individuels, le drainage Ctrl-C de 2609a et
la préservation des bits voisins, y compris lorsqu'un champ traverse deux mots,
et la séparation des drapeaux obscurs sans déduire la capture de l'état brut.
