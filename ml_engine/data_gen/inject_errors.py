import pandas as pd
import json
import random
import copy
import os
from collections import defaultdict
from tqdm import tqdm
from colorama import init, Fore

# ── Init ───────────────────────────────────────────────────────────────────────
init(autoreset=True)
random.seed(42)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

# ── Load data ──────────────────────────────────────────────────────────────────
with open(os.path.join(DATA_DIR, "prescriptions.json"), encoding="utf-8") as f:
    correct_prescriptions = json.load(f)

with open(os.path.join(DATA_DIR, "patients.json"), encoding="utf-8") as f:
    patients = json.load(f)

formulary = pd.read_csv(os.path.join(DATA_DIR, "drug_formulary.csv"))
ddi_rules  = pd.read_csv(os.path.join(DATA_DIR, "ddi_rules.csv"))
lasa_pairs = pd.read_csv(os.path.join(DATA_DIR, "lasa_pairs.csv"))
diag_map   = pd.read_csv(os.path.join(DATA_DIR, "diagnosis_drug_map.csv"))

# ── Build lookups ──────────────────────────────────────────────────────────────
patient_lookup    = {p["patient_id"]: p for p in patients}
formulary_lookup  = {row["drug_name"]: row for _, row in formulary.iterrows()}
all_drug_names    = formulary["drug_name"].dropna().tolist()

# LASA: drug -> [(partner, risk_level)]
lasa_lookup = defaultdict(list)
for _, row in lasa_pairs.iterrows():
    a    = str(row["drug_a"])
    b    = str(row["drug_b"])
    risk = str(row.get("risk_level", "high"))
    lasa_lookup[a].append((b, risk))
    lasa_lookup[b].append((a, risk))

# DDI: drug -> [(partner, severity, clinical_effect)]
ddi_lookup = defaultdict(list)
for _, row in ddi_rules.iterrows():
    a   = str(row["drug_a"])
    b   = str(row["drug_b"])
    sev = str(row.get("severity", "moderate"))
    eff = str(row.get("clinical_effect", ""))
    ddi_lookup[a].append((b, sev, eff))
    ddi_lookup[b].append((a, sev, eff))

ddi_rules_list = ddi_rules.to_dict("records")

# Diagnosis -> inappropriate drugs
diag_inappropriate = defaultdict(list)
for _, row in diag_map.iterrows():
    dx      = str(row["diagnosis"])
    raw     = str(row.get("inappropriate_drugs_example", ""))
    drugs_  = [d.strip() for d in raw.split("|") if d.strip()]
    diag_inappropriate[dx] = drugs_


# ── Helpers ────────────────────────────────────────────────────────────────────
def r5(value):
    """Round to nearest 5mg, minimum 5."""
    return max(5, round(value / 5) * 5)


def drug_obj_from_formulary(drug_name, duration=7):
    """Build a drug dict from formulary or sensible defaults."""
    frow = formulary_lookup.get(drug_name)
    if frow is not None:
        try:
            dose = r5(float(frow["normal_dose_mg"]))
        except (ValueError, TypeError):
            dose = 100
        return {
            "drug_name":     drug_name,
            "rxcui":         str(frow.get("rxcui", "")),
            "dose_mg":       dose,
            "dose_unit":     str(frow.get("dose_unit", "mg")),
            "frequency":     str(frow.get("frequency", "once daily")),
            "duration_days": duration,
            "route":         "oral",
        }
    return {
        "drug_name":     drug_name,
        "rxcui":         "",
        "dose_mg":       100,
        "dose_unit":     "mg",
        "frequency":     "once daily",
        "duration_days": duration,
        "route":         "oral",
    }


def rebuild_text(rx, drugs):
    """Rebuild prescription_text after drug list is modified."""
    patient       = patient_lookup.get(rx["patient_id"], {})
    name          = patient.get("name", "Unknown")
    age           = patient.get("age", "?")
    gender        = patient.get("gender", "Unknown")
    diagnosis_str = ", ".join(patient.get("diagnosis", []))
    allergies_str = ", ".join(patient.get("allergies", [])) or "None known"

    rx_lines = "\n".join(
        f"  {idx + 1}. {d['drug_name']} {d['dose_mg']}{d['dose_unit']} "
        f"{d['frequency']} x {d['duration_days']} days"
        for idx, d in enumerate(drugs)
    )

    return (
        f"Patient: {name}, Age: {age}yrs, {gender}\n"
        f"Diagnosis: {diagnosis_str}\n"
        f"Rx:\n{rx_lines}\n"
        f"Allergies: {allergies_str}\n"
        f"Dr. ID: {rx['doctor_id']}, {rx['hospital']}"
    )


def base_copy(prescription, rx_id, error_label):
    """Deep-copy a prescription and stamp it with error metadata."""
    rx = copy.deepcopy(prescription)
    rx["prescription_id"] = rx_id
    rx["is_correct"]      = False
    rx["error_label"]     = error_label
    rx["error_types"]     = [error_label]
    return rx


# ── Error injectors ────────────────────────────────────────────────────────────
def inject_lasa(prescription, rx_id):
    rx    = base_copy(prescription, rx_id, "LASA")
    drugs = rx["prescribed_drugs"]

    for drug_obj in random.sample(drugs, len(drugs)):
        original = drug_obj["drug_name"]
        partners = lasa_lookup.get(original)
        if partners:
            confused_with, risk_level = random.choice(partners)
            drug_obj["drug_name"] = confused_with
            frow = formulary_lookup.get(confused_with)
            if frow is not None:
                drug_obj["rxcui"] = str(frow.get("rxcui", ""))
            rx["lasa_details"]       = {"original_drug": original,
                                        "confused_with": confused_with,
                                        "risk_level":    risk_level}
            rx["prescription_text"]  = rebuild_text(rx, drugs)
            return rx

    # Fallback: similar first letter
    drug_obj  = drugs[0]
    original  = drug_obj["drug_name"]
    first     = original[0].lower()
    similar   = [d for d in all_drug_names if d.lower().startswith(first) and d != original]
    confused_with = random.choice(similar) if similar else random.choice(all_drug_names)

    drug_obj["drug_name"] = confused_with
    frow = formulary_lookup.get(confused_with)
    if frow is not None:
        drug_obj["rxcui"] = str(frow.get("rxcui", ""))
    rx["lasa_details"]      = {"original_drug": original,
                               "confused_with": confused_with,
                               "risk_level":    "high"}
    rx["prescription_text"] = rebuild_text(rx, drugs)
    return rx


def inject_ddi(prescription, rx_id):
    rx              = base_copy(prescription, rx_id, "DDI")
    drugs           = rx["prescribed_drugs"]
    existing_names  = {d["drug_name"] for d in drugs}

    for drug_obj in random.sample(drugs, len(drugs)):
        name_    = drug_obj["drug_name"]
        partners = [(b, sev, eff) for b, sev, eff in ddi_lookup.get(name_, [])
                    if b not in existing_names]
        if partners:
            interacting, severity, clinical_effect = random.choice(partners)
            new_drug = drug_obj_from_formulary(interacting,
                                               duration=random.choice([7, 10, 14, 30]))
            drugs.append(new_drug)
            rx["ddi_details"]       = {"drug_a": name_, "drug_b": interacting,
                                       "severity": severity,
                                       "clinical_effect": clinical_effect}
            rx["prescription_text"] = rebuild_text(rx, drugs)
            return rx

    # Fallback: scan ddi_rules_list for any pair where one side is present
    shuffled_rules = random.sample(ddi_rules_list, len(ddi_rules_list))
    for row in shuffled_rules:
        a, b = str(row["drug_a"]), str(row["drug_b"])
        if a in existing_names and b not in existing_names:
            target, anchor = b, a
        elif b in existing_names and a not in existing_names:
            target, anchor = a, b
        else:
            continue
        new_drug = drug_obj_from_formulary(target, duration=7)
        drugs.append(new_drug)
        rx["ddi_details"]       = {"drug_a": anchor, "drug_b": target,
                                   "severity": str(row.get("severity", "moderate")),
                                   "clinical_effect": str(row.get("clinical_effect", ""))}
        rx["prescription_text"] = rebuild_text(rx, drugs)
        return rx

    # Last resort: add any two interacting drugs as extra entries
    row = random.choice(ddi_rules_list)
    new_drug = drug_obj_from_formulary(str(row["drug_a"]), duration=7)
    drugs.append(new_drug)
    rx["ddi_details"]       = {"drug_a": str(row["drug_a"]), "drug_b": str(row["drug_b"]),
                               "severity": str(row.get("severity", "moderate")),
                               "clinical_effect": str(row.get("clinical_effect", ""))}
    rx["prescription_text"] = rebuild_text(rx, drugs)
    return rx


def inject_dosage_error(prescription, rx_id):
    MULTIPLIERS = [0.1, 0.2, 3.0, 5.0, 10.0]

    rx         = base_copy(prescription, rx_id, "DOSAGE_ERROR")
    drugs      = rx["prescribed_drugs"]
    drug_obj   = random.choice(drugs)
    drug_name  = drug_obj["drug_name"]

    frow = formulary_lookup.get(drug_name)
    try:
        normal_dose = float(frow["normal_dose_mg"]) if frow is not None \
                      else float(drug_obj.get("dose_mg", 100))
    except (ValueError, TypeError):
        normal_dose = float(drug_obj.get("dose_mg", 100))

    multiplier          = random.choice(MULTIPLIERS)
    wrong_dose          = round(normal_dose * multiplier, 1)
    drug_obj["dose_mg"] = wrong_dose

    rx["dosage_details"]     = {"drug_name":       drug_name,
                                "prescribed_dose": wrong_dose,
                                "normal_dose":     normal_dose,
                                "multiplier":      multiplier}
    rx["prescription_text"]  = rebuild_text(rx, drugs)
    return rx


def inject_indication_mismatch(prescription, rx_id):
    rx       = base_copy(prescription, rx_id, "INDICATION_MISMATCH")
    drugs    = rx["prescribed_drugs"]
    patient  = patient_lookup.get(prescription["patient_id"], {})
    diagnoses = patient.get("diagnosis", [])
    existing  = {d["drug_name"] for d in drugs}

    # Try patient's actual diagnoses first
    options = []
    for dx in diagnoses:
        for wrong_drug in diag_inappropriate.get(dx, []):
            if wrong_drug not in existing:
                options.append((wrong_drug, dx))

    if not options:
        # Fallback: scan all diagnoses for any inappropriate drug
        for dx, inapprop_list in diag_inappropriate.items():
            for wrong_drug in inapprop_list:
                if wrong_drug not in existing:
                    options.append((wrong_drug, dx))

    if options:
        wrong_drug, source_dx = random.choice(options)
        drug_obj              = random.choice(drugs)
        original_drug         = drug_obj["drug_name"]

        frow = formulary_lookup.get(wrong_drug)
        drug_obj["drug_name"] = wrong_drug
        if frow is not None:
            drug_obj["rxcui"] = str(frow.get("rxcui", ""))
            try:
                drug_obj["dose_mg"] = r5(float(frow["normal_dose_mg"]))
            except (ValueError, TypeError):
                pass
            drug_obj["dose_unit"]  = str(frow.get("dose_unit", "mg"))
            drug_obj["frequency"]  = str(frow.get("frequency", "once daily"))

        patient_dx_str = diagnoses[0] if diagnoses else source_dx
        rx["mismatch_details"]   = {
            "drug_name":        wrong_drug,
            "patient_diagnosis": patient_dx_str,
            "why_inappropriate": f"{wrong_drug} is not appropriate for {patient_dx_str}"
        }
        rx["prescription_text"]  = rebuild_text(rx, drugs)
        return rx

    # Absolute fallback: use a random drug not in formulary indications
    random_drug = random.choice(all_drug_names)
    drug_obj    = random.choice(drugs)
    drug_obj["drug_name"]    = random_drug
    rx["mismatch_details"]   = {
        "drug_name":        random_drug,
        "patient_diagnosis": diagnoses[0] if diagnoses else "unknown",
        "why_inappropriate": f"{random_drug} contraindicated for patient condition"
    }
    rx["prescription_text"]  = rebuild_text(rx, drugs)
    return rx


# ── Generate error prescriptions ───────────────────────────────────────────────
ERROR_CONFIGS = [
    ("LASA",                 750, inject_lasa),
    ("DDI",                  750, inject_ddi),
    ("DOSAGE_ERROR",         750, inject_dosage_error),
    ("INDICATION_MISMATCH",  750, inject_indication_mismatch),
]

error_prescriptions = []
error_idx = 1

for error_type, count, inject_fn in ERROR_CONFIGS:
    for _ in tqdm(range(count), desc=f"Injecting {error_type:<22}", unit="rx"):
        base_rx  = random.choice(correct_prescriptions)
        error_rx = inject_fn(base_rx, f"RXE{str(error_idx).zfill(5)}")
        error_prescriptions.append(error_rx)
        error_idx += 1

# ── Combine, shuffle, save ─────────────────────────────────────────────────────
augmented = correct_prescriptions + error_prescriptions
random.seed(42)
random.shuffle(augmented)

aug_path   = os.path.join(DATA_DIR, "augmented_prescriptions.json")
stats_path = os.path.join(DATA_DIR, "dataset_stats.json")

with open(aug_path, "w", encoding="utf-8") as f:
    json.dump(augmented, f, indent=2, ensure_ascii=False)

stats = {
    "total":           8000,
    "correct":         5000,
    "with_errors":     3000,
    "error_breakdown": {
        "LASA":                 750,
        "DDI":                  750,
        "DOSAGE_ERROR":         750,
        "INDICATION_MISMATCH":  750,
    },
    "class_balance": "37.5% errors / 62.5% correct",
}

with open(stats_path, "w", encoding="utf-8") as f:
    json.dump(stats, f, indent=2)

# ── Print summary ──────────────────────────────────────────────────────────────
print(Fore.GREEN  + f"✅ Augmented dataset: {len(augmented)} records")
print(Fore.YELLOW + f"⚠️  Error records: 3000 (37.5%)")
print(Fore.GREEN  + f"✅ Correct records: 5000 (62.5%)")
print(Fore.GREEN  + f"📁 Saved: {aug_path}")
print(Fore.GREEN  + f"📊 Saved: {stats_path}")
