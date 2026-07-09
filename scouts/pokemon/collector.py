import requests
from bs4 import BeautifulSoup

from scouts.base.atlas_scout import AtlasScout
from .parser import parse_pokemon_item

SOURCE_URL = "https://www.pokemon.com/us/news"


class PokemonScout(AtlasScout):

    brand = "Pokemon"

    category = "pokemon"

    def collect(self):

        response = requests.get(
            SOURCE_URL,
            headers={
                "User-Agent": "AtlasOS Pokemon Scout"
            },
            timeout=20,
        )

        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        items = []

        for link in soup.find_all("a", href=True):

            title = " ".join(
                link.get_text(" ", strip=True).split()
            )

            if len(title) < 20:
                continue

            text = title.lower()

            if not any(
                term in text
                for term in [
                    "pokemon center",
                    "pokémon center",
                    "exclusive",
                    "promo",
                    "elite trainer box",
                    "booster",
                    "collection",
                ]
            ):
                continue

            url = link["href"]

            if url.startswith("/"):
                url = "https://www.pokemon.com" + url

            item = parse_pokemon_item(
                title=title,
                url=url,
            )

            items.append(item)

        return items

    def run(self):

        print("Pokémon Scout running...")

        items = self.collect()

        print(f"Found {len(items)} Pokémon items")

        for item in items:
            self.save_opportunity(item)


def main():
    PokemonScout().run()


if __name__ == "__main__":
    main()