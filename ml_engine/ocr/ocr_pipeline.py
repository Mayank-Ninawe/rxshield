"""
OCR Pipeline for RxShield
Primary: Gemini Vision API (fast, accurate, cloud-based)
Fallback: Tesseract (when Gemini fails or no API key)

Old approach (TrOCR + line segmentation) was too slow and caused timeouts.
New approach: Gemini Vision API delivers both OCR AND structured extraction in 2-3 seconds.
"""

# ============================================================================
# SECTION 1 — Imports and Configuration
# ============================================================================

import os
import base64
import re
import io
import platform
import json
import numpy as np
from difflib import get_close_matches, SequenceMatcher
import google.generativeai as genai
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
from dotenv import load_dotenv

load_dotenv()

# Set Tesseract path for Windows
if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = (
        r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    )

# Configure Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

GEMINI_MODEL = "gemini-2.0-flash-exp"
_gemini_model = None

# Known drug names database (for fuzzy matching)
KNOWN_DRUG_NAMES = [
    'Metformin', 'Aspirin', 'Warfarin', 'Amoxicillin', 'Atorvastatin',
    'Amlodipine', 'Lisinopril', 'Metoprolol', 'Betaloc', 'Beteloc', 'Atenolol', 'Digoxin',
    'Furosemide', 'Tramadol', 'Codeine', 'Morphine', 'Ibuprofen', 'Diclofenac',
    'Paracetamol', 'Acetaminophen', 'Omeprazole', 'Pantoprazole', 'Ciprofloxacin',
    'Azithromycin', 'Clarithromycin', 'Ceftriaxone', 'Cephalexin',
    'Simvastatin', 'Rosuvastatin', 'Carbamazepine', 'Spironolactone',
    'Verapamil', 'Diltiazem', 'Cimetidine', 'Ranitidine', 'Famotidine',
    'Dorzolamide', 'Dorzolamidum', 'Oxprenolol', 'Oxprelol', 'Telmisartan', 'Losartan',
    'Glimepiride', 'Sitagliptin', 'Levothyroxine', 'Sertraline', 'Fluoxetine',
    'Prednisolone', 'Dexamethasone', 'Salbutamol', 'Theophylline', 'Ramipril',
    'Cetirizine', 'Naproxen', 'Ketorolac', 'Insulin', 'Gabapentin', 'Pregabalin',
    'Phenytoin', 'Valproate', 'Clonazepam', 'Alprazolam', 'Diazepam',
    'Metronidazole', 'Clindamycin', 'Doxycycline', 'Levofloxacin',
    'Hydrochlorothiazide', 'Enalapril', 'Bisoprolol', 'Propranolol',
    'Esomeprazole', 'Lansoprazole', 'Rabeprazole', 'Tamsulosin', 'Finasteride',
    'Sildenafil', 'Tadalafil', 'Montelukast', 'Loratadine', 'Fexofenadine',
    'Amitriptyline', 'Duloxetine', 'Mirtazapine', 'Risperidone', 'Quetiapine',
    'Olanzapine', 'Haloperidol', 'Chlorpromazine', 'Domperidone', 'Ondansetron',
    'Calcium', 'Vitamin', 'Folic', 'Iron', 'Zinc', 'Magnesium'
]

# Common drug names regex pattern (for exact matching fallback)
COMMON_DRUGS_PATTERN = re.compile(
    r'\b(Metformin|Aspirin|Warfarin|Amoxicillin|Atorvastatin|'
    r'Amlodipine|Lisinopril|Metoprolol|Betaloc|Beteloc|Beteloe|Atenolol|Digoxin|'
    r'Furosemide|Tramadol|Codeine|Morphine|Ibuprofen|Diclofenac|'
    r'Paracetamol|Acetaminophen|Omeprazole|Pantoprazole|Ciprofloxacin|'
    r'Azithromycin|Clarithromycin|Ceftriaxone|Cephalexin|'
    r'Simvastatin|Rosuvastatin|Carbamazepine|Spironolactone|'
    r'Verapamil|Diltiazem|Cimetidine|Ranitidine|Famotidine|'
    r'Dorzolamide|Dorzolamidum|Oxprenolol|Oxprelol|Telmisartan|Losartan|'
    r'Glimepiride|Sitagliptin|Levothyroxine|Sertraline|Fluoxetine|'
    r'Prednisolone|Dexamethasone|Salbutamol|Theophylline|Ramipril|'
    r'Cetirizine|Naproxen|Ketorolac|Insulin|Gabapentin|Pregabalin|'
    r'Phenytoin|Valproate|Clonazepam|Alprazolam|Diazepam|'
    r'Metronidazole|Clindamycin|Doxycycline|Levofloxacin|'
    r'Hydrochlorothiazide|Enalapril|Bisoprolol|Propranolol|'
    r'Esomeprazole|Lansoprazole|Rabeprazole|Tamsulosin|Finasteride|'
    r'Sildenafil|Tadalafil|Montelukast|Loratadine|Fexofenadine|'
    r'Amitriptyline|Duloxetine|Mirtazapine|Risperidone|Quetiapine|'
    r'Olanzapine|Haloperidol|Chlorpromazine|Domperidone|Ondansetron|'
    r'Calcium|Vitamin|Folic|Iron|Zinc|Magnesium)\b',
    re.IGNORECASE
)


def fuzzy_match_drugs(text: str, cutoff: float = 0.75) -> list:
    """
    Extract drug names using fuzzy string matching.
    Handles OCR errors and misspellings like 'Beteloe' -> 'Betaloc'
    
    Args:
        text: Text to search for drug names
        cutoff: Similarity threshold (0-1), default 0.75 means 75% similar
    
    Returns:
        List of [detected_word, corrected_drug_name, similarity_score] tuples
    """
    if not text:
        return []
    
    # Extract potential drug words (capitalized words 4+ chars, or words before dosage)
    # Look for patterns like "Beteloe 100mg" or "Dorzolamidum 10"
    potential_drugs = []
    
    # Pattern 1: Capitalized words followed by dosage
    pattern1 = re.finditer(r'\b([A-Z][a-z]{3,}[a-z]*)\s*\d+\s*(mg|mcg|ml|gm|g|units?|tabs?|caps?)', text, re.IGNORECASE)
    for match in pattern1:
        potential_drugs.append(match.group(1))
    
    # Pattern 2: Any capitalized word 5+ letters (likely drug name)
    pattern2 = re.finditer(r'\b([A-Z][a-z]{4,})\b', text)
    for match in pattern2:
        word = match.group(1)
        # Skip common non-drug words
        if word.lower() not in ['street', 'centre', 'center', 'medical', 'hospital', 
                                  'clinic', 'doctor', 'patient', 'prescription', 'label',
                                  'refill', 'signature', 'address', 'riverside']:
            potential_drugs.append(word)
    
    # Remove duplicates while preserving order
    potential_drugs = list(dict.fromkeys(potential_drugs))
    
    # Fuzzy match against known drug database
    matched_drugs = []
    seen_correct_names = set()
    
    for word in potential_drugs:
        # Try exact match first (case-insensitive)
        for known_drug in KNOWN_DRUG_NAMES:
            if word.lower() == known_drug.lower():
                if known_drug not in seen_correct_names:
                    matched_drugs.append((word, known_drug, 1.0))
                    seen_correct_names.add(known_drug)
                break
        else:
            # Fuzzy match
            matches = get_close_matches(word, KNOWN_DRUG_NAMES, n=1, cutoff=cutoff)
            if matches:
                correct_name = matches[0]
                similarity = SequenceMatcher(None, word.lower(), correct_name.lower()).ratio()
                if correct_name not in seen_correct_names:
                    matched_drugs.append((word, correct_name, similarity))
                    seen_correct_names.add(correct_name)
    
    return matched_drugs


def extract_drugs_with_regex(text: str) -> list:
    """
    Fallback drug name extraction using regex.
    Returns list of unique drug names found in text.
    """
    if not text:
        return []
    matches = COMMON_DRUGS_PATTERN.finditer(text)
    # Use dict to preserve order while removing duplicates (case-insensitive)
    seen = {}
    for match in matches:
        drug = match.group(0)
        drug_lower = drug.lower()
        if drug_lower not in seen:
            seen[drug_lower] = drug.capitalize()
    return list(seen.values())


# ============================================================================
# SECTION 2 — Gemini Model Loader (Lazy)
# ============================================================================

def load_gemini():
    """Lazy load Gemini model."""
    global _gemini_model
    if _gemini_model is None:
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY not found in .env")
        _gemini_model = genai.GenerativeModel(GEMINI_MODEL)
        print(f"✅ Gemini {GEMINI_MODEL} loaded for OCR")
    return _gemini_model


# ============================================================================
# SECTION 2.5 — Image Preprocessing for Handwriting
# ============================================================================

def preprocess_for_handwriting(image: Image.Image) -> Image.Image:
    """
    Enhance image to improve handwritten text recognition.
    Applies contrast enhancement, sharpening, and noise reduction.
    
    Args:
        image: PIL Image object
    
    Returns:
        Enhanced PIL Image object
    """
    try:
        # Convert to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Increase contrast to make handwriting more visible
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.8)  # Increase contrast by 80%
        
        # Increase sharpness to make edges clearer
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(2.0)  # Double sharpness
        
        # Slight brightness adjustment
        enhancer = ImageEnhance.Brightness(image)
        image = enhancer.enhance(1.1)  # 10% brighter
        
        # Apply light denoising (removes artifacts while preserving text)
        image = image.filter(ImageFilter.MedianFilter(size=3))
        
        # Sharpen again after denoising
        image = image.filter(ImageFilter.SHARPEN)
        
        return image
    except Exception as e:
        print(f"  ⚠️ Preprocessing failed: {e}, using original image")
        return image


# ============================================================================
# SECTION 2.7 — Drug Resolution with Gemini (Clinical Context)
# ============================================================================

def resolve_drugs_from_text(raw_ocr_text: str) -> list:
    """
    Takes raw OCR text (possibly with misspellings) and uses Gemini
    to identify ALL drug names using clinical context.
    Returns a normalized list of drugs with correct spellings.
    This is the KEY fix — handles any level of OCR distortion.
    """
    if not raw_ocr_text or len(raw_ocr_text.strip()) < 5:
        return []
    
    model = load_gemini()
    
    prompt = f"""You are a clinical pharmacist and medical OCR expert.
Below is text extracted from a handwritten medical prescription using OCR.
The OCR may have introduced errors, misspellings, and garbled characters.

YOUR TASK: Identify every drug/medicine name in this text, even if badly 
misspelled, and return their CORRECT standard pharmaceutical names.

Use clinical context clues:
- Numbers followed by mg/mcg/ml = doses → the word before it is a drug name
- Words like BID, TID, OD, BD, QD, twice daily = frequency → word before is a drug
- "Rx" symbol = prescription → items listed below are drugs
- Brand names, generic names, and common misspellings of both

OCR TEXT TO ANALYZE:
\"\"\"
{raw_ocr_text}
\"\"\"

Return ONLY a valid JSON array. No explanation. No markdown.
Each object must have exactly these fields:

[
  {{
    "ocr_name": "name exactly as it appeared in OCR text",
    "correct_name": "correct standard drug name (generic preferred)",
    "brand_name": "common brand name if applicable or null",
    "dose": "dose with unit e.g. 100mg — extracted from OCR context",
    "frequency": "frequency as written e.g. BID, twice daily, OD, TID",
    "confidence": "HIGH or MEDIUM or LOW based on how certain you are",
    "reasoning": "brief note on how you identified this drug"
  }}
]

Rules:
- If no drugs found, return empty array []
- Include ALL drugs, even if confidence is LOW
- For dose: always include the unit (mg, mcg, ml, units)
- If dose unclear from OCR, put null
- correct_name should be the INN (generic) name
- Do NOT include vitamins, minerals unless clearly prescribed therapeutically
- Return ONLY the JSON array, nothing else"""

    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                max_output_tokens=2048
            )
        )
        
        raw = response.text.strip()
        
        # Clean markdown
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        
        drugs = json.loads(raw)
        print(f"  ✅ Gemini resolved {len(drugs)} drugs from OCR text")
        for d in drugs:
            print(f"     '{d['ocr_name']}' → '{d['correct_name']}' "
                  f"({d['dose']}, {d['frequency']}) [{d['confidence']}]")
        return drugs
        
    except Exception as e:
        print(f"  ⚠️ Drug resolution error: {e}")
        return []


# ============================================================================
# SECTION 3 — Gemini Vision OCR (PRIMARY ENGINE)
# ============================================================================

def ocr_with_gemini(image: Image.Image, language: str = "auto") -> dict:
    """
    Uses Gemini Vision to extract prescription text from image.
    Returns both raw text AND structured drug data in one API call.
    
    Args:
        image: PIL Image object
        language: Language hint ("auto", "hindi", "marathi", etc.)
    
    Returns:
        dict with keys: text, engine, language, confidence, structured
    """
    model = load_gemini()
    
    # Convert PIL image to bytes for Gemini
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='JPEG', quality=95)
    img_bytes = img_byte_arr.getvalue()
    
    # Build language hint
    lang_hint = ""
    if language in ["hindi", "devanagari"]:
        lang_hint = """
IMPORTANT: This image contains Hindi/Devanagari text. 
- Look for drug names in BOTH English and Hindi script
- Drug names may be transliterated (written phonetically in Hindi)
- Common Hindi drug names: पैरासिटामोल (Paracetamol), आयबूप्रोफेन (Ibuprofen), मेटफोर्मिन (Metformin)
- If you see any medicine/tablet/capsule names in Devanagari, transliterate them to English
"""
    elif language == "marathi":
        lang_hint = """
IMPORTANT: This image contains Marathi/Devanagari text.
- Look for drug names in BOTH English and Marathi script
- Drug names may be transliterated in Devanagari
- Transliterate any Marathi drug names to English
"""
    
    # The prompt — designed specifically for prescription extraction
    prompt = f"""You are a medical OCR expert specializing in HANDWRITTEN and multilingual prescriptions. 
Your specialty is deciphering difficult doctor's handwriting.

CRITICAL TASK: Extract EVERY piece of text from this prescription image, focusing especially on HANDWRITTEN content.

🔍 HANDWRITTEN TEXT EXTRACTION (HIGHEST PRIORITY):
- Many prescriptions have poor, messy, or cursive doctor's handwriting - READ IT CAREFULLY
- Handwritten drug names are often abbreviated or misspelled - interpret them
- Look for pen/pencil marks, scribbles, and cursive writing
- Even if text is unclear or illegible, make your BEST GUESS - don't skip it
- Common handwriting challenges: letters merge together, poor spacing, unclear characters
- Interpret context: if something looks like a drug name pattern, include it

DRUG NAME DETECTION:
- Drug names can be handwritten, printed, typed, or stamped
- They appear in prescription body, margins, corners, headers
- Look for patterns: [Drug Name] + [Dose] + [Frequency]
- Medical abbreviations: Tab/T (tablet), Cap/C (capsule), Inj (injection), Syr (syrup)
- Dosage units: mg, mcg, ml, gm, units, IU
- Frequency: BD/BID (twice), TID (3x), QD/OD (once), PRN (as needed)
{lang_hint}

Return ONLY a valid JSON object. No markdown. No explanation.
No text before or after the JSON.

{{
  "raw_text": "Complete verbatim text from the entire image preserving line breaks with \\n. Include ALL words visible even if unclear.",
  "patient_name": "full patient name exactly as written or null",
  "patient_age": "age as string or null",
  "patient_address": "address or null",
  "date": "date as written or null",
  "hospital_clinic": "hospital or clinic name or null",
  "doctor_name": "doctor name exactly as written or null",
  "drugs": [
    {{
      "name": "exact drug/medicine name as written - if in Devanagari translate to English",
      "dose": "dose with unit e.g. 100mg, 5mg, 500mg — include unit",
      "frequency": "exactly as written e.g. BID, TID, OD, once daily, twice daily",
      "duration": "duration if mentioned e.g. 7 days, 1 month, or null",
      "quantity": "quantity e.g. 1 tab, 2 tabs, 1 cap or null",
      "instructions": "any special instructions for this drug or null"
    }}
  ],
  "special_instructions": "any general notes, diet advice, follow-up instructions or null",
  "language_detected": "english or hindi or marathi or mixed"
}}

STRICT RULES — follow exactly:
- HANDWRITTEN TEXT IS YOUR PRIMARY FOCUS - spend extra effort interpreting messy handwriting
- SEARCH THE ENTIRE IMAGE for drug names - check every corner, margin, and section
- Extract EVERY drug you can see or infer, even if handwriting is unclear
- If drug name is partially legible or messy, write your BEST INTERPRETATION - never skip
- For illegible handwriting, use context clues (dose, frequency nearby) to infer the drug
- **TOLERATE OCR ERRORS**: Include drug names even if spelling looks slightly wrong (e.g., "Beteloe" instead of "Betaloc", "Dorzolamidum" instead of "Dorzolamide")
- If a word looks like a drug name but has 1-2 character mistakes, include it anyway
- Include dose WITH unit (mg, mcg, ml) — never just a number
- For frequency keep original abbreviation: BID, TID, QD, OD, BD, QID, HS, AC, PC, PRN
- raw_text must be COMPLETE — include every visible character, even if unclear
- If you see Devanagari drug names, transliterate them to English Latin script
- drugs array must have ONE entry per drug line in the prescription
- If handwriting is illegible but you see a pattern (name + dose), include it with your best guess
- ONLY set drugs to [] if you're 100% certain there are NO medicines (e.g., blank form, lab report)
- If a field is not visible, use null — never omit the field
- Return ONLY the JSON object starting with {{ and ending with }}"""

    try:
        # Create image part for Gemini
        image_part = {
            "mime_type": "image/jpeg",
            "data": img_bytes
        }
        
        response = model.generate_content(
            [prompt, image_part],
            generation_config=genai.types.GenerationConfig(
                temperature=0.05,      # even lower for more deterministic extraction
                max_output_tokens=4096  # increased from 2048 to handle long prescriptions
            )
        )
        
        raw_response = response.text.strip()
        
        # Clean JSON response (remove markdown code blocks if present)
        if "```json" in raw_response:
            raw_response = raw_response.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_response:
            raw_response = raw_response.split("```")[1].split("```")[0].strip()
        
        # Parse JSON
        extracted = json.loads(raw_response)
        
        # Log extraction results
        drugs_count = len(extracted.get("drugs", []))
        if drugs_count > 0:
            print(f"  ✅ Gemini extracted {drugs_count} drugs from image")
            for i, drug in enumerate(extracted.get("drugs", [])[:3], 1):  # Show first 3
                print(f"     {i}. {drug.get('name', 'Unknown')} - {drug.get('dose', 'No dose')}")
        else:
            print(f"  ⚠️ No drugs found in first attempt")
        
        # RETRY if drugs array is empty
        if len(extracted.get("drugs", [])) == 0:
            print("  🔄 Retrying with handwriting-focused prompt...")
            try:
                retry_prompt = """This is a HANDWRITTEN PRESCRIPTION. Look at it again VERY CAREFULLY.

You are a doctor's handwriting expert. Your ONLY job: Find ALL medicine names in this image.

🎯 FOCUS ON HANDWRITTEN SECTIONS:
- Doctors have notoriously poor handwriting - but you can read it
- Look for cursive, scribbled, messy pen/pencil marks
- Drug names often look like: wavy lines + dose (e.g., "~~~~ 500mg")
- Even if you can only read 50-70% of letters, GUESS the drug name
- Context helps: if you see "500mg BID", there's likely a drug name before it

📍 WHERE TO LOOK:
1. Main prescription body (usually handwritten)
2. Below "Rx:" or similar markers
3. Numbered lists (1., 2., 3.)
4. Margins and corners
5. Below patient name/age section

🔤 COMMON PATTERNS:
- [Scribbled drug name] [dose]mg [frequency]
- T./Tab./Tablet [drug name]
- Inj./Injection [drug name]
- Drug names are often 7-15 characters long

Return ONLY this JSON format (no explanation, no markdown):
{{
  "drugs": [
    {{"name": "your best guess at drug name even if unclear", "dose": "100mg", "frequency": "BID", "duration": null, "quantity": "1 tab", "instructions": null}}
  ]
}}

IMPORTANT: Include EVERY potential drug name even if you're not 100% certain. Make educated guesses. DO NOT return empty array unless this is definitely not a prescription.

EVEN IF UNSURE, include potential drug names. Do not return empty drugs array unless you are 100% certain there are NO medicines in this image."""
            
                retry_response = model.generate_content(
                    [retry_prompt, image_part],
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.2,  # slightly higher to be more creative in finding drugs
                        max_output_tokens=2048
                    )
                )
                retry_raw = retry_response.text.strip()
                if "```json" in retry_raw:
                    retry_raw = retry_raw.split("```json")[1].split("```")[0].strip()
                elif "```" in retry_raw:
                    retry_raw = retry_raw.split("```")[1].split("```")[0].strip()
                
                retry_extracted = json.loads(retry_raw)
                if retry_extracted.get("drugs"):
                    extracted["drugs"] = retry_extracted["drugs"]
                    print(f"  ✅ Retry found {len(extracted['drugs'])} drugs")
                else:
                    # Second attempt: handwriting-focused prompt
                    print("  ⚠️ Second attempt also empty, trying handwriting-focused prompt...")
                    simple_prompt = """This image contains handwritten prescriptions with poor doctor's handwriting.
                    
Read the handwritten drug/medicine names carefully and list them as comma-separated values.
Even if handwriting is messy or unclear, include your best interpretation of what the drug names might be.
Look for any handwritten words that could be medicine names.
                    
List the drug names you can see (comma-separated):"""
                    simple_response = model.generate_content(
                        [simple_prompt, image_part],
                        generation_config=genai.types.GenerationConfig(
                            temperature=0.4,  # even higher for creative handwriting interpretation
                            max_output_tokens=512
                        )
                    )
                    drug_text = simple_response.text.strip()
                    if drug_text and len(drug_text) > 3:
                        # Parse comma-separated list
                        drug_names = [d.strip() for d in drug_text.split(',') if d.strip()]
                        if drug_names:
                            extracted["drugs"] = [{"name": name, "dose": None, "frequency": None, 
                                                  "duration": None, "quantity": None, "instructions": None} 
                                                 for name in drug_names[:10]]  # max 10
                            print(f"  ✅ Simple prompt found {len(extracted['drugs'])} drug names")
                    else:
                        # Third attempt: ultra-simple prompt
                        print("  ⚠️ Second attempt also empty, trying ultra-simple prompt...")
                        simple_prompt = "List every medicine/drug name you can see in this image as comma-separated values:"
                        simple_response = model.generate_content(
                            [simple_prompt, image_part],
                            generation_config=genai.types.GenerationConfig(
                                temperature=0.3, max_output_tokens=512
                            )
                        )
                        drug_text = simple_response.text.strip()
                        if drug_text and len(drug_text) > 3:
                            # Parse comma-separated list
                            drug_names = [d.strip() for d in drug_text.split(',') if d.strip()]
                            if drug_names:
                                extracted["drugs"] = [{"name": name, "dose": None, "frequency": None, 
                                                      "duration": None, "quantity": None, "instructions": None} 
                                                     for name in drug_names[:10]]  # max 10
                                print(f"  ✅ Simple prompt found {len(extracted['drugs'])} drug names")
            except Exception as e:
                print(f"  ❌ Retry parsing failed: {e}")
                pass
        
        raw_text = extracted.get("raw_text", "")
        final_drugs = extracted.get("drugs", [])
        
        # ── DRUG RESOLUTION: Fix misspelled drug names ──────────────────────
        raw_text_for_resolution = extracted.get("raw_text", "")
        
        # Always run drug resolution on raw_text — more reliable than
        # the structured drugs from the OCR step (handles misspellings)
        resolved_drugs = resolve_drugs_from_text(raw_text_for_resolution)
        
        # Build final drugs list:
        # Priority: resolved_drugs (if non-empty) → original extracted drugs
        if resolved_drugs:
            # Convert resolved format to standard structuredDrug format
            final_drugs_resolved = []
            for rd in resolved_drugs:
                final_drugs_resolved.append({
                    "name": rd["correct_name"],           # corrected name
                    "ocr_name": rd.get("ocr_name"),       # original OCR spelling
                    "brand_name": rd.get("brand_name"),
                    "dose": rd.get("dose"),
                    "frequency": rd.get("frequency"),
                    "duration": None,
                    "quantity": None,
                    "confidence": rd.get("confidence", "MEDIUM"),
                    "reasoning": rd.get("reasoning")
                })
            final_drugs = final_drugs_resolved
            print(f"  ✅ Used resolved drug list: {[d['name'] for d in final_drugs]}")
        elif not extracted.get("drugs"):
            # Last resort: retry with explicit drug focus
            print("  ⚠️ No drugs from either method, running targeted extraction...")
            retry = resolve_drugs_from_text(raw_text_for_resolution)
            if retry:
                final_drugs = [{
                    "name": r["correct_name"],
                    "ocr_name": r.get("ocr_name"),
                    "dose": r.get("dose"),
                    "frequency": r.get("frequency"),
                    "duration": None, 
                    "quantity": None
                } for r in retry]
        
        # ─────────────────────────────────────────────────────────────────────
        
        # Final log before returning
        print(f"  📤 Returning {len(final_drugs)} drugs in response")
        
        return {
            "text": raw_text,
            "engine": "Gemini Vision + Drug Resolution",
            "language": extracted.get("language_detected", language),
            "confidence": 0.95,   # Gemini is highly reliable
            "structured": {
                "patient_name": extracted.get("patient_name"),
                "patient_age": extracted.get("patient_age"),
                "patient_address": extracted.get("patient_address"),
                "date": extracted.get("date"),
                "hospital_clinic": extracted.get("hospital_clinic"),
                "doctor_name": extracted.get("doctor_name"),
                "drugs": final_drugs,
                "special_instructions": extracted.get("special_instructions")
            }
        }
    
    except json.JSONDecodeError:
        # Gemini returned text but not valid JSON — use raw text anyway
        print(f"  ⚠️ Gemini JSON parse failed, using raw text")
        return {
            "text": raw_response[:1000] if raw_response else "",
            "engine": "Gemini Vision (raw)",
            "language": language,
            "confidence": 0.85,
            "structured": {}
        }
    except Exception as e:
        print(f"  ❌ Gemini OCR error: {e}")
        return None   # triggers fallback


# ============================================================================
# SECTION 4 — Tesseract Fallback
# ============================================================================

def ocr_with_tesseract(image: Image.Image, language: str = "auto") -> dict:
    """
    Tesseract fallback when Gemini fails.
    
    Args:
        image: PIL Image object
        language: Language hint
    
    Returns:
        dict with OCR results
    """
    try:
        import cv2
        import numpy as np
        
        # Quick preprocess
        img_cv = cv2.cvtColor(np.array(image.convert('RGB')), cv2.COLOR_RGB2BGR)
        h, w = img_cv.shape[:2]
        if w < 1200:
            scale = 1200 / w
            img_cv = cv2.resize(img_cv, None, fx=scale, fy=scale,
                                interpolation=cv2.INTER_CUBIC)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        thresh = cv2.adaptiveThreshold(gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10)
        pil_img = Image.fromarray(thresh)
        
        # Language selection
        tess_lang = "eng"
        if language in ["hindi", "devanagari"]:
            tess_lang = "hin+eng"
        elif language == "marathi":
            tess_lang = "mar+eng"
        
        config = r"--oem 3 --psm 6 -c preserve_interword_spaces=1"
        text = pytesseract.image_to_string(pil_img, lang=tess_lang, config=config)
        
        data = pytesseract.image_to_data(pil_img, lang=tess_lang, config=config,
                                          output_type=pytesseract.Output.DICT)
        confs = [int(c) for c in data['conf'] if str(c).isdigit() and int(c) > 0]
        avg_conf = round(sum(confs)/len(confs), 2) if confs else 0
        
        return {
            "text": text.strip(),
            "engine": "Tesseract (fallback)",
            "language": language,
            "confidence": avg_conf,
            "structured": {}
        }
    except Exception as e:
        return {
            "text": "",
            "engine": "error",
            "language": language,
            "confidence": 0,
            "error": str(e),
            "structured": {}
        }


# ============================================================================
# SECTION 5 — Main OCR Function (Replaces old run_ocr)
# ============================================================================

def run_ocr(image: Image.Image, language: str = "auto") -> dict:
    """
    Primary: Gemini Vision (~2-3 sec, highly accurate)
    Fallback: Tesseract (if Gemini fails or no API key)
    
    Args:
        image: PIL Image object
        language: Language hint ("auto", "english", "hindi", "marathi", "devanagari")
    
    Returns:
        dict with OCR results including text, engine, language, confidence, structured
    """
    # Try Gemini first
    if GEMINI_API_KEY:
        print("🤖 Using Gemini Vision for OCR...")
        result = ocr_with_gemini(image, language)
        if result and result.get("text"):
            print(f"  ✅ Gemini extracted {len(result['text'])} chars")
            return result
        print("  ⚠️ Gemini returned empty, falling back to Tesseract...")
    else:
        print("⚠️ No GEMINI_API_KEY found, using Tesseract...")
    
    # Fallback to Tesseract
    print("🔤 Using Tesseract fallback...")
    return ocr_with_tesseract(image, language)


# ============================================================================
# SECTION 6 — Post-processing for prescription text
# ============================================================================

def clean_prescription_text(raw_text: str) -> str:
    """
    Cleans OCR output specifically for medical prescription text.
    Fixes common OCR errors in drug names and dosage notation.
    
    Args:
        raw_text: Raw OCR output text
    
    Returns:
        Cleaned and normalized prescription text
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


# ============================================================================
# SECTION 7 — Input Handlers (Base64 and File Path)
# ============================================================================

def ocr_from_base64(image_b64: str, language: str = "auto") -> dict:
    """
    Run OCR on base64-encoded image.
    
    Args:
        image_b64: Base64-encoded image string (with or without data URI prefix)
        language: Target language for OCR
    
    Returns:
        dict with OCR results + cleanedText, charCount, success fields
    """
    try:
        # Strip data URI prefix if present
        if "base64," in image_b64:
            image_b64 = image_b64.split("base64,")[1]
        
        image_bytes = base64.b64decode(image_b64)
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        
        # Run OCR
        result = run_ocr(image, language)
        
        # Add cleaned text and metadata
        result["cleanedText"] = clean_prescription_text(result.get("text", ""))
        result["charCount"] = len(result.get("cleanedText", ""))
        result["success"] = len(result.get("cleanedText", "")) > 5
        
        # NER FALLBACK: If Gemini didn't find drugs but we have text, try NER
        structured_drugs = result.get("structured", {}).get("drugs", [])
        if not structured_drugs and result.get("cleanedText"):
            print("  🔄 Gemini found no drugs, trying NER fallback on extracted text...")
            try:
                from ner.predict_ner import extract_entities
                ner_result = extract_entities(result["cleanedText"])
                drug_names = ner_result.get("drugs", [])
                dose_tokens = ner_result.get("doses", [])
                freq_tokens = ner_result.get("frequencies", [])
                dur_tokens = ner_result.get("durations", [])
                
                if drug_names:
                    print(f"  ✅ NER fallback found {len(drug_names)} drugs: {drug_names[:3]}")
                    # Build structured drugs from NER
                    fallback_drugs = []
                    for i, drug in enumerate(drug_names):
                        fallback_drugs.append({
                            "name": drug,
                            "dose": dose_tokens[i] if i < len(dose_tokens) else None,
                            "frequency": freq_tokens[i] if i < len(freq_tokens) else None,
                            "duration": dur_tokens[i] if i < len(dur_tokens) else None,
                            "quantity": None,
                            "instructions": None
                        })
                    if "structured" not in result:
                        result["structured"] = {}
                    result["structured"]["drugs"] = fallback_drugs
                    print(f"  📋 NER fallback populated {len(fallback_drugs)} structured drugs")
                else:
                    print("  ⚠️ NER fallback also found no drugs, trying regex fallback...")
                    # REGEX FALLBACK: Last resort - look for known drug names
                    regex_drugs = extract_drugs_with_regex(result["cleanedText"])
                    if regex_drugs:
                        print(f"  ✅ Regex fallback found {len(regex_drugs)} drugs: {regex_drugs[:3]}")
                        fallback_drugs = [{"name": drug, "dose": None, "frequency": None,
                                         "duration": None, "quantity": None, "instructions": None}
                                        for drug in regex_drugs]
                        if "structured" not in result:
                            result["structured"] = {}
                        result["structured"]["drugs"] = fallback_drugs
                    else:
                        print("  ⚠️ Regex fallback also found no drugs, trying fuzzy matching...")
                        # FUZZY MATCHING: Catch OCR errors and misspellings
                        fuzzy_matches = fuzzy_match_drugs(result["cleanedText"], cutoff=0.75)
                        if fuzzy_matches:
                            print(f"  ✅ Fuzzy matching found {len(fuzzy_matches)} drugs:")
                            for detected, corrected, similarity in fuzzy_matches[:5]:
                                print(f"     '{detected}' -> '{corrected}' ({similarity:.0%} match)")
                            
                            fallback_drugs = []
                            for detected_word, correct_name, similarity in fuzzy_matches:
                                # Extract dose from the line containing the drug
                                dose_match = re.search(
                                    rf'{re.escape(detected_word)}\s*(\d+\s*(?:mg|mcg|ml|gm|g|m))',
                                    result["cleanedText"],
                                    re.IGNORECASE
                                )
                                dose = dose_match.group(1) if dose_match else None
                                
                                fallback_drugs.append({
                                    "name": correct_name,  # Use corrected name
                                    "dose": dose,
                                    "frequency": None,
                                    "duration": None,
                                    "quantity": None,
                                    "instructions": f"Detected as '{detected_word}' with {similarity:.0%} confidence"
                                })
                            
                            if "structured" not in result:
                                result["structured"] = {}
                            result["structured"]["drugs"] = fallback_drugs
                        else:
                            print("  ⚠️ All fallback methods (NER, Regex, Fuzzy) found no drugs")
            except Exception as e:
                print(f"  ❌ Fallback error: {e}")
        
        return result
    except Exception as e:
        return {
            "text": "",
            "engine": "error",
            "language": language,
            "confidence": 0,
            "error": str(e),
            "cleanedText": "",
            "charCount": 0,
            "success": False,
            "structured": {}
        }


def ocr_from_file(image_path: str, language: str = "auto") -> dict:
    """
    Run OCR on image file.
    
    Args:
        image_path: Path to image file
        language: Target language for OCR
    
    Returns:
        dict with OCR results + cleanedText, charCount, success fields
    """
    try:
        image = Image.open(image_path).convert("RGB")
        
        # Run OCR
        result = run_ocr(image, language)
        
        # Add cleaned text and metadata
        result["cleanedText"] = clean_prescription_text(result.get("text", ""))
        result["charCount"] = len(result.get("cleanedText", ""))
        result["success"] = len(result.get("cleanedText", "")) > 5
        
        # NER FALLBACK: If Gemini didn't find drugs but we have text, try NER
        structured_drugs = result.get("structured", {}).get("drugs", [])
        if not structured_drugs and result.get("cleanedText"):
            print("  🔄 Gemini found no drugs, trying NER fallback on extracted text...")
            try:
                from ner.predict_ner import extract_entities
                ner_result = extract_entities(result["cleanedText"])
                drug_names = ner_result.get("drugs", [])
                dose_tokens = ner_result.get("doses", [])
                freq_tokens = ner_result.get("frequencies", [])
                dur_tokens = ner_result.get("durations", [])
                
                if drug_names:
                    print(f"  ✅ NER fallback found {len(drug_names)} drugs: {drug_names[:3]}")
                    # Build structured drugs from NER
                    fallback_drugs = []
                    for i, drug in enumerate(drug_names):
                        fallback_drugs.append({
                            "name": drug,
                            "dose": dose_tokens[i] if i < len(dose_tokens) else None,
                            "frequency": freq_tokens[i] if i < len(freq_tokens) else None,
                            "duration": dur_tokens[i] if i < len(dur_tokens) else None,
                            "quantity": None,
                            "instructions": None
                        })
                    if "structured" not in result:
                        result["structured"] = {}
                    result["structured"]["drugs"] = fallback_drugs
                    print(f"  📋 NER fallback populated {len(fallback_drugs)} structured drugs")
                else:
                    print("  ⚠️ NER fallback also found no drugs, trying regex fallback...")
                    # REGEX FALLBACK: Last resort - look for known drug names
                    regex_drugs = extract_drugs_with_regex(result["cleanedText"])
                    if regex_drugs:
                        print(f"  ✅ Regex fallback found {len(regex_drugs)} drugs: {regex_drugs[:3]}")
                        fallback_drugs = [{"name": drug, "dose": None, "frequency": None,
                                         "duration": None, "quantity": None, "instructions": None}
                                        for drug in regex_drugs]
                        if "structured" not in result:
                            result["structured"] = {}
                        result["structured"]["drugs"] = fallback_drugs
                    else:
                        print("  ⚠️ Regex fallback also found no drugs, trying fuzzy matching...")
                        # FUZZY MATCHING: Catch OCR errors and misspellings
                        fuzzy_matches = fuzzy_match_drugs(result["cleanedText"], cutoff=0.75)
                        if fuzzy_matches:
                            print(f"  ✅ Fuzzy matching found {len(fuzzy_matches)} drugs:")
                            for detected, corrected, similarity in fuzzy_matches[:5]:
                                print(f"     '{detected}' -> '{corrected}' ({similarity:.0%} match)")
                            
                            fallback_drugs = []
                            for detected_word, correct_name, similarity in fuzzy_matches:
                                # Extract dose from the line containing the drug
                                dose_match = re.search(
                                    rf'{re.escape(detected_word)}\s*(\d+\s*(?:mg|mcg|ml|gm|g|m))',
                                    result["cleanedText"],
                                    re.IGNORECASE
                                )
                                dose = dose_match.group(1) if dose_match else None
                                
                                fallback_drugs.append({
                                    "name": correct_name,  # Use corrected name
                                    "dose": dose,
                                    "frequency": None,
                                    "duration": None,
                                    "quantity": None,
                                    "instructions": f"Detected as '{detected_word}' with {similarity:.0%} confidence"
                                })
                            
                            if "structured" not in result:
                                result["structured"] = {}
                            result["structured"]["drugs"] = fallback_drugs
                        else:
                            print("  ⚠️ All fallback methods (NER, Regex, Fuzzy) found no drugs")
            except Exception as e:
                print(f"  ❌ Fallback error: {e}")
        
        return result
    except Exception as e:
        return {
            "text": "",
            "engine": "error",
            "language": language,
            "confidence": 0,
            "error": str(e),
            "cleanedText": "",
            "charCount": 0,
            "success": False,
            "structured": {}
        }
