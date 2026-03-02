import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Menu, X, LogOut } from "lucide-react";
import { useAuth } from "../context/AuthContext";

const Navbar = ({ onMenuToggle }) => {
  const [mlStatus, setMlStatus] = useState("checking");
  const [menuOpen, setMenuOpen] = useState(false);
  const { currentUser, logout } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    // Check ML API health on mount
    fetch("http://localhost:8000/health")
      .then(() => setMlStatus("online"))
      .catch(() => setMlStatus("offline"));
  }, []);

  const handleLogout = async () => {
    try {
      await logout();
      navigate("/login");
    } catch (error) {
      console.error("Logout failed:", error);
    }
  };

  const handleMenuToggle = () => {
    setMenuOpen(!menuOpen);
    onMenuToggle();
  };

  // Get user display name or email prefix
  const getUserDisplayName = () => {
    if (currentUser?.displayName) return currentUser.displayName;
    if (currentUser?.email) return currentUser.email.split("@")[0];
    return "User";
  };

  const getInitial = () => {
    const name = getUserDisplayName();
    return name.charAt(0).toUpperCase();
  };

  return (
    <nav className="fixed top-0 w-full z-50 bg-gray-950/80 backdrop-blur-md border-b border-gray-800">
      <div className="flex items-center justify-between px-4 py-3">
        {/* Left side */}
        <div className="flex items-center gap-3">
          <button
            onClick={handleMenuToggle}
            className="text-gray-400 hover:text-white transition-colors p-2 hover:bg-gray-800 rounded-lg"
          >
            {menuOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
          <div className="text-xl font-bold text-blue-400">💊 RxShield</div>
        </div>

        {/* Right side */}
        <div className="flex items-center gap-3">
          {/* ML Status indicator */}
          <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-900 rounded-lg border border-gray-800">
            <span className="text-xs text-gray-400">ML API</span>
            <div
              className={`w-2 h-2 rounded-full ${
                mlStatus === "online"
                  ? "bg-green-400"
                  : mlStatus === "offline"
                    ? "bg-red-400"
                    : "bg-gray-400"
              }`}
            />
          </div>

          {/* User display */}
          <div className="flex items-center gap-2">
            <div className="bg-blue-600 w-8 h-8 rounded-full flex items-center justify-center text-white text-sm font-semibold">
              {getInitial()}
            </div>
            <span className="hidden sm:inline text-sm text-gray-300">
              {getUserDisplayName()}
            </span>
          </div>

          {/* Logout button */}
          <button
            onClick={handleLogout}
            className="text-gray-400 hover:text-red-400 transition-colors p-2 hover:bg-gray-800 rounded-lg"
            title="Logout"
          >
            <LogOut size={20} />
          </button>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
