from memory.pokemon_memory import pokemon_memory


def detect_patterns():
    memory = pokemon_memory()

    observations = []

    if memory["promo_count"] >= 3:
        observations.append(
            "Promo activity is increasing compared to Atlas' historical observations."
        )

    if memory["exclusive_count"] >= 2:
        observations.append(
            "Exclusive Pokémon Center products continue appearing frequently."
        )

    if memory["watch_count"] > memory["buy_count"]:
        observations.append(
            "Most recent Pokémon opportunities are still classified as WATCH. Atlas is remaining patient until stronger signals appear."
        )

    if memory["total_items_seen"] >= 10:
        observations.append(
            "Atlas has accumulated enough Pokémon observations to begin identifying seasonal trends."
        )

    return observations