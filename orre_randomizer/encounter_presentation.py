"""Display numbers and acquisition conditions; never change game identities."""

PLUSLE_CONDITION = "Après la première victoire contre Bouledisco, dans le scénario."
HOOH_CONDITION = ("Purifier les 48 Pokémon obscurs d’origine, puis gagner les 100 combats du Mont Bataille "
                  "en mode Combat avec une équipe enregistrée depuis le mode Histoire, sans la changer.")


def colosseum_shadow_number(shadow_id):
    from .preview import BASE_SHADOWS
    numbers = {sid: number for number, (sid, _) in enumerate(BASE_SHADOWS, 1)}
    # The optional postgame opponent uses a spare internal slot, not roster no. 96.
    numbers[96] = len(BASE_SHADOWS) + 1
    return numbers.get(shadow_id, shadow_id)


def colosseum_gift_condition(row, text):
    if row.get('key') == 'plusle':
        return text(PLUSLE_CONDITION)
    if row.get('key') == 'ho-oh':
        return text(HOOH_CONDITION)
    if row.get('purifications') is not None:
        count = row['purifications']
        source = 'Adelbert · {count} purification' if count == 1 else 'Adelbert · {count} purifications'
        return text(source, count=count)
    if row.get('event'):
        return text('Distribution événementielle d’origine')
    return ''
