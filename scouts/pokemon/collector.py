from scouts.base.atlas_scout import AtlasScout
from scouts.pokemon.alert_brief import (
    PokemonAlertBrief,
)
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
from scouts.pokemon.release_brief import (
    PokemonReleaseBrief,
)
from scouts.pokemon.release_store import (
    PokemonReleaseStore,
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

        self.release_store = (
            PokemonReleaseStore()
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

        release_calendar = (
            self.release_store.save(
                items
            )
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
                "Product event:",
                state_change["event"],
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
                "Product type:",
                item["product_type"],
            )

            print(
                "Release date:",
                (
                    item.get(
                        "release_date"
                    )
                    or "Unknown"
                ),
            )

            print(
                "Release urgency:",
                item["release_urgency"][
                    "level"
                ],
            )

            print(
                "Consensus score:",
                (
                    f"{item.get('consensus_score', 0)}/100 "
                    f"({item.get('consensus_level', 'LOW')})"
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

            saved = self.save_opportunity(
                item
            )

            if saved:
                saved_count += 1
            else:
                duplicate_count += 1

        active_alerts = (
            self.alert_store.active()
        )

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
            f"New alerts created: "
            f"{alert_count}"
        )
        print(
            f"Active alerts: "
            f"{len(active_alerts)}"
        )
        print(
            f"Release calendar entries: "
            f"{release_calendar['count']}"
        )

        print("")
        print(
            PokemonAlertBrief.generate(
                active_alerts,
                limit=10,
            )
        )

        print("")
        print(
            PokemonReleaseBrief.generate(
                items=items,
                limit=15,
            )
        )

        return items


def main():
    scout = PokemonScout()
    scout.run()


if __name__ == "__main__":
    main()