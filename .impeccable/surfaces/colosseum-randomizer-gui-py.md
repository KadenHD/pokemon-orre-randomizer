---
version: 1
slug: "colosseum-randomizer-gui-py"
primary_target: "colosseum_randomizer/gui.py"
related_targets: ["colosseum_randomizer/ui_theme.py", "colosseum_randomizer/ui_workspace.py"]
---

# Surface : colosseum_randomizer/gui.py

Mode : Operate. La composition C reprend un assistant compact proche
des menus originaux de Colosseum. Composition approuvée :
`.impeccable/mocks/c-assistant-compact.png`.

Parcours : ROM d’origine → Réglages → Créer. Simple par défaut, avancé à la demande,
sans changer les paramètres lorsque l’on bascule. Les trois presets correspondent
à Options.recommended(), Options() et Options.none(). Un profil différent est
signalé comme personnalisé. FR/EN/DE/ES/IT/JA et langue système restent disponibles en traitement.

Le raffinement 0.12 approuvé conserve le monde graphique et sépare Configuration
et Aperçu des Pokémon. La seed et le menu Profils restent communs. Le contenu
est centré et limité à 1 200 px ; seul le contenu actif défile dans l’étape Réglages.

| Engagement visible | Réalisation |
|---|---|
| En-tête court, titre et langue | Titre RANDOMIZER en QLabel à côté du logo Pokémon Colosseum ; langue en QComboBox natif |
| Bandeau des trois étapes en haut | Trois QPushButton checkables ; étape active cyan, retours sans perte de saisie |
| Un panneau vert principal avec cadre argenté et angles coupés | QWidget/QPainter ; contenu Qt sémantique, aucun texte rasterisé |
| Trois points de départ dans le même groupe | Pokémon + capacités, Pokémon seuls, Copie à l’identique ; descriptions comparables et détails communs repliés par défaut |
| Seed et profils communs aux vues | QLineEdit, Nouvelle seed et menu Profils avec import/export ; aucune perte de valeurs ni d’aperçu valide au changement de vue |
| Catégories avancées adaptées à l’espace | Les 15 catégories et 74 contrôles, dont 56 booléens ; colonne de 192 px si la fenêtre fait au moins 900 px et que toutes les catégories tiennent en hauteur, sinon sélecteur compact ; choix actif conservé au redimensionnement ou changement de langue |
| Chromatiques | Personnalisation décochée par défaut ; taux de 0 à 100 % à quatre décimales et liaison à la seed visibles mais désactivés sans la personnalisation ; liaison cochée par défaut ; aide permanente pour 0 et 100 % ; pictogramme Poké Ball étoilée au trait |
| Aperçu réel commun | Calculer l’aperçu explicite, barre animée et annulation ; statut ✓ Aperçu à jour dans la rangée des onglets après résultat, détail en infobulle, Actualiser l’aperçu après modification ; noms FR/EN/DE/ES/IT/JA, niveaux disponibles et portraits 42 × 42 lus dans la ROM |
| Trois onglets de Pokémon | Starters · 2, Obscurs · 48 et Cadeaux · 4 ; deux portraits de starters et listes plates comparant Pokémon d’origine à Avec cette seed ; résultat partagé sans recalcul au changement d’onglet |
| Recherche et défilement lisibles | Recherche par nom ou numéro dans les six langues ; filtre chromatique quand le statut est connu, compteur de la plage visible parmi les résultats filtrés et état sans résultat ; liste occupant la hauteur disponible, barre de 15 px contrastée ; molette sur un champ sans focus transmise au formulaire parent |
| Fond à deux Poké Balls indigo | Texture réelle title.fsys/menu_042 exportée une fois et embarquée |
| Pied avec Retour et Continuer/Créer | Action persistante visible à 680 × 540 ; clavier, focus et état désactivé explicites ; aide liée à la configuration, à une nouvelle partie ou aux conditions d’événements selon la vue |
| Sortie, progression et résultat | Étape 3, format ISO/RVZ, destination séparée, annulation, dossier et rapport |

Les libellés inventés par le générateur ne sont pas repris. Les boutons de manette
ne sont pas des raccourcis de l’application. Le logo 96 × 32 reste un petit badge
à sa taille utile ; le titre principal est du texte. La construction locale utilise les images et sons exportés du jeu.

Points à vérifier : source absente/incompatible ; changements de langue et de mode
sans perdre chemins/seed/options ; retour entre étapes ; progression/annulation ;
pack corrompu avec repli sobre ; rendu petite fenêtre ; noms d’objets dans les
cinq langues de la ROM et correction bornée des pierres ; originaux préservés.

Ajouts confirmés : boutons Musique et Sons indépendants, activés au premier
lancement si disponibles, choix mémorisé. Pack autonome images/curseur/SFX/musique ; aucune lecture de ROM pour
démarrer l’interface, aucun cache à amorcer. Sous-libellés comparables des presets.
Lorsque la personnalisation des shinies et la liaison sont actives, une ligne sous
les starters annonce « Statuts chromatiques fixés par la seed. » avant le calcul
aux taux intermédiaires. L’aperçu utilise les décisions du moteur pour une
nouvelle partie : portraits normaux ou chromatiques authentiques de la ROM,
mentions textuelles traduites « chromatique » et « non chromatique », y compris
en dessous de 100 %. Une même espèce peut porter des statuts différents selon
la rencontre. Le taux n’impose pas de quota. À 0 et 100 %, les messages existants
annoncent respectivement l’absence ou la garantie des starters chromatiques.
Sans liaison, le statut reste tiré en jeu aux taux intermédiaires et la légende
l’indique. Changer la personnalisation, la liaison ou le taux invalide l’ancien
aperçu. Les profils 0.5 à 0.10.1 conservent la liaison désactivée à l’import.

Le calcul de production ne crée aucune ROM. Changer la ROM, la seed ou les
règles retire les lignes périmées et invite à actualiser. Les dons événementiels
sont étiquetés ; le pied de l’onglet Cadeaux rappelle leurs conditions d’obtention.
Si l’accès est activé, l’étiquette affiche plutôt le nom localisé d’Adelbert et
le seuil choisi. Les deux seuils et niveaux dépendent de la case d’accès, avec
descriptions dans les six langues et invalidation de l’aperçu après modification.
Les originaux et sauvegardes restent préservés. Aucun choix de direction ne reste
ouvert ; les contrôles futurs portent sur la petite et la grande fenêtre, les six
langues, les états de calcul/annulation, les filtres et la conservation des valeurs.
