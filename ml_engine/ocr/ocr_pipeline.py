"""
OCR Pipeline for RxShield
Handles both English handwritten prescriptions (TrOCR) and Hindi/Marathi (Tesseract)

CRITICAL FIX: TrOCR is a single-line model. Feeding full prescription image = garbage output.
Solution: OpenCV line segmentation → TrOCR per line + Tesseract fallback.
"""

# ============================================================================
# SECTION 1 — Imports and config
# ============================================================================

import os
import sys
import base64
import re
import io
import platform
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
import torch
import cv2  # pip install opencv-python-headless

# Set tesseract path for Windows
if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = (
        r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    )

TROCR_MODEL_NAME = "microsoft/trocr-base-handwritten"

# Lazy loading globals
_trocr_processor = None
_trocr_model = None
_device = None


# ============================================================================
# SECTION 1.5 — TrOCR loader
# ============================================================================

def load_trocr():
    """Lazy load TrOCR model and processor."""
    global _trocr_processor, _trocr_model, _device
    if _trocr_processor is None:
        from transformers import TrOCRProcessor, VisionEncoderDecoderModel
        print("⏳ Loading TrOCR model...")
        _trocr_processor = TrOCRProcessor.from_pretrained(TROCR_MODEL_NAME)
        _trocr_model = VisionEncoderDecoderModel.from_pretrained(TROCR_MODEL_NAME)
        _trocr_model.eval()
        _device = "cuda" if torch.cuda.is_available() else "cpu"
        _trocr_model = _trocr_model.to(_device)
        print(f"✅ TrOCR loaded on {_device}")


# ============================================================================
# SECTION 2 — ADVANCED Image Preprocessing
# ============================================================================

def preprocess_for_ocr(image: Image.Image) -> np.ndarray:
    """
    Returns a preprocessed numpy array (grayscale, denoised, 
    high contrast) optimized for OCR.
    OPTIMIZED FOR SPEED - reduced upscaling and simplified denoising.
    """
    # Convert PIL → OpenCV BGR
    img_cv = cv2.cvtColor(np.array(image.convert('RGB')), cv2.COLOR_RGB2BGR)
    
    # Upscale if too small (min 800px wide - reduced from 1200 for speed)
    h, w = img_cv.shape[:2]
    if w < 800:
        scale = 800 / w
        img_cv = cv2.resize(img_cv, None, fx=scale, fy=scale, 
                            interpolation=cv2.INTER_LINEAR)  # INTER_LINEAR is faster than CUBIC
    
    # Convert to grayscale
    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
    
    # Simple bilateral filter (much faster than fastNlMeansDenoising)
    gray = cv2.bilateralFilter(gray, 5, 50, 50)
    
    # Adaptive thresholding (works better than global for varied lighting)
    thresh = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 31, 10
    )
    
    # Skip morphological operations and deskewing for speed
    # These only provide marginal improvements but add significant time
    
    return thresh  # numpy uint8 array


# ============================================================================
# SECTION 3 — LINE SEGMENTATION (THE KEY FIX)
# ============================================================================

def segment_lines(preprocessed_img: np.ndarray) -> list:
    """
    Detects horizontal text lines in the image using 
    horizontal projection profile.
    Returns list of PIL Image crops, one per line.
    """
    # Invert: text = white, background = black for projection
    inverted = cv2.bitwise_not(preprocessed_img)
    
    # Horizontal projection: sum pixels per row
    row_sums = np.sum(inverted, axis=1)
    
    # Find rows with text (above threshold)
    threshold = np.max(row_sums) * 0.05
    text_rows = row_sums > threshold
    
    # Find start/end of each text line block
    lines = []
    in_line = False
    start = 0
    padding = 8  # pixels of padding above/below each line
    
    for i, has_text in enumerate(text_rows):
        if has_text and not in_line:
            in_line = True
            start = max(0, i - padding)
        elif not has_text and in_line:
            in_line = False
            end = min(len(text_rows), i + padding)
            line_height = end - start
            
            # Skip very thin lines (likely noise, not text)
            if line_height > 10:
                crop = preprocessed_img[start:end, :]
                
                # Skip lines that are mostly white (empty)
                if np.mean(crop) < 250:
                    lines.append(Image.fromarray(crop))
    
    # Handle last line
    if in_line:
        crop = preprocessed_img[start:, :]
        if np.mean(crop) < 250:
            lines.append(Image.fromarray(crop))
    
    print(f"  📏 Detected {len(lines)} text lines")
    return lines


# ============================================================================
# SECTION 4 — TrOCR on single line (internal helper)
# ============================================================================

def _trocr_single_line(line_img: Image.Image) -> str:
    """Run TrOCR on one line image. Returns text string."""
    load_trocr()
    
    # TrOCR needs RGB PIL image
    if line_img.mode != 'RGB':
        line_img = line_img.convert('RGB')
    
    # Ensure minimum height for TrOCR (it expects ~384px)
    w, h = line_img.size
    if h < 32:
        return ""  # too thin, skip
    if h < 100:
        scale = 100 / h
        line_img = line_img.resize((int(w*scale), 100), Image.LANCZOS)
    
    try:
        pixel_values = _trocr_processor(
            images=line_img, return_tensors="pt"
        ).pixel_values.to(_device)
        
        with torch.no_grad():
            generated_ids = _trocr_model.generate(
                pixel_values, max_new_tokens=64)  # Reduced from 128 for speed
        
        text = _trocr_processor.batch_decode(
            generated_ids, skip_special_tokens=True)[0]
        return text.strip()
    except Exception as e:
        print(f"  TrOCR line error: {e}")
        return ""


# ============================================================================
# SECTION 5 — MAIN English OCR function (REWRITTEN)
# ============================================================================

def ocr_english(image: Image.Image) -> dict:
    """
    Multi-line English OCR using:
    1. OpenCV preprocessing + line segmentation
    2. TrOCR per line (best for handwritten)
    3. Tesseract fallback ONLY if TrOCR fails
    OPTIMIZED FOR SPEED - limits lines and runs Tesseract only on failure.
    """
    print("🔍 Running FAST multi-line OCR pipeline...")
    
    # Step 1: Preprocess
    preprocessed = preprocess_for_ocr(image)
    
    # Step 2: Segment into lines
    lines = segment_lines(preprocessed)
    
    # Limit to first 20 lines for speed (most prescriptions are < 20 lines)
    MAX_LINES = 20
    if len(lines) > MAX_LINES:
        print(f"  ⚡ Limiting to first {MAX_LINES} lines for speed")
        lines = lines[:MAX_LINES]
    
    trocr_text = ""
    if len(lines) > 0:
        # Step 3: TrOCR each line
        line_texts = []
        for i, line_img in enumerate(lines):
            text = _trocr_single_line(line_img)
            if text:
                print(f"  Line {i+1}: {text}")
                line_texts.append(text)
        
        trocr_text = "\n".join(line_texts)
    
    # Step 4: Tesseract ONLY if TrOCR failed or gave very poor results
    tesseract_text = ""
    trocr_score = len(trocr_text)
    
    # Only run Tesseract if TrOCR extracted < 20 chars (likely failed)
    if trocr_score < 20:
        print("  ⚠️ TrOCR gave poor results, trying Tesseract fallback...")
        try:
            # PSM 6 = assume uniform block of text (best for prescriptions)
            config = r"--oem 3 --psm 6 -c preserve_interword_spaces=1"
            pil_thresh = Image.fromarray(preprocessed)
            tesseract_text = pytesseract.image_to_string(
                pil_thresh, lang="eng", config=config).strip()
            print(f"  📄 Tesseract extracted {len(tesseract_text)} chars")
        except Exception as e:
            print(f"  Tesseract fallback error: {e}")
    else:
        print(f"  ✅ TrOCR successful ({trocr_score} chars), skipping Tesseract")
    
    # Step 5: Choose best result (simplified logic)
    if trocr_text and len(trocr_text) >= 20:
        final_text = trocr_text
        engine_used = "TrOCR (line-segmented)"
    elif tesseract_text:
        final_text = tesseract_text
        engine_used = "Tesseract (fallback)"
    else:
        final_text = trocr_text or ""
        engine_used = "TrOCR (partial)"
    
    return {
        "text": final_text,
        "engine": engine_used,
        "language": "english",
        "confidence": None,
        "lines_detected": len(lines)
    }


# ============================================================================
# SECTION 6 — Devanagari OCR (Hindi/Marathi via Tesseract)
# ============================================================================

def ocr_devanagari(image: Image.Image, language: str = "hin+mar") -> dict:
    """
    Run OCR on Hindi/Marathi prescriptions using Tesseract.
    
    Args:
        image: PIL Image object
        language: Tesseract language code (hin+mar, hin, mar)
    
    Returns:
        dict with keys: text, engine, language, confidence
    """
    preprocessed = preprocess_for_ocr(image)
    pil_thresh = Image.fromarray(preprocessed)
    custom_config = r"--oem 3 --psm 6"
    try:
        text = pytesseract.image_to_string(
            pil_thresh, lang=language, config=custom_config)
        data = pytesseract.image_to_data(
            pil_thresh, lang=language, config=custom_config,
            output_type=pytesseract.Output.DICT)
        confidences = [int(c) for c in data['conf'] 
                       if str(c).isdigit() and int(c) > 0]
        avg_conf = sum(confidences)/len(confidences) if confidences else 0
        return {
            "text": text.strip(),
            "engine": "Tesseract",
            "language": language,
            "confidence": round(avg_conf, 2)
        }
    except Exception as e:
        return {
            "text": "",
            "engine": "error",
            "language": language,
            "confidence": 0,
            "error": str(e)
        }


# ============================================================================
# SECTION 7 — Auto-detect language and run OCR
# ============================================================================

def detect_script(image: Image.Image) -> str:
    """
    Quick script detection using Tesseract OSD (Orientation Script Detection).
    
    Args:
        image: PIL Image object
    
    Returns:
        'devanagari' or 'latin'
    """
    try:
        osd = pytesseract.image_to_osd(image, output_type=pytesseract.Output.DICT)
        script = osd.get('script', 'Latin')
        return 'devanagari' if script in ['Devanagari', 'HAN'] else 'latin'
    except Exception:
        # Default to English on error
        return 'latin'


def run_ocr(image: Image.Image, language: str = "auto") -> dict:
    """
    Run OCR with automatic or specified language detection.
    
    Args:
        image: PIL Image object
        language: "auto", "english", "hindi", "marathi", or "devanagari"
    
    Returns:
        dict with OCR results
    """
    try:
        # Auto-detect language if needed
        if language == "auto":
            detected = detect_script(image)
            language = "devanagari" if detected == "devanagari" else "english"
        
        # Route to appropriate OCR engine
        if language in ["hindi", "marathi", "devanagari"]:
            if language == "devanagari":
                lang_code = "hin+mar"
            elif language == "hindi":
                lang_code = "hin"
            else:  # marathi
                lang_code = "mar"
            result = ocr_devanagari(image, lang_code)
        else:
            result = ocr_english(image)
        
        result["detected_language"] = language
        return result
    except Exception as e:
        return {
            "text": "",
            "engine": "error",
            "language": language,
            "confidence": 0,
            "detected_language": language,
            "error": str(e)
        }


# ============================================================================
# SECTION 8 — Base64 image input handler (for FastAPI)
# ============================================================================

def ocr_from_base64(image_b64: str, language: str = "auto") -> dict:
    """
    Run OCR on base64-encoded image.
    
    Args:
        image_b64: Base64-encoded image string (with or without data URI prefix)
        language: Target language for OCR
    
    Returns:
        dict with OCR results
    """
    try:
        # Strip data URI prefix if present
        if "base64," in image_b64:
            image_b64 = image_b64.split("base64,")[1]
        
        image_bytes = base64.b64decode(image_b64)
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        return run_ocr(image, language)
    except Exception as e:
        return {
            "text": "",
            "engine": "error",
            "language": language,
            "confidence": 0,
            "error": str(e)
        }


# ============================================================================
# SECTION 9 — File path input handler
# ============================================================================

def ocr_from_file(image_path: str, language: str = "auto") -> dict:
    """
    Run OCR on image file.
    
    Args:
        image_path: Path to image file
        language: Target language for OCR
    
    Returns:
        dict with OCR results
    """
    try:
        image = Image.open(image_path).convert("RGB")
        return run_ocr(image, language)
    except Exception as e:
        return {
            "text": "",
            "engine": "error",
            "language": language,
            "confidence": 0,
            "error": str(e)
        }


# ============================================================================
# SECTION 10 — Post-processing for prescription text
# ============================================================================

def clean_prescription_text(raw_text: str) -> str:
    """
    Cleans OCR output specifically for medical prescription text.
    Fixes common OCR errors in drug names and dosage notation.
    """
    if not raw_text:
        return ""
    
    text = raw_text
    
    # Remove OCR separator markers
    text = re.sub(r'---+', '\n', text)
    
    # Fix spaced numbers before units: "100 m g" → "100 mg"
    text = re.sub(r'(\d+)\s+m\s*g', r'\1 mg', text, flags=re.IGNORECASE)
    text = re.sub(r'(\d+)\s+m\s*l', r'\1 ml', text, flags=re.IGNORECASE)
    text = re.sub(r'(\d+)\s+m\s*c\s*g', r'\1 mcg', text, flags=re.IGNORECASE)
    
    # Fix digit-unit spacing: "100mg" → "100 mg"
    text = re.sub(r'(\d+)(mg|mcg|ml|units?|tabs?|caps?)', 
                  r'\1 \2', text, flags=re.IGNORECASE)
    
    # Normalize frequency abbreviations
    freq_map = {
        r'\bBD\b': 'twice daily',
        r'\bBID\b': 'twice daily',
        r'\bTID\b': 'three times daily',
        r'\bTTD\b': 'three times daily',
        r'\bTDD\b': 'three times daily',
        r'\bQID\b': 'four times daily',
        r'\bQD\b': 'once daily',
        r'\bOD\b': 'once daily',
        r'\bHS\b': 'at bedtime',
        r'\bPRN\b': 'as needed',
        r'\bSOS\b': 'if needed',
        r'\bStat\b': 'immediately',
        r'\bAC\b': 'before meals',
        r'\bPC\b': 'after meals',
    }
    for pattern, replacement in freq_map.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    # Fix common OCR character confusions in drug names
    ocr_fixes = {
        r'\bBeta1oc\b': 'Betaloc',
        r'\bMetf0rmin\b': 'Metformin',
        r'\bAsp1rin\b': 'Aspirin',
        r'\bAmox1cillin\b': 'Amoxicillin',
        r'\b0mg\b': '0 mg',
        r'\bl\s+tab\b': '1 tab',  # 'l' misread as 1
        r'\bI\s+tab\b': '1 tab',  # 'I' misread as 1
    }
    for pattern, replacement in ocr_fixes.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    # Clean up lines
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        line = line.strip()
        # Remove lines that are just punctuation/symbols/single chars
        if len(line) < 2:
            continue
        # Remove lines that are only special characters
        if re.match(r'^[^\w\d]+$', line):
            continue
        cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines)
