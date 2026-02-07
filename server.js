import express from 'express';
import path from 'path';
import fs from 'fs';
import cors from 'cors';
import { fileURLToPath } from 'url'; // Required for __dirname fix

const app = express();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Allow multiple trusted origins via a whitelist
const whitelist = [
  'https://calendar.ben.place',
  // add other origins you trust, for example during development:
  'http://localhost:3000',
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
  methods: ['GET', 'POST'],
};

app.use(cors(corsOptions));

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

app.listen(3000, "0.0.0.0", () => {
  console.log("Listening on port 3000");
});