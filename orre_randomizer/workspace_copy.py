"""One vocabulary for both game workspaces; only native mechanics differ."""

ROM_DESCRIPTION = "{game} Europe, USA ou Japon (révision 0), sans modification. Le fichier d’origine est conservé."
ROM_USE_NOTICE = "Utilisez une copie du jeu que vous êtes autorisé à utiliser. Aucune ROM n’est fournie."
STEP_HELP = (
    "Choisissez la ROM d’origine.",
    "Le mode Avancé permet de modifier chaque option du choix sélectionné.",
    "Vérifiez la destination, puis créez la ROM.",
)
PRESET_DESCRIPTIONS = (
    "Randomise les Pokémon et leurs talents. Tous les stades d’évolution sont possibles, sans équilibrage de puissance.\nRandomise aussi les capacités, les apprentissages par niveau, les CT, les objets tenus et le contenu des coffres et des boutiques. Les objets protégés et les Balls d’origine en boutique sont conservés.",
    "Randomise les Pokémon et leurs talents. Tous les stades d’évolution sont possibles, sans équilibrage de puissance.\nLes capacités, les apprentissages par niveau, les CT et les objets ne sont pas randomisés. Les pierres d’évolution sont ajoutées en boutique.",
    "Crée une nouvelle ROM sans modifier les données du jeu. Aucun Pokémon, aucune capacité ni aucun objet n’est randomisé.\nUtile pour copier le jeu ou convertir son format ISO/GCM/RVZ.",
)
CUSTOM_PRESET = "Réglages personnalisés : vos options ne correspondent plus à un choix prédéfini. Ouvrez Avancé pour les voir ou les modifier. Choisir un des trois modes ci-dessus remplacera ces réglages."
PRESET_EVOLUTIONS = "Les évolutions sont accessibles dans le jeu. Le tirage évite les familles en double entre starters, Pokémon obscurs et cadeaux quand les règles le permettent."
PRESET_LEGENDARIES = "Les légendaires et fabuleux sont exclus des tirages. Les légendaires obscurs d’origine gardent leur espèce. Les Pokémon conservés gardent leurs propriétés d’origine, sauf leur statut chromatique. Les tirages se règlent en mode Avancé."
PRESET_SHINIES = "Taux chromatique : 5 %, fixé par la seed. Le statut est conservé après capture et purification."
COLOSSEUM_PRESET_NATIVE = "Les cadeaux événementiels et la quête bonus de Lugia obscur sont activés. L’équipe de Jakylla et son Lugia ne sont pas randomisés."
XD_PRESET_NATIVE = "Poké Places : 5 % de chance d’être chromatique à chaque nouvelle rencontre, visible avant le combat. Les fréquences d’apparition des espèces sont conservées. Doking demande le Pokémon rare de chaque lieu."

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
