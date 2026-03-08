const express = require("express");
const router = express.Router();
const axios = require("axios");
const multer = require("multer");
const { verifyToken } = require("../middleware/auth");
const { db } = require("../config/firebase");

const storage = multer.memoryStorage();
const upload = multer({
  storage,
  limits: { fileSize: 5 * 1024 * 1024 }, // 5MB
  fileFilter: (req, file, cb) => {
    const allowed = ["image/jpeg", "image/png", "image/webp", "image/jpg"];
    if (allowed.includes(file.mimetype)) {
      cb(null, true);
    } else {
      cb(new Error("Only JPG/PNG/WEBP images allowed"));
    }
  },
});

// POST /api/ocr/extract
router.post(
  "/extract",
  verifyToken,
  upload.single("prescription_image"),
  async (req, res) => {
    if (!req.file) {
      return res.status(400).json({ error: "No image file uploaded" });
    }

    try {
      // Convert buffer to base64
      const base64Image = req.file.buffer.toString("base64");
      const language = req.body.language || "auto";

      // Call ML API
      const mlResponse = await axios.post(
        `${process.env.ML_API_URL}/ocr`,
        {
          image_b64: base64Image,
          language: language,
        },
        { timeout: 120000 }, // 2 minutes
      );

      const ocrData = mlResponse.data;

      // Log to Firestore (async, don't await)
      db.collection("ocrLogs")
        .add({
          userId: req.user.uid,
          engine: ocrData.engine,
          language: ocrData.language,
          charCount: ocrData.charCount,
          success: ocrData.success,
          timestamp: new Date().toISOString(),
        })
        .catch(console.error);

      return res.json({
        extractedText: ocrData.extractedText,
        cleanedText: ocrData.cleanedText,
        engine: ocrData.engine,
        language: ocrData.language,
        confidence: ocrData.confidence,
        charCount: ocrData.charCount,
        linesDetected: ocrData.lines_detected || null,
        success: ocrData.success,
      });
    } catch (err) {
      console.error("OCR route error:", err.message);

      if (err.code === "ECONNREFUSED") {
        return res.status(503).json({
          error: "ML API is not running. Start ml_engine/api/main.py first.",
        });
      }

      return res.status(500).json({
        error: err.response?.data?.detail || err.message || "OCR failed",
      });
    }
  },
);

module.exports = router;
