import pandas as pd
import json
import random
import os
from faker import Faker
from tqdm import tqdm
from colorama import init, Fore, Style

# ── Init ───────────────────────────────────────────────────────────────────────
init(autoreset=True)
random.seed(42)

fake = Faker("en_IN")
Faker.seed(42)

# ── Load data ──────────────────────────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

formulary = pd.read_csv(os.path.join(DATA_DIR, "drug_formulary.csv"))
diag_map  = pd.read_csv(os.path.join(DATA_DIR, "diagnosis_drug_map.csv"))

drug_names   = formulary["drug_name"].dropna().tolist()
diagnoses    = diag_map["diagnosis"].dropna().tolist()

# ── Constants ──────────────────────────────────────────────────────────────────
BLOOD_GROUPS   = ["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-"]
CITIES         = [
    "Mumbai", "Delhi", "Nagpur", "Pune", "Bangalore",
    "Chennai", "Hyderabad", "Kolkata", "Jaipur", "Ahmedabad",
]
COMORBIDITIES  = [
    "Obesity", "Smoking", "Alcohol use", "CKD stage 2",
    "Mild hepatic impairment", "Osteoporosis", "Depression",
]
NUM_PATIENTS   = 5000


def pick_allergies():
    roll = random.random()
    if roll < 0.30:
        return []
    elif roll < 0.70:
        return random.sample(drug_names, 1)
    else:
        return random.sample(drug_names, min(2, len(drug_names)))


def pick_medications(patient_diagnoses):
    if random.random() < 0.20:
        return []

    meds = []
    for dx in patient_diagnoses:
        row = diag_map[diag_map["diagnosis"] == dx]
        if row.empty:
            continue
        appropriate = str(row.iloc[0]["appropriate_drugs"])
        candidates  = [d.strip() for d in appropriate.split("|") if d.strip()]
        if candidates:
            meds.extend(random.sample(candidates, min(2, len(candidates))))

    # Deduplicate and cap at 4
    seen, unique = set(), []
    for m in meds:
        if m not in seen:
            seen.add(m)
            unique.append(m)
        if len(unique) == 4:
            break
    return unique


def pick_comorbidities():
    if random.random() < 0.40:
        return []
    return random.sample(COMORBIDITIES, random.randint(1, 2))


# ── Generate ───────────────────────────────────────────────────────────────────
patients = []

for i in tqdm(range(NUM_PATIENTS), desc="Generating patients", unit="patient"):
    patient_diagnoses = random.sample(diagnoses, random.randint(1, min(3, len(diagnoses))))

    patient = {
        "patient_id":          f"PAT{str(i + 1).zfill(5)}",
        "name":                fake.name(),
        "age":                 random.randint(18, 85),
        "gender":              random.choice(["Male", "Female"]),
        "blood_group":         random.choice(BLOOD_GROUPS),
        "weight_kg":           round(random.uniform(40, 110), 1),
        "city":                random.choice(CITIES),
        "phone":               fake.phone_number(),
        "diagnosis":           patient_diagnoses,
        "allergies":           pick_allergies(),
        "current_medications": pick_medications(patient_diagnoses),
        "comorbidities":       pick_comorbidities(),
    }
    patients.append(patient)

# ── Save ───────────────────────────────────────────────────────────────────────
out_path = os.path.join(DATA_DIR, "patients.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(patients, f, indent=2, ensure_ascii=False)

# ── Stats ──────────────────────────────────────────────────────────────────────
ages             = [p["age"] for p in patients]
age_mean         = sum(ages) / len(ages)
age_min          = min(ages)
age_max          = max(ages)

from collections import Counter
all_diagnoses    = [dx for p in patients for dx in p["diagnosis"]]
top_3            = [d for d, _ in Counter(all_diagnoses).most_common(3)]

with_allergies   = sum(1 for p in patients if p["allergies"])
allergy_pct      = with_allergies / NUM_PATIENTS * 100

print(Fore.GREEN  + f"✅ Generated {NUM_PATIENTS} patients → {out_path}")
print(Fore.YELLOW + f"📊 Age distribution: mean={age_mean:.1f}, min={age_min}, max={age_max}")
print(Fore.YELLOW + f"🏥 Top diagnoses: {top_3}")
print(Fore.YELLOW + f"💊 Patients with allergies: {with_allergies} ({allergy_pct:.1f}%)")
