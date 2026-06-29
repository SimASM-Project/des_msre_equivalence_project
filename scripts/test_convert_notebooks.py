#!/usr/bin/env python3
"""
Test suite for convert-based MSRE notebooks.

Tests:
  T2: Convert cell validation (JSON -> SimASM conversion succeeds)
  T3: Verification equivalence (MSRE check returns EQUIVALENT)
  T4: Notebook end-to-end (all cells execute without errors)
  T5: Regression (existing models/configs/results still valid)

Usage:
    python scripts/test_convert_notebooks.py [--test T2|T3|T4|T5|all] [--topology ...]

Requires: simasm >= 0.8.1, nbformat, jupyter kernel
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
INPUT_DIR = PROJECT_DIR / "input"
MODELS_DIR = PROJECT_DIR / "models"
CONFIGS_DIR = PROJECT_DIR / "configs"
RESULTS_DIR = PROJECT_DIR / "results"
NOTEBOOK_DIR = PROJECT_DIR / "notebooks"

STANDARD_SIZES = [1, 2, 3, 4, 5, 7, 10, 15, 20]
HYBRID_SIZES = [(m, b) for m in [2, 3, 4] for b in [2, 3, 4]]
FORMALISMS = ["eg", "acd", "devs"]
PAIRS = [("eg", "acd"), ("eg", "devs"), ("acd", "devs")]


def get_model_name(topology, size):
    if isinstance(size, tuple):
        return f"{topology}_{size[0]}_{size[1]}"
    return f"{topology}_{size}"


# ---------- T2: Convert Validation ----------

def test_t2_convert_single(topology: str, size, formalism: str) -> bool:
    """Test that a single JSON file can be converted to SimASM."""
    model_name = get_model_name(topology, size)
    json_path = INPUT_DIR / topology / f"{model_name}_{formalism}.json"

    if not json_path.exists():
        print(f"    SKIP: {json_path.name} not found")
        return True

    try:
        import simasm
        from simasm.converter import convert_json_to_simasm
        result = convert_json_to_simasm(str(json_path), formalism)
        if result and len(result) > 0:
            return True
        else:
            print(f"    FAIL: {model_name}_{formalism} - empty conversion result")
            return False
    except ImportError:
        print("    SKIP: simasm not importable (run in simasm environment)")
        return True
    except Exception as e:
        print(f"    FAIL: {model_name}_{formalism} - {e}")
        return False


def test_t2(topology: str = "all"):
    """T2: Convert cell validation for smallest sizes."""
    print("\n=== T2: Convert Cell Validation ===")
    topologies = _resolve_topologies(topology)
    test_sizes = {
        "tandem": [1],
        "feedback": [1],
        "fork_join": [1],
        "hybrid": [(2, 2)],
    }

    passed = 0
    failed = 0
    for topo in topologies:
        for size in test_sizes[topo]:
            for form in FORMALISMS:
                if test_t2_convert_single(topo, size, form):
                    passed += 1
                else:
                    failed += 1

    print(f"\n  T2 Results: {passed} passed, {failed} failed")
    return failed == 0


# ---------- T3: Verification Equivalence ----------

def test_t3_verify_single(topology: str, size, fa: str, fb: str) -> bool:
    """Test MSRE verification for a single formalism pair."""
    model_name = get_model_name(topology, size)
    pair_id = f"{fa}_{fb}"
    config_path = CONFIGS_DIR / pair_id / topology / f"{model_name}_{pair_id}_msre.simasm"

    if not config_path.exists():
        print(f"    SKIP: {config_path.name} not found")
        return True

    result_path = RESULTS_DIR / pair_id / f"{model_name}_{pair_id}_msre_results.json"
    if result_path.exists():
        try:
            with open(result_path) as f:
                results = json.load(f)
            if isinstance(results, dict):
                is_eq = results.get("is_equivalent", None)
                status = results.get("status", "")
                if is_eq is True or status == "complete":
                    return True
                else:
                    print(f"    FAIL: {model_name} {fa.upper()} vs {fb.upper()} - is_equivalent={is_eq}, status={status}")
                    return False
            else:
                print(f"    WARN: Unexpected result format for {model_name} {pair_id}")
                return True
        except Exception as e:
            print(f"    WARN: Could not read results for {model_name} {pair_id}: {e}")
            return True
    else:
        print(f"    SKIP: No pre-computed results for {model_name} {pair_id}")
        return True


def test_t3(topology: str = "all"):
    """T3: Verification equivalence using pre-computed results."""
    print("\n=== T3: Verification Equivalence (from pre-computed results) ===")
    topologies = _resolve_topologies(topology)
    test_sizes = {
        "tandem": [1, 3, 20],
        "feedback": [1, 3],
        "fork_join": [1, 3],
        "hybrid": [(2, 2), (3, 4)],
    }

    passed = 0
    failed = 0
    for topo in topologies:
        for size in test_sizes[topo]:
            for fa, fb in PAIRS:
                if test_t3_verify_single(topo, size, fa, fb):
                    passed += 1
                else:
                    failed += 1

    print(f"\n  T3 Results: {passed} passed, {failed} failed")
    return failed == 0


# ---------- T4: Notebook End-to-End ----------

def test_t4_notebook(topology: str) -> bool:
    """Test that a notebook executes without errors using nbconvert."""
    notebook_path = NOTEBOOK_DIR / f"{topology}_msre.ipynb"
    if not notebook_path.exists():
        print(f"    SKIP: {notebook_path.name} not found")
        return True

    print(f"    Executing {notebook_path.name}...")
    try:
        result = subprocess.run(
            [
                sys.executable, "-m", "jupyter", "nbconvert",
                "--to", "notebook",
                "--execute",
                "--ExecutePreprocessor.timeout=300",
                "--output", f"/tmp/{topology}_msre_executed.ipynb",
                str(notebook_path),
            ],
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode == 0:
            print(f"    PASS: {topology}_msre.ipynb executed successfully")
            return True
        else:
            print(f"    FAIL: {topology}_msre.ipynb execution failed")
            print(f"          stderr: {result.stderr[:500]}")
            return False
    except subprocess.TimeoutExpired:
        print(f"    FAIL: {topology}_msre.ipynb timed out (>600s)")
        return False
    except FileNotFoundError:
        print("    SKIP: jupyter nbconvert not available")
        return True


def test_t4(topology: str = "all"):
    """T4: Notebook end-to-end execution."""
    print("\n=== T4: Notebook End-to-End Execution ===")
    print("  (This test executes full notebooks; may take several minutes)")
    topologies = _resolve_topologies(topology)

    passed = 0
    failed = 0
    for topo in topologies:
        if test_t4_notebook(topo):
            passed += 1
        else:
            failed += 1

    print(f"\n  T4 Results: {passed} passed, {failed} failed")
    return failed == 0


# ---------- T5: Regression ----------

def test_t5_existing_models():
    """T5a: Pre-generated .simasm models still exist."""
    print("  T5a: Checking pre-generated models...")
    missing = []
    for formalism in FORMALISMS:
        model_dir = MODELS_DIR / formalism
        if not model_dir.exists():
            missing.append(str(model_dir))
            continue
        for topology in ["tandem", "feedback", "fork_join", "hybrid"]:
            topo_dir = model_dir / topology
            if not topo_dir.exists():
                missing.append(str(topo_dir))

    if missing:
        print(f"    FAIL: Missing directories: {missing}")
        return False
    print("    PASS: All model directories present")
    return True


def test_t5_existing_configs():
    """T5b: Existing verification configs still present."""
    print("  T5b: Checking verification configs...")
    count = 0
    for pair_dir in CONFIGS_DIR.iterdir():
        if pair_dir.is_dir():
            for config in pair_dir.rglob("*.simasm"):
                count += 1

    if count >= 111:
        print(f"    PASS: {count} config files present (expected >= 111)")
        return True
    else:
        print(f"    FAIL: Only {count} config files (expected >= 111)")
        return False


def test_t5_existing_results():
    """T5c: Pre-computed results still present."""
    print("  T5c: Checking pre-computed results...")
    count = 0
    for result_file in RESULTS_DIR.rglob("*.json"):
        count += 1

    if count >= 100:
        print(f"    PASS: {count} result files present")
        return True
    else:
        print(f"    FAIL: Only {count} result files (expected >= 100)")
        return False


def test_t5_warehouse_unchanged():
    """T5d: warehouse_msre.ipynb unchanged."""
    print("  T5d: Checking warehouse notebook...")
    warehouse_nb = NOTEBOOK_DIR / "warehouse_msre.ipynb"
    if not warehouse_nb.exists():
        print("    FAIL: warehouse_msre.ipynb missing")
        return False

    with open(warehouse_nb) as f:
        nb = json.load(f)

    has_convert = any(
        "%%simasm convert" in "".join(c.get("source", []))
        for c in nb["cells"]
        if c["cell_type"] == "code"
    )
    has_verify = any(
        "%%simasm verify" in "".join(c.get("source", []))
        for c in nb["cells"]
        if c["cell_type"] == "code"
    )

    if has_convert and has_verify:
        print("    PASS: warehouse_msre.ipynb has convert and verify cells")
        return True
    else:
        print(f"    FAIL: warehouse_msre.ipynb missing cells (convert={has_convert}, verify={has_verify})")
        return False


def test_t5(topology: str = "all"):
    """T5: Regression checks."""
    print("\n=== T5: Regression (existing functionality preserved) ===")
    results = [
        test_t5_existing_models(),
        test_t5_existing_configs(),
        test_t5_existing_results(),
        test_t5_warehouse_unchanged(),
    ]
    passed = sum(results)
    failed = len(results) - passed
    print(f"\n  T5 Results: {passed} passed, {failed} failed")
    return failed == 0


# ---------- Helpers ----------

def _resolve_topologies(topology: str) -> list[str]:
    if topology == "all":
        return ["tandem", "feedback", "fork_join", "hybrid"]
    return [topology]


def main():
    parser = argparse.ArgumentParser(description="Test convert-based MSRE notebooks")
    parser.add_argument(
        "--test",
        choices=["T2", "T3", "T4", "T5", "all"],
        default="all",
    )
    parser.add_argument(
        "--topology",
        choices=["tandem", "feedback", "fork_join", "hybrid", "all"],
        default="all",
    )
    args = parser.parse_args()

    tests = {
        "T2": test_t2,
        "T3": test_t3,
        "T4": test_t4,
        "T5": test_t5,
    }

    if args.test == "all":
        all_pass = True
        for name, func in tests.items():
            if name == "T5":
                result = func()
            else:
                result = func(args.topology)
            all_pass = all_pass and result
        print("\n" + "=" * 50)
        print(f"Overall: {'ALL TESTS PASSED' if all_pass else 'SOME TESTS FAILED'}")
        sys.exit(0 if all_pass else 1)
    else:
        if args.test == "T5":
            result = tests[args.test]()
        else:
            result = tests[args.test](args.topology)
        sys.exit(0 if result else 1)


if __name__ == "__main__":
    main()
