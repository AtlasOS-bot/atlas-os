from scouts.base.atlas_scout import (
    AtlasScout,
)
from scouts.one_piece.internet_scout import (
    collect_one_piece_items,
)
from scouts.tcg.catalog_store import (
    TcgCatalogStore,
)
from scouts.tcg.enrichment import (
    enrich_tcg_item,
)


class OnePieceScout(
    AtlasScout
):
    brand = "One Piece Card Game"
    category = "one_piece"

    def __init__(self):
        super().__init__()

        self.catalog_store = (
            TcgCatalogStore()
        )

    def collect(self):
        raw_items = (
            collect_one_piece_items()
        )

        return [
            enrich_tcg_item(
                item=item,
                tcg_name="one_piece",
            )
            for item in raw_items
        ]

    def run(self):
        print(
            "One Piece Card Game "
            "Internet Scout running..."
        )

        items = self.collect()

        catalog_result = (
            self.catalog_store.upsert_many(
                items
            )
        )

        saved_count = 0
        duplicate_count = 0

        print("")
        print(
            f"Found {len(items)} unique "
            "One Piece products"
        )

        for item in items[:50]:
            print("")
            print("=" * 62)

            print(
                f"Analyzing: "
                f"{item.get('title', 'Unknown')}"
            )

            print("=" * 62)

            print(
                "Product type:",
                item.get(
                    "product_type",
                    "other",
                ),
            )

            print(
                "Set codes:",
                (
                    ", ".join(
                        item.get(
                            "set_codes",
                            [],
                        )
                    )
                    or "Unknown"
                ),
            )

            print(
                "Retail price:",
                format_price(item),
            )

            print(
                "Release date:",
                item.get(
                    "release_date"
                )
                or "Unknown",
            )

            print(
                "Availability:",
                item.get(
                    "availability"
                )
                or "Unknown",
            )

            print(
                "Limited release:",
                yes_no(
                    item.get(
                        "limited_release"
                    )
                ),
            )

            print(
                "Promo included:",
                yes_no(
                    item.get(
                        "promo_included"
                    )
                ),
            )

            print(
                "Collector variant:",
                yes_no(
                    item.get(
                        "collector_variant"
                    )
                ),
            )

            print(
                "Collector:",
                (
                    f"{item.get('collector_score', 0)}/100 "
                    f"({item.get('collector_level', 'LOW')})"
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
                "Official URL:",
                item.get("url")
                or "Unknown",
            )

            saved = (
                self.save_opportunity(
                    item
                )
            )

            if saved:
                saved_count += 1

            else:
                duplicate_count += 1

        top_items = (
            self.catalog_store.top(
                limit=10,
                category="one_piece",
            )
        )

        print("")
        print(
            "ONE PIECE SCOUT SUMMARY"
        )
        print("-----------------------")

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

        print("")
        print(
            "TOP ONE PIECE OPPORTUNITIES"
        )
        print("---------------------------")

        for position, item in enumerate(
            top_items,
            start=1,
        ):
            strategy = (
                item.get(
                    "best_strategy"
                )
                or {}
            )

            print(
                f"{position}. "
                f"{item.get('title', 'Unknown')}"
            )

            print(
                "   Strategy:",
                strategy.get(
                    "strategy",
                    "UNKNOWN",
                ),
            )

            print(
                "   Strategy score:",
                f"{strategy.get('score', 0)}/100",
            )

            print(
                "   Collector:",
                f"{item.get('collector_score', 0)}/100",
            )

            print(
                "   Flip:",
                f"{item.get('flip_score', 0)}/100",
            )

            print(
                "   Hold:",
                f"{item.get('hold_score', 0)}/100",
            )

            print("")

        print(
            "Live catalog saved to:"
        )

        print(
            ".atlas_data/"
            "tcg_live_catalog.json"
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


def yes_no(value):
    return (
        "YES"
        if value
        else "NO"
    )


def main():
    scout = OnePieceScout()
    scout.run()


if __name__ == "__main__":
    main()