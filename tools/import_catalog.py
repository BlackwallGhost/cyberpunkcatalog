#!/usr/bin/env python3
"""Refresh the bundled catalog from NetDeck's public Cyberpunk database.

The official Cyberpunk TCG site identifies NetDeck as its card-database provider.
Each printing is emitted separately so Beta, Retail, starter-deck, promo, and
alternate-art versions remain distinct collection entries.
"""
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse, unquote

import requests
from bs4 import BeautifulSoup

BASE = "https://netdeck.gg"
OUTPUT = Path("app/src/main/assets/catalog.json")
HEADERS = {"User-Agent": "CyberpunkCatalog/0.1 catalog importer"}

def normalized_text(soup):
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True))

def parse_printing(session, url, slug, number):
    response = session.get(url, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    body = normalized_text(soup)
    title = soup.title.get_text(" ", strip=True) if soup.title else slug
    title = title.split(" | ", 1)[0]
    if ":" in title:
        name, subtitle = [part.strip() for part in title.split(":", 1)]
    else:
        name, subtitle = title.strip(), ""

    set_match = re.search(r"Set:\s*(.*?)\s+\([^)]*\)\s+Rarity:\s*(.*?)\s+Illustrated by:", body, re.IGNORECASE)
    if not set_match:
        set_match = re.search(r"Set:\s*(.*?)\s+Rarity:\s*(.*?)\s+Illustrated by:", body, re.IGNORECASE)
    if not set_match:
        return None

    set_name, rarity = [part.strip() for part in set_match.groups()]
    type_match = re.search(r"\b(Legend|Unit|Program|Gear)\b", body)
    card_type = type_match.group(1) if type_match else ""
    stable_number = unquote(number)
    stable_id = slug + "-" + stable_number.lower().replace("β", "beta").replace(" ", "-")
    return {
        "id": stable_id,
        "name": name,
        "subtitle": subtitle,
        "setName": set_name,
        "collectorNumber": stable_number,
        "rarity": rarity,
        "type": card_type,
    }

def main():
    session = requests.Session()
    session.headers.update(HEADERS)
    card_urls = set()

    for page in (1, 2, 3):
        url = BASE + "/cards/cyberpunk" + ("" if page == 1 else "?page=" + str(page))
        response = session.get(url, timeout=30)
        if response.status_code != 200:
            continue
        soup = BeautifulSoup(response.text, "html.parser")
        for anchor in soup.select('a[href*="/cards/cyberpunk/"]'):
            href = anchor.get("href", "")
            parsed = urlparse(href)
            if parsed.path.count("/") == 3:
                card_urls.add(urljoin(BASE, parsed.path))

    records = []
    for card_url in sorted(card_urls):
        slug = card_url.rstrip("/").split("/")[-1]
        response = session.get(card_url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        printing_urls = set()
        for anchor in soup.select('a[href*="printing="]'):
            href = anchor.get("href")
            if href:
                printing_urls.add(urljoin(BASE, href))
        for printing_url in sorted(printing_urls):
            query = parse_qs(urlparse(printing_url).query)
            numbers = query.get("printing", [])
            if numbers:
                record = parse_printing(session, printing_url, slug, numbers[0])
                if record:
                    records.append(record)

    unique = {record["id"]: record for record in records}
    if not unique:
        print("Warning: no NetDeck records parsed; retaining bundled catalog.json")
        return
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(sorted(unique.values(), key=lambda x: x["id"]), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(unique)} public database printings to {OUTPUT}")

if __name__ == "__main__":
    main()
