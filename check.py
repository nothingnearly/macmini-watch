#!/usr/bin/env python3
"""
Apple Refurb Mac mini watcher.

Scrapes Apple's refurbished Mac mini page and pings a Discord webhook
when any listing is at or below PRICE_CAP. Tracks already-seen listings
in seen.json so you don't get spammed for the same item.
"""

import json
import os
import re
import sys
import urllib.request
from pathlib import Path

URL = "https://www.apple.com/shop/refurbished/mac/mac-mini"
PRICE_CAP = int(os.environ.get("PRICE_CAP", "800"))
WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL")
MODEL_FILTER = os.environ.get("MODEL_FILTER", "M4")  # set to "" to match all chips
SEEN_FILE = Path("seen.json")

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
)


def fetch_page() -> str:
    req = urllib.request.Request(URL, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def parse_listings(html: str) -> list[dict]:
    """
    Apple's refurb page renders each tile with a title link and a price.
    We pull (title, href, price) tuples with a tolerant regex pass.
    Format on Apple's page is roughly:
        <a ... href="/shop/product/XXXXXX/...">Refurbished Mac mini ...</a>
        ... <span class="price-info">$XXX.00</span>
    """
    listings = []

    # Anchors that point at refurb product pages
    anchor_pat = re.compile(
        r'<a[^>]+href="(/shop/product/[^"]+)"[^>]*>([^<]*Mac\s*mini[^<]*)</a>',
        re.IGNORECASE,
    )

    # Each tile is a <li class="rf-refurb-category-grid-no-results-item ..."> ... </li>
    # but structure shifts. Easier: split on product anchors and look ahead for a price.
    matches = list(anchor_pat.finditer(html))
    if not matches:
        return listings

    price_pat = re.compile(r"\$([\d,]+)\.\d{2}")

    for i, m in enumerate(matches):
        href, title = m.group(1), m.group(2).strip()
        # Search the next ~3000 chars after this anchor for the first price.
        window = html[m.end() : m.end() + 3000]
        pm = price_pat.search(window)
        if not pm:
            continue
        price = int(pm.group(1).replace(",", ""))
        listings.append(
            {
                "title": re.sub(r"\s+", " ", title),
                "url": "https://www.apple.com" + href.split("?")[0],
                "price": price,
            }
        )

    # Dedupe by url
    seen_urls = set()
    unique = []
    for item in listings:
        if item["url"] in seen_urls:
            continue
        seen_urls.add(item["url"])
        unique.append(item)
    return unique


def load_seen() -> set[str]:
    if not SEEN_FILE.exists():
        return set()
    try:
        return set(json.loads(SEEN_FILE.read_text()))
    except Exception:
        return set()


def save_seen(seen: set[str]) -> None:
    # Cap the file so it doesn't grow forever
    items = list(seen)[-500:]
    SEEN_FILE.write_text(json.dumps(items, indent=2))


def notify_discord(items: list[dict]) -> None:
    if not WEBHOOK:
        print("DISCORD_WEBHOOK_URL not set; would have notified about:")
        for it in items:
            print(f"  ${it['price']} - {it['title']} - {it['url']}")
        return

    lines = [f"🍎 **Refurb Mac mini alert** (cap ${PRICE_CAP})", ""]
    for it in items:
        lines.append(f"**${it['price']}** — [{it['title']}]({it['url']})")

    payload = json.dumps({"content": "\n".join(lines)}).encode("utf-8")
    req = urllib.request.Request(
        WEBHOOK,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        if resp.status >= 300:
            print(f"Discord webhook returned {resp.status}", file=sys.stderr)


def main() -> int:
    print(f"Checking {URL} (cap=${PRICE_CAP}, filter={MODEL_FILTER!r})")
    html = fetch_page()
    listings = parse_listings(html)
    print(f"Found {len(listings)} Mac mini listings")

    if MODEL_FILTER:
        listings = [
            l for l in listings if MODEL_FILTER.lower() in l["title"].lower()
        ]
        print(f"{len(listings)} match filter {MODEL_FILTER!r}")

    cheap = [l for l in listings if l["price"] <= PRICE_CAP]
    print(f"{len(cheap)} at or below ${PRICE_CAP}")

    seen = load_seen()
    fresh = [l for l in cheap if l["url"] not in seen]
    print(f"{len(fresh)} are new since last run")

    if fresh:
        notify_discord(fresh)
        for l in fresh:
            seen.add(l["url"])
        save_seen(seen)

    return 0


if __name__ == "__main__":
    sys.exit(main())
