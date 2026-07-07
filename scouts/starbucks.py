import os
import requests
from bs4 import BeautifulSoup

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

SOURCE_URL = "https://www.prnewswire.com/news/starbucks-coffee-company/"


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


def main():
    headers = {"User-Agent": "Mozilla/5.0 AtlasOS personal research scout"}

    response = requests.get(SOURCE_URL, headers=headers, timeout=20)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    title = None
    link = SOURCE_URL

    for a in soup.find_all("a", href=True):
        text = " ".join(a.get_text(" ", strip=True).split())
        href = a["href"]

        if len(text) > 25 and "Starbucks" in text:
            title = text
            if href.startswith("/"):
                link = "https://www.prnewswire.com" + href
            else:
                link = href
            break

    if not title:
        title = "Starbucks PR Newswire Scout Check"

    save_to_supabase(
        title=title,
        url=link,
        raw_text="Collected from PR Newswire Starbucks company page by Atlas Python Scout.",
    )


if __name__ == "__main__":
    main()
