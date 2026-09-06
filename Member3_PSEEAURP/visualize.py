#!/usr/bin/env python3
"""
visualize.py
Reads results/pseaurp_metrics.csv and produces the four standard
comparison plots (PDR, delay, throughput, network lifetime vs speed) so
they can be dropped straight into the Review 2 PPT / report.

Usage
-----
    python visualize.py
    python visualize.py --input results/pseaurp_metrics.csv --outdir results/plots
"""

import argparse
import os

import pandas as pd
import matplotlib.pyplot as plt


def plot_metric(df, x_col, y_col, ylabel, title, outpath):
    plt.figure(figsize=(7, 5))
    plt.plot(df[x_col], df[y_col], marker="o", linewidth=2, color="crimson")
    plt.xlabel("Node Speed (m/s)")
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(outpath, dpi=150)
    plt.close()
    print(f"  saved: {outpath}")


def main():
    parser = argparse.ArgumentParser(description="Plot PSE-EAURP results vs node speed.")
    parser.add_argument("--input", type=str, default="results/pseaurp_metrics.csv")
    parser.add_argument("--outdir", type=str, default="results/plots")
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    df = pd.read_csv(args.input)

    print(f"Loaded {len(df)} rows from {args.input}")
    print("-" * 60)

    plot_metric(df, "speed_mps", "pdr_percent", "Packet Delivery Ratio (%)",
                "PSE-EAURP: PDR vs Node Speed",
                os.path.join(args.outdir, "speed_vs_pdr.png"))

    plot_metric(df, "speed_mps", "avg_delay_ms", "Average Delay (ms)",
                "PSE-EAURP: Delay vs Node Speed",
                os.path.join(args.outdir, "speed_vs_delay.png"))

    plot_metric(df, "speed_mps", "throughput_kbps", "Throughput (kbps)",
                "PSE-EAURP: Throughput vs Node Speed",
                os.path.join(args.outdir, "speed_vs_throughput.png"))

    plot_metric(df, "speed_mps", "network_lifetime_rounds", "Network Lifetime (rounds)",
                "PSE-EAURP: Network Lifetime vs Node Speed",
                os.path.join(args.outdir, "speed_vs_lifetime.png"))

    print("-" * 60)
    print("All plots saved.")


if __name__ == "__main__":
    main()
