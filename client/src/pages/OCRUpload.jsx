import { useState, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "react-hot-toast";
import {
  Upload,
  FileImage,
  Languages,
  CheckCircle,
  AlertTriangle,
  XCircle,
  Loader2,
  ChevronRight,
  FlaskConical,
  Pill,
  User,
  RefreshCw,
  X,
  Scan,
} from "lucide-react";
import { ocrApi, patientApi } from "../utils/api";
import RiskReport from "../components/ui/RiskReport";
import { useTheme } from "../context/ThemeContext";
import Layout from "../components/Layout";

const LANGUAGES = [
  { value: "english", label: "🇬🇧 English", flag: "🇬🇧" },
  { value: "hindi", label: "🇮🇳 Hindi (हिंदी)", flag: "🇮🇳" },
  { value: "marathi", label: "🇮🇳 Marathi (मराठी)", flag: "🇮🇳" },
  { value: "hindi+marathi", label: "🇮🇳 Hindi + Marathi", flag: "🇮🇳" },
];

const OCRUpload = () => {
  const [uploadedFile, setUploadedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [language, setLanguage] = useState("english");
  const [step, setStep] = useState("idle");
  // idle → uploading → extracting → analyzing → done → error
  const [ocrResult, setOcrResult] = useState(null);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [patientId, setPatientId] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef(null);
  const { isDark } = useTheme();
  const navigate = useNavigate();

  // Handle file selection
  const handleFile = useCallback((file) => {
    if (!file) return;

    const allowed = ["image/jpeg", "image/png", "image/webp", "image/jpg"];
    if (!allowed.includes(file.type)) {
      toast.error("Only JPG, PNG, WEBP images allowed");
      return;
    }

    if (file.size > 5 * 1024 * 1024) {
      toast.error("File size must be under 5MB");
      return;
    }

    setUploadedFile(file);
    setPreviewUrl(URL.createObjectURL(file));
    setOcrResult(null);
    setAnalysisResult(null);
    setStep("idle");
  }, []);

  // Drag and drop handlers
  const handleDragOver = (e) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = () => {
    setDragOver(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    handleFile(e.dataTransfer.files[0]);
  };

  // Clear uploaded file
  const clearFile = () => {
    setUploadedFile(null);
    setPreviewUrl(null);
    setOcrResult(null);
    setAnalysisResult(null);
    setStep("idle");
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  // Main analyze function - combines OCR + Analysis
  const handleAnalyze = async () => {
    if (!uploadedFile) {
      toast.error("Please select a prescription image first");
      return;
    }

    setStep("extracting");
    setOcrResult(null);
    setAnalysisResult(null);

    try {
      const formData = new FormData();
      formData.append("prescription_image", uploadedFile);
      formData.append("language", language);

      // Add patient data if patientId was entered
      if (patientId) {
        try {
          const patRes = await patientApi.getById(patientId);
          formData.append("patientData", JSON.stringify(patRes.data));
        } catch {
          toast("Patient not found, analyzing without patient data", {
            icon: "ℹ️",
          });
        }
      }

      setStep("analyzing");

      // SINGLE CALL — OCR + Analyze together
      const res = await ocrApi.analyzeImage(formData);
      const data = res.data;

      setOcrResult({
        extractedText: data.extractedText,
        structuredDrugs: data.structuredDrugs || [],
        patientInfo: data.patientInfo,
        engine: data.engine,
        charCount: data.charCount,
      });

      if (data.analysis) {
        setAnalysisResult(data.analysis);
      }

      setStep("done");

      if (!data.ocrSuccess) {
        toast.error("No drugs detected in image. Try a clearer photo.");
        return;
      }

      const errCount = data.analysis?.errors?.length || 0;
      if (errCount === 0) {
        toast.success("✅ Prescription is SAFE — no issues found!");
      } else {
        toast.error(`⚠️ ${errCount} issue(s) found! Review the report below.`, {
          duration: 5000,
        });
      }
    } catch (err) {
      setStep("error");
      const msg = err.response?.data?.error || err.message || "Analysis failed";
      toast.error(`❌ ${msg}`);
    }
  };

  // Reset and start over
  const handleReset = () => {
    clearFile();
    setPatientId("");
  };

  // Step Progress Component
  const StepProgress = () => {
    const steps = [
      { key: "extracting", label: "Extracting Text", icon: FileImage },
      { key: "analyzing", label: "Analyzing Drugs", icon: FlaskConical },
      { key: "done", label: "Report Ready", icon: CheckCircle },
    ];
    const currentIdx = steps.findIndex((s) => s.key === step);

    return (
      <div className="flex items-center justify-center gap-2 my-6">
        {steps.map((s, i) => {
          const Icon = s.icon;
          const isActive = s.key === step;
          const isDone = currentIdx > i;
          return (
            <div key={s.key} className="flex items-center gap-2">
              <div
                className={`flex items-center gap-2 px-4 py-2 rounded-full 
                             text-sm font-medium transition-all duration-300 
                ${
                  isDone
                    ? "bg-green-500/20 text-green-400 border border-green-500/40"
                    : isActive
                      ? "bg-blue-500/20 text-blue-400 border border-blue-500/40 animate-pulse"
                      : "bg-gray-800/50 text-gray-500 border border-gray-700/30"
                }`}
              >
                {isActive && !isDone ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : isDone ? (
                  <CheckCircle size={14} />
                ) : (
                  <Icon size={14} />
                )}
                {s.label}
              </div>
              {i < steps.length - 1 && (
                <ChevronRight size={16} className="text-gray-600" />
              )}
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <Layout>
      <div className="max-w-7xl mx-auto px-4 py-6">
        {/* HEADER */}
        <div className="mb-6">
          <div className="flex items-center gap-3 mb-2">
            <Scan className="text-purple-400" size={32} />
            <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
              OCR Prescription Scanner
            </h1>
          </div>
          <p className="text-gray-600 dark:text-gray-400">
            Upload a prescription image — AI extracts and analyzes in seconds
          </p>
        </div>

        {/* STEP PROGRESS (show when processing) */}
        {["extracting", "analyzing", "done"].includes(step) && <StepProgress />}

        {/* TWO COLUMN LAYOUT */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* LEFT COLUMN — Upload Area */}
          <div
            className="bg-gray-50 dark:bg-gray-900 border border-gray-200 
                       dark:border-gray-800 rounded-2xl p-6 h-fit"
          >
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <FileImage className="text-blue-400" size={20} />
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                  Upload Prescription
                </h2>
              </div>
              {uploadedFile && (
                <button
                  onClick={clearFile}
                  className="text-gray-500 hover:text-red-500 transition-colors"
                >
                  <X size={18} />
                </button>
              )}
            </div>

            {/* Drop Zone or Preview */}
            {!uploadedFile ? (
              <>
                <div
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current?.click()}
                  className={`border-2 border-dashed rounded-xl p-10 text-center 
                             cursor-pointer transition-all mt-4 ${
                               dragOver
                                 ? "border-blue-500 bg-blue-900/20"
                                 : "border-gray-300 dark:border-gray-700 hover:border-gray-400 " +
                                   "dark:hover:border-gray-600 hover:bg-gray-100 " +
                                   "dark:hover:bg-gray-800/50"
                             }`}
                >
                  <Upload
                    size={48}
                    className="mx-auto text-gray-400 dark:text-gray-600 mb-3"
                  />
                  <p className="text-gray-900 dark:text-white font-medium">
                    Drop prescription image here
                  </p>
                  <p className="text-gray-500 text-sm mt-1">
                    or click to browse
                  </p>
                  <p className="text-gray-500 dark:text-gray-600 text-xs mt-3">
                    JPG, PNG, WEBP • Max 5MB
                  </p>
                </div>

                {/* Handwritten Prescription Tips */}
                <div className="mt-4 bg-blue-50 dark:bg-blue-900/10 border border-blue-200 dark:border-blue-800/30 rounded-lg p-3">
                  <p className="text-xs font-medium text-blue-800 dark:text-blue-300 mb-2">
                    ✨ Tips for handwritten prescriptions:
                  </p>
                  <ul className="text-xs text-blue-700 dark:text-blue-400 space-y-1">
                    <li>📸 Take photos in bright, even lighting</li>
                    <li>🎯 Keep handwriting in focus and avoid blur</li>
                    <li>
                      📐 Capture the entire prescription (don't cut edges)
                    </li>
                    <li>🔆 Avoid shadows or glare on the paper</li>
                  </ul>
                </div>

                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  onChange={(e) => handleFile(e.target.files[0])}
                  className="hidden"
                />
              </>
            ) : (
              <>
                {/* Image Preview */}
                <div
                  className="relative mt-4 rounded-xl overflow-hidden border 
                             border-gray-300 dark:border-gray-700"
                >
                  <img
                    src={previewUrl}
                    alt="prescription"
                    className="w-full max-h-80 object-contain bg-white dark:bg-gray-800"
                  />
                </div>

                {/* Language Selector */}
                <div className="mt-4">
                  <label
                    className="block text-sm font-medium text-gray-600 
                               dark:text-gray-400 mb-2"
                  >
                    🌐 Prescription Language
                  </label>
                  <div className="grid grid-cols-2 gap-2">
                    {LANGUAGES.map((lang) => (
                      <button
                        key={lang.value}
                        onClick={() => setLanguage(lang.value)}
                        className={`py-2.5 px-3 rounded-xl text-sm font-medium 
                                   border transition-all text-left ${
                                     language === lang.value
                                       ? "bg-blue-600/20 border-blue-500 text-blue-400"
                                       : "bg-gray-100 dark:bg-gray-800/50 " +
                                         "border-gray-200 dark:border-gray-700/50 " +
                                         "text-gray-600 dark:text-gray-400 " +
                                         "hover:border-gray-400 dark:hover:border-gray-500"
                                   }`}
                      >
                        {lang.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Patient ID Input (Optional) */}
                <div className="mt-4">
                  <label
                    className="block text-sm font-medium text-gray-600 
                               dark:text-gray-400 mb-2"
                  >
                    👤 Patient ID (Optional)
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. DEMO-001"
                    value={patientId}
                    onChange={(e) => setPatientId(e.target.value)}
                    className="w-full bg-gray-100 dark:bg-gray-800 
                               border border-gray-300 dark:border-gray-700 
                               rounded-xl px-4 py-3 text-sm 
                               text-gray-900 dark:text-white 
                               placeholder-gray-500 focus:outline-none 
                               focus:border-blue-500"
                  />
                </div>

                {/* Analyze Button */}
                <button
                  onClick={handleAnalyze}
                  disabled={
                    !uploadedFile ||
                    step === "extracting" ||
                    step === "analyzing"
                  }
                  className="w-full mt-5 py-3.5 rounded-xl font-semibold text-base 
                             bg-gradient-to-r from-blue-600 to-blue-500 
                             hover:from-blue-500 hover:to-blue-400 
                             disabled:opacity-50 disabled:cursor-not-allowed 
                             text-white transition-all duration-200 flex items-center 
                             justify-center gap-2"
                >
                  {step === "extracting" || step === "analyzing" ? (
                    <>
                      <Loader2 size={18} className="animate-spin" />{" "}
                      Processing...
                    </>
                  ) : (
                    <>
                      <FlaskConical size={18} /> Extract & Analyze
                    </>
                  )}
                </button>
              </>
            )}
          </div>

          {/* RIGHT COLUMN — Results */}
          <div className="space-y-4">
            {/* Show extracted text if available but no drugs found */}
            {ocrResult && !ocrResult.structuredDrugs?.length && (
              <div
                className="bg-yellow-50 dark:bg-yellow-900/20 
                           border border-yellow-200 dark:border-yellow-800/50 
                           rounded-xl p-4"
              >
                <div className="flex items-center gap-2 mb-3">
                  <AlertTriangle
                    className="text-yellow-600 dark:text-yellow-500"
                    size={20}
                  />
                  <h3 className="font-semibold text-yellow-900 dark:text-yellow-200">
                    Text Extracted, But No Drugs Detected
                  </h3>
                </div>
                <p className="text-sm text-yellow-800 dark:text-yellow-300 mb-3">
                  The OCR successfully extracted text from the image, but
                  couldn't identify any drug/medicine names. This might happen
                  if:
                </p>
                <ul className="text-sm text-yellow-800 dark:text-yellow-300 mb-3 ml-4 list-disc space-y-1">
                  <li>
                    The document is a lab report, medical exam form, or other
                    non-prescription document
                  </li>
                  <li>
                    Handwritten drug names are extremely unclear or illegible
                    (even with AI enhancement)
                  </li>
                  <li>
                    The image contains only patient information without
                    prescription details
                  </li>
                  <li>
                    The text is in a language/script where drug names appear
                    differently
                  </li>
                  <li>Image quality is too low or text is too blurry/faded</li>
                </ul>
                {ocrResult.extractedText && (
                  <div className="mt-3">
                    <label className="text-xs font-medium text-yellow-700 dark:text-yellow-400 mb-1 block">
                      Extracted Text ({ocrResult.charCount} characters):
                    </label>
                    <div className="bg-white dark:bg-gray-800/40 rounded-lg p-3 border border-yellow-200 dark:border-yellow-700/30 max-h-64 overflow-y-auto">
                      <pre className="text-xs text-gray-700 dark:text-gray-300 whitespace-pre-wrap font-mono">
                        {ocrResult.extractedText}
                      </pre>
                    </div>
                  </div>
                )}
                <div className="mt-3 p-2 bg-yellow-100 dark:bg-yellow-900/30 rounded-lg">
                  <p className="text-xs text-yellow-800 dark:text-yellow-300 font-medium mb-2">
                    💡 Tips for better handwritten prescription recognition:
                  </p>
                  <ul className="text-xs text-yellow-700 dark:text-yellow-400 ml-4 list-disc space-y-1">
                    <li>
                      Ensure the image is of an actual prescription with drug
                      names (not just forms or lab reports)
                    </li>
                    <li>
                      Take photos in good lighting - avoid shadows on
                      handwritten text
                    </li>
                    <li>
                      Hold camera steady and ensure handwriting is in focus
                    </li>
                    <li>
                      For very messy handwriting, try taking a clearer photo or
                      retake with better lighting
                    </li>
                    <li>
                      If text is in Hindi/Marathi, select the appropriate
                      language option
                    </li>
                    <li>
                      Ensure entire prescription is visible (not cut off at
                      edges)
                    </li>
                  </ul>
                </div>
              </div>
            )}

            {/* Extracted Drugs Display */}
            {ocrResult?.structuredDrugs?.length > 0 && (
              <div
                className="bg-gray-50 dark:bg-gray-900/60 
                           border border-gray-200 dark:border-gray-800/50 
                           rounded-xl p-4"
              >
                <p
                  className="text-sm font-semibold text-gray-700 dark:text-gray-300 
                             mb-3 flex items-center gap-2"
                >
                  <Pill size={15} />
                  Extracted Drugs ({ocrResult.structuredDrugs.length})
                  <span className="ml-auto text-xs text-blue-400">
                    via {ocrResult.engine}
                  </span>
                </p>
                <div className="space-y-2">
                  {ocrResult.structuredDrugs.map((drug, i) => (
                    <div
                      key={i}
                      className="flex items-start justify-between 
                                 bg-white dark:bg-gray-800/40 
                                 rounded-lg px-3 py-2.5 border 
                                 border-gray-200 dark:border-gray-700/30"
                    >
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span
                            className="text-gray-900 dark:text-white 
                                       font-semibold text-sm"
                          >
                            💊 {drug.name}
                          </span>
                          {/* Show OCR correction badge if name was corrected */}
                          {drug.ocr_name &&
                            drug.ocr_name.toLowerCase() !==
                              drug.name.toLowerCase() && (
                              <span
                                className="text-xs bg-yellow-900/40 
                                         dark:bg-yellow-900/40 
                                         text-yellow-700 dark:text-yellow-400
                                         px-2 py-0.5 rounded-full border
                                         border-yellow-700/40 dark:border-yellow-700/40"
                                title={`OCR read: "${drug.ocr_name}"`}
                              >
                                ✏️ corrected
                              </span>
                            )}
                          {/* Confidence badge */}
                          {drug.confidence && drug.confidence !== "HIGH" && (
                            <span
                              className={`text-xs px-2 py-0.5 rounded-full border
                                ${
                                  drug.confidence === "MEDIUM"
                                    ? "bg-orange-900/40 dark:bg-orange-900/40 text-orange-700 dark:text-orange-400 border-orange-700/40 dark:border-orange-700/40"
                                    : "bg-red-900/40 dark:bg-red-900/40 text-red-700 dark:text-red-400 border-red-700/40 dark:border-red-700/40"
                                }`}
                            >
                              {drug.confidence} conf.
                            </span>
                          )}
                        </div>
                        {/* OCR original name tooltip */}
                        {drug.ocr_name &&
                          drug.ocr_name.toLowerCase() !==
                            drug.name.toLowerCase() && (
                            <p className="text-xs text-gray-500 mt-0.5">
                              OCR read: "{drug.ocr_name}"
                            </p>
                          )}
                        <div className="flex flex-wrap gap-1.5 mt-1">
                          {drug.dose && (
                            <span
                              className="text-xs bg-blue-100 dark:bg-blue-900/40 
                                         text-blue-700 dark:text-blue-300 
                                         px-2 py-0.5 rounded-full border 
                                         border-blue-200 dark:border-blue-700/40"
                            >
                              {drug.dose}
                            </span>
                          )}
                          {drug.frequency && (
                            <span
                              className="text-xs bg-purple-100 dark:bg-purple-900/40 
                                         text-purple-700 dark:text-purple-300 
                                         px-2 py-0.5 rounded-full border 
                                         border-purple-200 dark:border-purple-700/40"
                            >
                              {drug.frequency}
                            </span>
                          )}
                          {drug.duration && (
                            <span
                              className="text-xs bg-gray-200 dark:bg-gray-700/60 
                                         text-gray-700 dark:text-gray-300 
                                         px-2 py-0.5 rounded-full"
                            >
                              {drug.duration}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Analysis Result - Full Risk Report */}
            {analysisResult && (
              <RiskReport result={analysisResult} onReset={handleReset} />
            )}

            {/* Empty State */}
            {!ocrResult && step === "idle" && (
              <div
                className="bg-gray-50 dark:bg-gray-900/60 
                           border border-gray-200 dark:border-gray-800/50 
                           rounded-xl p-12 text-center"
              >
                <FlaskConical
                  size={48}
                  className="mx-auto text-gray-400 dark:text-gray-600 mb-3"
                />
                <p className="text-gray-600 dark:text-gray-400 font-medium">
                  Upload a prescription to begin analysis
                </p>
                <p className="text-gray-500 dark:text-gray-500 text-sm mt-2">
                  AI will extract drugs and check for errors automatically
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default OCRUpload;
