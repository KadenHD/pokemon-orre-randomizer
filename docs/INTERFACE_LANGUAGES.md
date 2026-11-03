# Langues de l’interface et du jeu

L’outil propose les six langues originales de Pokémon Colosseum : français,
anglais, allemand, espagnol, italien et japonais. Elles sont toutes accessibles
dans le sélecteur, avant même de charger une ROM.

Au démarrage, **Système** suit la première langue reconnue dans les préférences
du système. Une variante régionale comme `es-MX`, `de-CH` ou `fr-CA` utilise le
catalogue correspondant. Si aucune langue n’est reconnue, l’outil utilise
l’anglais. Le choix manuel est enregistré et peut être remis sur **Système**.

Le changement s’applique immédiatement aux pages, options, aides, erreurs,
progression et dialogues de fichiers. Les chemins, la seed et les profils restent
intacts. Il ne modifie ni les réglages ni le résultat de la randomisation.
L’aperçu conserve son résultat et affiche les noms dans la nouvelle langue,
y compris les noms japonais. Les numéros du Pokédex national servent aussi
à la recherche. Les fiches et le journal HTML suivent la langue de l’outil.

## Langue dans le jeu

Le sélecteur de l’outil ne traduit pas la ROM. Le moteur accepte **Colosseum
Europe `GC6P01`, USA `GC6E01` et Japon `GC6J01`, révision 0**, au format ISO ou RVZ,
avec contrôle de l’empreinte complète de chaque image. L’interface conserve ses
six langues quelle que soit la région de la ROM.

Les cinq banques européennes sont conservées. Le jeu européen affiche les noms
de pierres dans la langue choisie dans le jeu, indépendamment de celle de l’outil :

| Langue du jeu | Soleil | Lune | Feu | Foudre | Eau | Plante |
| --- | --- | --- | --- | --- | --- | --- |
| Français | Pierre Soleil | Pierre Lune | Pierre Feu | Pierre Foudre | Pierre Eau | Pierre Plante |
| Anglais | Sun Stone | Moon Stone | Fire Stone | Thunder Stone | Water Stone | Leaf Stone |
| Allemand | Sonnenstein | Mondstein | Feuerstein | Donnerstein | Wasserstein | Blattstein |
| Espagnol | Piedra Solar | Piedra Lunar | Piedra Fuego | Piedra Trueno | Piedra Agua | Piedra Hoja |
| Italien | Pietra Solare | Pietra Lunare | Pietra Focaia | Pietra Tuono | Pietra Idrica | Pietra Foglia |

L’option **Espacer les noms des pierres** corrige onze libellés PAL et un libellé
USA sans remplacer les traductions natives. La ROM USA conserve l’anglais ;
la ROM japonaise conserve ses noms japonais, sans correctif d’espacement.
Les mots allemands composés restent en un seul mot. Une
**Copie à l’identique** laisse tous les textes d’origine inchangés.

## Vérification

Les tests contrôlent les clés, champs de formatage et choix de toutes les options,
la détection des variantes régionales, la persistance du choix et la conservation
du formulaire et de l’aperçu. Le diagnostic de l’exécutable parcourt 48 états :
six langues, deux tailles de fenêtre et quatre pages ou modes. Il vérifie aussi
le chargement des traductions Qt des dialogues.

La validation locale du 1er novembre 2026 vérifie les quatorze catégories de
réglages et le mode Simple dans les six langues, à 1040 × 800 et 680 × 540, soit
180 états sans débordement horizontal détecté. Elle lit les 30 noms de pierres
dans les banques de la ROM. Pour la seed `98205757d6a5da47`, les aperçus ISO et
RVZ correspondent au résultat de la version précédente et les empreintes des
sources restent identiques. Ces contrôles ne constituent pas une partie complète
sous Dolphin ; aucun profil ni aucune sauvegarde personnelle n’est ouvert.

Les rapports locaux sont conservés dans `build/languages-2026-11-01/` et exclus
des distributions. Les fichiers du moteur sont identiques à ceux de la version
précédente ; seuls des noms localisés sont ajoutés aux métadonnées du rapport.

Les validations régionales et les fiches/journaux ajoutés depuis cet essai sont
décrits dans les [notes v0.15](DESKTOP_V15.md). La recherche, la remise à zéro
d’une catégorie et le récapitulatif de la v0.16 sont suivis dans les
[notes v0.16](DESKTOP_V16.md), avec leurs propres résultats de validation.
