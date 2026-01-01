#!/usr/bin/env python3
"""
Validation Plots - Predicted vs Actual Execution Times
Generates academic-quality graphs with confidence intervals

References:
- Graham, R.L. (1969). Bounds on Multiprocessing Timing Anomalies
- Culler et al. (1993). LogP: A Practical Model of Parallel Computation
"""

import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from model.performance_model import (
    load_parameters, T_total, T_init, T_seq, T_comm, T_calc,
    speedup, efficiency, ModelParameters
)

# Style configuration
plt.style.use('seaborn-v0_8-whitegrid')
sns.set_palette("Set2")
plt.rcParams['font.size'] = 12
plt.rcParams['axes.titlesize'] = 14
plt.rcParams['axes.labelsize'] = 12
plt.rcParams['figure.figsize'] = (12, 8)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(SCRIPT_DIR, '..', 'benchmarks', 'results', 'validation')
OUTPUT_DIR = os.path.join(SCRIPT_DIR, 'output')


def load_validation_results(results_file: str) -> pd.DataFrame:
    """Load validation results from CSV."""
    if not os.path.exists(results_file):
        print(f"Error: Results file not found: {results_file}")
        sys.exit(1)

    df = pd.read_csv(results_file)
    return df


def calculate_statistics(data: np.ndarray) -> dict:
    """Calculate mean, std, and 95% confidence interval."""
    n = len(data)
    mean = np.mean(data)
    std = np.std(data, ddof=1)
    sem = std / np.sqrt(n)
    ci_95 = stats.t.ppf(0.975, n-1) * sem if n > 1 else 0

    return {
        'mean': mean,
        'std': std,
        'ci_95': ci_95,
        'n': n
    }


def plot_predicted_vs_actual(df: pd.DataFrame, params: ModelParameters,
                              mode: str = "NFS", output_dir: str = OUTPUT_DIR):
    """
    Plot predicted vs actual execution times with confidence intervals.
    This is the KEY validation graph.
    """
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))

    # Filter by mode
    df_mode = df[df['mode'].str.upper() == mode.upper()]

    workers_list = sorted(df_mode['workers'].unique())
    sizes = sorted(df_mode['size_mb'].unique())

    colors = plt.cm.viridis(np.linspace(0, 0.8, len(sizes)))

    # Left plot: T vs Workers for different sizes
    ax1 = axes[0]
    for idx, size in enumerate(sizes):
        df_size = df_mode[df_mode['size_mb'] == size]

        # Actual measurements
        actual_means = []
        actual_cis = []
        predicted = []

        for n in workers_list:
            df_n = df_size[df_size['workers'] == n]
            if len(df_n) > 0:
                stats_dict = calculate_statistics(df_n['time_seconds'].values)
                actual_means.append(stats_dict['mean'])
                actual_cis.append(stats_dict['ci_95'])
                predicted.append(T_total(size, n, mode, params))

        # Plot actual with error bars
        ax1.errorbar(workers_list[:len(actual_means)], actual_means,
                     yerr=actual_cis, fmt='o-', color=colors[idx],
                     label=f'{size} MB (actual)', capsize=3, markersize=6)

        # Plot predicted (dashed)
        ax1.plot(workers_list[:len(predicted)], predicted,
                 '--', color=colors[idx], alpha=0.7,
                 label=f'{size} MB (predicted)')

    ax1.set_xlabel('Number of Workers')
    ax1.set_ylabel('Execution Time (seconds)')
    ax1.set_title(f'Predicted vs Actual - {mode} Mode\n(Error bars = 95% CI)')
    ax1.legend(loc='upper right', fontsize=9)
    ax1.set_xscale('log', base=2)
    ax1.set_xticks(workers_list)
    ax1.set_xticklabels(workers_list)
    ax1.grid(True, alpha=0.3)

    # Right plot: Parity plot (predicted vs actual)
    ax2 = axes[1]
    all_predicted = []
    all_actual = []
    all_sizes = []

    for size in sizes:
        df_size = df_mode[df_mode['size_mb'] == size]
        for n in workers_list:
            df_n = df_size[df_size['workers'] == n]
            if len(df_n) > 0:
                pred = T_total(size, n, mode, params)
                actual = df_n['time_seconds'].mean()
                all_predicted.append(pred)
                all_actual.append(actual)
                all_sizes.append(size)

    # Scatter plot
    scatter = ax2.scatter(all_predicted, all_actual, c=all_sizes,
                          cmap='viridis', s=80, edgecolor='black', linewidth=0.5)

    # Perfect prediction line
    max_val = max(max(all_predicted), max(all_actual)) * 1.1
    ax2.plot([0, max_val], [0, max_val], 'r--', linewidth=2, label='Perfect prediction')

    # +/- 20% error bands
    ax2.fill_between([0, max_val], [0, max_val*0.8], [0, max_val*1.2],
                     alpha=0.2, color='gray', label='±20% error band')

    # Calculate R² and MAPE
    ss_res = sum((np.array(all_actual) - np.array(all_predicted))**2)
    ss_tot = sum((np.array(all_actual) - np.mean(all_actual))**2)
    r_squared = 1 - (ss_res / ss_tot)
    mape = np.mean(np.abs((np.array(all_actual) - np.array(all_predicted)) / np.array(all_actual))) * 100

    ax2.set_xlabel('Predicted Time (seconds)')
    ax2.set_ylabel('Actual Time (seconds)')
    ax2.set_title(f'Parity Plot - {mode} Mode\nR² = {r_squared:.3f}, MAPE = {mape:.1f}%')
    ax2.legend(loc='upper left')
    ax2.set_xlim(0, max_val)
    ax2.set_ylim(0, max_val)
    ax2.set_aspect('equal')

    plt.colorbar(scatter, ax=ax2, label='File Size (MB)')

    plt.tight_layout()

    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.join(output_dir, f'validation_predicted_vs_actual_{mode}.png')
    plt.savefig(filename, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"Saved: {filename}")

    return fig, r_squared, mape


def plot_speedup_efficiency(df: pd.DataFrame, params: ModelParameters,
                             mode: str = "NFS", output_dir: str = OUTPUT_DIR):
    """
    Plot speedup and efficiency curves.
    Key metrics for parallel performance evaluation.
    """
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))

    df_mode = df[df['mode'].str.upper() == mode.upper()]
    workers_list = sorted(df_mode['workers'].unique())
    sizes = sorted(df_mode['size_mb'].unique())

    colors = plt.cm.plasma(np.linspace(0.1, 0.9, len(sizes)))

    # Get T(1) for speedup calculation
    T_1_dict = {}
    for size in sizes:
        df_1 = df_mode[(df_mode['size_mb'] == size) & (df_mode['workers'] == 1)]
        if len(df_1) > 0:
            T_1_dict[size] = df_1['time_seconds'].mean()

    # Speedup plot
    ax1 = axes[0]
    for idx, size in enumerate(sizes):
        if size not in T_1_dict:
            continue

        T_1 = T_1_dict[size]
        speedups_actual = []
        speedups_pred = []

        for n in workers_list:
            df_n = df_mode[(df_mode['size_mb'] == size) & (df_mode['workers'] == n)]
            if len(df_n) > 0:
                T_n = df_n['time_seconds'].mean()
                speedups_actual.append(T_1 / T_n)
                speedups_pred.append(speedup(size, n, mode, params))

        ax1.plot(workers_list[:len(speedups_actual)], speedups_actual,
                 'o-', color=colors[idx], label=f'{size} MB (actual)', markersize=6)
        ax1.plot(workers_list[:len(speedups_pred)], speedups_pred,
                 '--', color=colors[idx], alpha=0.7, label=f'{size} MB (model)')

    # Ideal speedup line
    ax1.plot(workers_list, workers_list, 'k--', alpha=0.5, label='Ideal (S=n)')

    ax1.set_xlabel('Number of Workers (n)')
    ax1.set_ylabel('Speedup S(n) = T(1)/T(n)')
    ax1.set_title(f'Speedup - {mode} Mode\n(Closer to diagonal = better)')
    ax1.legend(loc='upper left', fontsize=9)
    ax1.set_xscale('log', base=2)
    ax1.set_yscale('log', base=2)
    ax1.set_xticks(workers_list)
    ax1.set_xticklabels(workers_list)
    ax1.grid(True, alpha=0.3)

    # Efficiency plot
    ax2 = axes[1]
    for idx, size in enumerate(sizes):
        if size not in T_1_dict:
            continue

        T_1 = T_1_dict[size]
        efficiencies_actual = []
        efficiencies_pred = []

        for n in workers_list:
            df_n = df_mode[(df_mode['size_mb'] == size) & (df_mode['workers'] == n)]
            if len(df_n) > 0:
                T_n = df_n['time_seconds'].mean()
                speedup_actual = T_1 / T_n
                efficiencies_actual.append(speedup_actual / n)
                efficiencies_pred.append(efficiency(size, n, mode, params))

        ax2.plot(workers_list[:len(efficiencies_actual)], efficiencies_actual,
                 'o-', color=colors[idx], label=f'{size} MB (actual)', markersize=6)
        ax2.plot(workers_list[:len(efficiencies_pred)], efficiencies_pred,
                 '--', color=colors[idx], alpha=0.7, label=f'{size} MB (model)')

    # Ideal efficiency line
    ax2.axhline(y=1.0, color='k', linestyle='--', alpha=0.5, label='Ideal (E=1)')

    ax2.set_xlabel('Number of Workers (n)')
    ax2.set_ylabel('Efficiency E(n) = S(n)/n')
    ax2.set_title(f'Efficiency - {mode} Mode\n(1.0 = perfect parallel efficiency)')
    ax2.legend(loc='upper right', fontsize=9)
    ax2.set_xscale('log', base=2)
    ax2.set_xticks(workers_list)
    ax2.set_xticklabels(workers_list)
    ax2.set_ylim(0, 1.1)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()

    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.join(output_dir, f'speedup_efficiency_{mode}.png')
    plt.savefig(filename, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"Saved: {filename}")

    return fig


def plot_time_decomposition(params: ModelParameters, size_mb: float = 100,
                             workers_list: list = None, mode: str = "NFS",
                             output_dir: str = OUTPUT_DIR):
    """
    Stacked bar chart showing time decomposition.
    Shows contribution of each component: T_init, T_seq, T_comm, T_calc, T_agg
    """
    if workers_list is None:
        workers_list = [1, 2, 4, 8, 16, 32, 64]

    fig, ax = plt.subplots(figsize=(14, 8))

    # Calculate components for each worker count
    t_init = [T_init(n, params) for n in workers_list]
    t_seq = [T_seq(size_mb, params) for n in workers_list]
    t_comm = [T_comm(size_mb, n, mode, params) for n in workers_list]
    t_calc = [T_calc(size_mb, n, params) for n in workers_list]
    t_agg = [params.T_agg for n in workers_list]

    x = np.arange(len(workers_list))
    width = 0.6

    # Stacked bars
    bars1 = ax.bar(x, t_init, width, label='T_init (initialization)', color='#FF6B6B')
    bars2 = ax.bar(x, t_seq, width, bottom=t_init, label='T_seq (sequential)', color='#4ECDC4')
    bars3 = ax.bar(x, t_comm, width, bottom=np.array(t_init)+np.array(t_seq),
                   label='T_comm (communication)', color='#45B7D1')
    bars4 = ax.bar(x, t_calc, width,
                   bottom=np.array(t_init)+np.array(t_seq)+np.array(t_comm),
                   label='T_calc (computation)', color='#96CEB4')
    bars5 = ax.bar(x, t_agg, width,
                   bottom=np.array(t_init)+np.array(t_seq)+np.array(t_comm)+np.array(t_calc),
                   label='T_agg (aggregation)', color='#FFEAA7')

    # Add total time labels on top
    totals = [T_total(size_mb, n, mode, params) for n in workers_list]
    for i, (total, n) in enumerate(zip(totals, workers_list)):
        ax.text(i, total + 0.02*max(totals), f'{total:.2f}s',
                ha='center', va='bottom', fontsize=10, fontweight='bold')

    ax.set_xlabel('Number of Workers')
    ax.set_ylabel('Time (seconds)')
    ax.set_title(f'Time Decomposition - {size_mb} MB, {mode} Mode\n'
                 f'Formula: T_total = T_init + T_seq + T_comm + T_calc + T_agg')
    ax.set_xticks(x)
    ax.set_xticklabels(workers_list)
    ax.legend(loc='upper right', fontsize=10)
    ax.grid(axis='y', alpha=0.3)

    plt.tight_layout()

    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.join(output_dir, f'time_decomposition_{mode}_{size_mb}MB.png')
    plt.savefig(filename, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"Saved: {filename}")

    return fig


def plot_error_analysis(df: pd.DataFrame, params: ModelParameters,
                         mode: str = "NFS", output_dir: str = OUTPUT_DIR):
    """
    Detailed error analysis between model and measurements.
    Shows relative error distribution and identifies model weaknesses.
    """
    fig, axes = plt.subplots(2, 2, figsize=(14, 12))

    df_mode = df[df['mode'].str.upper() == mode.upper()]

    # Calculate errors
    errors = []
    for _, row in df_mode.iterrows():
        predicted = T_total(row['size_mb'], row['workers'], mode, params)
        actual = row['time_seconds']
        rel_error = (predicted - actual) / actual * 100
        errors.append({
            'workers': row['workers'],
            'size_mb': row['size_mb'],
            'predicted': predicted,
            'actual': actual,
            'error_pct': rel_error,
            'abs_error': abs(predicted - actual)
        })

    errors_df = pd.DataFrame(errors)

    # Plot 1: Error distribution histogram
    ax1 = axes[0, 0]
    ax1.hist(errors_df['error_pct'], bins=20, edgecolor='black', alpha=0.7, color='steelblue')
    ax1.axvline(x=0, color='red', linestyle='--', linewidth=2, label='Perfect prediction')
    ax1.axvline(x=errors_df['error_pct'].mean(), color='orange', linestyle='--',
                linewidth=2, label=f'Mean error: {errors_df["error_pct"].mean():.1f}%')
    ax1.set_xlabel('Relative Error (%)')
    ax1.set_ylabel('Frequency')
    ax1.set_title('Error Distribution\n(Positive = overestimate, Negative = underestimate)')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Plot 2: Error vs Workers
    ax2 = axes[0, 1]
    for size in sorted(errors_df['size_mb'].unique()):
        df_size = errors_df[errors_df['size_mb'] == size]
        ax2.plot(df_size['workers'], df_size['error_pct'], 'o-', label=f'{size} MB')
    ax2.axhline(y=0, color='red', linestyle='--', alpha=0.5)
    ax2.axhline(y=20, color='gray', linestyle=':', alpha=0.5)
    ax2.axhline(y=-20, color='gray', linestyle=':', alpha=0.5)
    ax2.set_xlabel('Number of Workers')
    ax2.set_ylabel('Relative Error (%)')
    ax2.set_title('Error vs Number of Workers')
    ax2.legend(loc='best', fontsize=9)
    ax2.set_xscale('log', base=2)
    ax2.grid(True, alpha=0.3)

    # Plot 3: Error vs File Size
    ax3 = axes[1, 0]
    for n in sorted(errors_df['workers'].unique()):
        df_n = errors_df[errors_df['workers'] == n]
        ax3.plot(df_n['size_mb'], df_n['error_pct'], 'o-', label=f'{n} workers')
    ax3.axhline(y=0, color='red', linestyle='--', alpha=0.5)
    ax3.set_xlabel('File Size (MB)')
    ax3.set_ylabel('Relative Error (%)')
    ax3.set_title('Error vs File Size')
    ax3.legend(loc='best', fontsize=9)
    ax3.grid(True, alpha=0.3)

    # Plot 4: Summary statistics box
    ax4 = axes[1, 1]
    ax4.axis('off')

    stats_text = f"""
    ERROR ANALYSIS SUMMARY - {mode} Mode
    ══════════════════════════════════════

    Mean Relative Error:     {errors_df['error_pct'].mean():+.2f} %
    Std Dev:                 {errors_df['error_pct'].std():.2f} %

    Mean Absolute Error:     {errors_df['abs_error'].mean():.3f} s
    Max Absolute Error:      {errors_df['abs_error'].max():.3f} s

    MAPE:                    {np.mean(np.abs(errors_df['error_pct'])):.2f} %

    Predictions within:
      ±10%:  {(np.abs(errors_df['error_pct']) <= 10).sum()} / {len(errors_df)} ({(np.abs(errors_df['error_pct']) <= 10).mean()*100:.0f}%)
      ±20%:  {(np.abs(errors_df['error_pct']) <= 20).sum()} / {len(errors_df)} ({(np.abs(errors_df['error_pct']) <= 20).mean()*100:.0f}%)
      ±30%:  {(np.abs(errors_df['error_pct']) <= 30).sum()} / {len(errors_df)} ({(np.abs(errors_df['error_pct']) <= 30).mean()*100:.0f}%)

    ══════════════════════════════════════
    Model Quality Assessment:
    """

    mape = np.mean(np.abs(errors_df['error_pct']))
    if mape < 10:
        quality = "EXCELLENT - Model is highly accurate"
    elif mape < 20:
        quality = "GOOD - Model is reasonably accurate"
    elif mape < 30:
        quality = "ACCEPTABLE - Model needs refinement"
    else:
        quality = "POOR - Model needs significant revision"

    stats_text += f"    {quality}"

    ax4.text(0.1, 0.9, stats_text, transform=ax4.transAxes, fontsize=11,
             verticalalignment='top', fontfamily='monospace',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    plt.tight_layout()

    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.join(output_dir, f'error_analysis_{mode}.png')
    plt.savefig(filename, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"Saved: {filename}")

    return fig, errors_df


def main():
    """Main function to generate all validation plots."""
    print("\n" + "="*70)
    print("THEORETICAL MODEL VALIDATION - PLOT GENERATION")
    print("="*70 + "\n")

    # Load parameters
    config_file = os.path.join(SCRIPT_DIR, '..', 'model', 'model_config.ini')
    params = load_parameters(config_file)
    print(f"Loaded model parameters from: {config_file}\n")

    # Check for validation results
    results_file = os.path.join(RESULTS_DIR, 'validation_results.csv')

    if os.path.exists(results_file):
        print(f"Loading validation results from: {results_file}\n")
        df = load_validation_results(results_file)

        for mode in ['NFS', 'SCP']:
            if mode.upper() in df['mode'].str.upper().values:
                print(f"\nGenerating plots for {mode} mode...")
                plot_predicted_vs_actual(df, params, mode)
                plot_speedup_efficiency(df, params, mode)
                plot_error_analysis(df, params, mode)
    else:
        print(f"No validation results found at: {results_file}")
        print("Generating theoretical predictions only...\n")

    # Always generate decomposition plots (don't need real data)
    for mode in ['NFS', 'SCP']:
        for size in [100, 500, 1000]:
            print(f"Generating decomposition plot: {size} MB, {mode}")
            plot_time_decomposition(params, size, mode=mode)

    print(f"\n{'='*70}")
    print(f"All plots saved to: {OUTPUT_DIR}")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
