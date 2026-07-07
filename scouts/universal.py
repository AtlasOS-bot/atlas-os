import json
import os
import requests
from bs4 import BeautifulSoup

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]


def supabase_headers():
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def drop_already_exists(url):
    endpoint = f"{SUPABASE_URL}/rest/v1/raw_drops"
    params = {
        "url": f"eq.{url}",
        "select": "id",
        "limit": "1",
    }

    r = requests.get(endpoint, headers=supabase_headers(), params=params)
    r.raise_for_status()

    return len(r.json()) > 0


def save_to_supabase(brand, title, url, raw_text):
    if drop_already_exists(url):
        print(f"Duplicate skipped: {title}")
        return

    endpoint = f"{SUPABASE_URL}/rest/v1/raw_drops"

    payload = {
        "brand": brand,
        "title": title,
        "url": url,
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
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    for a in soup.find_all("a", href=True):
        title = " ".join(a.get_text(" ", strip=True).split())
        href = a["href"]

        if len(title) > 25 and keyword.lower() in title.lower():
            if href.startswith("/"):
                href = "https://www.prnewswire.com" + href
            return title, href

    return f"{keyword} Scout Check", source_url


def main():
    with open("config/brands.json", "r") as f:
        brands = json.load(f)

    for item in brands:
        brand = item["brand"]
        source_url = item["source_url"]
        keyword = item["required_keyword"]

        print(f"Checking {brand}...")

        title, url = find_latest_article(source_url, keyword)

        save_to_supabase(
            brand=brand,
            title=title,
            url=url,
            raw_text=f"Collected from {item['source_name']} by Atlas Universal Scout.",
        )


if __name__ == "__main__":
    main()
