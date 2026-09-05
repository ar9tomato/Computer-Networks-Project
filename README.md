# ATEAURP MANET Simulation Engine

An implementation and performance analysis of the **Adaptive Trust-Enhanced Energy-Aware Unicast Routing Protocol (ATEAURP)** for Mobile Ad-hoc Networks (MANETs).

## Features
- Dynamic trust-based routing engine with malicious node isolation.
- Energy consumption & network lifetime tracking.
- Automated node speed sweep experiments (10 to 40 m/s).
- Metric visualization generation (PDR, Delay, Throughput, Lifetime).

## Project Structure
```text
├── core/               # Network, node, and metrics modules
├── protocols/          # ATEAURP routing and trust engine implementation
├── results/            # Exported metrics (CSV) and plots (PNG)
├── run_experiments.py  # Simulation CLI entry point
├── visualize.py        # Plot generation script
└── requirements.txt    # Project dependencies
