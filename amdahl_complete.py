#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analyse complète du modèle théorique - Loi d'Amdahl
Projet GNU Make Distribué - Grenoble INP Ensimag

Ce script:
1. Lit les données expérimentales du repo
2. Calcule T_seq, T_par, C depuis les données réelles
3. Génère le modèle théorique complet
"""

import numpy as np
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt
import csv
import os

# =============================================================================
# 1. DONNÉES EXPÉRIMENTALES (vos mesures avec 1-20 workers)
# =============================================================================

# Données fournies par l'utilisateur
workers = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10,
                    11, 12, 13, 14, 15, 16, 17, 18, 19, 20])

temps_exp = np.array([
    262.39, 136.15, 91.18, 85.59, 65.02, 55.11, 48.79, 43.23, 40.19, 31.60,
    31.55, 33.60, 30.13, 29.10, 27.71, 27.63, 27.04, 25.82, 20.06, 24.93
])

T1 = temps_exp[0]  # Référence

# =============================================================================
# 2. DONNÉES OVERHEAD (depuis launcher CSV)
# =============================================================================

def lire_overhead_csv():
    """Lit les données d'overhead depuis le CSV launcher"""
    csv_path = "launcher-results/launcher_20251224_174358.csv"
    overhead_data = {}

    if os.path.exists(csv_path):
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                n = int(row['Workers'])
                t = float(row['LauncherTime'])
                if n not in overhead_data:
                    overhead_data[n] = []
                overhead_data[n].append(t)

        # Moyenne par nombre de workers
        return {n: np.mean(times) for n, times in overhead_data.items()}
    return {}

overhead_mesure = lire_overhead_csv()

# =============================================================================
# 3. DONNÉES ARCHITECTURE (depuis Data_Flow.md)
# =============================================================================

# Temps extraits de Data_Flow.md
ARCHITECTURE = {
    'split_time': 1.5,        # "1-2 seconds" → 1.5s moyenne
    'distribute_nfs': 0.4,    # "0.3-0.5 seconds" → 0.4s
    'distribute_scp': 3.0,    # "2-4 seconds" → 3s
    'compile_once': 0.1,      # "~100ms"
    'execute_per_task': 1.25, # "~1000-1500ms" → 1.25s
    'aggregate': 0.05,        # "~50ms"
    'num_partitions': 20,     # Makefile "premier" avec 20 tâches
}

# =============================================================================
# 4. MODÈLES THÉORIQUES
# =============================================================================

def amdahl_simple(N, T_seq, T_par):
    """Loi d'Amdahl classique: T(N) = T_seq + T_par/N"""
    return T_seq + T_par / N

def amdahl_overhead_sqrt(N, T_seq, T_par, C):
    """Amdahl avec overhead √N: T(N) = T_seq + T_par/N + C×√N"""
    return T_seq + T_par / N + C * np.sqrt(N)

def amdahl_overhead_linear(N, T_seq, T_par, C):
    """Amdahl avec overhead linéaire: T(N) = T_seq + T_par/N + C×N"""
    return T_seq + T_par / N + C * N

def amdahl_overhead_log(N, T_seq, T_par, C):
    """Amdahl avec overhead log: T(N) = T_seq + T_par/N + C×log(N)"""
    return T_seq + T_par / N + C * np.log(N)

# =============================================================================
# 5. CALIBRATION ET COMPARAISON DES MODÈLES
# =============================================================================

def calibrer_modele(model_func, workers, temps_exp, p0, bounds, model_name):
    """Calibre un modèle et retourne les paramètres + métriques"""
    try:
        popt, pcov = curve_fit(model_func, workers, temps_exp, p0=p0, bounds=bounds, maxfev=10000)

        # Prédictions
        temps_theo = model_func(workers, *popt)

        # Métriques
        residus = temps_exp - temps_theo
        ss_res = np.sum(residus**2)
        ss_tot = np.sum((temps_exp - np.mean(temps_exp))**2)
        r2 = 1 - (ss_res / ss_tot)
        rmse = np.sqrt(np.mean(residus**2))
        mape = np.mean(np.abs(residus / temps_exp)) * 100

        return {
            'name': model_name,
            'params': popt,
            'r2': r2,
            'rmse': rmse,
            'mape': mape,
            'temps_theo': temps_theo
        }
    except Exception as e:
        print(f"Erreur calibration {model_name}: {e}")
        return None

def main():
    print("\n" + "="*70)
    print("  ANALYSE COMPLÈTE - LOI D'AMDAHL")
    print("  Projet GNU Make Distribué - Ensimag")
    print("="*70)

    # =========================================================================
    # PARTIE 1: Analyse des données d'overhead du launcher
    # =========================================================================
    print("\n" + "-"*70)
    print("1. OVERHEAD MESURÉ (depuis launcher CSV)")
    print("-"*70)

    if overhead_mesure:
        print("\n  Workers | Overhead (s) | Par worker")
        print("  --------|--------------|------------")
        for n in sorted(overhead_mesure.keys()):
            print(f"  {n:>7} | {overhead_mesure[n]:>12.3f} | {overhead_mesure[n]/n:>10.3f}")

        # Régression linéaire sur l'overhead
        N_oh = np.array(sorted(overhead_mesure.keys()))
        T_oh = np.array([overhead_mesure[n] for n in N_oh])

        # Fit linéaire: overhead = a + b*N
        coeffs = np.polyfit(N_oh, T_oh, 1)
        print(f"\n  Modèle overhead: T_overhead = {coeffs[1]:.3f} + {coeffs[0]:.3f} × N")
        print(f"  → Overhead fixe: {coeffs[1]:.3f}s")
        print(f"  → Overhead par worker: {coeffs[0]:.3f}s")
    else:
        print("  Fichier CSV non trouvé")

    # =========================================================================
    # PARTIE 2: Décomposition théorique depuis l'architecture
    # =========================================================================
    print("\n" + "-"*70)
    print("2. DÉCOMPOSITION THÉORIQUE (depuis Data_Flow.md)")
    print("-"*70)

    A = ARCHITECTURE

    # Temps séquentiel = split + compile + aggregate
    T_seq_theo = A['split_time'] + A['compile_once'] + A['aggregate']

    # Temps parallèle = nombre_taches × temps_par_tache
    T_par_theo = A['num_partitions'] * A['execute_per_task']

    # Overhead distribution (NFS)
    T_dist = A['distribute_nfs']

    print(f"""
  Composantes séquentielles:
    • Split:     {A['split_time']:.2f}s
    • Compile:   {A['compile_once']:.2f}s
    • Aggregate: {A['aggregate']:.2f}s
    ─────────────────────────────
    • T_seq =    {T_seq_theo:.2f}s

  Composantes parallèles:
    • {A['num_partitions']} tâches × {A['execute_per_task']:.2f}s = {T_par_theo:.2f}s
    • T_par =    {T_par_theo:.2f}s

  Distribution (NFS):
    • T_dist =   {T_dist:.2f}s
""")

    # =========================================================================
    # PARTIE 3: Calibration de plusieurs modèles
    # =========================================================================
    print("\n" + "-"*70)
    print("3. CALIBRATION DES MODÈLES")
    print("-"*70)

    modeles = []

    # Modèle 1: Amdahl simple
    m1 = calibrer_modele(
        amdahl_simple, workers, temps_exp,
        p0=[20, 240],
        bounds=([0, 0], [np.inf, np.inf]),
        model_name="Amdahl Simple: T_seq + T_par/N"
    )
    if m1: modeles.append(m1)

    # Modèle 2: Amdahl + √N
    m2 = calibrer_modele(
        amdahl_overhead_sqrt, workers, temps_exp,
        p0=[20, 240, 1],
        bounds=([0, 0, 0], [np.inf, np.inf, np.inf]),
        model_name="Amdahl + √N: T_seq + T_par/N + C×√N"
    )
    if m2: modeles.append(m2)

    # Modèle 3: Amdahl + linéaire
    m3 = calibrer_modele(
        amdahl_overhead_linear, workers, temps_exp,
        p0=[20, 240, 0.1],
        bounds=([0, 0, 0], [np.inf, np.inf, np.inf]),
        model_name="Amdahl + Linéaire: T_seq + T_par/N + C×N"
    )
    if m3: modeles.append(m3)

    # Modèle 4: Amdahl + log
    m4 = calibrer_modele(
        amdahl_overhead_log, workers, temps_exp,
        p0=[20, 240, 1],
        bounds=([0, 0, 0], [np.inf, np.inf, np.inf]),
        model_name="Amdahl + Log: T_seq + T_par/N + C×log(N)"
    )
    if m4: modeles.append(m4)

    # Afficher comparaison
    print("\n  Modèle                              |    R²    |  RMSE  |  MAPE")
    print("  ------------------------------------|----------|--------|-------")
    for m in modeles:
        print(f"  {m['name']:<36} | {m['r2']:.4f}   | {m['rmse']:.2f}s  | {m['mape']:.1f}%")

    # Meilleur modèle
    best = max(modeles, key=lambda x: x['r2'])
    print(f"\n  ★ Meilleur modèle: {best['name']}")

    # =========================================================================
    # PARTIE 4: Formule finale avec le meilleur modèle
    # =========================================================================
    print("\n" + "-"*70)
    print("4. FORMULE FINALE CALIBRÉE")
    print("-"*70)

    # Utiliser le modèle simple (le plus élégant si R² similaire)
    T_seq, T_par = m1['params']

    print(f"""
  ┌───────────────────────────────────────────────────────────────┐
  │                                                               │
  │   T(N) = T_seq + T_par / N                                    │
  │                                                               │
  │   T(N) = {T_seq:.2f} + {T_par:.2f} / N                              │
  │                                                               │
  └───────────────────────────────────────────────────────────────┘

  Paramètres calibrés:
    • T_seq = {T_seq:.2f}s  (temps séquentiel incompressible)
    • T_par = {T_par:.2f}s  (temps parallélisable total)

  Vérification:
    • T(1)  = {T_seq:.2f} + {T_par:.2f}/1  = {T_seq + T_par:.2f}s  (mesuré: {temps_exp[0]:.2f}s)
    • T(10) = {T_seq:.2f} + {T_par:.2f}/10 = {T_seq + T_par/10:.2f}s  (mesuré: {temps_exp[9]:.2f}s)
    • T(20) = {T_seq:.2f} + {T_par:.2f}/20 = {T_seq + T_par/20:.2f}s  (mesuré: {temps_exp[19]:.2f}s)

  Qualité:
    • R² = {m1['r2']:.4f} ({m1['r2']*100:.2f}% de variance expliquée)
    • RMSE = {m1['rmse']:.2f}s
    • MAPE = {m1['mape']:.2f}%

  Interprétation physique:
    • Fraction séquentielle: f = {T_seq}/{T_seq+T_par:.2f} = {T_seq/(T_seq+T_par)*100:.1f}%
    • Fraction parallèle:    1-f = {T_par/(T_seq+T_par)*100:.1f}%
    • Speedup max (Amdahl):  S_max = 1/f = {(T_seq+T_par)/T_seq:.2f}
""")

    # =========================================================================
    # PARTIE 5: Calcul de l'overhead C
    # =========================================================================
    print("\n" + "-"*70)
    print("5. ANALYSE DE L'OVERHEAD")
    print("-"*70)

    if m2:
        T_seq2, T_par2, C = m2['params']
        print(f"""
  Modèle avec overhead: T(N) = T_seq + T_par/N + C×√N

  Paramètres:
    • T_seq = {T_seq2:.2f}s
    • T_par = {T_par2:.2f}s
    • C     = {C:.4f}s  (coefficient overhead)

  Interprétation de C = {C:.4f}:
    • À N=4:  overhead = {C:.4f} × √4  = {C*2:.4f}s
    • À N=16: overhead = {C:.4f} × √16 = {C*4:.4f}s
    • À N=20: overhead = {C:.4f} × √20 = {C*np.sqrt(20):.4f}s

  Note: C ≈ 0 signifie que l'overhead est négligeable
        Le modèle simple T(N) = T_seq + T_par/N suffit.
""")

    # =========================================================================
    # PARTIE 6: Décomposition de T_seq
    # =========================================================================
    print("\n" + "-"*70)
    print("6. DÉCOMPOSITION DE T_seq")
    print("-"*70)

    # Proportions estimées depuis l'architecture
    ratio_split = A['split_time'] / T_seq_theo
    ratio_compile = A['compile_once'] / T_seq_theo
    ratio_merge = A['aggregate'] / T_seq_theo

    T_split_est = T_seq * ratio_split
    T_compile_est = T_seq * ratio_compile
    T_merge_est = T_seq * ratio_merge

    print(f"""
  T_seq = {T_seq:.2f}s décomposé en:

    • T_compile = {T_compile_est:.2f}s  ({ratio_compile*100:.0f}% - compilation gcc)
    • T_split   = {T_split_est:.2f}s  ({ratio_split*100:.0f}% - FileSplitter Java)
    • T_merge   = {T_merge_est:.2f}s  ({ratio_merge*100:.0f}% - agrégation cat+awk)

  T_par = {T_par:.2f}s décomposé en:
    • {A['num_partitions']} tâches × {T_par/A['num_partitions']:.2f}s/tâche
""")

    # =========================================================================
    # PARTIE 7: Génération des graphiques
    # =========================================================================
    print("\n" + "-"*70)
    print("7. GÉNÉRATION DES GRAPHIQUES")
    print("-"*70)

    N_smooth = np.linspace(1, 20, 200)
    T_smooth = amdahl_simple(N_smooth, T_seq, T_par)

    fig, axes = plt.subplots(2, 2, figsize=(14, 11))
    fig.suptitle(f'Loi d\'Amdahl - GNU Make Distribué\nT(N) = {T_seq:.1f} + {T_par:.1f}/N  (R² = {m1["r2"]:.4f})',
                 fontsize=14, fontweight='bold')

    # Graphique 1: Temps d'exécution
    ax1 = axes[0, 0]
    ax1.scatter(workers, temps_exp, s=80, c='red', marker='o', label='Expérimental', zorder=5)
    ax1.plot(N_smooth, T_smooth, 'b-', linewidth=2.5, label='Théorique')
    ax1.axhline(y=T_seq, color='green', linestyle='--', alpha=0.7, label=f'T_seq = {T_seq:.1f}s')
    ax1.set_xlabel('Nombre de Workers (N)')
    ax1.set_ylabel('Temps d\'exécution (s)')
    ax1.set_title('Temps d\'exécution vs Workers')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    ax1.set_xlim(0, 21)

    # Graphique 2: Speedup
    ax2 = axes[0, 1]
    speedup_exp = T1 / temps_exp
    speedup_theo = T1 / T_smooth
    ax2.scatter(workers, speedup_exp, s=80, c='red', marker='o', label='Expérimental', zorder=5)
    ax2.plot(N_smooth, speedup_theo, 'b-', linewidth=2.5, label='Théorique')
    ax2.plot(N_smooth, N_smooth, 'g--', linewidth=1.5, alpha=0.7, label='Idéal (S=N)')
    ax2.set_xlabel('Nombre de Workers (N)')
    ax2.set_ylabel('Speedup S(N)')
    ax2.set_title('Accélération (Speedup)')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.set_xlim(0, 21)

    # Graphique 3: Efficacité
    ax3 = axes[1, 0]
    eff_exp = (T1 / temps_exp) / workers * 100
    eff_theo = (T1 / T_smooth) / N_smooth * 100
    ax3.scatter(workers, eff_exp, s=80, c='red', marker='o', label='Expérimental', zorder=5)
    ax3.plot(N_smooth, eff_theo, 'b-', linewidth=2.5, label='Théorique')
    ax3.axhline(y=100, color='green', linestyle='--', alpha=0.7, label='Idéal (100%)')
    ax3.axhline(y=50, color='orange', linestyle=':', alpha=0.7, label='Seuil 50%')
    ax3.set_xlabel('Nombre de Workers (N)')
    ax3.set_ylabel('Efficacité (%)')
    ax3.set_title('Efficacité Parallèle')
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    ax3.set_xlim(0, 21)
    ax3.set_ylim(0, 110)

    # Graphique 4: Décomposition
    ax4 = axes[1, 1]
    T_seq_arr = np.full_like(N_smooth, T_seq)
    T_par_arr = T_par / N_smooth
    ax4.fill_between(N_smooth, 0, T_seq_arr, alpha=0.7, label=f'T_seq = {T_seq:.1f}s', color='#3498db')
    ax4.fill_between(N_smooth, T_seq_arr, T_seq_arr + T_par_arr, alpha=0.7,
                     label=f'T_par/N', color='#2ecc71')
    ax4.scatter(workers, temps_exp, s=60, c='black', marker='x', label='Expérimental', zorder=5)
    ax4.set_xlabel('Nombre de Workers (N)')
    ax4.set_ylabel('Temps (s)')
    ax4.set_title('Décomposition du Temps')
    ax4.legend()
    ax4.grid(True, alpha=0.3)
    ax4.set_xlim(0, 21)

    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.savefig('amdahl_analysis_complete.png', dpi=300, bbox_inches='tight')
    print("  ✓ Graphiques sauvegardés: amdahl_analysis_complete.png")

    # =========================================================================
    # PARTIE 8: Tableau comparatif
    # =========================================================================
    print("\n" + "-"*70)
    print("8. TABLEAU COMPARATIF")
    print("-"*70)

    temps_theo = amdahl_simple(workers, T_seq, T_par)
    print("\n   N | T_exp (s) | T_theo (s) | Erreur  | Speedup | Efficacité")
    print("  ---|-----------|------------|---------|---------|----------")
    for i, N in enumerate(workers):
        err = (temps_exp[i] - temps_theo[i]) / temps_exp[i] * 100
        sp = T1 / temps_exp[i]
        eff = sp / N * 100
        print(f"  {N:>2} | {temps_exp[i]:>9.2f} | {temps_theo[i]:>10.2f} | {err:>+6.1f}% | {sp:>7.2f} | {eff:>8.1f}%")

    # =========================================================================
    # PARTIE 9: Export LaTeX
    # =========================================================================
    print("\n" + "-"*70)
    print("9. EXPORT LATEX")
    print("-"*70)

    latex = f"""% Formule calibrée - Loi d'Amdahl
\\begin{{equation}}
\\boxed{{T(N) = {T_seq:.2f} + \\frac{{{T_par:.2f}}}{{N}}}}
\\end{{equation}}

% Paramètres
\\begin{{table}}[h]
\\centering
\\begin{{tabular}}{{lrl}}
\\toprule
Paramètre & Valeur & Description \\\\
\\midrule
$T_{{\\text{{seq}}}}$ & {T_seq:.2f} s & Temps séquentiel \\\\
$T_{{\\text{{par}}}}$ & {T_par:.2f} s & Temps parallèle total \\\\
$R^2$ & {m1['r2']:.4f} & Qualité de l'ajustement \\\\
\\bottomrule
\\end{{tabular}}
\\end{{table}}
"""

    with open('amdahl_formule.tex', 'w') as f:
        f.write(latex)
    print("  ✓ Export LaTeX: amdahl_formule.tex")

    print("\n" + "="*70)
    print("  ANALYSE TERMINÉE")
    print("="*70)


if __name__ == "__main__":
    main()
