import { useState } from "react";
import Layout from "../components/Layout";
import RiskReport from "../components/ui/RiskReport";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import { usePrescription } from "../hooks/usePrescription";
import { useAuth } from "../context/AuthContext";
import {
  Pill,
  User,
  ChevronDown,
  ChevronUp,
  Stethoscope,
  Zap,
} from "lucide-react";
import toast from "react-hot-toast";

const DoctorDashboard = () => {
  const { loading, result, error, analyzePrescription, reset } =
    usePrescription();
  const { currentUser } = useAuth();

  const [prescriptionText, setPrescriptionText] = useState("");
  const [showPatientForm, setShowPatientForm] = useState(false);
  const [patientData, setPatientData] = useState({
    age: "",
    gender: "Male",
    weight_kg: "",
    diagnosis: "",
    allergies: "",
    current_medications: "",
    comorbidities: "",
  });

  // Helper to update patient data
  const updatePatient = (field, value) => {
    setPatientData((prev) => ({ ...prev, [field]: value }));
  };

  // Sample prescriptions for quick testing
  const SAMPLES = [
    {
      label: "✅ Safe: Diabetic Patient",
      text: "Rx:\n1. Metformin 500mg twice daily for 30 days\n2. Aspirin 75mg once daily\n3. Atorvastatin 20mg at night for 90 days\nAllergies: None known",
    },
    {
      label: "⚠️ DDI: Aspirin + Warfarin",
      text: "Rx:\n1. Aspirin 500mg three times daily\n2. Warfarin 5mg once daily\nPatient has DVT",
    },
    {
      label: "🚨 Overdose: Metformin",
      text: "Rx:\n1. Metformin 5000mg twice daily for 30 days\nDiagnosis: Type 2 Diabetes",
    },
    {
      label: "🔤 LASA: Tramadol",
      text: "Rx:\n1. Tramadol 50mg four times daily for 7 days\nDiagnosis: Moderate pain post-surgery",
    },
  ];

  // Handle prescription analysis
  const handleAnalyze = async (e) => {
    e.preventDefault();

    if (prescriptionText.trim().length < 10) {
      toast.error("Please enter a valid prescription text");
      return;
    }

    // Build patient payload
    const patientPayload = {
      age: parseInt(patientData.age) || 35,
      gender: patientData.gender || "Male",
      weight_kg: parseFloat(patientData.weight_kg) || 70,
      diagnosis: patientData.diagnosis
        ? patientData.diagnosis
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean)
        : [],
      allergies: patientData.allergies
        ? patientData.allergies
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean)
        : [],
      current_medications: patientData.current_medications
        ? patientData.current_medications
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean)
        : [],
      comorbidities: patientData.comorbidities
        ? patientData.comorbidities
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean)
        : [],
    };

    await analyzePrescription(prescriptionText, patientPayload);
  };

  // If we have results, show the report
  if (result) {
    return (
      <Layout>
        <RiskReport result={result} onReset={reset} />
      </Layout>
    );
  }

  // Otherwise, show the input form
  return (
    <Layout>
      <div className="max-w-4xl mx-auto">
        {/* HEADER */}
        <div className="mb-6">
          <div className="flex items-center gap-3 mb-2">
            <Stethoscope className="text-blue-400" size={32} />
            <h1 className="text-3xl font-bold text-white">
              Prescription Analyzer
            </h1>
          </div>
          <p className="text-gray-400 mb-2">
            Paste prescription text to detect errors instantly
          </p>
          <p className="text-sm text-gray-500">
            Welcome back, Dr.{" "}
            {currentUser?.displayName ||
              currentUser?.email?.split("@")[0] ||
              "Doctor"}
          </p>
        </div>

        {/* MAIN FORM CARD */}
        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 mb-4">
          <form onSubmit={handleAnalyze} className="space-y-6">
            {/* SECTION 1 — Quick Sample Buttons */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-3">
                Quick Test Samples:
              </label>
              <div className="flex flex-wrap gap-2">
                {SAMPLES.map((sample, index) => (
                  <button
                    key={index}
                    type="button"
                    onClick={() => setPrescriptionText(sample.text)}
                    className="text-xs border border-gray-700 rounded-lg px-3 py-1.5 hover:bg-gray-800 text-gray-400 transition-colors"
                  >
                    {sample.label}
                  </button>
                ))}
              </div>
            </div>

            {/* SECTION 2 — Prescription Text Area */}
            <div>
              <label className="flex items-center gap-2 text-sm font-medium text-gray-300 mb-2">
                <Pill size={16} />
                Prescription Text *
              </label>
              <textarea
                rows={8}
                value={prescriptionText}
                onChange={(e) => setPrescriptionText(e.target.value)}
                placeholder="Paste prescription text here...\n\nExample:\nRx:\n1. Metformin 500mg twice daily x 30 days\n2. Aspirin 75mg once daily"
                className="w-full bg-gray-800 border border-gray-700 rounded-xl p-4 text-white placeholder-gray-600 resize-none focus:outline-none focus:border-blue-500 font-mono text-sm transition-colors"
              />
              <p className="text-xs text-gray-500 text-right mt-1">
                {prescriptionText.length} characters
              </p>
            </div>

            {/* SECTION 3 — Patient Info (Collapsible) */}
            <div>
              <button
                type="button"
                onClick={() => setShowPatientForm(!showPatientForm)}
                className="w-full flex items-center justify-between bg-gray-800 rounded-xl px-4 py-3 text-gray-300 hover:bg-gray-750 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <User size={16} />
                  <span className="font-medium">
                    Patient Information (Optional)
                  </span>
                </div>
                {showPatientForm ? (
                  <ChevronUp size={16} />
                ) : (
                  <ChevronDown size={16} />
                )}
              </button>

              {showPatientForm && (
                <div className="mt-4 bg-gray-800/50 rounded-xl p-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* Age */}
                    <div>
                      <label className="block text-xs font-medium text-gray-400 mb-1">
                        Age
                      </label>
                      <input
                        type="number"
                        value={patientData.age}
                        onChange={(e) => updatePatient("age", e.target.value)}
                        placeholder="Patient age"
                        className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                      />
                    </div>

                    {/* Gender */}
                    <div>
                      <label className="block text-xs font-medium text-gray-400 mb-1">
                        Gender
                      </label>
                      <select
                        value={patientData.gender}
                        onChange={(e) =>
                          updatePatient("gender", e.target.value)
                        }
                        className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                      >
                        <option value="Male">Male</option>
                        <option value="Female">Female</option>
                        <option value="Other">Other</option>
                      </select>
                    </div>

                    {/* Weight */}
                    <div>
                      <label className="block text-xs font-medium text-gray-400 mb-1">
                        Weight (kg)
                      </label>
                      <input
                        type="number"
                        step="0.1"
                        value={patientData.weight_kg}
                        onChange={(e) =>
                          updatePatient("weight_kg", e.target.value)
                        }
                        placeholder="Weight in kg"
                        className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                      />
                    </div>

                    {/* Diagnosis */}
                    <div>
                      <label className="block text-xs font-medium text-gray-400 mb-1">
                        Diagnosis (comma-separated)
                      </label>
                      <input
                        type="text"
                        value={patientData.diagnosis}
                        onChange={(e) =>
                          updatePatient("diagnosis", e.target.value)
                        }
                        placeholder="e.g. Type 2 Diabetes, Hypertension"
                        className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                      />
                    </div>

                    {/* Allergies */}
                    <div>
                      <label className="block text-xs font-medium text-gray-400 mb-1">
                        Allergies (comma-separated)
                      </label>
                      <input
                        type="text"
                        value={patientData.allergies}
                        onChange={(e) =>
                          updatePatient("allergies", e.target.value)
                        }
                        placeholder="e.g. Penicillin, Sulfa"
                        className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                      />
                    </div>

                    {/* Current Medications */}
                    <div>
                      <label className="block text-xs font-medium text-gray-400 mb-1">
                        Current Medications (comma-separated)
                      </label>
                      <input
                        type="text"
                        value={patientData.current_medications}
                        onChange={(e) =>
                          updatePatient("current_medications", e.target.value)
                        }
                        placeholder="e.g. Metformin, Atenolol"
                        className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                      />
                    </div>
                  </div>

                  <p className="text-gray-500 text-xs mt-3">
                    💡 Adding patient info improves detection accuracy
                  </p>
                </div>
              )}
            </div>

            {/* SECTION 4 — Submit Button */}
            <button
              type="submit"
              disabled={loading || prescriptionText.trim().length < 10}
              className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:cursor-not-allowed text-white font-semibold py-4 rounded-xl flex items-center justify-center gap-2 text-lg transition-all"
            >
              {loading ? (
                <>
                  <LoadingSpinner size="sm" />
                  <span>Analyzing...</span>
                </>
              ) : (
                <>
                  <Zap size={18} />
                  <span>Analyze Prescription</span>
                </>
              )}
            </button>
          </form>
        </div>

        {/* BOTTOM INFO ROW */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 text-center">
            <p className="text-white font-semibold mb-1">4 Error Types</p>
            <p className="text-gray-400 text-xs">
              DDI, LASA, Dosage, Indication
            </p>
          </div>

          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 text-center">
            <p className="text-white font-semibold mb-1">AI Powered</p>
            <p className="text-gray-400 text-xs">
              DistilBERT NER + RandomForest
            </p>
          </div>

          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 text-center">
            <p className="text-white font-semibold mb-1">Instant Results</p>
            <p className="text-gray-400 text-xs">&lt; 5 second analysis</p>
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default DoctorDashboard;
