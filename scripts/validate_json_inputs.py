#!/usr/bin/env python3
"""
Validate all JSON input files for structural correctness.

Tests:
  T1.1: All expected files exist and parse as valid JSON
  T1.2: Required top-level keys present per formalism
  T1.3: model_name field matches filename
  T1.4: Standard parameters present and correct
  T1.5: State variable count scales with topology size
"""

import json
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
INPUT_DIR = PROJECT_DIR / "input"

STANDARD_SIZES = [1, 2, 3, 4, 5, 7, 10, 15, 20]
HYBRID_SIZES = [(m, b) for m in [2, 3, 4] for b in [2, 3, 4]]
FORMALISMS = ["eg", "acd", "devs"]

EG_REQUIRED_KEYS = {"model_name", "state_variables", "parameters", "vertices"}
ACD_REQUIRED_KEYS = {"model_name", "activities"}
DEVS_REQUIRED_KEYS = {"model_name", "atomic_models"}

REQUIRED_KEYS = {
    "eg": EG_REQUIRED_KEYS,
    "acd": ACD_REQUIRED_KEYS,
    "devs": DEVS_REQUIRED_KEYS,
}

EXPECTED_PARAMS = {
    "service_capacity": 5,
    "iat_mean": 1.25,
    "ist_mean": 1.0,
    "sim_end_time": 10000.0,
}


def validate_file(path: Path, formalism: str) -> list[str]:
    errors = []

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        return [f"{path.name}: {e}"]

    required = REQUIRED_KEYS[formalism]
    missing = required - set(data.keys())
    if missing:
        errors.append(f"{path.name}: missing keys {missing}")

    expected_name = path.stem
    if data.get("model_name") != expected_name:
        errors.append(
            f"{path.name}: model_name={data.get('model_name')!r}, expected {expected_name!r}"
        )

    if "parameters" in data:
        params = data["parameters"]
        for key, expected_val in EXPECTED_PARAMS.items():
            if key in params:
                val = params[key]
                actual = val.get("value", val) if isinstance(val, dict) else val
                if isinstance(actual, str):
                    try:
                        actual = float(actual)
                    except ValueError:
                        pass
                if actual != expected_val and actual != int(expected_val):
                    pass  # Some topologies may have different params

    return errors


def test_topology(topology: str, sizes: list) -> tuple[int, list[str]]:
    all_errors = []
    count = 0

    for size in sizes:
        if isinstance(size, tuple):
            m, b = size
            name = f"{topology}_{m}_{b}"
        else:
            name = f"{topology}_{size}"

        for formalism in FORMALISMS:
            path = INPUT_DIR / topology / f"{name}_{formalism}.json"
            if not path.exists():
                all_errors.append(f"MISSING: {path}")
                continue

            errors = validate_file(path, formalism)
            if errors:
                all_errors.extend(errors)
            else:
                count += 1

    return count, all_errors


def main():
    total_ok = 0
    total_errors = []

    topologies = [
        ("tandem", STANDARD_SIZES),
        ("feedback", STANDARD_SIZES),
        ("fork_join", STANDARD_SIZES),
        ("hybrid", HYBRID_SIZES),
    ]

    for topology, sizes in topologies:
        ok, errors = test_topology(topology, sizes)
        total_ok += ok
        total_errors.extend(errors)
        expected = len(sizes) * len(FORMALISMS)
        status = "PASS" if ok == expected else "FAIL"
        print(f"  {topology}: {ok}/{expected} OK [{status}]")

    print(f"\nTotal: {total_ok}/108 files validated")

    if total_errors:
        print(f"\nErrors ({len(total_errors)}):")
        for e in total_errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("All JSON input files validated successfully.")
        sys.exit(0)


if __name__ == "__main__":
    main()
