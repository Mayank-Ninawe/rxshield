import RiskBadge from "./RiskBadge";
import ErrorCard from "./ErrorCard";
import {
  CheckCircle,
  Clock,
  Pill,
  AlertTriangle,
  RotateCcw,
  Download,
} from "lucide-react";
import toast from "react-hot-toast";

const RiskReport = ({ result, onReset }) => {
  const {
    prescriptionId,
    extractedDrugs,
    errors,
    riskScore,
    riskLevel,
    summary,
    processingTime_ms,
  } = result;

  // Get progress bar color based on risk level
  const getProgressColor = () => {
    if (riskLevel === "SAFE" || riskLevel === "LOW") return "bg-green-500";
    if (riskLevel === "MEDIUM") return "bg-yellow-500";
    if (riskLevel === "HIGH") return "bg-red-500";
    if (riskLevel === "CRITICAL") return "bg-red-600 animate-pulse";
    return "bg-gray-500";
  };

  // Group errors by type
  const groupedErrors = {
    ALLERGY: errors.filter((e) => e.error_type === "ALLERGY"),
    DDI: errors.filter((e) => e.error_type === "DDI"),
    INDICATION_MISMATCH: errors.filter(
      (e) => e.error_type === "INDICATION_MISMATCH",
    ),
    DOSAGE_ERROR: errors.filter((e) => e.error_type === "DOSAGE_ERROR"),
    LASA: errors.filter((e) => e.error_type === "LASA"),
  };

  const copyReportId = () => {
    navigator.clipboard.writeText(prescriptionId);
    toast.success("Report ID copied!");
  };

  return (
    <div className="space-y-6">
      {/* SECTION A — Header bar */}
      <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
        <div className="flex items-start justify-between mb-3">
          <div>
            <h2 className="text-2xl font-bold text-white mb-1">
              Analysis Complete
            </h2>
            <p className="text-gray-500 text-sm">Report ID: {prescriptionId}</p>
          </div>
          <div className="flex items-center gap-3">
            <RiskBadge level={riskLevel} />
            <span className="text-gray-500 text-sm">{processingTime_ms}ms</span>
          </div>
        </div>

        <p className="text-gray-300 mb-4">{summary}</p>

        {/* Risk Score Progress Bar */}
        <div className="mt-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-gray-400">
              Risk Score: {(riskScore * 100).toFixed(0)}%
            </span>
          </div>
          <div className="w-full h-2 bg-gray-800 rounded-full overflow-hidden">
            <div
              className={`h-full ${getProgressColor()} transition-all duration-500`}
              style={{ width: `${riskScore * 100}%` }}
            />
          </div>
        </div>
      </div>

      {/* SECTION B — Stats row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <Pill className="text-blue-400 mb-2" size={24} />
          <p className="text-gray-400 text-xs mb-1">Drugs Found</p>
          <p className="text-white font-bold text-xl">
            {extractedDrugs.length}
          </p>
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <AlertTriangle className="text-orange-400 mb-2" size={24} />
          <p className="text-gray-400 text-xs mb-1">Issues Found</p>
          <p className="text-white font-bold text-xl">{errors.length}</p>
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <Clock className="text-purple-400 mb-2" size={24} />
          <p className="text-gray-400 text-xs mb-1">Analysis Time</p>
          <p className="text-white font-bold text-xl">{processingTime_ms}ms</p>
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <CheckCircle className="text-green-400 mb-2" size={24} />
          <p className="text-gray-400 text-xs mb-1">Status</p>
          <p className="text-white font-bold text-xl">{riskLevel}</p>
        </div>
      </div>

      {/* SECTION C — Extracted Drugs */}
      {extractedDrugs.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <Pill className="text-blue-400" size={20} />
            <h3 className="text-lg font-semibold text-white">
              Extracted Drugs
            </h3>
          </div>

          <div className="flex flex-wrap gap-2 overflow-x-auto">
            {extractedDrugs.map((drug, index) => (
              <span
                key={index}
                className="inline-flex items-center gap-2 bg-blue-900/30 border border-blue-700/50 text-blue-300 px-3 py-1.5 rounded-lg text-sm whitespace-nowrap"
              >
                💊 {drug.drug_name}
                {drug.dose && (
                  <span className="text-blue-400/70 text-xs">{drug.dose}</span>
                )}
                {drug.frequency && (
                  <span className="text-gray-500 text-xs">
                    • {drug.frequency}
                  </span>
                )}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* SECTION D — Errors section */}
      <div>
        {errors.length === 0 ? (
          <div className="bg-green-900/20 border border-green-700/50 rounded-xl p-6 text-center">
            <CheckCircle className="text-green-400 mx-auto mb-2" size={40} />
            <p className="text-green-400 font-semibold text-lg">
              No Issues Detected
            </p>
            <p className="text-gray-400 text-sm mt-1">
              This prescription appears safe for this patient.
            </p>
          </div>
        ) : (
          <div className="space-y-6">
            <h3 className="text-xl font-bold text-white flex items-center gap-2">
              ⚠️ Issues Detected ({errors.length})
            </h3>

            {/* ALLERGY errors (critical, show first) */}
            {groupedErrors.ALLERGY.length > 0 && (
              <div>
                <h4 className="text-red-400 font-semibold mb-3 flex items-center gap-2">
                  <AlertTriangle size={18} />
                  Allergy Alerts ({groupedErrors.ALLERGY.length})
                </h4>
                <div className="space-y-3">
                  {groupedErrors.ALLERGY.map((error, index) => (
                    <ErrorCard key={`allergy-${index}`} error={error} />
                  ))}
                </div>
              </div>
            )}

            {/* DDI errors */}
            {groupedErrors.DDI.length > 0 && (
              <div>
                <h4 className="text-orange-400 font-semibold mb-3">
                  Drug Interactions ({groupedErrors.DDI.length})
                </h4>
                <div className="space-y-3">
                  {groupedErrors.DDI.map((error, index) => (
                    <ErrorCard key={`ddi-${index}`} error={error} />
                  ))}
                </div>
              </div>
            )}

            {/* INDICATION_MISMATCH errors */}
            {groupedErrors.INDICATION_MISMATCH.length > 0 && (
              <div>
                <h4 className="text-red-400 font-semibold mb-3">
                  Indication Mismatches (
                  {groupedErrors.INDICATION_MISMATCH.length})
                </h4>
                <div className="space-y-3">
                  {groupedErrors.INDICATION_MISMATCH.map((error, index) => (
                    <ErrorCard key={`indication-${index}`} error={error} />
                  ))}
                </div>
              </div>
            )}

            {/* DOSAGE_ERROR errors */}
            {groupedErrors.DOSAGE_ERROR.length > 0 && (
              <div>
                <h4 className="text-yellow-400 font-semibold mb-3">
                  Dosage Errors ({groupedErrors.DOSAGE_ERROR.length})
                </h4>
                <div className="space-y-3">
                  {groupedErrors.DOSAGE_ERROR.map((error, index) => (
                    <ErrorCard key={`dosage-${index}`} error={error} />
                  ))}
                </div>
              </div>
            )}

            {/* LASA errors */}
            {groupedErrors.LASA.length > 0 && (
              <div>
                <h4 className="text-purple-400 font-semibold mb-3">
                  LASA Alerts ({groupedErrors.LASA.length})
                </h4>
                <div className="space-y-3">
                  {groupedErrors.LASA.map((error, index) => (
                    <ErrorCard key={`lasa-${index}`} error={error} />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* SECTION E — Action buttons */}
      <div className="flex gap-3">
        <button
          onClick={onReset}
          className="flex items-center gap-2 px-6 py-3 border border-gray-700 text-gray-300 hover:bg-gray-800 rounded-lg transition-colors font-medium"
        >
          <RotateCcw size={18} />
          Analyze Another
        </button>

        <button
          onClick={copyReportId}
          className="flex items-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors font-medium"
        >
          <Download size={18} />
          Copy Report ID
        </button>
      </div>
    </div>
  );
};

export default RiskReport;
