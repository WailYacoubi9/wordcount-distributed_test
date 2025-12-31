#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analyse de la Loi d'Amdahl pour GNU Make Distribué
Projet Grenoble INP - Ensimag

Ce script analyse les résultats expérimentaux d'exécution distribuée
et calibre un modèle théorique basé sur la loi d'Amdahl modifiée.

Modèle: T(N) = T_seq + T_par/N + C×√N

Auteur: Analyse automatique
Date: 2025
"""

import numpy as np
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings('ignore')

# =============================================================================
# DONNÉES EXPÉRIMENTALES
# =============================================================================

# Nombre de workers
workers = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10,
                    11, 12, 13, 14, 15, 16, 17, 18, 19, 20])

# Temps d'exécution mesurés (secondes)
temps_experimental = np.array([
    262.39, 136.15, 91.18, 85.59, 65.02, 55.11, 48.79, 43.23, 40.19, 31.60,
    31.55, 33.60, 30.13, 29.10, 27.71, 27.63, 27.04, 25.82, 20.06, 24.93
])

# Temps de référence (1 worker)
T1 = temps_experimental[0]

# =============================================================================
# MODÈLE THÉORIQUE - LOI D'AMDAHL MODIFIÉE
# =============================================================================

def amdahl_model(N, T_seq, T_par, C):
    """
    Modèle d'Amdahl modifié avec overhead de coordination.

    T(N) = T_seq + T_par/N + C×√N

    Paramètres:
    -----------
    N : int ou array
        Nombre de workers
    T_seq : float
        Temps séquentiel incompressible (compile + split + merge)
    T_par : float
        Temps total des tâches parallélisables
    C : float
        Coefficient d'overhead (coordination Master-Workers)

    Retourne:
    ---------
    float ou array : Temps d'exécution prédit
    """
    return T_seq + T_par / N + C * np.sqrt(N)


def speedup_theorique(N, T_seq, T_par, C):
    """Calcule le speedup théorique S(N) = T(1)/T(N)"""
    T1_theo = amdahl_model(1, T_seq, T_par, C)
    TN_theo = amdahl_model(N, T_seq, T_par, C)
    return T1_theo / TN_theo


def efficacite_theorique(N, T_seq, T_par, C):
    """Calcule l'efficacité théorique E(N) = S(N)/N"""
    return speedup_theorique(N, T_seq, T_par, C) / N


# =============================================================================
# CALIBRATION PAR RÉGRESSION
# =============================================================================

def calibrer_modele(workers, temps_exp, verbose=True):
    """
    Calibre les paramètres du modèle par régression non-linéaire.

    Contraintes:
    - T_seq > 15s (temps séquentiel réaliste)
    - C > 0.5s (overhead minimal)
    """

    # Estimation initiale des paramètres
    p0 = [20.0, 240.0, 1.0]  # T_seq, T_par, C

    # Bornes des paramètres
    # T_seq: [15, 100], T_par: [50, 500], C: [0.5, 20]
    bounds = ([15.0, 50.0, 0.5], [100.0, 500.0, 20.0])

    try:
        # Régression avec scipy.optimize.curve_fit
        popt, pcov = curve_fit(
            amdahl_model,
            workers,
            temps_exp,
            p0=p0,
            bounds=bounds,
            method='trf',  # Trust Region Reflective
            maxfev=10000
        )

        T_seq, T_par, C = popt

        # Calcul des incertitudes (écarts-types)
        perr = np.sqrt(np.diag(pcov))

        if verbose:
            print("\n" + "="*70)
            print("CALIBRATION DU MODÈLE D'AMDAHL")
            print("="*70)
            print(f"\nParamètres optimisés:")
            print(f"  • T_seq = {T_seq:.2f} ± {perr[0]:.2f} s")
            print(f"  • T_par = {T_par:.2f} ± {perr[1]:.2f} s")
            print(f"  • C     = {C:.2f} ± {perr[2]:.2f} s")

        return popt, pcov

    except Exception as e:
        print(f"Erreur lors de la calibration: {e}")
        return None, None


def calculer_metriques(workers, temps_exp, params):
    """Calcule les métriques de qualité du modèle."""

    T_seq, T_par, C = params

    # Prédictions du modèle
    temps_theo = amdahl_model(workers, T_seq, T_par, C)

    # Résidus
    residus = temps_exp - temps_theo

    # R² (coefficient de détermination)
    ss_res = np.sum(residus**2)
    ss_tot = np.sum((temps_exp - np.mean(temps_exp))**2)
    r2 = 1 - (ss_res / ss_tot)

    # Erreur moyenne absolue (MAE)
    mae = np.mean(np.abs(residus))

    # Erreur moyenne relative (MAPE)
    mape = np.mean(np.abs(residus / temps_exp)) * 100

    # Erreur quadratique moyenne (RMSE)
    rmse = np.sqrt(np.mean(residus**2))

    return {
        'r2': r2,
        'mae': mae,
        'mape': mape,
        'rmse': rmse,
        'temps_theo': temps_theo,
        'residus': residus
    }


def decomposition_temps(T_seq, T_par, verbose=True):
    """
    Décompose le temps séquentiel en composantes.

    Structure du Makefile:
    1. compile (compilation)
    2. split (découpage)
    3. 20 tâches parallèles
    4. merge (fusion)

    Hypothèses de répartition basées sur la structure typique:
    - compile: ~40% du temps séquentiel
    - split: ~30% du temps séquentiel
    - merge: ~30% du temps séquentiel
    """

    # Répartition estimée du temps séquentiel
    T_compile = T_seq * 0.40
    T_split = T_seq * 0.30
    T_merge = T_seq * 0.30

    # Temps par tâche parallèle (20 tâches)
    T_task = T_par / 20

    if verbose:
        print("\n" + "-"*70)
        print("DÉCOMPOSITION DU TEMPS")
        print("-"*70)
        print(f"\nTemps séquentiel (T_seq = {T_seq:.2f}s):")
        print(f"  • Compilation : {T_compile:.2f}s (~40%)")
        print(f"  • Split       : {T_split:.2f}s (~30%)")
        print(f"  • Merge       : {T_merge:.2f}s (~30%)")
        print(f"\nTemps parallèle (T_par = {T_par:.2f}s):")
        print(f"  • 20 tâches × {T_task:.2f}s/tâche")

    return {
        'T_compile': T_compile,
        'T_split': T_split,
        'T_merge': T_merge,
        'T_task': T_task
    }


# =============================================================================
# GÉNÉRATION DES GRAPHIQUES
# =============================================================================

def generer_graphiques(workers, temps_exp, params, metriques, output_prefix="amdahl"):
    """Génère les 4 graphiques de qualité publication."""

    T_seq, T_par, C = params
    temps_theo = metriques['temps_theo']

    # Données pour les courbes lisses
    N_smooth = np.linspace(1, 20, 200)
    temps_smooth = amdahl_model(N_smooth, T_seq, T_par, C)

    # Calculs pour speedup et efficacité
    speedup_exp = T1 / temps_exp
    speedup_theo = T1 / temps_theo
    speedup_smooth = T1 / temps_smooth

    efficacite_exp = speedup_exp / workers
    efficacite_theo = speedup_theo / workers
    efficacite_smooth = speedup_smooth / N_smooth

    # Configuration globale des graphiques
    plt.rcParams.update({
        'font.size': 11,
        'axes.labelsize': 12,
        'axes.titlesize': 13,
        'legend.fontsize': 10,
        'xtick.labelsize': 10,
        'ytick.labelsize': 10,
        'figure.dpi': 100,
        'savefig.dpi': 300,
        'figure.figsize': (10, 8),
        'axes.grid': True,
        'grid.alpha': 0.3
    })

    # Figure avec 4 sous-graphiques
    fig, axes = plt.subplots(2, 2, figsize=(14, 11))
    fig.suptitle('Analyse de la Loi d\'Amdahl - GNU Make Distribué\n'
                 f'Modèle: T(N) = {T_seq:.1f} + {T_par:.1f}/N + {C:.2f}×√N',
                 fontsize=14, fontweight='bold')

    # =========================================================================
    # Graphique 1: Temps d'exécution
    # =========================================================================
    ax1 = axes[0, 0]
    ax1.scatter(workers, temps_exp, s=80, c='#e74c3c', marker='o',
                label='Expérimental', zorder=5, edgecolors='darkred', linewidths=1)
    ax1.plot(N_smooth, temps_smooth, 'b-', linewidth=2.5,
             label=f'Théorique (R² = {metriques["r2"]:.4f})')
    ax1.set_xlabel('Nombre de Workers (N)')
    ax1.set_ylabel('Temps d\'exécution (s)')
    ax1.set_title('Temps d\'exécution vs Nombre de Workers')
    ax1.legend(loc='upper right')
    ax1.set_xlim(0, 21)
    ax1.set_ylim(0, 280)
    ax1.axhline(y=T_seq, color='green', linestyle='--', alpha=0.7,
                label=f'T_seq = {T_seq:.1f}s')
    ax1.legend(loc='upper right')

    # =========================================================================
    # Graphique 2: Speedup (Accélération)
    # =========================================================================
    ax2 = axes[0, 1]
    ax2.scatter(workers, speedup_exp, s=80, c='#e74c3c', marker='o',
                label='Expérimental', zorder=5, edgecolors='darkred', linewidths=1)
    ax2.plot(N_smooth, speedup_smooth, 'b-', linewidth=2.5, label='Théorique')
    ax2.plot(N_smooth, N_smooth, 'g--', linewidth=1.5, alpha=0.7, label='Idéal (S=N)')
    ax2.set_xlabel('Nombre de Workers (N)')
    ax2.set_ylabel('Speedup S(N) = T(1)/T(N)')
    ax2.set_title('Accélération (Speedup)')
    ax2.legend(loc='upper left')
    ax2.set_xlim(0, 21)
    ax2.set_ylim(0, 15)

    # =========================================================================
    # Graphique 3: Efficacité
    # =========================================================================
    ax3 = axes[1, 0]
    ax3.scatter(workers, efficacite_exp * 100, s=80, c='#e74c3c', marker='o',
                label='Expérimental', zorder=5, edgecolors='darkred', linewidths=1)
    ax3.plot(N_smooth, efficacite_smooth * 100, 'b-', linewidth=2.5, label='Théorique')
    ax3.axhline(y=100, color='green', linestyle='--', alpha=0.7, label='Idéal (100%)')
    ax3.axhline(y=50, color='orange', linestyle=':', alpha=0.7, label='Seuil 50%')
    ax3.set_xlabel('Nombre de Workers (N)')
    ax3.set_ylabel('Efficacité E(N) = S(N)/N (%)')
    ax3.set_title('Efficacité Parallèle')
    ax3.legend(loc='upper right')
    ax3.set_xlim(0, 21)
    ax3.set_ylim(0, 110)

    # =========================================================================
    # Graphique 4: Décomposition du temps
    # =========================================================================
    ax4 = axes[1, 1]

    # Composantes du temps pour chaque N
    temps_seq_arr = np.full_like(N_smooth, T_seq)
    temps_par_arr = T_par / N_smooth
    temps_overhead_arr = C * np.sqrt(N_smooth)

    ax4.fill_between(N_smooth, 0, temps_seq_arr, alpha=0.7,
                     label=f'Séquentiel (T_seq={T_seq:.1f}s)', color='#3498db')
    ax4.fill_between(N_smooth, temps_seq_arr, temps_seq_arr + temps_par_arr,
                     alpha=0.7, label=f'Parallèle (T_par={T_par:.1f}s)', color='#2ecc71')
    ax4.fill_between(N_smooth, temps_seq_arr + temps_par_arr,
                     temps_seq_arr + temps_par_arr + temps_overhead_arr,
                     alpha=0.7, label=f'Overhead (C={C:.2f}s)', color='#e74c3c')

    ax4.scatter(workers, temps_exp, s=60, c='black', marker='x',
                label='Expérimental', zorder=5, linewidths=2)
    ax4.set_xlabel('Nombre de Workers (N)')
    ax4.set_ylabel('Temps (s)')
    ax4.set_title('Décomposition du Temps par Composante')
    ax4.legend(loc='upper right')
    ax4.set_xlim(0, 21)
    ax4.set_ylim(0, 280)

    plt.tight_layout(rect=[0, 0.03, 1, 0.95])

    # Sauvegarde
    filename = f"{output_prefix}_analysis.png"
    plt.savefig(filename, dpi=300, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    print(f"\n✓ Graphiques sauvegardés: {filename}")

    plt.show()

    return fig


# =============================================================================
# TABLEAU COMPARATIF
# =============================================================================

def afficher_tableau_comparatif(workers, temps_exp, params, metriques):
    """Affiche un tableau comparatif théorie vs expérimental."""

    T_seq, T_par, C = params
    temps_theo = metriques['temps_theo']
    residus = metriques['residus']

    # Calculs
    speedup_exp = T1 / temps_exp
    speedup_theo = T1 / temps_theo
    efficacite_exp = (speedup_exp / workers) * 100
    efficacite_theo = (speedup_theo / workers) * 100
    erreur_rel = (residus / temps_exp) * 100

    print("\n" + "="*100)
    print("TABLEAU COMPARATIF: THÉORIE vs EXPÉRIMENTAL")
    print("="*100)

    header = (f"{'N':>3} | {'T_exp(s)':>10} | {'T_theo(s)':>10} | {'Erreur':>8} | "
              f"{'S_exp':>7} | {'S_theo':>7} | {'E_exp(%)':>8} | {'E_theo(%)':>8}")
    print(header)
    print("-"*100)

    for i, N in enumerate(workers):
        print(f"{N:>3} | {temps_exp[i]:>10.2f} | {temps_theo[i]:>10.2f} | "
              f"{erreur_rel[i]:>+7.1f}% | {speedup_exp[i]:>7.2f} | {speedup_theo[i]:>7.2f} | "
              f"{efficacite_exp[i]:>8.1f} | {efficacite_theo[i]:>8.1f}")

    print("-"*100)
    print(f"{'MOY':>3} | {np.mean(temps_exp):>10.2f} | {np.mean(temps_theo):>10.2f} | "
          f"{np.mean(np.abs(erreur_rel)):>+7.1f}% | {np.mean(speedup_exp):>7.2f} | "
          f"{np.mean(speedup_theo):>7.2f} | {np.mean(efficacite_exp):>8.1f} | "
          f"{np.mean(efficacite_theo):>8.1f}")
    print("="*100)


# =============================================================================
# EXPORT LATEX
# =============================================================================

def exporter_latex(workers, temps_exp, params, metriques, decomp, filename="amdahl_results.tex"):
    """Exporte tous les résultats en format LaTeX."""

    T_seq, T_par, C = params
    temps_theo = metriques['temps_theo']
    residus = metriques['residus']

    speedup_exp = T1 / temps_exp
    speedup_theo = T1 / temps_theo
    efficacite_exp = (speedup_exp / workers) * 100
    erreur_rel = (residus / temps_exp) * 100

    latex_content = r"""% =============================================================================
% ANALYSE DE LA LOI D'AMDAHL - GNU MAKE DISTRIBUÉ
% Projet Grenoble INP - Ensimag
% Généré automatiquement par amdahl_analysis.py
% =============================================================================

\documentclass[11pt,a4paper]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage[french]{babel}
\usepackage{amsmath,amssymb}
\usepackage{booktabs}
\usepackage{graphicx}
\usepackage{siunitx}
\usepackage{xcolor}

\begin{document}

% -----------------------------------------------------------------------------
% FORMULE CALIBRÉE
% -----------------------------------------------------------------------------
\section{Modèle Théorique Calibré}

Le modèle d'Amdahl modifié avec overhead de coordination:

\begin{equation}
\boxed{T(N) = T_{\text{seq}} + \frac{T_{\text{par}}}{N} + C \cdot \sqrt{N}}
\end{equation}

Avec les paramètres calibrés:

\begin{equation}
\boxed{T(N) = """ + f"{T_seq:.2f}" + r""" + \frac{""" + f"{T_par:.2f}" + r"""}{N} + """ + f"{C:.2f}" + r""" \cdot \sqrt{N}}
\end{equation}

\begin{table}[h]
\centering
\caption{Paramètres du modèle calibré}
\begin{tabular}{lrl}
\toprule
\textbf{Paramètre} & \textbf{Valeur} & \textbf{Description} \\
\midrule
$T_{\text{seq}}$ & """ + f"{T_seq:.2f}" + r""" s & Temps séquentiel incompressible \\
$T_{\text{par}}$ & """ + f"{T_par:.2f}" + r""" s & Temps total parallélisable \\
$C$ & """ + f"{C:.2f}" + r""" s & Coefficient d'overhead \\
\bottomrule
\end{tabular}
\end{table}

% -----------------------------------------------------------------------------
% MÉTRIQUES DE QUALITÉ
% -----------------------------------------------------------------------------
\section{Qualité du Modèle}

\begin{table}[h]
\centering
\caption{Métriques de qualité de l'ajustement}
\begin{tabular}{lr}
\toprule
\textbf{Métrique} & \textbf{Valeur} \\
\midrule
Coefficient de détermination ($R^2$) & """ + f"{metriques['r2']:.4f}" + r""" \\
Erreur moyenne absolue (MAE) & """ + f"{metriques['mae']:.2f}" + r""" s \\
Erreur moyenne relative (MAPE) & """ + f"{metriques['mape']:.2f}" + r""" \% \\
Erreur quadratique moyenne (RMSE) & """ + f"{metriques['rmse']:.2f}" + r""" s \\
\bottomrule
\end{tabular}
\end{table}

% -----------------------------------------------------------------------------
% DÉCOMPOSITION DU TEMPS
% -----------------------------------------------------------------------------
\section{Décomposition du Temps}

\begin{table}[h]
\centering
\caption{Décomposition du temps d'exécution}
\begin{tabular}{lrr}
\toprule
\textbf{Composante} & \textbf{Temps (s)} & \textbf{Proportion} \\
\midrule
Compilation & """ + f"{decomp['T_compile']:.2f}" + r""" & 40\% de $T_{\text{seq}}$ \\
Split (découpage) & """ + f"{decomp['T_split']:.2f}" + r""" & 30\% de $T_{\text{seq}}$ \\
Merge (fusion) & """ + f"{decomp['T_merge']:.2f}" + r""" & 30\% de $T_{\text{seq}}$ \\
\midrule
\textbf{Total séquentiel} & \textbf{""" + f"{T_seq:.2f}" + r"""} & \\
\midrule
20 tâches parallèles & """ + f"{T_par:.2f}" + r""" & """ + f"{decomp['T_task']:.2f}" + r""" s/tâche \\
\bottomrule
\end{tabular}
\end{table}

% -----------------------------------------------------------------------------
% TABLEAU COMPARATIF COMPLET
% -----------------------------------------------------------------------------
\section{Résultats Détaillés}

\begin{table}[h]
\centering
\caption{Comparaison théorie vs expérimental}
\sisetup{round-mode=places, round-precision=2}
\begin{tabular}{r S[round-precision=2] S[round-precision=2] S[round-precision=1] S[round-precision=2] S[round-precision=1]}
\toprule
{$N$} & {$T_{\exp}$ (s)} & {$T_{\text{théo}}$ (s)} & {Erreur (\%)} & {Speedup} & {Eff. (\%)} \\
\midrule
"""

    # Ajout des lignes de données
    for i, N in enumerate(workers):
        latex_content += f"{N} & {temps_exp[i]:.2f} & {temps_theo[i]:.2f} & {erreur_rel[i]:+.1f} & {speedup_exp[i]:.2f} & {efficacite_exp[i]:.1f} \\\\\n"

    latex_content += r"""\bottomrule
\end{tabular}
\end{table}

% -----------------------------------------------------------------------------
% ANALYSE
% -----------------------------------------------------------------------------
\section{Analyse}

\begin{itemize}
    \item \textbf{Fraction séquentielle:} $f = T_{\text{seq}} / T(1) = """ + f"{T_seq/T1*100:.1f}" + r"""\%$
    \item \textbf{Fraction parallèle:} $1-f = """ + f"{(1-T_seq/T1)*100:.1f}" + r"""\%$
    \item \textbf{Speedup maximum théorique:} $S_{\max} = 1/f = """ + f"{T1/T_seq:.2f}" + r"""$
    \item \textbf{Speedup observé à N=20:} $S_{20} = """ + f"{speedup_exp[-1]:.2f}" + r"""$
    \item \textbf{Efficacité moyenne:} """ + f"{np.mean(efficacite_exp):.1f}" + r"""\%
\end{itemize}

% Figure
\begin{figure}[h]
\centering
\includegraphics[width=\textwidth]{amdahl_analysis.png}
\caption{Analyse complète de la loi d'Amdahl}
\end{figure}

\end{document}
"""

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(latex_content)

    print(f"✓ Export LaTeX sauvegardé: {filename}")

    return latex_content


# =============================================================================
# AFFICHAGE DE LA FORMULE FINALE
# =============================================================================

def afficher_formule_finale(params, metriques):
    """Affiche la formule finale calibrée."""

    T_seq, T_par, C = params

    print("\n" + "="*70)
    print("FORMULE FINALE CALIBRÉE")
    print("="*70)

    print(f"""
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│   T(N) = T_seq + T_par/N + C×√N                                     │
│                                                                     │
│   T(N) = {T_seq:.2f} + {T_par:.2f}/N + {C:.2f}×√N                           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

Qualité de l'ajustement:
  • R²   = {metriques['r2']:.4f} ({metriques['r2']*100:.2f}% de variance expliquée)
  • MAE  = {metriques['mae']:.2f} s (erreur moyenne absolue)
  • MAPE = {metriques['mape']:.2f}% (erreur moyenne relative)
  • RMSE = {metriques['rmse']:.2f} s (erreur quadratique moyenne)

Interprétation:
  • Temps séquentiel: {T_seq:.2f}s ({T_seq/T1*100:.1f}% du temps total à N=1)
  • Temps parallèle:  {T_par:.2f}s ({T_par/T1*100:.1f}% du temps total à N=1)
  • Overhead:         {C:.2f}×√N secondes

Speedup théorique maximal (loi d'Amdahl classique):
  • S_max = 1/f = T(1)/T_seq = {T1/T_seq:.2f}
""")


# =============================================================================
# PROGRAMME PRINCIPAL
# =============================================================================

def main():
    """Fonction principale d'analyse."""

    print("\n" + "#"*70)
    print("#" + " "*68 + "#")
    print("#" + "  ANALYSE DE LA LOI D'AMDAHL - GNU MAKE DISTRIBUÉ  ".center(68) + "#")
    print("#" + "  Projet Grenoble INP - Ensimag  ".center(68) + "#")
    print("#" + " "*68 + "#")
    print("#"*70)

    print(f"\nDonnées: {len(workers)} points expérimentaux")
    print(f"Temps de référence T(1) = {T1:.2f}s")

    # 1. Calibration du modèle
    params, pcov = calibrer_modele(workers, temps_experimental)

    if params is None:
        print("Erreur: Impossible de calibrer le modèle.")
        return

    T_seq, T_par, C = params

    # 2. Calcul des métriques
    metriques = calculer_metriques(workers, temps_experimental, params)

    # 3. Décomposition du temps
    decomp = decomposition_temps(T_seq, T_par)

    # 4. Affichage de la formule finale
    afficher_formule_finale(params, metriques)

    # 5. Tableau comparatif
    afficher_tableau_comparatif(workers, temps_experimental, params, metriques)

    # 6. Génération des graphiques
    print("\n" + "-"*70)
    print("GÉNÉRATION DES GRAPHIQUES")
    print("-"*70)
    generer_graphiques(workers, temps_experimental, params, metriques)

    # 7. Export LaTeX
    print("\n" + "-"*70)
    print("EXPORT LATEX")
    print("-"*70)
    exporter_latex(workers, temps_experimental, params, metriques, decomp)

    print("\n" + "="*70)
    print("ANALYSE TERMINÉE AVEC SUCCÈS")
    print("="*70)
    print("\nFichiers générés:")
    print("  • amdahl_analysis.png  (graphiques 300 DPI)")
    print("  • amdahl_results.tex   (export LaTeX complet)")
    print("")


if __name__ == "__main__":
    main()
