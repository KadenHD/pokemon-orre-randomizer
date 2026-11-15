"""Presentation order only; never change gift identities or random draws."""


def order_purification_gifts(rows):
    """Sort threshold-bearing rows in place of one another, stably by count.

    Keep every other gift at its original position. Zero is a real threshold;
    missing thresholds and native event-only gifts keep their existing order.
    The input list and its records are never mutated.
    """
    rows = list(rows)
    positions = [index for index, row in enumerate(rows) if type(row.get("purifications")) is int]
    ordered = sorted((rows[index] for index in positions), key=lambda row: row["purifications"])
    for index, row in zip(positions, ordered, strict=True):
        rows[index] = row
    return rows
