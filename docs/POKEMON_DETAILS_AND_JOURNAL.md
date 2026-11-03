# Fiches Pokémon et journal HTML

Les fiches décrivent les données finales de la partie configurée : types,
talents possibles, statistiques de base, capacités de départ, apprentissages,
CT compatibles et branches d’évolution. Elles sont calculées après les règles
de Pokémon, de boss, de niveaux, de capacités, de CT et de noms.

## Évolutions

Les méthodes sont relues dans le REL final. L’affichage ne déduit pas une
évolution de l’espèce d’origine ni d’une simple case cochée. Avec l’adaptation
des échanges avec objet, la fiche d’Onix indique une montée de niveau à partir
du niveau 40. Sans cette adaptation, elle affiche l’échange avec Peau Métal et
signale que cette condition demande une adaptation pour être accessible dans
Colosseum.

Toutes les branches suivantes sont incluses. Avec les évolutions adaptées,
Fantominus indique Fantominus → Spectrum au niveau 25, puis Spectrum →
Ectoplasma au niveau 40. Une pierre requise porte son nom dans la langue
d’affichage. Les Pokémon obscurs rappellent qu’ils doivent être purifiés avant
de pouvoir évoluer.

Les talents sont présentés comme des possibilités : la fiche ne prétend pas
prédire le talent effectivement choisi par le jeu, les IV, le genre, la nature
ou le PID complet. Les règles natives dépendant de la personnalité restent
signalées comme telles. Les capacités inconnues ou marqueurs spéciaux gardent
leur identifiant au lieu d’être attribués à une capacité ordinaire.

## Langues et origine des noms

L’affichage existe en français, anglais, allemand, espagnol, italien et japonais.
Les noms natifs de la ROM sont utilisés lorsqu’elle possède la langue demandée.
Pour les autres langues des ROM USA et japonaises, les noms d’interface utilisent
les catalogues BSD de [PokéAPI](https://github.com/PokeAPI/pokeapi) : espèces,
types, 354 capacités ordinaires, 77 talents et douze objets d’évolution.

Ces catalogues fournissent uniquement des noms. La puissance, la précision, les
PP, les statistiques, les types, les talents admissibles, les compatibilités et
les conditions d’évolution proviennent des octets finaux du jeu. Les noms
modernes du catalogue de repli ne modifient pas les textes ni les mécaniques
de la ROM.

`licenses/pokeapi-details.json` conserve les URL, les empreintes SHA-256 des trois
CSV sources, leur sélection et le hash du module produit. Le script
`scripts/generate_detail_names.py` reconstruit le module à partir de ces CSV
fournis localement. Aucun téléchargement n’a lieu pendant l’utilisation de
l’application. La licence est conservée dans `licenses/pokeapi.txt`.

## Journal

Le journal HTML est consultable hors ligne dans un navigateur. Ses sections
commencent fermées : réglages, starters, obscurs, cadeaux, dresseurs, évolutions
et CT. Ouvrir une section révèle son contenu ; les sections suivantes restent
fermées. Le journal reprend le même instantané final que les fiches, sans tirer
une seconde fois les Pokémon.

La seed, la version, l’identité du jeu et ses empreintes sont affichées. Les
chemins personnels du rapport de création ne sont pas repris. Les textes de
seed, de nom ou de réglage sont échappés comme du texte, même s’ils contiennent
des balises. Le fichier n’embarque ni script, ni image du jeu, ni ressource ou
requête réseau. Une politique de contenu interdit les chargements externes.

Le statut chromatique est annoncé seulement lorsqu’il est connu : taux de
0 ou 100 %, ou décision liée à la seed. Avec un taux intermédiaire sans liaison,
le journal indique que le statut sera décidé en jeu. Les conditions d’Adelbert
restent affichées pour les cadeaux concernés.

## Vérification

Les tests couvrent la lecture des octets finaux malgré des valeurs d’origine
différentes, les conditions d’évolution, la purification préalable, les branches
successives, les six langues, les compatibilités CT, l’absence de modification
de l’instantané et le refus des références invalides. Le journal est contrôlé
pour ses spoilers fermés, ses textes échappés, l’absence de chemin personnel et
de ressource externe, et le refus d’écraser un fichier existant.

Les fiches ne constituent pas une observation en jeu de chaque évolution ni
une prédiction de tous les tirages natifs. Elles décrivent les données finales
de la nouvelle partie et distinguent les propriétés encore décidées par le jeu.
