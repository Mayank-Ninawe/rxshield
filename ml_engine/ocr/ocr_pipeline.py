"""
OCR Pipeline for RxShield
Handles both English handwritten prescriptions (TrOCR) and Hindi/Marathi (Tesseract)
"""

# ============================================================================
# SECTION 1 — Imports and config
# ============================================================================

import os
import sys
import base64
import re
import numpy as np
from PIL import Image, ImageEnhance
import pytesseract
import torch
import io
import platform

# Set tesseract path for Windows
if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = (
        r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    )

TROCR_MODEL_NAME = "microsoft/trocr-base-handwritten"

# Lazy loading globals
_trocr_processor = None
_trocr_model = None


# ============================================================================
# SECTION 2 — TrOCR loader
# ============================================================================

def load_trocr():
    """Lazy load TrOCR model and processor."""
    global _trocr_processor, _trocr_model
    if _trocr_processor is None:
        from transformers import TrOCRProcessor, VisionEncoderDecoderModel
        print("⏳ Loading TrOCR model (first time ~500MB download)...")
        _trocr_processor = TrOCRProcessor.from_pretrained(TROCR_MODEL_NAME)
        _trocr_model = VisionEncoderDecoderModel.from_pretrained(TROCR_MODEL_NAME)
        _trocr_model.eval()
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _trocr_model = _trocr_model.to(device)
        print(f"✅ TrOCR loaded on {device}")


# ============================================================================
# SECTION 3 — Image preprocessing
# ============================================================================

def preprocess_image(image: Image.Image) -> Image.Image:
    """
    Preprocess image for OCR.
    - Convert to RGB
    - Resize if too large
    - Apply contrast enhancement
    """
    try:
        # Convert to RGB if not already
        if image.mode != "RGB":
            image = image.convert("RGB")
        
        # Resize if image width > 2000, scale down maintaining aspect ratio
        max_width = 2000
        if image.width > max_width:
            aspect_ratio = image.height / image.width
            new_width = max_width
            new_height = int(new_width * aspect_ratio)
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Apply light contrast enhancement
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.5)
        
        return image
    except Exception as e:
        print(f"Warning: Preprocessing error: {e}")
        return image


# ============================================================================
# SECTION 4 — English OCR via TrOCR
# ============================================================================

def ocr_english(image: Image.Image) -> dict:
    """
    Run OCR on English handwritten prescriptions using TrOCR.
    
    Args:
        image: PIL Image object
    
    Returns:
        dict with keys: text, engine, language, confidence
    """
    try:
        load_trocr()
        image = preprocess_image(image)
        
        device = next(_trocr_model.parameters()).device
        pixel_values = _trocr_processor(
            images=image, return_tensors="pt"
        ).pixel_values.to(device)
        
        with torch.no_grad():
            generated_ids = _trocr_model.generate(
                pixel_values, max_new_tokens=256
            )
        
        generated_text = _trocr_processor.batch_decode(
            generated_ids, skip_special_tokens=True
        )[0]
        
        return {
            "text": generated_text.strip(),
            "engine": "TrOCR",
            "language": "english",
            "confidence": None  # TrOCR doesn't give confidence score
        }
    except Exception as e:
        return {
            "text": "",
            "engine": "TrOCR",
            "language": "english",
            "confidence": 0,
            "error": str(e)
        }


# ============================================================================
# SECTION 5 — Hindi/Marathi OCR via Tesseract
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
    try:
        image = preprocess_image(image)
        
        # Tesseract config
        custom_config = r"--oem 3 --psm 6"
        
        # Extract text
        text = pytesseract.image_to_string(
            image, lang=language, config=custom_config
        )
        
        # Get confidence data
        data = pytesseract.image_to_data(
            image, lang=language, config=custom_config,
            output_type=pytesseract.Output.DICT
        )
        
        confidences = [
            int(c) for c in data['conf']
            if str(c).isdigit() and int(c) > 0
        ]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        return {
            "text": text.strip(),
            "engine": "Tesseract",
            "language": language,
            "confidence": round(avg_confidence, 2)
        }
    except Exception as e:
        return {
            "text": "",
            "engine": "Tesseract",
            "language": language,
            "confidence": 0,
            "error": str(e)
        }


# ============================================================================
# SECTION 6 — Auto-detect language and run OCR
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
# SECTION 7 — Base64 image input handler (for FastAPI)
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
# SECTION 8 — File path input handler
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
# SECTION 9 — Post-processing for prescription text
# ============================================================================

def clean_prescription_text(raw_text: str) -> str:
    """
    Clean and normalize OCR output for prescription text.
    
    Args:
        raw_text: Raw OCR text output
    
    Returns:
        Cleaned text string
    """
    try:
        text = raw_text
        
        # Fix common OCR errors in drug names
        replacements = {
            "0mg": "0 mg",
            "5mg": "5 mg",
            "0mcg": "0 mcg",
            "\n": " ",
            "  ": " "
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        # Apply regex for unit spacing: 10mg -> 10 mg
        text = re.sub(r'(\d+)(mg|mcg|ml|units)', r'\1 \2', text)
        
        # Strip leading/trailing whitespace from each line
        lines = [line.strip() for line in text.split('\n')]
        
        # Remove empty lines
        lines = [line for line in lines if line]
        
        # Join and clean up
        text = '\n'.join(lines)
        
        # Remove excessive whitespace
        text = re.sub(r' +', ' ', text)
        text = text.strip()
        
        return text
    except Exception as e:
        print(f"Warning: Text cleaning error: {e}")
        return raw_text
