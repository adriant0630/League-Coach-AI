"""
Scraper for League of Legends Wiki Strategy pages.

Pulls raw wikitext from wiki.leagueoflegends.com for each champion's
/Strategy subpage, and saves it locally so we only need to hit the
wiki once per champion (cleaning/chunking happens in a later step,
on the saved files, not by re-scraping).

Usage:
    python scrape.py
"""

import requests
import time
import os
import json

# Champions to scrape for the initial test batch.
CHAMPIONS = [
    "Yasuo", "Zed", "Ahri", "Lux", "Jinx", "Lee Sin", "Darius",
    "Garen", "Thresh", "Vayne", "Kai'Sa", "Akali", "Katarina",
    "Malphite", "Leona", "Jhin", "Ezreal", "Riven", "Ashe", "Morgana",
]

BASE_URL = "https://wiki.leagueoflegends.com/en-us/{champion}/Strategy"

# Identify ourselves for each API request as per MediaWiki API etiquette
HEADERS = {
    "User-Agent": "LOL-Tool-Portfolio-Project/1.0 (educational/portfolio use; contact: powerpillow04@gmail.com)"
}

# delay so that we are not spamming their website
DELAY_SECONDS = 2

OUTPUT_DIR = "raw_pages"


def fetch_strategy_page(champion: str) -> str | None:
    """Fetch raw wikitext for a single champion's Strategy page.

    Returns the raw wikitext as a string, or None if the request failed
    (e.g. champion has no Strategy page, or a network error occurred).
    """
    # Champion names with spaces need them replaced for the URL,
    # e.g. "Lee Sin" -> "Lee_Sin"
    url_name = champion.replace(" ", "_")
    url = BASE_URL.format(champion=url_name) + "?action=raw"

    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
    except requests.RequestException as e:
        print(f"  [ERROR] Network error for {champion}: {e}")
        return None

    if response.status_code == 200:
        return response.text
    else:
        print(f"  [WARN] {champion} returned status {response.status_code}")
        return None


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    results = {}

    for i, champion in enumerate(CHAMPIONS, start=1):
        print(f"[{i}/{len(CHAMPIONS)}] Fetching {champion}...")
        wikitext = fetch_strategy_page(champion)

        if wikitext:
            # Save each champion's raw wikitext to its own file
            filename = champion.replace(" ", "_") + ".txt"
            filepath = os.path.join(OUTPUT_DIR, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(wikitext)
            results[champion] = "success"
            print(f"  Saved to {filepath} ({len(wikitext)} chars)")
        else:
            results[champion] = "failed"

        # Be polite to the wiki's servers between requests.
        # Skip the delay after the very last request.
        if i < len(CHAMPIONS):
            time.sleep(DELAY_SECONDS)

    # Writes a small summary so we can see what succeeded/failed at a glance
    summary_path = os.path.join(OUTPUT_DIR, "_scrape_summary.json")
    with open(summary_path, "w") as f:
        json.dump(results, f, indent=2)

    succeeded = sum(1 for v in results.values() if v == "success")
    print(f"\nDone. {succeeded}/{len(CHAMPIONS)} champions scraped successfully.")
    print(f"Summary saved to {summary_path}")


if __name__ == "__main__":
    main()