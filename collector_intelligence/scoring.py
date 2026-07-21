"""
Atlas v21 - Module 3: individual score computations.

Every score function takes a CollectorOpportunity (and optional
ScoringContext) and returns (value, explanation), where value is a
0-100 float and explanation is
{"positives": [...], "negatives": [...], "notes": [...]}. Nothing here
invents a fact - a function only reacts to fields the opportunity
actually has set. Missing evidence yields a low/neutral score plus a
note, never a guessed high score.
"""

COMPLETE_SET_MARKERS = [
    "complete set",
    "complete promo set",
    "full set",
    "entire set",
    "whole set",
]


def clamp(value, low=0.0, high=100.0):
    return max(low, min(high, value))


# Backward-compatible internal alias used throughout this module.
_clamp = clamp


def _explanation():
    return {"positives": [], "negatives": [], "notes": []}


# ---------------------------------------------------------------
# Shared evidence helpers
# ---------------------------------------------------------------

def is_rumored(opportunity):
    """
    True if the opportunity's own status says "rumored", or if any
    of the raw Module 2 signal detections attached as evidence were
    flagged rumored. A rumor must never be silently treated as a
    confirmed release just because status wasn't set.
    """
    if (opportunity.status or "").strip().lower() == "rumored":
        return True

    for item in opportunity.evidence or []:
        if isinstance(item, dict) and item.get("rumored"):
            return True

    return False


def product_represents_complete_set(opportunity):
    """
    True if the opportunity's own identity fields describe a complete
    set (i.e. the product being evaluated IS the set), as opposed to
    an individual item whose only resale evidence happens to be a
    complete-set price.
    """
    haystack = " ".join(
        filter(
            None,
            [
                opportunity.product_name,
                opportunity.edition_name,
                opportunity.category,
                opportunity.subcategory,
            ],
        )
    ).lower()

    return any(marker in haystack for marker in COMPLETE_SET_MARKERS)


def resale_refers_to_complete_set(opportunity):
    """
    True if any risk note or raw evidence detection indicates the
    known resale price describes a complete set rather than a single
    unit (this is exactly what Module 2's mentions_complete_set()
    flags via a RISK_WARNING signal).
    """
    for risk in opportunity.risks or []:
        if "complete set" in risk.lower():
            return True

    for item in opportunity.evidence or []:
        if isinstance(item, dict):
            notes = (item.get("notes") or "").lower()

            if "complete set" in notes:
                return True

    return False


def is_complete_set_mismatch(opportunity):
    """
    True when resale evidence describes a complete set but the
    opportunity itself is not the complete set - the exact situation
    the mission spec requires flagging with a warning, a confidence
    reduction, and a CRITICAL_BUY block.
    """
    return resale_refers_to_complete_set(
        opportunity
    ) and not product_represents_complete_set(opportunity)


def resolve_target_buy_price(opportunity):
    """
    Module 3's buy-price priority: required_spend, then retail_price,
    then a pre-set target_buy_price (e.g. an analyst override already
    on the opportunity). Distinct from Module 1's resolved_spend() in
    that it also considers an existing target_buy_price.
    """
    if opportunity.required_spend is not None:
        return opportunity.required_spend, "required_spend"

    if opportunity.retail_price is not None:
        return opportunity.retail_price, "retail_price"

    if opportunity.target_buy_price is not None:
        return opportunity.target_buy_price, "target_buy_price"

    return None, None


def resolve_target_sell_price(opportunity):
    """
    Module 3's resale-price priority: recent_sold_price, then
    current_market_price, then estimated_market_price.
    peak_market_price is deliberately never used here - the mission
    spec forbids treating a peak as the normal expected sell price.
    """
    if opportunity.recent_sold_price is not None:
        return opportunity.recent_sold_price, "observed"

    if opportunity.current_market_price is not None:
        return opportunity.current_market_price, "observed"

    if opportunity.estimated_market_price is not None:
        return opportunity.estimated_market_price, "estimated"

    return None, None


def _has_identity_beyond_brand(opportunity):
    return any(
        [
            opportunity.franchise,
            opportunity.collaboration_partner,
            opportunity.product_line,
            opportunity.set_or_series,
        ]
    )


# ---------------------------------------------------------------
# COLLECTOR SCORE
# ---------------------------------------------------------------

def score_collector(opportunity, context=None):
    explanation = _explanation()
    value = 0.0

    if opportunity.exclusive_artwork:
        value += 15
        explanation["positives"].append("Exclusive artwork")

    if opportunity.exclusive_character:
        value += 12
        explanation["positives"].append("Exclusive character")

    if opportunity.artist_name:
        value += 8
        explanation["positives"].append(
            f"Named artist significance ({opportunity.artist_name})"
        )

    if opportunity.anniversary_release:
        value += 12
        explanation["positives"].append("Anniversary relevance")

    if opportunity.first_collaboration:
        value += 12
        explanation["positives"].append("First collaboration of its kind")

    if opportunity.first_edition:
        value += 10
        explanation["positives"].append("First edition")

    if opportunity.numbered:
        value += 8
        explanation["positives"].append("Numbered release")

    if opportunity.set_or_series:
        value += 8
        explanation["positives"].append("Part of a cohesive collectible set")

    if (
        opportunity.event_exclusive
        or opportunity.convention_exclusive
        or opportunity.tournament_exclusive
    ):
        value += 10
        explanation["positives"].append(
            "Difficult-to-recreate acquisition story "
            "(event/convention/tournament exclusive)"
        )

    if opportunity.source_type == "OFFICIAL":
        value += 7
        explanation["positives"].append("Official licensed release")

    if opportunity.collaboration_partner:
        value += 8
        explanation["positives"].append(
            f"Named collaboration partner ({opportunity.collaboration_partner})"
        )

    # A recognized franchise/named characters are legitimate but
    # deliberately weak signals - the mission spec lists them as
    # positive evidence while also warning never to let franchise
    # popularity alone drive a high score. Kept small on purpose.
    if opportunity.franchise:
        value += 5
        explanation["positives"].append(
            f"Recognized franchise ({opportunity.franchise}) - weighted "
            "modestly, not treated as strong evidence alone"
        )

    if opportunity.character_names:
        value += 5
        explanation["positives"].append(
            "Named characters: " + ", ".join(opportunity.character_names)
        )

    if context and context.franchise_strength is not None:
        bonus = _clamp(context.franchise_strength, 0, 100) * 0.15
        value += bonus
        explanation["notes"].append(
            "Franchise-strength context applied "
            f"(+{bonus:.1f} from caller-supplied franchise_strength)"
        )

    if value == 0:
        explanation["notes"].append(
            "No structured collector-desirability evidence found "
            "(franchise/brand popularity alone is not scored)"
        )

    return _clamp(value), explanation


# ---------------------------------------------------------------
# FLIP SCORE
# ---------------------------------------------------------------

def score_flip(opportunity, context=None, complete_set_mismatch=False):
    explanation = _explanation()
    value = 0.0

    buy_price, _ = resolve_target_buy_price(opportunity)
    sell_price, sell_kind = resolve_target_sell_price(opportunity)

    if buy_price and sell_price:
        ratio = sell_price / buy_price
        spread_points = 0.0

        if ratio >= 3:
            spread_points = 25
        elif ratio >= 2:
            spread_points = 18
        elif ratio >= 1.5:
            spread_points = 10
        elif ratio > 1:
            spread_points = 4

        if complete_set_mismatch:
            # The spread is still real evidence of upside - flip
            # attractiveness isn't zeroed out here. The bulk of the
            # complete-set penalty belongs to risk_score/confidence_
            # score (see score_risk/score_confidence), which is what
            # ultimately caps the recommendation - this is a mild
            # discount, not a second full penalty.
            spread_points *= 0.75
            explanation["negatives"].append(
                "Resale price reflects a complete set, not this "
                "individual item - spread discounted accordingly"
            )

        if spread_points:
            value += spread_points
            explanation["positives"].append(
                f"Retail-to-resale spread ratio {ratio:.1f}x "
                f"({sell_kind})"
            )
    else:
        explanation["notes"].append(
            "Cannot compute a retail-to-resale spread - "
            "buy and/or sell price unknown"
        )

    if opportunity.sellout_speed:
        value += 12
        explanation["positives"].append(
            f"Rapid sellout observed ({opportunity.sellout_speed})"
        )

    if opportunity.demand_direction == "SURGING":
        value += 10
        explanation["positives"].append("Surging demand")
    elif opportunity.demand_direction == "RISING":
        value += 6
        explanation["positives"].append("Rising demand")
    elif opportunity.demand_direction == "FALLING":
        value -= 15
        explanation["negatives"].append("Falling demand")

    exclusivity_flags = [
        opportunity.retailer_exclusive,
        opportunity.event_exclusive,
        opportunity.lottery_required,
        opportunity.membership_required,
    ]

    if any(exclusivity_flags):
        value += 6
        explanation["positives"].append(
            "Difficult acquisition adds flip premium"
        )

    if opportunity.purchase_window_start and opportunity.purchase_window_end:
        value += 5
        explanation["positives"].append("Narrow, defined purchase window")

    if opportunity.limited_quantity:
        value += 8
        explanation["positives"].append("Limited quantity")

    if opportunity.purchase_limit:
        value += 4
        explanation["positives"].append(
            f"Purchase limit of {opportunity.purchase_limit} per customer"
        )

    if opportunity.exclusive_promo:
        value += 5
        explanation["positives"].append("Exclusive promotional acquisition")

    if not _has_identity_beyond_brand(opportunity):
        value -= 8
        explanation["negatives"].append(
            "Unclear item identity beyond brand name"
        )

    if (opportunity.status or "").strip().lower() == "rumored":
        value -= 15
        explanation["negatives"].append("Release not yet confirmed")

    return _clamp(value), explanation


# ---------------------------------------------------------------
# HOLD SCORE
# ---------------------------------------------------------------

def score_hold(opportunity, context=None):
    explanation = _explanation()
    value = 0.0

    if opportunity.sealed_product:
        value += 10
        explanation["positives"].append("Sealed product")

    if opportunity.first_edition:
        value += 10
        explanation["positives"].append("First edition")

    if opportunity.anniversary_release:
        value += 8
        explanation["positives"].append("Meaningful anniversary")

    if opportunity.exclusive_artwork:
        value += 8
        explanation["positives"].append("Exclusive art")

    if opportunity.stated_quantity is not None:
        if opportunity.stated_quantity <= 1000:
            value += 10
            explanation["positives"].append(
                f"Low stated quantity ({opportunity.stated_quantity})"
            )
        else:
            value += 3
            explanation["positives"].append(
                f"Stated quantity known ({opportunity.stated_quantity})"
            )

    if opportunity.event_exclusive or opportunity.tournament_exclusive:
        value += 8
        explanation["positives"].append("Event/tournament exclusivity")

    if opportunity.collaboration_partner and opportunity.first_collaboration:
        value += 10
        explanation["positives"].append(
            "Historically important first collaboration"
        )

    if opportunity.lottery_required or opportunity.membership_required:
        value += 6
        explanation["positives"].append(
            "Discontinued/restricted acquisition method"
        )

    if context and context.franchise_strength is not None:
        bonus = _clamp(context.franchise_strength, 0, 100) * 0.15
        value += bonus
        explanation["notes"].append(
            "Franchise-strength context applied "
            f"(+{bonus:.1f} from caller-supplied franchise_strength)"
        )

    if opportunity.demand_direction == "FALLING":
        value -= 10
        explanation["negatives"].append("Falling demand")

    no_scarcity_evidence = not any(
        [
            opportunity.limited_quantity,
            opportunity.numbered,
            opportunity.stated_quantity,
            opportunity.event_exclusive,
            opportunity.convention_exclusive,
            opportunity.tournament_exclusive,
            opportunity.membership_exclusive,
            opportunity.retailer_exclusive,
            opportunity.region_exclusive,
        ]
    )

    if no_scarcity_evidence:
        value -= 10
        explanation["negatives"].append(
            "No differentiation from a normal mass-produced product"
        )

    return _clamp(value), explanation


# ---------------------------------------------------------------
# SCARCITY SCORE
# ---------------------------------------------------------------

def score_scarcity(opportunity, context=None, config=None):
    explanation = _explanation()
    value = 0.0

    low_q = config.low_stated_quantity_threshold if config else 100
    mod_q = config.moderate_stated_quantity_threshold if config else 500
    high_q = config.high_stated_quantity_threshold if config else 2000

    if opportunity.stated_quantity is not None:
        quantity = opportunity.stated_quantity

        if quantity <= low_q:
            value += 25
        elif quantity <= mod_q:
            value += 18
        elif quantity <= high_q:
            value += 10
        else:
            value += 4

        explanation["positives"].append(
            f"Stated production quantity: {quantity}"
        )

    if opportunity.numbered:
        value += 10
        explanation["positives"].append("Numbered release")

    if opportunity.purchase_limit:
        value += 8
        explanation["positives"].append(
            f"Purchase limit of {opportunity.purchase_limit}"
        )

    if opportunity.event_exclusive:
        value += 10
        explanation["positives"].append("Event-exclusive distribution")

    if opportunity.tournament_exclusive:
        value += 10
        explanation["positives"].append("Tournament-exclusive distribution")

    if opportunity.convention_exclusive:
        value += 8
        explanation["positives"].append("Convention-exclusive distribution")

    if opportunity.membership_exclusive or opportunity.membership_required:
        value += 8
        explanation["positives"].append("Membership requirement")

    if opportunity.lottery_required:
        value += 12
        explanation["positives"].append("Lottery-restricted distribution")

    if opportunity.region_exclusive or opportunity.regional_exclusive:
        value += 6
        explanation["positives"].append("Regional restriction")

    if opportunity.purchase_window_start and opportunity.purchase_window_end:
        value += 6
        explanation["positives"].append("Narrow purchase window")

    if (opportunity.status or "").strip().lower() == "sold_out":
        value += 8
        explanation["positives"].append("Currently sold out")

    has_corroborating_evidence = value > 0

    if opportunity.limited_quantity and not has_corroborating_evidence:
        value += 5
        explanation["notes"].append(
            "\"Limited quantity\" flag present with no corroborating "
            "stated quantity, purchase limit, or exclusivity evidence "
            "- treated as a weak scarcity signal, not proof"
        )
    elif opportunity.limited_quantity:
        explanation["positives"].append(
            "Limited-quantity flag corroborated by other scarcity evidence"
        )

    if value == 0:
        explanation["notes"].append(
            "No scarcity evidence found"
        )

    return _clamp(value), explanation


# ---------------------------------------------------------------
# DEMAND SCORE
# ---------------------------------------------------------------

def score_demand(opportunity, context=None):
    explanation = _explanation()
    value = 0.0

    if opportunity.sold_listing_count is not None:
        value += _clamp(opportunity.sold_listing_count / 5, 0, 15)
        explanation["positives"].append(
            f"Observed sold listings: {opportunity.sold_listing_count}"
        )

    if opportunity.sales_velocity is not None:
        value += _clamp(opportunity.sales_velocity, 0, 15)
        explanation["positives"].append(
            f"Sales velocity: {opportunity.sales_velocity}"
        )

    if opportunity.sellout_speed:
        value += 15
        explanation["positives"].append(
            f"Rapid sellout ({opportunity.sellout_speed})"
        )

    if opportunity.demand_direction == "SURGING":
        value += 20
        explanation["positives"].append("Surging demand")
    elif opportunity.demand_direction == "RISING":
        value += 10
        explanation["positives"].append("Rising demand")
    elif opportunity.demand_direction == "FALLING":
        value -= 15
        explanation["negatives"].append("Falling demand")

    if len(opportunity.catalyst_signals) >= 3:
        value += 8
        explanation["positives"].append(
            "Multiple independent catalyst signals reported"
        )

    if value == 0:
        explanation["notes"].append("No demand evidence found")

    return _clamp(value), explanation


# ---------------------------------------------------------------
# HYPE SCORE
# ---------------------------------------------------------------

def score_hype(opportunity, context=None):
    explanation = _explanation()
    value = 0.0

    if opportunity.collaboration_partner:
        value += 15
        explanation["positives"].append("Collaboration announcement")

    signal_types = {
        item.get("signal_type")
        for item in (opportunity.evidence or [])
        if isinstance(item, dict)
    }

    if "COMMUNITY_HYPE" in signal_types:
        value += 15
        explanation["positives"].append("Community hype detected")

    if "RAPID_SELLOUT" in signal_types or opportunity.sellout_speed:
        value += 10
        explanation["positives"].append(
            "Rapid sellout suggests release-day attention"
        )

    if opportunity.demand_direction == "SURGING":
        value += 10
        explanation["positives"].append("Surging short-term demand")

    if opportunity.redeemable_reward or opportunity.event_exclusive:
        value += 5
        explanation["positives"].append(
            "Event/redemption structure typical of hyped drops"
        )

    if value == 0:
        explanation["notes"].append("No hype-specific evidence found")

    return _clamp(value), explanation


# ---------------------------------------------------------------
# ACQUISITION SCORE
# ---------------------------------------------------------------

def score_acquisition(opportunity, context=None, config=None):
    explanation = _explanation()
    value = 100.0

    high_spend = config.high_spend_threshold if config else 100.0
    very_high_spend = config.very_high_spend_threshold if config else 500.0

    if opportunity.membership_required or opportunity.membership_exclusive:
        value -= 15
        explanation["negatives"].append("Membership required")

    if opportunity.lottery_required:
        value -= 20
        explanation["negatives"].append("Lottery required")

    if opportunity.event_attendance_required:
        value -= 20
        explanation["negatives"].append("Event attendance required")

    if opportunity.bundle_required:
        value -= 10
        explanation["negatives"].append("Bundle purchase required")

    if opportunity.purchase_limit == 1:
        value -= 5
        explanation["negatives"].append(
            "Purchase limit of 1 restricts acquiring multiple units"
        )

    spend, spend_field = resolve_target_buy_price(opportunity)

    if spend is not None:
        if spend >= very_high_spend:
            value -= 20
            explanation["negatives"].append(
                f"High capital locked per unit (${spend:,.2f} via "
                f"{spend_field})"
            )
        elif spend >= high_spend:
            value -= 10
            explanation["negatives"].append(
                f"Meaningful capital locked per unit (${spend:,.2f} via "
                f"{spend_field})"
            )

    exclusivity_friction = [
        opportunity.retailer_exclusive,
        opportunity.region_exclusive,
        opportunity.convention_exclusive,
        opportunity.tournament_exclusive,
    ]

    friction_count = sum(1 for flag in exclusivity_friction if flag)

    if friction_count:
        penalty = min(friction_count * 10, 20)
        value -= penalty
        explanation["negatives"].append(
            "Restricted availability adds acquisition complexity"
        )

    if opportunity.online_available:
        value += 10
        explanation["positives"].append(
            "Available online - practical to acquire"
        )

    if value == 100.0:
        explanation["notes"].append(
            "No acquisition friction evidence found - treated as easy "
            "by default"
        )

    return _clamp(value), explanation


# ---------------------------------------------------------------
# RISK SCORE
# ---------------------------------------------------------------

def score_risk(
    opportunity,
    context=None,
    complete_set_mismatch=False,
    rumored=False,
):
    explanation = _explanation()
    value = 10.0  # every resale opportunity carries some baseline risk
    explanation["notes"].append("Baseline resale risk: 10")

    if rumored:
        value += 30
        explanation["negatives"].append("Rumored/unconfirmed release")

    if not _has_identity_beyond_brand(opportunity):
        value += 10
        explanation["negatives"].append(
            "Incomplete product identity beyond brand"
        )

    if complete_set_mismatch:
        value += 25
        explanation["negatives"].append(
            "Resale evidence describes a complete set applied to an "
            "individual item"
        )

    _, sell_kind = resolve_target_sell_price(opportunity)

    if sell_kind == "estimated":
        value += 10
        explanation["negatives"].append(
            "Resale price is an estimate, not an observed sale"
        )

    if opportunity.demand_direction == "FALLING":
        value += 15
        explanation["negatives"].append("Declining demand/prices")

    if opportunity.redeemable_reward:
        value += 8
        explanation["negatives"].append("Redemption uncertainty")

    extra_risks = max(0, len(opportunity.risks or []) - 2)

    if extra_risks:
        bonus = min(extra_risks * 4, 12)
        value += bonus
        explanation["negatives"].append(
            f"{len(opportunity.risks)} distinct risk factors reported"
        )

    return _clamp(value), explanation


# ---------------------------------------------------------------
# CONFIDENCE SCORE
# ---------------------------------------------------------------

SOURCE_TYPE_CONFIDENCE_POINTS = {
    "OFFICIAL": 25,
    "PRESS_RELEASE": 15,
    "RETAILER": 15,
    "NEWS": 8,
    "EVENT": 8,
    "COMMUNITY": 0,
    "MARKETPLACE": 0,
    "SOCIAL": -10,
    "OTHER": -10,
}


def score_confidence(
    opportunity,
    context=None,
    complete_set_mismatch=False,
    rumored=False,
):
    explanation = _explanation()
    value = 40.0
    explanation["notes"].append("Baseline confidence: 40")

    source_points = SOURCE_TYPE_CONFIDENCE_POINTS.get(
        opportunity.source_type, -10
    )
    value += source_points

    if opportunity.source_type:
        explanation["positives" if source_points > 0 else "negatives"].append(
            f"Source type: {opportunity.source_type}"
        )
    else:
        explanation["negatives"].append("No source type recorded")

    identity_fields = [
        opportunity.brand,
        opportunity.franchise,
        opportunity.product_name,
        opportunity.collaboration_partner,
    ]
    identity_count = sum(1 for field in identity_fields if field)

    if identity_count >= 4:
        value += 10
        explanation["positives"].append("Complete product identity")
    elif identity_count >= 2:
        value += 5
        explanation["positives"].append("Partial product identity")

    buy_price, _ = resolve_target_buy_price(opportunity)

    if buy_price is not None:
        value += 8
        explanation["positives"].append("Buy-side price known")

    _, sell_kind = resolve_target_sell_price(opportunity)

    if sell_kind == "observed":
        value += 12
        explanation["positives"].append("Observed (not estimated) resale price")
    elif sell_kind == "estimated":
        value += 4
        explanation["notes"].append("Resale price is only an estimate")

    evidence = opportunity.evidence or []

    if evidence:
        value += 8
        explanation["positives"].append(
            f"{len(evidence)} traceable signal detections as evidence"
        )

        confirmed_count = sum(
            1 for item in evidence
            if isinstance(item, dict) and item.get("confirmed")
        )
        estimated_count = sum(
            1 for item in evidence
            if isinstance(item, dict) and item.get("estimated")
        )
        rumored_count = sum(
            1 for item in evidence
            if isinstance(item, dict) and item.get("rumored")
        )

        if rumored_count:
            value -= 20
            explanation["negatives"].append(
                "Some evidence detections were flagged rumored"
            )
        elif confirmed_count >= estimated_count and confirmed_count > 0:
            value += 10
            explanation["positives"].append(
                "Majority of evidence is confirmed, not estimated"
            )

    if complete_set_mismatch:
        value -= 15
        explanation["negatives"].append(
            "Confidence reduced: resale evidence applies to a complete "
            "set, not this individual item"
        )

    if rumored:
        value -= 15
        explanation["negatives"].append(
            "Confidence reduced: opportunity is rumored/unconfirmed"
        )

    if not opportunity.release_date and not opportunity.status:
        value -= 8
        explanation["negatives"].append(
            "No release date or status known"
        )

    return _clamp(value), explanation
