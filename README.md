# MANET Routing Protocols — Comparative Simulation Project

A comparative simulation and performance analysis of **trust-aware, energy-aware, predictive, and reinforcement-learning-based routing protocols for Mobile Ad-hoc Networks (MANETs)**.

The project studies the evolution of routing strategies from conventional **AODV** to increasingly intelligent and adaptive approaches:

**AODV → EAURP → ATEAURP → PSE-EAURP → DRL-EAURP → MADRL-EAURP**

Each team member independently implements one stage of this progression using a common simulation environment and evaluation methodology, allowing the protocols to be compared under the same network conditions.

---

## Project Overview

Mobile Ad-hoc Networks (MANETs) consist of mobile wireless nodes that communicate without relying on fixed infrastructure. Because nodes can move dynamically, network topology changes frequently, making routing a challenging problem.

Traditional routing protocols such as **AODV (Ad hoc On-Demand Distance Vector)** primarily focus on finding routes based on network connectivity. However, MANETs can also suffer from:

* Node mobility
* Unstable links
* Malicious or misbehaving nodes
* Limited energy
* Route failures
* Increasing communication delay
* Reduced packet delivery

This project investigates how routing performance can be improved by progressively incorporating:

1. Energy awareness
2. Trust management
3. Adaptive trust estimation
4. Predictive trust analysis
5. Deep/reinforcement learning
6. Multi-agent reinforcement learning

The protocols are evaluated using common network conditions and performance metrics.

---

## Objectives

The major objectives of this project are:

* Implement and simulate multiple MANET routing protocols.
* Establish **AODV as a baseline routing protocol**.
* Introduce energy-aware and trust-aware routing mechanisms.
* Detect and isolate malicious or misbehaving nodes.
* Improve routing decisions using historical and predictive trust information.
* Investigate reinforcement-learning-based routing.
* Extend centralized learning to multi-agent learning.
* Compare protocols using standardized performance metrics.
* Study the effect of node mobility on routing performance.
* Analyze the trade-offs between security, reliability, delay, throughput, and network lifetime.

---

# Protocol Evolution

The project follows a progressive improvement model.

```text
                         AODV
                          │
                          ▼
                        EAURP
                          │
                          ▼
                       ATEAURP
                          │
                          ▼
                      PSE-EAURP
                          │
                          ▼
                      DRL-EAURP
                          │
                          ▼
                     MADRL-EAURP
```

### 1. AODV

**Ad hoc On-Demand Distance Vector**

AODV is used as the baseline routing protocol.

It establishes routes only when required and maintains routing information through route discovery and route maintenance mechanisms.

---

### 2. EAURP

**Energy-Aware Unicast Routing Protocol**

EAURP extends the baseline routing approach by considering the energy state of nodes.

The objective is to avoid excessive use of low-energy nodes and increase overall network lifetime.

**Key idea:**

> Select routes while considering both connectivity and energy availability.

---

### 3. ATEAURP

**Adaptive Trust-Enhanced Energy-Aware Unicast Routing Protocol**

ATEAURP introduces dynamic trust evaluation into energy-aware routing.

It monitors node behavior and uses trust information to reduce the probability of forwarding packets through malicious or unreliable nodes.

The adaptive trust update follows:

```text
T(t+1) = 0.7 × T(t) + 0.3 × PFR
```

where:

* `T(t)` = previous trust value
* `PFR` = Packet Forwarding Ratio
* `T(t+1)` = updated trust value

### Key Features

* Dynamic trust-based routing
* Malicious-node isolation
* Energy monitoring
* Network lifetime tracking
* Node mobility experiments
* Performance visualization

---

### 4. PSE-EAURP

**Predictive Secure Energy-Aware Unicast Routing Protocol**

PSE-EAURP extends ATEAURP by introducing **predictive trust estimation**.

Instead of reacting only after a node demonstrates poor behavior, the protocol uses historical trust information to predict future behavior.

A three-slot weighted trust history is used:

```text
T_pred = 0.5 × T(t)
       + 0.3 × T(t-1)
       + 0.2 × T(t-2)
```

The predicted trust is then incorporated into routing decisions.

### PT_CREV

PSE-EAURP also introduces **Predictive Trust-Controlled Revocation (PT_CREV)**.

Nodes whose predicted trust remains sufficiently low can be:

* Flagged as suspicious
* Blacklisted
* Removed from future routes
* Reported across the network

This allows the protocol to react to potentially malicious nodes before their behavior causes significant network degradation.

---

### 5. DRL-EAURP

**Deep/Reinforcement-Learning-Based Energy-Aware Unicast Routing Protocol**

DRL-EAURP introduces reinforcement learning into routing decisions.

Instead of relying exclusively on manually defined routing rules, a learning agent evaluates network conditions and learns which routing decisions provide better long-term performance.

The learning process considers factors such as:

* Trust
* Energy
* Connectivity
* Packet delivery
* Network conditions
* Routing performance

The objective is to learn routing policies that improve overall network performance.

---

### 6. MADRL-EAURP

**Multi-Agent Deep Reinforcement Learning Energy-Aware Unicast Routing Protocol**

MADRL-EAURP extends the reinforcement-learning approach to multiple cooperating agents.

The project uses a **Centralized Training with Decentralized Execution (CTDE)** approach.

Multiple agents can cooperate while learning during training, while routing decisions can be made locally during execution.

The approach incorporates:

* Multi-agent learning
* Cooperative routing
* Local decision-making
* 2-hop information exchange/gossip
* QMIX/VDN-style value decomposition

This represents the most advanced routing strategy in the project.

---

# Common Simulation Environment

To make the comparison meaningful, the protocols use a common simulation baseline.

| Parameter       | Configuration                |
| --------------- | ---------------------------- |
| Deployment Area | 1000 × 1000 m²               |
| Default Nodes   | 50                           |
| Maximum Nodes   | Up to 500                    |
| Node Speed      | 10–40 m/s                    |
| Connectivity    | Euclidean distance threshold |
| Routing         | Multi-hop                    |
| Network Type    | Mobile Ad-hoc Network        |
| Trust           | Protocol dependent           |
| Energy Model    | Protocol dependent           |
| Malicious Nodes | Supported                    |
| Experiments     | Automated                    |

Using a shared environment ensures that differences in results are primarily caused by the routing algorithms rather than completely different simulation settings.

---

# Performance Metrics

The protocols are evaluated using the following metrics.

### Packet Delivery Ratio — PDR

Measures the percentage of transmitted packets that successfully reach their destination.

```text
PDR = Successfully Delivered Packets
      -------------------------------- × 100
       Total Packets Sent
```

Higher PDR indicates better reliability.

---

### Average Delay

Measures the average time required for packets to travel from source to destination.

Lower delay indicates faster communication.

---

### Throughput

Measures the amount of useful data successfully transmitted through the network per unit time.

Typically represented in:

```text
kbps
```

Higher throughput indicates better network utilization.

---

### Packet Loss

Measures the number or percentage of packets that fail to reach their destination.

Lower packet loss indicates better routing reliability.

---

### Network Lifetime

Measures how long the network remains operational before nodes begin to fail because of energy depletion or other conditions.

Higher network lifetime indicates better energy efficiency.

---


# Requirements

The project primarily uses **Python** for simulation, experimentation, and visualization.

### Software

* Python 3.x
* pip
* Git

### Python Libraries

The exact dependencies for each implementation are provided in its respective:

```text
requirements.txt
```

---


# Experimental Workflow

The general workflow is:

```text
                 ┌─────────────────────┐
                 │   Network Setup     │
                 └──────────┬──────────┘
                            │
                            ▼
                 ┌─────────────────────┐
                 │ Generate MANET      │
                 │ Nodes & Topology    │
                 └──────────┬──────────┘
                            │
                            ▼
                 ┌─────────────────────┐
                 │ Select Routing      │
                 │ Protocol            │
                 └──────────┬──────────┘
                            │
                            ▼
                 ┌─────────────────────┐
                 │ Run Simulation      │
                 │ Across Mobility     │
                 │ Conditions          │
                 └──────────┬──────────┘
                            │
                            ▼
                 ┌─────────────────────┐
                 │ Collect Metrics     │
                 │ PDR / Delay / etc.  │
                 └──────────┬──────────┘
                            │
                            ▼
                 ┌─────────────────────┐
                 │ Generate Graphs     │
                 │ & Comparisons       │
                 └─────────────────────┘
```

---

# Research Progression

The project can be viewed as a progression from conventional routing to intelligent adaptive routing:

| Stage           | Main Improvement                         |
| --------------- | ---------------------------------------- |
| **AODV**        | On-demand routing baseline               |
| **EAURP**       | Energy-aware routing                     |
| **ATEAURP**     | Dynamic trust + energy awareness         |
| **PSE-EAURP**   | Predictive trust + controlled revocation |
| **DRL-EAURP**   | Reinforcement-learning-based routing     |
| **MADRL-EAURP** | Cooperative multi-agent learning         |

This progression allows the project to investigate how increasingly sophisticated decision-making mechanisms affect MANET performance.

---

# Team Contributions

| Member   | Protocol     | Primary Contribution                   |
| -------- | ------------ | -------------------------------------- |
| Member 1 | AODV + EAURP | Baseline and energy-aware routing      |
| Member 2 | ATEAURP      | Adaptive trust-based routing           |
| Member 3 | PSE-EAURP    | Predictive trust and secure revocation |
| Member 4 | DRL-EAURP    | Reinforcement-learning-based routing   |
| Member 5 | MADRL-EAURP  | Multi-agent reinforcement learning     |

Each implementation is maintained in its own directory while following the shared simulation methodology.

---

# Why Compare These Protocols?

The comparison demonstrates the evolution of routing intelligence:

```text
Connectivity
     ↓
Energy Awareness
     ↓
Trust Awareness
     ↓
Trust Prediction
     ↓
Reinforcement Learning
     ↓
Multi-Agent Reinforcement Learning
```

This makes it possible to study the trade-offs between:

* Reliability
* Security
* Energy efficiency
* Adaptability
* Delay
* Throughput
* Computational complexity
* Network lifetime

---

# Technologies Used

* **Python**
* **Network Simulation**
* **MANET Routing**
* **AODV**
* **Trust Management**
* **Energy-Aware Routing**
* **Predictive Analytics**
* **Reinforcement Learning**
* **Multi-Agent Reinforcement Learning**
* **QMIX / VDN**
* **Data Visualization**
* **Performance Analysis**

---

# Project Status

This repository is developed as a **Computer Networks academic project** focused on implementing, simulating, and comparing progressively enhanced MANET routing protocols.

The implementations are organized independently while following a shared simulation baseline to support meaningful comparative analysis.

---

## Repository

**GitHub:**
https://github.com/ar9tomato/Computer-Networks-Project

---

Run it:

```bash
python run_all_experiments.py                           # tuned mode (default)
python run_all_experiments.py --delivery-mode simulated  # PDR derived from routing
python visualize_all.py --output-dir plots/tuned
python visualize_all.py --input results/combined_metrics_simulated.csv \
                        --output-dir plots/simulated

# node-count scaling sweep, fixed speed, density-matched grid
python node_scaling_experiment.py --delivery-mode simulated
```

Baseline for every protocol: 4,000 packets, 100 J/node, speeds [10, 20, 30, 40]
m/s, 100 ms/round. Both delivery modes reproduce byte-identically across runs.

Consolidated MANET routing-protocol comparison across all five members'
protocols: AODV, EAURP, ATEAURP, PSE-EAURP, DRL-EAURP, and MADRL-EAURP. Each
member folder used to have its own duplicated `run_experiments.py` +
`visualize.py`. This refactor replaces all of them with one root-level
runner and one root-level visualizer that produce a single consolidated
results file and one set of comparative charts covering every protocol.

## Folder structure

```
Computer-Networks-Project/
├── engines/                      # protocol implementations, one per member
│   ├── aodv_eaurp/                # Member1_AODV_EAURP_Review2 -> AODVEngine, EAURPEngine
│   ├── ateaurp/                   # Member2_ATEAURP           -> ATEAURPEngine
│   ├── pse_eaurp/                 # Member3_PSEEAURP          -> PSEEAURPEngine
│   ├── drl_eaurp/                 # Member_4_DRL_EAURP        -> DRLEAURPEngine
│   └── madrl_eaurp/               # Member5_MADRL_EAURP       -> MADRLEAURP (torch-based)
│       each with its own core/ (Network, Node, MetricsCollector)
│       and protocols/ (the routing engine itself)
├── engine_adapters/               # the glue that makes one pipeline possible
│   ├── __init__.py                # isolated import helper + common row schema
│   ├── benchmark.py               # shared baseline params + unified metric schema
│   ├── aodv_eaurp_adapter.py       # runs AODV + EAURP
│   ├── ateaurp_adapter.py          # runs ATEAURP
│   ├── pse_eaurp_adapter.py        # runs PSE-EAURP
│   ├── drl_eaurp_adapter.py        # runs DRL-EAURP
│   └── madrl_eaurp_adapter.py      # runs MADRL-EAURP
├── run_all_experiments.py         # root runner, speed sweep, all 6 protocols
├── node_scaling_experiment.py     # root runner, node-count sweep, all 6 protocols
├── visualize_all.py                # root visualizer (all 6 on one chart)
├── results/
│   ├── combined_metrics.csv            # generated - tuned mode, speed sweep
│   ├── combined_metrics_simulated.csv  # generated - simulated mode, speed sweep
│   ├── node_scaling_metrics.csv        # generated - node-count sweep
│   └── metric_applicability.csv        # which 0.0 values are structural
├── plots/
│   ├── tuned/           *.png          # generated (5 charts)
│   ├── simulated/       *.png          # generated (5 charts)
│   └── node_scaling/    *.png          # generated (PDR/delay vs. node count)
└── requirements.txt
```


## `node_scaling_experiment.py`

`run_all_experiments.py` sweeps speed at a fixed 50 nodes.
`node_scaling_experiment.py` instead sweeps node count (default 50 / 100 /
200 / 400) at a fixed speed, so you can see how each protocol holds up as
the network grows. To make that a fair comparison, the deployment grid is
scaled with node count so average node density (and average neighbour
count) stays constant across the sweep; otherwise more nodes on a fixed
grid just means a denser network, which flatters every protocol for a
reason that has nothing to do with how well it coordinates a larger
population. See `density_matched_grid()` in `engine_adapters/benchmark.py`.

```bash
python node_scaling_experiment.py                                  # default sweep, tuned mode
python node_scaling_experiment.py --delivery-mode simulated        # PDR derived from routing
python node_scaling_experiment.py --node-counts 50 100 200 400 800
python node_scaling_experiment.py --skip madrl_eaurp                # torch not installed
```

Writes `results/node_scaling_metrics.csv`, one row per `(protocol,
num_nodes)` pair.


## Usage

```bash
pip install -r requirements.txt

# Run all six protocols across the standard speed sweep (10/20/30/40 m/s)
python run_all_experiments.py

# Optional: customize the sweep or round counts per engine
python run_all_experiments.py --speeds 10 20 30 40 \
    --aodv-eaurp-rounds 400 --aodv-eaurp-packets-per-round 4 \
    --ateaurp-rounds 200 --ateaurp-packets-per-round 20 \
    --pse-eaurp-rounds 200 --pse-eaurp-packets-per-round 20 \
    --drl-eaurp-rounds 200 --drl-eaurp-packets-per-round 20

# Skip an engine (e.g. if torch isn't installed for MADRL-EAURP)
python run_all_experiments.py --skip madrl_eaurp

# Node-count scaling sweep instead of the speed sweep
python node_scaling_experiment.py --delivery-mode simulated

# Plot every protocol present in the results on the same comparative charts
python visualize_all.py
```

`run_all_experiments.py` writes `results/combined_metrics.csv` with one row
per `(protocol, speed)` pair across all engines that ran.
`node_scaling_experiment.py` writes `results/node_scaling_metrics.csv` with
one row per `(protocol, num_nodes)` pair instead. `visualize_all.py` reads
the speed-sweep file and writes one PNG per metric under `plots/`, with
every protocol present plotted together using a fixed, distinct
color/marker/line-style per protocol and a legend.
