const express = require("express");
const app = express();
const path = require("path");


app.get("/", (req, res) => {
  res.json({
    status: "ok",
    message: "Eello from Oracle Cloud",
    time: new Date().toISOString()
  });
});

app.get("/calendar", (req, res) => {
  const filePath = path.join(__dirname, "testpayload.json");

  fs.readFile(filePath, "utf8", (err, data) => {
    if (err) {
      return res.status(500).json({ error: "Failed to load payload" });
    }
    res.json(JSON.parse(data));
  });
});



app.listen(3000, "0.0.0.0", () => {
  console.log("Listening on port 3000");
});
