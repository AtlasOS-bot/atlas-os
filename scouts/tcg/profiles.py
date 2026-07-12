TCG_PROFILES = {
    "lorcana": {
        "brand": "Disney Lorcana",
        "official_domains": {
            "disneylorcana.com",
            "www.disneylorcana.com",
            "ravensburger.com",
            "www.ravensburger.com",
        },
        "product_rules": [
            (
                "booster_display",
                [
                    "booster display",
                    "booster box",
                    "display box",
                    "24 booster packs",
                ],
            ),
            (
                "booster_pack",
                [
                    "booster pack",
                ],
            ),
            (
                "illumineers_trove",
                [
                    "illumineer's trove",
                    "illumineers trove",
                    "trove",
                ],
            ),
            (
                "gift_set",
                [
                    "gift set",
                    "gift box",
                ],
            ),
            (
                "collection_set",
                [
                    "collection starter set",
                    "collection set",
                    "collector's collection",
                    "collectors collection",
                    "curator's collection",
                    "curators collection",
                ],
            ),
            (
                "quest_box",
                [
                    "illumineer's quest",
                    "illumineers quest",
                ],
            ),
            (
                "starter_deck",
                [
                    "starter deck",
                    "2-player starter set",
                    "two-player starter set",
                    "gateway",
                ],
            ),
            (
                "promo_card",
                [
                    "promo card",
                    "promotional card",
                    "set championship promo",
                    "challenge promo",
                ],
            ),
            (
                "playmat",
                [
                    "playmat",
                    "play mat",
                ],
            ),
            (
                "accessory",
                [
                    "card sleeves",
                    "deck box",
                    "portfolio",
                    "binder",
                    "lore counter",
                    "damage dice",
                ],
            ),
        ],
        "high_value_terms": {
            "enchanted": 20,
            "serialized": 24,
            "promo card": 14,
            "exclusive": 12,
            "limited": 12,
            "collector": 10,
            "curator": 10,
            "set championship": 14,
            "challenge promo": 16,
            "first chapter": 15,
            "disney100": 18,
            "d23": 22,
        },
        "scarcity_terms": {
            "limited edition": 16,
            "exclusive": 12,
            "while supplies last": 14,
            "special collection": 10,
            "event exclusive": 18,
            "tournament exclusive": 18,
            "online exclusive": 12,
        },
        "risk_terms": {
            "reprint": -14,
            "reprinted": -14,
            "restock": -8,
            "available again": -8,
            "mass market": -5,
        },
        "base_scores": {
            "booster_display": 34,
            "booster_pack": 12,
            "illumineers_trove": 29,
            "gift_set": 25,
            "collection_set": 30,
            "quest_box": 24,
            "starter_deck": 16,
            "promo_card": 30,
            "playmat": 16,
            "accessory": 8,
            "other": 5,
        },
        "sealed_types": {
            "booster_display",
            "booster_pack",
            "illumineers_trove",
            "gift_set",
            "collection_set",
            "quest_box",
            "starter_deck",
        },
    },
    "one_piece": {
        "brand": "One Piece Card Game",
        "official_domains": {
            "en.onepiece-cardgame.com",
            "onepiece-cardgame.com",
            "p-bandai.com",
            "p-bandai.com/us",
        },
        "product_rules": [
            (
                "booster_box",
                [
                    "booster box",
                    "booster display",
                    "24 packs",
                ],
            ),
            (
                "booster_pack",
                [
                    "booster pack",
                    "extra booster",
                    "premium booster",
                ],
            ),
            (
                "starter_deck",
                [
                    "starter deck",
                    "start deck",
                ],
            ),
            (
                "double_pack",
                [
                    "double pack set",
                    "double pack",
                ],
            ),
            (
                "tin_pack",
                [
                    "tin pack set",
                    "tin pack",
                ],
            ),
            (
                "devil_fruits_collection",
                [
                    "devil fruits collection",
                    "devil fruit collection",
                ],
            ),
            (
                "illustration_box",
                [
                    "illustration box",
                ],
            ),
            (
                "premium_collection",
                [
                    "premium collection",
                    "premium card collection",
                    "premium bandai",
                    "premium card set",
                ],
            ),
            (
                "promo_card",
                [
                    "promo card",
                    "promotion card",
                    "tournament pack",
                    "winner card",
                ],
            ),
            (
                "accessory",
                [
                    "card sleeves",
                    "card sleeve",
                    "playmat",
                    "play mat",
                    "storage box",
                    "deck case",
                ],
            ),
        ],
        "high_value_terms": {
            "manga rare": 24,
            "manga card": 24,
            "alternate art": 14,
            "alt art": 14,
            "leader parallel": 15,
            "special card": 13,
            "secret rare": 12,
            "promotion card": 12,
            "promo card": 12,
            "winner card": 20,
            "championship": 18,
            "anniversary": 16,
            "premium bandai": 18,
            "limited": 12,
            "exclusive": 12,
        },
        "scarcity_terms": {
            "premium bandai": 18,
            "order limit": 12,
            "limit 1": 16,
            "limited edition": 16,
            "event exclusive": 18,
            "store exclusive": 14,
            "official shop exclusive": 16,
            "while supplies last": 14,
        },
        "risk_terms": {
            "reprint": -16,
            "reprinted": -16,
            "card the best": -5,
            "restock": -8,
            "available again": -8,
        },
        "base_scores": {
            "booster_box": 35,
            "booster_pack": 15,
            "starter_deck": 18,
            "double_pack": 22,
            "tin_pack": 23,
            "devil_fruits_collection": 27,
            "illustration_box": 25,
            "premium_collection": 33,
            "promo_card": 32,
            "accessory": 8,
            "other": 5,
        },
        "sealed_types": {
            "booster_box",
            "booster_pack",
            "starter_deck",
            "double_pack",
            "tin_pack",
            "devil_fruits_collection",
            "illustration_box",
            "premium_collection",
        },
    },
}


def normalize_tcg_name(value):
    normalized = (
        str(value or "")
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )

    aliases = {
        "disney_lorcana": "lorcana",
        "lorcana_tcg": "lorcana",
        "onepiece": "one_piece",
        "one_piece_card_game": "one_piece",
        "one_piece_tcg": "one_piece",
    }

    return aliases.get(
        normalized,
        normalized,
    )


def get_tcg_profile(tcg_name):
    normalized = normalize_tcg_name(
        tcg_name
    )

    if normalized not in TCG_PROFILES:
        raise ValueError(
            f"Unsupported TCG profile: {tcg_name}"
        )

    return TCG_PROFILES[normalized]