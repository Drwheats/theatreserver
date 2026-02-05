import requests
from bs4 import BeautifulSoup
import json
import re
from urllib.parse import urljoin

# Config
OUTPUT_FILE = "all_movies.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def clean_time(time_str):
    """Converts '6:30 pm' or '18:30' into integer 630 or 1830."""
    try:
        # Remove anything that isn't a digit or 'am/pm'
        time_str = time_str.lower().strip()
        numbers = re.findall(r'\d+', time_str)
        if not numbers: return 0
        
        hour = int(numbers[0])
        minute = int(numbers[1]) if len(numbers) > 1 else 0
        
        # Convert to 24h format if 'pm' is present and it's not 12
        if 'pm' in time_str and hour < 12:
            hour += 12
        # Convert 12am to 0
        if 'am' in time_str and hour == 12:
            hour = 0
            
        return (hour * 100) + minute
    except:
        return 0

def scrape_paradise():
    url = "https://paradiseonbloor.com/coming-soon/"
    movies = []
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Paradise groups movies in .showtimes-description-inner
        for block in soup.select(".showtimes-description-inner"):
            # 1. Get Title
            title_tag = block.select_one("h2")
            title = title_tag.get_text(strip=True) if title_tag else "Unknown Title"
            
            # 2. Get Date (Avoiding the ARIA span)
            # We look for h3 (common for dates) or .show-date, specifically avoiding the aria-label
            date = "Unknown Date"
            date_tag = block.select_one("h3, .show-date")
            if date_tag:
                date_text = date_tag.get_text(strip=True)
                # If it's that annoying SEO string, we try to find a sibling or parent date
                if "Dates with showtimes for" in date_text:
                    # Logic fallback: Look for a span that DOESN'T have aria-label
                    alt_date = block.find("span", {"class": None}, string=re.compile(r'\d'))
                    date = alt_date.get_text(strip=True) if alt_date else date_text
                else:
                    date = date_text

            # 3. Get Link
            link_tag = block.find("a", href=True)
            link = urljoin(url, link_tag["href"]) if link_tag else None
            
            # 4. Get Showtimes
            # Paradise uses <li> tags for times
            showtimes = []
            for li in block.find_all("li"):
                time_text = li.get_text(strip=True)
                # Ensure it looks like a time (e.g., 7:00 pm)
                if re.search(r"\d{1,2}:\d{2}", time_text):
                    showtimes.append(time_text)

            movies.append({
                "source": "The Paradise",
                "title": title,
                "date": date, # You may need to format this to YYYY-MM-DD in main()
                "showtimes": showtimes,
                "link": link,
                "runtime": None, # Paradise runtime is often inconsistent in HTML
            })
    except Exception as e:
        print(f"❌ Error Paradise: {e}")
    return movies

def scrape_revue():
    url = "https://revuecinema.ca/calendar/"
    events = []

    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")

        script_text = None
        for script in soup.find_all("script"):
            if script.string and "new FullCalendar.Calendar" in script.string:
                script_text = script.string
                break

        if not script_text:
            print("⚠️ Revue Calendar script not found")
            return []

        # Extract events array
        match = re.search(r"events:\s*(\[[\s\S]*?\])\s*,\s*eventTimeFormat", script_text)
        if not match:
            print("⚠️ Revue Events JSON not found in script")
            return []

        raw_events = json.loads(match.group(1))

        for ev in raw_events:
            start = ev.get("start", "") # "YYYY-MM-DD HH:MM:SS"
            if " " in start:
                date, time = start.split(" ")
                showtime = time[:5]
            else:
                date = start
                showtime = "TBD"

            events.append({
                "source": "Revue Cinema",
                "title": ev.get("title"),
                "date": date,
                "showtimes": [showtime], # Put in list to match Paradise format
                "link": ev.get("url"),
                "runtime": None
            })
    except Exception as e:
        print(f"❌ Error scraping Revue: {e}")

    # CRITICAL: This return makes the function "iterable" for main()
    return events



def main():
    raw_data = []
    final_data = []

    scrapers = [scrape_paradise, 
                #scrape_revue
                ]

    for scraper in scrapers:
        print(f"📡 Running {scraper.__name__}...")
        raw_data.extend(scraper())

    # --- THE FLATTENING STEP ---
    for entry in raw_data:
        showtimes = entry.get("showtimes", [])
        
        if not showtimes:
            # If no times found, still keep the entry but set time to 0
            new_entry = entry.copy()
            new_entry.pop("showtimes", None)
            new_entry["showtime"] = 0
            final_data.append(new_entry)
            continue

        for t in showtimes:
            new_entry = entry.copy()
            # Remove the list version
            new_entry.pop("showtimes", None)
            # Add the flattened, integer version
            new_entry["showtime"] = clean_time(t)
            final_data.append(new_entry)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Done! Flattened into {len(final_data)} total showtime entries.")

if __name__ == "__main__":
    main()
