import axios from "axios";
import { auth } from "../firebase/config";

// SECTION 1 — API Base URLs
const NODE_API = import.meta.env.VITE_NODE_API_URL || "http://localhost:5000";
const ML_API = import.meta.env.VITE_ML_API_URL || "http://localhost:8000";

// Create axios instances
export const nodeApi = axios.create({
  baseURL: NODE_API,
  timeout: 30000,
  headers: { "Content-Type": "application/json" },
});

export const mlApi = axios.create({
  baseURL: ML_API,
  timeout: 60000, // ML can be slow
  headers: { "Content-Type": "application/json" },
});

// SECTION 2 — Request interceptor for nodeApi (auto-attach Firebase token)
nodeApi.interceptors.request.use(
  async (config) => {
    try {
      const user = auth.currentUser;
      if (user) {
        const token = await user.getIdToken();
        config.headers.Authorization = `Bearer ${token}`;
      }
    } catch (err) {
      console.error("Token fetch failed:", err);
    }
    return config;
  },
  (error) => Promise.reject(error),
);

// SECTION 3 — Response interceptor for nodeApi (global error handling)
nodeApi.interceptors.response.use(
  (response) => response,
  (error) => {
    const message =
      error.response?.data?.error || error.message || "Something went wrong";

    if (error.response?.status === 401) {
      console.warn("Unauthorized - redirecting to login");
      window.location.href = "/login";
    }

    return Promise.reject({ message, status: error.response?.status });
  },
);

// SECTION 4 — API service functions

// PRESCRIPTION APIs (hit Node.js which calls ML)
export const prescriptionApi = {
  analyze: (data) =>
    nodeApi.post("/api/prescription/analyze", data, { timeout: 120000 }), // 2 minutes for ML processing
  getById: (id) => nodeApi.get(`/api/prescription/${id}`),
  getByPatient: (patientId) =>
    nodeApi.get(`/api/prescription/patient/${patientId}`),
  updateStatus: (id, data) =>
    nodeApi.patch(`/api/prescription/${id}/status`, data),
};

// PATIENT APIs
export const patientApi = {
  create: (data) => nodeApi.post("/api/patients", data),
  getAll: () => nodeApi.get("/api/patients"),
  getById: (id) => nodeApi.get(`/api/patients/${id}`),
  update: (id, data) => nodeApi.put(`/api/patients/${id}`, data),
  delete: (id) => nodeApi.delete(`/api/patients/${id}`),
};

// AUDIT APIs
export const auditApi = {
  getAll: (limit = 50) => nodeApi.get(`/api/audit?limit=${limit}`),
  getByPrescription: (rxId) => nodeApi.get(`/api/audit/prescription/${rxId}`),
};

// OCR API (hit Node.js which forwards to ML)
export const ocrApi = {
  extract: (formData) =>
    nodeApi.post("/api/ocr/extract", formData, {
      headers: { "Content-Type": "multipart/form-data" },
      timeout: 120000, // 2 minutes timeout for OCR
    }),
};

// ML API direct (for health check only)
export const mlHealthApi = {
  check: () => mlApi.get("/health"),
};
