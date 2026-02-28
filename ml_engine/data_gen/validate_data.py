import pandas as pd
import json
import random
import os
from collections import Counter
from colorama import init, Fore, Style

# ── Init ───────────────────────────────────────────────────────────────────────
init(autoreset=True)
random.seed(42)

DATA_DIR    = os.path.join(os.path.dirname(__file__), "..", "data")
REPORT_PATH = os.path.join(DATA_DIR, "validation_report.txt")

report_lines = []
passed = 0
failed = 0


def log(line, color=None):
    """Print with optional color and append plain text to report."""
    if color:
        print(color + line)
    else:
        print(line)
    report_lines.append(line)


def check(label, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        log(f"  ✅ {label}" + (f" — {detail}" if detail else ""), Fore.GREEN)
    else:
        failed += 1
        log(f"  ❌ {label}" + (f" — {detail}" if detail else ""), Fore.RED)
    return condition


# ══════════════════════════════════════════════════════════════════════════════
# CHECK 1 — File existence
# ══════════════════════════════════════════════════════════════════════════════
log("\n── CHECK 1: File Existence ──────────────────────────────────────────────")

REQUIRED_FILES = [
    "patients.json",
    "prescriptions.json",
    "augmented_prescriptions.json",
    "drug_formulary.csv",
    "lasa_pairs.csv",
    "ddi_rules.csv",
    "diagnosis_drug_map.csv",
    "dataset_stats.json",
]

files_ok = True
for fname in REQUIRED_FILES:
    exists = os.path.isfile(os.path.join(DATA_DIR, fname))
    check(fname, exists, "found" if exists else "MISSING")
    if not exists:
        files_ok = False

if not files_ok:
    log("\n⛔ Critical files missing — cannot continue validation.", Fore.RED)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
    raise SystemExit(1)

# ── Load all data ──────────────────────────────────────────────────────────────
with open(os.path.join(DATA_DIR, "patients.json"), encoding="utf-8") as f:
    patients = json.load(f)

with open(os.path.join(DATA_DIR, "augmented_prescriptions.json"), encoding="utf-8") as f:
    augmented = json.load(f)

with open(os.path.join(DATA_DIR, "prescriptions.json"), encoding="utf-8") as f:
    correct_prescriptions = json.load(f)

formulary = pd.read_csv(os.path.join(DATA_DIR, "drug_formulary.csv"))

# ══════════════════════════════════════════════════════════════════════════════
# CHECK 2 — Patient data quality
# ══════════════════════════════════════════════════════════════════════════════
log("\n── CHECK 2: Patient Data Quality ────────────────────────────────────────")

check("Total records", len(patients) == 5000,
      f"found {len(patients)}, expected 5000")

patient_ids = [p["patient_id"] for p in patients]
check("No duplicate patient_ids", len(patient_ids) == len(set(patient_ids)),
      f"{len(patient_ids) - len(set(patient_ids))} duplicates found")

ages = [p.get("age") for p in patients]
ages_ok = all(isinstance(a, int) and 18 <= a <= 85 for a in ages)
age_min  = min(ages)
age_max  = max(ages)
check("Age range 18–85", ages_ok, f"min={age_min}, max={age_max}")

REQUIRED_PATIENT_FIELDS = [
    "patient_id", "name", "age", "gender",
    "diagnosis", "allergies", "current_medications",
]
for field in REQUIRED_PATIENT_FIELDS:
    missing = sum(1 for p in patients if field not in p)
    check(f"Field '{field}' present", missing == 0,
          f"{missing} records missing" if missing else "all present")

# ══════════════════════════════════════════════════════════════════════════════
# CHECK 3 — Prescription data quality
# ══════════════════════════════════════════════════════════════════════════════
log("\n── CHECK 3: Prescription Data Quality ───────────────────────────────────")

total_rx   = len(augmented)
correct_rx = sum(1 for rx in augmented if rx.get("is_correct") is True)
error_rx   = sum(1 for rx in augmented if rx.get("is_correct") is False)

check("Total records", total_rx == 8000, f"found {total_rx}, expected 8000")
check("Correct prescriptions", correct_rx == 5000,
      f"found {correct_rx}, expected 5000")
check("Error prescriptions", error_rx == 3000,
      f"found {error_rx}, expected 3000")

rx_ids = [rx["prescription_id"] for rx in augmented]
check("No duplicate prescription_ids",
      len(rx_ids) == len(set(rx_ids)),
      f"{len(rx_ids) - len(set(rx_ids))} duplicates found")

no_drugs = sum(
    1 for rx in augmented
    if not isinstance(rx.get("prescribed_drugs"), list)
    or len(rx["prescribed_drugs"]) == 0
)
check("All prescriptions have ≥1 drug", no_drugs == 0,
      f"{no_drugs} prescriptions with 0 drugs" if no_drugs else "all have drugs")

bool_ok = all(isinstance(rx.get("is_correct"), bool) for rx in augmented)
check("is_correct is always boolean", bool_ok)

bad_error_types = sum(
    1 for rx in augmented
    if rx.get("is_correct") is False
    and (not isinstance(rx.get("error_types"), list)
         or len(rx["error_types"]) == 0)
)
check("Error prescriptions have non-empty error_types", bad_error_types == 0,
      f"{bad_error_types} error records missing error_types" if bad_error_types else "all present")

# Error type distribution
error_type_counts = Counter(
    rx["error_types"][0]
    for rx in augmented
    if rx.get("is_correct") is False
    and isinstance(rx.get("error_types"), list)
    and rx["error_types"]
)
log("  📊 Error type distribution:", Fore.YELLOW)
for etype, count in sorted(error_type_counts.items()):
    log(f"       {etype:<25} {count}", Fore.YELLOW)

# ══════════════════════════════════════════════════════════════════════════════
# CHECK 4 — Drug formulary quality
# ══════════════════════════════════════════════════════════════════════════════
log("\n── CHECK 4: Drug Formulary Quality ──────────────────────────────────────")

drug_count = len(formulary)
check("Drug count", drug_count == 40, f"found {drug_count}, expected 40")

dup_drugs = formulary["drug_name"].dropna().duplicated().sum()
check("No duplicate drug_names", dup_drugs == 0,
      f"{dup_drugs} duplicates" if dup_drugs else "all unique")

bad_doses = (pd.to_numeric(formulary["normal_dose_mg"], errors="coerce").fillna(0) <= 0).sum()
check("All normal_dose_mg > 0", bad_doses == 0,
      f"{bad_doses} invalid doses" if bad_doses else "all valid")

if "drug_class" in formulary.columns:
    class_counts = formulary["drug_class"].value_counts()
    log("  📊 Drug count by class:", Fore.YELLOW)
    for cls, cnt in class_counts.items():
        log(f"       {cls:<30} {cnt}", Fore.YELLOW)

# ══════════════════════════════════════════════════════════════════════════════
# CHECK 5 — Cross-reference check
# ══════════════════════════════════════════════════════════════════════════════
log("\n── CHECK 5: Cross-Reference Check ───────────────────────────────────────")

formulary_drugs = set(formulary["drug_name"].dropna().tolist())
patient_id_set  = set(patient_ids)

# Error prescriptions are allowed to have drugs outside the formulary
error_rx_ids = {
    rx["prescription_id"]
    for rx in augmented
    if rx.get("is_correct") is False
}

sample_100 = random.sample(augmented, 100)
xref_passed = 0

for rx in sample_100:
    pid_ok   = rx.get("patient_id") in patient_id_set
    is_error = rx.get("prescription_id") in error_rx_ids

    if is_error:
        # For error prescriptions only check patient_id
        if pid_ok:
            xref_passed += 1
    else:
        # For correct prescriptions check both patient_id and drugs in formulary
        drugs_ok = all(
            d.get("drug_name") in formulary_drugs
            for d in rx.get("prescribed_drugs", [])
        )
        if pid_ok and drugs_ok:
            xref_passed += 1

xref_ok = xref_passed >= 90  # allow 10% tolerance for edge cases
check(f"Cross-reference check: {xref_passed}/100 passed", xref_ok,
      f"{xref_passed}/100 ({100-xref_passed} failed)")

# ══════════════════════════════════════════════════════════════════════════════
# Final summary
# ══════════════════════════════════════════════════════════════════════════════
log("\n── Summary ──────────────────────────────────────────────────────────────")
log(f"  ✅ Passed: {passed}", Fore.GREEN)
log(f"  ❌ Failed: {failed}", Fore.RED)

all_ok = failed == 0
verdict = "Data is ready for ML training ✅" if all_ok else "Fix issues before training ⚠️"
log(f"\n  {verdict}", Fore.GREEN if all_ok else Fore.YELLOW)

# ── Save report ────────────────────────────────────────────────────────────────
with open(REPORT_PATH, "w", encoding="utf-8") as f:
    f.write("\n".join(report_lines))

log(f"\n📄 Report saved: {REPORT_PATH}", Fore.GREEN)
