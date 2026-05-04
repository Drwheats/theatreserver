import puppeteer from "puppeteer";

const TARGET_URL =
  "https://boxoffice.hotdocs.ca/websales/pages/list.aspx?cp242=KenticoInclude&epguid=a2104450-7e47-4369-a17d-c247570c3939&";

function parseRuntimeMinutes(text) {
  if (!text) return 0;
  const hourMatch = text.match(/\b(\d{1,2})\s*h(?:\s*(\d{1,2})\s*(?:min|m|minutes))?\b/i);
  if (hourMatch) {
    const h = Number(hourMatch[1] || 0);
    const m = Number(hourMatch[2] || 0);
    return h * 60 + m;
  }
  const minMatch = text.match(/\b(\d{2,3})\s*(?:min|m|minutes)\b/i);
  return minMatch ? Number(minMatch[1]) : 0;
}

async function scrape() {
  const browser = await puppeteer.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  });

  try {
    const page = await browser.newPage();
    await page.setUserAgent(
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    );
    await page.setViewport({ width: 1366, height: 900 });

    await page.goto(TARGET_URL, { waitUntil: "networkidle2", timeout: 90000 });
    await page.waitForSelector("body", { timeout: 15000 });
    await new Promise((resolve) => setTimeout(resolve, 3000));

    const rows = await page.evaluate(() => {
      const text = (el) => (el ? el.textContent.replace(/\s+/g, " ").trim() : "");
      const cleanTitle = (el) => {
        const clone = el.cloneNode(true);
        clone.querySelectorAll(".Descriptive").forEach((d) => d.remove());
        return text(clone);
      };

      const items = [];
      for (const card of document.querySelectorAll(".Item.ItemShow")) {
        const titleEl = card.querySelector(".Name");
        const title = titleEl ? cleanTitle(titleEl) : "";
        const detailsHref = card.querySelector(".ViewLink")?.href || "";
        const cardText = text(card);
        const showings = card.querySelectorAll(".Showing");
        for (const showing of showings) {
          const dateRaw = showing.getAttribute("data-agl_date") || "";
          const timeText = text(showing.querySelector("a")) || "";
          items.push({
            title,
            detailsHref,
            cardText,
            dateRaw,
            timeText,
          });
        }
      }
      return items;
    });

    const seen = new Set();
    const out = [];
    for (const row of rows) {
      const title = (row.title || "").trim();
      if (!title || !row.dateRaw || !row.timeText) continue;
      const dm = row.dateRaw.match(/(\d{1,2})\/(\d{1,2})\/(\d{2,4})/);
      if (!dm) continue;
      const month = Number(dm[1]);
      const day = Number(dm[2]);
      const year = Number(dm[3].length === 2 ? `20${dm[3]}` : dm[3]);
      const date = `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
      const runtime = parseRuntimeMinutes(row.cardText);
      const showtime = row.timeText.toUpperCase();
      const key = `${title}|${date}|${showtime}`;
      if (seen.has(key)) continue;
      seen.add(key);
      out.push({
        source: "Hot Docs",
        title,
        date,
        showtimes: [showtime],
        link: row.detailsHref || TARGET_URL,
        runtime,
      });
    }

    process.stdout.write(JSON.stringify(out));
  } finally {
    await browser.close();
  }
}

scrape().catch((err) => {
  process.stderr.write(String(err?.stack || err));
  process.exit(1);
});
