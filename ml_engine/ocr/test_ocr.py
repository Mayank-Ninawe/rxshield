"""
Test script for OCR Pipeline
Tests TrOCR and Tesseract functionality
"""

from ocr_pipeline import (
    ocr_from_file,
    ocr_from_base64,
    run_ocr,
    clean_prescription_text
)
from PIL import Image, ImageDraw, ImageFont
import os
import base64


def test_1_synthetic_image_ocr():
    """Create a synthetic handwritten-style test image and run OCR."""
    print("\n" + "=" * 55)
    print("TEST 1 — Synthetic Image OCR")
    print("=" * 55)
    
    # Create a white PIL image (800x300 pixels, RGB, white background)
    img = Image.new("RGB", (800, 300), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    # Try to use a system font, fallback to default
    try:
        font = ImageFont.truetype("arial.ttf", 28)
        font_small = ImageFont.truetype("arial.ttf", 22)
    except Exception:
        try:
            # Try alternative Windows font path
            font = ImageFont.truetype("C:\\Windows\\Fonts\\arial.ttf", 28)
            font_small = ImageFont.truetype("C:\\Windows\\Fonts\\arial.ttf", 22)
        except Exception:
            font = ImageFont.load_default()
            font_small = font
    
    # Draw text on the image (dark blue ink color)
    ink_color = (20, 20, 120)
    
    draw.text((20, 40), "Rx: Metformin 500 mg twice daily x 30 days", fill=ink_color, font=font)
    draw.text((20, 90), "Tab Aspirin 75 mg once daily", fill=ink_color, font=font)
    draw.text((20, 140), "Atorvastatin 20 mg at night x 90 days", fill=ink_color, font=font)
    draw.text((20, 190), "Allergies: Penicillin", fill=ink_color, font=font_small)
    draw.text((20, 240), "Dr. ID: DOC001 | City Hospital, Nashik", fill=ink_color, font=font_small)
    
    # Save image
    output_path = "ocr/test_prescription.png"
    os.makedirs("ocr", exist_ok=True)
    img.save(output_path)
    print(f"✅ Test image created: {output_path}")
    
    # Run OCR on this image
    print("\nRunning OCR...")
    result = ocr_from_file(output_path, language="english")
    cleaned = clean_prescription_text(result['text'])
    
    # Print results
    print("=" * 55)
    print(f"OCR Engine : {result['engine']}")
    print(f"Language   : {result['language']}")
    print(f"Confidence : {result['confidence']}")
    print("\nRaw Text:")
    print(result['text'])
    print("-" * 55)
    print("Cleaned Text:")
    print(cleaned)
    print("=" * 55)
    
    return result


def test_2_base64_input():
    """Test base64 input."""
    print("\n" + "=" * 55)
    print("TEST 2 — Base64 Input")
    print("=" * 55)
    
    # Read the saved test image as base64
    image_path = "ocr/test_prescription.png"
    
    if not os.path.exists(image_path):
        print(f"❌ Test image not found: {image_path}")
        return None
    
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    
    result2 = ocr_from_base64(b64, language="english")
    
    if "error" in result2:
        print(f"❌ Base64 OCR error: {result2['error']}")
    else:
        print(f"✅ Base64 input test: {len(result2['text'])} chars extracted")
    
    return result2


def test_3_tesseract_availability():
    """Check Tesseract installation and language packs."""
    print("\n" + "=" * 55)
    print("TEST 3 — Tesseract Availability Check")
    print("=" * 55)
    
    try:
        import pytesseract
        langs = pytesseract.get_languages(config='')
        print(f"✅ Tesseract available. Languages: {langs}")
        
        if 'hin' in langs:
            print("✅ Hindi (hin) language pack installed")
        else:
            print("⚠️  Hindi not found. Add hin.traineddata to tessdata folder")
        
        if 'mar' in langs:
            print("✅ Marathi (mar) language pack installed")
        else:
            print("⚠️  Marathi not found. Add mar.traineddata to tessdata folder")
    
    except Exception as e:
        print(f"❌ Tesseract error: {e}")
        print("   Install Tesseract from: https://github.com/UB-Mannheim/tesseract/wiki")


def main():
    """Run all OCR tests."""
    print("\n" + "🔬" * 27)
    print("RxShield OCR Pipeline Test Suite")
    print("🔬" * 27)
    
    # Run all tests
    test_1_synthetic_image_ocr()
    test_2_base64_input()
    test_3_tesseract_availability()
    
    # Final message
    print("\n" + "=" * 55)
    print("✅ OCR Pipeline test complete!")
    print("=" * 55 + "\n")


if __name__ == "__main__":
    main()
