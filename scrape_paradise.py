import requests
from bs4 import BeautifulSoup
import json
import re
from urllib.parse import urljoin

URL = "https://paradiseonbloor.com/coming-soon/"
OUTPUT_FILE = "movies_paradise.json"

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

def scrape_coming_soon():
    response = requests.get(URL, headers=headers)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    movies = []

    for block in soup.select(".showtimes-description-inner"):
        text = block.get_text(" ", strip=True)

        # --- Title ---
        title_tag = block.select_one("h2, .showtimes-title, .film-title")
        title = title_tag.get_text(strip=True) if title_tag else None

        # --- Link (usually "See full details") ---
        link = None
        for a in block.find_all("a", href=True):
            if "detail" in a.get_text(strip=True).lower():
                link = urljoin(URL, a["href"])
                break

        # --- Date ---
        date_tag = block.select_one(".selected-date, strong, p")
        date = date_tag.get_text(strip=True) if date_tag else None

        # --- Runtime ---
        runtime_match = re.search(
            r"Run\s*Time:\s*([\d]+(?:\s*min)?)",
            text,
            re.I
        )
        runtime = runtime_match.group(1) if runtime_match else None

        # --- Showtimes ---
        showtimes = []
        for elem in block.find_all("li"):
            t = elem.get_text(strip=True)
            if re.search(r"\b\d{1,2}:\d{2}\s*(am|pm)?\b", t, re.I):
                showtimes.append(t)

        movies.append({
            "Location": "The Paradise",
            "date": date,
            "showtimes": showtimes if showtimes else None,
            "title": title,
            "link": link,
            "runtime": runtime,
        })

    # Save JSON
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(movies, f, indent=2, ensure_ascii=False)

    print(f"✔ Extracted {len(movies)} entries → {OUTPUT_FILE}")

if __name__ == "__main__":
    scrape_coming_soon()
