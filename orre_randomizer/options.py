"""Shared typed settings for the desktop UI, CLI and reproduction reports."""
from dataclasses import dataclass, field, fields


def rule(label: str, group: str, description: str, default: bool = True):
    return field(default=default, metadata={"label": label, "group": group, "description": description, "kind": "bool"})


def setting(default, label: str, group: str, description: str, **details):
    return field(default=default, metadata={"label": label, "group": group, "description": description, **details})


@dataclass(frozen=True)
class Options:
    randomize_trainers: bool = rule("Changer les Pokémon non obscurs", "Dresseurs", "Remplace les Pokémon non obscurs des dresseurs. Les niveaux et les capacités se règlent séparément.")
    randomize_shadows: bool = rule("Changer les Pokémon obscurs", "Dresseurs", "Remplace les 48 obscurs. Un même obscur garde la même espèce dans toutes ses rencontres.")
    unique_shadows: bool = rule("Familles différentes pour les obscurs", "Dresseurs", "Chaque obscur appartient à une famille d’évolution différente. Toutes les formes évolutives restent possibles.")
    trainer_theme_mode: str = setting("none", "Types des équipes non obscures", "Dresseurs", "Sans thème : tirage habituel. Au hasard : un type commun par équipe. Type d’origine si possible : garde le type partagé initial, sinon choisit un thème admissible. Les Pokémon obscurs restent inchangés. Nécessite le remplacement des Pokémon non obscurs.", kind="choice", choices=(("none", "Sans thème"), ("random", "Un type au hasard"), ("preserve", "Type d’origine si possible")))
    trainer_force_evolved: bool = rule("Adversaires non obscurs au stade final", "Dresseurs", "À partir du niveau choisi, impose une forme qui n’évolue plus. Sans randomiser les espèces, fait évoluer le Pokémon dans sa propre famille. Utilise le niveau après les bonus des boss ; les obscurs restent inchangés.", False)
    trainer_evolution_level: int = setting(40, "Stade final à partir du niveau", "Dresseurs", "Seuil de l’option Stade final : de 1 à 100. Ne change pas les niveaux eux-mêmes, les starters ni les Pokémon offerts.", kind="int", minimum=1, maximum=100, step=1)
    custom_shinies: bool = rule("Personnaliser les chromatiques", "Chromatiques", "Active le taux choisi pour les nouveaux Pokémon des dresseurs, obscurs, starters et cadeaux identifiés. Débloque les starters et cadeaux. Désactivé : comportement d’origine. Ne relance pas les tirages déjà enregistrés.", False)
    seeded_shinies: bool = rule("Lier les chromatiques à la seed", "Chromatiques", "La seed fixe le statut de chaque starter, cadeau, obscur et emplacement de dresseur. L’aperçu montre le résultat pour une nouvelle partie. Désactivé : tirage en jeu. Les Pokémon déjà générés gardent leur statut.")
    shiny_chance_percent: float = setting(1.0, "Taux de chromatiques (%)", "Chromatiques", "Probabilité appliquée à chaque Pokémon : avec la seed si l’option est activée, sinon par tirage en jeu. 0 % : aucun ; 100 % : tous. Les obscurs gardent leur statut après capture et purification. Les Pokémon déjà générés ne sont pas retirés au sort.", kind="float", minimum=0.0, maximum=100.0, step=0.1, decimals=4)
    starter_umbreon: bool = rule("Remplacer le premier starter", "Starters et cadeaux", "Change le premier starter. Son niveau reste le même ; son expérience est adaptée au Pokémon tiré.")
    starter_espeon: bool = rule("Remplacer le second starter", "Starters et cadeaux", "Change le second starter. Son niveau reste le même ; son expérience est adaptée au Pokémon tiré.")
    starter_umbreon_species: int = setting(0, "Premier starter", "Starters et cadeaux", "Tirage avec la seed, ou Pokémon choisi. Un choix manuel remplace les filtres de stade et de puissance individuelle ; les exclusions et les règles du duo restent appliquées. Sans remplacement de Noctali, ce choix est ignoré.", kind="int", minimum=0, maximum=386, step=1, selector="species")
    starter_espeon_species: int = setting(0, "Second starter", "Starters et cadeaux", "Tirage avec la seed, ou Pokémon choisi. Un choix manuel remplace les filtres de stade et de puissance individuelle ; les exclusions et les règles du duo restent appliquées. Sans remplacement de Mentali, ce choix est ignoré.", kind="int", minimum=0, maximum=386, step=1, selector="species")
    starter_stage: str = setting("base", "Stade des starters", "Starters et cadeaux", "Forme de base : sans préévolution. Première évolution : un stade après la base. Évolution finale : forme évoluée qui n’évolue plus. Un starter d’origine conservé n’est pas concerné.", kind="choice", choices=(("any", "Tous les stades"), ("base", "Forme de base"), ("first", "Première évolution"), ("final", "Évolution finale")))
    starter_three_stage_families: bool = rule("Familles à trois stades uniquement", "Starters et cadeaux", "Exige deux évolutions successives disponibles dans le jeu. Les branches ne comptent pas comme des stades. Avec l’équilibrage, les formes de base sont comparées à Évoli. Un starter d’origine conservé n’est pas concerné.")
    starter_balance_pair: bool = rule("Starters de puissance proche", "Starters et cadeaux", "Limite l’écart de total des statistiques à 20 % du plus faible, ou 50 points si cette marge est plus grande. Le calcul utilise les statistiques finales.", False)
    starter_distinct_families: bool = rule("Starters de familles différentes", "Starters et cadeaux", "Empêche de tirer deux membres de la même famille d’évolution. S’applique aussi si vous gardez un des starters d’origine.", False)
    diverse_story_families: bool = rule("Éviter les familles en double dans l’histoire", "Starters et cadeaux", "Cherche une famille différente pour chaque starter, obscur et cadeau. Les choix manuels et les autres règles restent prioritaires si aucun tirage sans doublon n’est possible.", False)
    starter_complementary_types: bool = rule("Starters sans type commun", "Starters et cadeaux", "Les deux starters tirés ne partagent aucun type. Tient compte des types randomisés.", False)
    gift_plusle: bool = rule("Remplacer Posipi", "Starters et cadeaux", "Change le Posipi offert en gardant son niveau. Écarte les Pokémon trop grands pour la scène.")
    gift_hooh: bool = rule("Remplacer Ho-Oh", "Starters et cadeaux", "Change la récompense Ho-Oh. Les conditions pour l’obtenir restent les mêmes.")
    event_celebi: bool = rule("Remplacer Celebi événementiel", "Starters et cadeaux", "Change le Pokémon de ce cadeau. Activez l’accès aux cadeaux événementiels pour le recevoir auprès d’Adelbert ; sinon, ses conditions d’origine restent nécessaires.")
    event_pikachu: bool = rule("Remplacer Pikachu événementiel", "Starters et cadeaux", "Change le Pokémon de ce cadeau. Activez l’accès aux cadeaux événementiels pour le recevoir auprès d’Adelbert ; sinon, ses conditions d’origine restent nécessaires.")
    accessible_event_gifts: bool = rule("Rendre les cadeaux événementiels accessibles", "Starters et cadeaux", "Adelbert remet les cadeaux de Pikachu et Celebi près de la Relique Sacrée après le nombre de purifications choisi. Adelbert devient disponible après les scènes d’introduction à la purification. Chaque cadeau ne peut être reçu qu’une fois par sauvegarde. Les espèces et les statuts suivent les autres réglages.")
    event_pikachu_purifications: int = setting(10, "Purifications pour le cadeau de Pikachu", "Starters et cadeaux", "Nombre de Pokémon obscurs à purifier pour recevoir ce cadeau auprès d’Adelbert. 0 : disponible sans purification dès que le dialogue est accessible.", kind="int", minimum=0, maximum=48, step=1)
    event_celebi_purifications: int = setting(25, "Purifications pour le cadeau de Celebi", "Starters et cadeaux", "Nombre de Pokémon obscurs à purifier pour recevoir ce cadeau auprès d’Adelbert. 0 : disponible sans purification dès que le dialogue est accessible.", kind="int", minimum=0, maximum=48, step=1)
    event_pikachu_level: int = setting(30, "Niveau du cadeau de Pikachu", "Starters et cadeaux", "Niveau fixé à la réception du cadeau auprès d’Adelbert, même si Pikachu est remplacé. N’a aucun effet lorsque l’accès aux cadeaux événementiels est désactivé.", kind="int", minimum=1, maximum=100, step=1)
    event_celebi_level: int = setting(45, "Niveau du cadeau de Celebi", "Starters et cadeaux", "Niveau fixé à la réception du cadeau auprès d’Adelbert, même si Celebi est remplacé. N’a aucun effet lorsque l’accès aux cadeaux événementiels est désactivé.", kind="int", minimum=1, maximum=100, step=1)
    evolve_trade: bool = rule("Évolutions par échange au niveau 40", "Évolutions", "Kadabra, Machopeur, Gravalanch et Spectrum évoluent en gagnant un niveau à partir du niveau 40.")
    evolve_trade_items: bool = rule("Échanges avec objet : niveau ou pierre", "Évolutions", "Onix, Hypocéan, Insécateur et Porygon : niveau 40. Têtarte : Pierre Soleil. Ramoloss : Pierre Eau.")
    evolve_coquiperl: bool = rule("Faire évoluer Coquiperl avec des pierres", "Évolutions", "Pierre Eau pour Serpang ; Pierre Lune pour Rosabyss.")
    evolve_day_night: bool = rule("Faire évoluer Évoli avec des pierres", "Évolutions", "Pierre Soleil pour Mentali ; Pierre Lune pour Noctali.")
    evolve_beauty: bool = rule("Faire évoluer Barpau au niveau 40", "Évolutions", "Barpau évolue en Milobellus en gagnant un niveau à partir du niveau 40.")
    stones_phenac: bool = rule("Vendre les six pierres à Phénacit", "Boutiques", "Ajoute les six pierres d’évolution à 2 100 chacune, sans retirer les objets déjà vendus.")
    stones_pyrite: bool = rule("Vendre les six pierres à Pyrite", "Boutiques", "Ajoute les six pierres d’évolution à 2 100 chacune, sans retirer les objets déjà vendus.")
    readable_stone_names: bool = rule("Espacer les noms des pierres", "Boutiques", "Ajoute les espaces manquants dans les noms des pierres. Les noms suivent la langue choisie dans le jeu, indépendamment de celle de l’outil.")

    randomize_trainer_moves: bool = rule("Capacités des dresseurs", "Capacités", "Remplace les capacités ordinaires. Les capacités obscures et les emplacements spéciaux sont conservés.", False)
    randomize_starter_moves: bool = rule("Capacités de départ des starters", "Capacités", "Change les quatre capacités de chaque starter, même si vous gardez le Pokémon d’origine.", False)
    randomize_gift_moves: bool = rule("Capacités des Pokémon offerts", "Capacités", "Change les capacités de départ des Pokémon offerts, sans toucher aux autres Pokémon de la même espèce.", False)
    randomize_learnsets: bool = rule("Capacités apprises par niveau", "Capacités", "Change les capacités apprises. Les niveaux d’apprentissage restent les mêmes.", False)
    ensure_damaging_move: bool = rule("Au moins une capacité offensive", "Capacités", "Chaque ensemble de capacités tiré contient au moins une capacité qui inflige des dégâts.")
    ensure_stab_move: bool = rule("Au moins une capacité du même type", "Capacités", "Inclut une capacité offensive du type actuel du Pokémon, y compris après randomisation des types.")
    no_duplicate_moves: bool = rule("Éviter les capacités en double", "Capacités", "Évite les doublons parmi les quatre capacités et dans les apprentissages par niveau.")
    ban_self_destruct: bool = rule("Exclure Destruction et Explosion", "Capacités", "Ces deux capacités ne peuvent pas être tirées.")
    ban_ohko: bool = rule("Exclure les capacités K.O. en un coup", "Capacités", "Exclut Guillotine, Empal’Korne, Abîme et Glaciation.")
    moves_mode: str = setting("balanced", "Choix des capacités", "Capacités", "Adapté au Pokémon : tient compte du niveau et des statistiques. Au hasard : ignore ces critères. Les protections cochées restent actives.", kind="choice", choices=(("balanced", "Adapté au Pokémon"), ("chaos", "Au hasard")))
    randomize_abilities: bool = rule("Changer les talents", "Talents", "Tire des talents présents dans le jeu. Garde Mystik reste réservé à Munja.", False)
    abilities_family_consistent: bool = rule("Mêmes talents dans une famille", "Talents", "Les membres d’une famille partagent les talents tirés. Chaque espèce garde un ou deux talents selon son cas d’origine.")
    randomize_stats: bool = rule("Redistribuer les statistiques", "Statistiques", "Répartit à nouveau les PV, l’Attaque, la Défense, l’Attaque Spéciale, la Défense Spéciale et la Vitesse. Munja garde 1 PV de base.", False)
    preserve_stat_totals: bool = rule("Garder le total des statistiques", "Statistiques", "Répartit le total d’origine. Si cette option est désactivée, tire un nouveau total entre 250 et 680.")
    randomize_types: bool = rule("Changer les types", "Types", "Change les types de chaque espèce, en gardant un ou deux types. Munja conserve ses types.", False)
    types_family_consistent: bool = rule("Mêmes types dans une famille", "Types", "Les membres d’une famille d’évolution partagent les types tirés.")
    allow_gen1: bool = rule("Génération I", "Pokémon autorisés", "Autorise les Pokémon n° 1 à 151 du Pokédex national.")
    allow_gen2: bool = rule("Génération II", "Pokémon autorisés", "Autorise les Pokémon n° 152 à 251 du Pokédex national.")
    allow_gen3: bool = rule("Génération III", "Pokémon autorisés", "Autorise les Pokémon n° 252 à 386 du Pokédex national.")
    allow_legendaries: bool = rule("Légendaires et fabuleux", "Pokémon autorisés", "Inclut les 21 légendaires et fabuleux des trois générations.")
    excluded_species: tuple[int, ...] = setting((), "Pokémon exclus", "Pokémon autorisés", "Retire les espèces cochées de tous les remplacements : dresseurs, obscurs, starters et cadeaux. N’exclut pas automatiquement leur famille. Les Pokémon conservés restent inchangés.", kind="species_set")
    excluded_types: tuple[int, ...] = setting((), "Types d’origine exclus", "Pokémon autorisés", "Retire du tirage les espèces ayant l’un de ces types dans le jeu d’origine, y compris les doubles types. Les Pokémon conservés et les types randomisés se règlent séparément.", kind="type_set")
    balance_species: bool = rule("Garder une puissance proche de l’original", "Pokémon autorisés", "Préfère des Pokémon dont le total de statistiques est proche de celui du Pokémon remplacé. Les exclusions restent appliquées.", False)
    randomize_held_items: bool = rule("Changer les objets tenus", "Objets tenus", "Remplace les objets déjà tenus par les adversaires. Les Pokémon sans objet restent sans objet.", False)
    useful_held_items_only: bool = rule("Objets utiles en combat uniquement", "Objets tenus", "Tire des baies de soin et des objets de combat, sans objet clé ni objet d’évolution.")
    trainer_level_multiplier: float = setting(1.0, "Niveau des adversaires ×", "Niveaux et capture", "Multiplie les niveaux, entre 1 et 100. Les starters et les Pokémon offerts gardent leur niveau.", kind="float", minimum=0.5, maximum=2.0, step=0.05)
    progressive_levels: bool = rule("Difficulté progressive", "Niveaux et capture", "Remplace le multiplicateur global par trois réglages selon le niveau d’origine de l’adversaire : 1 à 35, 36 à 50, puis 51 à 100. Les bonus des boss sont ajoutés ensuite. Ne change pas les starters ni les cadeaux.", False)
    early_level_multiplier: float = setting(1.0, "Début — niveaux d’origine 1–35 ×", "Niveaux et capture", "Multiplicateur des adversaires de niveau d’origine 1 à 35 lorsque la difficulté progressive est activée.", kind="float", minimum=0.5, maximum=2.0, step=0.05)
    mid_level_multiplier: float = setting(1.0, "Milieu — niveaux d’origine 36–50 ×", "Niveaux et capture", "Multiplicateur des adversaires de niveau d’origine 36 à 50 lorsque la difficulté progressive est activée.", kind="float", minimum=0.5, maximum=2.0, step=0.05)
    late_level_multiplier: float = setting(1.0, "Fin — niveaux d’origine 51–100 ×", "Niveaux et capture", "Multiplicateur des adversaires de niveau d’origine 51 à 100 lorsque la difficulté progressive est activée.", kind="float", minimum=0.5, maximum=2.0, step=0.05)
    experience_multiplier: float = setting(1.0, "Expérience gagnée ×", "Niveaux et capture", "Multiplie l’expérience gagnée en combat. ×1 conserve le jeu d’origine. Ne change pas l’expérience de départ des starters et cadeaux.", kind="float", minimum=0.25, maximum=5.0, step=0.25, decimals=2)
    purification_multiplier: int = setting(1, "Vitesse de purification ×", "Niveaux et capture", "Multiplie les diminutions de la jauge obscure. ×1 conserve le jeu d’origine ; la purification finale à la Relique reste nécessaire.", kind="int", minimum=1, maximum=10, step=1)
    capture_rate_multiplier: float = setting(1.0, "Taux de capture des obscurs ×", "Niveaux et capture", "Multiplie les taux de capture des obscurs, jusqu’à un maximum de 255.", kind="float", minimum=0.25, maximum=5.0, step=0.25)
    minimum_catch_rate: int = setting(0, "Taux de capture minimum", "Niveaux et capture", "0 : aucun minimum ajouté. Une autre valeur relève les taux de capture inférieurs à ce seuil.", kind="int", minimum=0, maximum=255, step=5)

    randomize_tm_moves: bool = rule("Mélanger les capacités des 50 CT", "CT", "Échange les capacités des 50 CT et leurs descriptions. Les huit CS restent inchangées.", False)
    tm_compatibility_mode: str = setting("original", "Compatibilité des CT", "CT", "Choisissez si chaque Pokémon garde ses CT d’origine, suit ses types actuels, apprend toutes les CT ou reçoit des compatibilités au hasard. Les CS restent inchangées.", kind="choice", choices=(("original", "D’origine"), ("type", "Selon les types"), ("universal", "Toutes les CT"), ("random", "Au hasard")))
    tm_ensure_offensive: bool = rule("Au moins une CT offensive compatible", "CT", "Lors d’un changement de compatibilité, garantit au moins une CT qui inflige des dégâts. Ne s’applique pas au mode d’origine.")
    randomize_field_items: bool = rule("Changer les objets des coffres", "Objets trouvés", "Remplace les objets ordinaires des coffres. Garde les quantités, les objets clés et les pierres. Les récompenses de l’histoire restent inchangées.", False)
    items_similar_value: bool = rule("Garder une valeur proche", "Objets trouvés", "Dans les coffres et les boutiques, garde la catégorie de l’objet et un prix entre la moitié et le double du prix d’origine.")
    keep_capture_items: bool = rule("Garder les Balls d’origine", "Objets trouvés", "Conserve les Balls déjà présentes dans les coffres et les boutiques. Les objets rares sans prix sont toujours conservés.")
    randomize_shop_items: bool = rule("Changer les objets vendus", "Boutiques", "Change les objets des six boutiques prises en charge. Les autres listes, les monnaies spéciales et les pierres restent inchangées.", False)
    shop_keep_healing: bool = rule("Garder les soins en boutique", "Boutiques", "Conserve les soins et les objets de combat déjà vendus.")
    boss_stronger: bool = rule("Renforcer les boss de l’histoire", "Boss", "Pour les Pokémon non obscurs : +10 % de niveau après le réglage général, IV d’au moins 20 et EV d’au moins 64 si le total reste légal. Ne change pas les obscurs ni la taille des équipes.", False)
    boss_team_variety: bool = rule("Éviter les familles en double chez les boss", "Boss", "Remplace les doublons de famille parmi leurs Pokémon non obscurs. Respecte les Pokémon autorisés et conserve les obscurs.", False)
    boss_shadow_legendary_mode: str = setting("any", "Légendaires et fabuleux obscurs", "Boss", "Suivre : utilise les réglages généraux. Garder : un légendaire ou fabuleux reste dans cette catégorie, les autres restent ordinaires. Aucun : les exclut. Les exclusions générales s’appliquent toujours.", kind="choice", choices=(("any", "Suivre les réglages généraux"), ("preserve", "Garder le statut d’origine"), ("exclude", "Aucun légendaire ni fabuleux")))
    boss_shadow_power_mode: str = setting("global", "Puissance des obscurs", "Boss", "Suivre : reprend l’équilibrage général. Proche : écart maximal de 20 % du total d’origine, ou 50 points si cette marge est plus grande. Sans équilibrage : ne cherche pas une puissance proche. Les filtres et le minimum restent appliqués.", kind="choice", choices=(("global", "Suivre les réglages généraux"), ("similar", "Proche de l’original"), ("free", "Sans équilibrage")))
    boss_shadow_min_bst: int = setting(0, "Total de statistiques minimum des obscurs", "Boss", "0 : aucun minimum. Compare le total des statistiques d’origine, avant leur redistribution. Ne change ni les niveaux ni les taux de capture.", kind="int", minimum=0, maximum=780, step=10)

    @classmethod
    def none(cls):
        return cls(starter_stage="any", **{item.name: False for item in fields(cls) if item.metadata["kind"] == "bool"})

    @classmethod
    def recommended(cls):
        return cls(randomize_trainer_moves=True, randomize_starter_moves=True,
                   randomize_gift_moves=True, randomize_learnsets=True, balance_species=True,
                   randomize_tm_moves=True, tm_compatibility_mode="type",
                   randomize_field_items=True, randomize_shop_items=True, boss_team_variety=True,
                   starter_balance_pair=True, starter_distinct_families=True, starter_complementary_types=True)

    @property
    def has_changes(self) -> bool:
        active = ("randomize_trainers", "randomize_shadows", *SPECIAL_OPTIONS.values(),
                  "randomize_trainer_moves", "randomize_starter_moves", "randomize_gift_moves",
                  "randomize_learnsets", "randomize_abilities", "randomize_stats", "randomize_types", "randomize_held_items",
                  "randomize_tm_moves", "randomize_field_items", "randomize_shop_items", "boss_stronger", "boss_team_variety", "trainer_force_evolved", "custom_shinies", "accessible_event_gifts")
        return (any(getattr(self, name) for name in active) or self.readable_stone_names or bool(self.evolution_groups) or bool(self.stone_shops)
                or (any(value != 1.0 for value in (self.early_level_multiplier, self.mid_level_multiplier, self.late_level_multiplier)) if self.progressive_levels else self.trainer_level_multiplier != 1.0)
                or self.experience_multiplier != 1.0 or self.purification_multiplier != 1
                or self.capture_rate_multiplier != 1.0 or self.minimum_catch_rate > 0
                or self.tm_compatibility_mode != "original")

    @property
    def evolution_groups(self) -> set[str]:
        return {name.removeprefix("evolve_") for name in (
            "evolve_trade", "evolve_trade_items", "evolve_coquiperl", "evolve_day_night", "evolve_beauty") if getattr(self, name)}

    @property
    def stone_shops(self) -> tuple[int, ...]:
        return tuple(index for index, enabled in ((3, self.stones_phenac), (5, self.stones_pyrite)) if enabled)


SPECIAL_OPTIONS = {"umbreon": "starter_umbreon", "espeon": "starter_espeon", "plusle": "gift_plusle",
                   "ho-oh": "gift_hooh", "celebi-event": "event_celebi", "pikachu-event": "event_pikachu"}
