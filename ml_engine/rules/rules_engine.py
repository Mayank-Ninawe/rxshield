import re
import difflib
from typing import List, Dict, Optional

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 0 — BRAND TO GENERIC MAPPING
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BRAND_TO_GENERIC = {
    # Common brand names → generic (INN) names
    "beteloe":      "metoprolol",
    "betaloc":      "metoprolol",
    "betalol":      "metoprolol",
    "meteloc":      "metoprolol",
    "dorzolamidum": "dorzolamide",
    "dorzolam":     "dorzolamide",
    "oxprelol":     "oxprenolol",
    "oxprenelol":   "oxprenolol",
    "cimetidin":    "cimetidine",
    "cimetidim":    "cimetidine",
    "amoxicilin":   "amoxicillin",
    "amoxycillin":  "amoxicillin",
    "paracetamol":  "paracetamol",
    "parcetamol":   "paracetamol",
    "metfromin":    "metformin",
    "metfomin":     "metformin",
    "atorvastin":   "atorvastatin",
    "atorvasttin":  "atorvastatin",
    "amlodipine":   "amlodipine",
    "amlodipin":    "amlodipine",
    "lisinopil":    "lisinopril",
    "lissinopril":  "lisinopril",
    "ciprofloxacin":"ciprofloxacin",
    "ciprofloxacn": "ciprofloxacin",
    "warfrin":      "warfarin",
    "warfarine":    "warfarin",
    "diclofenec":   "diclofenac",
    "diclofenack":  "diclofenac",
    "ibeprofen":    "ibuprofen",
    "ibuprofen":    "ibuprofen",
    "ibuprofin":    "ibuprofen",
    "omeprazol":    "omeprazole",
    "pantoprazol":  "pantoprazole",
    "azithromycn":  "azithromycin",
    "azithromicin": "azithromycin",
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 1 — COMPREHENSIVE DDI DATABASE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DDI_DATABASE = [
  # Format: (drug_a, drug_b, severity, mechanism, explanation, solution)
  
  # ── WARFARIN INTERACTIONS (CRITICAL) ────────────────────────────────────
  ("warfarin","aspirin","CRITICAL",
   "Additive anticoagulant + antiplatelet effect",
   "Warfarin + Aspirin: Warfarin inhibits clotting factors while aspirin "
   "inhibits platelet aggregation. Combined use dramatically increases "
   "risk of serious bleeding — GI bleed, intracranial hemorrhage.",
   "Avoid concurrent use. If antiplatelet therapy needed, use lowest "
   "effective aspirin dose (75mg) only with close INR monitoring. "
   "Consider alternative antiplatelet if combination unavoidable."),

  ("warfarin","ibuprofen","HIGH",
   "NSAID displaces warfarin from protein binding + GI irritation",
   "NSAIDs like Ibuprofen displace warfarin from plasma proteins, "
   "raising free warfarin levels. Also causes GI mucosal damage "
   "increasing bleeding risk.",
   "Replace Ibuprofen with Paracetamol (acetaminophen) for pain relief "
   "in anticoagulated patients. Monitor INR closely if NSAID unavoidable."),

  ("warfarin","diclofenac","HIGH",
   "NSAID-warfarin interaction: elevated INR + GI bleed risk",
   "Diclofenac inhibits COX-1/COX-2 and displaces warfarin from "
   "albumin binding, increasing bleeding risk significantly.",
   "Substitute with Paracetamol. If Diclofenac must be used, "
   "reduce warfarin dose, monitor INR every 3-4 days."),

  ("warfarin","naproxen","HIGH",
   "NSAID-warfarin interaction",
   "Naproxen + Warfarin: Enhanced bleeding risk due to combined "
   "anticoagulant and antiplatelet effects.",
   "Use Paracetamol instead. Monitor INR if combination required."),

  ("warfarin","clarithromycin","HIGH",
   "CYP3A4 inhibition increases warfarin levels",
   "Clarithromycin inhibits CYP3A4, reducing warfarin metabolism "
   "and significantly raising INR.",
   "Monitor INR closely. Consider reducing warfarin dose by 25-50% "
   "during antibiotic course."),

  ("warfarin","erythromycin","HIGH",
   "CYP3A4 inhibition increases warfarin levels",
   "Erythromycin inhibits CYP3A4 enzyme, slowing warfarin breakdown "
   "and increasing bleeding risk.",
   "Monitor INR closely. Azithromycin is a safer alternative "
   "antibiotic in anticoagulated patients."),

  ("warfarin","metronidazole","HIGH",
   "CYP2C9 inhibition dramatically increases warfarin effect",
   "Metronidazole strongly inhibits CYP2C9, the main enzyme "
   "metabolizing warfarin-S (active form). INR can double.",
   "Avoid combination. If unavoidable, reduce warfarin dose "
   "by 25-50% and monitor INR every 2-3 days."),

  ("warfarin","fluconazole","CRITICAL",
   "CYP2C9 inhibition — INR can triple",
   "Fluconazole is a potent CYP2C9 and CYP3A4 inhibitor. "
   "Can cause life-threatening bleeding by tripling warfarin levels.",
   "Avoid concurrent use. Use topical antifungal if possible. "
   "If systemic antifungal needed, reduce warfarin dose 50% "
   "and monitor INR daily."),

  ("warfarin","tramadol","HIGH",
   "CYP2C9 inhibition + serotonergic effect",
   "Tramadol inhibits CYP2C9 and has serotonergic activity. "
   "Combined with warfarin increases bleeding risk and seizure risk.",
   "Monitor INR closely. Consider alternative analgesic."),

  # ── ASPIRIN INTERACTIONS ─────────────────────────────────────────────────
  ("aspirin","clopidogrel","HIGH",
   "Dual antiplatelet therapy — increased bleeding",
   "Aspirin + Clopidogrel (dual antiplatelet) significantly increases "
   "major bleeding risk. Only justified post-stent/ACS with close monitoring.",
   "Only use dual antiplatelet when clinically indicated (ACS/stent). "
   "Use PPI cover (Pantoprazole). Limit duration per guidelines."),

  ("aspirin","ibuprofen","MEDIUM",
   "Ibuprofen blocks aspirin's antiplatelet effect",
   "Ibuprofen competes with aspirin for COX-1 binding, potentially "
   "blocking aspirin's cardioprotective antiplatelet effect.",
   "Take aspirin 30+ min before ibuprofen, or use "
   "Paracetamol instead of Ibuprofen."),

  ("aspirin","ketorolac","CRITICAL",
   "Dual NSAIDs: severe GI bleed + renal risk",
   "Aspirin + Ketorolac (Toradol): Both NSAIDs together dramatically "
   "increase GI bleeding, ulceration, and renal failure risk.",
   "Never co-prescribe two NSAIDs. Use one NSAID only. "
   "Add PPI if NSAID + aspirin combination is unavoidable."),

  # ── BETA BLOCKERS ────────────────────────────────────────────────────────
  ("metoprolol","verapamil","CRITICAL",
   "Additive AV node blockade — cardiac arrest risk",
   "Metoprolol (beta-blocker) + Verapamil (calcium channel blocker): "
   "Both depress AV node conduction. Can cause complete heart block, "
   "severe bradycardia, or cardiac arrest.",
   "This combination is generally contraindicated. If both must be "
   "used, start at very low doses with continuous cardiac monitoring."),

  ("metoprolol","diltiazem","HIGH",
   "Additive AV node and cardiac depression",
   "Diltiazem + Metoprolol: Both slow heart rate and depress "
   "cardiac conduction. Risk of severe bradycardia and heart block.",
   "Use with extreme caution. Monitor heart rate. "
   "Prefer amlodipine (dihydropyridine CCB) instead of Diltiazem."),

  ("atenolol","verapamil","CRITICAL",
   "Additive AV node blockade — cardiac arrest risk",
   "Atenolol + Verapamil: High risk of complete heart block. "
   "Both agents depress AV nodal conduction additively.",
   "Contraindicated combination. Use dihydropyridine CCB "
   "(Amlodipine) if calcium channel blocker needed with beta-blocker."),

  ("betaloc","oxprenolol","CRITICAL",
   "Double beta-blocker — additive bradycardia",
   "Betaloc (Metoprolol) + Oxprenolol are BOTH beta-blockers. "
   "Prescribing two beta-blockers simultaneously is never indicated. "
   "Risk of severe bradycardia, heart block, and hypotension.",
   "Use only ONE beta-blocker. Choose metoprolol OR oxprenolol "
   "based on indication, not both together."),

  ("metoprolol","oxprenolol","CRITICAL",
   "Double beta-blocker — never indicated",
   "Two beta-blockers prescribed simultaneously. This is a "
   "prescribing error — additive bradycardia and heart block risk.",
   "Use only ONE beta-blocker. Remove one from the prescription."),

  # ── CIMETIDINE INTERACTIONS (CYP inhibitor) ──────────────────────────────
  ("cimetidine","metoprolol","HIGH",
   "CYP2D6 inhibition — metoprolol toxicity",
   "Cimetidine inhibits CYP2D6, the primary enzyme metabolizing "
   "metoprolol. This can increase metoprolol levels by 30-100%, "
   "causing excessive beta-blockade, severe bradycardia, hypotension.",
   "Replace cimetidine with Famotidine or Ranitidine (do not inhibit "
   "CYP2D6). Or reduce metoprolol dose and monitor heart rate."),

  ("cimetidine","warfarin","HIGH",
   "CYP1A2/2C9 inhibition increases warfarin levels",
   "Cimetidine inhibits multiple CYP enzymes including CYP2C9 "
   "used for warfarin metabolism, leading to increased INR.",
   "Replace with Famotidine. If Cimetidine must be used, "
   "monitor INR closely and adjust warfarin dose."),

  ("cimetidine","phenytoin","HIGH",
   "CYP inhibition — phenytoin toxicity",
   "Cimetidine reduces phenytoin clearance, raising serum levels "
   "and risking phenytoin toxicity (nystagmus, ataxia, confusion).",
   "Replace Cimetidine with Famotidine or Omeprazole. "
   "Monitor phenytoin levels."),

  # ── SSRI / SEROTONIN INTERACTIONS ────────────────────────────────────────
  ("sertraline","tramadol","HIGH",
   "Serotonin syndrome risk",
   "Both sertraline (SSRI) and tramadol have serotonergic activity. "
   "Combination can cause serotonin syndrome: agitation, hyperthermia, "
   "tremor, seizures — potentially fatal.",
   "Avoid combination. If pain relief needed, use non-serotonergic "
   "analgesic (Paracetamol, NSAIDs with GI cover)."),

  ("fluoxetine","tramadol","HIGH",
   "Serotonin syndrome + CYP2D6 inhibition",
   "Fluoxetine inhibits CYP2D6 AND has serotonergic activity. "
   "Tramadol levels rise AND serotonin syndrome risk increases.",
   "Use non-serotonergic analgesic. If tramadol needed, "
   "use minimum effective dose with close monitoring."),

  ("sertraline","linezolid","CRITICAL",
   "Serotonin syndrome — potentially fatal",
   "Linezolid has MAO inhibitor activity. SSRIs + MAOIs = "
   "severe serotonin syndrome with hyperthermia, seizures, death.",
   "CONTRAINDICATED. Do not use together. "
   "Allow 2-week washout between MAOI and SSRI."),

  # ── ACE INHIBITORS + POTASSIUM ────────────────────────────────────────────
  ("lisinopril","spironolactone","HIGH",
   "Hyperkalaemia risk",
   "ACE inhibitors (Lisinopril) + Potassium-sparing diuretics "
   "(Spironolactone) can cause life-threatening hyperkalaemia "
   "(elevated potassium leading to cardiac arrhythmias).",
   "Monitor serum potassium closely (weekly initially). "
   "Keep K+ below 5.5 mEq/L. Reduce or stop one agent if K+ rises."),

  ("ramipril","spironolactone","HIGH",
   "Hyperkalaemia — cardiac arrhythmia risk",
   "Ramipril (ACE inhibitor) + Spironolactone: Additive potassium "
   "retention. Risk of hyperkalaemia and fatal arrhythmia.",
   "Monitor potassium levels weekly. Avoid if eGFR < 30. "
   "Use caution in diabetics and elderly."),

  # ── ANTIBIOTICS ───────────────────────────────────────────────────────────
  ("metformin","contrast","HIGH",
   "Metformin + contrast media: lactic acidosis risk",
   "IV contrast agents cause transient renal impairment, "
   "reducing metformin clearance and risking lactic acidosis.",
   "Hold metformin 48 hours before and after IV contrast. "
   "Restart only after renal function confirmed normal."),

  ("ciprofloxacin","theophylline","HIGH",
   "CYP1A2 inhibition — theophylline toxicity",
   "Ciprofloxacin inhibits CYP1A2, reducing theophylline clearance "
   "and causing toxicity: nausea, arrhythmias, seizures.",
   "Reduce theophylline dose by 30-50%. Monitor theophylline levels. "
   "Consider azithromycin as safer antibiotic alternative."),

  # ── DIGOXIN ───────────────────────────────────────────────────────────────
  ("digoxin","furosemide","HIGH",
   "Hypokalaemia from furosemide potentiates digoxin toxicity",
   "Furosemide causes potassium loss. Hypokalaemia makes the heart "
   "more sensitive to digoxin, risking fatal arrhythmias.",
   "Monitor serum K+ and digoxin levels. "
   "Give potassium supplementation. Keep K+ > 3.5 mEq/L."),

  ("digoxin","amiodarone","CRITICAL",
   "Amiodarone inhibits P-gp — digoxin toxicity",
   "Amiodarone inhibits P-glycoprotein, reducing digoxin renal "
   "elimination and causing digoxin toxicity (bradycardia, AV block).",
   "Reduce digoxin dose by 50% when starting amiodarone. "
   "Monitor digoxin levels and ECG closely."),

  # ── STATINS ───────────────────────────────────────────────────────────────
  ("atorvastatin","clarithromycin","HIGH",
   "CYP3A4 inhibition — statin myopathy risk",
   "Clarithromycin inhibits CYP3A4, increasing atorvastatin levels "
   "and risk of myopathy and rhabdomyolysis.",
   "Temporarily suspend atorvastatin during clarithromycin course. "
   "Or use Pravastatin (not CYP3A4 metabolized) if statin needed."),

  ("simvastatin","amlodipine","MEDIUM",
   "Amlodipine moderately inhibits CYP3A4 — simvastatin levels rise",
   "Amlodipine can modestly increase simvastatin levels, "
   "raising myopathy risk slightly.",
   "Cap simvastatin at 20mg when combined with amlodipine. "
   "Consider switching to Rosuvastatin or Atorvastatin."),

  # ── TRAMADOL / CODEINE ────────────────────────────────────────────────────
  ("tramadol","codeine","HIGH",
   "Double opioid — additive CNS and respiratory depression",
   "Two opioid analgesics together cause additive CNS depression, "
   "respiratory depression, sedation, and overdose risk.",
   "Use only ONE opioid analgesic at a time. "
   "Combine with non-opioid (Paracetamol/NSAID) instead."),

  ("tramadol","diazepam","HIGH",
   "CNS depression — respiratory failure risk",
   "Tramadol + Benzodiazepine (Diazepam): Synergistic CNS and "
   "respiratory depression. Risk of fatal respiratory arrest.",
   "Avoid combination. If both essential, use minimum doses "
   "with respiratory monitoring."),

  # ── METFORMIN ─────────────────────────────────────────────────────────────
  ("metformin","alcohol","HIGH",
   "Lactic acidosis risk with excessive alcohol",
   "Alcohol impairs lactate metabolism, and combined with metformin "
   "can trigger potentially fatal lactic acidosis.",
   "Advise patient to avoid excessive alcohol. "
   "Warn about signs: muscle pain, weakness, breathing difficulty."),

  # ── NSAIDs + RENAL/HTN ────────────────────────────────────────────────────
  ("ibuprofen","lisinopril","HIGH",
   "NSAIDs blunt ACE inhibitor effect + renal impairment",
   "NSAIDs reduce prostaglandin-mediated renal vasodilation, "
   "blunting ACE inhibitor antihypertensive effect and "
   "risking acute kidney injury especially in elderly/dehydrated.",
   "Use Paracetamol for pain relief in patients on ACE inhibitors. "
   "If NSAID needed short-term, monitor renal function."),

  ("diclofenac","lisinopril","HIGH",
   "NSAIDs blunt ACE inhibitor + renal risk",
   "Diclofenac reduces effectiveness of Lisinopril and "
   "can precipitate acute renal failure in susceptible patients.",
   "Paracetamol preferred. Monitor BP and renal function "
   "if NSAID unavoidable."),
]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 2 — DOSAGE DATABASE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Format: drug_name_lower → (min_dose_mg, max_dose_mg, typical_dose_mg, unit_note)
DOSAGE_DATABASE = {
  "metformin":       (250,  2000, 500,   "500-1000mg BD typical; max 2000mg/day"),
  "metformin er":    (500,  2000, 1000,  "Extended release; max 2000mg/day"),
  "aspirin":         (75,   1000, 300,   "75mg cardio / 300-600mg analgesic"),
  "atorvastatin":    (10,   80,   20,    "10-80mg once daily"),
  "simvastatin":     (5,    40,   20,    "10-40mg at night; max 40mg with amlo"),
  "amlodipine":      (2.5,  10,   5,     "5-10mg once daily"),
  "lisinopril":      (2.5,  40,   10,    "10-40mg once daily"),
  "ramipril":        (1.25, 10,   5,     "5-10mg once daily"),
  "atenolol":        (25,   100,  50,    "50-100mg once daily"),
  "metoprolol":      (25,   200,  50,    "50-100mg BD or 100-200mg SR once daily"),
  "betaloc":         (25,   200,  50,    "Metoprolol brand; 50-100mg BD"),
  "warfarin":        (1,    10,   5,     "Dose individualised by INR; typical 2-10mg"),
  "digoxin":         (0.0625, 0.25, 0.125, "0.0625-0.25mg once daily"),
  "furosemide":      (20,   80,   40,    "20-80mg once or twice daily"),
  "paracetamol":     (250,  1000, 500,   "500-1000mg every 4-6h; max 4g/day"),
  "ibuprofen":       (200,  800,  400,   "200-400mg TID; max 1200mg OTC/2400mg Rx"),
  "diclofenac":      (25,   75,   50,    "50mg BD or 75mg BD"),
  "omeprazole":      (10,   40,   20,    "20-40mg once daily"),
  "pantoprazole":    (20,   80,   40,    "40mg once daily"),
  "amoxicillin":     (250,  1000, 500,   "250-500mg TID; 875mg BD for severe"),
  "azithromycin":    (250,  500,  500,   "500mg day 1 then 250mg days 2-5"),
  "ciprofloxacin":   (250,  750,  500,   "500mg BD; 750mg for severe"),
  "clarithromycin":  (250,  500,  500,   "250-500mg BD"),
  "metronidazole":   (200,  800,  400,   "400mg TID or 500mg BD"),
  "cetirizine":      (5,    10,   10,    "10mg once daily"),
  "levothyroxine":   (25,   300,  100,   "Typically 50-200mcg; dose per TSH"),
  "prednisolone":    (5,    60,   20,    "Dose varies widely by indication"),
  "tramadol":        (50,   100,  50,    "50-100mg every 4-6h; max 400mg/day"),
  "codeine":         (15,   60,   30,    "15-60mg every 4-6h; max 240mg/day"),
  "morphine":        (5,    30,   10,    "5-30mg every 4h; highly variable"),
  "glimepiride":     (1,    8,    2,     "1-4mg once daily; max 8mg"),
  "glibenclamide":   (2.5,  20,   5,     "2.5-10mg once daily; max 20mg"),
  "sitagliptin":     (25,   100,  100,   "100mg once daily; 50mg if eGFR 30-50"),
  "carbamazepine":   (100,  400,  200,   "100-400mg BD"),
  "phenytoin":       (100,  300,  200,   "100-300mg once daily; monitor levels"),
  "cimetidine":      (200,  800,  400,   "200-400mg BD or 400mg BD; NOT 50mg"),
  "ranitidine":      (75,   300,  150,   "150mg BD or 300mg at night"),
  "spironolactone":  (25,   200,  50,    "25-100mg once daily"),
  "telmisartan":     (20,   80,   40,    "40-80mg once daily"),
  "losartan":        (25,   100,  50,    "50-100mg once daily"),
  "valsartan":       (40,   320,  160,   "80-160mg once daily"),
  "salbutamol":      (2,    8,    4,     "2-4mg TID/QID or inhaler 100-200mcg"),
  "theophylline":    (100,  400,  200,   "Monitor serum levels; narrow TI"),
  "insulin":         (4,    100,  20,    "Dose individualised; U per injection"),
  "dorzolamide":     (10,   10,   10,    "Eye drops 2% — oral tablets unusual"),
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 3 — HELPER FUNCTIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def normalise(name: str) -> str:
    """Lowercase, strip, resolve brand→generic, fuzzy fallback."""
    if not name:
        return ""
    n = name.lower().strip()
    n = re.sub(r'\s+', ' ', n)
    
    # Direct brand→generic lookup
    resolved = BRAND_TO_GENERIC.get(n, n)
    if resolved != n:
        return resolved
    
    # If already in known drug list, return as-is
    all_known = list(DOSAGE_DATABASE.keys()) + list(BRAND_TO_GENERIC.keys())
    if resolved in all_known:
        return resolved
    
    # Fuzzy match against known drug names (handles OCR typos)
    matches = difflib.get_close_matches(
        resolved,
        all_known,
        n=1,
        cutoff=0.75    # 75% similarity threshold
    )
    if matches:
        best = matches[0]
        # Resolve brand→generic on fuzzy match too
        return BRAND_TO_GENERIC.get(best, best)
    
    return resolved  # return as-is if no fuzzy match


def parse_dose_mg(dose_str: Optional[str]) -> Optional[float]:
    """
    Extract numeric dose value from dose string.
    Examples: "500mg" -> 500.0, "1.25 mg" -> 1.25
    """
    if not dose_str:
        return None
    
    # Extract first number from string
    match = re.search(r'(\d+\.?\d*)', str(dose_str))
    if match:
        return float(match.group(1))
    return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 4 — DETECTION FUNCTIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def check_ddi(drug_names: List[str]) -> List[Dict]:
    """
    Check for drug-drug interactions using DDI_DATABASE.
    Returns list of DDI errors found.
    """
    errors = []
    normalized_drugs = [normalise(d) for d in drug_names]
    
    for i, drug_a in enumerate(normalized_drugs):
        for j, drug_b in enumerate(normalized_drugs):
            if i >= j:  # Avoid duplicate checks
                continue
            
            # Check both directions in DDI_DATABASE
            for ddi_a, ddi_b, severity, mechanism, explanation, solution in DDI_DATABASE:
                if (drug_a == ddi_a and drug_b == ddi_b) or \
                   (drug_a == ddi_b and drug_b == ddi_a):
                    errors.append({
                        "error_type": "DDI",
                        "drug_a": drug_names[i],
                        "drug_b": drug_names[j],
                        "severity": severity,
                        "message": f"{drug_names[i]} + {drug_names[j]}: {mechanism}",
                        "explanation": explanation,
                        "solution": solution,
                        "confidence": 0.95,
                        "details": {
                            "mechanism": mechanism,
                            "interaction_type": "drug-drug"
                        }
                    })
    
    return errors


def check_dosage_errors(extracted_drugs: List[Dict]) -> List[Dict]:
    """
    Check for dosage errors using DOSAGE_DATABASE.
    extracted_drugs: [{"drug_name": "Metformin", "dose": "500mg"}, ...]
    """
    errors = []
    
    for drug_info in extracted_drugs:
        drug_name = normalise(drug_info.get("drug_name", ""))
        dose_str = drug_info.get("dose")
        
        if drug_name not in DOSAGE_DATABASE:
            continue
        
        dose_mg = parse_dose_mg(dose_str)
        if dose_mg is None:
            continue
        
        min_dose, max_dose, typical_dose, note = DOSAGE_DATABASE[drug_name]
        
        # Check if dose is outside safe range
        if dose_mg < min_dose or dose_mg > max_dose:
            if dose_mg < min_dose:
                severity = "MEDIUM" if dose_mg >= min_dose * 0.5 else "HIGH"
                message = f"{drug_info['drug_name']}: Dose {dose_mg}mg is below minimum safe dose ({min_dose}mg)"
                explanation = (
                    f"Prescribed dose ({dose_mg}mg) is below the therapeutic range. "
                    f"Minimum effective dose is {min_dose}mg. Underdosing may result in "
                    f"treatment failure or disease progression."
                )
                solution = (
                    f"Increase dose to at least {min_dose}mg (typical: {typical_dose}mg). "
                    f"Verify patient-specific factors. {note}"
                )
            else:  # dose_mg > max_dose
                severity = "HIGH" if dose_mg <= max_dose * 1.5 else "CRITICAL"
                message = f"{drug_info['drug_name']}: Dose {dose_mg}mg exceeds maximum safe dose ({max_dose}mg)"
                explanation = (
                    f"Prescribed dose ({dose_mg}mg) exceeds maximum safe dose ({max_dose}mg). "
                    f"Overdosing significantly increases risk of toxicity and adverse effects."
                )
                solution = (
                    f"Reduce dose to maximum {max_dose}mg (typical: {typical_dose}mg). "
                    f"Monitor for toxicity. {note}"
                )
            
            errors.append({
                "error_type": "DOSAGE_ERROR",
                "drug": drug_info['drug_name'],
                "severity": severity,
                "message": message,
                "explanation": explanation,
                "solution": solution,
                "confidence": 0.90,
                "details": {
                    "prescribed_dose_mg": dose_mg,
                    "min_safe_dose_mg": min_dose,
                    "max_safe_dose_mg": max_dose,
                    "typical_dose_mg": typical_dose,
                    "dosage_note": note
                }
            })
    
    return errors


def check_allergy(drug_names: List[str], patient_data: Dict) -> List[Dict]:
    """
    Check if patient is allergic to any prescribed drugs.
    """
    errors = []
    allergies = patient_data.get("allergies", [])
    
    if not allergies:
        return errors
    
    allergies_normalized = [normalise(a) for a in allergies]
    
    for drug_name in drug_names:
        if normalise(drug_name) in allergies_normalized:
            errors.append({
                "error_type": "ALLERGY",
                "drug": drug_name,
                "severity": "CRITICAL",
                "message": f"ALERT: Patient is allergic to {drug_name}!",
                "explanation": (
                    f"Patient has a documented allergy to {drug_name}. "
                    f"Administering this drug may cause anaphylaxis, rash, "
                    f"angioedema, or other severe allergic reactions."
                ),
                "solution": (
                    f"Immediately discontinue {drug_name}. "
                    f"Consider therapeutic alternatives from a different drug class "
                    f"without cross-reactivity. Review allergy history."
                ),
                "confidence": 1.0,
                "details": {
                    "allergy_list": allergies
                }
            })
    
    return errors


def check_indication_mismatch(drug_names: List[str], patient_data: Dict) -> List[Dict]:
    """
    Simple indication mismatch checking based on common drug-diagnosis relationships.
    This is a basic implementation - can be expanded with more comprehensive data.
    """
    errors = []
    diagnosis_list = patient_data.get("diagnosis", [])
    
    if not diagnosis_list:
        return errors
    
    # Simple indication map (expandable)
    indication_map = {
        "metformin": ["diabetes", "type 2 diabetes", "t2dm", "prediabetes"],
        "insulin": ["diabetes", "type 1 diabetes", "type 2 diabetes", "t1dm", "t2dm"],
        "glimepiride": ["diabetes", "type 2 diabetes", "t2dm"],
        "atorvastatin": ["hyperlipidemia", "high cholesterol", "dyslipidemia", "cvd"],
        "simvastatin": ["hyperlipidemia", "high cholesterol", "dyslipidemia"],
        "lisinopril": ["hypertension", "high blood pressure", "heart failure", "htn"],
        "amlodipine": ["hypertension", "high blood pressure", "angina", "htn"],
        "warfarin": ["atrial fibrillation", "dvt", "thrombosis", "stroke prevention"],
        "aspirin": ["cvd", "stroke", "mi", "heart disease", "cardiovascular"],
        "levothyroxine": ["hypothyroidism", "thyroid", "hashimoto"],
    }
    
    diagnosis_lower = [d.lower() for d in diagnosis_list]
    
    for drug_name in drug_names:
        drug_normalized = normalise(drug_name)
        
        if drug_normalized in indication_map:
            expected_conditions = indication_map[drug_normalized]
            
            # Check if any diagnosis matches expected conditions
            has_match = any(
                any(cond in diag for cond in expected_conditions)
                for diag in diagnosis_lower
            )
            
            if not has_match:
                errors.append({
                    "error_type": "INDICATION_MISMATCH",
                    "drug": drug_name,
                    "severity": "MEDIUM",
                    "message": f"{drug_name} may not be indicated for current diagnosis",
                    "explanation": (
                        f"{drug_name} is typically indicated for: {', '.join(expected_conditions)}. "
                        f"Patient's diagnosis: {', '.join(diagnosis_list)}. "
                        f"This may be appropriate off-label use, but requires verification."
                    ),
                    "solution": (
                        f"Verify clinical rationale for prescribing {drug_name} for this diagnosis. "
                        f"If off-label use is intended, document justification. "
                        f"Consider alternatives specifically indicated for {', '.join(diagnosis_list)}."
                    ),
                    "confidence": 0.70,
                    "details": {
                        "expected_indications": expected_conditions,
                        "patient_diagnosis": diagnosis_list
                    }
                })
    
    return errors


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 5 — MAIN ENTRY POINT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def run_all_checks(
    drug_names: List[str],
    patient_data: Dict,
    extracted_drugs: List[Dict]
) -> Dict:
    """
    Run all 4 error detection checks.
    
    Args:
        drug_names: List of drug names ["Metformin", "Aspirin"]
        patient_data: Patient info dict with diagnosis, allergies, etc.
        extracted_drugs: List of dicts [{"drug_name": "Metformin", "dose": "500mg"}]
    
    Returns:
        {
            "errors": [list of error dicts],
            "summary": "..."
        }
    """
    all_errors = []
    
    # 1. DDI Check
    ddi_errors = check_ddi(drug_names)
    all_errors.extend(ddi_errors)
    
    # 2. Dosage Error Check
    dosage_errors = check_dosage_errors(extracted_drugs)
    all_errors.extend(dosage_errors)
    
    # 3. Allergy Check
    allergy_errors = check_allergy(drug_names, patient_data)
    all_errors.extend(allergy_errors)
    
    # 4. Indication Mismatch Check
    indication_errors = check_indication_mismatch(drug_names, patient_data)
    all_errors.extend(indication_errors)
    
    # Generate summary
    error_counts = {}
    for err in all_errors:
        error_type = err["error_type"]
        error_counts[error_type] = error_counts.get(error_type, 0) + 1
    
    summary = f"Found {len(all_errors)} total issues: " + ", ".join(
        f"{count} {etype}" for etype, count in error_counts.items()
    ) if all_errors else "No issues detected"
    
    return {
        "errors": all_errors,
        "summary": summary,
        "total_errors": len(all_errors),
        "error_counts": error_counts
    }
