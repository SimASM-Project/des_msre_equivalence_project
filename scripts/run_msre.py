#!/usr/bin/env python3
"""
Incremental MSRE runner with resume support.

Saves results after each seed so progress survives interruptions.
Checks for existing results and skips completed configs.

Usage:
    python scripts/run_msre.py                          # run all 111 configs
    python scripts/run_msre.py --pair eg_acd             # run only EG-ACD pair
    python scripts/run_msre.py --pair eg_devs             # run only EG-DEVS pair
    python scripts/run_msre.py --pair acd_devs            # run only ACD-DEVS pair
    python scripts/run_msre.py --pair eg_acd --topology tandem  # filter further
    python scripts/run_msre.py --pair eg_acd --name tandem_2    # name substring
    python scripts/run_msre.py --status                  # show progress only
"""

import sys
import json
import time
import argparse
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR.parent.parent))

from simasm.verification.run_verification_msre import run_single_seed_msre
from simasm.verification.run_verification import load_verification_spec

CONFIGS_DIR = PROJECT_DIR / "configs"
RESULTS_DIR = PROJECT_DIR / "results"


def find_configs(pair_filter=None, topology_filter=None, name_filter=None):
    configs = []
    for pair_dir in sorted(CONFIGS_DIR.iterdir()):
        if not pair_dir.is_dir():
            continue
        if pair_filter and pair_dir.name != pair_filter:
            continue
        for topo_dir in sorted(pair_dir.iterdir()):
            if not topo_dir.is_dir():
                continue
            if topology_filter and topo_dir.name != topology_filter:
                continue
            for config_file in sorted(topo_dir.glob("*.simasm")):
                if name_filter and name_filter not in config_file.stem:
                    continue
                configs.append(config_file)
    return configs


def get_result_path(spec, base_path):
    if spec.output.file_path:
        return base_path / spec.output.file_path
    return None


def load_existing_results(result_path):
    if result_path and result_path.exists():
        try:
            with open(result_path) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None
    return None


def save_results(result_path, spec, seed_results, failed_seeds, run_length=None):
    all_equivalent = len(failed_seeds) == 0
    equivalent_count = len(seed_results) - len(failed_seeds)
    rl = run_length or spec.check.run_length or 100.0

    output = {
        "verification": spec.name,
        "check_type": "macro_step_refinement",
        "seeds": [r["seed"] for r in seed_results],
        "num_seeds": len(seed_results),
        "target_seeds": len(spec.seeds),
        "run_length": rl,
        "equivalent_count": equivalent_count,
        "failed_seeds": failed_seeds,
        "is_equivalent": all_equivalent,
        "complete": len(seed_results) == len(spec.seeds),
        "status": "EQUIVALENT" if all_equivalent else "NOT_EQUIVALENT",
        "per_seed_results": seed_results,
    }

    result_path.parent.mkdir(parents=True, exist_ok=True)
    with open(result_path, "w") as f:
        json.dump(output, f, indent=2)


def check_progress(config_path):
    try:
        spec = load_verification_spec(str(config_path))
    except Exception:
        return 0, 0, "ERROR"

    result_path = get_result_path(spec, config_path.parent)
    existing = load_existing_results(result_path)

    total = len(spec.seeds)
    if not existing:
        return 0, total, "PENDING"

    completed = len(existing.get("per_seed_results", []))
    if completed >= total:
        status = existing.get("status", "EQUIVALENT")
        return completed, total, status
    return completed, total, "IN_PROGRESS"


def run_config_incremental(config_path, run_length_override=None, verbose=True):
    base_path = config_path.parent
    spec = load_verification_spec(str(config_path))
    run_length = run_length_override or spec.check.run_length or 100.0
    result_path = get_result_path(spec, base_path)

    if not result_path:
        if verbose:
            print(f"  SKIP {config_path.stem}: no output path")
        return "SKIP"

    existing = load_existing_results(result_path)
    completed_seeds = set()
    seed_results = []
    failed_seeds = []

    if existing:
        existing_rl = existing.get("run_length", 100.0)
        if abs(existing_rl - run_length) > 0.1:
            if verbose:
                print(f"  RESET {config_path.stem}: run_length changed ({existing_rl} -> {run_length})")
        else:
            for sr in existing.get("per_seed_results", []):
                completed_seeds.add(sr["seed"])
                seed_results.append(sr)
                if not sr.get("is_equivalent", False):
                    failed_seeds.append(sr["seed"])

    remaining = [s for s in spec.seeds if s not in completed_seeds]

    if not remaining:
        if verbose:
            status = existing.get("status", "DONE")
            print(f"  SKIP {config_path.stem} ({len(completed_seeds)}/{len(spec.seeds)} done, {status})")
        return existing.get("status", "EQUIVALENT")

    if verbose:
        print(f"  {config_path.stem}: {len(completed_seeds)}/{len(spec.seeds)} done, "
              f"{len(remaining)} remaining (T={run_length})", flush=True)

    for i, seed in enumerate(remaining):
        if verbose:
            print(f"    [{len(completed_seeds)+i+1}/{len(spec.seeds)}] seed {seed}...",
                  end="", flush=True)
        t0 = time.time()

        seed_timeout = spec.check.timeout or 60
        try:
            result = run_single_seed_msre(spec, base_path, seed, run_length)
            elapsed = time.time() - t0

            if elapsed > seed_timeout:
                raise TimeoutError(f"seed took {elapsed:.0f}s (limit {seed_timeout}s)")

            seed_results.append(result)
            if not result["is_equivalent"]:
                failed_seeds.append(seed)

            save_results(result_path, spec, seed_results, failed_seeds, run_length)

            if verbose:
                summary = result.get("step_profile_summary", {})
                m_mean = summary.get("m_mean", 0)
                n_mean = summary.get("n_mean", 0)
                status = "EQUIV" if result["is_equivalent"] else "FAIL"
                print(f" {status} ({result['boundaries_checked']} bnd, "
                      f"m={m_mean:.1f} n={n_mean:.1f}, {elapsed:.1f}s)")
        except Exception as e:
            elapsed = time.time() - t0
            error_result = {
                "seed": seed,
                "is_equivalent": False,
                "error": str(e),
                "elapsed_sec": round(elapsed, 2),
            }
            seed_results.append(error_result)
            failed_seeds.append(seed)
            save_results(result_path, spec, seed_results, failed_seeds, run_length)
            if verbose:
                print(f" ERROR ({elapsed:.1f}s): {e}")

    if verbose:
        status = "EQUIVALENT" if not failed_seeds else "NOT_EQUIVALENT"
        print(f"  DONE {config_path.stem}: {len(seed_results)} seeds -> {status}")

    return "EQUIVALENT" if not failed_seeds else "NOT_EQUIVALENT"


def show_status(configs):
    by_pair = {}
    for config_path in configs:
        pair = config_path.parent.parent.name
        topo = config_path.parent.name
        completed, total, status = check_progress(config_path)
        by_pair.setdefault(pair, []).append((topo, config_path.stem, completed, total, status))

    total_configs = 0
    total_done = 0
    total_in_progress = 0
    total_pending = 0

    for pair in sorted(by_pair):
        print(f"\n--- {pair.upper()} ---")
        for topo, name, completed, total, status in by_pair[pair]:
            total_configs += 1
            if status in ("EQUIVALENT", "NOT_EQUIVALENT"):
                total_done += 1
                mark = "DONE"
            elif status == "IN_PROGRESS":
                total_in_progress += 1
                mark = f"{completed}/{total}"
            else:
                total_pending += 1
                mark = "TODO"
            print(f"  [{mark:>8}] {name}")

    print(f"\nSummary: {total_done} done, {total_in_progress} in-progress, "
          f"{total_pending} pending / {total_configs} total")


def main():
    parser = argparse.ArgumentParser(description="Incremental MSRE verification runner")
    parser.add_argument("--pair", choices=["eg_acd", "eg_devs", "acd_devs"],
                        help="Filter by formalism pair")
    parser.add_argument("--topology", help="Filter by topology (tandem, feedback, fork_join, hybrid, warehouse)")
    parser.add_argument("--name", help="Filter by name substring")
    parser.add_argument("--run-length", type=float, default=None,
                        help="Override simulation run length (default: from config, usually 100)")
    parser.add_argument("--status", action="store_true", help="Show progress only, don't run")
    args = parser.parse_args()

    configs = find_configs(args.pair, args.topology, args.name)
    if not configs:
        print("No configs found matching filters.")
        sys.exit(1)

    if args.status:
        show_status(configs)
        return

    rl_msg = f", T={args.run_length}" if args.run_length else ""
    print(f"Found {len(configs)} config(s) to process{rl_msg}")
    t_start = time.time()
    results = {"EQUIVALENT": 0, "NOT_EQUIVALENT": 0, "SKIP": 0, "ERROR": 0}

    for i, config_path in enumerate(configs):
        print(f"\n[{i+1}/{len(configs)}] {config_path.parent.parent.name}/{config_path.parent.name}/{config_path.stem}")
        status = run_config_incremental(config_path, run_length_override=args.run_length)
        results[status] = results.get(status, 0) + 1

    elapsed = time.time() - t_start
    print(f"\n{'='*70}")
    print(f"  COMPLETE in {elapsed:.0f}s")
    print(f"  Equivalent: {results['EQUIVALENT']} | Not Equivalent: {results['NOT_EQUIVALENT']} | "
          f"Skipped: {results['SKIP']} | Error: {results.get('ERROR', 0)}")
    print(f"{'='*70}")

    sys.exit(0 if results["NOT_EQUIVALENT"] == 0 and results.get("ERROR", 0) == 0 else 1)


if __name__ == "__main__":
    main()
