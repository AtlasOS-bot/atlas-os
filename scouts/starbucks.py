import os
import requests
import xml.etree.ElementTree as ET

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

RSS_URL = "https://stories.starbucks.com/feed/"


def save_to_supabase(title, url):
    endpoint = f"{SUPABASE_URL}/rest/v1/raw_drops"

    payload = {
        "brand": "Starbucks",
        "title": title,
        "url": url,
        "raw_text": "Collected by Atlas Python Scout",
        "already_scored": False
    }

    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

    r = requests.post(endpoint, json=payload, headers=headers)

    print(r.status_code)
    print(r.text)

    r.raise_for_status()


def main():

    headers = {
        "User-Agent": "Mozilla/5.0 AtlasOS"
    }

    response = requests.get(RSS_URL, headers=headers, timeout=20)
    response.raise_for_status()

    root = ET.fromstring(response.content)

    item = root.find("./channel/item")

    if item is None:
        print("No stories found.")
        return

    title = item.findtext("title")
    link = item.findtext("link")

    print(title)
    print(link)

    save_to_supabase(title, link)


if __name__ == "__main__":
    main()
