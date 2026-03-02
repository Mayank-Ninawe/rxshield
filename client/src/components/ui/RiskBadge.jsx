import {
  CheckCircle,
  AlertCircle,
  AlertTriangle,
  AlertOctagon,
  ShieldAlert,
} from "lucide-react";

const RiskBadge = ({ level }) => {
  const config = {
    SAFE: {
      bg: "bg-green-900/40",
      text: "text-green-400",
      border: "border-green-700",
      Icon: CheckCircle,
      animate: "",
    },
    LOW: {
      bg: "bg-yellow-900/40",
      text: "text-yellow-400",
      border: "border-yellow-700",
      Icon: AlertCircle,
      animate: "",
    },
    MEDIUM: {
      bg: "bg-orange-900/40",
      text: "text-orange-400",
      border: "border-orange-700",
      Icon: AlertTriangle,
      animate: "",
    },
    HIGH: {
      bg: "bg-red-900/40",
      text: "text-red-400",
      border: "border-red-700",
      Icon: AlertOctagon,
      animate: "",
    },
    CRITICAL: {
      bg: "bg-red-950/60",
      text: "text-red-300",
      border: "border-red-500",
      Icon: ShieldAlert,
      animate: "animate-pulse",
    },
  };

  const { bg, text, border, Icon, animate } = config[level] || config.LOW;

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full border text-sm font-semibold ${bg} ${text} ${border} ${animate}`}
    >
      <Icon size={14} />
      {level}
    </span>
  );
};

export default RiskBadge;
