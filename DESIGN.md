---
name: Colosseum Randomizer
description: Interface Qt native inspirée des menus originaux de Colosseum.
colors:
  forest-panel: "#082b24"
  indigo-background: "#181b3b"
  field-ink: "#0b1c20"
  text-ivory: "#f2f6f1"
  text-mint: "#c1d8cf"
  silver-frame: "#b6ccc4"
  cyan-state: "#71e2e6"
  teal-selected: "#125359"
  button-face: "#172c33"
  field-edge: "#829e98"
  action-gold: "#efd574"
  action-face: "#173e38"
  action-hover: "#245d4f"
typography:
  display:
    fontFamily: "Segoe UI"
    fontSize: "27px"
    fontWeight: 700
  headline:
    fontFamily: "Segoe UI"
    fontSize: "23px"
    fontWeight: 650
  body:
    fontFamily: "Segoe UI"
    fontSize: "14px"
  note:
    fontFamily: "Segoe UI"
    fontSize: "13px"
rounded:
  control: "4px"
spacing:
  compact: "8px"
  group: "12px"
  page: "16px"
  outer: "24px"
components:
  button:
    backgroundColor: "{colors.button-face}"
    textColor: "{colors.text-ivory}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "4px 12px"
  button-primary:
    backgroundColor: "{colors.action-face}"
    textColor: "{colors.text-ivory}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "3px 17px"
  button-primary-hover:
    backgroundColor: "{colors.action-hover}"
    textColor: "{colors.text-ivory}"
  input:
    backgroundColor: "{colors.field-ink}"
    textColor: "{colors.text-ivory}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "5px 8px"
  selection:
    backgroundColor: "{colors.teal-selected}"
    textColor: "{colors.text-ivory}"
  menu-panel:
    backgroundColor: "{colors.forest-panel}"
    textColor: "{colors.text-ivory}"
---

# Design System: Colosseum Randomizer

## Overview

**Creative North Star: "Les menus de Colosseum"**

Le système reprend les panneaux verts, les cadres argentés à angles coupés et
la sélection cyan du jeu original. Le fond indigo et les petits portraits donnent
le contexte ; les champs et les boutons restent des contrôles Qt lisibles.

Les images et l’audio appartiennent au pack d’interface embarqué. L’apparence
ne dépend pas d’une ROM sélectionnée, d’un téléchargement ou d’un cache utilisateur.
La police du système, les sélecteurs natifs et les noms accessibles des contrôles
restent les conventions de l’application de bureau.

**Key Characteristics:**

- Panneaux vert forêt sur un fond indigo tiré du jeu.
- Cadres argentés anguleux, sans ombre portée ajoutée.
- Sélection et focus cyan ; action principale bordée d’or pâle.
- Petits portraits authentiques et textes rendus par Qt.
- Contrôles audio indépendants, activés au premier lancement si disponibles, avec choix mémorisé.

## Colors

Le vert occupe la surface de travail ; l’indigo porte l’image de fond. Les
accents expriment un état ou une action, avec les valeurs du frontmatter.

### Primary

- **Cyan d’état** : focus clavier, sélection des boutons et catégorie active.
- **Sarcelle de sélection** : fond des contrôles cochés et des lignes choisies.

### Secondary

- **Or d’action** : contour de l’action principale ; son focus reste cyan.

### Neutral

- **Vert forêt** : panneau central et palette des fenêtres et enfants Qt.
- **Indigo de fond** : fond de repli et support de la texture du titre.
- **Encre des champs** : saisies, cases et progression.
- **Ivoire de texte** : libellés et contenu courant.
- **Menthe de texte** : notes et descriptions secondaires.
- **Argent de cadre** : contour externe du panneau à angles coupés.
- **Face des boutons** et **bord des champs** : contrôles disponibles au repos.

**The State Rule.** Le cyan indique le focus ou la sélection. Il accompagne
une coche, un état de bouton, un curseur ou une position ; aucune information
critique ne repose uniquement sur la couleur.

## Typography

**Display Font:** Segoe UI sous Windows ; police sans sérif du système sur les
autres plateformes. Aucune police du jeu n’est embarquée.

**Body Font:** même famille que les titres. Les tailles et graisses réelles sont
définies dans le frontmatter ; les contrôles héritent de la police de l’application.

### Hierarchy

- **Display** : nom de l’outil dans l’en-tête, avec retour à la ligne autorisé.
- **Headline** : titre de la zone de travail courante.
- **Body** : boutons, champs, catégories et cases.
- **Note** : sous-libellés des préréglages, aides et légendes.

**The Native Text Rule.** Les textes utiles restent des widgets Qt, traduits
et exposés aux technologies d’assistance. Les images ne remplacent pas les
libellés, les descriptions ou les commandes.

## Layout

La fenêtre utilise un en-tête compact, une navigation horizontale, un panneau
de travail dominant et des actions ancrées sous ce panneau. Les dimensions
préférées sont limitées par l’écran ; le minimum implémenté est de 680 × 540.
Les zones de contenu défilent et les actions principales restent à l’extérieur.

Les marges externes sont de 24 px horizontalement et 18 px verticalement. Les
groupes se séparent de 12 px. Le cadre réserve 8 px autour des pages ; celles-ci
ajoutent 16 px horizontalement et 12 px verticalement. Le contenu des pages est
centré et limité à 1 200 px de large. Les rangées fixes des réglages et de
l’aperçu sont espacées de 6 px pour réserver la hauteur au contenu actif.

En japonais, les contrôles utilisent Yu Gothic UI, Meiryo ou Noto Sans CJK JP
selon les polices installées. Le nom de l’application garde Segoe UI. Les tailles,
couleurs et états restent ceux du thème ; le texte japonais revient à la ligne.

Les réglages séparent Configuration et Aperçu des Pokémon. La seed et le menu
Profils restent dans une rangée commune, au-dessus du contenu de chaque vue.
Changer de vue conserve les règles et le résultat valide. Les détails communs
des préréglages sont repliés par défaut.

En avancé, les catégories occupent une colonne de 192 px quand la fenêtre fait
au moins 900 px de large et que les quinze catégories tiennent en hauteur.
Sinon, un sélecteur compact remplace la colonne. Le choix actif et les valeurs
sont conservés. Le formulaire actif défile sans défilement englobant de l’étape.

L’aperçu possède sa propre zone de résultat, sans hauteur maximale fixe. Les
portraits des starters accompagnent les noms et niveaux ; les obscurs et les
cadeaux occupent une liste native. Le pied Retour/Continuer reste en dehors
de ces zones et demeure visible dans la petite fenêtre de 680 × 540.

## Elevation & Depth

La profondeur vient des tons et des deux contours du panneau. La texture du
jeu est assombrie avant le dessin des contrôles. L’implémentation n’ajoute ni
ombre portée ni flou décoratif ; les changements d’état sont immédiats.

**The Frame Rule.** Le cadre argenté appartient au panneau de travail. Les
champs, listes et boutons gardent leurs traits plus fins pour préserver la hiérarchie.

## Shapes

Le panneau est un polygone à huit sommets : angles extérieurs coupés de 11 px,
contour externe de 2 px et contour interne plus fin, décalé de 5 px. Les champs
et boutons utilisent de petits coins arrondis. Les étapes sont jointives et carrées.

Les portraits restent petits : pixels originaux de 42 × 42, centrés dans un
emplacement de 48 × 48. Le logo de 96 × 32 est un badge dans l’en-tête ; le nom
principal de l’outil reste du texte.

## Components

### Buttons

- **Repos** : face sombre, trait argenté fin et texte ivoire.
- **Principal** : face verte, bordure d’or de 2 px et graisse renforcée.
- **Survol** : éclaircissement de la face et du contour.
- **Focus et sélection** : bordure cyan de 2 px, avec compensation du padding.
- **Désactivé** : face, bordure et texte atténués ; la commande reste reconnaissable.
- **Préréglages** : boutons alignés avec un sous-libellé bref pour comparer les choix.

### Inputs / Fields

Les champs sont sombres, avec un trait fin et une hauteur minimale de contenu
de 24 px. Le focus épaissit le trait et compense le padding ; la largeur du
contenu ne saute pas. Les cases affichent une coche dessinée, en plus du fond cyan.

La molette ne modifie pas un nombre ou une liste de choix sans focus : elle est
transmise à la zone de défilement parente lorsqu’elle existe. Un champ ayant le
focus conserve son comportement natif de modification.

### Encounter Preview

La vue Aperçu des Pokémon contient trois onglets Qt : Starters · 2, Obscurs · 48
et Cadeaux · 4. « Calculer l’aperçu » lance explicitement le moteur commun aux
trois groupes. Le changement d’onglet réutilise le résultat valide. Pendant le
calcul, une barre animée, une explication et l’annulation restent disponibles.
Après calcul, la coche et « Aperçu à jour » remplacent la commande dans la
rangée des onglets ; le détail du résultat reste accessible par son infobulle.

La liste native présente deux colonnes nommées « Pokémon d’origine » et
« Avec cette seed », sous un en-tête sombre. Chaque onglet présente une liste
plate ; chaque ligne associe le nom d’origine au remplacement,
avec son petit portrait de ROM (42 × 42) et son niveau lorsqu’il est disponible.
Les noms, les colonnes et les onglets sont traduits dans les six langues.
La sélection conserve la sarcelle existante ; aucun nouvel accent n’est ajouté.

La recherche accepte les noms dans les six langues et les numéros du Pokédex.
Un filtre de statut est disponible lorsque le résultat chromatique est connu.
Le compteur indique la plage de lignes visible parmi les résultats filtrés ;
une recherche vide de résultats l’annonce explicitement. La liste seule défile,
avec une barre de 15 px et une poignée claire d’au moins 44 px.

Modifier la ROM, la seed ou les règles retire les anciennes lignes et invite à
actualiser. Les cadeaux événementiels indiquent le donneur localisé et le seuil
de purification lorsque leur accès est activé ; sinon, ils gardent la mention
d’événement externe. Le pied rappelle les conditions actives dans l’onglet Cadeaux. Dans les autres
groupes, il précise la portée « nouvelle partie » et l’absence de ROM créée.

### Dependent Settings

Une case peut activer le champ numérique qui la suit. Le champ reste visible et
conserve sa valeur lorsque la case est décochée ; son texte et son contour sont
atténués par l’état désactivé natif. L’aide reste lisible sous les deux contrôles.

Dans « Chromatiques », la case « Personnaliser les shinies » précède la case
« Lier les chromatiques à la seed », puis le taux en pourcentage de 0 à 100,
affiché avec quatre décimales. La personnalisation est décochée au premier
lancement ; le taux proposé de 1 % et la liaison restent visibles mais inactifs.
La liaison est cochée par défaut et conserve sa valeur lorsqu’elle est désactivée.
Une note permanente explique les deux extrêmes. Les textes restent localisés,
avec le séparateur décimal de la langue choisie.

Avec la personnalisation et la liaison actives, la ligne visible avant le calcul
annonce « Statuts chromatiques fixés par la seed. » aux taux intermédiaires.
L’aperçu utilise les décisions exactes du moteur pour une nouvelle partie : chaque
starter, obscur et cadeau reçoit son portrait normal ou chromatique authentique.
Le nom porte aussi la mention traduite « chromatique » ou « non chromatique » ;
la couleur du portrait n’est donc pas la seule information. Une même espèce peut
apparaître sous les deux formes selon la rencontre. La légende précise la portée
« nouvelle partie » et ne promet aucun nombre minimal de chromatiques.

Sans liaison, la légende conserve l’explication du tirage en jeu aux taux
intermédiaires et utilise les portraits ordinaires. Les messages spécifiques à
0 et 100 % restent visibles avant le calcul lorsque la personnalisation est
activée. Modifier le taux, la personnalisation ou la liaison retire les résultats
périmés dans les deux vues. Les noms et statuts restent lisibles si un portrait
ne peut pas être décodé. Ces états reprennent les cadres, couleurs et actions de
la composition C existante.

### Exclusion Selectors

Une ligne de réglage associe un résumé (« Aucune exclusion » ou un nombre) à
« Choisir… ». Le dialogue conserve les champs sombres, les textes Qt et la liste
verte du système existant. Le titre et l’aide précèdent la recherche ; le compteur
et les boutons OK / Annuler restent sous la liste défilante.

Une coche signifie toujours « exclu ». Sa marque sombre sur fond cyan reprend
les cases des réglages, sans remplacer l’état accessible du contrôle natif.
La recherche accepte les noms localisés et les numéros ; les actions de groupe
portent seulement sur les résultats visibles. OK applique la sélection ; Annuler
ferme le dialogue sans modifier la valeur du réglage.

### Navigation

L’icône d’application est **Éclipse**. Les deux
croissants noir/or et lilas/rouge forment une silhouette commune. Le master PNG
et l’ICO 16–256 px sont dans `assets/app/`, indépendamment du pack du jeu. Elle
sert à l’exécutable, aux fenêtres et au raccourci local.

Les étapes sont des boutons checkables alignés sans espacement. L’étape active
combine fond sarcelle, contour cyan et curseur Poké Ball. Les catégories utilisent
une liste native à séparateurs discrets et une sélection cyan. Les quinze catégories
ont des pictogrammes sémantiques au trait de 20 px, menthe au repos et cyan en sélection :
équipe, cadeau, éclair, disque CT, couronne, filtre, talent, graphique, étiquette,
main tenant un objet, coffre, capture et niveau, arbre d’évolution, boutique,
Poké Ball étoilée pour les chromatiques.
Ces icônes sont dessinées par l’application et restent disponibles sans le pack du jeu.
La ligne active reste dans la partie visible de la liste après un redimensionnement
ou un changement de langue ; le sélecteur compact représente la même catégorie.

Les onglets reprennent les faces sombres des boutons et le fond sarcelle pour
la sélection, soulignée en cyan. Leur padding est de 6 px verticalement et
13 px horizontalement. Le menu Profils utilise les mêmes couleurs et regroupe
l’import et l’export sans ajouter une rangée permanente de commandes.

### Menu Panel

Le panneau est dessiné par `QPainter`, avec ses enfants Qt accessibles. Les pages
défilantes conservent un fond transparent pour rester dans la même surface verte.
Le fond du titre, le logo et les portraits proviennent du pack local validé.

### Audio Controls

« Musique » et « Sons » sont deux boutons checkables dans l’en-tête. Leur état
coché utilise la même sélection cyan que les autres commandes. Les préférences
sont mémorisées indépendamment des réglages de partie ; les canaux de musique
et de navigation sont séparés. Une sortie audio indisponible ne bloque pas la création.

## Do's and Don'ts

Dans « Starters et cadeaux », l’accès aux cadeaux événementiels commande quatre
champs : deux seuils de purification et deux niveaux de réception. Les valeurs
restent mémorisées mais désactivées sans cette option. Les descriptions précisent
que les scènes d’introduction doivent être terminées, même avec un seuil nul.
Les dialogues du jeu suivent les cinq langues PAL, indépendamment des six langues
de l’interface ; l’aperçu conserve les mêmes espèces et statuts que le moteur.

### Do:

- **Do** conserver les vrais petits visuels du pack embarqué et leurs proportions.
- **Do** réserver le cyan aux états interactifs et l’or au contour de l’action principale.
- **Do** garder les textes traduisibles, le focus clavier et les noms accessibles des contrôles.
- **Do** faire défiler le contenu actif et garder les actions de navigation visibles sur une petite fenêtre.

### Don't:

- **Don't** remettre l’ancienne palette bleue ou supprimer les ressources du jeu du système choisi.
- **Don't** agrandir les portraits jusqu’à en faire l’élément dominant de la zone de travail.
- **Don't** rasteriser les libellés ou transformer les captures de maquette en interface cliquable.
- **Don't** faire dépendre le démarrage visuel et sonore d’une première ROM ou d’un cache à remplir.
