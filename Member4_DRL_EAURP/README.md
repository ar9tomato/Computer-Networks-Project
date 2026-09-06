# Member 4 - DRL-EAURP

Adapted from the supplied DRL-EAURP notebook and the team's Member2 repository interface.

**Important:** the supplied notebook uses tabular Q-learning, not a neural-network DQN. This implementation preserves that source.

State: `<T_avg, E_avg, M_avg>`

Actions: 0=exploitation, 1=exploration

Reward: +1 delivery, -1 loss

Exploitation adjustment: +0.08; exploration adjustment: +0.02

Copy the team's common `core/` directory into this folder, then run:

```powershell
python -m pip install -r requirements.txt
python run_experiments.py
```

Quick test:

```powershell
python run_experiments.py --nodes 50 --rounds 10 --packets-per-round 5
```
