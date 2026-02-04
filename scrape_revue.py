import requests
from bs4 import BeautifulSoup
import json
import re

URL = "https://revuecinema.ca/calendar/"
OUTPUT_FILE = "movies_revue.json"

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

def scrape_revue():
    res = requests.get(URL, headers=headers)
    res.raise_for_status()

    soup = BeautifulSoup(res.text, "html.parser")

    script_text = None
    for script in soup.find_all("script"):
        if script.string and "new FullCalendar.Calendar" in script.string:
            script_text = script.string
            break

    if not script_text:
        raise RuntimeError("Calendar script not found")

    # Extract events array
    match = re.search(r"events:\s*(\[[\s\S]*?\])\s*,\s*eventTimeFormat", script_text)
    if not match:
        raise RuntimeError("Events JSON not found")

    raw_events = json.loads(match.group(1))

    events = []
    for ev in raw_events:
        start = ev["start"]  # "YYYY-MM-DD HH:MM:SS"

        date, time = start.split(" ")

        events.append({
            "Location": "Revue Cinema",
            "title": ev["title"],
            "link": ev["url"],
            "date": date,
            "showtime": time[:5],  # HH:MM
            "runtime": None
        })

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(events, f, indent=2, ensure_ascii=False)

    print(f"✔ Extracted {len(events)} events → {OUTPUT_FILE}")

if __name__ == "__main__":
    scrape_revue()
