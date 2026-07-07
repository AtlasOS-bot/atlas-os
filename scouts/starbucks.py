import os
import re
import requests
from bs4 import BeautifulSoup

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

STARBUCKS_URL = "https://about.starbucks.com/"


def save_to_supabase(title, url, raw_text):
    endpoint = f"{SUPABASE_URL}/rest/v1/raw_drops"

    payload = {
        "brand": "Starbucks",
        "title": title,
        "url": url,
        "raw_text": raw_text,
        "already_scored": False,
    }

    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

    r = requests.post(endpoint, json=payload, headers=headers)
    print(r.status_code)
    print(r.text)
    r.raise_for_status()


def clean_text(text):
    return re.sub(r"\s+", " ", text).strip()


def main():
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; AtlasOS/1.0; personal research)"
    }

    response = requests.get(STARBUCKS_URL, headers=headers, timeout=20)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    headlines = []
    for tag in soup.find_all(["h1", "h2", "h3"]):
        text = clean_text(tag.get_text(" ", strip=True))
        if len(text) > 20 and "Starbucks" in text:
            headlines.append(text)

    if headlines:
        title = headlines[0]
    else:
        title = "Starbucks Homepage Scout Check"

    save_to_supabase(
        title=title,
        url=STARBUCKS_URL,
        raw_text="Collected from official Starbucks homepage by Atlas Python Scout.",
    )


if __name__ == "__main__":
    main()
