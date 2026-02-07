import requests
from bs4 import BeautifulSoup
import json
import re
import os
from urllib.parse import urljoin
from datetime import datetime, timedelta

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

def scrape_imagine_carlton():
    location = "Imagine Cinemas : Carlton"
    movies = []
    
    try:
        for i in range(10):
            date = datetime.now() + timedelta(days=i)
            date_str = date.strftime('%Y-%m-%d')
            
            url = f'https://imaginecinemas.com/cinema/carlton/?date={date_str}'
            response = requests.get(url, headers=HEADERS, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            elements = soup.select('.movie-showtime')
            
            
            for element in elements:
                title_elem = element.select_one('.movie-title')
                title = title_elem.get_text(strip=True) if title_elem else "Unknown Title"
                times = element.select('.times')
                
                for time in times:
                    perf_elem = time.select_one('.movie-performance')
                    if not perf_elem:
                        continue
                    
                    temp = perf_elem.get_text(strip=True)
                    temp_link = perf_elem.get('href')
                    
                    showtimes = temp.split("PM")
                    for showtime in showtimes:
                        if showtime.strip():
                            movies.append({
                                "source": location,
                                "title": title,
                                "date": date_str,
                                "showtimes": [showtime.strip() + "PM"],
                                "link": temp_link,
                                "runtime": None
                            })
    except Exception as e:
        print(f"❌ Error Imagine Carlton: {e}")
    
    return movies

def scrape_innis():
    url = "https://innis.utoronto.ca/happening-at-innis/"
    events = []
    prefix = "CINSSU presents: Free Friday Film"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")

        # scan section blocks that Elementor generates and look for the event anchor
        sections = soup.find_all('section', class_=lambda c: c and 'elementor-section' in c)
        seen = set()
        month_regex = r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|January|February|March|April|May|June|July|August|September|October|November|December)'

        for sec in sections:
            a = sec.find('a', string=re.compile(re.escape(prefix), re.I))
            if not a:
                # sometimes the anchor text is inside a child element
                a = sec.find('a')
                if not a or not re.search(re.escape(prefix), a.get_text(" ", strip=True), re.I):
                    continue

            full_text = a.get_text(" ", strip=True)
            # remove the prefix and any separators, then strip leading dashes/en-dashes
            title = re.sub(rf'^{re.escape(prefix)}\s*[:\-–—]?\s*', '', full_text, flags=re.I).strip()
            title = re.sub(r'^[\s\u2013\u2014\-–—]+', '', title).strip()
            if not title:
                continue
            if title in seen:
                continue
            seen.add(title)

            link = urljoin(url, a['href']) if a.has_attr('href') else None

            # try to parse month/day from nearby heading titles
            headings = [h.get_text(strip=True) for h in sec.select('.elementor-heading-title')]
            date_text = ''
            for i, txt in enumerate(headings):
                m_mon = re.search(month_regex, txt, re.I)
                if m_mon:
                    # look for day in same text or next
                    m_day = re.search(r'(\d{1,2})', txt)
                    if not m_day and i + 1 < len(headings):
                        m_day = re.search(r'(\d{1,2})', headings[i+1])
                        month_name = m_mon.group(0)
                    else:
                        month_name = m_mon.group(0)
                    if m_day:
                        day = m_day.group(1)
                        # try parsing with both abbreviated and full month
                        for fmt in ("%b %d %Y", "%B %d %Y"):
                            try:
                                dt = datetime.strptime(f"{month_name} {day} {datetime.now().year}", fmt)
                                date_text = dt.strftime("%Y-%m-%d")
                                break
                            except:
                                continue
                    if date_text:
                        break

            # fallback: look for ISO date or default to today
            if not date_text:
                bigtxt = sec.get_text(" ", strip=True)
                mdate = re.search(r'(\d{4}-\d{2}-\d{2})', bigtxt)
                if mdate:
                    date_text = mdate.group(1)
                else:
                    date_text = datetime.now().strftime("%Y-%m-%d")

            # find first time in the section
            bigtxt = sec.get_text(" ", strip=True)
            mtime = re.search(r'(\d{1,2}:\d{2}\s*(?:am|pm)?)', bigtxt, re.I)
            times = [mtime.group(1)] if mtime else []

            events.append({
                "source": "Innis College",
                "title": title,
                "date": date_text,
                "showtimes": times,
                "link": link,
                "runtime": None
            })
    except Exception as e:
        print(f"❌ Error Innis: {e}")
    return events

def main():
    raw_data = []
    final_data = []

    scrapers = [
        # scrape_paradise, 
        # scrape_revue,
        # scrape_tiff_local,
        # scrape_imagine_carlton,
        scrape_innis
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