const LoadingSpinner = ({ size = "md", text = "", fullscreen = false }) => {
  const sizeMap = {
    sm: 16,
    md: 32,
    lg: 48,
  };

  const spinnerSize = sizeMap[size] || sizeMap.md;

  const spinner = (
    <div className="flex flex-col items-center justify-center gap-3">
      <div
        className="rounded-full border-4 border-gray-700 border-t-blue-500 animate-spin"
        style={{ width: spinnerSize, height: spinnerSize }}
      />
      {text && <p className="text-gray-400 text-sm">{text}</p>}
    </div>
  );

  if (fullscreen) {
    return (
      <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
        {spinner}
      </div>
    );
  }

  return spinner;
};

export default LoadingSpinner;
