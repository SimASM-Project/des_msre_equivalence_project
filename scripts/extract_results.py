#!/usr/bin/env python3
"""
Extract and display MSRE verification results from pre-computed JSON files.

Reads results from the results/ directory and prints summary tables
for all topologies, including step counts, segment lengths, and
refinement ratios.

Usage:
    python scripts/extract_results.py
"""

import json
import os
from collections import defaultdict
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_DIR / "results"

PAIRS = ["eg_acd", "eg_devs", "acd_devs"]
PAIR_FORMALISMS = {
    "eg_acd": ("EG", "ACD"),
    "eg_devs": ("EG", "DEVS"),
    "acd_devs": ("ACD", "DEVS"),
}
STANDARD_SIZES = [1, 2, 3, 4, 5, 7, 10, 15, 20]
TOPOLOGIES = ["tandem", "feedback", "fork_join"]
HYBRID_SIZES = ["2_2", "2_3", "2_4", "3_2", "3_3", "3_4", "4_2", "4_3", "4_4"]


def parse_filename(fname):
    fname = fname.replace("_msre_results.json", "")
    for pair in PAIRS:
        if f"_{pair}" in fname:
            model = fname.replace(f"_{pair}", "")
            if model == "warehouse":
                return "warehouse", "1", pair
            for topo in ["fork_join", "tandem", "feedback", "hybrid"]:
                if model.startswith(topo + "_"):
                    size = model[len(topo) + 1:]
                    return topo, size, pair
    return None, None, None


def aggregate_seeds(data):
    seeds = data["per_seed_results"]
    n = len(seeds)
    avg_K = sum(s["boundaries_checked"] for s in seeds) / n
    avg_steps_a = sum(s["total_steps_a"] for s in seeds) / n
    avg_steps_b = sum(s["total_steps_b"] for s in seeds) / n
    avg_m_mean = sum(s["step_profile_summary"]["m_mean"] for s in seeds) / n
    avg_n_mean = sum(s["step_profile_summary"]["n_mean"] for s in seeds) / n
    global_m_min = min(s["step_profile_summary"]["m_range"][0] for s in seeds)
    global_m_max = max(s["step_profile_summary"]["m_range"][1] for s in seeds)
    global_n_min = min(s["step_profile_summary"]["n_range"][0] for s in seeds)
    global_n_max = max(s["step_profile_summary"]["n_range"][1] for s in seeds)
    return {
        "K": avg_K,
        "steps_a": avg_steps_a,
        "steps_b": avg_steps_b,
        "m_mean": avg_m_mean,
        "n_mean": avg_n_mean,
        "m_range": [global_m_min, global_m_max],
        "n_range": [global_n_min, global_n_max],
        "all_equivalent": data["status"] == "EQUIVALENT",
        "num_seeds": n,
    }


def load_all_data():
    all_data = defaultdict(lambda: defaultdict(dict))
    for pair in PAIRS:
        pair_dir = RESULTS_DIR / pair
        if not pair_dir.exists():
            continue
        for fname in os.listdir(pair_dir):
            if not fname.endswith("_results.json"):
                continue
            filepath = pair_dir / fname
            with open(filepath, "r") as f:
                data = json.load(f)
            topo, size, p = parse_filename(fname)
            if topo is None:
                print(f"WARN: could not parse {fname}")
                continue
            agg = aggregate_seeds(data)
            all_data[topo][size][p] = agg
    return all_data


def build_combined_row(all_data, topo, size):
    pairs = all_data[topo][size]
    eg_acd = pairs.get("eg_acd")
    eg_devs = pairs.get("eg_devs")
    acd_devs = pairs.get("acd_devs")

    K_values = []
    if eg_acd: K_values.append(eg_acd["K"])
    if eg_devs: K_values.append(eg_devs["K"])
    if acd_devs: K_values.append(acd_devs["K"])
    K = sum(K_values) / len(K_values) if K_values else 0

    eg_steps = eg_acd["steps_a"] if eg_acd else (eg_devs["steps_a"] if eg_devs else None)
    eg_seg_mean = eg_acd["m_mean"] if eg_acd else (eg_devs["m_mean"] if eg_devs else None)
    eg_seg_range = eg_acd["m_range"] if eg_acd else (eg_devs["m_range"] if eg_devs else None)

    acd_steps = eg_acd["steps_b"] if eg_acd else (acd_devs["steps_a"] if acd_devs else None)
    acd_seg_mean = eg_acd["n_mean"] if eg_acd else (acd_devs["m_mean"] if acd_devs else None)
    acd_seg_range = eg_acd["n_range"] if eg_acd else (acd_devs["m_range"] if acd_devs else None)

    devs_steps = eg_devs["steps_b"] if eg_devs else (acd_devs["steps_b"] if acd_devs else None)
    devs_seg_mean = eg_devs["n_mean"] if eg_devs else (acd_devs["n_mean"] if acd_devs else None)
    devs_seg_range = eg_devs["n_range"] if eg_devs else (acd_devs["n_range"] if acd_devs else None)

    return {
        "K": K,
        "EG_steps": eg_steps, "EG_seg_mean": eg_seg_mean, "EG_seg_range": eg_seg_range,
        "ACD_steps": acd_steps, "ACD_seg_mean": acd_seg_mean, "ACD_seg_range": acd_seg_range,
        "DEVS_steps": devs_steps, "DEVS_seg_mean": devs_seg_mean, "DEVS_seg_range": devs_seg_range,
    }


def fmt_range(r):
    if r is None: return "---"
    return f"[{r[0]},{r[1]}]"


def fmt_num(n, decimals=0):
    if n is None: return "---"
    if decimals == 0:
        return f"{int(round(n)):,}"
    return f"{n:.{decimals}f}"


def main():
    all_data = load_all_data()

    header = (f"{'n':>4} | {'K':>8} | {'EG steps':>10} {'EG seg.l':>8} {'EG range':>8} | "
              f"{'ACD steps':>10} {'ACD seg.l':>8} {'ACD range':>9} | "
              f"{'DEVS steps':>10} {'DEVS seg.l':>9} {'DEVS range':>10}")

    for topo_name, topo_label in [("tandem", "TANDEM"), ("feedback", "FEEDBACK"), ("fork_join", "FORK-JOIN")]:
        print("=" * 100)
        print(f"{topo_label} TOPOLOGY")
        print("=" * 100)
        print(header)
        print("-" * len(header))
        for size in STANDARD_SIZES:
            s = str(size)
            row = build_combined_row(all_data, topo_name, s)
            print(f"{size:>4} | {fmt_num(row['K']):>8} | "
                  f"{fmt_num(row['EG_steps']):>10} {fmt_num(row['EG_seg_mean'],2):>8} {fmt_range(row['EG_seg_range']):>8} | "
                  f"{fmt_num(row['ACD_steps']):>10} {fmt_num(row['ACD_seg_mean'],2):>8} {fmt_range(row['ACD_seg_range']):>9} | "
                  f"{fmt_num(row['DEVS_steps']):>10} {fmt_num(row['DEVS_seg_mean'],2):>9} {fmt_range(row['DEVS_seg_range']):>10}")
        print()

    print("=" * 100)
    print("HYBRID TOPOLOGY")
    print("=" * 100)
    h2 = (f"{'(m,b)':>6} | {'K':>8} | {'EG steps':>10} {'EG seg.l':>8} {'EG range':>8} | "
          f"{'ACD steps':>10} {'ACD seg.l':>8} {'ACD range':>9} | "
          f"{'DEVS steps':>10} {'DEVS seg.l':>9} {'DEVS range':>10}")
    print(h2)
    print("-" * len(h2))
    for size in HYBRID_SIZES:
        row = build_combined_row(all_data, "hybrid", size)
        label = f"({size.replace('_',',')})"
        print(f"{label:>6} | {fmt_num(row['K']):>8} | "
              f"{fmt_num(row['EG_steps']):>10} {fmt_num(row['EG_seg_mean'],2):>8} {fmt_range(row['EG_seg_range']):>8} | "
              f"{fmt_num(row['ACD_steps']):>10} {fmt_num(row['ACD_seg_mean'],2):>8} {fmt_range(row['ACD_seg_range']):>9} | "
              f"{fmt_num(row['DEVS_steps']):>10} {fmt_num(row['DEVS_seg_mean'],2):>9} {fmt_range(row['DEVS_seg_range']):>10}")

    print()
    print("=" * 100)
    print("WAREHOUSE")
    print("=" * 100)
    row = build_combined_row(all_data, "warehouse", "1")
    print(f"K = {fmt_num(row['K'],1)}")
    print(f"EG:   steps={fmt_num(row['EG_steps'],1)}, seg.len={fmt_num(row['EG_seg_mean'],2)}, range={fmt_range(row['EG_seg_range'])}")
    print(f"ACD:  steps={fmt_num(row['ACD_steps'],1)}, seg.len={fmt_num(row['ACD_seg_mean'],2)}, range={fmt_range(row['ACD_seg_range'])}")
    print(f"DEVS: steps={fmt_num(row['DEVS_steps'],1)}, seg.len={fmt_num(row['DEVS_seg_mean'],2)}, range={fmt_range(row['DEVS_seg_range'])}")

    print()
    print("WAREHOUSE PAIRWISE:")
    for pair in PAIRS:
        d = all_data["warehouse"]["1"].get(pair)
        if d:
            fa, fb = PAIR_FORMALISMS[pair]
            print(f"  {pair}: K={d['K']:.1f}, {fa} steps={d['steps_a']:.1f}, {fb} steps={d['steps_b']:.1f}, "
                  f"{fa} seg.l={d['m_mean']:.2f}, {fb} seg.l={d['n_mean']:.2f}, "
                  f"{fa} range={fmt_range(d['m_range'])}, {fb} range={fmt_range(d['n_range'])}")

    print()
    print("=" * 100)
    print("REFINEMENT RATIOS (ACD/EG, DEVS/EG, ACD/DEVS)")
    print("=" * 100)
    for topo in TOPOLOGIES + ["hybrid"]:
        sizes = STANDARD_SIZES if topo in TOPOLOGIES else HYBRID_SIZES
        print(f"\n{topo}:")
        for size in sizes:
            s = str(size)
            row = build_combined_row(all_data, topo, s)
            if row["EG_steps"] and row["ACD_steps"] and row["DEVS_steps"]:
                acd_eg = row["ACD_steps"] / row["EG_steps"]
                devs_eg = row["DEVS_steps"] / row["EG_steps"]
                acd_devs_r = row["ACD_steps"] / row["DEVS_steps"]
                label = s if topo != "hybrid" else f"({s.replace('_',',')})"
                print(f"  {label:>6}: ACD/EG={acd_eg:.3f}  DEVS/EG={devs_eg:.3f}  ACD/DEVS={acd_devs_r:.3f}")

    print(f"\nwarehouse:")
    row = build_combined_row(all_data, "warehouse", "1")
    if row["EG_steps"] and row["ACD_steps"] and row["DEVS_steps"]:
        print(f"  EG/DEVS={row['EG_steps']/row['DEVS_steps']:.3f}  "
              f"ACD/DEVS={row['ACD_steps']/row['DEVS_steps']:.3f}  "
              f"EG/ACD={row['EG_steps']/row['ACD_steps']:.3f}")

    print()
    print("=" * 100)
    print("K CONSISTENCY CHECK")
    print("=" * 100)
    max_diff = 0
    for topo in list(all_data.keys()):
        for size in all_data[topo]:
            ks = []
            for pair in PAIRS:
                if pair in all_data[topo][size]:
                    ks.append(all_data[topo][size][pair]["K"])
            if len(ks) > 1:
                diff = max(ks) - min(ks)
                if diff > 0.001:
                    print(f"  {topo} {size}: K diff = {diff:.4f} ({ks})")
                max_diff = max(max_diff, diff)
    if max_diff < 0.001:
        print("  ALL CONSISTENT (max diff < 0.001)")


if __name__ == "__main__":
    main()
