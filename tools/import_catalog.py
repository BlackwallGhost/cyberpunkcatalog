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

BASE = "https://cyberpunktcg.com"
OUTPUT = Path("app/src/main/assets/catalog.json")
HEADERS = {"User-Agent": "CyberpunkCatalog/0.1 catalog importer"}

def normalized_text(soup):
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True))

def parse_printing(session, url, slug, printing_id):
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
    number_match = re.search(r"NUMBER:\\s*([^\\s]+)", body, re.IGNORECASE)
    if not number_match:
        return None
    stable_number = number_match.group(1).strip()
    stable_id = slug + "-" + unquote(printing_id).lower()
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

    listing_urls = {BASE + "/cards"}
    for page in (2, 3):
        for parameter in ("page", "p", "pageIndex"):
            listing_urls.add(f"{BASE}/cards?{parameter}={page}")

    for url in sorted(listing_urls):
        response = session.get(url, timeout=30)
        if response.status_code != 200:
            continue
        soup = BeautifulSoup(response.text, "html.parser")
        for anchor in soup.select('a[href^="/cards/"]'):
            href = anchor.get("href", "")
            parsed = urlparse(href)
            if parsed.path.count("/") == 2 and parsed.path.rstrip("/") != "/cards":
                card_urls.add(urljoin(BASE, parsed.path))

    records = []
    for card_url in sorted(card_urls):
        slug = card_url.rstrip("/").split("/")[-1]
        response = session.get(card_url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        printing_ids = set()
        for anchor in soup.select('a[href*="printing"]'):
            href = anchor.get("href", "")
            match = re.search(r"printing(?:=|%3D)([0-9a-f-]{36})", href, re.IGNORECASE)
            if match:
                printing_ids.add(match.group(1))
        for pattern in (
            r"printing=([0-9a-f-]{36})",
            r"printing%3D([0-9a-f-]{36})",
            r'"printing"\\s*:\\s*"([0-9a-f-]{36})"',
            r'"id"\\s*:\\s*"([0-9a-f-]{36})"',
        ):
            printing_ids.update(re.findall(pattern, response.text, re.IGNORECASE))

        for printing_id in sorted(printing_ids):
            printing_url = card_url + "?printing=" + printing_id
            record = parse_printing(session, printing_url, slug, printing_id)
            if record:
                records.append(record)

    unique = {record["id"]: record for record in records}
    if len(card_urls) < 100 or len(unique) < 100:
        raise RuntimeError(
            f"Catalog import incomplete: found {len(card_urls)} cards and {len(unique)} printings"
        )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(sorted(unique.values(), key=lambda x: x["id"]), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(unique)} public database printings to {OUTPUT}")

if __name__ == "__main__":
    main()
