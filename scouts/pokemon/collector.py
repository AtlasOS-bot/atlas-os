from scouts.base.atlas_scout import AtlasScout
from scouts.pokemon.enrichment import (
    enrich_pokemon_item,
)
from scouts.pokemon.internet_scout import (
    collect_official_pokemon_items,
)


class PokemonScout(AtlasScout):
    brand = "Pokemon"
    category = "pokemon"

    def collect(self):
        raw_items = (
            collect_official_pokemon_items()
        )

        return [
            enrich_pokemon_item(item)
            for item in raw_items
        ]

    def run(self):
        print(
            "Pokémon Internet Scout running..."
        )

        items = self.collect()

        print(
            f"Found {len(items)} unique "
            "Pokémon candidates"
        )

        saved_count = 0
        duplicate_count = 0

        for item in items[:50]:
            print("")
            print(
                f"Analyzing: {item['title']}"
            )
            print(
                "Product type:",
                item["product_type"],
            )
            print(
                "Collector tier:",
                item["collector_tier"],
            )
            print(
                "Release urgency:",
                item["release_urgency"]["level"],
            )

            saved = self.save_opportunity(
                item
            )

            if saved:
                saved_count += 1
            else:
                duplicate_count += 1

        print("")
        print("Pokémon Scout Summary")
        print("---------------------")
        print(f"Candidates: {len(items)}")
        print(f"Saved: {saved_count}")
        print(
            f"Duplicates skipped: "
            f"{duplicate_count}"
        )

        return items


def main():
    scout = PokemonScout()
    scout.run()


if __name__ == "__main__":
    main()