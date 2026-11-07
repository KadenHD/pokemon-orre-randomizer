"""One vocabulary for both game workspaces; only native mechanics differ."""

ROM_DESCRIPTION = "{game} Europe, USA ou Japon (révision 0), sans modification. Le fichier d’origine est conservé."
ROM_USE_NOTICE = "Utilisez une copie du jeu que vous êtes autorisé à utiliser. Aucune ROM n’est fournie."
STEP_HELP = (
    "Choisissez la ROM d’origine.",
    "Le mode Avancé permet de modifier chaque option du choix sélectionné.",
    "Vérifiez la destination, puis créez la ROM.",
)
PRESET_DESCRIPTIONS = (
    "Remplace les Pokémon des dresseurs, les obscurs, les starters et les cadeaux, avec une puissance proche de l’original.\nRandomise aussi les capacités de départ, les apprentissages par niveau, les CT et les objets des coffres et des boutiques.",
    "Remplace les Pokémon des dresseurs, les obscurs, les starters et les cadeaux, avec une puissance proche de l’original.\nGarde les capacités de départ, les apprentissages par niveau et les CT. Les objets restent en place, sauf les pierres ajoutées en boutique.",
    "Crée une nouvelle ROM sans modifier les données du jeu. Aucun Pokémon, aucune capacité ni aucun objet n’est randomisé.\nUtile pour copier le jeu ou convertir son format ISO/RVZ.",
)
CUSTOM_PRESET = "Réglages personnalisés : vos options ne correspondent plus à un choix prédéfini. Ouvrez Avancé pour les voir ou les modifier. Choisir un des trois modes ci-dessus remplacera ces réglages."
PRESET_EVOLUTIONS = "Les évolutions sont adaptées au jeu et les pierres sont ajoutées en boutique. Les starters commencent sous leur forme de base, dans une famille à trois stades. Le tirage évite les familles en double entre starters, obscurs et cadeaux quand les règles le permettent."
PRESET_SHINIES = "Chaque Pokémon concerné a 5 % de chance d’être chromatique. La seed fixe le résultat."

CATEGORY_HELP = {
    "Dresseurs": "Les obscurs sont réglés séparément des autres Pokémon.",
    "Starters et cadeaux": "Réglez les starters et les Pokémon offerts.",
    "Capacités": "Choisissez les capacités à changer et les protections à appliquer.",
    "CT": "Les descriptions suivent les capacités tirées. Les CS restent inchangées.",
    "Boss": "Ces réglages concernent les boss de l’histoire. Le choix de chaque obscur est conservé lors de ses réapparitions.",
    "Pokémon autorisés": "Ces filtres s’appliquent aux Pokémon remplacés.",
    "Talents": "Garde Mystik reste réservé à Munja.",
    "Statistiques": "Les statistiques sont redistribuées pour chaque espèce. Munja garde 1 PV de base.",
    "Types": "Les nouveaux types sont pris en compte pour les capacités du même type.",
    "Objets tenus": "Les Pokémon sans objet restent sans objet.",
    "Objets trouvés": "Les coffres gardent leur position et leur quantité d’objets. Les objets clés restent inchangés.",
    "Niveaux et capture": "Ces réglages ne changent pas le niveau des starters ni des Pokémon offerts.",
    "Évolutions": "Pour les évolutions par pierre, activez la vente de pierres dans « Boutiques ».",
    "Boutiques": "Réglez les objets vendus et la disponibilité des pierres d’évolution.",
    "Chromatiques": "La seed fixe les statuts chromatiques ; décochez l’option pour un tirage en jeu.",
}
XD_CATEGORY_HELP = {
    "Poké Places": "Change les rencontres des Poké Places. Doking demande le Pokémon de l’emplacement rare de chaque lieu.",
    "Chromatiques": "La seed fixe le statut chromatique du starter, des cadeaux et, si activé, des obscurs. Les Poké Places ont leur propre réglage.",
}

CATEGORY_ORDER = tuple(CATEGORY_HELP)[:2] + ("Poké Places",) + tuple(CATEGORY_HELP)[2:]
