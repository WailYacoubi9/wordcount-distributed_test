#!/usr/bin/env python3
"""
Parameter Measurement Plots
Visualizes measured parameters with confidence intervals

Generates plots for:
- RMI latency and overhead
- Transfer bandwidth (SCP vs NFS)
- Wordcount processing speed
- Initialization time model
"""

import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from scipy.optimize import curve_fit

# Style configuration
plt.style.use('seaborn-v0_8-whitegrid')
sns.set_palette("Set2")
plt.rcParams['font.size'] = 12
plt.rcParams['axes.titlesize'] = 14
plt.rcParams['axes.labelsize'] = 12
plt.rcParams['figure.figsize'] = (12, 8)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(SCRIPT_DIR, '..', 'benchmarks', 'results')
OUTPUT_DIR = os.path.join(SCRIPT_DIR, 'output')


def calculate_ci(data: np.ndarray, confidence: float = 0.95) -> tuple:
    """Calculate confidence interval."""
    n = len(data)
    mean = np.mean(data)
    std = np.std(data, ddof=1)
    sem = std / np.sqrt(n)
    h = stats.t.ppf((1 + confidence) / 2, n - 1) * sem
    return mean, std, h


def plot_rmi_latency(results_dir: str = RESULTS_DIR, output_dir: str = OUTPUT_DIR):
    """
    Plot RMI latency measurements.
    Shows L_rmi (lookup) and o_rmi (overhead) with confidence intervals.
    """
    rmi_file = os.path.join(results_dir, 'rmi', 'rmi_latency.csv')

    if not os.path.exists(rmi_file):
        print(f"RMI results not found: {rmi_file}")
        return None

    df = pd.read_csv(rmi_file)

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # Plot 1: Lookup latency distribution
    ax1 = axes[0]
    lookup_times = df['lookup_time_ms'].dropna()
    mean, std, ci = calculate_ci(lookup_times.values)

    ax1.hist(lookup_times, bins=30, edgecolor='black', alpha=0.7, color='steelblue')
    ax1.axvline(x=mean, color='red', linestyle='--', linewidth=2,
                label=f'Mean: {mean:.2f} ms')
    ax1.axvspan(mean - ci, mean + ci, alpha=0.3, color='red',
                label=f'95% CI: [{mean-ci:.2f}, {mean+ci:.2f}]')

    ax1.set_xlabel('Lookup Time (ms)')
    ax1.set_ylabel('Frequency')
    ax1.set_title('RMI Naming.lookup() Latency (L_rmi)\nLogP Model Parameter')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Plot 2: Execution overhead distribution
    ax2 = axes[1]
    exec_times = df['execute_time_ms'].dropna()
    mean, std, ci = calculate_ci(exec_times.values)

    ax2.hist(exec_times, bins=30, edgecolor='black', alpha=0.7, color='coral')
    ax2.axvline(x=mean, color='red', linestyle='--', linewidth=2,
                label=f'Mean: {mean:.2f} ms')
    ax2.axvspan(mean - ci, mean + ci, alpha=0.3, color='red',
                label=f'95% CI: [{mean-ci:.2f}, {mean+ci:.2f}]')

    ax2.set_xlabel('Execution Overhead (ms)')
    ax2.set_ylabel('Frequency')
    ax2.set_title('RMI executeCommand() Overhead (o_rmi)\nLogP Model Parameter')
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()

    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.join(output_dir, 'rmi_latency_distribution.png')
    plt.savefig(filename, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"Saved: {filename}")

    return fig


def plot_transfer_bandwidth(results_dir: str = RESULTS_DIR, output_dir: str = OUTPUT_DIR):
    """
    Plot transfer benchmark results.
    Compares SCP vs NFS bandwidth and latency.
    """
    transfer_file = os.path.join(results_dir, 'transfer', 'transfer_results.csv')

    if not os.path.exists(transfer_file):
        print(f"Transfer results not found: {transfer_file}")
        return None

    df = pd.read_csv(transfer_file)

    fig, axes = plt.subplots(2, 2, figsize=(14, 12))

    # Plot 1: Bandwidth vs File Size
    ax1 = axes[0, 0]
    for mode in ['SCP', 'NFS']:
        df_mode = df[df['mode'] == mode]
        sizes = sorted(df_mode['size_mb'].unique())

        means = []
        cis = []
        for size in sizes:
            bw_data = df_mode[df_mode['size_mb'] == size]['bandwidth_mbps'].values
            mean, std, ci = calculate_ci(bw_data)
            means.append(mean)
            cis.append(ci)

        color = '#FF6B6B' if mode == 'SCP' else '#4ECDC4'
        ax1.errorbar(sizes, means, yerr=cis, fmt='o-', color=color,
                     label=mode, capsize=4, markersize=6)

    ax1.set_xlabel('File Size (MB)')
    ax1.set_ylabel('Bandwidth (MB/s)')
    ax1.set_title('Transfer Bandwidth: SCP vs NFS\n(Higher is better)')
    ax1.legend()
    ax1.set_xscale('log')
    ax1.grid(True, alpha=0.3)

    # Plot 2: Latency vs File Size
    ax2 = axes[0, 1]
    for mode in ['SCP', 'NFS']:
        df_mode = df[df['mode'] == mode]
        sizes = sorted(df_mode['size_mb'].unique())

        means = []
        cis = []
        for size in sizes:
            lat_data = df_mode[df_mode['size_mb'] == size]['latency_ms'].values
            mean, std, ci = calculate_ci(lat_data)
            means.append(mean)
            cis.append(ci)

        color = '#FF6B6B' if mode == 'SCP' else '#4ECDC4'
        ax2.errorbar(sizes, means, yerr=cis, fmt='o-', color=color,
                     label=mode, capsize=4, markersize=6)

    ax2.set_xlabel('File Size (MB)')
    ax2.set_ylabel('Latency (ms)')
    ax2.set_title('Transfer Latency: SCP vs NFS\n(Lower is better)')
    ax2.legend()
    ax2.set_xscale('log')
    ax2.grid(True, alpha=0.3)

    # Plot 3: Bandwidth distribution (box plot)
    ax3 = axes[1, 0]
    scp_bw = df[df['mode'] == 'SCP']['bandwidth_mbps']
    nfs_bw = df[df['mode'] == 'NFS']['bandwidth_mbps']

    bp = ax3.boxplot([scp_bw, nfs_bw], labels=['SCP', 'NFS'], patch_artist=True)
    bp['boxes'][0].set_facecolor('#FF6B6B')
    bp['boxes'][1].set_facecolor('#4ECDC4')

    ax3.set_ylabel('Bandwidth (MB/s)')
    ax3.set_title('Bandwidth Distribution\n(All file sizes combined)')
    ax3.grid(True, alpha=0.3)

    # Plot 4: Summary statistics
    ax4 = axes[1, 1]
    ax4.axis('off')

    scp_bw_mean, scp_bw_std, scp_bw_ci = calculate_ci(scp_bw.values)
    nfs_bw_mean, nfs_bw_std, nfs_bw_ci = calculate_ci(nfs_bw.values)
    scp_lat = df[df['mode'] == 'SCP']['latency_ms']
    nfs_lat = df[df['mode'] == 'NFS']['latency_ms']
    scp_lat_mean, scp_lat_std, scp_lat_ci = calculate_ci(scp_lat.values)
    nfs_lat_mean, nfs_lat_std, nfs_lat_ci = calculate_ci(nfs_lat.values)

    stats_text = f"""
    TRANSFER PARAMETER SUMMARY
    ════════════════════════════════════════════

    SCP Transfer:
      Bandwidth (BW_scp):  {scp_bw_mean:.1f} ± {scp_bw_ci:.1f} MB/s
      Latency (L_scp):     {scp_lat_mean:.1f} ± {scp_lat_ci:.1f} ms

    NFS Transfer:
      Bandwidth (BW_nfs):  {nfs_bw_mean:.1f} ± {nfs_bw_ci:.1f} MB/s
      Latency (L_nfs):     {nfs_lat_mean:.1f} ± {nfs_lat_ci:.1f} ms

    ════════════════════════════════════════════

    NFS Speedup Factor:
      Bandwidth: {nfs_bw_mean/scp_bw_mean:.1f}x faster
      Latency:   {scp_lat_mean/nfs_lat_mean:.1f}x lower

    ════════════════════════════════════════════
    """

    ax4.text(0.1, 0.9, stats_text, transform=ax4.transAxes, fontsize=11,
             verticalalignment='top', fontfamily='monospace',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    plt.tight_layout()

    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.join(output_dir, 'transfer_benchmark.png')
    plt.savefig(filename, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"Saved: {filename}")

    return fig


def plot_wordcount_speed(results_dir: str = RESULTS_DIR, output_dir: str = OUTPUT_DIR):
    """
    Plot wordcount processing speed (V_wc).
    Shows lines/second processing rate.
    """
    wc_file = os.path.join(results_dir, 'wordcount', 'wordcount_speed.csv')

    if not os.path.exists(wc_file):
        print(f"Wordcount results not found: {wc_file}")
        return None

    df = pd.read_csv(wc_file)

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # Plot 1: Speed vs File Size
    ax1 = axes[0]
    sizes = sorted(df['lines'].unique())

    means = []
    cis = []
    for size in sizes:
        speed_data = df[df['lines'] == size]['lines_per_second'].values
        mean, std, ci = calculate_ci(speed_data)
        means.append(mean)
        cis.append(ci)

    ax1.errorbar(sizes, means, yerr=cis, fmt='o-', color='steelblue',
                 capsize=4, markersize=8, linewidth=2)
    ax1.axhline(y=np.mean(means), color='red', linestyle='--',
                label=f'Mean V_wc: {np.mean(means):.0f} lines/s')

    ax1.set_xlabel('File Size (lines)')
    ax1.set_ylabel('Processing Speed (lines/second)')
    ax1.set_title('Wordcount Processing Speed (V_wc)\n(Higher is better)')
    ax1.legend()
    ax1.set_xscale('log')
    ax1.grid(True, alpha=0.3)

    # Plot 2: Distribution
    ax2 = axes[1]
    all_speeds = df['lines_per_second'].values
    mean, std, ci = calculate_ci(all_speeds)

    ax2.hist(all_speeds, bins=30, edgecolor='black', alpha=0.7, color='steelblue')
    ax2.axvline(x=mean, color='red', linestyle='--', linewidth=2,
                label=f'Mean: {mean:.0f} lines/s')
    ax2.axvspan(mean - ci, mean + ci, alpha=0.3, color='red',
                label=f'95% CI: [{mean-ci:.0f}, {mean+ci:.0f}]')

    ax2.set_xlabel('Processing Speed (lines/second)')
    ax2.set_ylabel('Frequency')
    ax2.set_title('Wordcount Speed Distribution\nParameter for T_calc')
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()

    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.join(output_dir, 'wordcount_speed.png')
    plt.savefig(filename, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"Saved: {filename}")

    return fig


def linear_model(n, alpha, beta):
    """Linear model for T_init: T = alpha*n + beta"""
    return alpha * n + beta


def plot_init_time(results_dir: str = RESULTS_DIR, output_dir: str = OUTPUT_DIR):
    """
    Plot initialization time model.
    Shows T_init(n) = alpha*n + beta with linear regression.
    """
    init_file = os.path.join(results_dir, 'init', 'init_times.csv')

    if not os.path.exists(init_file):
        print(f"Init results not found: {init_file}")
        return None

    df = pd.read_csv(init_file)

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # Get unique worker counts
    workers = sorted(df['workers'].unique())

    # Calculate means and CIs
    means = []
    cis = []
    for n in workers:
        times = df[df['workers'] == n]['init_time_seconds'].values
        mean, std, ci = calculate_ci(times)
        means.append(mean)
        cis.append(ci)

    # Fit linear model
    popt, pcov = curve_fit(linear_model, workers, means)
    alpha, beta = popt
    perr = np.sqrt(np.diag(pcov))

    # Calculate R²
    y_pred = [linear_model(n, alpha, beta) for n in workers]
    ss_res = sum((np.array(means) - np.array(y_pred))**2)
    ss_tot = sum((np.array(means) - np.mean(means))**2)
    r_squared = 1 - (ss_res / ss_tot)

    # Plot 1: Data with fitted model
    ax1 = axes[0]
    ax1.errorbar(workers, means, yerr=cis, fmt='o', color='steelblue',
                 capsize=4, markersize=8, label='Measurements')

    n_fit = np.linspace(min(workers), max(workers), 100)
    ax1.plot(n_fit, linear_model(n_fit, alpha, beta), 'r-', linewidth=2,
             label=f'Model: T = {alpha:.3f}n + {beta:.3f}')

    ax1.fill_between(n_fit,
                     linear_model(n_fit, alpha - perr[0], beta - perr[1]),
                     linear_model(n_fit, alpha + perr[0], beta + perr[1]),
                     alpha=0.3, color='red', label='95% CI on fit')

    ax1.set_xlabel('Number of Workers (n)')
    ax1.set_ylabel('Initialization Time (seconds)')
    ax1.set_title(f'Initialization Time Model: T_init(n) = αn + β\n'
                  f'α = {alpha:.3f} ± {perr[0]:.3f}, β = {beta:.3f} ± {perr[1]:.3f}, R² = {r_squared:.4f}')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Plot 2: Residuals
    ax2 = axes[1]
    residuals = np.array(means) - np.array(y_pred)
    ax2.scatter(workers, residuals, s=80, edgecolor='black')
    ax2.axhline(y=0, color='red', linestyle='--', linewidth=2)

    ax2.set_xlabel('Number of Workers (n)')
    ax2.set_ylabel('Residual (Actual - Predicted)')
    ax2.set_title('Residual Analysis\n(Should be randomly distributed around 0)')
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()

    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.join(output_dir, 'init_time_model.png')
    plt.savefig(filename, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"Saved: {filename}")

    # Print summary
    print(f"\nInitialization Model Parameters:")
    print(f"  alpha = {alpha:.4f} ± {perr[0]:.4f} s/worker")
    print(f"  beta  = {beta:.4f} ± {perr[1]:.4f} s")
    print(f"  R²    = {r_squared:.4f}")

    return fig


def main():
    """Generate all parameter plots."""
    print("\n" + "="*70)
    print("PARAMETER MEASUREMENT VISUALIZATION")
    print("="*70 + "\n")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Generating parameter plots...\n")

    # Try to generate each plot
    plot_rmi_latency()
    plot_transfer_bandwidth()
    plot_wordcount_speed()
    plot_init_time()

    print(f"\n{'='*70}")
    print(f"All parameter plots saved to: {OUTPUT_DIR}")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
