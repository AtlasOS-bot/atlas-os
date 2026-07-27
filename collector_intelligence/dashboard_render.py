"""
Atlas v21 - Module 8: static HTML rendering.

Pure string-templating over the view models from dashboard_view.py -
no classification/formatting decisions are made here, only markup.
All user-originating text (notes, tags, product names sourced from
user overrides) is HTML-escaped; nothing here executes user content.

This module renders complete, static pages - the deployment model
stays "static file," matching the existing dashboard/index.html; only
the file-generation step moves from inline JS to tested Python. Live
interactivity (heart toggling, notes, overrides, manual items) is
handled by the thin dashboard/app.js layer these pages load.
"""

import json
from html import escape as _esc

from collector_intelligence.dashboard_models import VALID_LINK_TYPES


_STRENGTH_CLASS = {
    "STRONG": "strong", "MEDIUM": "medium", "WEAK": "weak", "UNKNOWN": "unknown",
}
_CONFIDENCE_CLASS = {"HIGH": "high", "MEDIUM": "medium", "LOW": "low"}
_TREND_SYMBOL = {"RISING": "↑", "STABLE": "→", "FALLING": "↓", "UNKNOWN": "?"}


def _badge(text, css_class, aria_label, data_role=None):
    role_attr = f'data-role="{_esc(data_role)}" ' if data_role else ""
    return (
        f'<span {role_attr}class="badge badge--{css_class}" role="status" '
        f'aria-label="{_esc(aria_label)}">{_esc(text)}</span>'
    )


def render_demand_tags(tags):
    if not tags:
        return ""
    items = "".join(f'<li class="tag">{_esc(tag)}</li>' for tag in tags)
    return f'<ul class="demand-tags" aria-label="Demand tags">{items}</ul>'


def render_heart_button(opportunity_id, hearted):
    pressed = "true" if hearted else "false"
    glyph = "♥" if hearted else "♡"  # filled / empty heart
    label = "Remove from Hearted Items" if hearted else "Save to Hearted Items"
    state_class = "hearted" if hearted else "not-hearted"

    return (
        f'<button type="button" class="heart-btn heart-btn--{state_class}" '
        f'data-action="toggle-heart" data-opportunity-id="{_esc(opportunity_id)}" '
        f'aria-pressed="{pressed}" aria-label="{_esc(label)}">'
        f'<span aria-hidden="true">{glyph}</span></button>'
    )


def render_links(links):
    parts = []
    for link_type in VALID_LINK_TYPES:
        link = links.get(link_type)
        if not link or not link.available:
            continue
        parts.append(
            f'<a class="action-link" href="{_esc(link.url)}" target="_blank" '
            f'rel="noopener noreferrer">{_esc(link.label)}</a>'
        )
    return "".join(parts)


def render_opportunity_card(card, details=None):
    """`card` is a ProductCardViewModel; `details` an optional
    CardDetailsViewModel rendered inside a collapsed <details> panel."""
    strength_class = _STRENGTH_CLASS.get(card.market_strength, "unknown")
    confidence_class = _CONFIDENCE_CLASS.get(card.confidence, "low")

    strength_badge = _badge(
        card.market_strength, strength_class, f"Market strength: {card.market_strength.title()}",
        data_role="strength-badge",
    )
    override_badge = (
        '<span class="badge badge--override" role="status">Manual override</span>'
        if card.market_strength_is_override else ""
    )
    confidence_badge = _badge(card.confidence, confidence_class, f"Confidence: {card.confidence.title()}")

    caution_badge = (
        '<span class="badge badge--caution" role="status">Complete-set pricing</span>'
        if card.unit_scope_is_caution else ""
    )

    trend_symbol = _TREND_SYMBOL.get(card.market_trend, "?")

    demand_tags_html = render_demand_tags(card.demand_tags)
    links_html = render_links(card.links)
    heart_html = render_heart_button(card.opportunity_id, card.hearted)

    notes_indicator = (
        '<span class="notes-indicator" aria-hidden="true">&#9998;</span>' if card.has_notes else ""
    )

    details_html = ""
    if details and (details.why_bullets or details.risks):
        why_items = "".join(f"<li>{_esc(bullet)}</li>" for bullet in details.why_bullets)
        risk_items = "".join(f"<li>{_esc(risk)}</li>" for risk in details.risks)
        details_html = f"""
      <details class="card-details">
        <summary>Why Atlas rated this market this way</summary>
        <div class="details-body">
          {f'<ul class="why-bullets">{why_items}</ul>' if why_items else ""}
          {f'<h4>Risks</h4><ul class="risk-bullets">{risk_items}</ul>' if risk_items else ""}
        </div>
      </details>"""

    # Atlas's own computed values, embedded so app.js NEVER re-derives
    # classification client-side - it only reads what Python already
    # decided, e.g. to pre-fill "Atlas says WEAK" in the override form.
    atlas_values = _esc(json.dumps({
        "market_strength": card.atlas_market_strength,
        "market_trend": card.atlas_market_trend,
        "demand_tags": card.demand_tags,
    }))

    return f"""
    <article class="card" data-opportunity-id="{_esc(card.opportunity_id)}"
              data-atlas-values="{atlas_values}" data-hearted="{'true' if card.hearted else 'false'}">
      <div class="card-image">
        <img src="{_esc(card.image.url)}" alt="{_esc(card.image.alt_text)}" loading="lazy"
             class="{'placeholder' if card.image.is_placeholder else ''}">
      </div>
      <div class="card-body">
        <div class="card-header">
          <h3 class="card-title">{_esc(card.product_name)}{notes_indicator}</h3>
          <div class="card-badges" data-role="strength-badges">{strength_badge}{override_badge}</div>
        </div>
        <div class="card-meta">
          <span class="updated-time">{_esc(card.updated_relative)}</span>
          <div class="card-badges">{confidence_badge}</div>
        </div>
        <div class="card-stats">
          <div class="stat"><span class="stat-label">MSRP</span><span class="stat-value">{_esc(card.msrp_display)}</span></div>
          <div class="stat"><span class="stat-label">Last sold</span><span class="stat-value">{_esc(card.last_sold_display)}</span></div>
          <div class="stat"><span class="stat-label">Trend</span><span class="stat-value" data-role="trend-value">{_esc(card.market_trend)} <span aria-hidden="true" data-role="trend-symbol">{trend_symbol}</span></span></div>
          <div class="stat"><span class="stat-label">Unit</span><span class="stat-value">{_esc(card.unit_scope)}{(" " + caution_badge) if caution_badge else ""}</span></div>
        </div>
        {demand_tags_html}
        <div class="card-actions">
          {links_html}
          <button type="button" class="action-btn" data-action="notes" data-opportunity-id="{_esc(card.opportunity_id)}">Notes</button>
          <button type="button" class="action-btn" data-action="edit" data-opportunity-id="{_esc(card.opportunity_id)}">Edit</button>
          {heart_html}
        </div>
      </div>{details_html}
    </article>"""


_PAGE_SHELL = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  {demo_banner}
  <div class="shell">
    <header class="page-header">
      <h1>ATLAS</h1>
      <nav aria-label="Primary">
        <a href="{index_href}">All Drops</a>
        <a href="{hearted_href}">Hearted Items</a>
        <button type="button" id="nav-add-item" data-action="add-item">+ Add Item</button>
      </nav>
    </header>
    {body}
  </div>
  <div id="drawer" class="drawer" hidden aria-hidden="true">
    <div class="drawer-content" role="dialog" aria-modal="true">
      <button type="button" class="drawer-close" data-action="cancel-drawer" aria-label="Close">&times;</button>
      <div id="drawer-body"></div>
    </div>
  </div>
  <template id="manual-item-form-template">{manual_item_form}</template>
  <script src="app.js"></script>
</body>
</html>
"""

_DEMO_BANNER = (
    '<div class="demo-banner" role="status">'
    "DEMO DATA — sample data for local preview only. Not connected to Supabase."
    "</div>"
)


def _page_shell(title, body, demo):
    return _PAGE_SHELL.format(
        title=_esc(f"{title} (Demo)" if demo else title),
        body=body,
        manual_item_form=_MANUAL_ITEM_FORM,
        demo_banner=_DEMO_BANNER if demo else "",
        index_href="demo-index.html" if demo else "index.html",
        hearted_href="demo-hearted.html" if demo else "hearted.html",
    )


def render_dashboard_page(cards, details_by_id=None, title="Atlas Collector Dashboard", demo=False):
    details_by_id = details_by_id or {}

    if not cards:
        body = '<p class="empty-state">No opportunities to show yet.</p>'
    else:
        card_html = "".join(
            render_opportunity_card(card, details_by_id.get(card.opportunity_id))
            for card in cards
        )
        body = f'<section class="cards-grid" aria-label="Opportunities">{card_html}</section>'

    return _page_shell(title, body, demo)


# ---------------------------------------------------------------
# Hearted Items page
# ---------------------------------------------------------------

_STATUS_LABELS = {
    "SAVED": "Saved", "APPROVED": "Approved", "DENIED": "Denied",
    "PURCHASED": "Purchased", "SOLD": "Sold", "ARCHIVED": "Archived",
}


def render_hearted_item_row(row):
    strength_class = _STRENGTH_CLASS.get(row.market_strength, "unknown")
    strength_badge = _badge(row.market_strength, strength_class, f"Market strength: {row.market_strength.title()}")
    status_label = _STATUS_LABELS.get(row.status, row.status)
    manual_badge = '<span class="badge badge--manual" role="status">Manual</span>' if row.is_manual else ""
    tags_html = "".join(f'<li class="tag">{_esc(tag)}</li>' for tag in row.tags)

    links = []
    if row.product_link:
        links.append(f'<a class="action-link" href="{_esc(row.product_link)}" target="_blank" rel="noopener noreferrer">View Product</a>')
    if row.ebay_sold_link:
        links.append(f'<a class="action-link" href="{_esc(row.ebay_sold_link)}" target="_blank" rel="noopener noreferrer">eBay Sold</a>')

    notes_indicator = '<span class="notes-indicator" aria-hidden="true">&#9998;</span>' if row.has_notes else ""

    return f"""
    <article class="hearted-row" data-hearted-item-id="{_esc(row.hearted_item_id)}"
              data-status="{_esc(row.status)}" data-priority="{_esc(row.priority or '')}"
              data-category="{_esc(row.category or '')}" data-archived="{'true' if row.archived else 'false'}"
              data-is-manual="{'true' if row.is_manual else 'false'}"
              data-product-name="{_esc(row.product_name.lower())}" data-hearted-at="{_esc(row.hearted_at)}">
      <div class="hearted-row-image">
        <img src="{_esc(row.image.url)}" alt="{_esc(row.image.alt_text)}" loading="lazy"
             class="{'placeholder' if row.image.is_placeholder else ''}">
      </div>
      <div class="hearted-row-body">
        <div class="hearted-row-header">
          <h3>{_esc(row.product_name)}{notes_indicator}</h3>
          <div class="card-badges">{strength_badge}{manual_badge}</div>
        </div>
        <div class="hearted-row-stats">
          <span class="stat"><span class="stat-label">Status</span><span class="stat-value">{_esc(status_label)}</span></span>
          <span class="stat"><span class="stat-label">Target</span><span class="stat-value">{_esc(row.target_price_display)}</span></span>
          <span class="stat"><span class="stat-label">Qty</span><span class="stat-value">{_esc(str(row.quantity) if row.quantity is not None else "—")}</span></span>
          <span class="stat"><span class="stat-label">Priority</span><span class="stat-value">{_esc(row.priority or "—")}</span></span>
        </div>
        {f'<ul class="demand-tags" aria-label="Tags">{tags_html}</ul>' if tags_html else ""}
        <div class="card-actions">
          {"".join(links)}
          <button type="button" class="action-btn" data-action="notes" data-hearted-item-id="{_esc(row.hearted_item_id)}">Notes</button>
          <button type="button" class="action-btn" data-action="edit-hearted" data-hearted-item-id="{_esc(row.hearted_item_id)}">Edit</button>
          <button type="button" class="action-btn" data-action="archive-hearted" data-hearted-item-id="{_esc(row.hearted_item_id)}">
            {"Unarchive" if row.archived else "Archive"}
          </button>
          <button type="button" class="heart-btn heart-btn--hearted" data-action="unheart"
                  data-hearted-item-id="{_esc(row.hearted_item_id)}" aria-pressed="true"
                  aria-label="Remove from Hearted Items"><span aria-hidden="true">&#9829;</span></button>
        </div>
      </div>
    </article>"""


_MANUAL_ITEM_FORM = """
    <form id="manual-item-form" class="drawer-form" aria-label="Add manual item">
      <h2>Add manual item</h2>
      <label for="mi-product-name">Product name</label>
      <input id="mi-product-name" name="product_name" type="text" required>

      <label for="mi-image-url">Product image URL</label>
      <input id="mi-image-url" name="image_url" type="url" placeholder="https://...">

      <label for="mi-product-link">Product link</label>
      <input id="mi-product-link" name="product_link" type="url" placeholder="https://...">

      <label for="mi-ebay-link">eBay sold link</label>
      <input id="mi-ebay-link" name="ebay_sold_link" type="url" placeholder="https://...">

      <label for="mi-msrp">MSRP</label>
      <input id="mi-msrp" name="msrp" type="number" step="0.01" min="0">

      <label for="mi-last-sold">Last sold price</label>
      <input id="mi-last-sold" name="last_sold_price" type="number" step="0.01" min="0">

      <label for="mi-market-strength">Market strength</label>
      <select id="mi-market-strength" name="market_strength">
        <option value="UNKNOWN">Unknown</option>
        <option value="STRONG">Strong</option>
        <option value="MEDIUM">Medium</option>
        <option value="WEAK">Weak</option>
      </select>

      <label for="mi-category">Category</label>
      <input id="mi-category" name="category" type="text">

      <label for="mi-priority">Priority</label>
      <select id="mi-priority" name="priority">
        <option value="">None</option>
        <option value="high">High</option>
        <option value="medium">Medium</option>
        <option value="low">Low</option>
      </select>

      <label for="mi-target-price">Target price</label>
      <input id="mi-target-price" name="target_price" type="number" step="0.01" min="0">

      <label for="mi-quantity">Quantity</label>
      <input id="mi-quantity" name="quantity" type="number" step="1" min="0">

      <label for="mi-tags">Tags (comma separated)</label>
      <input id="mi-tags" name="tags" type="text">

      <label for="mi-notes">My Notes</label>
      <textarea id="mi-notes" name="notes" rows="3"></textarea>

      <div class="form-actions">
        <button type="submit">Save item</button>
        <button type="button" data-action="cancel-drawer">Cancel</button>
      </div>
    </form>"""


# Note: the override form and notes panel are built dynamically by
# app.js (they need live data - the current override values, the
# notes list - that only exist client-side), unlike the manual-item
# form above which has no live data dependency and so is safely
# embeddable as a static <template>.


def render_hearted_items_page(rows, title="Hearted Items", demo=False):
    if not rows:
        body = '<p class="empty-state">No hearted items yet. Heart a product or add one manually.</p>'
    else:
        row_html = "".join(render_hearted_item_row(row) for row in rows)
        body = f'<section class="hearted-list" aria-label="Hearted items">{row_html}</section>'

    controls = """
    <div class="hearted-controls">
      <label for="hi-search" class="sr-only">Search hearted items</label>
      <input id="hi-search" type="search" placeholder="Search...">

      <label for="hi-filter-status" class="sr-only">Filter by status</label>
      <select id="hi-filter-status">
        <option value="">All statuses</option>
        <option value="SAVED">Saved</option>
        <option value="APPROVED">Approved</option>
        <option value="DENIED">Denied</option>
        <option value="PURCHASED">Purchased</option>
        <option value="SOLD">Sold</option>
        <option value="ARCHIVED">Archived</option>
      </select>

      <label for="hi-sort" class="sr-only">Sort</label>
      <select id="hi-sort">
        <option value="hearted_at_desc">Newest first</option>
        <option value="hearted_at_asc">Oldest first</option>
        <option value="priority">Priority</option>
        <option value="name">Name</option>
      </select>

      <button type="button" id="hi-add-manual">+ Add manual item</button>
    </div>"""

    full_body = controls + body
    return _page_shell(title, full_body, demo)
