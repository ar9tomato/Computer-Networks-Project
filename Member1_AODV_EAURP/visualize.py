"""
visualize.py

Reads results/aodv_metrics.csv and results/eaurp_metrics.csv (produced by
run_experiments.py) and generates comparative line charts (AODV vs EAURP)
for each required metric, saved as PNG files under graphs/:

    - Speed vs PDR (%)
    - Speed vs Average Delay (ms)
    - Speed vs Packet Loss (%)
    - Speed vs Throughput (kbps)
    - Speed vs Network Lifetime (rounds)

Usage (from the project root):
    python visualize.py
"""

import os

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RESULTS_DIR = "results"
GRAPHS_DIR = "graphs"

AODV_CSV = os.path.join(RESULTS_DIR, "aodv_metrics.csv")
EAURP_CSV = os.path.join(RESULTS_DIR, "eaurp_metrics.csv")

# (column_name, y_axis_label, chart_title, output_filename)
METRICS_TO_PLOT = [
    ("pdr_percent", "Packet Delivery Ratio (%)",
     "Speed vs Packet Delivery Ratio", "speed_vs_pdr.png"),
    ("avg_delay_ms", "Average Delay (ms)",
     "Speed vs Average Delay", "speed_vs_delay.png"),
    ("packet_loss_percent", "Packet Loss (%)",
     "Speed vs Packet Loss", "speed_vs_packet_loss.png"),
    ("throughput_kbps", "Throughput (kbps)",
     "Speed vs Throughput", "speed_vs_throughput.png"),
    ("network_lifetime_rounds", "Network Lifetime (rounds)",
     "Speed vs Network Lifetime", "speed_vs_lifetime.png"),
]


def load_results():
    if not os.path.exists(AODV_CSV) or not os.path.exists(EAURP_CSV):
        raise FileNotFoundError(
            "Could not find results CSVs. Run `python run_experiments.py` first."
        )
    aodv_df = pd.read_csv(AODV_CSV).sort_values("speed_mps")
    eaurp_df = pd.read_csv(EAURP_CSV).sort_values("speed_mps")
    return aodv_df, eaurp_df


def plot_metric(aodv_df, eaurp_df, column, ylabel, title, filename):
    plt.figure(figsize=(7, 5))
    plt.plot(aodv_df["speed_mps"], aodv_df[column],
             marker="o", linewidth=2, label="AODV (baseline)", color="#d62728")
    plt.plot(eaurp_df["speed_mps"], eaurp_df[column],
             marker="s", linewidth=2, label="EAURP", color="#2ca02c")

    plt.title(title, fontsize=13, fontweight="bold")
    plt.xlabel("Node Speed (m/s)", fontsize=11)
    plt.ylabel(ylabel, fontsize=11)
    plt.xticks(sorted(set(aodv_df["speed_mps"]).union(eaurp_df["speed_mps"])))
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend()
    plt.tight_layout()

    os.makedirs(GRAPHS_DIR, exist_ok=True)
    out_path = os.path.join(GRAPHS_DIR, filename)
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Saved {out_path}")


def main():
    aodv_df, eaurp_df = load_results()
    for column, ylabel, title, filename in METRICS_TO_PLOT:
        plot_metric(aodv_df, eaurp_df, column, ylabel, title, filename)
    print("\nAll comparative graphs generated in the 'graphs/' directory.")


if __name__ == "__main__":
    main()
