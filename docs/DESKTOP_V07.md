# Interface v0.7

La composition C propose un assistant ROM → Réglages → Créer, avec les
panneaux verts, cadres argentés et sélections cyan de Colosseum.

Le mode Simple propose Pokémon + capacités, Pokémon seuls et Copie à l’identique.
Chaque choix décrit ce qui change ; le mode Avancé expose les
60 paramètres dans 14 catégories ; seed et profils restent accessibles dans un
tiroir. Les choix sont conservés lorsque l’on change de mode ou de langue.
Les actions de navigation et de création restent visibles à 680 × 540.

Le pack `colosseum_randomizer/assets/game/` contient le fond, le logo, les portraits,
un curseur Poké Ball, trois effets de menu et le thème du titre. Il est embarqué
dans l’exécutable et dans les sources de cette construction locale. Le démarrage
de l’interface ne lit aucune ROM et ne dépend pas d’un cache utilisateur.

Les images sont décodées depuis les textures natives. Les trois effets sont les
échantillons du jeu : déplacement, validation et retour, avec un gain de 25 %.
Le thème est un rendu DSP de Dolphin identifié par la partition et la récurrence
du signal : 99,25 secondes, rééchantillonnées à 44,1 kHz, gain de 15 %, filtre
passe-haut 20 Hz et courts fondus. Aucun lecteur MusyX ni Dolphin n’est nécessaire
pour écouter le morceau dans l’application. Le début et la fin musicaux ont été
estimés par corrélation ; les frames exportées et leurs empreintes sont enregistrées.

Musique et Sons se commandent séparément et sont activés au premier
lancement si disponibles ; les préférences sont mémorisées hors des profils de partie. Sous
Windows, deux lecteurs natifs distincts permettent aux clics de ne pas couper
la musique. Aucun réglage de volume du système n’est modifié.

Le réglage « Espacer les noms des pierres » ajoute onze espaces dans les noms
compacts natifs en français, anglais, italien et espagnol. Les composés allemands
restent inchangés. Les cinq langues du jeu sont conservées. La correction
déduplique douze textes déjà identiques pour libérer de la place : taille du REL,
positions des tables, relocations et tous les autres IDs de textes sont préservés.

Les profils v0.5/v0.6 sont validés avec leur empreinte d’origine, puis importés avec
ce nouveau réglage désactivé. Une vérification reproduit exactement l’ISO du profil
v0.5 de contrôle. Le choix Copie à l’identique désactive aussi la correction des noms.

L’ISO de contrôle avec les réglages conseillés a pour empreinte SHA-256 :
`9bb9f44aed82a12ae9e8f2cecf461c14d38074f9aaedc2c2687c5356d1ba1317`.
Chaque création reste vérifiée intégralement et refuse une destination existante.
Les contrôles de scénario précédents sont consignés dans le rapport Dolphin ;
ils ne constituent pas une nouvelle partie complète jouée avec cette version.

Preuves locales dans `build/v07-qa/` : captures de l’interface, tests d’audio natif,
compatibilité des anciens profils, rapport de création et audit de conservation.
Les sources et transformations des ressources embarquées sont enregistrées dans
le manifeste `colosseum_randomizer/assets/game/provenance.json`.
