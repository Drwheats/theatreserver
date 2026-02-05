import requests
from bs4 import BeautifulSoup
import json
import re
import os
from urllib.parse import urljoin
from datetime import datetime

# Config
OUTPUT_FILE = "all_movies.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def format_date_to_iso(raw_date):
    """Converts 'Fri,  Feb 6' -> '2026-02-06'"""
    if not raw_date or "Unknown Date" in raw_date or "," not in raw_date:
        return datetime.now().strftime("%Y-%m-%d")
    try:
        parts = raw_date.split(',')
        clean_date = " ".join(parts[1].split()) 
        year = datetime.now().year
        dt = datetime.strptime(f"{clean_date} {year}", "%b %d %Y")
        return dt.strftime("%Y-%m-%d")
    except Exception as e:
        print(f"⚠️ Error formatting '{raw_date}': {e}")
        return datetime.now().strftime("%Y-%m-%d")

def clean_time(time_str):
    """Converts '6:30 pm' or '18:30' into integer 630 or 1830."""
    if isinstance(time_str, int): return time_str
    try:
        time_str = time_str.lower().strip()
        numbers = re.findall(r'\d+', time_str)
        if not numbers: return 0
        hour = int(numbers[0])
        minute = int(numbers[1]) if len(numbers) > 1 else 0
        if 'pm' in time_str and hour < 12: hour += 12
        if 'am' in time_str and hour == 12: hour = 0
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
        for block in soup.select(".showtimes-description-inner"):
            title_tag = block.select_one("h2")
            title = title_tag.get_text(strip=True) if title_tag else "Unknown Title"
            
            date = "Unknown Date"
            date_tag = block.select_one("h3, .show-date")
            if date_tag:
                date_text = date_tag.get_text(strip=True)
                if "Dates with showtimes for" in date_text:
                    alt_date = block.find("span", {"class": None}, string=re.compile(r'\d'))
                    date = alt_date.get_text(strip=True) if alt_date else date_text
                else:
                    date = date_text

            link_tag = block.find("a", href=True)
            link = urljoin(url, link_tag["href"]) if link_tag else None
            
            showtimes = [li.get_text(strip=True) for li in block.find_all("li") 
                         if re.search(r"\d{1,2}:\d{2}", li.get_text())]

            movies.append({
                "source": "The Paradise",
                "title": title,
                "date": format_date_to_iso(date), 
                "showtimes": showtimes,
                "link": link,
                "runtime": None,
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
        script_text = next((s.string for s in soup.find_all("script") if s.string and "new FullCalendar.Calendar" in s.string), None)
        if not script_text: return []

        match = re.search(r"events:\s*(\[[\s\S]*?\])\s*,\s*eventTimeFormat", script_text)
        if not match: return []

        raw_events = json.loads(match.group(1))
        for ev in raw_events:
            start = ev.get("start", "")
            date, showtime = start.split(" ") if " " in start else (start, "TBD")
            events.append({
                "source": "Revue Cinema",
                "title": ev.get("title"),
                "date": date,
                "showtimes": [showtime],
                "link": ev.get("url"),
                "runtime": None
            })
    except Exception as e:
        print(f"❌ Error Revue: {e}")
    return events

def scrape_tiff_local():
    """Processes TIFF JSON with specific title filters and 4K cleanup."""
    file_path = "tiffjson.json"
    standardized_movies = []
    
    # Titles to ignore completely
    blacklist = ["Film Reference Library Public Hours", "CLOSED FOR PRIVATE RENTAL"]
    
    if not os.path.exists(file_path):
        print(f"❌ TIFF file not found: {file_path}")
        return []

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            data = json.load(f, strict=False)
            
        for item in data.get("items", []):
            title = item.get("title", "Unknown Title").strip()
            
            # 1. Filter out blacklisted titles
            if title in blacklist:
                continue
            
            # 2. Cut out ": 4K Restoration!" if it appears at the end
            # Using $ to ensure it only trims the suffix
            title = re.sub(r": 4K Restoration!$", "", title, flags=re.IGNORECASE).strip()
            
            link = f"https://tiff.net{item.get('url', '')}"
            
            for schedule in item.get("scheduleItems", []):
                raw_start = schedule.get("startTime", "")
                if not raw_start: continue
                
                dt_obj = datetime.strptime(raw_start, "%Y-%m-%d %H:%M:%S")
                
                standardized_movies.append({
                    "source": "TIFF Lightbox",
                    "title": title,
                    "date": dt_obj.strftime("%Y-%m-%d"),
                    "showtimes": [dt_obj.strftime("%H:%M")], 
                    "link": link,
                    "runtime": None
                })
    except Exception as e:
        print(f"❌ Error TIFF: {e}")
    return standardized_movies

def main():
    raw_data = []
    final_data = []

    scrapers = [
        scrape_paradise, 
        scrape_revue,
        scrape_tiff_local
    ]

    for scraper in scrapers:
        print(f"📡 Running {scraper.__name__}...")
        result = scraper()
        if result:
            raw_data.extend(result)

    print("🔨 Flattening and formatting showtimes...")
    for entry in raw_data:
        showtimes = entry.get("showtimes", [])
        
        if not showtimes:
            new_entry = entry.copy()
            new_entry.pop("showtimes", None)
            new_entry["showtime"] = 0
            final_data.append(new_entry)
            continue

        for t in showtimes:
            new_entry = entry.copy()
            new_entry.pop("showtimes", None)
            new_entry["showtime"] = clean_time(t)
            final_data.append(new_entry)

    # Final sort by date and then time
    final_data.sort(key=lambda x: (x['date'], x['showtime']))

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final_data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Success! {len(final_data)} entries saved to {OUTPUT_FILE}.")

if __name__ == "__main__":
    main()