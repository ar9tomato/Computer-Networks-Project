#!/usr/bin/env python3
"""
visualize_all.py

Reads results/combined_metrics.csv (produced by run_all_experiments.py)
and plots ONE comparative chart per metric with AODV, EAURP, and ATEAURP
all on the same axes, replacing the old per-member `visualize.py`
scripts. Saved as PNGs under plots/:

    - speed_vs_pdr.png
    - speed_vs_throughput.png
    - speed_vs_delay.png
    - speed_vs_lifetime.png
    - speed_vs_packet_loss.png (bonus: same source data already has it)

Usage (from the project root):
    python visualize_all.py
"""

import argparse
import os

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

DEFAULT_INPUT = "results/combined_metrics.csv"
DEFAULT_OUTPUT_DIR = "plots"

# (column, ylabel, title, filename)
METRICS_TO_PLOT = [
    ("pdr_percent", "Packet Delivery Ratio (%)",
     "Speed vs Packet Delivery Ratio", "speed_vs_pdr.png"),
    ("throughput_kbps", "Throughput (kbps)",
     "Speed vs Throughput", "speed_vs_throughput.png"),
    ("avg_delay_ms", "Average Delay (ms)",
     "Speed vs Average Delay", "speed_vs_delay.png"),
    ("network_lifetime_rounds", "Network Lifetime (rounds)",
     "Speed vs Network Lifetime", "speed_vs_lifetime.png"),
    ("packet_loss_percent", "Packet Loss (%)",
     "Speed vs Packet Loss", "speed_vs_packet_loss.png"),
]

# Distinct, stable style per protocol so charts are consistent across runs
# regardless of which protocols are present.
PROTOCOL_STYLES = {
    "AODV":        {"color": "#d62728", "marker": "o", "linestyle": "-"},
    "EAURP":       {"color": "#2ca02c", "marker": "s", "linestyle": "--"},
    "ATEAURP":     {"color": "#1f77b4", "marker": "^", "linestyle": "-."},
    "PSE-EAURP":   {"color": "#9467bd", "marker": "D", "linestyle": ":"},
    "DRL-EAURP":   {"color": "#ff7f0e", "marker": "v", "linestyle": "-"},
    "MADRL-EAURP": {"color": "#17becf", "marker": "P", "linestyle": "--"},
}
FALLBACK_STYLE_CYCLE = [
    {"color": "#e377c2", "marker": "X", "linestyle": "-."},
    {"color": "#7f7f7f", "marker": "*", "linestyle": ":"},
]


def load_results(input_path):
    if not os.path.exists(input_path):
        raise FileNotFoundError(
            f"Could not find {input_path}. Run `python run_all_experiments.py` first."
        )
    df = pd.read_csv(input_path)
    if "protocol" not in df.columns or "speed_mps" not in df.columns:
        raise ValueError(f"{input_path} is missing required 'protocol'/'speed_mps' columns.")
    return df


def plot_metric(df, column, ylabel, title, filepath):
    if column not in df.columns:
        print(f"  skipping {title}: column '{column}' not present in results")
        return

    plt.figure(figsize=(8, 5.5))
    fallback_idx = 0
    for protocol in sorted(df["protocol"].unique()):
        subset = df[df["protocol"] == protocol].sort_values("speed_mps")
        if subset[column].isna().all():
            continue
        style = PROTOCOL_STYLES.get(protocol)
        if style is None:
            style = FALLBACK_STYLE_CYCLE[fallback_idx % len(FALLBACK_STYLE_CYCLE)]
            fallback_idx += 1
        plt.plot(subset["speed_mps"], subset[column],
                  marker=style["marker"], linestyle=style["linestyle"],
                  color=style["color"], linewidth=2, markersize=7, label=protocol)

    plt.title(title, fontsize=13, fontweight="bold")
    plt.xlabel("Node Speed (m/s)", fontsize=11)
    plt.ylabel(ylabel, fontsize=11)
    plt.grid(True, alpha=0.3)
    plt.legend(title="Protocol")
    plt.tight_layout()
    plt.savefig(filepath, dpi=150)
    plt.close()
    print(f"  wrote {filepath}")


def main():
    parser = argparse.ArgumentParser(
        description="Plot comparative AODV vs EAURP vs ATEAURP charts from combined_metrics.csv."
    )
    parser.add_argument("--input", type=str, default=DEFAULT_INPUT,
                         help=f"Consolidated metrics CSV (default: {DEFAULT_INPUT}).")
    parser.add_argument("--output-dir", type=str, default=DEFAULT_OUTPUT_DIR,
                         help=f"Directory to write PNGs to (default: {DEFAULT_OUTPUT_DIR}).")
    args = parser.parse_args()

    df = load_results(args.input)
    os.makedirs(args.output_dir, exist_ok=True)

    print(f"Plotting {sorted(df['protocol'].unique())} across speeds {sorted(df['speed_mps'].unique())} ...")
    for column, ylabel, title, filename in METRICS_TO_PLOT:
        plot_metric(df, column, ylabel, title, os.path.join(args.output_dir, filename))

    print("Done.")


if __name__ == "__main__":
    main()
