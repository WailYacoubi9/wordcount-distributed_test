#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mesure des composantes du Makefile distribué
Projet Grenoble INP - Ensimag

Exécutez ce script DANS le répertoire contenant votre Makefile.
"""

import subprocess
import time
import os
import sys

# =============================================================================
# CONFIGURATION - ADAPTEZ À VOTRE MAKEFILE
# =============================================================================

# Commandes à mesurer (adaptez selon votre Makefile)
COMMANDS = {
    'clean': 'make clean',
    'compile': 'make compile',
    'split': 'make split',
    'task': 'make list1.txt',      # Une seule tâche parallèle
    'merge': 'make list.txt',       # Fusion finale
    'all_tasks': None,              # Sera géré séparément
}

# Nombre de tâches parallèles
NUM_PARALLEL_TASKS = 20

# Nombre de répétitions pour moyenner
REPETITIONS = 3


def run_command(cmd, silent=True):
    """Exécute une commande et retourne le temps d'exécution."""
    start = time.perf_counter()
    try:
        if silent:
            subprocess.run(cmd, shell=True, check=True,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.run(cmd, shell=True, check=True)
        success = True
    except subprocess.CalledProcessError:
        success = False
    end = time.perf_counter()
    return end - start, success


def measure_with_repetitions(name, setup_cmds, measure_cmd, reps=REPETITIONS):
    """Mesure une commande plusieurs fois avec setup préalable."""
    times = []

    print(f"\n  Mesure de {name}...")

    for i in range(reps):
        # Setup (clean + prérequis)
        for cmd in setup_cmds:
            run_command(cmd)

        # Mesure
        t, success = run_command(measure_cmd)

        if success:
            times.append(t)
            print(f"    Run {i+1}: {t:.2f}s")
        else:
            print(f"    Run {i+1}: ÉCHEC")

    if times:
        avg = sum(times) / len(times)
        print(f"    → Moyenne: {avg:.2f}s")
        return avg
    return None


def main():
    print("=" * 70)
    print("  MESURE DES COMPOSANTES DU MAKEFILE DISTRIBUÉ")
    print("=" * 70)

    results = {}

    # -------------------------------------------------------------------------
    # 1. Mesurer T_compile
    # -------------------------------------------------------------------------
    print("\n[1/5] T_compile (compilation)")
    results['T_compile'] = measure_with_repetitions(
        "compile",
        setup_cmds=['make clean'],
        measure_cmd='make compile'
    )

    # -------------------------------------------------------------------------
    # 2. Mesurer T_split
    # -------------------------------------------------------------------------
    print("\n[2/5] T_split (découpage)")
    results['T_split'] = measure_with_repetitions(
        "split",
        setup_cmds=['make clean', 'make compile'],
        measure_cmd='make split'
    )

    # -------------------------------------------------------------------------
    # 3. Mesurer T_task (une tâche)
    # -------------------------------------------------------------------------
    print("\n[3/5] T_task (une tâche listX.txt)")
    results['T_task'] = measure_with_repetitions(
        "list1.txt",
        setup_cmds=['make clean', 'make compile', 'make split'],
        measure_cmd='make list1.txt'
    )

    # -------------------------------------------------------------------------
    # 4. Mesurer T_merge
    # -------------------------------------------------------------------------
    print("\n[4/5] T_merge (fusion)")

    # Pour mesurer merge, il faut d'abord exécuter toutes les tâches
    def setup_for_merge():
        run_command('make clean')
        run_command('make compile')
        run_command('make split')
        for i in range(1, NUM_PARALLEL_TASKS + 1):
            run_command(f'make list{i}.txt')

    times = []
    print(f"\n  Mesure de merge...")
    for i in range(REPETITIONS):
        setup_for_merge()
        t, success = run_command('make list.txt')
        if success:
            times.append(t)
            print(f"    Run {i+1}: {t:.2f}s")

    if times:
        results['T_merge'] = sum(times) / len(times)
        print(f"    → Moyenne: {results['T_merge']:.2f}s")

    # -------------------------------------------------------------------------
    # 5. Mesurer T_par (toutes les tâches séquentiellement)
    # -------------------------------------------------------------------------
    print("\n[5/5] T_par (20 tâches en séquentiel)")

    times = []
    print(f"\n  Mesure des 20 tâches...")
    for i in range(REPETITIONS):
        run_command('make clean')
        run_command('make compile')
        run_command('make split')

        start = time.perf_counter()
        for j in range(1, NUM_PARALLEL_TASKS + 1):
            run_command(f'make list{j}.txt')
        end = time.perf_counter()

        t = end - start
        times.append(t)
        print(f"    Run {i+1}: {t:.2f}s")

    results['T_par'] = sum(times) / len(times)
    print(f"    → Moyenne: {results['T_par']:.2f}s")

    # -------------------------------------------------------------------------
    # RÉSUMÉ
    # -------------------------------------------------------------------------
    T_seq = (results.get('T_compile', 0) +
             results.get('T_split', 0) +
             results.get('T_merge', 0))

    results['T_seq'] = T_seq
    results['T_total_1'] = T_seq + results.get('T_par', 0)

    print("\n" + "=" * 70)
    print("  RÉSULTATS MESURÉS")
    print("=" * 70)
    print(f"""
  Composantes séquentielles:
    • T_compile = {results.get('T_compile', 'N/A'):.2f}s
    • T_split   = {results.get('T_split', 'N/A'):.2f}s
    • T_merge   = {results.get('T_merge', 'N/A'):.2f}s
    ─────────────────────────
    • T_seq     = {T_seq:.2f}s

  Composantes parallèles:
    • T_task    = {results.get('T_task', 'N/A'):.2f}s (1 tâche)
    • T_par     = {results.get('T_par', 'N/A'):.2f}s (20 tâches)

  Temps total théorique (N=1):
    • T(1)      = {results['T_total_1']:.2f}s

  Comparaison avec T(1) expérimental = 262.39s
    • Différence = {abs(262.39 - results['T_total_1']):.2f}s
""")

    # Export
    with open('measured_times.txt', 'w') as f:
        f.write("# Mesures des composantes\n")
        for key, val in results.items():
            if val is not None:
                f.write(f"{key}={val:.2f}\n")

    print("Résultats sauvegardés dans: measured_times.txt")

    # Code Python à copier
    print("\n" + "-" * 70)
    print("VALEURS À UTILISER DANS amdahl_analysis.py:")
    print("-" * 70)
    print(f"""
# Valeurs mesurées expérimentalement
T_seq_measured = {T_seq:.2f}  # compile + split + merge
T_par_measured = {results.get('T_par', 0):.2f}  # 20 tâches parallèles

# Seulement C reste à calibrer par régression
""")


if __name__ == "__main__":
    main()
