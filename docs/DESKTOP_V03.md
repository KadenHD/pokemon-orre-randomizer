# Application v0.3 : paramètres de partie

Le moteur `advanced-gameplay-rules-v5` ajoute 26 paramètres aux seize règles
précédentes : 42 paramètres au total, dont 38 booléens, un choix de mode et trois
valeurs numériques. L'application reste locale et conserve la ROM source.

## Configuration

| Catégorie | Réglages |
| --- | --- |
| Dresseurs | Espèces ordinaires, obscurs, familles obscures uniques |
| Starters et dons | Noctali, Mentali, Posipi, Ho-Oh, Celebi, Pikachu indépendants |
| Capacités | Attaques dresseurs, starters, dons ; apprentissages par niveau ; mode cohérent/chaos ; garanties offensive et même type ; doublons ; exclusions Destruction/Explosion et K.O. en un coup |
| Espèces autorisées | Générations I/II/III ; légendaires/fabuleux ; puissance comparable |
| Talents | Randomisation ; cohérence par famille |
| Statistiques | Redistribution ; conservation du total d'origine |
| Types | Randomisation ; cohérence par famille |
| Objets tenus | Remplacer les objets présents ; sélection utile en combat |
| Difficulté et capture | Niveaux ×0,5–2 ; capture ×0,25–5 ; minimum 0–255 |
| Évolutions | Les cinq catégories accessibles de la v0.2 |
| Boutiques | Pierres à Phénacit et Pyrite séparément |

Le preset recommandé active les espèces, les quatre randomisations de capacités
en mode cohérent, les remplacements de puissance comparable, les protections,
les évolutions accessibles et les boutiques. Types, talents, statistiques et objets
restent désactivés. Les multiplicateurs restent à 1 et le minimum de capture à 0.
« Tout désactiver » remet aussi les valeurs numériques à leur valeur neutre.
La CLI conserve les anciens changements par défaut ; ses nouvelles options sont
explicites, par exemple `--randomize-learnsets --randomize-starter-moves`.

## Règles et protections

- Chaque tirage utilise SHA-256 avec la seed et une clé stable. Les options et
  versions sont enregistrées dans le rapport JSON ; aucune RNG système ne décide
  des données de la partie.
- Le mode cohérent adapte la puissance au niveau et préfère une seconde attaque
  correspondant à la statistique offensive. La séparation physique/spécial est
  celle de la génération III, déterminée par le type.
- Les quatre attaques peuvent être tirées séparément des espèces. Les garanties
  utilisent les types finaux après randomisation. Les niveaux d'apprentissage et
  les octets réservés restent intacts ; les fenêtres de quatre apprentissages
  conservent une attaque offensive du même type si cette protection est activée.
- Charge Noire et les marqueurs spéciaux sont protégés : les 30 enregistrements
  de dresseurs qui en contiennent conservent tout leur bloc de capacités. Les
  autres enregistrements ne changent que les identifiants des attaques.
- Les filtres ne sont jamais relâchés silencieusement. Les 48 groupes obscurs
  restent synchronisés et leurs familles restent distinctes lorsque demandé.
  Une combinaison impossible produit une erreur récupérable.
- Dès qu'un filtre d'espèces ou la puissance comparable est actif, Munja est
  exclu des remplacements pour éviter les blocages de combat liés à Garde Mystik.
  La sélection historique sans ces réglages reste compatible avec la v0.2 et
  peut tirer Munja. Ses propriétés natives et son PV de base restent protégés.
  Garde Mystik n'est pas attribué aux autres espèces.
- Les statistiques sont bornées à 1–255. Sans conservation du total, le total
  tiré est compris entre 250 et 680. Les talents sont tirés dans le catalogue
  natif, avec un ou deux emplacements selon l'espèce.
- Les objets sont remplacés uniquement dans les emplacements déjà occupés,
  dans un catalogue observé chez les adversaires ; les marqueurs restent intacts.
  Le Bandeau Choix n'est pas choisi sans attaque physique infligeant des dégâts.
- Les niveaux restent entre 1 et 100 ; les starters et dons gardent leur niveau.
  La capture modifie les 48 groupes actifs et reste entre 1 et 255.

## Attaques des dons et image disque

Les dons calculent normalement leurs attaques depuis les apprentissages globaux.
Une petite routine PowerPC appelle le constructeur natif puis ses quatre setters
de capacités. Elle permet de régler les attaques d'un don sans modifier les
autres Pokémon de son espèce. Lorsque seuls les apprentissages sont randomisés,
elle conserve au contraire les attaques natives appropriées à l'espèce du don.

La section de code ajoutée fait 544 octets pour les quatre dons et sa protection
d'arène mémoire. Le DOL étendu est placé dans un espace libre de l'ISO et son
pointeur de démarrage est adapté ; la FST et le DOL original restent conservés à
leur emplacement initial. Les signatures des instructions, les branches et les
plages de modification sont vérifiées avant toute sortie.

## Validation locale

111 tests Python passent, dont les contrôles Qt, les limites numériques, les
tirages cohérents/chaos, les types finaux, les 48 familles, les niveaux/captures,
les champs réservés et l'indépendance des dons. Un petit interpréteur PowerPC
teste les appels des quatre setters, le retour constructeur, les registres et
la protection de l'arène. Ces tests ne remplacent pas l'obtention réelle des dons
tardifs dans une partie complète.

ISO avec le préréglage recommandé et la seed historique de test :

```
source  1e3b4aa806ac3367cca13496f7701137e9437e7bac0101f75b9b137633a10aa9
sortie  425f1d846db101bfceaed6f941c05890eaa34cd27c5cf0fed0732830e84c7ebd
```

Les 1 459 978 240 octets de l'ISO sont vérifiés contre la source et les seuls
remplacements attendus. Le hash source est recalculé en fin de traitement.
Construction locale observée : environ 10 secondes avec le codec Rust.
La nouvelle ISO démarre à froid sous Dolphin 2609a, avec un profil isolé, une
carte mémoire vierge et sans ancien état rapide. Les sauvegardes du profil
habituel ne sont pas chargées dans ce test.

Les deux starters ont été ouverts dans une nouvelle partie : Gardevoir niveau 26
(Extrasenseur, Éclair, Protection, Onde Boréale) et Saquedeneu niveau 25
(Poing Dard, Larcin, Reflet Magik, Bulles d'O). Les noms, niveaux, quatre attaques
et PP affichés correspondent au rapport. L'EXP du premier starter est 21 970,
seuil attendu pour son groupe de croissance au niveau 26.

Une seconde construction reproduit exactement le SHA-256 de l'ISO recommandée.
Le preset sans changement reproduit exactement le SHA-256 de la source.
Un parcours RVZ → RVZ a aussi été exécuté avec types, talents, statistiques,
objets et attaques randomisés, génération III seule sans légendaires, niveaux
×1,25, capture ×2 et minimum 100. L'ISO issue de sa redécompression correspond
à l'ISO vérifiée avant compression (`97805312f1f72eb6db29654b310ef4f7da5e039c24e22177da922a1bab3ea6cd`).
Les 2 011 fichiers extraits et les 20 fichiers inventoriés du profil Dolphin
original conservent tous leurs empreintes SHA-256.

L'exécutable Windows 0.3 a démarré sans terminal et a créé sa propre ISO avec
le preset recommandé en 10,02 secondes. Son SHA-256 est identique à celui de la
version source et la fenêtre affiche le succès à 100 %. Les pages Capacités et
Difficulté/capture ont été contrôlées visuellement. Les archives passent les
contrôles d'intégrité et d'absence de données du jeu ; les sources extraites
sans ROM exécutent 111 tests avec succès, dont 29 ignorés faute de données locales.

Les fichiers locaux de preuve et rapports restent dans `build/v03-qa/` et
`build/v03-default.iso.json`, hors distribution. Le scénario complet, tous les
dons tardifs, l'équilibrage et les autres ordinateurs restent à valider. Le
contrôle manuel actuel vérifie le démarrage, l'EXP et les attaques des starters ;
un combat complet avec ces nouvelles attaques reste à jouer.
