"""Encounter move policies retain historical boolean profile values.

False keeps native encounter behavior, True draws moves, and 'natural' uses level-up
data. This preserves the signed shape of older profiles without conflating a
non-random selection with keeping the previous species' move slots.
"""
from typing import Literal, TypeAlias

MoveMode: TypeAlias = bool | Literal["natural"]
MOVE_CHOICES = ((False, "Capacités d’origine"), ("natural", "Capacités naturelles du Pokémon"),
                (True, "Capacités aléatoires"))
MOVE_DESCRIPTION = ("D’origine : conserve le fonctionnement de la rencontre du jeu. "
                    "Naturelles : utilise les capacités apprises par niveau par la nouvelle espèce. "
                    "Aléatoires : tire de nouvelles capacités. Les capacités obscures et les emplacements spéciaux restent protégés.")


def natural_moves(learnset, level, originals, valid_moves):
    """Last distinct learned moves at this level, filling only regular slots."""
    result = list(originals)
    slots = [i for i, move in enumerate(result) if move == 0 or move in valid_moves]
    if not slots:
        return result
    learned = []
    for learned_level, move in learnset:
        if 0 < learned_level <= level and move in valid_moves:
            if move in learned:
                learned.remove(move)
            learned.append(move)
    chosen = learned[-len(slots):]
    for slot, move in zip(slots, chosen + [0] * (len(slots) - len(chosen)), strict=True):
        result[slot] = move
    return result
