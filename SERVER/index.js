import express from "express";
import cors from "cors";
import dotenv from "dotenv";
import cookieParser from "cookie-parser";
import db from "./db.js";
import cropRoutes from "./routes/CropHealthRoutes.js";
import authRoutes from "./routes/authRoutes.js";
import errorHandler from "./middleware/errorMiddleware.js";

dotenv.config();

const app = express();
const PORT = process.env.PORT || 5000;

app.use(cors({
  origin: true,
  credentials: true,
}));
app.use(cookieParser());
app.use(express.json());

// Health check
app.get("/api/health", async (req, res) => {
  try {
    const dbResult = await db.query("SELECT NOW()");
    res.json({
      status: "OK",
      message: "Running",
      dbTime: dbResult.rows[0].now,
    });
  } catch (err) {
    res.status(500).json({ status: "Warning", error: err.message });
  }
});

// Authentication & Moderator Routes
app.use("/api/auth", authRoutes);
app.use("/api", authRoutes);

// Crop Health Routes
app.use("/api", cropRoutes);

// Global Error Handler
app.use(errorHandler);

app.listen(PORT, () => {
  console.log(`Server is running on port ${PORT}`);
});
