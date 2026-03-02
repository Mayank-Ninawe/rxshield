import { NavLink } from "react-router-dom";
import {
  X,
  LayoutDashboard,
  ScanLine,
  ShieldCheck,
  FileText,
} from "lucide-react";

const Sidebar = ({ isOpen, onClose }) => {
  const navLinks = [
    { path: "/dashboard", icon: LayoutDashboard, label: "Dashboard" },
    { path: "/ocr-upload", icon: ScanLine, label: "OCR Upload" },
    { path: "/pharmacist", icon: ShieldCheck, label: "Pharmacist" },
    { path: "/audit-log", icon: FileText, label: "Audit Log" },
  ];

  return (
    <>
      {/* Sidebar */}
      <aside
        className={`fixed left-0 top-0 h-full z-40 w-64 bg-gray-950 border-r border-gray-800 transition-transform duration-300 flex flex-col ${
          isOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
        }`}
      >
        {/* Top: Logo + close button (mobile only) */}
        <div className="flex items-center justify-between p-4 border-b border-gray-800 md:border-0">
          <div className="text-xl font-bold text-blue-400">💊 RxShield</div>
          <button
            onClick={onClose}
            className="md:hidden text-gray-400 hover:text-white transition-colors p-2 hover:bg-gray-800 rounded-lg"
          >
            <X size={20} />
          </button>
        </div>

        {/* Middle: Nav links */}
        <nav className="flex-1 py-4">
          <ul className="space-y-1">
            {navLinks.map((link) => {
              const Icon = link.icon;
              return (
                <li key={link.path}>
                  <NavLink
                    to={link.path}
                    onClick={() => onClose()}
                    className={({ isActive }) =>
                      `flex items-center gap-3 px-4 py-3 transition-colors ${
                        isActive
                          ? "bg-blue-600/20 text-blue-400 border-r-2 border-blue-500"
                          : "text-gray-400 hover:bg-gray-900 hover:text-white"
                      }`
                    }
                  >
                    <Icon size={20} />
                    <span className="font-medium">{link.label}</span>
                  </NavLink>
                </li>
              );
            })}
          </ul>
        </nav>

        {/* Bottom: Version info */}
        <div className="p-4 border-t border-gray-800">
          <p className="text-xs text-gray-600 font-semibold">RxShield v1.0.0</p>
          <p className="text-xs text-gray-700 mt-1">
            Made for safer prescriptions
          </p>
        </div>
      </aside>

      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-30 md:hidden"
          onClick={onClose}
        />
      )}
    </>
  );
};

export default Sidebar;
