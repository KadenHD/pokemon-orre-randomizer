# Application v0.4 : CT, coffres, boutiques et boss

Cette version ajoute dix paramètres : sept booléens de changement/protection,
deux autres booléens de boss et un mode de compatibilité. Le total est de
52 paramètres, dont 47 booléens, dans quatorze catégories natives.
Le moteur est `tm-items-boss-rules-v6`.

## CT

- `randomize_tm_moves` permute les 50 capacités CT originales, sans point fixe.
  Ce n'est pas un tirage parmi toutes les attaques du jeu.
- Chaque description d'objet CT suit sa capacité, dans les cinq langues.
  Les chaînes et noms d'objet restent intacts ; seuls les identifiants de
  description sont déplacés.
- `tm_compatibility_mode` : `original`, `type`, `universal` ou `random`.
  Le mode par type utilise les types finaux, même s'ils sont randomisés.
- `tm_ensure_offensive` garantit une CT offensive compatible dans les modes de
  réécriture. Un type sans CT offensive native, notamment Insecte, peut recevoir
  une compatibilité hors type ; ce repli est signalé dans le rapport.
- Les huit capacités CS et leurs huit octets de compatibilité restent intacts.
  Le mode `original` conserve tous les octets de compatibilité, même si la
  garantie est cochée. Une compatibilité ne donne pas l'objet CT au joueur.

## Coffres et boutiques

`randomize_field_items` modifie les identifiants d'objets dans la table vérifiée
des 74 trésors PAL. Avec les protections recommandées, 38 placements sont
admissibles. Les clés, Flûtes du Temps, pierres et cases vides sont protégées.
Les quantités, modèles, coordonnées, salles et drapeaux de réception ne changent
pas. Les objets donnés par des scripts de personnages restent hors périmètre.

`randomize_shop_items` transforme les six stocks identifiés 3, 4, 5, 6, 7 et 9.
Un mapping global sans doublon préserve les suffixes communs aux catalogues et
reste dans l'allocation native de 122 entrées. Les huit autres listes conservent
leur stock courant ; les menus, monnaies et articles à prix nul restent protégés.
Les parfums de purification de poche spéciale restent également d'origine.

Les remplacements gardent une catégorie d'usage identique. Trois protections
sont réglables :

- `items_similar_value` : prix entre la moitié et le double du prix natif,
  pour les coffres et les stocks.
- `keep_capture_items` : conserver les Balls présentes, pour les deux surfaces.
- `shop_keep_healing` : conserver les objets de soin et d'usage en combat vendus.

Les deux ajouts de pierres existants restent indépendants. Leur composition
avec la randomisation des stocks préserve les six pierres disponibles dans les
boutiques choisies. Les cinq archives de langue reçoivent les mêmes tables ;
leurs onze autres membres restent identiques après décompression.

## Boss

Les deux réglages s'appliquent à Bouledisco, Dakim, Vénus, Teck, Helgonza,
Jakylla et Nosfrat : 32 variantes identifiées, 161 slots peuplés, dont 16 obscurs
protégés et 145 non-obscurs admissibles. Aucune identification par simple seuil
de niveau n'est utilisée.

- `boss_stronger` : niveau courant +10 %, après le multiplicateur global, borné
  à 100 ; IV minimum 20 et EV minimum 64/stat si le total ne dépasse pas 510.
  Les valeurs existantes ne sont pas abaissées.
- `boss_team_variety` : remplacer les doublons de famille modifiables selon les
  filtres d'espèces. Les capacités sont recalculées pour les espèces rerollées
  si leur randomisation est activée, avec les types finaux.

Les obscurs, marqueurs spéciaux, slots vides, scripts et tailles d'équipe sont
conservés. Les doublons impossibles à résoudre sans toucher ces protections sont
signalés et conservés. La règle des 48 familles obscures reste indépendante.

## Presets et reproduction

Le preset recommandé ajoute les CT selon les types, les coffres, les stocks avec
soins conservés et la variété des boss. Le renforcement des boss reste désactivé.
Les nouveaux changements restent désactivés dans les valeurs de base de la CLI,
pour conserver les anciens usages. Exemples d'options :

```
--randomize-tm-moves --tm-compatibility-mode type --randomize-field-items
--randomize-shop-items --no-shop-keep-healing --boss-stronger --boss-team-variety
```

Le rapport JSON local dans `build/v04-qa/` consigne la seed, les options et les tirages
de validation.

## Références et limites

Les observations binaires, sources primaires épinglées et bornes de recherche
sont détaillées dans [CT](reverse-engineering/V04_TM_RESEARCH.md),
[objets](reverse-engineering/V04_ITEMS_RESEARCH.md) et
[boss](reverse-engineering/V04_BOSS_RESEARCH.md).
La validation des octets et invariants ne certifie pas l'équilibrage ni un
scénario complet joué. Les contrôles sous Dolphin sont consignés séparément
avec les résultats observés.

## Validation locale

**147 tests Python et trois tests Rust passent.** Ils couvrent les 50 CT,
386 espèces, huit CS conservées, descriptions appariées, compatibilités avec
types finaux, coffres et marqueurs protégés, matching des stocks sans doublon,
capacité de 122 entrées, cinq langues et règles de boss composées avec les
autres randomisations. Les profils temporaires de conversion ont leurs propres
tests d'erreur et d'annulation.

| Essai | Résultat |
| --- | --- |
| Préréglage recommandé, seed historique de test | ISO SHA-256 `9699bea0c4b16f7baf8e98cf7555d665c977d26d944b0ff444ae2a90760e81c1` |
| Deuxième construction depuis la même source | SHA-256 identique |
| Exécutable Windows, même seed/preset | Même ISO, succès à 100 %, 10,78 s observées |
| Tous changements désactivés | ISO strictement identique à la source `1e3b4aa806ac3367cca13496f7701137e9437e7bac0101f75b9b137633a10aa9` |
| RVZ → RVZ avec règles avancées et 145 slots de boss renforcés | ISO après redécompression SHA-256 `b926659b65792834b07d61c7107a1ab89999074a9bbea61578f83ab81e7a18a1` |
| Même essai RVZ après correctif du profil de conversion | Même ISO, roundtrip vérifié, 21,72 s, aucune fenêtre bloquante |
| Exécutable Windows final, RVZ → RVZ, preset recommandé | Même ISO recommandée, roundtrip vérifié, succès à 100 %, 15,56 s, aucune fenêtre bloquante |

Chaque ISO est comparée sur ses 1 459 978 240 octets à la source et aux seuls
remplacements exacts attendus. La source est hachée de nouveau en fin de
traitement ; les RVZ produites sont redécompressées et comparées avant publication.
Les 2 011 fichiers de `game/` et les 20 fichiers inventoriés du profil Dolphin
original gardent leurs empreintes, vérifiées après fermeture du test.

### Observation Dolphin

Dolphin 2609a a démarré à froid la RVZ avancée, sans état rapide, avec une carte
mémoire copiée dans un profil isolé. Le sac affiche **CT06 Plénitude**,
**CT41 Lance-Flamme** et **CT49 Queue de Fer**, conformément au rapport.
La description visible de CT06 décrit Plénitude. Le contrôle natif interdit
toujours l'apprentissage aux Pokémon obscurs ; le test sur l'équipe chargée
confirme cette restriction. Aucun apprentissage effectif après purification
n'est revendiqué.

Les stocks et boss sont contrôlés dans les données et par les tests ; leurs
achats et combats de cette version n'ont pas été rejoués. Il reste aussi à
parcourir les coffres en jeu, les dons tardifs et le scénario complet.
Captures et manifestes locaux : `build/v04-qa/evidence/` et
`build/v04-qa/validation.json`, exclus des distributions.

### Conversion non interactive

Un essai a exposé une boîte DolphinTool `IOS_FS: Failed to rename temporary FST
file` dans son profil Wii temporaire. La conversion et la vérification complète
ont réussi après fermeture de ce diagnostic, mais une boîte modale ne convient
pas à un worker en arrière-plan.

Le convertisseur prépare maintenant seulement son propre
`dolphin-user/Config/Dolphin.ini` temporaire avec `Interface/UsePanicHandlers=False`.
Les autres réglages sont conservés, ainsi que les vérifications du code retour,
de l'existence de sortie, de chaque octet ISO et du roundtrip RVZ. Le profil
Dolphin personnel n'est pas modifié. La clé est déclarée dans la
[configuration primaire de Dolphin](https://github.com/dolphin-emu/dolphin/blob/master/Source/Core/Core/Config/MainSettings.cpp).
