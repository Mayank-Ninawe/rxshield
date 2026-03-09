require("dotenv").config();

const express = require("express");
const cors = require("cors");

// Initialize Firebase Admin early
require("./config/firebase");

const prescriptionRoutes = require("./routes/prescription");
const patientRoutes = require("./routes/patient");
const ocrRoutes = require("./routes/ocr");
const auditRoutes = require("./routes/audit");

const app = express();
const PORT = process.env.PORT || 5000;

// ── Middleware ────────────────────────────────────────────────────────────────
// CORS Configuration for production
const allowedOrigins = [
  "http://localhost:5173", // Vite dev server
  "http://localhost:3000", // Alternative dev port
  "http://localhost:4173", // Vite preview
  process.env.FRONTEND_URL, // Vercel production URL
  process.env.CLIENT_URL, // Fallback (legacy)
].filter(Boolean); // Remove undefined values

app.use(
  cors({
    origin: function (origin, callback) {
      // Allow requests with no origin (mobile apps, Postman, curl)
      if (!origin) return callback(null, true);

      // Check if origin is in allowed list
      if (allowedOrigins.includes(origin)) {
        return callback(null, true);
      }

      // In development, allow any localhost origin as fallback
      if (
        process.env.NODE_ENV !== "production" &&
        origin.match(/^http:\/\/localhost:\d+$/)
      ) {
        return callback(null, true);
      }

      callback(new Error(`CORS: Origin ${origin} not allowed`));
    },
    credentials: true,
    methods: ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allowedHeaders: ["Content-Type", "Authorization"],
  }),
);
app.use(express.json({ limit: "10mb" }));
app.use(express.urlencoded({ extended: true, limit: "10mb" }));

// ── Routes ────────────────────────────────────────────────────────────────────
app.use("/api/prescription", prescriptionRoutes);
app.use("/api/patients", patientRoutes);
app.use("/api/ocr", ocrRoutes);
app.use("/api/audit", auditRoutes);

// Health check
app.get("/health", (_req, res) => {
  res.json({
    status: "ok",
    service: "RxShield API",
    mlApiUrl: process.env.ML_API_URL,
    timestamp: new Date().toISOString(),
  });
});

// Health check for Railway (uses /api/health)
app.get("/api/health", (_req, res) => {
  res.json({ status: "ok", service: "RxShield Backend" });
});

// ── 404 handler ───────────────────────────────────────────────────────────────
app.use((_req, res) => {
  res.status(404).json({ error: "Route not found" });
});

// ── Global error handler ──────────────────────────────────────────────────────
// eslint-disable-next-line no-unused-vars
app.use((err, _req, res, _next) => {
  console.error(err.stack);
  res.status(500).json({ error: err.message || "Internal server error" });
});

// ── Start ─────────────────────────────────────────────────────────────────────
app.listen(PORT, () => {
  console.log(`✅ RxShield server running on port ${PORT}`);
});
