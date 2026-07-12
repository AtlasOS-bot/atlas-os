from scouts.base.atlas_scout import (
    AtlasScout,
)
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
            print("=" * 60)
            print(
                f"Analyzing: {item['title']}"
            )
            print("=" * 60)

            print(
                "Product summary:",
                item["product_summary"],
            )

            print(
                "Product type:",
                item["product_type"],
            )

            print(
                "Set or collection:",
                (
                    item.get("set_name")
                    or "Unknown"
                ),
            )

            print(
                "SKU:",
                (
                    item.get("sku")
                    or "Unknown"
                ),
            )

            print(
                "Retail price:",
                format_price(item),
            )

            print(
                "Availability:",
                (
                    item.get(
                        "availability"
                    )
                    or "Unknown"
                ),
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
                "Booster packs:",
                (
                    item.get(
                        "pack_count"
                    )
                    if item.get(
                        "pack_count"
                    ) is not None
                    else "Unknown"
                ),
            )

            print(
                "Promo cards:",
                (
                    item.get(
                        "promo_card_count"
                    )
                    if item.get(
                        "promo_card_count"
                    ) is not None
                    else "Unknown"
                ),
            )

            accessories = item.get(
                "included_accessories"
            ) or []

            print(
                "Included accessories:",
                (
                    ", ".join(
                        accessories
                    )
                    if accessories
                    else "Unknown"
                ),
            )

            print(
                "Image:",
                (
                    item.get(
                        "image_url"
                    )
                    or "Unknown"
                ),
            )

            print(
                "Official confirmations:",
                item.get(
                    "confirmation_count",
                    1,
                ),
            )

            print(
                "Sources:",
                (
                    ", ".join(
                        item.get(
                            "sources",
                            [],
                        )
                    )
                    or "Unknown"
                ),
            )

            print(
                "Detail completeness:",
                (
                    f"{item['detail_completeness_score']}/100 "
                    f"({item['detail_completeness_level']})"
                ),
            )

            missing = item.get(
                "missing_detail_fields"
            ) or []

            print(
                "Missing details:",
                (
                    ", ".join(missing)
                    if missing
                    else "None"
                ),
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


def format_price(item):
    price = item.get(
        "retail_price"
    )

    currency = (
        item.get("currency")
        or "USD"
    )

    if price is None:
        return "Unknown"

    try:
        price_text = (
            f"{float(price):.2f}"
        )

    except (
        TypeError,
        ValueError,
    ):
        return str(price)

    if currency == "USD":
        return f"${price_text}"

    return f"{price_text} {currency}"


def main():
    scout = PokemonScout()
    scout.run()


if __name__ == "__main__":
    main()