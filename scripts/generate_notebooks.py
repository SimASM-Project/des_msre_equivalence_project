#!/usr/bin/env python3
"""
Generate MSRE reproducibility notebooks.

Produces 5 Jupyter notebooks (one per topology) from the verification
config files in configs/. Each notebook contains one %%simasm verify cell
per (size, formalism pair), with model paths relative to the notebooks/
directory and run_length set to 100.0 for fast interactive execution.

Usage:
    python scripts/generate_notebooks.py [--topology tandem|feedback|fork_join|hybrid|warehouse|all]
"""

import argparse
import os
import re
from pathlib import Path

import nbformat

PROJECT_DIR = Path(__file__).resolve().parent.parent
CONFIGS_DIR = PROJECT_DIR / "configs"
NOTEBOOK_DIR = PROJECT_DIR / "notebooks"

PAIRS = [
    ("eg_acd", "EG vs ACD"),
    ("eg_devs", "EG vs DEVS"),
    ("acd_devs", "ACD vs DEVS"),
]

STANDARD_SIZES = ["1", "2", "3", "4", "5", "7", "10", "15", "20"]
HYBRID_SIZES = ["2_2", "2_3", "2_4", "3_2", "3_3", "3_4", "4_2", "4_3", "4_4"]

TOPOLOGY_DESCRIPTIONS = {
    "tandem": (
        "# MSRE Verification: Tandem Topology\n\n"
        "A **tandem queueing network** with $n$ stations in series. "
        "Entities arrive at station 1, are served, and proceed sequentially to station $n$. "
        "Each station has 5 servers (`service_capacity=5`), exponential inter-arrival times "
        "(`iat_mean=1.25`), and exponential service times (`ist_mean=1.0`).\n\n"
        "## Macro-Step Refinement Equivalence (MSRE)\n\n"
        "Each cell below verifies that two formalism translations produce **identical "
        "observable labels at every tick boundary** (simulation time advance). "
        "The observation level is boolean: `QueueNonEmpty` and `ServerBusy` per station.\n\n"
        "**Notebook parameters**: `seed=42`, `run_length=100.0` (fast interactive execution)."
    ),
    "feedback": (
        "# MSRE Verification: Feedback Topology\n\n"
        "A **feedback queueing network** with $n$ stations in series. "
        "After completing service at station $n$, entities are routed back to station 1 "
        "with a fixed probability, creating recirculation. "
        "Each station has 5 servers (`service_capacity=5`).\n\n"
        "## Macro-Step Refinement Equivalence (MSRE)\n\n"
        "Each cell below verifies that two formalism translations produce **identical "
        "observable labels at every tick boundary**.\n\n"
        "**Notebook parameters**: `seed=42`, `run_length=100.0`."
    ),
    "fork_join": (
        "# MSRE Verification: Fork-Join Topology\n\n"
        "A **fork-join queueing network** with $n$ parallel branches. "
        "Arriving entities are split (forked) into $n$ sub-entities, each processed "
        "independently at a branch server. All sub-entities must complete before the "
        "entity is reassembled (joined). Each branch server has 5 servers.\n\n"
        "## Macro-Step Refinement Equivalence (MSRE)\n\n"
        "Each cell below verifies that two formalism translations produce **identical "
        "observable labels at every tick boundary**.\n\n"
        "**Notebook parameters**: `seed=42`, `run_length=100.0`."
    ),
    "hybrid": (
        "# MSRE Verification: Hybrid Topology\n\n"
        "A **hybrid queueing network** combining $m$ tandem stations with a fork-join "
        "section of $b$ parallel branches (`hybrid_m_b`). "
        "This topology tests mixed serial-parallel structures. "
        "Each station has 5 servers.\n\n"
        "## Macro-Step Refinement Equivalence (MSRE)\n\n"
        "Each cell below verifies that two formalism translations produce **identical "
        "observable labels at every tick boundary**.\n\n"
        "**Notebook parameters**: `seed=42`, `run_length=100.0`."
    ),
    "warehouse": (
        "# MSRE Verification: Warehouse Case Study\n\n"
        "An **industry-scale warehouse outbound process model** with 6 stations: "
        "PickA, PickB (parallel picking zones), Label, Scan, Pack, Release (serial processing). "
        "Based on operational data from a third-party logistics company. "
        "Stations have heterogeneous parameters (service times from 1.0 to 288.8 minutes, "
        "up to 4 workers per station).\n\n"
        "## Macro-Step Refinement Equivalence (MSRE)\n\n"
        "Each cell below verifies that two formalism translations produce **identical "
        "observable labels at every tick boundary**.\n\n"
        "**Notebook parameters**: `seed=42`, `run_length=100.0`."
    ),
}


def rewrite_config(config_text: str, config_path: Path) -> str:
    """Rewrite a config file for notebook use.

    Changes:
    - Model import paths: rewritten as relative paths from NOTEBOOK_DIR
    - seed_range / seed: normalized to seed: 42
    - run_length: set to 100.0
    - timeout: set to 60
    - Remove output file_path line (results display inline)
    """
    config_dir = config_path.parent

    def replace_import_path(match):
        prefix = match.group(1)
        rel_path = match.group(2)
        abs_model = (config_dir / rel_path).resolve()
        new_path = os.path.relpath(abs_model, NOTEBOOK_DIR.resolve()).replace("\\", "/")
        return f'{prefix}"{new_path}"'

    result = re.sub(
        r'(import \w+ from )"([^"]+)"',
        replace_import_path,
        config_text,
    )

    result = re.sub(r"seed_range: \d+ to \d+", "seed: 42", result)
    result = re.sub(r"seed: \d+", "seed: 42", result)
    result = re.sub(r"run_length: [\d.]+", "run_length: 100.0", result)
    result = re.sub(r"timeout: \d+", "timeout: 60", result)
    result = re.sub(r'\s*file_path:.*\n', '\n', result)

    return result


def size_sort_key(size_str: str) -> tuple:
    parts = size_str.split("_")
    return tuple(int(p) for p in parts)


def get_size_label(topology: str, size: str) -> str:
    if topology == "hybrid":
        m, b = size.split("_")
        return f"hybrid ({m},{b}): {m} tandem + {b} branches"
    if topology == "warehouse":
        return "warehouse (6 stations)"
    return f"$n = {size}$"


def generate_notebook(topology: str) -> nbformat.NotebookNode:
    nb = nbformat.v4.new_notebook()
    nb.metadata["kernelspec"] = {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    }

    nb.cells.append(nbformat.v4.new_markdown_cell(TOPOLOGY_DESCRIPTIONS[topology]))

    nb.cells.append(nbformat.v4.new_code_cell(
        'import simasm\n'
        'assert simasm.__version__ >= "0.7.0", '
        'f"Requires simasm >= 0.7.0, got {simasm.__version__}"'
    ))

    if topology == "warehouse":
        sizes = [""]
    elif topology == "hybrid":
        sizes = sorted(HYBRID_SIZES, key=size_sort_key)
    else:
        sizes = sorted(STANDARD_SIZES, key=size_sort_key)

    for size in sizes:
        if topology == "warehouse":
            size_label = "Warehouse"
        else:
            size_label = get_size_label(topology, size)

        nb.cells.append(nbformat.v4.new_markdown_cell(f"## {size_label}"))

        for pair_id, pair_label in PAIRS:
            pair_dir = CONFIGS_DIR / pair_id / topology
            if topology == "warehouse":
                config_name = f"warehouse_{pair_id}_msre.simasm"
            else:
                config_name = f"{topology}_{size}_{pair_id}_msre.simasm"

            config_path = pair_dir / config_name
            if not config_path.exists():
                print(f"  WARNING: missing {config_path}")
                continue

            config_text = config_path.read_text(encoding="utf-8")
            rewritten = rewrite_config(config_text, config_path)

            nb.cells.append(nbformat.v4.new_code_cell(
                f"%%simasm verify\n{rewritten.strip()}"
            ))

    nb.cells.append(nbformat.v4.new_markdown_cell(
        "## Summary\n\n"
        "All verification cells above should return **EQUIVALENT**. "
        "This confirms macro-step refinement equivalence across all three formalism "
        "pairs for this topology."
    ))

    return nb


def main():
    parser = argparse.ArgumentParser(description="Generate MSRE reproducibility notebooks")
    parser.add_argument(
        "--topology",
        choices=["tandem", "feedback", "fork_join", "hybrid", "warehouse", "all"],
        default="all",
    )
    args = parser.parse_args()

    topologies = (
        ["tandem", "feedback", "fork_join", "hybrid", "warehouse"]
        if args.topology == "all"
        else [args.topology]
    )

    NOTEBOOK_DIR.mkdir(parents=True, exist_ok=True)

    for topology in topologies:
        nb = generate_notebook(topology)
        out_path = NOTEBOOK_DIR / f"{topology}_msre.ipynb"
        nbformat.write(nb, str(out_path))
        cell_count = len(nb.cells)
        print(f"Generated {out_path.name} ({cell_count} cells)")

    print(f"\nDone. Notebooks in: {NOTEBOOK_DIR}")


if __name__ == "__main__":
    main()
