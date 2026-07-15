import json
import os
from datetime import datetime, timezone
from pathlib import Path

from scouts.pokemon.enrichment import (
    enrich_pokemon_item,
)
from scouts.pokemon.internet_scout import (
    collect_official_pokemon_items,
)


DEFAULT_LIVE_SCAN_PATH = Path(
    os.environ.get(
        "ATLAS_POKEMON_LIVE_SCAN_PATH",
        ".atlas_data/pokemon_live_scan.json",
    )
)


DEFAULT_LIVE_HISTORY_PATH = Path(
    os.environ.get(
        "ATLAS_POKEMON_LIVE_HISTORY_PATH",
        ".atlas_data/pokemon_live_history",
    )
)


class PokemonLiveMonitor:

    def __init__(
        self,
        scan_path=None,
        history_directory=None,
        collector=None,
        enricher=None,
    ):
        self.scan_path = (
            Path(scan_path)
            if scan_path
            else DEFAULT_LIVE_SCAN_PATH
        )

        self.history_directory = (
            Path(history_directory)
            if history_directory
            else DEFAULT_LIVE_HISTORY_PATH
        )

        self.collector = (
            collector
            or collect_official_pokemon_items
        )

        self.enricher = (
            enricher
            or enrich_pokemon_item
        )

    def scan(self):
        started_at = utc_now()

        print("")
        print("=" * 64)
        print("ATLAS POKÉMON LIVE MONITOR")
        print("=" * 64)
        print(
            f"Scan started: {started_at}"
        )
        print("")

        scan_errors = []

        try:
            raw_items = self.collector()

        except Exception as error:
            raw_items = []

            scan_errors.append({
                "stage": "collection",
                "error_type": (
                    type(error).__name__
                ),
                "message": str(error),
            })

            print(
                "Pokémon collection failed:",
                f"{type(error).__name__}:",
                str(error),
            )

        enriched_items = []

        for raw_item in raw_items:
            try:
                enriched = self.enricher(
                    raw_item
                )

                normalized = (
                    normalize_live_item(
                        enriched
                    )
                )

                if normalized:
                    enriched_items.append(
                        normalized
                    )

            except Exception as error:
                scan_errors.append({
                    "stage": "enrichment",
                    "title": (
                        raw_item.get(
                            "title"
                        )
                        if isinstance(
                            raw_item,
                            dict,
                        )
                        else None
                    ),
                    "error_type": (
                        type(error).__name__
                    ),
                    "message": str(error),
                })

                print(
                    "Product enrichment failed:",
                    f"{type(error).__name__}:",
                    str(error),
                )

        unique_items = (
            deduplicate_live_items(
                enriched_items
            )
        )

        completed_at = utc_now()

        snapshot = {
            "scan_id": scan_identifier(
                completed_at
            ),
            "started_at": started_at,
            "completed_at": completed_at,
            "source": "pokemon_official",
            "status": (
                "SUCCESS"
                if not scan_errors
                else (
                    "PARTIAL"
                    if unique_items
                    else "FAILED"
                )
            ),
            "raw_item_count": len(
                raw_items
            ),
            "product_count": len(
                unique_items
            ),
            "error_count": len(
                scan_errors
            ),
            "errors": scan_errors,
            "summary": (
                build_scan_summary(
                    unique_items
                )
            ),
            "items": unique_items,
        }

        saved_paths = self.save(
            snapshot
        )

        self.print_summary(
            snapshot=snapshot,
            saved_paths=saved_paths,
        )

        return snapshot

    def save(self, snapshot):
        self.scan_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        write_json_atomic(
            path=self.scan_path,
            payload=snapshot,
        )

        self.history_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        history_path = (
            self.history_directory
            / (
                snapshot["scan_id"]
                + ".json"
            )
        )

        write_json_atomic(
            path=history_path,
            payload=snapshot,
        )

        return {
            "current_path": str(
                self.scan_path
            ),
            "history_path": str(
                history_path
            ),
        }

    def load_latest(self):
        return load_json(
            self.scan_path
        )

    def list_history(self):
        if not self.history_directory.exists():
            return []

        history_files = sorted(
            self.history_directory.glob(
                "*.json"
            ),
            reverse=True,
        )

        return [
            {
                "path": str(path),
                "snapshot": load_json(
                    path
                ),
            }
            for path in history_files
        ]

    def print_summary(
        self,
        snapshot,
        saved_paths,
    ):
        summary = snapshot.get(
            "summary",
            {},
        )

        print("")
        print("=" * 64)
        print("POKÉMON LIVE SCAN SUMMARY")
        print("=" * 64)

        print(
            "Status:",
            snapshot.get(
                "status",
                "UNKNOWN",
            ),
        )

        print(
            "Products found:",
            snapshot.get(
                "product_count",
                0,
            ),
        )

        print(
            "In stock:",
            summary.get(
                "in_stock_count",
                0,
            ),
        )

        print(
            "Out of stock:",
            summary.get(
                "out_of_stock_count",
                0,
            ),
        )

        print(
            "Preorder:",
            summary.get(
                "preorder_count",
                0,
            ),
        )

        print(
            "Unknown availability:",
            summary.get(
                "unknown_availability_count",
                0,
            ),
        )

        print(
            "Known prices:",
            summary.get(
                "known_price_count",
                0,
            ),
        )

        print(
            "Pokémon Center exclusives:",
            summary.get(
                "exclusive_count",
                0,
            ),
        )

        print(
            "Errors:",
            snapshot.get(
                "error_count",
                0,
            ),
        )

        print("")
        print("Top products detected:")
        print("----------------------")

        top_items = snapshot.get(
            "items",
            [],
        )[:15]

        if not top_items:
            print(
                "No products were detected "
                "during this scan."
            )

        for position, item in enumerate(
            top_items,
            start=1,
        ):
            print(
                f"{position}. "
                f"{item.get('title', 'Unknown product')}"
            )

            print(
                "   Availability:",
                item.get(
                    "availability"
                )
                or "Unknown",
            )

            print(
                "   Retail:",
                format_price(
                    item
                ),
            )

            print(
                "   Collector:",
                (
                    f"{item.get('collector_score', 0)}/100"
                ),
            )

            print(
                "   Flip:",
                (
                    f"{item.get('flip_score', 0)}/100"
                ),
            )

            print(
                "   Hold:",
                (
                    f"{item.get('hold_score', 0)}/100"
                ),
            )

            print(
                "   URL:",
                item.get(
                    "url"
                )
                or "Unknown",
            )

            print("")

        print(
            "Latest scan saved to:"
        )

        print(
            saved_paths[
                "current_path"
            ]
        )

        print(
            "History snapshot saved to:"
        )

        print(
            saved_paths[
                "history_path"
            ]
        )


def normalize_live_item(item):
    if not isinstance(
        item,
        dict,
    ):
        return None

    title = clean_text(
        item.get("title")
    )

    if not title:
        return None

    normalized = dict(item)

    normalized["title"] = title

    normalized["category"] = (
        item.get("category")
        or "pokemon"
    )

    normalized["brand"] = (
        item.get("brand")
        or "Pokemon"
    )

    normalized["url"] = (
        clean_text(
            item.get("url")
        )
        or None
    )

    normalized["sku"] = (
        clean_text(
            item.get("sku")
        )
        or None
    )

    normalized["availability"] = (
        clean_text(
            item.get(
                "availability"
            )
        )
        or None
    )

    normalized["retail_price"] = (
        normalize_price(
            item.get(
                "retail_price"
            )
        )
    )

    normalized["currency"] = (
        clean_text(
            item.get("currency")
        )
        or (
            "USD"
            if normalized[
                "retail_price"
            ] is not None
            else None
        )
    )

    normalized["release_date"] = (
        clean_text(
            item.get(
                "release_date"
            )
        )
        or None
    )

    normalized["image_url"] = (
        clean_text(
            item.get(
                "image_url"
            )
        )
        or None
    )

    normalized["live_product_key"] = (
        live_product_key(
            normalized
        )
    )

    normalized["observed_at"] = (
        utc_now()
    )

    return normalized


def deduplicate_live_items(items):
    indexed = {}

    for item in items:
        key = (
            item.get(
                "live_product_key"
            )
            or live_product_key(
                item
            )
        )

        if not key:
            continue

        existing = indexed.get(
            key
        )

        if existing is None:
            indexed[key] = dict(
                item
            )

            continue

        indexed[key] = merge_items(
            existing=existing,
            incoming=item,
        )

    unique_items = list(
        indexed.values()
    )

    unique_items.sort(
        key=live_ranking_key,
        reverse=True,
    )

    return unique_items


def merge_items(
    existing,
    incoming,
):
    merged = dict(existing)

    for key, value in incoming.items():
        if value in (
            None,
            "",
            [],
            {},
        ):
            continue

        current = merged.get(
            key
        )

        if current in (
            None,
            "",
            [],
            {},
        ):
            merged[key] = value

        elif key == "sources":
            merged[key] = merge_lists(
                current,
                value,
            )

        elif (
            key == "description"
            and len(str(value))
            > len(str(current))
        ):
            merged[key] = value

    return merged


def build_scan_summary(items):
    in_stock_count = 0
    out_of_stock_count = 0
    preorder_count = 0
    unknown_availability_count = 0
    known_price_count = 0
    exclusive_count = 0

    product_types = {}

    for item in items:
        availability = (
            normalize_availability(
                item.get(
                    "availability"
                )
            )
        )

        if availability in {
            "instock",
            "available",
            "availablefororder",
        }:
            in_stock_count += 1

        elif availability in {
            "outofstock",
            "soldout",
            "unavailable",
            "discontinued",
        }:
            out_of_stock_count += 1

        elif availability in {
            "preorder",
            "preorderonly",
            "comingsoon",
        }:
            preorder_count += 1

        else:
            unknown_availability_count += 1

        if item.get(
            "retail_price"
        ) is not None:
            known_price_count += 1

        if item.get(
            "pokemon_center_exclusive"
        ):
            exclusive_count += 1

        product_type = (
            item.get(
                "product_type"
            )
            or "other"
        )

        product_types[
            product_type
        ] = (
            product_types.get(
                product_type,
                0,
            )
            + 1
        )

    return {
        "in_stock_count": (
            in_stock_count
        ),
        "out_of_stock_count": (
            out_of_stock_count
        ),
        "preorder_count": (
            preorder_count
        ),
        "unknown_availability_count": (
            unknown_availability_count
        ),
        "known_price_count": (
            known_price_count
        ),
        "exclusive_count": (
            exclusive_count
        ),
        "product_types": (
            product_types
        ),
    }


def live_product_key(item):
    sku = normalize_identifier(
        item.get("sku")
    )

    if sku:
        return f"pokemon:sku:{sku}"

    url = normalize_url(
        item.get("url")
    )

    if url:
        return f"pokemon:url:{url}"

    title = normalize_title(
        item.get("title")
    )

    if title:
        return (
            f"pokemon:title:{title}"
        )

    return None


def live_ranking_key(item):
    strategy = (
        item.get(
            "best_strategy"
        )
        or {}
    )

    if isinstance(
        strategy,
        dict,
    ):
        strategy_score = (
            number_value(
                strategy.get(
                    "score"
                )
            )
        )

    else:
        strategy_score = 0

    return (
        availability_rank(
            item.get(
                "availability"
            )
        ),
        number_value(
            item.get(
                "collector_score"
            )
        ),
        number_value(
            item.get(
                "popularity_score"
            )
        ),
        number_value(
            item.get(
                "flip_score"
            )
        ),
        number_value(
            item.get(
                "hold_score"
            )
        ),
        strategy_score,
    )


def availability_rank(value):
    normalized = (
        normalize_availability(
            value
        )
    )

    if normalized in {
        "instock",
        "available",
        "availablefororder",
    }:
        return 4

    if normalized in {
        "preorder",
        "preorderonly",
        "comingsoon",
    }:
        return 3

    if normalized in {
        "outofstock",
        "soldout",
        "unavailable",
    }:
        return 2

    return 1


def merge_lists(
    first,
    second,
):
    first_values = (
        first
        if isinstance(
            first,
            list,
        )
        else [first]
    )

    second_values = (
        second
        if isinstance(
            second,
            list,
        )
        else [second]
    )

    return list(
        dict.fromkeys(
            value
            for value in (
                first_values
                + second_values
            )
            if value
        )
    )


def normalize_availability(value):
    return (
        str(value or "")
        .strip()
        .lower()
        .replace("_", "")
        .replace("-", "")
        .replace(" ", "")
    )


def normalize_identifier(value):
    return (
        str(value or "")
        .strip()
        .lower()
        .replace(" ", "-")
        .replace("_", "-")
    )


def normalize_url(value):
    return (
        str(value or "")
        .strip()
        .lower()
        .split("#")[0]
        .rstrip("/")
    )


def normalize_title(value):
    characters = []

    for character in (
        str(value or "")
        .strip()
        .lower()
    ):
        if character.isalnum():
            characters.append(
                character
            )

        else:
            characters.append(" ")

    return " ".join(
        "".join(
            characters
        ).split()
    )


def normalize_price(value):
    if value in (
        None,
        "",
    ):
        return None

    try:
        return round(
            float(
                str(value)
                .replace("$", "")
                .replace(",", "")
                .strip()
            ),
            2,
        )

    except (
        TypeError,
        ValueError,
    ):
        return None


def number_value(value):
    try:
        return float(
            value or 0
        )

    except (
        TypeError,
        ValueError,
    ):
        return 0.0


def format_price(item):
    price = item.get(
        "retail_price"
    )

    if price is None:
        return "Unknown"

    currency = (
        item.get("currency")
        or "USD"
    )

    try:
        amount = float(
            price
        )

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


def clean_text(value):
    return " ".join(
        str(value or "")
        .replace("\n", " ")
        .replace("\t", " ")
        .split()
    )


def scan_identifier(
    timestamp=None,
):
    timestamp = (
        timestamp
        or utc_now()
    )

    try:
        parsed = (
            datetime.fromisoformat(
                timestamp.replace(
                    "Z",
                    "+00:00",
                )
            )
        )

    except ValueError:
        parsed = datetime.now(
            timezone.utc
        )

    return parsed.strftime(
        "%Y-%m-%d_%H-%M-%S-%f"
    )


def write_json_atomic(
    path,
    payload,
):
    temporary_path = (
        path.with_suffix(
            path.suffix
            + ".tmp"
        )
    )

    with temporary_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            payload,
            file,
            indent=2,
            ensure_ascii=False,
        )

    temporary_path.replace(
        path
    )


def load_json(path):
    if not path.exists():
        return {}

    try:
        with path.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(
                file
            )

    except (
        json.JSONDecodeError,
        OSError,
    ):
        return {}

    return (
        data
        if isinstance(
            data,
            dict,
        )
        else {}
    )


def utc_now():
    return datetime.now(
        timezone.utc
    ).isoformat()


def main():
    monitor = (
        PokemonLiveMonitor()
    )

    monitor.scan()


if __name__ == "__main__":
    main()