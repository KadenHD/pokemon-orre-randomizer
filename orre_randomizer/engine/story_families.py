"""Joint evolution-family allocation for starters, Shadow Pokémon and gifts."""
from functools import lru_cache
from hashlib import sha256

from .family_matching import match_families


def ordered_family_edges(seed, hard, preferred, families):
    edges = {}
    for slot, pool in hard.items():
        favored = {families[index] for index in preferred[slot]}
        edges[slot] = sorted({families[index] for index in pool}, key=lambda family: (
            family not in favored, sha256(f"story-families-v1\0{seed}\0{slot}\0{family}".encode()).digest(), family))
    return edges


def allocate_story_families(edges, reserved):
    order = sorted(edges, key=lambda slot: (len(edges[slot]), slot))
    return match_families(edges, order, reserved)


def select_story_starters(preferred_pair, pairings, families, edges, reserved):
    """Keep the seeded draw if it fits, otherwise try every valid family pair."""
    baseline = allocate_story_families(edges, reserved)
    can_fit_all = len(baseline) == len(edges)
    used = set(baseline.values())

    @lru_cache(maxsize=None)
    def fits(extra):
        if not extra or used.isdisjoint(extra):
            return True
        if len(extra) == 2 and any(not fits((family,)) for family in extra):
            return False
        return len(allocate_story_families(edges, reserved | set(extra))) == len(edges)

    def penalty(pair):
        first, second = (families[index] for index in pair)
        return int(first == second) + int(first in reserved) + int(second in reserved)

    def complete(pair):
        return can_fit_all and not penalty(pair) and fits(tuple(sorted(families[index] for index in pair)))

    if complete(preferred_pair):
        return preferred_pair
    best = preferred_pair
    for first, seconds in pairings.items():
        for second in seconds:
            pair = first, second
            if complete(pair):
                return pair
            if penalty(pair) < penalty(best):
                best = pair
    return best
