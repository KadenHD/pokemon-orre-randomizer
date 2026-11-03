# Textes de l’interface

L’outil s’adresse à des joueurs qui choisissent leur ROM et leurs réglages.
Les textes doivent expliquer l’effet d’une option ou l’action suivante.

Les trois choix du mode Simple sont des points de départ, pas des réglages
personnalisés :

| Français | Anglais | Japonais | Portée |
| --- | --- | --- | --- |
| Pokémon + capacités | Pokémon + moves | ポケモン＋わざ | Pokémon de puissance proche, capacités et apprentissages, CT, coffres et boutiques |
| Pokémon seuls | Pokémon only | ポケモンのみ | Pokémon remplacés sans équilibrage ; capacités, apprentissages et CT conservés |
| Copie à l’identique | Unchanged copy | そのままコピー | Données du jeu inchangées, conversion ISO/RVZ possible |

Les descriptions précisent les Pokémon concernés et les aides communes aux deux
modes randomisés : évolutions, vente de pierres et familles d’obscurs différentes.
Le texte « réglages personnalisés » apparaît quand les options diffèrent des trois
choix prédéfinis. Il indique comment les consulter en Avancé et que sélectionner
un choix prédéfini les remplace. Les valeurs des trois jeux d’options sont inchangées.

« Voir les starters » est une action explicite pour révéler le tirage. Avant le
calcul, la légende nomme les portraits d’origine. Après le calcul, elle confirme
la correspondance avec la seed et les réglages. Une modification remplace le
résultat par les originaux avec une invitation à recalculer ; un changement de
langue traduit le résultat déjà calculé sans relancer le tirage. Les noms japonais
des 386 espèces viennent du jeu de données PokéAPI, sous sa licence conservée
dans `licenses/pokeapi.txt` ; la sélection et l’empreinte sont dans
`licenses/pokeapi-names.json`. Les noms français et anglais et les portraits sont
lus dans la ROM choisie. Aucun service externe n’est appelé pendant l’aperçu.

| Français | Anglais | Usage |
| --- | --- | --- |
| ROM d’origine | Original ROM | Fichier sélectionné par le joueur, toujours conservé |
| Nouvelle ROM | New ROM | Fichier créé par l’outil |
| Réglages | Settings | Choix qui déterminent la partie |
| Profil | Profile | Fichier contenant la seed et les réglages |
| Capacités | Moves | Employer le terme Pokémon, y compris pour une capacité offensive |
| Talents | Abilities | Ne pas confondre avec les capacités |
| Pokémon offerts | Gift Pokémon | Pokémon reçus en cadeau ou en récompense |
| Famille d’évolution | Evolution family | Espèces reliées par une évolution |

- Les boutons nomment l’action : « Créer la ROM », « Ouvrir le rapport ».
- Les cases décrivent leur effet : « Remplacer Noctali », « Garder les soins en boutique ».
- Les aides expliquent le comportement au présent. Elles gardent les limites
  utiles : niveau 40, prix des pierres, seuil de statistiques, etc.
- Les introductions de rubrique tiennent en une ou deux phrases. Elles ne
  répètent pas la liste des options.
- Une erreur indique ce qui bloque et comment reprendre. Les détails internes
  ne remplacent pas cette explication.
- Éviter les slogans, les répétitions et les termes internes comme « routine
  identifiée », « octets natifs » ou « marqueurs » dans le parcours courant.
- Les noms de réglages, les paramètres de traduction, les valeurs du profil et
  la seed sont distincts. Une reformulation ne change pas les tirages.

Les libellés français sont dans `options.py` et `gui.py`. Les catalogues anglais
et japonais sont dans `locales/en.py` et `locales/ja.py`. Toute modification doit
rester cohérente dans les trois langues et conserver le sens des options.

En japonais : わざ pour les capacités, とくせい pour les talents, 種族値 pour les
statistiques de base et ダークポケモン pour les obscurs, selon la
[présentation japonaise officielle](https://www.pokemon.co.jp/game/other/colosseum/).
La purification est le [リライブ](https://www.nintendo.co.jp/ngc/gxxj/snatch/index.html).
Les noms de fichiers, seeds, identifiants de réglages et champs de formatage sont
conservés littéralement. Les textes japonais utilisent des polices système avec
repli sur Yu Gothic UI, Meiryo et Noto Sans CJK JP ; aucun fichier de police propriétaire
n’est distribué avec l’application.
