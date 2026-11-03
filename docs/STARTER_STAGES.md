# Starter evolution stages — 0.8.0

The **Pokémon + moves** and **Pokémon only** modes by default select the two starters from the
three-stage family base forms. The levels remain at 26 and 25. The other filters and the d'evolution
fixes retain their usual settings.

In **Advanced → Starters and gifts**.

| Choice of stage | Eligible Pokémon |
| --- | --- |
| Any stage | No filter on the stadium |
| Base form | Without preevolution, including Pokémon which does not evolve if the three-stage filter is deactivated |
| First evolution | An evolution after a base. For example Ivysaur |
| Final evolution | Evolved shape without further evolution. For example Venusaur |

**Three-stage families only** requires two successive evolutions present in Colosseum. The number of
branches does not count: Eevee and its evolutions form a family at two stages. Wurmple and its two
branches form a family at three stages. Babies are taken into account: Pichu → Pikachu → Raichu. The
evolutions added after the third generation are not invented.

These rules only change the starters replaced. Keep Umbreon or Espeon its species, level and
experience. This starter can nevertheless force its partner if the rules of power, types or families
of the duo are active. If no pair is possible, the tool indicates which constraints to adjust. It
does not bypass exclusions.

## Balancing and reproduction

With the three-stage filter and the Base selection, the near power option compares the candidates to
Eevee, the base of origin of the duo, instead of comparing a base to Umbreon or Espeon. The power of
the duo is always compared between the two actually drawn species, with their final statistics.

The chains come from the targets of evolution of the original verified REL. The calculation refuses
cycles, distinguishes the stages of the branches and does not change any condition of evolution. The
options of accessible evolutions and of sale of stones remain responsible for the practical
conditions of evolution in the game.

The uniform choice among the eligible pairs keeps the drawing field `starter-pair-sha256-v1`. The
profiles 0.5, 0.6, 0.6.1 and 0.7 are checked first with their original footprint, then converted:
the former Boolean of basic shapes becomes the Base or All Stages choice, and the new filter is
disabled. They therefore keep their selections and their old balance. Their re-export is in the
current format and keeps these values, without enabling the new defects.

The engine `starter-evolution-stages-v9` applies to the European ROM GC6P01, revision 0, in ISO or
RVZ format. The language of the interface does not participate in the drawing.
