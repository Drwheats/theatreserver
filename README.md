# theatreserver
Express server for Local Theatre app calendar and blog content.

## Features
- Calendar JSON endpoint used by the frontend.
- File-backed blog CMS API (create, read, update, delete posts).
- Blog image upload support.
- SEO-friendly blog pages for crawler indexing.
- `sitemap.xml` and `robots.txt` generation.

## Tech Stack
- Node.js + Express (`type: module`)
- Multer for multipart image uploads
- JSON file persistence (`data/blog_posts.json`)

## Project Layout
- `server.js`: main Express app and all routes.
- `all_movies.json`: generated movie calendar payload.
- `data/blog_posts.json`: blog post storage (auto-created).
- `uploads/blog-images/`: uploaded image storage (auto-created).

## Setup
1. Install dependencies:
   - `npm install`
2. Configure blog auth token env var:
   - `export BLOG_ADMIN_TOKEN="Zx7ZUXjoM9gn7W7p8omm"`
3. Start the server:
   - `npm start`
3. Server listens on:
   - `http://0.0.0.0:3000`

## Existing Calendar API
- `GET /`
  - health/info payload.
- `GET /calendar`
  - returns parsed `all_movies.json`.

## Blog API
Base URL examples below assume local server: `http://localhost:3000`

### Data Model
Each post stores:
- `id`: unique id string
- `title`: post title
- `slug`: URL-safe unique slug
- `excerpt`: short summary
- `content`: full text content
- `seoTitle`: title used in metadata
- `seoDescription`: description used in metadata
- `imagePath`: server-relative image path (if uploaded)
- `publishedAt`: ISO timestamp
- `updatedAt`: ISO timestamp
- `imageUrl`: absolute URL added in API responses

### Endpoints
- `GET /api/blog/posts`
  - returns all posts, newest first.
- `GET /api/blog/posts/:slug`
  - returns one post by slug.
- `POST /api/blog/posts`
  - creates a post.
  - requires `Authorization: Bearer <BLOG_ADMIN_TOKEN>`
  - content type: `multipart/form-data`
  - required fields: `title`, `content`
  - optional fields: `excerpt`, `slug`, `seoTitle`, `seoDescription`, `image`
- `PUT /api/blog/posts/:id`
  - updates post by id.
  - requires `Authorization: Bearer <BLOG_ADMIN_TOKEN>`
  - content type: `multipart/form-data`
  - supports same fields as create.
- `DELETE /api/blog/posts/:id`
  - requires `Authorization: Bearer <BLOG_ADMIN_TOKEN>`
  - deletes a post and its image file (if present).

### Example: Create Post with Image
```bash
curl -X POST "http://localhost:3000/api/blog/posts" \
  -H "Authorization: Bearer Zx7ZUXjoM9gn7W7p8omm" \
  -F "title=TIFF Hidden Gems" \
  -F "content=Long-form content here..." \
  -F "excerpt=Quick summary for cards" \
  -F "seoTitle=TIFF Hidden Gems You Shouldn't Miss" \
  -F "seoDescription=A curated list of TIFF hidden gems." \
  -F "image=@/absolute/path/to/image.jpg"
```

### Example: Update Post
```bash
curl -X PUT "http://localhost:3000/api/blog/posts/<POST_ID>" \
  -H "Authorization: Bearer Zx7ZUXjoM9gn7W7p8omm" \
  -F "title=Updated title" \
  -F "content=Updated content"
```

### Example: Delete Post
```bash
curl -X DELETE "http://localhost:3000/api/blog/posts/<POST_ID>" \
  -H "Authorization: Bearer Zx7ZUXjoM9gn7W7p8omm"
```

## SEO / Indexing Routes
- `GET /blog`
  - HTML blog index page with links to each post.
- `GET /blog/:slug`
  - HTML detail page for one post.
  - includes canonical link and Open Graph metadata.
- `GET /sitemap.xml`
  - includes `/blog` and each `/blog/:slug` URL.
- `GET /robots.txt`
  - allows crawling and points crawlers to sitemap.

## Static Uploads
- Uploaded files are served from:
  - `GET /uploads/blog-images/<filename>`

## CORS
Whitelist currently includes:
- `https://calendar.ben.place`
- `http://localhost:3000`
- `http://localhost:5173`

If you deploy frontend/backend on different domains, add frontend origin to `whitelist` in `server.js`.

## Frontend Integration (localtheatreapp)
Frontend at `/home/ben/Programming/localtheatreapp` now uses this blog backend directly.

### Frontend changes made
- `src/Components/BlogView.tsx`
  - now calls `GET /api/blog/posts`
  - links posts by slug: `/blog/<slug>`
- `src/Components/BlogPage.tsx`
  - now calls `GET /api/blog/posts/:slug`
  - uses `useParams()` instead of URL splitting
- `src/main.tsx`
  - blog detail route changed to `/blog/:slug`

### API base URL used by frontend
- Uses `VITE_API_BASE` when provided.
- Falls back to `https://api.ben.place` if not set.

For local development, set this in `/home/ben/Programming/localtheatreapp/.env`:
```env
VITE_API_BASE=http://localhost:3000
```

Then run frontend normally.

## Scraper
Run:
- `python3 scrape_paradise.py`

It writes `all_movies.json` and prints a per-theatre entry count summary.
It also writes `all_music.json` for local music events.

Output entries include:
- `event_type: "cinema"` for movie/theatre sources
- `event_type: "music"` for `scrape_local_music` sources

### Adding New Scrapers
- Add your scraper function in `scrape_paradise.py`.
- Register it in one of:
  - `MOVIE_SCRAPER_SOURCES`
  - `MUSIC_SCRAPER_SOURCES`
- Format: `("Source Name", "scrape_function_name")`

### Hot Docs (Puppeteer) on Linux/ARM
- Hot Docs scraping uses Puppeteer against `boxoffice.hotdocs.ca`.
- On ARM servers, set a system Chrome/Chromium path:
  - `export PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium-browser`
  - or `export PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium`

## Operational Notes
- Blog persistence is filesystem-based, not database-backed.
- Back up `data/blog_posts.json` and `uploads/blog-images/`.
- On multi-instance deployments, move storage to shared object storage/database.
- Blog write endpoints require `BLOG_ADMIN_TOKEN`.

## Quick Smoke Checklist
1. `npm start` in this repo.
2. `GET /api/blog/posts` returns JSON array.
3. `POST /api/blog/posts` with image succeeds.
4. `GET /blog/<slug>` returns HTML with correct metadata.
5. Frontend `Blog` view loads posts from this backend.
