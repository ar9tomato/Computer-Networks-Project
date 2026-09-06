# MADRL-EAURP MANET Protocol Simulation

This project simulates the Multi-Agent Deep Reinforcement Learning with EAURP (MADRL-EAURP) routing protocol for Mobile Ad-hoc Networks (MANETs). 

## Technical Overview
- **What is MADRL-EAURP?**: Integrates Deep Reinforcement Learning with EAURP routing protocol.
- **CTDE Architecture (Value Decomposition Networks - VDN)**: Implemented using VDN for decentralized execution.
- **Local State Transformation**: `[Buffer Occupancy, Residual Energy, 1-Hop Neighbor Trust]`.

## Installation Requirements
```bash
pip install numpy pandas matplotlib torch
```

## Running the Project in VS Code
1. Run the experiments (generates metrics in `results/ateaurp_metrics.csv`):
   ```bash
   python run_experiments.py
   ```
2. Generate visualizations (saves plots in `results/plots/`):
   ```bash
   python visualize.py
   ```
3. Package the project:
   ```bash
   python make_zip.py
   ```
