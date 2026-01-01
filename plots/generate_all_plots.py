#!/usr/bin/env python3
"""
Master Script - Generate All Validation and Parameter Plots

This script orchestrates the generation of all academic-quality plots
for the theoretical model validation.

Output plots:
1. Parameter Measurements:
   - RMI latency distribution
   - Transfer bandwidth comparison (SCP vs NFS)
   - Wordcount processing speed
   - Initialization time linear model

2. Model Validation:
   - Predicted vs Actual execution times
   - Speedup and Efficiency curves
   - Time decomposition breakdown
   - Error analysis

Usage:
    python generate_all_plots.py [--results-dir DIR] [--output-dir DIR]
"""

import os
import sys
import argparse
from datetime import datetime

# Ensure we can import from parent
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    parser = argparse.ArgumentParser(description='Generate all validation plots')
    parser.add_argument('--results-dir', default=None,
                        help='Directory containing benchmark results')
    parser.add_argument('--output-dir', default=None,
                        help='Output directory for plots')
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    results_dir = args.results_dir or os.path.join(script_dir, '..', 'benchmarks', 'results')
    output_dir = args.output_dir or os.path.join(script_dir, 'output')

    print("\n" + "="*70)
    print("COMPLETE PLOT GENERATION")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    print(f"\nResults directory: {os.path.abspath(results_dir)}")
    print(f"Output directory:  {os.path.abspath(output_dir)}")
    print("="*70 + "\n")

    os.makedirs(output_dir, exist_ok=True)

    # Track success/failure
    success = []
    failed = []

    # 1. Parameter Plots
    print("\n" + "-"*50)
    print("PHASE 1: Parameter Measurement Plots")
    print("-"*50 + "\n")

    try:
        from plot_parameters import (
            plot_rmi_latency, plot_transfer_bandwidth,
            plot_wordcount_speed, plot_init_time
        )

        for name, func in [
            ('RMI Latency', lambda: plot_rmi_latency(results_dir, output_dir)),
            ('Transfer Bandwidth', lambda: plot_transfer_bandwidth(results_dir, output_dir)),
            ('Wordcount Speed', lambda: plot_wordcount_speed(results_dir, output_dir)),
            ('Init Time Model', lambda: plot_init_time(results_dir, output_dir)),
        ]:
            try:
                result = func()
                if result:
                    success.append(name)
                else:
                    failed.append(f"{name} (no data)")
            except Exception as e:
                failed.append(f"{name}: {e}")
                print(f"  Warning: {name} failed - {e}")

    except ImportError as e:
        failed.append(f"Parameter plots: Import error - {e}")
        print(f"  Error importing plot_parameters: {e}")

    # 2. Validation Plots
    print("\n" + "-"*50)
    print("PHASE 2: Model Validation Plots")
    print("-"*50 + "\n")

    try:
        from plot_validation import (
            plot_predicted_vs_actual, plot_speedup_efficiency,
            plot_time_decomposition, plot_error_analysis,
            load_validation_results
        )
        sys.path.insert(0, os.path.join(script_dir, '..'))
        from model.performance_model import load_parameters, ModelParameters

        # Load model parameters
        config_file = os.path.join(script_dir, '..', 'model', 'model_config.ini')
        params = load_parameters(config_file)

        # Check for validation results
        val_file = os.path.join(results_dir, 'validation', 'validation_results.csv')

        if os.path.exists(val_file):
            df = load_validation_results(val_file)

            for mode in ['NFS', 'SCP']:
                if mode.upper() in df['mode'].str.upper().values:
                    for name, func in [
                        (f'Predicted vs Actual ({mode})',
                         lambda m=mode: plot_predicted_vs_actual(df, params, m, output_dir)),
                        (f'Speedup/Efficiency ({mode})',
                         lambda m=mode: plot_speedup_efficiency(df, params, m, output_dir)),
                        (f'Error Analysis ({mode})',
                         lambda m=mode: plot_error_analysis(df, params, m, output_dir)),
                    ]:
                        try:
                            result = func()
                            if result:
                                success.append(name)
                        except Exception as e:
                            failed.append(f"{name}: {e}")
        else:
            print(f"  No validation data found at: {val_file}")
            failed.append("Validation plots (no data)")

        # Decomposition plots (don't need real data)
        for mode in ['NFS', 'SCP']:
            for size in [100, 500]:
                name = f'Time Decomposition ({size}MB, {mode})'
                try:
                    plot_time_decomposition(params, size, mode=mode, output_dir=output_dir)
                    success.append(name)
                except Exception as e:
                    failed.append(f"{name}: {e}")

    except ImportError as e:
        failed.append(f"Validation plots: Import error - {e}")
        print(f"  Error importing plot_validation: {e}")

    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"\nSuccessful plots: {len(success)}")
    for s in success:
        print(f"  ✓ {s}")

    if failed:
        print(f"\nFailed/Skipped: {len(failed)}")
        for f in failed:
            print(f"  ✗ {f}")

    print(f"\n{'='*70}")
    print(f"Output saved to: {os.path.abspath(output_dir)}")
    print("="*70 + "\n")

    # List generated files
    if os.path.exists(output_dir):
        files = [f for f in os.listdir(output_dir) if f.endswith('.png')]
        if files:
            print("Generated files:")
            for f in sorted(files):
                size = os.path.getsize(os.path.join(output_dir, f))
                print(f"  {f} ({size/1024:.1f} KB)")


if __name__ == "__main__":
    main()
