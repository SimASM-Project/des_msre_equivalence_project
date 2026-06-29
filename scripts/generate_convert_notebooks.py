#!/usr/bin/env python3
"""
Generate MSRE reproducibility notebooks with JSON-to-SimASM conversion.

Produces 4 Jupyter notebooks (tandem, feedback, fork_join, hybrid) that follow
the warehouse_msre.ipynb pattern:
  1. Load JSON specification files via %%simasm convert
  2. Register models in memory
  3. Verify MSRE across formalism pairs via %%simasm verify

Usage:
    python scripts/generate_convert_notebooks.py [--topology tandem|feedback|fork_join|hybrid|all]
"""

import argparse
from pathlib import Path

import nbformat

PROJECT_DIR = Path(__file__).resolve().parent.parent
NOTEBOOK_DIR = PROJECT_DIR / "notebooks"

STANDARD_SIZES = [1, 2, 3, 4, 5, 7, 10, 15, 20]
HYBRID_SIZES = [(m, b) for m in [2, 3, 4] for b in [2, 3, 4]]

TOPOLOGY_DESCRIPTIONS = {
    "tandem": (
        "# MSRE Verification: Tandem Topology\n\n"
        "A **tandem queueing network** with $n$ stations in series. "
        "Entities arrive at station 1, are served, and proceed sequentially to station $n$. "
        "Each station has 5 servers (`service_capacity=5`), exponential inter-arrival times "
        "(`iat_mean=1.25`), and exponential service times (`ist_mean=1.0`).\n\n"
        "## Macro-Step Refinement Equivalence (MSRE)\n\n"
        "Each section below converts the JSON specification into SimASM via `%%simasm convert`, "
        "then verifies that all three formalism translations produce **identical "
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
        "Each section below converts the JSON specification into SimASM via `%%simasm convert`, "
        "then verifies MSRE across all three formalism pairs.\n\n"
        "**Notebook parameters**: `seed=42`, `run_length=100.0`."
    ),
    "fork_join": (
        "# MSRE Verification: Fork-Join Topology\n\n"
        "A **fork-join queueing network** with $n$ parallel branches. "
        "Arriving entities are split (forked) into $n$ sub-entities, each processed "
        "independently at a branch server. All sub-entities must complete before the "
        "entity is reassembled (joined). Each branch server has 5 servers.\n\n"
        "## Macro-Step Refinement Equivalence (MSRE)\n\n"
        "Each section below converts the JSON specification into SimASM via `%%simasm convert`, "
        "then verifies MSRE across all three formalism pairs.\n\n"
        "**Notebook parameters**: `seed=42`, `run_length=100.0`."
    ),
    "hybrid": (
        "# MSRE Verification: Hybrid Topology\n\n"
        "A **hybrid queueing network** combining $m$ tandem stations with a fork-join "
        "section of $b$ parallel branches (`hybrid_m_b`). "
        "This topology tests mixed serial-parallel structures. "
        "Each station has 5 servers.\n\n"
        "## Macro-Step Refinement Equivalence (MSRE)\n\n"
        "Each section below converts the JSON specification into SimASM via `%%simasm convert`, "
        "then verifies MSRE across all three formalism pairs.\n\n"
        "**Notebook parameters**: `seed=42`, `run_length=100.0`."
    ),
}


def get_model_name(topology: str, size) -> str:
    if topology == "hybrid":
        m, b = size
        return f"hybrid_{m}_{b}"
    return f"{topology}_{size}"


def get_num_stations(topology: str, size) -> int:
    if topology == "hybrid":
        m, b = size
        return m + b
    return size


def get_size_label(topology: str, size) -> str:
    if topology == "hybrid":
        m, b = size
        return f"hybrid ({m},{b}): {m} tandem + {b} branches"
    return f"$n = {size}$"


def make_convert_cell(topology: str, model_name: str, formalism: str) -> str:
    formalism_key = {
        "eg": "event_graph",
        "acd": "acd",
        "devs": "devs",
    }[formalism]
    source_path = f"../input/{topology}/{model_name}_{formalism}.json"
    register_name = f"{model_name}_{formalism}"

    return (
        f"%%simasm convert\n"
        f"convert {register_name}:\n"
        f'    source: "{source_path}"\n'
        f"    formalism: {formalism_key}\n"
        f'    register: "{register_name}"\n'
        f"    print: 30\n"
        f"endconvert"
    )


def get_devs_prefix(topology: str) -> str:
    if topology == "fork_join":
        return "Branch_Server"
    return "Server"


def make_labels_block(
    formalism_a: str,
    formalism_b: str,
    num_stations: int,
    topology: str,
) -> str:
    lines = ["    labels:"]
    devs_prefix = get_devs_prefix(topology)

    for i in range(1, num_stations + 1):
        queue_pred_a = _get_predicate("queue", formalism_a, i, devs_prefix)
        queue_pred_b = _get_predicate("queue", formalism_b, i, devs_prefix)
        server_pred_a = _get_predicate("server", formalism_a, i, devs_prefix)
        server_pred_b = _get_predicate("server", formalism_b, i, devs_prefix)

        fa_upper = formalism_a.upper()
        fb_upper = formalism_b.upper()

        lines.append(f'        label queue_{i}_nonempty for {fa_upper}: "{queue_pred_a}"')
        lines.append(f'        label queue_{i}_nonempty for {fb_upper}: "{queue_pred_b}"')
        lines.append(f'        label server_{i}_busy for {fa_upper}: "{server_pred_a}"')
        lines.append(f'        label server_{i}_busy for {fb_upper}: "{server_pred_b}"')

    lines.append("    endlabels")
    return "\n".join(lines)


def _get_predicate(obs_type: str, formalism: str, station: int, devs_prefix: str) -> str:
    if obs_type == "queue":
        if formalism == "eg":
            return f"queue_count_{station} > 0"
        elif formalism == "acd":
            return f"marking(Q_{station}) > 0"
        else:
            return f"{devs_prefix}_{station}_queue_count > 0"
    else:
        if formalism == "eg":
            return f"server_count_{station} > 0"
        elif formalism == "acd":
            return f"marking(S_{station}) < num_servers"
        else:
            return f"{devs_prefix}_{station}_server_count > 0"


def make_observables_block(
    formalism_a: str,
    formalism_b: str,
    num_stations: int,
) -> str:
    fa_upper = formalism_a.upper()
    fb_upper = formalism_b.upper()
    lines = ["    observables:"]

    for i in range(1, num_stations + 1):
        lines.append(f"        observable queue_{i}_nonempty:")
        lines.append(f"            {fa_upper} -> queue_{i}_nonempty")
        lines.append(f"            {fb_upper} -> queue_{i}_nonempty")
        lines.append(f"        endobservable")
        lines.append(f"        observable server_{i}_busy:")
        lines.append(f"            {fa_upper} -> server_{i}_busy")
        lines.append(f"            {fb_upper} -> server_{i}_busy")
        lines.append(f"        endobservable")

    lines.append("    endobservables")
    return "\n".join(lines)


def make_verify_cell(
    model_name: str,
    formalism_a: str,
    formalism_b: str,
    num_stations: int,
    topology: str,
) -> str:
    fa_upper = formalism_a.upper()
    fb_upper = formalism_b.upper()
    verification_name = f"{model_name}_{formalism_a}_{formalism_b}_msre"
    register_a = f"{model_name}_{formalism_a}"
    register_b = f"{model_name}_{formalism_b}"

    labels = make_labels_block(formalism_a, formalism_b, num_stations, topology)
    observables = make_observables_block(formalism_a, formalism_b, num_stations)

    return (
        f"%%simasm verify\n"
        f"// MSRE Verification: {model_name} {fa_upper} vs {fb_upper}\n\n"
        f"verification {verification_name}:\n\n"
        f"    models:\n"
        f'        import {fa_upper} from "{register_a}"\n'
        f'        import {fb_upper} from "{register_b}"\n'
        f"    endmodels\n\n"
        f"    seed: 42\n\n"
        f"{labels}\n\n"
        f"{observables}\n\n"
        f"    check:\n"
        f"        type: macro_step_refinement\n"
        f"        run_length: 100.0\n"
        f"        timeout: 60\n"
        f"    endcheck\n\n"
        f"    output:\n"
        f'        format: "json"\n'
        f"        include_counterexample: true\n"
        f"    endoutput\n\n"
        f"endverification"
    )


PAIRS = [("eg", "acd"), ("eg", "devs"), ("acd", "devs")]


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
        'assert simasm.__version__ >= "0.8.1", '
        'f"Requires simasm >= 0.8.1, got {simasm.__version__}"'
    ))

    if topology == "hybrid":
        sizes = sorted(HYBRID_SIZES)
    else:
        sizes = STANDARD_SIZES

    for size in sizes:
        model_name = get_model_name(topology, size)
        num_stations = get_num_stations(topology, size)
        size_label = get_size_label(topology, size)

        nb.cells.append(nbformat.v4.new_markdown_cell(f"## {size_label}"))

        for formalism in ["eg", "acd", "devs"]:
            nb.cells.append(nbformat.v4.new_code_cell(
                make_convert_cell(topology, model_name, formalism)
            ))

        for fa, fb in PAIRS:
            nb.cells.append(nbformat.v4.new_code_cell(
                make_verify_cell(model_name, fa, fb, num_stations, topology)
            ))

    nb.cells.append(nbformat.v4.new_markdown_cell(
        "## Summary\n\n"
        "All verification cells above should return **EQUIVALENT**. "
        "This confirms macro-step refinement equivalence across all three formalism "
        "pairs for this topology."
    ))

    return nb


def main():
    parser = argparse.ArgumentParser(
        description="Generate MSRE notebooks with JSON-to-SimASM conversion"
    )
    parser.add_argument(
        "--topology",
        choices=["tandem", "feedback", "fork_join", "hybrid", "all"],
        default="all",
    )
    args = parser.parse_args()

    topologies = (
        ["tandem", "feedback", "fork_join", "hybrid"]
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
