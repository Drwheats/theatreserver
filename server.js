import express from 'express';
import path from 'path';
import fs from 'fs';
import cors from 'cors';
import multer from 'multer';
import { fileURLToPath } from 'url'; // Required for __dirname fix

const app = express();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Allow multiple trusted origins via a whitelist
const whitelist = [
  'https://calendar.ben.place',
  // add other origins you trust, for example during development:
  'http://localhost:3000',
  'http://localhost:5173',
];

const corsOptions = {
  origin: (origin, callback) => {
    // If no origin (e.g. server-to-server or curl), allow it
    if (!origin) return callback(null, true);
    if (whitelist.indexOf(origin) !== -1) {
      callback(null, true);
    } else {
      callback(new Error('Not allowed by CORS'));
    }
  },
  methods: ['GET', 'POST', 'PUT', 'DELETE'],
};

app.use(cors(corsOptions));
app.use(express.json({ limit: '2mb' }));

const DATA_DIR = path.join(__dirname, 'data');
const BLOG_DATA_FILE = path.join(DATA_DIR, 'blog_posts.json');
const UPLOADS_DIR = path.join(__dirname, 'uploads');
const BLOG_IMAGE_DIR = path.join(UPLOADS_DIR, 'blog-images');

for (const dir of [DATA_DIR, UPLOADS_DIR, BLOG_IMAGE_DIR]) {
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
}

if (!fs.existsSync(BLOG_DATA_FILE)) {
  fs.writeFileSync(BLOG_DATA_FILE, '[]', 'utf8');
}

app.use('/uploads', express.static(UPLOADS_DIR));

const storage = multer.diskStorage({
  destination: (_req, _file, cb) => cb(null, BLOG_IMAGE_DIR),
  filename: (_req, file, cb) => {
    const ext = path.extname(file.originalname).toLowerCase();
    const safeExt = ['.jpg', '.jpeg', '.png', '.webp', '.gif'].includes(ext) ? ext : '.jpg';
    cb(null, `${Date.now()}-${Math.round(Math.random() * 1e9)}${safeExt}`);
  },
});

const upload = multer({
  storage,
  limits: { fileSize: 8 * 1024 * 1024 },
  fileFilter: (_req, file, cb) => {
    if (file.mimetype.startsWith('image/')) cb(null, true);
    else cb(new Error('Only image uploads are allowed'));
  },
});

function readBlogPosts() {
  try {
    const raw = fs.readFileSync(BLOG_DATA_FILE, 'utf8');
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch (_err) {
    return [];
  }
}

function writeBlogPosts(posts) {
  fs.writeFileSync(BLOG_DATA_FILE, JSON.stringify(posts, null, 2), 'utf8');
}

function slugify(input) {
  return String(input || '')
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\s-]/g, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '');
}

function ensureUniqueSlug(posts, desired, currentId = null) {
  const base = slugify(desired) || `post-${Date.now()}`;
  let candidate = base;
  let counter = 2;
  while (posts.some((p) => p.slug === candidate && p.id !== currentId)) {
    candidate = `${base}-${counter++}`;
  }
  return candidate;
}

function escapeHtml(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function normalizePostForApi(post, req) {
  const host = `${req.protocol}://${req.get('host')}`;
  const imageUrl = post.imagePath ? `${host}${post.imagePath}` : null;
  return { ...post, imageUrl };
}

function resolvePublicPathToDisk(publicPath) {
  // Stored paths are public URLs like "/uploads/blog-images/file.jpg".
  // Strip leading slash so path.join stays inside this project directory.
  return path.join(__dirname, String(publicPath || '').replace(/^\/+/, ''));
}

app.get("/", (req, res) => {
  res.json({
    status: "ok",
    message: "Hello from Oracle Cloud",
    time: new Date().toISOString()
  });
});

app.get("/calendar", (req, res) => {
  const filePath = path.join(__dirname, "all_movies.json");

  fs.readFile(filePath, "utf8", (err, data) => {
    if (err) {
      console.error(err); // Good for debugging on the server
      return res.status(500).json({ error: "Failed to load payload" });
    }
    try {
      res.json(JSON.parse(data));
    } catch (parseErr) {
      res.status(500).json({ error: "Invalid JSON format in file" });
    }
  });
});

app.get('/api/blog/posts', (req, res) => {
  const posts = readBlogPosts()
    .sort((a, b) => new Date(b.publishedAt) - new Date(a.publishedAt))
    .map((p) => normalizePostForApi(p, req));
  res.json(posts);
});

app.get('/api/blog/posts/:slug', (req, res) => {
  const posts = readBlogPosts();
  const post = posts.find((p) => p.slug === req.params.slug);
  if (!post) return res.status(404).json({ error: 'Post not found' });
  res.json(normalizePostForApi(post, req));
});

app.post('/api/blog/posts', upload.single('image'), (req, res) => {
  const posts = readBlogPosts();
  const title = (req.body.title || '').trim();
  const content = (req.body.content || '').trim();
  const excerpt = (req.body.excerpt || '').trim();
  const seoTitle = (req.body.seoTitle || title).trim();
  const seoDescription = (req.body.seoDescription || excerpt || content.slice(0, 160)).trim();
  const requestedSlug = (req.body.slug || title).trim();

  if (!title || !content) {
    return res.status(400).json({ error: 'title and content are required' });
  }

  const slug = ensureUniqueSlug(posts, requestedSlug);
  const now = new Date().toISOString();
  const imagePath = req.file ? `/uploads/blog-images/${req.file.filename}` : null;
  const id = `${Date.now()}-${Math.round(Math.random() * 1e6)}`;

  const post = {
    id,
    title,
    slug,
    excerpt,
    content,
    seoTitle,
    seoDescription,
    imagePath,
    publishedAt: now,
    updatedAt: now,
  };

  posts.push(post);
  writeBlogPosts(posts);
  res.status(201).json(normalizePostForApi(post, req));
});

app.put('/api/blog/posts/:id', upload.single('image'), (req, res) => {
  const posts = readBlogPosts();
  const idx = posts.findIndex((p) => p.id === req.params.id);
  if (idx === -1) return res.status(404).json({ error: 'Post not found' });

  const post = posts[idx];
  const title = (req.body.title ?? post.title).trim();
  const content = (req.body.content ?? post.content).trim();
  const excerpt = (req.body.excerpt ?? post.excerpt).trim();
  const seoTitle = (req.body.seoTitle ?? post.seoTitle ?? title).trim();
  const seoDescription = (req.body.seoDescription ?? post.seoDescription ?? excerpt).trim();
  const requestedSlug = (req.body.slug ?? post.slug).trim();
  const slug = ensureUniqueSlug(posts, requestedSlug || title, post.id);

  if (!title || !content) {
    return res.status(400).json({ error: 'title and content are required' });
  }

  let imagePath = post.imagePath;
  if (req.file) {
    if (imagePath) {
      const oldPath = resolvePublicPathToDisk(imagePath);
      if (fs.existsSync(oldPath)) fs.unlinkSync(oldPath);
    }
    imagePath = `/uploads/blog-images/${req.file.filename}`;
  }

  const updated = {
    ...post,
    title,
    slug,
    content,
    excerpt,
    seoTitle,
    seoDescription,
    imagePath,
    updatedAt: new Date().toISOString(),
  };
  posts[idx] = updated;
  writeBlogPosts(posts);
  res.json(normalizePostForApi(updated, req));
});

app.delete('/api/blog/posts/:id', (req, res) => {
  const posts = readBlogPosts();
  const idx = posts.findIndex((p) => p.id === req.params.id);
  if (idx === -1) return res.status(404).json({ error: 'Post not found' });

  const [deleted] = posts.splice(idx, 1);
  if (deleted.imagePath) {
    const filePath = resolvePublicPathToDisk(deleted.imagePath);
    if (fs.existsSync(filePath)) fs.unlinkSync(filePath);
  }

  writeBlogPosts(posts);
  res.json({ ok: true });
});

app.get('/blog', (req, res) => {
  const host = `${req.protocol}://${req.get('host')}`;
  const posts = readBlogPosts().sort((a, b) => new Date(b.publishedAt) - new Date(a.publishedAt));

  const items = posts
    .map((p) => {
      const imageTag = p.imagePath
        ? `<img src="${escapeHtml(host + p.imagePath)}" alt="${escapeHtml(p.title)}" style="max-width:480px;width:100%;height:auto;border-radius:8px;"/>`
        : '';
      return `<article style="margin-bottom:2rem;">
        <h2><a href="/blog/${escapeHtml(p.slug)}">${escapeHtml(p.title)}</a></h2>
        <p><small>${new Date(p.publishedAt).toDateString()}</small></p>
        ${imageTag}
        <p>${escapeHtml(p.excerpt || '')}</p>
      </article>`;
    })
    .join('\n');

  const html = `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Blog</title>
  <meta name="description" content="Local theatre blog posts." />
  <link rel="canonical" href="${host}/blog" />
</head>
<body style="font-family:Arial,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;">
  <h1>Blog</h1>
  ${items || '<p>No posts yet.</p>'}
</body>
</html>`;
  res.type('html').send(html);
});

app.get('/blog/:slug', (req, res) => {
  const host = `${req.protocol}://${req.get('host')}`;
  const posts = readBlogPosts();
  const post = posts.find((p) => p.slug === req.params.slug);
  if (!post) return res.status(404).send('Post not found');

  const canonical = `${host}/blog/${post.slug}`;
  const imageUrl = post.imagePath ? `${host}${post.imagePath}` : '';
  const html = `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>${escapeHtml(post.seoTitle || post.title)}</title>
  <meta name="description" content="${escapeHtml(post.seoDescription || post.excerpt || '')}" />
  <link rel="canonical" href="${canonical}" />
  <meta property="og:type" content="article" />
  <meta property="og:title" content="${escapeHtml(post.seoTitle || post.title)}" />
  <meta property="og:description" content="${escapeHtml(post.seoDescription || post.excerpt || '')}" />
  <meta property="og:url" content="${canonical}" />
  ${imageUrl ? `<meta property="og:image" content="${escapeHtml(imageUrl)}" />` : ''}
</head>
<body style="font-family:Arial,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;">
  <p><a href="/blog">Back to Blog</a></p>
  <article>
    <h1>${escapeHtml(post.title)}</h1>
    <p><small>Published ${new Date(post.publishedAt).toDateString()}</small></p>
    ${imageUrl ? `<img src="${escapeHtml(imageUrl)}" alt="${escapeHtml(post.title)}" style="max-width:680px;width:100%;height:auto;border-radius:8px;" />` : ''}
    <div style="white-space:pre-wrap;line-height:1.6;margin-top:1rem;">${escapeHtml(post.content)}</div>
  </article>
</body>
</html>`;
  res.type('html').send(html);
});

app.get('/sitemap.xml', (req, res) => {
  const host = `${req.protocol}://${req.get('host')}`;
  const posts = readBlogPosts();
  const urls = [
    `<url><loc>${host}/blog</loc></url>`,
    ...posts.map((p) => {
      const lastmod = p.updatedAt || p.publishedAt;
      return `<url><loc>${host}/blog/${p.slug}</loc><lastmod>${lastmod}</lastmod></url>`;
    }),
  ].join('');

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">${urls}</urlset>`;
  res.type('application/xml').send(xml);
});

app.get('/robots.txt', (req, res) => {
  const host = `${req.protocol}://${req.get('host')}`;
  res.type('text/plain').send(`User-agent: *\nAllow: /\nSitemap: ${host}/sitemap.xml\n`);
});

app.listen(3000, "0.0.0.0", () => {
  console.log("Listening on port 3000");
});
