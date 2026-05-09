#!/usr/bin/env python3
"""
Apple Refurb Mac mini watcher.

Scrapes Apple's refurbished Mac page and pings a Discord webhook
when a Mac mini is at or below PRICE_CAP. Tracks already-seen listings
in seen.json so you don't get spammed for the same item.
"""

import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

URL = "https://www.apple.com/shop/refurbished/mac/mac-mini"
PRICE_CAP = int(os.environ.get("PRICE_CAP", "800"))
WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL")
MODEL_FILTER = os.environ.get("MODEL_FILTER", "M4")  # set to "" to match any chip
PRODUCT_FILTER = os.environ.get("PRODUCT_FILTER", "Mac-mini")  # url-path token
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
    Find every refurb product link and extract its title from the URL slug.
    Then look ahead in the HTML for the first price that follows.
    Apple's product URLs encode the title, e.g.
        /shop/product/G1JX2LL/A/Refurbished-Mac-mini-Apple-M4-Chip-...
    """
    listings = []
    href_pat = re.compile(r'href="(/shop/product/[A-Za-z0-9]+/[Aa]/[^"#?]+)')
    price_pat = re.compile(r"\$([\d,]+)\.\d{2}")

    matches = list(href_pat.finditer(html))
    for m in matches:
        href = m.group(1)
        # Title slug is the last segment after /A/
        slug = href.rsplit("/", 1)[-1]
        # URL-decode (handles %E2%80%91 non-breaking hyphen, etc.)
        title = urllib.parse.unquote(slug).replace("-", " ").strip()

        # Find the first price within the next ~3000 chars
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
                "slug": slug.lower(),
            }
        )

    # Dedupe by url (keep first occurrence)
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
    items = list(seen)[-500:]  # cap so the file doesn't grow forever
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
    print(f"Checking {URL}")
    print(
        f"Filters: PRODUCT={PRODUCT_FILTER!r}, MODEL={MODEL_FILTER!r}, "
        f"CAP=${PRICE_CAP}"
    )
    html = fetch_page()
    all_listings = parse_listings(html)
    print(f"Found {len(all_listings)} total product listings")

    minis = [l for l in all_listings if PRODUCT_FILTER.lower() in l["slug"]]
    print(f"{len(minis)} match product filter {PRODUCT_FILTER!r}")

    if MODEL_FILTER:
        minis = [l for l in minis if MODEL_FILTER.lower() in l["title"].lower()]
        print(f"{len(minis)} also match chip filter {MODEL_FILTER!r}")

    cheap = [l for l in minis if l["price"] <= PRICE_CAP]
    print(f"{len(cheap)} at or below ${PRICE_CAP}")

    seen = load_seen()
    fresh = [l for l in cheap if l["url"] not in seen]
    print(f"{len(fresh)} are new since last run")

    if fresh:
        notify_discord(fresh)
        for l in fresh:
            seen.add(l["url"])
        save_seen(seen)

    if minis:
        print("\nAll Mac minis found on page:")
        for l in sorted(minis, key=lambda x: x["price"]):
            print(f"  ${l['price']} - {l['title']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
