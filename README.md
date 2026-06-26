# DES Macro-Step Refinement Equivalence (MSRE) Verification

Replication package for the empirical verification of **macro-step refinement equivalence** across three discrete-event simulation (DES) formalisms: Event Graphs (EG), Activity Cycle Diagrams (ACD), and DEVS.

Each formalism encodes the same queueing network as a SimASM (Abstract State Machine for Simulation) program. MSRE verification confirms that all three formalism translations produce **identical observable labels at every simulation tick boundary**, establishing behavioural equivalence at the macro-step level.

## File Structure

```
des_msre_equivalence_project/
├── README.md
├── requirements.txt
│
├── models/                     111 SimASM model files
│   ├── eg/                     Event Graph models
│   │   ├── tandem/             tandem_{1..20}_eg.simasm
│   │   ├── feedback/           feedback_{1..20}_eg.simasm
│   │   ├── fork_join/          fork_join_{1..20}_eg.simasm
│   │   ├── hybrid/             hybrid_{m_b}_eg.simasm
│   │   └── warehouse/          warehouse_eg.simasm
│   ├── acd/                    Activity Cycle Diagram models (same structure)
│   └── devs/                   DEVS models (same structure)
│
├── configs/                    Verification configs (seed=42, T=100)
│   ├── eg_acd/                 EG vs ACD pair
│   ├── eg_devs/                EG vs DEVS pair
│   └── acd_devs/               ACD vs DEVS pair
│
├── results/                    Pre-computed results (from paper: 30 seeds, T=10000)
│   ├── eg_acd/
│   ├── eg_devs/
│   └── acd_devs/
│
├── notebooks/                  Jupyter notebooks (seed=42, T=100)
│   ├── tandem_msre.ipynb
│   ├── feedback_msre.ipynb
│   ├── fork_join_msre.ipynb
│   ├── hybrid_msre.ipynb
│   └── warehouse_msre.ipynb
│
└── scripts/
    ├── run_msre.py             CLI verification runner with resume support
    ├── extract_results.py      Print summary tables from pre-computed results
    └── generate_notebooks.py   Regenerate notebooks from configs
```

## Quick Start

### 1. Create and activate a virtual environment:
     python -m venv venv
     venv\Scripts\activate

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run a notebook

```bash
jupyter notebook notebooks/warehouse_msre.ipynb
```

Run all cells. Each `%%simasm verify` cell checks one (topology, size, formalism pair) and prints **EQUIVALENT** on success.

### 4. View pre-computed results

```bash
python scripts/extract_results.py
```

This prints summary tables (step counts, segment lengths, refinement ratios) from the paper-scale results in `results/`.

## Topologies

| Topology | Description | Sizes |
|----------|-------------|-------|
| **Tandem** | $n$ stations in series | $n \in \{1,2,3,4,5,7,10,15,20\}$ |
| **Feedback** | $n$ stations with recirculation to station 1 | $n \in \{1,2,3,4,5,7,10,15,20\}$ |
| **Fork-Join** | $n$ parallel branches, fork then join | $n \in \{1,2,3,4,5,7,10,15,20\}$ |
| **Hybrid** | $m$ tandem + $b$ fork-join branches | $(m,b) \in \{2,3,4\} \times \{2,3,4\}$ |
| **Warehouse** | 6-station outbound process (industry case study) | 1 configuration |

All models use `service_capacity=5`, `iat_mean=1.25`, `ist_mean=1.0`.

## Three Formalisms

| Formalism | Algorithm | Reference |
|-----------|-----------|-----------|
| Event Graph (EG) | Next-Event Time-Advance | Schruben (1983) |
| Activity Cycle Diagram (ACD) | Activity Scanning | Tocher (1963) |
| DEVS | Abstract Simulator | Zeigler et al. (2000) |

Each model is written in SimASM, a formal specification language based on Abstract State Machines that provides a common semantic framework for all three DES formalisms.

## Verification Method

**Macro-Step Refinement Equivalence (MSRE)** checks that two SimASM programs, compiled from different formalisms for the same queueing network, produce identical observable behaviour:

1. Both programs are run with the same random seed and simulation end time.
2. At every **tick boundary** (each simulation time advance), the observable labels are compared.
3. Observable labels are boolean predicates on the state: `QueueNonEmpty` and `ServerBusy` per station.
4. If all labels match at every boundary for all seeds, the programs are declared **equivalent**.

## Running Full Verification (CLI)

The `scripts/run_msre.py` runner executes verification configs from the command line with incremental save/resume:

```bash
# Run all 111 configs
python scripts/run_msre.py

# Run only EG vs ACD tandem models
python scripts/run_msre.py --pair eg_acd --topology tandem

# Check progress without running
python scripts/run_msre.py --status
```

## Pre-computed Results

The `results/` directory contains verification outputs from the paper's full-scale runs:
- **30 seeds** (42 to 71)
- **run_length = 10,000** simulation time units

The notebooks and configs in this package use `seed=42` and `run_length=100.0` for fast interactive verification. The pre-computed results serve as evidence that equivalence holds at paper scale.

## Requirements

- Python 3.10+
- `simasm >= 0.7.0` (with `%%simasm verify` Jupyter magic support)
- Jupyter (for notebooks)
