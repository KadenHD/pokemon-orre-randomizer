# Stades des starters — 0.8.0

Les modes **Pokémon + capacités** et **Pokémon seuls** choisissent par défaut
les deux starters parmi les formes de base de familles à trois stades.
Les niveaux restent à 26 et 25. Les autres filtres et les corrections d’évolution
conservent leurs réglages habituels.

Dans **Avancé → Starters et cadeaux** :

| Choix du stade | Pokémon admissibles |
| --- | --- |
| Tous les stades | Aucun filtre sur le stade |
| Forme de base | Sans préévolution, y compris les Pokémon qui n’évoluent pas si le filtre à trois stades est désactivé |
| Première évolution | Une évolution après une base ; par exemple Herbizarre |
| Évolution finale | Forme évoluée sans évolution supplémentaire ; par exemple Florizarre |

**Familles à trois stades uniquement** exige deux évolutions successives présentes
dans Colosseum. Le nombre de branches ne compte pas : Évoli et ses évolutions
forment une famille à deux stades. Chenipotte et ses deux branches forment une
famille à trois stades. Les bébés sont pris en compte : Pichu → Pikachu → Raichu.
Les évolutions ajoutées après la troisième génération ne sont pas inventées.

Ces règles ne changent que les starters remplacés. Garder Noctali ou Mentali
conserve son espèce, son niveau et son expérience. Ce starter peut néanmoins
contraindre son partenaire si les règles de puissance, de types ou de familles
du duo sont actives. Si aucune paire n’est possible, l’outil indique quelles
contraintes ajuster ; il ne contourne pas les exclusions.

## Équilibrage et reproduction

Avec le filtre à trois stades et le choix Base, l’option de puissance proche
compare les candidats à Évoli, la base d’origine du duo, au lieu de comparer une
base à Noctali ou Mentali. La puissance du duo est toujours comparée entre les
deux espèces effectivement tirées, avec leurs statistiques finales.

Les chaînes viennent des cibles d’évolution du REL original vérifié. Le calcul
refuse les cycles, distingue les stades des branches et ne change aucune
condition d’évolution. Les options d’évolutions accessibles et de vente de
pierres restent responsables des conditions pratiques d’évolution dans le jeu.

Le choix uniforme parmi les paires admissibles garde le domaine de tirage
`starter-pair-sha256-v1`. Les profils 0.5, 0.6, 0.6.1 et 0.7 sont d’abord vérifiés
avec leur empreinte d’origine, puis convertis : l’ancien booléen de formes de
base devient le choix Base ou Tous les stades, et le nouveau filtre est désactivé.
Ils gardent donc leurs sélections et leur ancien équilibrage. Leur réexport se
fait au format courant et conserve ces valeurs, sans activer les nouveaux défauts.

Le moteur `starter-evolution-stages-v9` s’applique à la ROM européenne GC6P01,
révision 0, au format ISO ou RVZ. La langue de l’interface ne participe pas au tirage.
