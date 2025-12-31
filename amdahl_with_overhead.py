#!/usr/bin/env python3
"""
Analyse avec overhead réel mesuré depuis le launcher CSV
"""

import numpy as np
from scipy.optimize import curve_fit

# Données expérimentales
workers = np.array([1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20])
temps_exp = np.array([262.39,136.15,91.18,85.59,65.02,55.11,48.79,43.23,40.19,31.60,
                      31.55,33.60,30.13,29.10,27.71,27.63,27.04,25.82,20.06,24.93])

# =============================================================================
# OVERHEAD MESURÉ (depuis launcher CSV)
# =============================================================================
# Régression sur les données launcher: T_overhead = 1.046 + 0.507 × N
OVERHEAD_FIXE = 1.046      # Temps fixe (initialisation RMI, connexion)
OVERHEAD_PAR_WORKER = 0.507  # Temps par worker (sérialisation, communication)

def overhead_mesure(N):
    """Overhead mesuré expérimentalement"""
    return OVERHEAD_FIXE + OVERHEAD_PAR_WORKER * N

# =============================================================================
# MODÈLES
# =============================================================================

def model_avec_overhead_fixe(N, T_seq_pur, T_par):
    """
    Modèle avec overhead MESURÉ (pas calibré)
    T(N) = T_seq_pur + T_par/N + overhead(N)
    """
    return T_seq_pur + T_par/N + overhead_mesure(N)

def model_overhead_sqrt(N, T_seq, T_par, C):
    """Modèle classique avec C×√N"""
    return T_seq + T_par/N + C * np.sqrt(N)

def model_overhead_linear(N, T_seq, T_par, C):
    """Modèle avec overhead linéaire C×N"""
    return T_seq + T_par/N + C * N

# =============================================================================
# ANALYSE
# =============================================================================

print("\n" + "="*70)
print("  ANALYSE AVEC OVERHEAD RÉEL")
print("="*70)

# 1. Overhead mesuré
print("\n" + "-"*70)
print("1. OVERHEAD MESURÉ (depuis launcher CSV)")
print("-"*70)
print(f"""
  Formule mesurée: T_overhead(N) = {OVERHEAD_FIXE:.3f} + {OVERHEAD_PAR_WORKER:.3f} × N

  Exemples:
    • N=1:  overhead = {overhead_mesure(1):.2f}s
    • N=5:  overhead = {overhead_mesure(5):.2f}s
    • N=10: overhead = {overhead_mesure(10):.2f}s
    • N=20: overhead = {overhead_mesure(20):.2f}s
""")

# 2. Calibration avec overhead fixé
print("-"*70)
print("2. CALIBRATION AVEC OVERHEAD FIXÉ")
print("-"*70)

popt1, _ = curve_fit(model_avec_overhead_fixe, workers, temps_exp,
                     p0=[5, 240], bounds=([0,0], [np.inf, np.inf]))
T_seq_pur, T_par = popt1

temps_theo1 = model_avec_overhead_fixe(workers, T_seq_pur, T_par)
r2_1 = 1 - np.sum((temps_exp - temps_theo1)**2) / np.sum((temps_exp - np.mean(temps_exp))**2)

print(f"""
  Modèle: T(N) = T_seq_pur + T_par/N + overhead(N)

  Où: overhead(N) = {OVERHEAD_FIXE:.3f} + {OVERHEAD_PAR_WORKER:.3f} × N  (MESURÉ)

  Paramètres calibrés:
    • T_seq_pur = {T_seq_pur:.2f}s  (temps séquentiel SANS overhead)
    • T_par     = {T_par:.2f}s

  R² = {r2_1:.4f}
""")

# 3. Comparaison avec overhead linéaire calibré
print("-"*70)
print("3. CALIBRATION OVERHEAD LINÉAIRE")
print("-"*70)

popt2, _ = curve_fit(model_overhead_linear, workers, temps_exp,
                     p0=[5, 240, 0.5], bounds=([0,0,0], [np.inf, np.inf, np.inf]))
T_seq2, T_par2, C_lin = popt2

temps_theo2 = model_overhead_linear(workers, T_seq2, T_par2, C_lin)
r2_2 = 1 - np.sum((temps_exp - temps_theo2)**2) / np.sum((temps_exp - np.mean(temps_exp))**2)

print(f"""
  Modèle: T(N) = T_seq + T_par/N + C × N

  Paramètres calibrés:
    • T_seq = {T_seq2:.2f}s
    • T_par = {T_par2:.2f}s
    • C     = {C_lin:.4f}s/worker

  R² = {r2_2:.4f}

  Comparaison avec overhead mesuré:
    • C mesuré    = {OVERHEAD_PAR_WORKER:.3f}s/worker
    • C calibré   = {C_lin:.4f}s/worker
    • Différence  = {abs(OVERHEAD_PAR_WORKER - C_lin):.4f}s
""")

# 4. Formule finale
print("-"*70)
print("4. FORMULE FINALE AVEC OVERHEAD")
print("-"*70)

# Utiliser l'overhead mesuré + T_seq calibré
T_seq_total = T_seq_pur + OVERHEAD_FIXE  # T_seq effectif

print(f"""
  ┌─────────────────────────────────────────────────────────────────┐
  │                                                                 │
  │   T(N) = T_seq + T_par/N + C×N                                  │
  │                                                                 │
  │   T(N) = {T_seq_pur:.2f} + {T_par:.2f}/N + {OVERHEAD_PAR_WORKER:.3f}×N + {OVERHEAD_FIXE:.2f}    │
  │                                                                 │
  │   Simplifié:                                                    │
  │   T(N) = {T_seq_pur + OVERHEAD_FIXE:.2f} + {T_par:.2f}/N + {OVERHEAD_PAR_WORKER:.3f}×N                  │
  │                                                                 │
  └─────────────────────────────────────────────────────────────────┘

  Décomposition:
    • T_seq_pur     = {T_seq_pur:.2f}s  (séquentiel pur: compile+split+merge)
    • Overhead fixe = {OVERHEAD_FIXE:.2f}s  (initialisation RMI)
    • T_par         = {T_par:.2f}s  (20 tâches parallèles)
    • C             = {OVERHEAD_PAR_WORKER:.3f}s/worker  (overhead par worker)

  Vérification:
    • T(1)  = {T_seq_pur:.2f} + {T_par:.2f}/1 + {OVERHEAD_PAR_WORKER:.3f}×1 + {OVERHEAD_FIXE:.2f} = {model_avec_overhead_fixe(1, T_seq_pur, T_par):.2f}s  (exp: 262.39s)
    • T(10) = {T_seq_pur:.2f} + {T_par:.2f}/10 + {OVERHEAD_PAR_WORKER:.3f}×10 + {OVERHEAD_FIXE:.2f} = {model_avec_overhead_fixe(10, T_seq_pur, T_par):.2f}s  (exp: 31.60s)
    • T(20) = {T_seq_pur:.2f} + {T_par:.2f}/20 + {OVERHEAD_PAR_WORKER:.3f}×20 + {OVERHEAD_FIXE:.2f} = {model_avec_overhead_fixe(20, T_seq_pur, T_par):.2f}s  (exp: 24.93s)
""")

# 5. Tableau
print("-"*70)
print("5. TABLEAU AVEC DÉCOMPOSITION")
print("-"*70)
print("\n   N | T_exp | T_theo | T_seq | T_par/N | Overhead | Erreur")
print("  ---|-------|--------|-------|---------|----------|-------")
for i, N in enumerate(workers):
    t_theo = model_avec_overhead_fixe(N, T_seq_pur, T_par)
    t_seq = T_seq_pur
    t_par_n = T_par / N
    t_overhead = overhead_mesure(N)
    err = (temps_exp[i] - t_theo) / temps_exp[i] * 100
    print(f"  {N:>2} | {temps_exp[i]:>5.1f} | {t_theo:>6.1f} | {t_seq:>5.1f} | {t_par_n:>7.1f} | {t_overhead:>8.1f} | {err:>+5.1f}%")

print("\n" + "="*70)
print("  CONCLUSION")
print("="*70)
print(f"""
  L'overhead N'EST PAS négligeable !

  À N=20 workers:
    • T_seq_pur  = {T_seq_pur:.2f}s ({T_seq_pur/model_avec_overhead_fixe(20, T_seq_pur, T_par)*100:.1f}%)
    • T_par/N    = {T_par/20:.2f}s ({T_par/20/model_avec_overhead_fixe(20, T_seq_pur, T_par)*100:.1f}%)
    • Overhead   = {overhead_mesure(20):.2f}s ({overhead_mesure(20)/model_avec_overhead_fixe(20, T_seq_pur, T_par)*100:.1f}%)
                   ─────────
    • Total      = {model_avec_overhead_fixe(20, T_seq_pur, T_par):.2f}s

  L'overhead représente {overhead_mesure(20)/model_avec_overhead_fixe(20, T_seq_pur, T_par)*100:.1f}% du temps total à N=20!
""")
