#!/usr/bin/env python3
"""
Mesure des temps pour la loi d'Amdahl sur Grid'5000
Exécuter DANS le répertoire du projet après setup.sh
"""

import subprocess
import time
import os
import sys

# =============================================================================
# CONFIGURATION - Adapter selon votre Makefile
# =============================================================================

NFS_DIR = os.path.expanduser("~/nfs_wordcount")
PROJECT_DIR = os.path.expanduser("~/wordcount-distributed")
NUM_TASKS = 20  # Nombre de tâches parallèles

REPETITIONS = 3  # Nombre de répétitions pour moyenner

# =============================================================================
# FONCTIONS
# =============================================================================

def run(cmd, silent=True):
    """Exécute une commande et retourne (temps, succès)"""
    start = time.perf_counter()
    try:
        if silent:
            subprocess.run(cmd, shell=True, check=True,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.run(cmd, shell=True, check=True)
        return time.perf_counter() - start, True
    except:
        return time.perf_counter() - start, False


def measure(name, cmd, setup_cmd=None, reps=REPETITIONS):
    """Mesure une commande plusieurs fois"""
    times = []
    print(f"\n  Mesure de {name}...")

    for i in range(reps):
        if setup_cmd:
            run(setup_cmd)
        t, ok = run(cmd)
        if ok:
            times.append(t)
            print(f"    Run {i+1}: {t:.3f}s")
        else:
            print(f"    Run {i+1}: ÉCHEC")

    if times:
        avg = sum(times) / len(times)
        print(f"    → Moyenne: {avg:.3f}s")
        return avg
    return 0


def main():
    print("=" * 60)
    print("  MESURE DES COMPOSANTES - LOI D'AMDAHL")
    print("=" * 60)

    os.chdir(NFS_DIR)
    print(f"\nRépertoire: {os.getcwd()}")

    results = {}

    # -------------------------------------------------------------------------
    # 1. T_COMPILE : Compilation du programme wordcount
    # -------------------------------------------------------------------------
    print("\n[1/4] T_COMPILE (compilation gcc)")

    # Supprimer le binaire et recompiler
    results['T_compile'] = measure(
        "gcc wordcount",
        f"gcc -o {NFS_DIR}/wordcount {PROJECT_DIR}/test/wordcount.c",
        setup_cmd=f"rm -f {NFS_DIR}/wordcount"
    )

    # -------------------------------------------------------------------------
    # 2. T_SPLIT : Découpage du fichier (FileSplitter Java)
    # -------------------------------------------------------------------------
    print("\n[2/4] T_SPLIT (découpage fichier)")

    # Créer un fichier test si nécessaire
    test_file = f"{NFS_DIR}/test_input.txt"
    if not os.path.exists(test_file):
        with open(test_file, 'w') as f:
            f.write("Test file for measurement.\n" * 1000)

    results['T_split'] = measure(
        "FileSplitter",
        f"java -cp {PROJECT_DIR}/bin utils.FileSplitter {test_file} {NUM_TASKS} part",
        setup_cmd=f"rm -f {NFS_DIR}/part*.txt"
    )

    # -------------------------------------------------------------------------
    # 3. T_TASK : Temps d'UNE tâche (wordcount sur 1 fichier)
    # -------------------------------------------------------------------------
    print("\n[3/4] T_TASK (une tâche wordcount)")

    # S'assurer que part1.txt existe
    run(f"java -cp {PROJECT_DIR}/bin utils.FileSplitter {test_file} {NUM_TASKS} part")

    results['T_task'] = measure(
        "wordcount part1.txt",
        f"{NFS_DIR}/wordcount {NFS_DIR}/part1.txt > {NFS_DIR}/count1.txt"
    )

    # -------------------------------------------------------------------------
    # 4. T_MERGE : Fusion des résultats (cat + awk)
    # -------------------------------------------------------------------------
    print("\n[4/4] T_MERGE (fusion résultats)")

    # Créer les fichiers count*.txt
    for i in range(1, NUM_TASKS + 1):
        run(f"{NFS_DIR}/wordcount {NFS_DIR}/part{i}.txt > {NFS_DIR}/count{i}.txt 2>/dev/null || echo 0 > {NFS_DIR}/count{i}.txt")

    # Construire la commande de merge
    count_files = " ".join([f"{NFS_DIR}/count{i}.txt" for i in range(1, NUM_TASKS + 1)])
    merge_cmd = f"cat {count_files} | awk '{{sum += $1}} END {{print sum}}' > {NFS_DIR}/total.txt"

    results['T_merge'] = measure("merge (cat + awk)", merge_cmd)

    # -------------------------------------------------------------------------
    # CALCUL DE T_PAR (temps total des tâches en séquentiel)
    # -------------------------------------------------------------------------
    print("\n[BONUS] T_PAR (toutes les tâches séquentiellement)")

    times = []
    for rep in range(REPETITIONS):
        start = time.perf_counter()
        for i in range(1, NUM_TASKS + 1):
            run(f"{NFS_DIR}/wordcount {NFS_DIR}/part{i}.txt > {NFS_DIR}/count{i}.txt")
        t = time.perf_counter() - start
        times.append(t)
        print(f"    Run {rep+1}: {t:.3f}s")

    results['T_par'] = sum(times) / len(times)
    print(f"    → Moyenne: {results['T_par']:.3f}s")

    # -------------------------------------------------------------------------
    # RÉSUMÉ
    # -------------------------------------------------------------------------
    T_seq = results['T_compile'] + results['T_split'] + results['T_merge']
    T_par = results['T_par']
    T_total = T_seq + T_par

    print("\n" + "=" * 60)
    print("  RÉSULTATS MESURÉS")
    print("=" * 60)
    print(f"""
  TEMPS SÉQUENTIEL (T_seq):
    T_compile = {results['T_compile']:.3f}s
    T_split   = {results['T_split']:.3f}s
    T_merge   = {results['T_merge']:.3f}s
    ─────────────────────────
    T_seq     = {T_seq:.3f}s

  TEMPS PARALLÈLE (T_par):
    T_task    = {results['T_task']:.3f}s  (1 tâche)
    T_par     = {T_par:.3f}s  ({NUM_TASKS} tâches)

  TEMPS TOTAL THÉORIQUE (N=1):
    T(1)      = {T_total:.3f}s

  OVERHEAD (C):
    Pour calculer C, comparez T(N) mesuré avec T(N) théorique.
    C = (T_exp - T_seq - T_par/N) / √N

    Exemple avec vos données N=20, T_exp=24.93s:
    C = (24.93 - {T_seq:.2f} - {T_par:.2f}/20) / √20
    C = (24.93 - {T_seq:.2f} - {T_par/20:.2f}) / 4.47
""")

    # Export
    with open(f"{NFS_DIR}/measured_times.txt", 'w') as f:
        f.write(f"# Mesures Grid'5000 - {time.strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"T_COMPILE={results['T_compile']:.3f}\n")
        f.write(f"T_SPLIT={results['T_split']:.3f}\n")
        f.write(f"T_MERGE={results['T_merge']:.3f}\n")
        f.write(f"T_SEQ={T_seq:.3f}\n")
        f.write(f"T_TASK={results['T_task']:.3f}\n")
        f.write(f"T_PAR={T_par:.3f}\n")

    print(f"  Résultats sauvegardés: {NFS_DIR}/measured_times.txt")
    print("")


if __name__ == "__main__":
    main()
