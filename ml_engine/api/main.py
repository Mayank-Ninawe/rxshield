"""
RxShield ML API - FastAPI Server
Integrates all 4 ML models: NER, Classifier, Anomaly Detection, LASA
Plus OCR for prescription image processing
"""

import sys
import os
import time
import uuid
import re
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Add parent directory to path so we can import sibling modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rules.rules_engine import run_all_checks, normalise

from api.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    OCRRequest,
    OCRResponse,
    HealthResponse,
    ExtractedDrug,
    ErrorDetail,
    StructuredDrug,
    PatientInfo,
    AnalyzeFromOCRRequest,
    OCRDrug
)

# Import model modules (lazy - they load on first use)
from ner.predict_ner import extract_entities
from classifier.predict_classifier import check_all_drugs
from anomaly.predict_anomaly import check_dosage_anomaly
from lasa.lasa_detector import check_lasa_confusion
from ocr.ocr_pipeline import ocr_from_base64, clean_prescription_text, resolve_drugs_from_text


# ============================================================================
# APP SETUP
# ============================================================================

app = FastAPI(
    title="RxShield ML API",
    description="Prescription error detection ML service",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)


# ============================================================================
# STARTUP EVENT
# ============================================================================

@app.on_event("startup")
async def startup():
    """Initialize API on startup."""
    print("🚀 RxShield ML API starting...")
    print("📦 Models will load lazily on first request")
    print("✅ API ready at http://localhost:8000")


# ============================================================================
# HEALTH ENDPOINT
# ============================================================================

@app.get("/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint showing loaded models."""
    return HealthResponse(
        status="ok",
        service="RxShield ML API",
        models_loaded={
            "ner": "distilbert-ner (lazy)",
            "classifier": "random-forest (lazy)",
            "anomaly": "isolation-forest (lazy)",
            "lasa": "rule-based + phonetic (loaded)",
            "ocr": "trocr + tesseract (lazy)"
        }
    )


# ============================================================================
# CORE ANALYZE ENDPOINT
# ============================================================================

@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_prescription(request: AnalyzeRequest):
    """
    Main prescription analysis endpoint.
    Uses rules engine for reliable error detection.
    """
    start_time = time.time()
    errors = []
    
    prescription_id = f"RX-{uuid.uuid4().hex[:8].upper()}"
    patient_dict = request.patientData.dict()
    text = request.prescriptionText

    # ── STEP 1: NER ──────────────────────────────────────────────────────────
    drug_names = []
    extracted_drugs = []
    try:
        ner_result = extract_entities(text)
        drug_names = ner_result.get("drugs", [])
        dose_tokens = ner_result.get("doses", [])
        freq_tokens = ner_result.get("frequencies", [])
        dur_tokens  = ner_result.get("durations", [])
        
        extracted_drugs = [
            ExtractedDrug(
                drug_name=drug,
                dose=dose_tokens[i] if i < len(dose_tokens) else None,
                frequency=freq_tokens[i] if i < len(freq_tokens) else None,
                duration=dur_tokens[i] if i < len(dur_tokens) else None
            )
            for i, drug in enumerate(drug_names)
        ]
    except Exception as e:
        print(f"NER error: {e}")
        # Fallback: extract drug names with regex from text
        drug_pattern = re.compile(
            r'\b(Metformin|Aspirin|Warfarin|Amoxicillin|Atorvastatin|'
            r'Amlodipine|Lisinopril|Metoprolol|Betaloc|Atenolol|Digoxin|'
            r'Furosemide|Tramadol|Codeine|Morphine|Ibuprofen|Diclofenac|'
            r'Paracetamol|Omeprazole|Pantoprazole|Ciprofloxacin|'
            r'Azithromycin|Clarithromycin|Ceftriaxone|Cephalexin|'
            r'Simvastatin|Rosuvastatin|Carbamazepine|Spironolactone|'
            r'Verapamil|Diltiazem|Cimetidine|Ranitidine|Famotidine|'
            r'Dorzolamide|Oxprenolol|Oxprelol|Telmisartan|Losartan|'
            r'Glimepiride|Sitagliptin|Levothyroxine|Sertraline|Fluoxetine|'
            r'Prednisolone|Dexamethasone|Salbutamol|Theophylline|Ramipril|'
            r'Cetirizine|Naproxen|Ketorolac)\b',
            re.IGNORECASE
        )
        drug_names = list(dict.fromkeys(
            m.group(0) for m in drug_pattern.finditer(text)
        ))
        extracted_drugs = [ExtractedDrug(drug_name=d) for d in drug_names]

    # ── STEP 2: Extract doses from text for dosage checking ─────────────────
    # Build extracted_drugs_raw for rules engine
    extracted_drugs_raw = []
    for ed in extracted_drugs:
        extracted_drugs_raw.append({
            "drug_name": ed.drug_name,
            "dose": ed.dose
        })
    
    # If doses missing from NER, try regex extraction
    if drug_names and not any(e.dose for e in extracted_drugs):
        # Pattern: "DrugName 500mg" or "DrugName 500 mg"
        for i, drug in enumerate(drug_names):
            pattern = re.compile(
                re.escape(drug) + r'\s+(\d+\.?\d*)\s*(?:mg|mcg|ml|units?)',
                re.IGNORECASE
            )
            m = pattern.search(text)
            if m:
                extracted_drugs[i] = ExtractedDrug(
                    drug_name=extracted_drugs[i].drug_name,
                    dose=m.group(0).split(drug, 1)[-1].strip(),
                    frequency=extracted_drugs[i].frequency,
                    duration=extracted_drugs[i].duration
                )
                extracted_drugs_raw[i]["dose"] = m.group(0).split(drug, 1)[-1].strip()

    # ── STEP 3: RUN RULES ENGINE (ALL 4 CHECKS) ─────────────────────────────
    if drug_names:
        try:
            rules_result = run_all_checks(
                drug_names=drug_names,
                patient_data=patient_dict,
                extracted_drugs=extracted_drugs_raw
            )
            
            for err in rules_result["errors"]:
                errors.append(ErrorDetail(
                    error_type=err["error_type"],
                    drug=err.get("drug"),
                    drug_a=err.get("drug_a"),
                    drug_b=err.get("drug_b"),
                    severity=err["severity"],
                    message=err["message"],
                    explanation=err.get("explanation"),
                    solution=err.get("solution"),
                    confidence=err.get("confidence"),
                    details=err.get("details")
                ))
        except Exception as e:
            print(f"Rules engine error: {e}")

    # ── STEP 4: LASA Check (already working) ─────────────────────────────────
    for drug_name in drug_names:
        try:
            lasa = check_lasa_confusion(drug_name)
            if lasa['has_lasa_risk'] and lasa['risk_level'] in ['CRITICAL','HIGH']:
                errors.append(ErrorDetail(
                    error_type="LASA",
                    drug=drug_name,
                    severity=lasa['risk_level'],
                    message=lasa['recommendation'],
                    explanation=(
                        f"'{drug_name}' has visual/phonetic similarity with other drugs: "
                        f"{[p['partner'] for p in lasa['known_lasa_pairs']]}. "
                        f"Dispensing errors between these drugs are documented."
                    ),
                    solution=(
                        "Use TALL MAN lettering. Verbally confirm drug name. "
                        "Apply barcode verification. Double-check before dispensing."
                    ),
                    details={
                        "known_pairs": lasa['known_lasa_pairs'],
                        "phonetic_similar": lasa['phonetic_similar_drugs']
                    }
                ))
        except Exception as e:
            print(f"LASA error for {drug_name}: {e}")

    # ── STEP 5: Calculate risk score ─────────────────────────────────────────
    severity_weights = {"CRITICAL":1.0,"HIGH":0.7,"MEDIUM":0.4,"LOW":0.2}
    if not errors:
        risk_score = 0.0
    else:
        scores = [severity_weights.get(e.severity, 0.1) for e in errors]
        risk_score = min(1.0, max(scores) * 0.6 + (len(errors)-1) * 0.1)

    risk_level = (
        "CRITICAL" if risk_score > 0.75 else
        "HIGH"     if risk_score > 0.5  else
        "MEDIUM"   if risk_score > 0.25 else
        "LOW"      if risk_score > 0    else
        "SAFE"
    )

    error_types = list(set(e.error_type for e in errors))
    summary = (
        f"✅ Prescription appears safe. {len(extracted_drugs)} drug(s) found."
        if not errors else
        f"⚠️ {len(errors)} issue(s) found: {', '.join(error_types)}. "
        f"Risk level: {risk_level}."
    )

    processing_time = (time.time() - start_time) * 1000

    return AnalyzeResponse(
        status="analyzed",
        prescriptionId=prescription_id,
        extractedDrugs=extracted_drugs,
        errors=errors,
        riskScore=round(risk_score, 4),
        riskLevel=risk_level,
        summary=summary,
        processingTime_ms=round(processing_time, 2)
    )


# ============================================================================
# ANALYZE FROM OCR ENDPOINT (Direct structured input)
# ============================================================================

@app.post("/analyze-from-ocr", response_model=AnalyzeResponse)
async def analyze_from_ocr(request: AnalyzeFromOCRRequest):
    """
    Analyze prescription using Gemini's pre-parsed drug list.
    Much more accurate than re-parsing OCR text with NER.
    Bypasses NER completely - uses structured drugs directly from OCR.
    """
    start_time = time.time()
    errors = []
    prescription_id = f"RX-{uuid.uuid4().hex[:8].upper()}"
    patient_dict = request.patientData.dict()
    
    # Build drug names and extracted_drugs directly from OCR structured data
    drug_names = [d.name for d in request.structuredDrugs if d.name]
    
    # If no structured drugs came from OCR, try resolving from raw text
    if not request.structuredDrugs and request.rawText:
        print("⚠️ No structured drugs received, resolving from raw text...")
        resolved = resolve_drugs_from_text(request.rawText)
        if resolved:
            request = request.copy(update={
                "structuredDrugs": [
                    OCRDrug(
                        name=r["correct_name"],
                        ocr_name=r.get("ocr_name"),
                        dose=r.get("dose"),
                        frequency=r.get("frequency")
                    )
                    for r in resolved
                ]
            })
            drug_names = [d.name for d in request.structuredDrugs if d.name]
            print(f"✅ Resolved {len(request.structuredDrugs)} drugs from raw text")
    
    extracted_drugs = [
        ExtractedDrug(
            drug_name=d.name,
            dose=d.dose,
            frequency=d.frequency,
            duration=d.duration
        )
        for d in request.structuredDrugs if d.name
    ]
    
    extracted_drugs_raw = [
        {"drug_name": d.name, "dose": d.dose}
        for d in request.structuredDrugs if d.name
    ]
    
    if not drug_names:
        # Fallback: try to extract from rawText if structuredDrugs is empty
        if request.rawText:
            fallback_req = AnalyzeRequest(
                prescriptionText=request.rawText,
                patientData=request.patientData
            )
            return await analyze_prescription(fallback_req)
        return AnalyzeResponse(
            status="no_drugs_found",
            prescriptionId=prescription_id,
            extractedDrugs=[],
            errors=[],
            riskScore=0.0,
            riskLevel="SAFE",
            summary="No drugs found in prescription. Please verify the image quality.",
            processingTime_ms=0
        )
    
    # Run Rules Engine (same as /analyze)
    try:
        rules_result = run_all_checks(
            drug_names=drug_names,
            patient_data=patient_dict,
            extracted_drugs=extracted_drugs_raw
        )
        for err in rules_result["errors"]:
            errors.append(ErrorDetail(
                error_type=err["error_type"],
                drug=err.get("drug"),
                drug_a=err.get("drug_a"),
                drug_b=err.get("drug_b"),
                severity=err["severity"],
                message=err["message"],
                explanation=err.get("explanation"),
                solution=err.get("solution"),
                confidence=err.get("confidence"),
                details=err.get("details")
            ))
    except Exception as e:
        print(f"Rules engine error: {e}")
    
    # LASA check
    for drug_name in drug_names:
        try:
            lasa = check_lasa_confusion(drug_name)
            if lasa['has_lasa_risk'] and lasa['risk_level'] in ['CRITICAL','HIGH']:
                errors.append(ErrorDetail(
                    error_type="LASA",
                    drug=drug_name,
                    severity=lasa['risk_level'],
                    message=lasa['recommendation'],
                    explanation=f"'{drug_name}' has visual/phonetic similarity with: "
                               f"{[p['partner'] for p in lasa['known_lasa_pairs']]}",
                    solution="Use TALL MAN lettering. Verbally confirm drug name before dispensing.",
                    details={"known_pairs": lasa['known_lasa_pairs']}
                ))
        except Exception as e:
            print(f"LASA error: {e}")
    
    # Risk calculation (same logic as /analyze)
    severity_weights = {"CRITICAL":1.0,"HIGH":0.7,"MEDIUM":0.4,"LOW":0.2}
    risk_score = 0.0
    if errors:
        scores = [severity_weights.get(e.severity, 0.1) for e in errors]
        risk_score = min(1.0, max(scores)*0.6 + (len(errors)-1)*0.1)
    
    risk_level = (
        "CRITICAL" if risk_score > 0.75 else
        "HIGH"     if risk_score > 0.5  else
        "MEDIUM"   if risk_score > 0.25 else
        "LOW"      if risk_score > 0    else "SAFE"
    )
    
    error_types = list(set(e.error_type for e in errors))
    summary = (
        f"✅ Prescription appears safe. {len(extracted_drugs)} drug(s) checked."
        if not errors else
        f"⚠️ {len(errors)} issue(s): {', '.join(error_types)}. Risk: {risk_level}."
    )
    
    return AnalyzeResponse(
        status="analyzed",
        prescriptionId=prescription_id,
        extractedDrugs=extracted_drugs,
        errors=errors,
        riskScore=round(risk_score, 4),
        riskLevel=risk_level,
        summary=summary,
        processingTime_ms=round((time.time()-start_time)*1000, 2)
    )


# ============================================================================
# OCR ENDPOINT
# ============================================================================

@app.post("/ocr", response_model=OCRResponse)
async def extract_text(request: OCRRequest):
    """
    OCR endpoint for extracting text from prescription images.
    Supports Gemini Vision (primary) with structured extraction and Tesseract (fallback).
    """
    try:
        result = ocr_from_base64(
            request.image_b64,
            language=request.language.value
        )
        
        if 'error' in result and not result.get('text'):
            raise HTTPException(
                status_code=400,
                detail=f"OCR failed: {result['error']}"
            )
        
        structured_data = result.get("structured", {})
        
        # Log what we got from OCR
        raw_drugs = structured_data.get("drugs", [])
        print(f"  📦 ML API received {len(raw_drugs)} drugs from OCR pipeline")
        
        # Build structured drugs list
        structured_drugs = []
        for drug in raw_drugs:
            structured_drugs.append(StructuredDrug(
                name=drug.get("name", ""),
                dose=drug.get("dose"),
                frequency=drug.get("frequency"),
                duration=drug.get("duration"),
                quantity=drug.get("quantity")
            ))
        
        print(f"  📋 ML API returning {len(structured_drugs)} structured drugs to Express")
        
        # Build patient info
        patient_info = None
        if any(structured_data.get(k) for k in 
               ["patient_name", "patient_age", "doctor_name", "hospital_clinic"]):
            patient_info = PatientInfo(
                patient_name=structured_data.get("patient_name"),
                patient_age=structured_data.get("patient_age"),
                patient_address=structured_data.get("patient_address"),
                date=structured_data.get("date"),
                hospital_clinic=structured_data.get("hospital_clinic"),
                doctor_name=structured_data.get("doctor_name"),
                special_instructions=structured_data.get("special_instructions")
            )
        
        cleaned = result.get("cleanedText", 
                             clean_prescription_text(result.get("text", "")))
        
        return OCRResponse(
            extractedText=result.get("text", ""),
            cleanedText=cleaned,
            engine=result.get("engine", "unknown"),
            language=result.get("language", "unknown"),
            confidence=result.get("confidence"),
            charCount=len(cleaned),
            success=len(cleaned) > 5,
            structuredDrugs=structured_drugs,
            patientInfo=patient_info
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# QUICK TEST ENDPOINT (remove before production)
# ============================================================================

@app.get("/test")
def test_endpoint():
    """Quick test endpoint to verify model accessibility."""
    test_text = "Rx: Metformin 500mg twice daily for 30 days, Aspirin 75mg once daily"
    test_patient = {
        "age": 55,
        "gender": "Male",
        "weight_kg": 75,
        "diagnosis": ["Type 2 Diabetes"],
        "allergies": [],
        "current_medications": [],
        "comorbidities": []
    }
    ner_result = extract_entities(test_text)
    return {
        "status": "ok",
        "test_ner_output": ner_result,
        "message": "All models accessible"
    }


# ============================================================================
# MAIN BLOCK
# ============================================================================

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
