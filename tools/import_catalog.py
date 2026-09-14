#!/usr/bin/env python3
"""Refresh the bundled catalog from NetDeck's public Cyberpunk database.

The official Cyberpunk TCG site identifies NetDeck as its card-database provider.
Each printing is emitted separately so Beta, Retail, starter-deck, promo, and
alternate-art versions remain distinct collection entries.
"""
import json
import re
import sys
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
    response.encoding = "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")
    body = normalized_text(soup)
    title = soup.title.get_text(" ", strip=True) if soup.title else slug
    title = title.split(" | ", 1)[0]
    if ":" in title:
        name, subtitle = [part.strip() for part in title.split(":", 1)]
    else:
        name, subtitle = title.strip(), ""

    set_match = re.search(
        r"SET:\s*(.*?)\s+RARITY:\s*(.*?)\s+NUMBER:", body, re.IGNORECASE
    )
    if not set_match:
        return None

    set_name, rarity = [part.strip() for part in set_match.groups()]
    type_match = re.search(r"\b(Legend|Unit|Program|Gear)\b", body, re.IGNORECASE)
    card_type = type_match.group(1).title() if type_match else ""
    number_match = re.search(r"NUMBER:\s*([^\s]+)", body, re.IGNORECASE)
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
    for page in (0, 1, 2, 3):
        for parameter in ("page", "p", "pageIndex", "currentPage"):
            listing_urls.add(f"{BASE}/cards?{parameter}={page}")

    for offset in (60, 120):
        for parameter in ("offset", "skip", "start"):
            listing_urls.add(f"{BASE}/cards?{parameter}={offset}")
    for page in (2, 3):
        for parameter in ("pagination", "pageNumber"):
            listing_urls.add(f"{BASE}/cards?{parameter}={page}")
    for letter in "abcdefghijklmnopqrstuvwxyz":
        for parameter in ("search", "q"):
            listing_urls.add(f"{BASE}/cards?{parameter}={letter}")

    for url in sorted(listing_urls):
        response = session.get(url, timeout=30)
        if response.status_code != 200:
            continue
        response.encoding = "utf-8"
        if url == BASE + "/cards":
            clues = sorted(set(re.findall(r'.{0,100}(?:pagination|pageSize|totalPages|api/|/api|cursor|offset).{0,180}', response.text, re.IGNORECASE)))
            print("PAGING CLUES:", repr(clues[:30]), file=sys.stderr, flush=True)
            script_clues = []
            page_soup = BeautifulSoup(response.text, "html.parser")
            for script in page_soup.select("script[src]"):
                script_url = urljoin(BASE, script.get("src"))
                script_response = session.get(script_url, timeout=30)
                if script_response.status_code != 200:
                    continue
                for pattern in (
                    r"netdeck", r"/api/", r"cards.{0,80}(?:limit|offset)",
                    r"limit.{0,80}offset", r"offset.{0,80}limit",
                ):
                    for match in re.finditer(pattern, script_response.text, re.IGNORECASE):
                        script_clues.append(
                            script_url + " :: " +
                            script_response.text[max(0, match.start() - 300):match.start() + 800]
                        )
                        if len(script_clues) >= 40:
                            break
                    if len(script_clues) >= 40:
                        break
                if len(script_clues) >= 40:
                    break
            urls = sorted(set(re.findall(r'https?://[^"'\\s)]+', script_response.text)))
            routes = sorted(set(re.findall(r'["\'](/[^"\']*(?:api|cards)[^"\']*)["\']', script_response.text, re.IGNORECASE)))
            print("SCRIPT URLS:", repr([u for u in urls if "netdeck" in u or "cyberpunk" in u]), file=sys.stderr, flush=True)
            print("SCRIPT ROUTES:", repr(routes[:100]), file=sys.stderr, flush=True)
            print("SCRIPT CLUES:", repr(script_clues[-10:]), file=sys.stderr, flush=True)
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
        response.encoding = "utf-8"
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
            r"printing\\u003[dD]([0-9a-f-]{36})",
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
