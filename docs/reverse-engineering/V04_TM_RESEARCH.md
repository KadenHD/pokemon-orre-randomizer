# CT et compatibilités — PAL GC6P01, 31 octobre 2026

Cette enquête et le module `colosseum_randomizer/engine/tm_rules.py` concernent le
DOL original SHA-256
`a788176a45eb88dbd227246a7205ab9856bc79f3cca7e4a0f5376cf466664df5` et le
`common_rel` original SHA-256
`ee2677af555dc59626f978e743235831a76cb23bae93f3fdd1060d808f749d0b`.
Les originaux sont lus, jamais écrits. Les observations ci-dessous sont statiques.

## Structure corroborée et mesures locales

Le schéma primaire [CMTMs.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/enums/CMTMs.swift)
situe la table PAL dans le DOL à `0x3B20D0`, avec huit octets par entrée et un
indice de capacité u16 big endian à `+6`. Il définit 50 CT et 58 CT/CS ensemble :
il y a donc **8 CS**, et non 89 compatibilités. Les CT correspondent aux objets
`0x121..0x152`. Le remplacement d'une capacité y met aussi à jour sa description
d'objet ; recopier un identifiant de description de capacité directement vers
un objet ne suffit pas, car les ressources de texte sont différentes.

La lecture locale confirme 50 capacités CT distinctes. Les six premiers octets
des entrées CT valent `00 00 00 00 00 00`, ceux des CS
`01 00 00 00 00 00`. Les huit capacités CS sont, dans l'ordre,
`15, 19, 57, 70, 148, 249, 127, 291`. Les entrées CT/CS occupent
`[0x3B20D0, 0x3B22A0)`. Les tuples exacts sont vérifiés par le moteur avant édition.
L'observation complète et l'empreinte du DOL sont conservées dans
`analysis/generated/v03-references/pal-tm-original-observations.json`.

Le schéma [CMPokemonStats.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/enumerable/CMPokemonStats.swift)
indique un enregistrement d'espèce de `0x11C` octets, les types à `+0x30/+0x31`
et les compatibilités commençant à `+0x34`, à raison d'un octet booléen par CT/CS.
Les 50 CT occupent donc `+0x34..+0x65`, puis les huit CS `+0x66..+0x6D`.
Les champs d'objets tenus commencent à `+0x70` et ne doivent pas être atteints.

Dans le REL local, la table d'espèces est à `2033100`, contient 413 entrées,
dont 386 espèces avec un numéro national entre 1 et 386. Les 58 octets de chacune
de ces espèces valent exclusivement 0 ou 1. Les 27 entrées supplémentaires sont
préservées. Les octets de CS et les deux octets suivants ne sont pas modifiés.

Le schéma [CMItem.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/enumerable/CMItem.swift)
situe les 397 objets PAL à `0x3ADDA0`, par enregistrements de `0x28` octets.
La description est un u32 big endian à `+0x14`, distinct du nom à `+0x10`.
Les 50 identifiants de description CT lus localement sont `10195..10244`.

## Texte dans les cinq langues

Les ressources originales `pocket_menu.fsys`, `pocket_menu_ge.fsys`,
`pocket_menu_fr.fsys`, `pocket_menu_it.fsys`, `pocket_menu_sp.fsys` contiennent
chacune une table de 631 entrées avec le tag correspondant UK/GE/FR/IT/SP.
Les **50 identifiants CT sont présents dans chacune des cinq tables**. Le contrôle
vérifie leurs bornes et leurs données non vides ; les séquences de contrôle du
texte sont laissées en place. Les empreintes des archives, des membres et des
250 intervalles de texte sont conservées dans
`analysis/generated/v03-references/pal-tm-description-locales.json`.

Le module permute uniquement les 50 capacités CT natives. Chaque capacité emporte
l'identifiant de description de son ancienne CT. Les textes eux-mêmes, leurs
retours à la ligne, leurs traductions et les noms CT01..CT50 restent inchangés.
Cette méthode évite de fabriquer ou de tronquer des traductions. Elle limite
volontairement le choix aux **50 capacités déjà proposées en CT**, sans ajouter
d'autres capacités au catalogue des CT.

Cette vérification porte sur les ressources originales locales. Le moteur reçoit
REL/DOL, pas les archives de texte ; il ne revérifie donc pas ces cinq archives
pour chaque ROM utilisateur. Il ne répare pas une archive déjà modifiée.

## Règles implémentées

Contrat : `apply_tm_rules(original_rel, current_rel, original_dol, current_dol,
seed, options, tables=None) -> (rel, dol, report)`. Le wrapper contrôle les deux
empreintes d'origine et le schéma fourni. Il accepte un DOL courant déjà agrandi,
avec une nouvelle section `text2` et son en-tête, sans les réécrire.

- `randomize_tm_moves` : permutation reproductible des 50 couples
  capacité/description. Un cycle de Sattolo garantit qu'aucune CT ne garde sa
  capacité d'origine. Les 50 capacités natives restent présentes une fois chacune.
- `tm_compatibility_mode="original"` : aucun octet de compatibilité ne change,
  même si les CT sont mélangées ou si la garantie offensive est cochée.
- `"type"` : une CT est compatible si le type de sa capacité finale figure parmi
  les types **finaux** de l'espèce, après une éventuelle randomisation des types.
- `"universal"` : les 386 espèces réelles peuvent apprendre les 50 CT. Cela inclut
  les espèces normalement incapables d'apprendre des CT.
- `"random"` : chaque couple espèce/numéro de CT a une probabilité de 50 %, avec
  un tirage déterministe indépendant des autres couples.
- `tm_ensure_offensive=True` : dans les trois modes de réécriture seulement,
  ajoute au besoin une compatibilité avec une CT offensive. Il préfère le type
  de l'espèce ; faute de candidat, il autorise explicitement une CT d'un autre
  type et le signale. Il ne modifie jamais les capacités elles-mêmes.

Les tirages ont un domaine SHA-256 propre, avec des clés séparées pour permutation,
compatibilité et garantie. Activer une compatibilité ou sa garantie ne change pas
la permutation des CT. La garantie retient les dégâts ordinaires à puissance
supérieure à 1 et les dégâts fondés sur le niveau déjà reconnus par le moteur ;
elle écarte les K.O. en un coup, les suicides et Lutte. Les 50 CT natives ne
contiennent aucune de ces capacités écartées. Le pool local fournit 28 capacités
offensives selon cette définition, réparties sur 16 types. Le type Insecte n'y
dispose pas de CT offensive, d'où le repli explicite possible.

Cette garantie signifie « au moins une CT offensive compatible dans le catalogue ».
Elle ne donne pas l'objet au joueur, ne modifie pas sa disponibilité dans le
scénario, ne promet pas une CT du bon type pour chaque espèce et ne remplace pas
les quatre capacités apprises par le Pokémon.

## Bornes d'édition et validation

Le DOL n'autorise que les deux octets de capacité de chacune des 50 CT et les
quatre octets de description de chacun des 50 objets CT, soit au plus 300 octets.
Les autres champs d'objet, notamment prix, nom, effets et fonctions, sont protégés.
Le REL n'autorise que les 50 octets CT des 386 espèces réelles en mode de
réécriture, soit 19 300 octets. Les rapports contiennent les offsets permis,
le nombre de changements et une vérification intégrale des octets extérieurs.
Les tailles d'entrée sont conservées et les 8 CS restent strictement intactes.

`python -m unittest tests.test_tm_rules -v` : **10 tests passent**, dont une
vérification du PAL original. Ils couvrent la permutation sans point fixe,
l'appariement capacité/description, la reproductibilité, l'indépendance des
tirages, les types courants, le repli offensif, le mode original strict,
les signatures invalides, la liste d'octets autorisés et un DOL courant agrandi.
L'essai du menu d'apprentissage dans Dolphin reste une validation d'intégration
distincte ; cette sous-enquête n'a lancé ni Dolphin ni reçu de CT en jeu.

Les trois sources primaires sont épinglées au commit
`f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0`. Leurs copies, liens et SHA-256 sont
répertoriés dans `analysis/generated/v03-references/tm-research-manifest.json`.
L'implémentation Python est originale ; aucun code Swift tiers n'est intégré
dans l'application.
