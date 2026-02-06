import express from 'express';
import path from 'path';
import fs from 'fs';
import cors from 'cors';
import { fileURLToPath } from 'url'; // Required for __dirname fix

const app = express();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

app.use(cors({
    origin: 'https://calendar.ben.place', // Be specific
    methods: ['GET', 'POST'],
}));

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