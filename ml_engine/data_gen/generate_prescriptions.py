import pandas as pd
import json
import random
import os
from datetime import date, timedelta
from collections import Counter
from tqdm import tqdm
from colorama import init, Fore

# ── Init ───────────────────────────────────────────────────────────────────────
init(autoreset=True)
random.seed(42)

# ── Paths ──────────────────────────────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

# ── Load data ──────────────────────────────────────────────────────────────────
with open(os.path.join(DATA_DIR, "patients.json"), encoding="utf-8") as f:
    patients = json.load(f)

formulary = pd.read_csv(os.path.join(DATA_DIR, "drug_formulary.csv"))
diag_map  = pd.read_csv(os.path.join(DATA_DIR, "diagnosis_drug_map.csv"))

# Build lookup dicts for fast access
formulary_lookup = {
    row["drug_name"]: row
    for _, row in formulary.iterrows()
}
diag_lookup = {
    row["diagnosis"]: row
    for _, row in diag_map.iterrows()
}

# ── Constants ──────────────────────────────────────────────────────────────────
HOSPITALS = [
    "AIIMS Nagpur", "City Hospital", "Apollo", "Fortis",
    "Government Medical College", "Rainbow Clinic", "Medanta", "Wockhardt",
]
DURATIONS = [3, 5, 7, 10, 14, 30, 60, 90]

# Weighted route selection: 80% oral, 10% IV, 10% split among rest
ROUTE_OPTIONS  = ["oral", "IV", "topical", "inhaled", "sublingual"]
ROUTE_WEIGHTS  = [0.80, 0.10, 0.04, 0.04, 0.02]

TODAY = date.today()


def weighted_route():
    return random.choices(ROUTE_OPTIONS, weights=ROUTE_WEIGHTS, k=1)[0]


def round_to_nearest_5(value):
    return max(5, round(value / 5) * 5)


def build_prescribed_drugs(patient):
    """Pick drugs based on diagnoses, apply dose variation, cap at 4."""
    drugs = []
    seen  = set()

    for dx in patient.get("diagnosis", []):
        row = diag_lookup.get(dx)
        if row is None:
            continue

        candidates = [d.strip() for d in str(row["appropriate_drugs"]).split("|") if d.strip()]
        selected   = random.sample(candidates, min(2, len(candidates)))

        for drug_name in selected:
            if drug_name in seen or len(drugs) >= 4:
                break
            seen.add(drug_name)

            frow = formulary_lookup.get(drug_name)
            if frow is None:
                continue

            try:
                base_dose = float(frow["normal_dose_mg"])
            except (ValueError, TypeError):
                base_dose = 100.0

            varied_dose = round_to_nearest_5(base_dose * random.uniform(0.9, 1.1))

            drugs.append({
                "drug_name":    drug_name,
                "rxcui":        str(frow.get("rxcui", "")),
                "dose_mg":      varied_dose,
                "dose_unit":    str(frow.get("dose_unit", "mg")),
                "frequency":    str(frow.get("frequency", "once daily")),
                "duration_days": random.choice(DURATIONS),
                "route":        weighted_route(),
            })

    # Ensure at least 1 drug — fall back to a random formulary drug
    if not drugs:
        frow = formulary.sample(1).iloc[0]
        try:
            base_dose = float(frow["normal_dose_mg"])
        except (ValueError, TypeError):
            base_dose = 100.0

        drugs.append({
            "drug_name":    frow["drug_name"],
            "rxcui":        str(frow.get("rxcui", "")),
            "dose_mg":      round_to_nearest_5(base_dose * random.uniform(0.9, 1.1)),
            "dose_unit":    str(frow.get("dose_unit", "mg")),
            "frequency":    str(frow.get("frequency", "once daily")),
            "duration_days": random.choice(DURATIONS),
            "route":        weighted_route(),
        })

    return drugs


def build_prescription_text(patient, drugs, doctor_id, hospital):
    diagnosis_str  = ", ".join(patient.get("diagnosis", []))
    allergies_str  = ", ".join(patient.get("allergies", [])) or "None known"

    rx_lines = "\n".join(
        f"  {idx + 1}. {d['drug_name']} {d['dose_mg']}{d['dose_unit']} "
        f"{d['frequency']} x {d['duration_days']} days"
        for idx, d in enumerate(drugs)
    )

    return (
        f"Patient: {patient['name']}, Age: {patient['age']}yrs, {patient['gender']}\n"
        f"Diagnosis: {diagnosis_str}\n"
        f"Rx:\n{rx_lines}\n"
        f"Allergies: {allergies_str}\n"
        f"Dr. ID: {doctor_id}, {hospital}"
    )


# ── Generate ───────────────────────────────────────────────────────────────────
prescriptions = []

for i, patient in enumerate(tqdm(patients, desc="Generating prescriptions", unit="rx")):
    doctor_id = f"DOC{random.randint(1, 50):03d}"
    hospital  = random.choice(HOSPITALS)
    rx_date   = str(TODAY - timedelta(days=random.randint(0, 365)))

    drugs = build_prescribed_drugs(patient)

    prescription = {
        "prescription_id":   f"RX{str(i + 1).zfill(5)}",
        "patient_id":        patient["patient_id"],
        "doctor_id":         doctor_id,
        "hospital":          hospital,
        "date":              rx_date,
        "prescribed_drugs":  drugs,
        "prescription_text": build_prescription_text(patient, drugs, doctor_id, hospital),
        "error_label":       "none",
        "error_types":       [],
        "is_correct":        True,
    }
    prescriptions.append(prescription)

# ── Save ───────────────────────────────────────────────────────────────────────
out_path = os.path.join(DATA_DIR, "prescriptions.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(prescriptions, f, indent=2, ensure_ascii=False)

# ── Stats ──────────────────────────────────────────────────────────────────────
all_drug_names  = [d["drug_name"] for rx in prescriptions for d in rx["prescribed_drugs"]]
avg_drugs       = len(all_drug_names) / len(prescriptions)
top_drug, top_count = Counter(all_drug_names).most_common(1)[0]

print(Fore.GREEN  + f"✅ Generated {len(prescriptions)} prescriptions → {out_path}")
print(Fore.YELLOW + f"📋 Avg drugs per prescription: {avg_drugs:.2f}")
print(Fore.YELLOW + f"🏥 Most common drug: {top_drug} ({top_count} times)")
