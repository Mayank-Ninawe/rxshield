import { useState } from "react";
import { prescriptionApi } from "../utils/api";
import toast from "react-hot-toast";

export const usePrescription = () => {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const analyzePrescription = async (
    prescriptionText,
    patientData,
    patientId = null,
  ) => {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await prescriptionApi.analyze({
        prescriptionText,
        patientData,
        patientId,
      });
      setResult(res.data);

      // Check if there are actual errors
      const hasErrors = res.data.errors && res.data.errors.length > 0;

      if (!hasErrors || res.data.riskLevel === "SAFE") {
        toast.success("✅ Prescription is safe!");
      } else if (res.data.riskLevel === "CRITICAL") {
        toast.error("🚨 Critical errors detected!");
      } else {
        // Only show warning if there are actual errors
        toast("⚠️ Issues found - review required", {
          icon: "⚠️",
          style: { background: "#854d0e", color: "#fef9c3" },
        });
      }

      return res.data;
    } catch (err) {
      const msg = err.message || "Analysis failed";
      setError(msg);
      toast.error(msg);
      return null;
    } finally {
      setLoading(false);
    }
  };

  const reset = () => {
    setResult(null);
    setError(null);
  };

  return { loading, result, error, analyzePrescription, reset };
};
