"""
Atlas v21 - Module 8: DEMO dataset for local dashboard testing only.

Everything in this module is fabricated sample data for visually
testing the dashboard UI - it is never written to Supabase, and the
live generator (scripts/generate_dashboard.py) never imports this
file. Every demo opportunity_id is prefixed "demo-" so demo and live
data can never collide or be mistaken for one another even if
inspected directly in the DOM/HTML.

Market strength, confidence, and market trend on these cards are NOT
hardcoded - they are computed the exact same way live cards are
(evaluate_opportunity + classify_market_strength/classify_confidence),
so the demo faithfully exercises the real classification logic, not a
fake shortcut.

Product images are simple generated placeholder SVGs (dashboard/assets/demo/) -
plain shapes/colors, not real brand logos or scraped photos. Product
and eBay links point at example.com and are clearly inert.
"""

from datetime import datetime, timedelta, timezone

from collector_intelligence.dashboard_models import (
    HeartedItem, OpportunityImage, OpportunityUserOverride, UserExternalLink,
)
from collector_intelligence.models import CollectorOpportunity

DEMO_LABEL = "DEMO"
DEMO_ID_PREFIX = "demo-"


def _hours_ago(hours):
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()


def _demo_image(slug, alt_text):
    return OpportunityImage(
        opportunity_id=f"{DEMO_ID_PREFIX}{slug}",
        primary_image_url=f"assets/demo/{slug}.svg",
        image_alt_text=alt_text,
        image_source_name="Demo asset",
    )


def _demo_links(slug):
    return [
        UserExternalLink(
            owner_type="opportunity", owner_id=f"{DEMO_ID_PREFIX}{slug}",
            link_type="ebay_sold", url=f"https://example.com/demo/ebay-sold/{slug}",
            label="eBay Sold (demo)",
        ),
    ]


def build_demo_opportunities():
    """Returns the 8 demo CollectorOpportunity objects. Field values
    are chosen to exercise a realistic SPREAD of market strength,
    confidence, and trend once run through the real scoring engine -
    none of those values are hardcoded here."""

    return [
        CollectorOpportunity(
            opportunity_id=f"{DEMO_ID_PREFIX}pitch-black-etb",
            product_name="Pitch Black ETB",
            brand="Pokemon", franchise="Pokemon TCG",
            category="Trading Card Game", subcategory="Elite Trainer Box",
            retail_price=49.99, recent_sold_price=140.0, current_market_price=135.0,
            sold_listing_count=80, sales_velocity=15.0, sellout_speed="under 10 minutes",
            demand_direction="SURGING", stated_quantity=80, limited_quantity=True,
            purchase_limit=1, catalyst_signals=["community_hype", "press_pickup", "influencer_post"],
            sealed_product=True, exclusive_promo=True, status="sold_out",
            source_type="OFFICIAL", source_name="Pokemon Center (demo)",
            purchase_url="https://example.com/demo/pitch-black-etb",
            last_verified_at=_hours_ago(2),
        ),
        CollectorOpportunity(
            opportunity_id=f"{DEMO_ID_PREFIX}pokemon-center-etb",
            product_name="Pokemon Center ETB",
            brand="Pokemon", franchise="Pokemon TCG",
            category="Trading Card Game", subcategory="Elite Trainer Box",
            retail_price=44.99, recent_sold_price=60.0, current_market_price=58.0,
            sold_listing_count=15, demand_direction="RISING", stated_quantity=1500,
            sealed_product=True, source_type="RETAILER", source_name="Pokemon Center (demo)",
            purchase_url="https://example.com/demo/pokemon-center-etb",
            last_verified_at=_hours_ago(6),
        ),
        CollectorOpportunity(
            opportunity_id=f"{DEMO_ID_PREFIX}one-piece-round1-promo",
            product_name="ONE PIECE Round1 Promo",
            brand="Bandai", franchise="One Piece",
            category="Trading Card Game", subcategory="Promo Card",
            retailer="Round1", redeemable_reward=True, event_exclusive=True,
            recent_sold_price=85.0, current_market_price=80.0,
            sold_listing_count=25, demand_direction="RISING",
            source_type="COMMUNITY", source_name="Community reports (demo)",
            purchase_url="https://example.com/demo/one-piece-round1-promo",
            last_verified_at=_hours_ago(18),
        ),
        CollectorOpportunity(
            opportunity_id=f"{DEMO_ID_PREFIX}starbucks-halloween-cup",
            product_name="Starbucks Halloween Cup",
            brand="Starbucks", category="Seasonal Merchandise",
            retail_price=24.99, recent_sold_price=45.0, current_market_price=40.0,
            sold_listing_count=60, demand_direction="FLAT", sellout_speed="same day",
            source_type="SOCIAL", source_name="Social posts (demo)",
            purchase_url="https://example.com/demo/starbucks-halloween-cup",
            last_verified_at=_hours_ago(30),
        ),
        CollectorOpportunity(
            opportunity_id=f"{DEMO_ID_PREFIX}disney-lorcana-set",
            product_name="Disney Lorcana Set (Demo)",
            brand="Disney", franchise="Lorcana",
            category="Trading Card Game", subcategory="Booster Case",
            retail_price=99.99, recent_sold_price=150.0, current_market_price=145.0,
            sold_listing_count=30, demand_direction="RISING", stated_quantity=800,
            sealed_product=True, source_type="RETAILER", source_name="Retailer listing (demo)",
            purchase_url="https://example.com/demo/disney-lorcana-set",
            last_verified_at=_hours_ago(10),
        ),
        CollectorOpportunity(
            opportunity_id=f"{DEMO_ID_PREFIX}dodgers-giveaway",
            product_name="Dodgers Stadium Giveaway Bobblehead (Demo)",
            brand="MLB", franchise="Dodgers",
            category="Stadium Giveaway",
            redeemable_reward=True, event_exclusive=True,
            recent_sold_price=35.0, current_market_price=30.0,
            sold_listing_count=12, demand_direction="FLAT", stated_quantity=40000,
            source_type="NEWS", source_name="Local news (demo)",
            purchase_url="https://example.com/demo/dodgers-giveaway",
            last_verified_at=_hours_ago(48),
        ),
        CollectorOpportunity(
            opportunity_id=f"{DEMO_ID_PREFIX}funko-convention-exclusive",
            product_name="Funko Convention Exclusive Pop! (Demo)",
            brand="Funko", category="Vinyl Figure",
            retail_price=20.0, recent_sold_price=180.0, current_market_price=170.0,
            sold_listing_count=8, demand_direction="RISING",
            convention_exclusive=True, stated_quantity=1800,
            source_type="EVENT", source_name="Convention floor report (demo)",
            purchase_url="https://example.com/demo/funko-convention-exclusive",
            last_verified_at=_hours_ago(4),
        ),
        CollectorOpportunity(
            opportunity_id=f"{DEMO_ID_PREFIX}lego-insider-set",
            product_name="LEGO Insider Exclusive Set (Demo)",
            brand="LEGO", category="Building Set",
            retail_price=59.99, status="announced",
            source_type="OFFICIAL", source_name="LEGO newsroom (demo)",
            purchase_url="https://example.com/demo/lego-insider-set",
            last_verified_at=_hours_ago(72),
        ),
    ]


def build_demo_images():
    """opportunity_id -> OpportunityImage, one per demo item."""
    slugs_and_alts = [
        ("pitch-black-etb", "Pitch Black ETB"),
        ("pokemon-center-etb", "Pokemon Center ETB"),
        ("one-piece-round1-promo", "ONE PIECE Round1 Promo"),
        ("starbucks-halloween-cup", "Starbucks Halloween Cup"),
        ("disney-lorcana-set", "Disney Lorcana Set"),
        ("dodgers-giveaway", "Dodgers Stadium Giveaway Bobblehead"),
        ("funko-convention-exclusive", "Funko Convention Exclusive Pop!"),
        ("lego-insider-set", "LEGO Insider Exclusive Set"),
    ]
    return {
        f"{DEMO_ID_PREFIX}{slug}": _demo_image(slug, alt)
        for slug, alt in slugs_and_alts
    }


def build_demo_links():
    """opportunity_id -> [UserExternalLink], eBay Sold only (product
    link already comes from purchase_url like a real OFFICIAL/RETAILER
    opportunity would)."""
    slugs = [
        "pitch-black-etb", "pokemon-center-etb", "one-piece-round1-promo",
        "starbucks-halloween-cup", "disney-lorcana-set", "dodgers-giveaway",
        "funko-convention-exclusive", "lego-insider-set",
    ]
    return {f"{DEMO_ID_PREFIX}{slug}": _demo_links(slug) for slug in slugs}


def build_demo_overrides():
    """Exactly one demo override, so the visual report has a card
    showing the 'Manual override' badge. Atlas's own read on the Funko
    convention exclusive is thin (only 8 sold listings so far); the
    override represents a collector's real-time floor report."""
    return {
        f"{DEMO_ID_PREFIX}funko-convention-exclusive": OpportunityUserOverride(
            opportunity_id=f"{DEMO_ID_PREFIX}funko-convention-exclusive",
            market_strength_override="STRONG",
            reason="Sold out on the convention floor in under 5 minutes - "
                   "stronger than the thin early listing data shows.",
        ),
    }


def build_demo_hearted_items():
    """One Atlas-linked heart, one fully-manual entry - covers both
    Hearted Items row types in the visual report."""
    return [
        HeartedItem(
            id="demo-hearted-1",
            opportunity_id=f"{DEMO_ID_PREFIX}pitch-black-etb",
            status="SAVED", priority="high", target_price=120.0,
            hearted_at=_hours_ago(1),
        ),
        HeartedItem(
            id="demo-hearted-2",
            opportunity_id=None,
            product_name="Vintage Charizard Card (Demo, manual entry)",
            image_url="assets/demo/manual-entry.svg",
            product_link="https://example.com/demo/vintage-charizard",
            ebay_sold_link="https://example.com/demo/ebay-sold/vintage-charizard",
            msrp=None, last_sold_price=650.0, market_strength="STRONG",
            category="Trading Card", priority="medium", target_price=600.0,
            quantity=1, tags=["grail", "vintage"],
            status="SAVED", hearted_at=_hours_ago(20),
        ),
    ]
