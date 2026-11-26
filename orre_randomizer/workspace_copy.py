"""One vocabulary for both game workspaces; only native mechanics differ."""

ROM_DESCRIPTION = "{game} Europe, USA ou Japon (révision 0), sans modification. Le fichier d’origine est conservé."
ROM_USE_NOTICE = "Utilisez une copie du jeu que vous êtes autorisé à utiliser. Aucune ROM n’est fournie."
STEP_HELP = (
    "Choisissez la ROM d’origine.",
    "Le mode Avancé permet de modifier chaque option du choix sélectionné.",
    "Vérifiez la destination, puis créez la ROM.",
)
PRESET_DESCRIPTIONS = (
    "Pokémon et talents aléatoires, à tous les stades d'évolution et sans équilibrage.\nCapacités, apprentissages, CT, objets tenus, coffres et boutiques randomisés. Les Balls en boutique et les objets de progression restent disponibles.",
    "Pokémon et talents aléatoires, à tous les stades d'évolution et sans équilibrage.\nCapacités de départ de l'espèce, adaptées au niveau. Aucun mélange des apprentissages, CT ou objets.",
    "Conserve les données du jeu et crée une copie au format ISO, GCM ou RVZ.",
)
CUSTOM_PRESET = "Réglages personnalisés : vos options ne correspondent plus à un choix prédéfini. Ouvrez Avancé pour les voir ou les modifier. Choisir un des trois modes ci-dessus remplacera ces réglages."
PRESET_EVOLUTIONS = "Évolutions accessibles et type Fée activé. Le tirage évite les familles en double entre starters, obscurs et cadeaux si possible."
PRESET_LEGENDARIES = "Légendaires et fabuleux exclus des tirages. Les légendaires obscurs d'origine gardent leur espèce."
PRESET_SHINIES = "Chromatiques : 5 %, avec un statut fixé par la seed et conservé après capture, évolution et purification."
COLOSSEUM_PRESET_NATIVE = "Cadeaux événementiels et quête de Lugia obscur activés, avec l'équipe prévue pour Jakylla."
XD_PRESET_NATIVE = "Poké Places : 5 % de chromatiques à chaque nouvelle rencontre, visibles avant le combat. Doking demande le Pokémon rare de chaque lieu."

CATEGORY_HELP = {
    "Dresseurs": "Les obscurs sont réglés séparément des autres Pokémon.",
    "Starters et cadeaux": "Réglez les starters et les Pokémon offerts.",
    "Capacités": "Choisissez les capacités à changer et les protections à appliquer.",
    "CT": "Les descriptions suivent les capacités tirées. Les CS restent inchangées.",
    "Boss": "Ces réglages concernent les boss de l’histoire. Le choix de chaque obscur est conservé lors de ses réapparitions.",
    "Pokémon autorisés": "Réglez les remplacements et les propriétés des Pokémon conservés.",
    "Talents": "Garde Mystik reste réservé à Munja.",
    "Statistiques": "Les statistiques sont redistribuées pour chaque espèce. Munja garde 1 PV de base.",
    "Types": "Les nouveaux types sont pris en compte pour les capacités du même type.",
    "Objets tenus": "Les Pokémon sans objet restent sans objet.",
    "Objets trouvés": "Les coffres gardent leur position et leur quantité d’objets. Les objets clés restent inchangés.",
    "Niveaux et capture": "Ces réglages ne changent pas le niveau des starters ni des Pokémon offerts.",
    "Évolutions": "Pour les évolutions par pierre, activez la vente de pierres dans « Boutiques ».",
    "Boutiques": "Réglez les objets vendus et la disponibilité des pierres d’évolution.",
    "Chromatiques": "La seed fixe les statuts chromatiques au taux choisi.",
}
XD_CATEGORY_HELP = {
    "Poké Places": "Change les rencontres des Poké Places. Doking demande le Pokémon de l’emplacement rare de chaque lieu.",
    "Chromatiques": "La seed fixe le statut chromatique du starter, des cadeaux et, si activé, des obscurs. Les Poké Places ont leur propre réglage.",
}

CATEGORY_ORDER = tuple(CATEGORY_HELP)[:2] + ("Poké Places",) + tuple(CATEGORY_HELP)[2:]
