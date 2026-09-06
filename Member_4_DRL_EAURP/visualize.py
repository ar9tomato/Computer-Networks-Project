import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path


# ---------------------------------------------------------
# File locations
# ---------------------------------------------------------

CSV_FILE = Path("results/drl_eaurp_metrics.csv")
RESULTS_DIR = Path("results")

RESULTS_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------
# Check CSV
# ---------------------------------------------------------

if not CSV_FILE.exists():
    print(f"ERROR: Could not find {CSV_FILE}")
    print("Run this first:")
    print("    python run_experiments.py")
    raise SystemExit(1)


# ---------------------------------------------------------
# Read results
# ---------------------------------------------------------

df = pd.read_csv(CSV_FILE)

print("=" * 60)
print("DRL-EAURP Results Visualization")
print("=" * 60)

print("\nData loaded:")
print(df.to_string(index=False))

print("\nColumns found:")
print(list(df.columns))


# ---------------------------------------------------------
# Helper function
# ---------------------------------------------------------

def make_plot(x, y, xlabel, ylabel, title, filename):
    plt.figure(figsize=(8, 5))

    plt.plot(
        df[x],
        df[y],
        marker="o",
        linewidth=2
    )

    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title(title)

    plt.grid(True, alpha=0.3)

    plt.tight_layout()

    output = RESULTS_DIR / filename

    plt.savefig(output, dpi=300)

    print(f"Created: {output}")

    plt.show()


# ---------------------------------------------------------
# 1. Speed vs Average Delay
# ---------------------------------------------------------

make_plot(
    "speed_mps",
    "avg_delay_ms",
    "Node Speed (m/s)",
    "Average Delay (ms)",
    "DRL-EAURP: Speed vs Average Delay",
    "speed_vs_delay.png"
)


# ---------------------------------------------------------
# 2. Speed vs Network Lifetime
# ---------------------------------------------------------

make_plot(
    "speed_mps",
    "network_lifetime_rounds",
    "Node Speed (m/s)",
    "Network Lifetime (rounds)",
    "DRL-EAURP: Speed vs Network Lifetime",
    "speed_vs_lifetime.png"
)


# ---------------------------------------------------------
# 3. Speed vs PDR
# ---------------------------------------------------------

make_plot(
    "speed_mps",
    "pdr_percent",
    "Node Speed (m/s)",
    "Packet Delivery Ratio (%)",
    "DRL-EAURP: Speed vs PDR",
    "speed_vs_pdr.png"
)


# ---------------------------------------------------------
# 4. Speed vs Throughput
# ---------------------------------------------------------

make_plot(
    "speed_mps",
    "throughput_kbps",
    "Node Speed (m/s)",
    "Throughput (kbps)",
    "DRL-EAURP: Speed vs Throughput",
    "speed_vs_throughput.png"
)


# ---------------------------------------------------------
# Finished
# ---------------------------------------------------------

print("\n" + "=" * 60)
print("All 4 plots generated successfully.")
print(f"Check the '{RESULTS_DIR}' folder.")
print("=" * 60)