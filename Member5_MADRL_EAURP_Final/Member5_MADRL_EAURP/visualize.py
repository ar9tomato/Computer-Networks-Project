import os
import pandas as pd
import matplotlib.pyplot as plt

def generate_plots():
    csv_path = 'results/ateaurp_metrics.csv'
    
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found. Run experiments first.")
        return
        
    df = pd.read_csv(csv_path)
    os.makedirs('results/plots', exist_ok=True)
    
    # Matches the exact filenames requested
    charts = [
        ('PDR_percent', 'Speed vs PDR', 'PDR (%)', 'speed_vs_pdr.png'),
        ('Average_Delay_ms', 'Speed vs Latency', 'Average Delay (ms)', 'speed_vs_delay.png'),
        ('Throughput', 'Speed vs Throughput', 'Throughput (pkts/step)', 'speed_vs_throughput.png'),
        ('Lifetime', "Speed vs Lifetime", "Network Lifetime", 'speed_vs_lifetime.png')
    ]
    
    for col, title, ylabel, filename in charts:
        plt.figure(figsize=(8, 5))
        plt.plot(df['Speed_mps'], df[col], marker='o', linestyle='-', color='b', linewidth=2)
        plt.title(title, fontsize=14)
        plt.xlabel('Speed (m/s)', fontsize=12)
        plt.ylabel(ylabel, fontsize=12)
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.xticks(df['Speed_mps'])
        
        save_path = f'results/plots/{filename}'
        plt.savefig(save_path, bbox_inches='tight')
        plt.close()
        print(f"Saved plot: {save_path}")

if __name__ == "__main__":
    generate_plots()
