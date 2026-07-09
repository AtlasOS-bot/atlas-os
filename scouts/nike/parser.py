def parse_nike_item(title, url, description=""):
    return {
        "brand": "Nike",
        "title": title,
        "description": description,
        "url": url,
        "category": "nike",
        "source": "nike",
    }