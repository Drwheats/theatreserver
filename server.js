const express = require("express");
const app = express();

app.get("/", (req, res) => {
  res.json({
    status: "ok",
    message: "Chello from Oracle Cloud",
    time: new Date().toISOString()
  });
});

app.listen(3000, "0.0.0.0", () => {
  console.log("Listening on port 3000");
});
