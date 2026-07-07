import json
import os
import re
from datetime import datetime, timezone, timedelta

import requests
from bs4 import BeautifulSoup

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
MAX_DAYS_OLD = 30


def supabase_headers():
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def clean_text(text):
    return " ".join(text.split()).strip()


def parse_date(text):
    text = clean_text(text)

    patterns = [
        (r"([A-Z][a-z]{2} \d{2}, \d{4}, \d{2}:\d{2} ET)", "%b %d, %Y, %H:%M ET"),
        (r"([A-Z][a-z]+ \d{1,2}, \d{4})", "%B %d, %Y"),
        (r"([A-Z]+ \d{1,2} \d{4})", "%B %d %Y"),
    ]

    for pattern, fmt in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                date_text = match.group(1).title()
                dt = datetime.strptime(date_text, fmt)
                return dt.replace(tzinfo=timezone.utc).isoformat()
            except Exception:
                pass

    return None


def remove_date_from_title(title):
    title = re.sub(r"^[A-Z][a-z]{2} \d{2}, \d{4}, \d{2}:\d{2} ET\s+", "", title)
    title = re.sub(r"^[A-Z]+ \d{1,2} \d{4}\s+", "", title)
    title = re.sub(r"^[A-Z][a-z]+ \d{1,2}, \d{4}\s+", "", title)
    return clean_text(title)


def is_recent(published_at):
    if not published_at:
        return False

    published = datetime.fromisoformat(published_at)
    now = datetime.now(timezone.utc)
    return published >= now - timedelta(days=MAX_DAYS_OLD)


def drop_already_exists(url):
    endpoint = f"{SUPABASE_URL}/rest/v1/raw_drops"
    r = requests.get(
        endpoint,
        headers=supabase_headers(),
        params={"url": f"eq.{url}", "select": "id", "limit": "1"},
    )
    r.raise_for_status()
    return len(r.json()) > 0


def save_to_supabase(brand, title, url, raw_text, published_at):
    if not is_recent(published_at):
        print(f"Old or undated skipped: {title} | {published_at}")
        return

    if drop_already_exists(url):
        print(f"Duplicate skipped: {title}")
        return

    endpoint = f"{SUPABASE_URL}/rest/v1/raw_drops"
    payload = {
        "brand": brand,
        "title": title,
        "url": url,
        "published_at": published_at,
        "raw_text": raw_text,
        "already_scored": False,
    }

    r = requests.post(endpoint, json=payload, headers=supabase_headers())
    print(f"{brand}: {r.status_code}")
    print(r.text)
    r.raise_for_status()


def find_latest_article(source_url, keyword):
    headers = {"User-Agent": "Mozilla/5.0 AtlasOS personal research scout"}
    response = requests.get(source_url, headers=headers, timeout=20)

    if response.status_code != 200:
        print(f"Source skipped: {source_url} returned {response.status_code}")
        return None, None, None

    soup = BeautifulSoup(response.text, "html.parser")
    candidates = []

    for a in soup.find_all("a", href=True):
        title = clean_text(a.get_text(" ", strip=True))
        href = a["href"]

        if len(title) < 20:
            continue

        if keyword.lower() not in title.lower():
            continue

        published_at = parse_date(title)
        clean_title = remove_date_from_title(title)

        if href.startswith("/"):
            if "prnewswire.com" in source_url:
                href = "https://www.prnewswire.com" + href
            elif "disneyparksblog.com" in source_url:
                href = "https://disneyparksblog.com" + href
            elif "lego.com" in source_url:
                href = "https://www.lego.com" + href

        candidates.append((clean_title, href, published_at))

    for title, href, published_at in candidates:
        if is_recent(published_at):
            return title, href, published_at

    if candidates:
        title, href, published_at = candidates[0]
        print(f"Found only old/undated article: {title} | {published_at}")
        return title, href, published_at

    print(f"No matching article found for keyword: {keyword}")
    return None, None, None


def main():
    with open("config/brands.json", "r") as f:
        brands = json.load(f)

    for item in brands:
        brand = item["brand"]
        print(f"Checking {brand}...")

        title, url, published_at = find_latest_article(
            item["source_url"],
            item["required_keyword"],
        )

        if not title or not url:
            print(f"{brand}: no save this run.")
            continue

        save_to_supabase(
            brand=brand,
            title=title,
            url=url,
            raw_text=f"Collected from {item['source_name']} by Atlas Universal Scout.",
            published_at=published_at,
        )


if __name__ == "__main__":
    main()
