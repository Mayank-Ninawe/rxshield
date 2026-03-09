/**
 * Axios instance for ML API communication
 * Handles timeouts and error messages for ML API calls
 */

const axios = require("axios");

const mlAxios = axios.create({
  baseURL: process.env.ML_API_URL || "http://localhost:8000",
  timeout: 45000, // 45 seconds for Gemini OCR + drug resolution
  headers: { "Content-Type": "application/json" },
});

mlAxios.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.code === "ECONNABORTED") {
      err.message = "ML API timeout — is ml_engine/api/main.py running?";
    }
    if (err.code === "ECONNREFUSED") {
      err.message = "ML API is offline — start with: python api/main.py";
    }
    return Promise.reject(err);
  },
);

module.exports = mlAxios;
