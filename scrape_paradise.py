import requests
from bs4 import BeautifulSoup
import html
import json
import re
from urllib.parse import urljoin, urlparse
from datetime import datetime, timedelta, date

# Config
OUTPUT_FILE = "all_movies.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
BLACKLIST_TITLES = {
    "film reference library public hours",
    "closed for private rental",
    "secret movie club",
    "international cinema cafe",
    "setting the scene exhibition",
    "closed for staff party",
}
FOX_BASE_URL = "https://www.foxtheatre.ca"
FOX_NOW_SHOWING_URL = f"{FOX_BASE_URL}/whats-on/now-showing/"
FOX_AJAX_URL = f"{FOX_BASE_URL}/wp-admin/admin-ajax.php"
FOX_DATES_PER_PAGE = 3
FOX_TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\s*(?:am|pm)\b", re.IGNORECASE)
FOX_RUNTIME_RE = re.compile(r"\b(\d{2,3}\s*mins?)\b", re.IGNORECASE)
FOX_ATTR_RE = re.compile(r'([a-zA-Z_:][\w:.-]*)="([^"]*)"')
FOX_HREF_RE = re.compile(r'href="([^"]+)"')
FOX_SHOWTIME_SPAN_RE = re.compile(
    r'<span[^>]*data-date="([^"]+)"[^>]*>(.*?)</span>', re.IGNORECASE | re.DOTALL
)

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
    """Fetches TIFF JSON feed and normalizes events to scraper output format."""
    url = "https://tiff.net/filmlisttemplatejson"
    standardized_movies = []
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        data = response.json()
            
        for item in data.get("items", []):
            title = item.get("title", "Unknown Title").strip()
            
            # 1. Filter out blacklisted titles
            if title.lower() in BLACKLIST_TITLES:
                continue
            
            # 2. Cut out ": 4K Restoration!" if it appears at the end
            # Using $ to ensure it only trims the suffix
            title = re.sub(r": 4K Restoration!$", "", title, flags=re.IGNORECASE).strip()
            
            link = f"https://tiff.net{item.get('url', '')}"
            
            for schedule in item.get("scheduleItems", []):
                raw_start = schedule.get("startTime", "")
                if not raw_start:
                    continue

                dt_obj = None
                for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
                    try:
                        dt_obj = datetime.strptime(raw_start, fmt)
                        break
                    except ValueError:
                        continue
                if not dt_obj:
                    continue
                
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

def is_on_or_after_yesterday(raw_date):
    """Returns True if date is yesterday or newer."""
    if not raw_date:
        return False
    try:
        date_part = str(raw_date).strip()[:10]
        entry_date = datetime.strptime(date_part, "%Y-%m-%d").date()
        yesterday = (datetime.now() - timedelta(days=1)).date()
        return entry_date >= yesterday
    except Exception:
        return False

def normalize_text(value):
    """Fixes common escaped-unicode artifacts like '\\u00c9' or 'u00c9'."""
    if value is None:
        return value
    text = str(value)
    # Decode standard unicode escape sequences.
    text = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), text)
    # Decode malformed tokens missing the backslash (e.g., MONTRu00c9AL).
    text = re.sub(r"u00([0-9a-fA-F]{2})", lambda m: chr(int(m.group(1), 16)), text)
    return text

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

def fox_parse_date(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None

def fox_clean_text(value):
    return re.sub(r"\s+", " ", value or "").strip()

def fox_strip_tags(value):
    return fox_clean_text(html.unescape(re.sub(r"<[^>]+>", " ", value)))

def fox_fetch_results(loaded_dates):
    payload = {
        "action": "now_showing_query",
        "paged": 1,
        "view_type": "date-view",
        "keyword": "",
        "dates": "",
        "genres": "",
        "series": "",
        "dates_per_page": FOX_DATES_PER_PAGE,
        "page_id": 2588,
    }
    if loaded_dates:
        payload["loaded_dates[]"] = loaded_dates
    else:
        payload["loaded_dates"] = ""

    headers = HEADERS.copy()
    headers["Referer"] = FOX_NOW_SHOWING_URL
    headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"

    response = requests.post(FOX_AJAX_URL, data=payload, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()

def fox_build_slug_title_map(response_data):
    mapping = {}
    posts = response_data.get("posts", [])
    if not isinstance(posts, list):
        return mapping

    for post in posts:
        link = post.get("guid")
        title = post.get("post_title")
        if not link or not title:
            continue
        path = urlparse(link).path.rstrip("/")
        if path:
            mapping[path] = title
    return mapping

def fox_parse_first_tag_attrs(item_html):
    tag_end = item_html.find(">")
    if tag_end == -1:
        return {}
    first_tag = item_html[:tag_end]
    return {k: html.unescape(v) for k, v in FOX_ATTR_RE.findall(first_tag)}

def fox_extract_item_blocks(posts_html):
    blocks = []
    cursor = 0
    marker = '<div class="item"'
    while True:
        start = posts_html.find(marker, cursor)
        if start == -1:
            break

        depth = 0
        i = start
        while i < len(posts_html):
            next_open = posts_html.find("<div", i)
            next_close = posts_html.find("</div>", i)

            if next_open == -1 and next_close == -1:
                break
            if next_close == -1 or (next_open != -1 and next_open < next_close):
                depth += 1
                i = next_open + 4
                continue

            depth -= 1
            i = next_close + 6
            if depth == 0:
                blocks.append(posts_html[start:i])
                cursor = i
                break
        else:
            break
    return blocks

def fox_extract_movie_link(item_html):
    for href in FOX_HREF_RE.findall(item_html):
        url = html.unescape(href)
        if "/movies/" not in url:
            continue
        if "#section-buy-tickets" in url:
            continue
        return urljoin(FOX_BASE_URL, url)
    return None

def fox_extract_showtimes(item_html, date_str):
    showtimes = []
    for span_date, span_body in FOX_SHOWTIME_SPAN_RE.findall(item_html):
        if fox_clean_text(html.unescape(span_date)) != date_str:
            continue
        text = fox_strip_tags(span_body)
        if FOX_TIME_RE.search(text):
            showtimes.append(text)

    if not showtimes:
        for match in FOX_TIME_RE.finditer(fox_strip_tags(item_html)):
            showtimes.append(fox_clean_text(match.group(0)))

    deduped = []
    seen = set()
    for showtime in showtimes:
        key = showtime.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(showtime)
    return deduped

def fox_extract_item(item_html, slug_title_map, cutoff_date):
    attrs = fox_parse_first_tag_attrs(item_html)
    date_str = fox_clean_text(attrs.get("data-date", ""))
    show_date = fox_parse_date(date_str)
    if not show_date or show_date > cutoff_date:
        return None

    movie_link = fox_extract_movie_link(item_html)
    if not movie_link:
        return None

    movie_path = urlparse(movie_link).path.rstrip("/")
    title = slug_title_map.get(movie_path)
    if not title:
        return None

    showtimes = fox_extract_showtimes(item_html, date_str)
    text = fox_strip_tags(item_html)
    runtime_match = FOX_RUNTIME_RE.search(text)
    runtime = fox_clean_text(runtime_match.group(1)) if runtime_match else None

    return {
        "source": "Fox Theatre",
        "date": date_str,
        "showtimes": showtimes if showtimes else None,
        "title": title,
        "link": movie_link,
        "runtime": runtime,
    }

def scrape_fox():
    cutoff_date = date.today() + timedelta(days=14)
    loaded_dates = []
    all_results = []
    seen = set()

    try:
        while True:
            payload = fox_fetch_results(loaded_dates)
            response_data = payload.get("data", {})
            posts_html = payload.get("posts", "")
            if not isinstance(response_data, dict):
                response_data = {}
            if not isinstance(posts_html, str):
                posts_html = ""

            slug_title_map = fox_build_slug_title_map(response_data)
            for block in fox_extract_item_blocks(posts_html):
                item = fox_extract_item(block, slug_title_map, cutoff_date)
                if not item:
                    continue
                key = (item["title"], item["date"], tuple(item["showtimes"] or []))
                if key in seen:
                    continue
                seen.add(key)
                all_results.append(item)

            new_loaded_dates = [
                d for d in payload.get("loaded_dates", []) if isinstance(d, str) and d.strip()
            ]
            parsed_loaded = [fox_parse_date(d) for d in new_loaded_dates]
            parsed_loaded = [d for d in parsed_loaded if d is not None]
            max_loaded = max(parsed_loaded) if parsed_loaded else None

            if not new_loaded_dates or new_loaded_dates == loaded_dates:
                break
            loaded_dates = new_loaded_dates

            if max_loaded and max_loaded >= cutoff_date:
                break
    except Exception as e:
        print(f"❌ Error Fox Theatre: {e}")
        return []

    all_results.sort(key=lambda x: (x["date"], (x["showtimes"] or [""])[0], x["title"]))
    return all_results

def main():
    raw_data = []
    final_data = []
    scraper_counts = {}

    scraper_jobs = [
        ("The Paradise", scrape_paradise),
        ("Revue Cinema", scrape_revue),
        ("TIFF Lightbox", scrape_tiff_local),
        ("Imagine Cinemas : Carlton", scrape_imagine_carlton),
        ("Innis College", scrape_innis),
        ("Fox Theatre", scrape_fox),
    ]

    for theatre_name, scraper in scraper_jobs:
        print(f"📡 Running {scraper.__name__}...")
        result = scraper() or []
        scraper_counts[theatre_name] = len(result)
        if result:
            raw_data.extend(result)

    filtered_raw_data = []
    for entry in raw_data:
        normalized_entry = entry.copy()
        normalized_entry["title"] = normalize_text(normalized_entry.get("title"))
        title = (normalized_entry.get("title") or "").strip().lower()
        if title in BLACKLIST_TITLES:
            continue
        if not is_on_or_after_yesterday(normalized_entry.get("date")):
            continue
        filtered_raw_data.append(normalized_entry)

    print("🔨 Flattening and formatting showtimes...")
    for entry in filtered_raw_data:
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

    print("📊 Scrape summary:")
    for theatre_name, _ in scraper_jobs:
        print(f"   Got {scraper_counts.get(theatre_name, 0)} entries for {theatre_name}")
    print(f"✅ Success! {len(final_data)} entries saved to {OUTPUT_FILE}.")

if __name__ == "__main__":
    main()
