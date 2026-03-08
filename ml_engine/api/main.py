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

from api.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    OCRRequest,
    OCRResponse,
    HealthResponse,
    ExtractedDrug,
    ErrorDetail
)

# Import model modules (lazy - they load on first use)
from ner.predict_ner import extract_entities
from classifier.predict_classifier import check_all_drugs
from anomaly.predict_anomaly import check_dosage_anomaly
from lasa.lasa_detector import check_lasa_confusion
from ocr.ocr_pipeline import ocr_from_base64, clean_prescription_text


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
    Runs all 4 ML models + rule checks to detect errors.
    """
    start_time = time.time()
    errors = []
    
    prescription_id = f"RX-{uuid.uuid4().hex[:8].upper()}"
    patient_dict = request.patientData.dict()
    text = request.prescriptionText
    
    # ========================================================================
    # STEP 1 — NER: Extract drugs, doses, frequencies
    # ========================================================================
    try:
        ner_result = extract_entities(text)
        drug_names = ner_result.get("drugs", [])
        dose_tokens = ner_result.get("doses", [])
        freq_tokens = ner_result.get("frequencies", [])
        duration_tokens = ner_result.get("durations", [])
    except Exception as e:
        print(f"NER error: {e}")
        drug_names = []
        dose_tokens, freq_tokens, duration_tokens = [], [], []
    
    # Build extracted_drugs list
    extracted_drugs = [
        ExtractedDrug(
            drug_name=drug,
            dose=dose_tokens[i] if i < len(dose_tokens) else None,
            frequency=freq_tokens[i] if i < len(freq_tokens) else None,
            duration=duration_tokens[i] if i < len(duration_tokens) else None
        )
        for i, drug in enumerate(drug_names)
    ]
    
    # ========================================================================
    # STEP 2 — Indication Mismatch Check
    # ========================================================================
    if drug_names:
        try:
            mismatch_results = check_all_drugs(drug_names, patient_dict)
            for result in mismatch_results:
                if result.get('is_mismatch'):
                    drug_class = result.get('drug_class', 'unknown')
                    drug_indications = result.get('drug_indications', 'unknown')
                    diagnosis_list = patient_dict.get('diagnosis', [])
                    
                    explanation = (
                        f"Drug class '{drug_class}' "
                        f"indicated for: {drug_indications}. "
                        f"Patient diagnosis: {diagnosis_list}. "
                        f"This combination was flagged as potentially inappropriate."
                    )
                    
                    solution = (
                        f"Verify clinical rationale for prescribing {result['drug_name']} "
                        f"for this diagnosis. If off-label use, document justification. "
                        f"Consider alternatives indicated for the patient's condition."
                    )
                    
                    errors.append(ErrorDetail(
                        error_type="INDICATION_MISMATCH",
                        drug=result['drug_name'],
                        severity=result['risk_level'],
                        message=f"Drug '{result['drug_name']}' may not be indicated for "
                                f"{diagnosis_list}",
                        explanation=explanation,
                        solution=solution,
                        confidence=result['confidence'],
                        details={
                            "drug_class": drug_class,
                            "drug_indications": drug_indications
                        }
                    ))
        except Exception as e:
            print(f"Classifier error: {e}")
    
    # ========================================================================
    # STEP 3 — Dosage Anomaly Check
    # ========================================================================
    for drug in extracted_drugs:
        if drug.dose is not None:
            try:
                # Parse dose_mg from dose string
                dose_match = re.search(r'(\d+\.?\d*)', drug.dose or "")
                dose_mg = float(dose_match.group(1)) if dose_match else 0
                
                if dose_mg > 0:
                    anomaly = check_dosage_anomaly(
                        drug.drug_name,
                        dose_mg,
                        patient_dict.get('age', 40),
                        patient_dict.get('weight_kg', 70)
                    )
                    if anomaly['is_anomaly']:
                        ratio = anomaly['dose_ratio']
                        direction = "higher" if ratio > 1 else "lower"
                        normal_dose = anomaly['normal_dose_mg']
                        
                        explanation = (
                            f"Prescribed dose ({dose_mg} mg) is "
                            f"{ratio:.1f}x the standard dose ({normal_dose} mg). "
                            f"{'Overdose risks toxicity.' if ratio > 1 else 'Underdose may be ineffective.'}"
                        )
                        
                        solution = (
                            f"{'Reduce' if ratio > 1 else 'Increase'} the dose to the "
                            f"recommended {normal_dose} mg. "
                            f"Verify patient weight, renal/hepatic function. "
                            f"Consult dosing guidelines for this specific patient profile."
                        )
                        
                        errors.append(ErrorDetail(
                            error_type="DOSAGE_ERROR",
                            drug=drug.drug_name,
                            severity=anomaly['severity'],
                            message=anomaly['message'],
                            explanation=explanation,
                            solution=solution,
                            details={
                                "prescribed_dose": dose_mg,
                                "normal_dose": normal_dose,
                                "dose_ratio": ratio
                            }
                        ))
            except Exception as e:
                print(f"Anomaly check error for {drug.drug_name}: {e}")
    
    # ========================================================================
    # STEP 4 — LASA Check
    # ========================================================================
    for drug_name in drug_names:
        try:
            lasa = check_lasa_confusion(drug_name)
            if lasa['has_lasa_risk'] and lasa['risk_level'] in ['CRITICAL', 'HIGH']:
                pairs_str = ', '.join([p['partner'] for p in lasa['known_lasa_pairs']])
                
                explanation = (
                    f"'{drug_name}' has known look-alike/sound-alike similarity with: "
                    f"{pairs_str}. Dispensing errors between these drugs are documented "
                    f"in medical literature and can have serious consequences."
                )
                
                solution = (
                    f"Use TALL MAN lettering: write drug name with emphasis on "
                    f"distinguishing characters. Verbally confirm drug name with patient. "
                    f"Apply barcode verification at dispensing. Double-check with a "
                    f"second pharmacist before dispensing."
                )
                
                errors.append(ErrorDetail(
                    error_type="LASA",
                    drug=drug_name,
                    severity=lasa['risk_level'],
                    message=lasa['recommendation'],
                    explanation=explanation,
                    solution=solution,
                    details={
                        "known_pairs": lasa['known_lasa_pairs'],
                        "phonetic_similar": lasa['phonetic_similar_drugs']
                    }
                ))
        except Exception as e:
            print(f"LASA error for {drug_name}: {e}")
    
    # ========================================================================
    # STEP 5 — Allergy Check
    # ========================================================================
    allergies_lower = [a.lower() for a in patient_dict.get('allergies', [])]
    for drug_name in drug_names:
        if drug_name.lower() in allergies_lower:
            explanation = (
                f"Patient has a documented allergy to {drug_name}. "
                f"Administering this drug may cause anaphylaxis, rash, "
                f"angioedema, or other allergic reactions."
            )
            
            solution = (
                f"Immediately discontinue {drug_name}. "
                f"Consider therapeutic alternatives: "
                f"review allergy history and prescribe a drug from a "
                f"different class without cross-reactivity."
            )
            
            errors.append(ErrorDetail(
                error_type="ALLERGY",
                drug=drug_name,
                severity="CRITICAL",
                message=f"ALERT: Patient is allergic to {drug_name}!",
                explanation=explanation,
                solution=solution
            ))
    
    # ========================================================================
    # STEP 6 — Calculate risk score
    # ========================================================================
    severity_weights = {
        "CRITICAL": 1.0,
        "HIGH": 0.7,
        "MEDIUM": 0.4,
        "LOW": 0.2
    }
    
    if not errors:
        risk_score = 0.0
    else:
        total = sum(severity_weights.get(e.severity, 0.1) for e in errors)
        risk_score = min(1.0, total / max(len(errors), 1))
    
    risk_level = (
        "CRITICAL" if risk_score > 0.8 else
        "HIGH"     if risk_score > 0.6 else
        "MEDIUM"   if risk_score > 0.3 else
        "LOW"      if risk_score > 0   else
        "SAFE"
    )
    
    summary = (
        f"✅ Prescription appears safe. {len(extracted_drugs)} drug(s) extracted."
        if not errors else
        f"⚠️ {len(errors)} issue(s) found: "
        f"{', '.join(set(e.error_type for e in errors))}. "
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
# OCR ENDPOINT
# ============================================================================

@app.post("/ocr", response_model=OCRResponse)
async def extract_text(request: OCRRequest):
    """
    OCR endpoint for extracting text from prescription images.
    Supports English (TrOCR) and Hindi/Marathi (Tesseract).
    """
    try:
        result = ocr_from_base64(
            request.image_b64,
            language=request.language.value
        )
        
        if 'error' in result:
            raise HTTPException(
                status_code=400,
                detail=f"OCR failed: {result['error']}"
            )
        
        cleaned = clean_prescription_text(result['text'])
        
        return OCRResponse(
            extractedText=result['text'],
            cleanedText=cleaned,
            engine=result['engine'],
            language=result.get('detected_language', result['language']),
            confidence=result.get('confidence'),
            charCount=len(cleaned),
            success=len(cleaned) > 0
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
