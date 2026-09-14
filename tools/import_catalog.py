#!/usr/bin/env python3
"""Build catalog.json from the official Cyberpunk TCG card database.

The official site is the source of truth. Each printing is emitted as its own
record so Beta, Retail, starter-deck, promo, and alternate-art versions remain
distinct collection entries.
"""
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

BASE = "https://cyberpunktcg.com"
OUTPUT = Path("app/src/main/assets/catalog.json")
HEADERS = {"User-Agent": "CyberpunkCatalog/0.1 catalog importer"}

def text_of(soup):
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True))

def parse_printing(url, fallback_slug):
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    body = text_of(soup)
    title = soup.title.get_text(" ", strip=True) if soup.title else fallback_slug
    title = title.split(" | ", 1)[0]
    if ":" in title:
        name, subtitle = [part.strip() for part in title.split(":", 1)]
    else:
        name, subtitle = title.strip(), ""

    match = re.search(
        r"SET:\s*(.*?)\s+RARITY:\s*(.*?)\s+NUMBER:\s*([^\s]+)",
        body,
        re.IGNORECASE,
    )
    if not match:
        return None
    set_name, rarity, number = [part.strip() for part in match.groups()]
    type_match = re.search(r"\b(LEGEND|UNIT|PROGRAM|GEAR)\b", body)
    card_type = type_match.group(1).title() if type_match else ""
    parsed = urlparse(url)
    query = parsed.query.replace("=", "-").replace("&", "-")
    stable_id = fallback_slug + ("-" + query if query else "-" + number.lower())
    return {
        "id": stable_id,
        "name": name,
        "subtitle": subtitle,
        "setName": set_name,
        "collectorNumber": number,
        "rarity": rarity,
        "type": card_type,
    }

def main():
    session = requests.Session()
    session.headers.update(HEADERS)
    card_urls = set()

    for page in (1, 2, 3):
        url = BASE + "/cards" + ("" if page == 1 else "?page=" + str(page))
        response = session.get(url, timeout=30)
        if response.status_code != 200:
            continue
        soup = BeautifulSoup(response.text, "html.parser")
        for anchor in soup.select('a[href^="/cards/"]'):
            href = anchor.get("href", "")
            if href.count("/") == 2 and "?" not in href:
                card_urls.add(urljoin(BASE, href))

    records = []
    for card_url in sorted(card_urls):
        slug = card_url.rstrip("/").split("/")[-1]
        response = session.get(card_url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        printing_urls = {
            urljoin(BASE, anchor.get("href"))
            for anchor in soup.select('a[href*="printing="]')
            if anchor.get("href")
        }
        if not printing_urls:
            printing_urls = {card_url}
        for printing_url in sorted(printing_urls):
            record = parse_printing(printing_url, slug)
            if record:
                records.append(record)

    unique = {record["id"]: record for record in records}
    if not unique:
        raise RuntimeError("No official card records were parsed; refusing to overwrite catalog.json")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(sorted(unique.values(), key=lambda x: x["id"]), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(unique)} official printings to {OUTPUT}")

if __name__ == "__main__":
    main()
