
import express from "express";
import cors from "cors";
import dotenv from "dotenv";
import db from "./db.js";

dotenv.config();

const app = express();
const PORT = process.env.PORT || 5000;

app.use(cors());
app.use(express.json());

app.get("/api/health", async (req, res) => {
    try {
        const dbResult = await db.query("SELECT NOW()");

        res.json({
            status: "OK",
            message: "Running",
            dbTime: dbResult.rows[0].now
        });

    } catch (err) {
        console.error(err);

        res.status(500).json({
            status: "Warning",
            message: "Something in DB is out",
            error: err.message
        });
    }
});

app.listen(PORT, () => {
    console.log(`Server is running on port ${PORT}`);
});