# Capacités et dons PAL — observations du 31 octobre 2026

Périmètre : le DOL PAL GC6P01 révision 0, SHA-256
`a788176a45eb88dbd227246a7205ab9856bc79f3cca7e4a0f5376cf466664df5`,
et les tables du `common_rel` original déjà fingerprinté. Les observations sont
statiques sauf indication contraire ; aucun essai Dolphin n'a été lancé dans
cette sous-enquête.

## Données de dresseurs

Les quatre indices de capacité sont les u16 à `+0x36/+0x3E/+0x46/+0x4E` d'un
enregistrement de 0x50 octets. Les blocs sont espacés de huit octets. Les exemples
locaux montrent leurs six octets précédents nuls pour les capacités ordinaires.
Le schéma communautaire lit et écrit seulement les u16 ; il n'identifie pas de
champ PP de dresseur dans ces blocs. Ne pas inventer un champ PP à modifier.

Les marqueurs lus comme `0xFFFF` sont, dans les cas examinés, des mots u32 complets
`0xFFFFFFFF` à `+0x34/+0x3C/+0x44/+0x4C`. Leur signification à l'exécution reste
non établie ici. Les protéger et laisser intacts les autres octets du bloc.

Le pool normal doit exclure 0, 355, 357 (entrées absentes/spéciales), 356 (Charge
Noire) et 165 (Lutte). Les options de restriction peuvent retirer les effets de
K.O. en un coup (indices 12, 32, 90, 329, effet 38 observé) et les attaques suicide
(120, 153, effet 7). Les indices, noms et effets sont corroborés par la table locale.

## Starters et cadeaux : deux mécanismes différents

Les starters ont quatre instructions `li r5, capacité` aux bases DOL existantes
de Noctali/Mentali plus `0x14/0x24/0x34/0x44`, donc les u16 à
`+0x16/+0x26/+0x36/+0x46`. Les `li r4, emplacement` précédentes donnent 0 à 3.
Les huit branches qui suivent ciblent toutes le setter natif RAM `0x80127ECC`.
Valeurs d'origine : Noctali `[44,290,269,289]`, Mentali `[93,216,115,270]`.

Les quatre cadeaux utilisent le constructeur natif RAM `0x80128238`, puis leurs
propres opérations de métadonnées. Le lecteur primaire décrit des capacités
dérivées des apprentissages par niveau. Leurs bases n'ont pas les quatre mêmes
immediates que les starters : écrire aux mêmes offsets corromprait des instructions
sans rapport. Modifier seulement les apprentissages toucherait aussi les autres
spécimens de la même espèce, ce qui ne fournit pas une option de cadeau indépendante.

`engine/gift_move_hooks.py` apporte donc une branche spécifique au constructeur
de chaque cadeau demandé, dans une nouvelle section DOL `text2`. Le wrapper appelle
le constructeur original, assigne les quatre capacités avec le setter natif, puis
rend le résultat original du constructeur. Il conserve SP, LR et les registres
non volatils r30/r31. Les arguments originaux sont remis au constructeur ; les
paramètres, conditions d'événement et opérations de métadonnées restent en place.

## Réservation explicite du code ajouté

Les sections initialisées et les trois zones de BSS remplissent leur intervalle
utile jusqu'à `0x804CBCB8` ; les trous entre .sdata et .sdata2 ne sont pas libres.
Le SP initial vaut `0x804DBCB8`. La valeur basse d'arène native par défaut est
`0x804E3CC0`, construite dans OSInit par les mots `3C60804E / 38633CC0`.

La section ajoutée commence précisément à `0x804E3CC0`, au-dessus du BSS et des
piles originales. La feuille native `OSSetArenaLo` à `0x8009E4F0` contient
`906D8168 / 4E800020`. Sa première instruction branche désormais vers un garde
qui stocke le maximum de l'argument original et de la fin de section alignée à
32 octets ; r3 reste inchangé. Le getter à `0x8009E4E0` lit la même variable.

Les branches originales à `0x8009D088` et `0x8009D0C4` appellent ce setter, avant
l'appel ClearArena de `0x8009D2D0`. ClearArena lit ce getter avant ses mises à zéro.
La borne inclut donc le code ajouté avant le premier effacement d'arène, y compris
les chemins qui prennent une borne fournie en mémoire basse ou le repli de debug.
Le programme de démarrage ne peut pas effacer cette section par ses zones BSS
d'origine, qui se terminent plus bas. La borne haute par défaut observée est
`0x81700000`, largement au-dessus de la section ajoutée.

Les quatre wrappers prennent 128 octets chacun, le garde 32 : 544 octets ajoutés
au DOL pour quatre cadeaux. Seuls trois mots du descripteur text2, la première
instruction du setter d'arène et les appels constructeur sélectionnés changent
dans le DOL préexistant. Le module vérifie cette liste exacte et tous les opcodes
de départ. Le reconstructeur ISO doit déplacer le DOL agrandi dans une zone sûre
et adapter le pointeur de boot, plutôt que d'écraser la FST qui suit l'ancien DOL.

Six tests passent : interprétation indépendante du sous-ensemble PPC émis, appels
et ABI sous écrasement des registres volatils, deux branches du garde, bornes des
branches, descripteur DOL, liste d'octets permise et signatures d'origine. Ces tests
ne remplacent pas un cold boot et l'observation d'un cadeau effectivement reçu.

La source communautaire propose aussi d'effacer des fonctions TRK entre RAM
`0x800C1948..0x800C7B9C` ; la carte PAL corrobore leurs noms. Cette approche n'est
pas retenue : la section ajoutée et réservée évite d'effacer un ancien sous-système.

## Objets tenus

Table locale du DOL : `0x3ADDA0`, stride 0x28, 397 entrées ; nom u32 `+0x10`,
interdiction de porter u8 `+1`, effet tenu u8 `+0x0B`. Les noms sont résolus dans
les textes français du REL. Exemples vérifiés : 183 Vive Griffe, 186 Bandeau Choix,
196 Bandeau, 198 Lentilscope, 200 Restes, 219 Grelot Coque, 179 Poudreclaire,
180 Herbe Blanche, 185 Herbe Mental, 187 Roche Royale, 221 Encens Doux.

Les baies 133..142 et 168..172 ont des effets tenus. Un sous-pool générique utile
peut les combiner avec ces objets. Le Bandeau Choix mérite un filtrage selon les
attaques physiques si une utilité systématique est promise. Les objets 110 et
254..258 ont un effet tenu nul (Pépite et foulards). Éviter génériquement 181
(Brac. Macho), 191 (Rosée Âme), 192/193 (objets Coquiperl) et 202 (Balle Lumière),
dont l'intérêt est d'entraînement ou limité à certaines espèces.

## Sources et provenance

Sources primaires épinglées au commit `f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0`
de [Pokemon-XD-Code](https://github.com/PekanMmd/Pokemon-XD-Code/tree/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0) :
`CMTrainerPokemon.swift`, `XGDemoStarterPokemon.swift`, `CMGiftPokemon.swift`,
`CMItem.swift`, `CMItems.swift`, `XGMove.swift`, `XGMoves.swift`,
`XGAssemblyCode.swift`, `XGAssemblyCodeExtensions.swift`, `XGPatcher.swift`.
Carte primaire : [GC6P01.map](https://github.com/StarsMmd/Colo-XD-PBR-symbol-maps/blob/93d5da920e7f03b8854b79963d94739ec66abd1d/GC6P01.map).
Copies et empreintes : `analysis/generated/v03-references/`, hors distribution.
Le code de l'application n'intègre pas l'implémentation Swift de ces outils.
