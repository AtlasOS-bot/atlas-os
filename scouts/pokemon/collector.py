from scouts.base.atlas_scout import AtlasScout
from scouts.pokemon.alert_intelligence import (
    calculate_alert_intelligence,
)
from scouts.pokemon.alert_store import (
    PokemonAlertStore,
)
from scouts.pokemon.enrichment import (
    enrich_pokemon_item,
)
from scouts.pokemon.internet_scout import (
    collect_official_pokemon_items,
)
from scouts.pokemon.state_tracker import (
    PokemonStateTracker,
)


class PokemonScout(AtlasScout):
    brand = "Pokemon"
    category = "pokemon"

    def __init__(self):
        super().__init__()

        self.state_tracker = (
            PokemonStateTracker()
        )

        self.alert_store = (
            PokemonAlertStore()
        )

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
        meaningful_change_count = 0
        alert_count = 0

        for item in items[:50]:
            state_change = (
                self.state_tracker.observe(
                    item
                )
            )

            item["state_change"] = (
                state_change
            )

            item["state_event"] = (
                state_change["event"]
            )

            item["state_importance"] = (
                state_change["importance"]
            )

            alert = (
                calculate_alert_intelligence(
                    item
                )
            )

            item["alert_intelligence"] = (
                alert
            )

            saved_alert = (
                self.alert_store.save(
                    item=item,
                    alert=alert,
                )
            )

            if (
                state_change["event"]
                != "NO_CHANGE"
            ):
                meaningful_change_count += 1

            if saved_alert:
                alert_count += 1

            print("")
            print(
                f"Analyzing: {item['title']}"
            )

            print(
                "Product type:",
                item["product_type"],
            )

            print(
                "Official confirmations:",
                item.get(
                    "confirmation_count",
                    1,
                ),
            )

            print(
                "Consensus score:",
                (
                    f"{item.get('consensus_score', 0)}/100 "
                    f"({item.get('consensus_level', 'LOW')})"
                ),
            )

            print(
                "Product event:",
                state_change["event"],
            )

            print(
                "Event importance:",
                state_change["importance"],
            )

            print(
                "Event reason:",
                state_change["reason"],
            )

            print(
                "Alert score:",
                f"{alert['score']}/100",
            )

            print(
                "Alert priority:",
                alert["priority"],
            )

            print(
                "Alert action:",
                alert["action"],
            )

            print(
                "Alert created:",
                (
                    "YES"
                    if saved_alert
                    else "NO"
                ),
            )

            print(
                "Popularity:",
                (
                    f"{item['popularity_score']}/100 "
                    f"({item['popularity_level']})"
                ),
            )

            print(
                "Collector score:",
                f"{item['collector_score']}/100",
            )

            print(
                "Collector level:",
                item["collector_level"],
            )

            print(
                "Flip score:",
                f"{item['flip_score']}/100",
            )

            print(
                "Hold score:",
                f"{item['hold_score']}/100",
            )

            print(
                "Sleeper score:",
                f"{item['sleeper_score']}/100",
            )

            print(
                "Best strategy:",
                item["best_strategy"][
                    "strategy"
                ],
            )

            print(
                "Release urgency:",
                item["release_urgency"][
                    "level"
                ],
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
        print(
            f"Meaningful state changes: "
            f"{meaningful_change_count}"
        )
        print(
            f"Alerts created: "
            f"{alert_count}"
        )

        return items


def main():
    scout = PokemonScout()
    scout.run()


if __name__ == "__main__":
    main()