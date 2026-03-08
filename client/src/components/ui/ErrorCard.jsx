import { useState } from "react";
import {
  Zap,
  FileX,
  TrendingUp,
  Copy,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import RiskBadge from "./RiskBadge";

const ErrorCard = ({ error }) => {
  const [detailsOpen, setDetailsOpen] = useState(false);

  const errorTypeConfig = {
    DDI: { icon: Zap, color: "orange", label: "Drug Interaction" },
    INDICATION_MISMATCH: {
      icon: FileX,
      color: "red",
      label: "Indication Mismatch",
    },
    DOSAGE_ERROR: { icon: TrendingUp, color: "yellow", label: "Dosage Error" },
    LASA: { icon: Copy, color: "purple", label: "LASA Alert" },
    ALLERGY: { icon: AlertTriangle, color: "red", label: "Allergy Alert" },
  };

  const config = errorTypeConfig[error.error_type] || errorTypeConfig.DDI;
  const Icon = config.icon;
  const colorClass = `border-${config.color}-700`;
  const hoverColorClass = `hover:border-${config.color}-500`;
  const iconColorClass = `text-${config.color}-400`;
  const isAllergy = error.error_type === "ALLERGY";
  const pulseClass = isAllergy ? "animate-pulse" : "";

  return (
    <div
      className={`bg-gray-50 dark:bg-gray-900 border ${colorClass} ${pulseClass} rounded-xl p-4 ${hoverColorClass} transition-all`}
    >
      {/* Header row */}
      <div className="flex items-center justify-between gap-3 mb-3">
        <div className="flex items-center gap-2">
          <Icon size={20} className={iconColorClass} />
          <span className="text-sm font-medium text-gray-600 dark:text-gray-300">
            {config.label}
          </span>
        </div>
        <RiskBadge level={error.severity} />
      </div>

      {/* Drug info row */}
      {(error.drug || (error.drug_a && error.drug_b)) && (
        <div className="mb-2">
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {error.drug && (
              <span>
                Drug:{" "}
                <span className="font-semibold text-gray-700 dark:text-gray-200">
                  {error.drug}
                </span>
              </span>
            )}
            {error.drug_a && error.drug_b && (
              <span className="font-semibold text-gray-700 dark:text-gray-200">
                {error.drug_a} + {error.drug_b}
              </span>
            )}
          </p>
        </div>
      )}

      {/* Message */}
      <p className="text-gray-600 dark:text-gray-300 text-sm mb-3">
        {error.message}
      </p>

      {/* Explanation Section */}
      {error.explanation && (
        <div className="mt-3 bg-gray-800/60 dark:bg-gray-800/60 rounded-lg p-3 border-l-4 border-l-orange-500">
          <p className="text-xs font-semibold text-gray-400 dark:text-gray-400 uppercase tracking-wide mb-1">
            🔬 Why This Is a Problem
          </p>
          <p className="text-sm text-gray-300 dark:text-gray-300 leading-relaxed">
            {error.explanation}
          </p>
        </div>
      )}

      {/* Solution Section */}
      {error.solution && (
        <div className="mt-2 bg-green-900/20 dark:bg-green-900/20 rounded-lg p-3 border-l-4 border-l-green-500">
          <p className="text-xs font-semibold text-green-400 dark:text-green-400 uppercase tracking-wide mb-1">
            ✅ Recommended Action
          </p>
          <p className="text-sm text-green-300 dark:text-green-300 leading-relaxed">
            {error.solution}
          </p>
        </div>
      )}

      {/* Confidence */}
      {error.confidence !== undefined && (
        <p className="text-xs text-gray-500 mb-2 mt-3">
          Model confidence: {(error.confidence * 100).toFixed(1)}%
        </p>
      )}

      {/* Details accordion */}
      {error.details && Object.keys(error.details).length > 0 && (
        <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-800">
          <button
            onClick={() => setDetailsOpen(!detailsOpen)}
            className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200 transition-colors"
          >
            {detailsOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            <span>Details</span>
          </button>

          {detailsOpen && (
            <div className="mt-3 space-y-2">
              {Object.entries(error.details).map(([key, value]) => (
                <div key={key} className="flex gap-2 text-xs">
                  <span className="text-gray-500 font-medium min-w-25">
                    {key}:
                  </span>
                  <span className="text-gray-500 dark:text-gray-400">
                    {String(value)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ErrorCard;
