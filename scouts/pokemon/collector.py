import requests
from bs4 import BeautifulSoup

from .parser import parse_pokemon_item
from .scorer import score_pokemon_item

SOURCE_URL = "https://www.pokemon.com/us/news"


def collect_pokemon_center_items():
    print("Pokémon Scout running...")

    response = requests.get(
        SOURCE_URL,
        headers={"User-Agent": "AtlasOS Pokemon Scout"},
        timeout=20,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    items = []

    for link in soup.find_all("a", href=True):
        title = " ".join(link.get_text(" ", strip=True).split())
        url = link["href"]

        if len(title) < 20:
            continue

        text = title.lower()

        if not any(
            term in text
            for term in [
                "pokemon center",
                "pokémon center",
                "exclusive",
                "elite trainer box",
                "etb",
                "booster",
                "promo",
                "collection",
            ]
        ):
            continue

        if url.startswith("/"):
            url = "https://www.pokemon.com" + url

        item = parse_pokemon_item(title=title, url=url)
        intelligence = score_pokemon_item(item)

        item["intelligence"] = intelligence
        items.append(item)

    return items


if __name__ == "__main__":
    results = collect_pokemon_center_items()

    print(f"Found {len(results)} Pokémon items")

    for item in results[:5]:
        print("-----")
        print(item["title"])
        print(item["url"])
        print(item["intelligence"])