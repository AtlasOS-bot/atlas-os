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
from scouts.tcg.catalog_store import (
    TcgCatalogStore,
)


EMPTY_RELEASE_CALENDAR = {
    "generated_at": None,
    "count": 0,
    "releases": [],
}

EMPTY_CATALOG_RESULT = {
    "generated_at": None,
    "count": 0,
    "created_this_scan": 0,
    "updated_this_scan": 0,
    "items": [],
}


class PokemonScout(
    AtlasScout
):
    brand = "Pokemon"
    category = "pokemon"

    def __init__(
        self,
        collector=None,
        enricher=None,
    ):
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

        self.catalog_store = (
            TcgCatalogStore()
        )

        self.collector = (
            collector
            or collect_official_pokemon_items
        )

        self.enricher = (
            enricher
            or enrich_pokemon_item
        )

    def collect(self):
        try:
            raw_items = self.collector()

        except Exception as error:
            self._log_stage_failure(
                stage="collection",
                error=error,
            )

            raw_items = []

        enriched_items = []

        for raw_item in raw_items:
            try:
                enriched_items.append(
                    self.enricher(raw_item)
                )

            except Exception as error:
                self._log_stage_failure(
                    stage="enrichment",
                    error=error,
                    identifier=self._item_title(
                        raw_item
                    ),
                )

        return enriched_items

    def run(self):
        print(
            "Pokémon Internet Scout running..."
        )

        items = self.collect()

        print(
            f"Found {len(items)} unique "
            "Pokémon candidates"
        )

        try:
            release_calendar = (
                self.release_store.save(
                    items
                )
            )

        except Exception as error:
            self._log_stage_failure(
                stage="release_calendar",
                error=error,
            )

            release_calendar = dict(
                EMPTY_RELEASE_CALENDAR
            )

        saved_count = 0
        duplicate_count = 0
        opportunity_failed_count = 0
        meaningful_change_count = 0
        alert_count = 0
        failed_item_count = 0

        for item in items[:50]:
            if not isinstance(item, dict):
                failed_item_count += 1

                self._log_stage_failure(
                    stage="item_processing",
                    error=TypeError(
                        "item is not a dict"
                    ),
                    identifier=self._item_title(
                        item
                    ),
                )

                continue

            try:
                state_change = (
                    self.state_tracker.observe(
                        item
                    )
                )

            except Exception as error:
                self._log_stage_failure(
                    stage="state_tracking",
                    error=error,
                    identifier=self._item_title(
                        item
                    ),
                )

                state_change = None

            if state_change is not None:
                item["state_change"] = (
                    state_change
                )

                item["state_event"] = (
                    state_change["event"]
                )

                item["state_importance"] = (
                    state_change["importance"]
                )

            try:
                alert = (
                    calculate_alert_intelligence(
                        item
                    )
                )

            except Exception as error:
                self._log_stage_failure(
                    stage="alert_scoring",
                    error=error,
                    identifier=self._item_title(
                        item
                    ),
                )

                alert = None

            saved_alert = None

            if alert is not None:
                item["alert_intelligence"] = (
                    alert
                )

                try:
                    saved_alert = (
                        self.alert_store.save(
                            item=item,
                            alert=alert,
                        )
                    )

                except Exception as error:
                    self._log_stage_failure(
                        stage="alert_persistence",
                        error=error,
                        identifier=self._item_title(
                            item
                        ),
                    )

                    saved_alert = None

            if (
                state_change
                and state_change["event"]
                != "NO_CHANGE"
            ):
                meaningful_change_count += 1

            if saved_alert:
                alert_count += 1

            print("")
            print("=" * 64)

            print(
                f"Analyzing: "
                f"{item.get('title', 'Unknown')}"
            )

            print("=" * 64)

            print(
                "Product summary:",
                (
                    item.get(
                        "product_summary"
                    )
                    or "Unknown"
                ),
            )

            print(
                "Product type:",
                item.get(
                    "product_type",
                    "other",
                ),
            )

            print(
                "Set or collection:",
                (
                    item.get(
                        "set_name"
                    )
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
                display_value(
                    item.get(
                        "pack_count"
                    )
                ),
            )

            print(
                "Promo cards:",
                display_value(
                    item.get(
                        "promo_card_count"
                    )
                ),
            )

            accessories = (
                item.get(
                    "included_accessories"
                )
                or []
            )

            print(
                "Included accessories:",
                (
                    ", ".join(accessories)
                    if accessories
                    else "Unknown"
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
                    f"{item.get('detail_completeness_score', 0)}/100 "
                    f"({item.get('detail_completeness_level', 'LIMITED')})"
                ),
            )

            missing_details = (
                item.get(
                    "missing_detail_fields"
                )
                or []
            )

            print(
                "Missing details:",
                (
                    ", ".join(
                        missing_details
                    )
                    if missing_details
                    else "None"
                ),
            )

            print(
                "Product event:",
                (state_change or {}).get(
                    "event",
                    "UNKNOWN",
                ),
            )

            print(
                "Event importance:",
                (state_change or {}).get(
                    "importance",
                    "UNKNOWN",
                ),
            )

            print(
                "Event reason:",
                (state_change or {}).get(
                    "reason",
                    "State tracking failed "
                    "for this item.",
                ),
            )

            print(
                "Alert score:",
                f"{(alert or {}).get('score', 0)}/100",
            )

            print(
                "Alert priority:",
                (alert or {}).get(
                    "priority",
                    "UNKNOWN",
                ),
            )

            print(
                "Alert action:",
                (alert or {}).get(
                    "action",
                    "UNKNOWN",
                ),
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
                "Release urgency:",
                (
                    item.get(
                        "release_urgency"
                    )
                    or {}
                ).get(
                    "level",
                    "LOW",
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
                "Popularity:",
                (
                    f"{item.get('popularity_score', 0)}/100 "
                    f"({item.get('popularity_level', 'LOW')})"
                ),
            )

            print(
                "Collector score:",
                (
                    f"{item.get('collector_score', 0)}/100 "
                    f"({item.get('collector_level', 'LOW')})"
                ),
            )

            print(
                "Flip score:",
                f"{item.get('flip_score', 0)}/100",
            )

            print(
                "Hold score:",
                f"{item.get('hold_score', 0)}/100",
            )

            print(
                "Sleeper score:",
                f"{item.get('sleeper_score', 0)}/100",
            )

            strategy = (
                item.get(
                    "best_strategy"
                )
                or {}
            )

            print(
                "Best strategy:",
                strategy.get(
                    "strategy",
                    "UNKNOWN",
                ),
            )

            print(
                "Strategy score:",
                f"{strategy.get('score', 0)}/100",
            )

            print(
                "Hold profile:",
                (
                    item.get(
                        "hold_profile"
                    )
                    or "Unknown"
                ),
            )

            print(
                "Official URL:",
                (
                    item.get("url")
                    or "Unknown"
                ),
            )

            try:
                saved = (
                    self.save_opportunity(
                        item
                    )
                )

            except Exception as error:
                self._log_stage_failure(
                    stage=(
                        "reasoning_and_"
                        "opportunity_persistence"
                    ),
                    error=error,
                    identifier=self._item_title(
                        item
                    ),
                )

                saved = None

            if saved is True:
                saved_count += 1

            elif saved is False:
                duplicate_count += 1

            else:
                opportunity_failed_count += 1

        try:
            catalog_result = (
                self.catalog_store.upsert_many(
                    items
                )
            )

        except Exception as error:
            self._log_stage_failure(
                stage="catalog",
                error=error,
            )

            catalog_result = dict(
                EMPTY_CATALOG_RESULT
            )

        try:
            active_alerts = (
                self.alert_store.active()
            )

        except Exception as error:
            self._log_stage_failure(
                stage="alert_summary",
                error=error,
            )

            active_alerts = []

        try:
            top_pokemon = (
                self.catalog_store.top(
                    limit=10,
                    category="pokemon",
                )
            )

        except Exception as error:
            self._log_stage_failure(
                stage="catalog_summary",
                error=error,
            )

            top_pokemon = []

        print("")
        print(
            "POKÉMON SCOUT SUMMARY"
        )
        print("---------------------")

        print(
            f"Candidates: {len(items)}"
        )

        print(
            f"Saved opportunities: "
            f"{saved_count}"
        )

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

        print(
            "New catalog products:",
            catalog_result[
                "created_this_scan"
            ],
        )

        print(
            "Updated catalog products:",
            catalog_result[
                "updated_this_scan"
            ],
        )

        print(
            "Total TCG catalog products:",
            catalog_result["count"],
        )

        print(
            f"Items with processing failures: "
            f"{failed_item_count}"
        )

        print(
            f"Opportunities that failed to save: "
            f"{opportunity_failed_count}"
        )

        print("")
        print(
            "TOP POKÉMON OPPORTUNITIES"
        )
        print("-------------------------")

        if not top_pokemon:
            print(
                "No Pokémon catalog "
                "products available yet."
            )

        for position, product in enumerate(
            top_pokemon,
            start=1,
        ):
            product_strategy = (
                product.get(
                    "best_strategy"
                )
                or {}
            )

            print(
                f"{position}. "
                f"{product.get('title', 'Unknown')}"
            )

            print(
                "   Strategy:",
                product_strategy.get(
                    "strategy",
                    "UNKNOWN",
                ),
            )

            print(
                "   Strategy score:",
                (
                    f"{product_strategy.get('score', 0)}/100"
                ),
            )

            print(
                "   Collector:",
                (
                    f"{product.get('collector_score', 0)}/100"
                ),
            )

            print(
                "   Flip:",
                (
                    f"{product.get('flip_score', 0)}/100"
                ),
            )

            print(
                "   Hold:",
                (
                    f"{product.get('hold_score', 0)}/100"
                ),
            )

            print(
                "   Sleeper:",
                (
                    f"{product.get('sleeper_score', 0)}/100"
                ),
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

        print("")
        print(
            "Pokémon products added to:"
        )

        print(
            ".atlas_data/"
            "tcg_live_catalog.json"
        )

        return items

    @staticmethod
    def _item_title(item):
        if isinstance(item, dict):
            return (
                item.get("title")
                or item.get("url")
                or "Unknown item"
            )

        return "Unknown item"

    @staticmethod
    def _log_stage_failure(
        stage,
        error,
        identifier=None,
    ):
        location = (
            f" ({identifier})"
            if identifier
            else ""
        )

        print(
            f"[PokemonScout] {stage} "
            f"failed{location}: "
            f"{type(error).__name__}: "
            f"{error}"
        )


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
        amount = float(price)

    except (
        TypeError,
        ValueError,
    ):
        return str(price)

    if currency == "USD":
        return f"${amount:.2f}"

    return (
        f"{amount:.2f} "
        f"{currency}"
    )


def display_value(value):
    if value is None:
        return "Unknown"

    return value


def main():
    scout = PokemonScout()
    scout.run()


if __name__ == "__main__":
    main()