def parse_pokemon_item(title, url, description=""):
    return {
        "brand": "Pokémon Center",
        "title": title,
        "description": description,
        "url": url,
        "category": "TCG",
        "source": "pokemon_center",
    }