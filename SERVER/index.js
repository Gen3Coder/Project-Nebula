import express from "express";
import cors from "cors";
import dotenv from "dotenv";
import db from "./db.js";
import cropRoutes from "./routes/CropHealthRoutes.js"; 

dotenv.config();

const app = express();
const PORT = process.env.PORT || 5000;

app.use(cors());
app.use(express.json());

// Health check
app.get("/api/health", async (req, res) => {
  try {
    const dbResult = await db.query("SELECT NOW()");
    res.json({
      status: "OK",
      message: "Running",
      dbTime: dbResult.rows[0].now
    });
  } catch (err) {
    res.status(500).json({ status: "Warning", error: err.message });
  }
});

// Crop Health Routes
app.use("/api", cropRoutes); 

app.listen(PORT, () => {
  console.log(`Server is running on port ${PORT}`);
});