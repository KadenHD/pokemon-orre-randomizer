"""Deterministic maximum matching for encounter slots and evolution families."""


def match_families(edges, order, reserved=()):
    owners, chosen = {}, {}
    reserved = frozenset(reserved)

    def augment(slot, visited):
        for family in edges[slot]:
            if family in visited or family in reserved:
                continue
            visited.add(family)
            previous = owners.get(family)
            if previous is None or augment(previous, visited):
                owners[family] = slot
                chosen[slot] = family
                return True
        return False

    for slot in order:
        augment(slot, set())
    return chosen
