# Interface multilingue — v0.6

La v0.6.1 reprend les textes français et anglais : libellés plus courts,
vocabulaire commun aux rubriques, aides centrées sur l’effet des options et
messages d’erreur orientés vers l’action suivante. Les 59 réglages et leurs
valeurs restent inchangés. Les profils v0.5, v0.6 et v0.6.1 restent acceptés.
Les [conventions de rédaction](INTERFACE_COPY.md) décrivent le vocabulaire retenu.

L'interface suit la langue du système au premier lancement : français ou anglais,
avec repli sur l'anglais si aucune langue système proposée n'est prise en charge.
Le sélecteur de l'en-tête propose **Système**, **Français** et **English** ; les
noms des langues restent reconnaissables dans leur propre langue.

Le changement s'applique immédiatement aux 59 paramètres, quatorze catégories,
descriptions, aides accessibles, choix, actions, titres et filtres des dialogues,
erreurs récupérables et messages de progression. Les nombres des champs suivent
la locale choisie. Les contrôles natifs des sélecteurs de fichiers restent ceux
du système ; leurs boutons peuvent donc suivre la langue de Windows.

Le formulaire reste intact : seed, chemins, format, paramètres, catégorie active,
volet RVZ et progression. Le choix est aussi disponible pendant une création.
L'état et les étapes déjà affichées sont retraduits depuis leurs messages source.

## Préférence locale et reproduction

Seule la clé `interface/language` est mémorisée dans un fichier INI utilisateur
QSettings, organisation et application `ColosseumRandomizer`. La valeur est
`system`, `fr` ou `en`. Aucun chemin de ROM ni seed n'est enregistré dans cette
préférence. Un choix illisible ou inconnu revient au système ; une écriture
impossible est signalée dans l'interface sans empêcher le choix pour la session.

La langue ne fait pas partie des 59 règles, des profils partagés ou des arguments
du moteur. Elle ne change pas la langue de la ROM ni ses tirages. Le moteur reste
`starter-shadow-boss-rules-v7`. La v0.6 accepte les profils v0.5 et v0.6, avec
contrôle de version du moteur, schéma, valeurs et empreinte d'origine. Une v0.5
ne sait pas importer un profil exporté par une version plus récente.

## Implémentation et contrôles

Le catalogue anglais est un module Python inclus hors ligne dans les sources et
l'exécutable. Le français est la langue source. Les messages paramétrés gardent
leurs paramètres séparés : les chemins et seeds ne sont jamais traduits. Les
détails techniques bruts d'une erreur système ou de format restent des diagnostics
dans leur langue d'origine, précédés d'un message d'interface traduit.

La détection utilise les langues UI ordonnées de
[QLocale](https://doc.qt.io/qtforpython-6/PySide6/QtCore/QLocale.html#PySide6.QtCore.QLocale.uiLanguages),
et la préférence utilise
[QSettings](https://doc.qt.io/qtforpython-6/PySide6/QtCore/QSettings.html).
La suite passe **211 tests Python et trois tests Rust**. Elle couvre notamment :

- langues système avec régions et variantes, priorité et repli ;
- couverture des libellés, descriptions, choix et paramètres de formatage ;
- choix manuel mémorisé, puis retour au système ;
- maintien des règles, seeds Unicode, chemins contenant des accolades et profils ;
- changement pendant un vrai worker Qt en arrière-plan, sans le redémarrer ;
- erreurs, annulation, succès et titres/filtres des sélecteurs ;
- actions accessibles dans une fenêtre de 680 × 540 en français et en anglais ;
- compatibilité et détection de falsification des profils v0.5.

Une course de fin de worker observée pendant ces vérifications a aussi été
corrigée : le thread natif termine son nettoyage avant que l'interface ne libère
sa référence et ne réactive les réglages. Les fenêtres de test sont détruites
explicitement sur le thread UI pour isoler leurs objets Qt.

Les limites de validation du jeu restent celles du
[rapport Dolphin](DOLPHIN_VALIDATION_2026-10-31.md). Cette évolution de l'interface
n'ajoute aucun nouveau réglage de randomisation.

## Essai de l'exécutable Windows

La version reconstruite a été ouverte sous Windows en mode système français,
changée en anglais, fermée puis relancée : le choix anglais est retrouvé.
L'import du profil v0.5 de référence réussit dans cette interface anglaise.
Une création complète prend **11,30 s**. Le résultat, les chemins et la seed
restent affichés lors du retour au français.

L'ISO générée a été réempreintée indépendamment :
`648cc8c0744c87fce40a7d4dbdd3f6f95f8df29bc48415ee33507cb5d1894b35`,
identique à la référence v0.5 pour la même seed et les mêmes règles. La source
reste intacte et tous les octets de sortie sont vérifiés par le moteur. La langue
de l'interface ne change donc pas ce résultat de référence.

L'audit après cet essai retrouve les images sources, les 2 011 fichiers du jeu,
les 2 691 fichiers de l'installation Dolphin et les 46 fichiers du profil
Dolphin personnel inchangés. Les rapports, captures et images d'essai restent
privés sous `build/`, hors distribution.
