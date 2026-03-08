const express = require("express");
const router = express.Router();
const axios = require("axios");
const { db } = require("../config/firebase");
const { verifyToken } = require("../middleware/auth");
const { checkDrugInteraction } = require("../utils/rxnorm");

router.use(verifyToken);

// POST /api/prescription/analyze
router.post("/analyze", async (req, res) => {
  try {
    const { patientId, prescriptionText, patientData } = req.body;

    // Step A: ML API — NER + error detection
    let extractedDrugs = [];
    let dosages = [];
    let errors = [];
    let riskScore = 0;

    try {
      const mlResponse = await axios.post(
        `${process.env.ML_API_URL}/analyze`,
        {
          prescriptionText,
          patientData,
        },
        { timeout: 120000 }, // 2 minutes timeout for ML processing
      );
      extractedDrugs = mlResponse.data.extractedDrugs ?? [];
      dosages = mlResponse.data.dosages ?? [];
      errors = mlResponse.data.errors ?? [];
      riskScore = mlResponse.data.riskScore ?? 0;
    } catch (_mlErr) {
      // ML API unavailable — proceed with empty results
    }

    // Step B: Drug-Drug Interaction check via RxNorm
    const rxcuiList = extractedDrugs.map((drug) => drug?.rxcui).filter(Boolean);

    if (rxcuiList.length >= 2) {
      const interactions = await checkDrugInteraction(rxcuiList);
      const ddiErrors = interactions.map((interaction) => ({
        type: "DDI",
        ...interaction,
      }));
      errors = [...errors, ...ddiErrors];
    }

    // Step C: Allergy check
    const allergiesLower = (patientData?.allergies ?? []).map((a) =>
      a.toLowerCase(),
    );

    for (const drugObj of extractedDrugs) {
      const drugName = typeof drugObj === "string" ? drugObj : drugObj?.name;
      if (!drugName) continue;

      if (allergiesLower.includes(drugName.toLowerCase())) {
        errors.push({
          type: "ALLERGY",
          drug: drugName,
          message: `Patient is allergic to ${drugName}`,
          severity: "CRITICAL",
        });
      }
    }

    // Step D: Save prescription to Firestore
    const status = errors.length > 0 ? "flagged" : "clear";

    const prescriptionDoc = await db.collection("prescriptions").add({
      patientId,
      prescriptionText,
      extractedDrugs,
      dosages,
      errors,
      riskScore,
      analyzedBy: req.user.uid,
      status,
      createdAt: new Date().toISOString(),
    });

    // Step E: Save to audit log
    await db.collection("auditLog").add({
      action: "prescription_analyzed",
      prescriptionId: prescriptionDoc.id,
      patientId,
      doctorId: req.user.uid,
      errorCount: errors.length,
      riskScore,
      timestamp: new Date().toISOString(),
    });

    res.json({
      prescriptionId: prescriptionDoc.id,
      extractedDrugs,
      dosages,
      errors,
      riskScore,
      status,
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /api/prescription/flagged — get prescriptions by status
router.get("/flagged", async (req, res) => {
  try {
    const status = req.query.status || "flagged";

    let query = db.collection("prescriptions");

    if (status !== "all") {
      query = query.where("status", "==", status);
    }

    query = query.orderBy("createdAt", "desc").limit(50);

    const snapshot = await query.get();
    const prescriptions = snapshot.docs.map((doc) => ({
      id: doc.id,
      ...doc.data(),
    }));

    res.json(prescriptions);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /api/prescription/:id — single prescription
router.get("/:id", async (req, res) => {
  try {
    const doc = await db.collection("prescriptions").doc(req.params.id).get();

    if (!doc.exists) {
      return res.status(404).json({ error: "Prescription not found" });
    }

    res.json({ id: doc.id, ...doc.data() });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /api/prescription/patient/:patientId — all prescriptions for a patient
router.get("/patient/:patientId", async (req, res) => {
  try {
    const snapshot = await db
      .collection("prescriptions")
      .where("patientId", "==", req.params.patientId)
      .orderBy("createdAt", "desc")
      .get();

    const prescriptions = snapshot.docs.map((doc) => ({
      id: doc.id,
      ...doc.data(),
    }));

    res.json(prescriptions);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// PATCH /api/prescription/:id/status — pharmacist review
router.patch("/:id/status", async (req, res) => {
  try {
    const { status, pharmacistNote } = req.body;

    await db.collection("prescriptions").doc(req.params.id).update({
      status,
      pharmacistNote,
      reviewedBy: req.user.uid,
      reviewedAt: new Date().toISOString(),
    });

    res.json({ success: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;
