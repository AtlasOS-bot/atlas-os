"""
Atlas v21 - Module 6 test fixtures. Deterministic canned content for
every connector type - no live network access anywhere in this file
or in anything that consumes it.
"""

ROUND1_OFFICIAL_ANNOUNCEMENT_HTML = """
<html><head><title>ONE PIECE x ROUND1 PROMOTIONAL PACK CAMPAIGN</title></head>
<body>
<h1>ONE PIECE x ROUND1 PROMOTIONAL PACK CAMPAIGN</h1>
<p>One Piece and Round1 launched a limited collaboration campaign.
Customers who spend $200 on eligible arcade play receive four
exclusive promotional card packs. The campaign runs at participating
Round1 locations for a limited time.</p>
</body></html>
"""

ROUND1_RETAILER_PAGE_HTML = """
<html><head><title>Round1 Store - One Piece Promo</title>
<script type="application/ld+json">
{"@type": "Product", "name": "ONE PIECE x ROUND1 Promotional Pack Campaign",
 "sku": "R1-OP-001",
 "offers": {"price": "200", "priceCurrency": "USD", "availability": "https://schema.org/InStock"}}
</script>
</head><body>
<h1>ONE PIECE x ROUND1 Promotional Pack Campaign</h1>
<p>One Piece x Round1 collaboration campaign is now live at
participating Round1 locations. Limit 1 per customer.</p>
</body></html>
"""

ROUND1_RSS_FEED_XML = """<?xml version="1.0"?>
<rss version="2.0"><channel>
<title>Collector News Feed</title>
<link>https://example.com</link>
<item>
<title>One Piece x Round1 Collaboration Announced</title>
<link>https://example.com/news/1</link>
<description>One Piece and Round1 launched a limited collaboration campaign.</description>
<pubDate>Mon, 20 Jul 2026 00:00:00 GMT</pubDate>
<guid>round1-guid-1</guid>
</item>
</channel></rss>
"""

ROUND1_MARKETPLACE_JSON = """
{"listings": [
  {"title": "One Piece x Round1 Complete Promo Set", "marketplace": "Resale Tracker",
   "price": 2200, "sold": true, "unit_scope": "complete_set"}
]}
"""

ROUND1_EVENT_PAGE_HTML = """
<html><head><title>Round1 Collector Meetup</title>
<script type="application/ld+json">
{"@type": "Event", "name": "Round1 Collector Meetup",
 "startDate": "2026-08-01", "endDate": "2026-08-01",
 "location": {"name": "Round1 Downtown"},
 "organizer": {"name": "Round1 Events"},
 "description": "Meet other One Piece x Round1 collectors."}
</script>
</head><body><h1>Round1 Collector Meetup</h1></body></html>
"""

GENERIC_ATOM_FEED_XML = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<title>Brand X Atom Feed</title>
<link href="https://example.com/atom" />
<entry>
<title>Brand X Announces Partner Co Collaboration</title>
<link href="https://example.com/atom/1" />
<summary>Brand X and Partner Co announced a collaboration.</summary>
<updated>2026-07-01T00:00:00Z</updated>
<id>atom-guid-1</id>
</entry>
</feed>
"""

GENERIC_JSON_FEED = """
{"articles": [
  {"title": "Brand X News", "body": "Brand X and Partner Co launched a collaboration.",
   "source_name": "Brand X Wire", "source_type": "NEWS"}
]}
"""

GENERIC_XML_FEED = """<?xml version="1.0"?>
<catalog>
<products>
<product>
<product_name>Brand X Item</product_name>
<retailer>Brand X Store</retailer>
<retail_price>60</retail_price>
</product>
</products>
</catalog>
"""

CHANGED_PAGE_V1 = "<html><head><title>Brand X Item</title></head><body><p>Brand X and Partner Co launched a collaboration. Retail price is $60.</p></body></html>"
CHANGED_PAGE_V2 = "<html><head><title>Brand X Item</title></head><body><p>Brand X and Partner Co launched a collaboration. Retail price is $50 (price drop).</p></body></html>"

UNCHANGED_PAGE = CHANGED_PAGE_V1

INVALID_RSS_XML = "<rss version=\"2.0\"><channel><title>Broken"
INVALID_JSON_TEXT = "{not valid json"
INVALID_XML_TEXT = "<unclosed><tag>"
