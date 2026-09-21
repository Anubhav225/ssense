#!/usr/bin/env python3
import json
import sys
from pathlib import Path

# Add slm-server to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from security import validate_and_repair_report

raw_from_model = {
    "global_legal_reasoning": "No explicit, active contradictions of the DPDP Act 2023 or DPDP Rules 2025 were found in the policy text.",
    "violations": [],
    "schema_version": "1.0",
    "rules_applied": [],
    "dpdp_trust_score": 50,
    "subtlety_score": 0
}

raw_str = json.dumps(raw_from_model)
repaired = validate_and_repair_report(raw_str)
print("SUCCESS! Repaired report:")
print(json.dumps(repaired, indent=2))
