#!/usr/bin/env python3
"""
Modele Theorique de Performance - Wordcount Distribue
======================================================

Ce module implemente le modele theorique pour predire les performances
du systeme de wordcount distribue sur Grid'5000.

Fondements Academiques:
-----------------------
1. Theoreme de Graham (1969) - Borne de scheduling
   T <= Sigma(T_i) / m + T_max

2. Modele LogP (Culler et al., 1993)
   - L: Latence reseau
   - o: Overhead CPU
   - g: Gap entre messages
   - P: Nombre de processeurs

3. Modele BSP (Valiant, 1990)
   - Super-etapes: calcul + communication + synchronisation

References:
-----------
- Graham, R.L. (1969). Bounds on Multiprocessing Timing Anomalies.
  SIAM Journal on Applied Mathematics, 17(2), 416-429.
- Culler, D. et al. (1993). LogP: Towards a Realistic Model.
  ACM SIGPLAN Notices, 28(7), 1-12.
- Valiant, L.G. (1990). A Bridging Model for Parallel Computation.
  Communications of the ACM, 33(8), 103-111.

Usage:
------
    python theoretical_model.py --calibrate data.csv
    python theoretical_model.py --predict --workers 64 --size 1000
    python theoretical_model.py --validate measured.csv
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from dataclasses import dataclass, field
from typing import Literal, Optional, Dict, List
from pathlib import Path
import json
import argparse

# ============================================================================
#                           PARAMETRES DU MODELE
# ============================================================================

@dataclass
class ModelParameters:
    """
    Parametres du modele theorique.

    Ces parametres doivent etre calibres a partir de mesures reelles
    sur Grid'5000 avant d'etre utilises pour des predictions.

    Unites:
    - Temps: secondes
    - Taille: MB
    - Bande passante: MB/s
    """

    # --- Initialisation du cluster ---
    init_fixed_overhead: float = 1.5    # Overhead fixe (demarrage master)
    init_per_worker: float = 0.5        # Temps par worker (SSH + JVM + RMI)

    # --- Decoupage fichier ---
    disk_bandwidth: float = 500.0       # Bande passante disque (MB/s)

    # --- Distribution (SCP) ---
    scp_latency: float = 0.300          # Latence SCP (secondes)
    scp_bandwidth: float = 400.0        # Debit SCP (MB/s)

    # --- Distribution (NFS) ---
    nfs_latency: float = 0.004          # Latence NFS (secondes)
    nfs_bandwidth: float = 5000.0       # Debit NFS (MB/s)

    # --- Calcul ---
    wordcount_speed: float = 1_000_000  # Vitesse traitement (mots/seconde)
    words_per_mb: float = 100_000       # Densite de mots (~10 mots/ligne, 10K lignes/MB)
    scheduling_overhead: float = 0.5    # Overhead ordonnancement par batch

    # --- RMI ---
    rmi_lookup_time: float = 0.100      # Temps Naming.lookup() (secondes)
    rmi_call_overhead: float = 0.010    # Overhead appel distant (secondes)

    # --- Agregation ---
    aggregation_time: float = 0.050     # Temps fusion finale (secondes)

    def to_dict(self) -> Dict:
        """Convertir en dictionnaire pour serialisation."""
        return {
            'init_fixed_overhead': self.init_fixed_overhead,
            'init_per_worker': self.init_per_worker,
            'disk_bandwidth': self.disk_bandwidth,
            'scp_latency': self.scp_latency,
            'scp_bandwidth': self.scp_bandwidth,
            'nfs_latency': self.nfs_latency,
            'nfs_bandwidth': self.nfs_bandwidth,
            'wordcount_speed': self.wordcount_speed,
            'words_per_mb': self.words_per_mb,
            'scheduling_overhead': self.scheduling_overhead,
            'rmi_lookup_time': self.rmi_lookup_time,
            'rmi_call_overhead': self.rmi_call_overhead,
            'aggregation_time': self.aggregation_time
        }

    @classmethod
    def from_dict(cls, d: Dict) -> 'ModelParameters':
        """Creer depuis un dictionnaire."""
        return cls(**d)

    def save(self, filepath: str):
        """Sauvegarder les parametres en JSON."""
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, filepath: str) -> 'ModelParameters':
        """Charger les parametres depuis un fichier JSON."""
        with open(filepath, 'r') as f:
            return cls.from_dict(json.load(f))


# ============================================================================
#                           MODELE THEORIQUE
# ============================================================================

class TheoreticalModel:
    """
    Modele theorique de performance pour le wordcount distribue.

    Le temps total est decompose en 5 phases:

    T_total = T_init + T_split + T_dist + T_calc + T_agg

    Chaque phase est modelisee selon des fondements theoriques etablis.
    """

    def __init__(self, params: Optional[ModelParameters] = None):
        """
        Initialiser le modele.

        Args:
            params: Parametres du modele. Si None, utilise les valeurs par defaut.
        """
        self.params = params or ModelParameters()

    # -------------------------------------------------------------------------
    #                           COMPOSANTES TEMPORELLES
    # -------------------------------------------------------------------------

    def T_init(self, n_workers: int) -> float:
        """
        Temps d'initialisation du cluster.

        Modele: T_init = alpha * n + beta

        Fondement theorique:
        - Chaque worker necessite une connexion SSH
        - Demarrage d'une JVM (~200-500ms)
        - Creation du registry RMI (~100ms)
        - Latence reseau Grid'5000 (~50-100ms)

        Args:
            n_workers: Nombre de workers a demarrer

        Returns:
            Temps d'initialisation en secondes
        """
        return self.params.init_fixed_overhead + self.params.init_per_worker * n_workers

    def T_split(self, file_size_mb: float) -> float:
        """
        Temps de decoupage du fichier d'entree.

        Modele: T_split = S / BW_disk

        Fondement theorique:
        - Operation I/O bound
        - Lineaire avec la taille du fichier
        - Limitee par la bande passante disque

        Args:
            file_size_mb: Taille du fichier en MB

        Returns:
            Temps de decoupage en secondes
        """
        return file_size_mb / self.params.disk_bandwidth

    def T_dist(self, file_size_mb: float, n_workers: int,
               mode: Literal["SCP", "NFS"] = "NFS") -> float:
        """
        Temps de distribution des partitions aux workers.

        Modele SCP (sequentiel):
            T_dist = n * (L_scp + (S/n) / BW_scp)
                   = n * L_scp + S / BW_scp

        Modele NFS:
            T_dist ≈ L_nfs (acces direct, negligeable)

        Fondement theorique (LogP):
        - L: Latence de base pour etablir la connexion
        - Temps de transfert: taille / bande passante
        - Pour SCP: overhead de chiffrement (~10-20%)

        Args:
            file_size_mb: Taille totale du fichier
            n_workers: Nombre de workers
            mode: Mode de transfert ("SCP" ou "NFS")

        Returns:
            Temps de distribution en secondes
        """
        if mode.upper() == "SCP":
            partition_size = file_size_mb / n_workers
            return n_workers * (self.params.scp_latency +
                               partition_size / self.params.scp_bandwidth)
        else:  # NFS
            return self.params.nfs_latency

    def T_calc(self, file_size_mb: float, n_workers: int) -> float:
        """
        Temps de calcul parallele.

        Modele (Graham + RMI):
            T_calc = T_wordcount + T_rmi + T_scheduling

        Ou:
            T_wordcount = (S * mots/MB) / (n * vitesse)
            T_rmi = n * (T_lookup + T_call)
            T_scheduling = overhead constant

        Fondement theorique:
        - Borne de Graham: T <= Sigma(T_i)/m + T_max
        - Partitions equilibrees => T ≈ T_moyen
        - Overhead RMI pour chaque appel distant

        Args:
            file_size_mb: Taille du fichier
            n_workers: Nombre de workers

        Returns:
            Temps de calcul en secondes
        """
        # Estimation du nombre de mots
        total_words = file_size_mb * self.params.words_per_mb
        words_per_worker = total_words / n_workers

        # Temps de traitement par worker
        T_wordcount = words_per_worker / self.params.wordcount_speed

        # Overhead RMI (un appel par worker)
        T_rmi = n_workers * (self.params.rmi_lookup_time +
                            self.params.rmi_call_overhead)

        return T_wordcount + T_rmi + self.params.scheduling_overhead

    def T_agg(self) -> float:
        """
        Temps d'agregation finale des resultats.

        Modele: T_agg = constante

        Fondement theorique:
        - Operation locale sur le master
        - Fusion des resultats partiels (cat | awk)
        - Independant du nombre de workers

        Returns:
            Temps d'agregation en secondes
        """
        return self.params.aggregation_time

    # -------------------------------------------------------------------------
    #                           PREDICTIONS
    # -------------------------------------------------------------------------

    def T_total(self, file_size_mb: float, n_workers: int,
                mode: Literal["SCP", "NFS"] = "NFS") -> float:
        """
        Temps total predit par le modele.

        T_total = T_init + T_split + T_dist + T_calc + T_agg

        Args:
            file_size_mb: Taille du fichier en MB
            n_workers: Nombre de workers
            mode: Mode de transfert

        Returns:
            Temps total en secondes
        """
        return (self.T_init(n_workers) +
                self.T_split(file_size_mb) +
                self.T_dist(file_size_mb, n_workers, mode) +
                self.T_calc(file_size_mb, n_workers) +
                self.T_agg())

    def breakdown(self, file_size_mb: float, n_workers: int,
                  mode: Literal["SCP", "NFS"] = "NFS") -> Dict[str, float]:
        """
        Decomposition detaillee du temps par phase.

        Args:
            file_size_mb: Taille du fichier
            n_workers: Nombre de workers
            mode: Mode de transfert

        Returns:
            Dictionnaire avec le temps de chaque phase
        """
        return {
            'T_init': self.T_init(n_workers),
            'T_split': self.T_split(file_size_mb),
            'T_dist': self.T_dist(file_size_mb, n_workers, mode),
            'T_calc': self.T_calc(file_size_mb, n_workers),
            'T_agg': self.T_agg(),
            'T_total': self.T_total(file_size_mb, n_workers, mode)
        }

    # -------------------------------------------------------------------------
    #                           METRIQUES DE PERFORMANCE
    # -------------------------------------------------------------------------

    def speedup(self, file_size_mb: float, n_workers: int,
                mode: Literal["SCP", "NFS"] = "NFS") -> float:
        """
        Acceleration theorique.

        Speedup(n) = T(1) / T(n)

        Fondement: Loi d'Amdahl / Gustafson

        Args:
            file_size_mb: Taille du fichier
            n_workers: Nombre de workers
            mode: Mode de transfert

        Returns:
            Facteur d'acceleration
        """
        T_1 = self.T_total(file_size_mb, 1, mode)
        T_n = self.T_total(file_size_mb, n_workers, mode)
        return T_1 / T_n

    def efficiency(self, file_size_mb: float, n_workers: int,
                   mode: Literal["SCP", "NFS"] = "NFS") -> float:
        """
        Efficacite theorique.

        Efficiency(n) = Speedup(n) / n

        Interpretation:
        - E = 1: Parallelisme parfait
        - E < 1: Overhead de parallelisation
        - E > 1: Super-lineaire (effet de cache)

        Args:
            file_size_mb: Taille du fichier
            n_workers: Nombre de workers
            mode: Mode de transfert

        Returns:
            Efficacite (0 a 1)
        """
        return self.speedup(file_size_mb, n_workers, mode) / n_workers

    # -------------------------------------------------------------------------
    #                           ANALYSE DE SENSIBILITE
    # -------------------------------------------------------------------------

    def sensitivity_analysis(self, file_size_mb: float, n_workers: int,
                            mode: str = "NFS",
                            variation: float = 0.2) -> Dict[str, float]:
        """
        Analyse de sensibilite du modele.

        Mesure l'impact de chaque parametre sur le temps total.

        Args:
            file_size_mb: Taille du fichier
            n_workers: Nombre de workers
            mode: Mode de transfert
            variation: Variation relative des parametres (+/- 20% par defaut)

        Returns:
            Impact relatif de chaque parametre
        """
        base_time = self.T_total(file_size_mb, n_workers, mode)
        impacts = {}

        # Liste des parametres a tester
        param_names = [
            'init_fixed_overhead', 'init_per_worker',
            'scp_latency', 'scp_bandwidth',
            'wordcount_speed', 'rmi_lookup_time'
        ]

        for param in param_names:
            original_value = getattr(self.params, param)

            # Augmenter le parametre
            setattr(self.params, param, original_value * (1 + variation))
            time_increased = self.T_total(file_size_mb, n_workers, mode)

            # Restaurer
            setattr(self.params, param, original_value)

            # Impact relatif
            impacts[param] = (time_increased - base_time) / base_time

        return impacts


# ============================================================================
#                           CALIBRATION
# ============================================================================

def calibrate_model(measured_df: pd.DataFrame,
                    file_size_col: str = 'FileSize_MB',
                    workers_col: str = 'Workers',
                    mode_col: str = 'Mode',
                    time_col: str = 'T_total_ms') -> ModelParameters:
    """
    Calibrer les parametres du modele a partir de mesures reelles.

    Utilise une optimisation par moindres carres pour minimiser
    l'erreur entre predictions et mesures.

    Args:
        measured_df: DataFrame avec les mesures
        file_size_col: Nom de la colonne taille
        workers_col: Nom de la colonne workers
        mode_col: Nom de la colonne mode
        time_col: Nom de la colonne temps (en ms)

    Returns:
        Parametres calibres
    """
    from scipy.optimize import minimize

    def objective(params_vector):
        """Fonction objectif: minimiser l'erreur quadratique."""
        params = ModelParameters(
            init_fixed_overhead=params_vector[0],
            init_per_worker=params_vector[1],
            scp_latency=params_vector[2],
            scp_bandwidth=params_vector[3],
            wordcount_speed=params_vector[4],
            rmi_lookup_time=params_vector[5]
        )
        model = TheoreticalModel(params)

        total_error = 0
        for _, row in measured_df.iterrows():
            predicted = model.T_total(
                file_size_mb=row[file_size_col],
                n_workers=row[workers_col],
                mode=row[mode_col]
            ) * 1000  # Convertir en ms

            actual = row[time_col]
            total_error += (predicted - actual) ** 2

        return total_error

    # Valeurs initiales
    x0 = [1.5, 0.5, 0.3, 400, 1_000_000, 0.1]

    # Bornes des parametres
    bounds = [
        (0.1, 10),          # init_fixed_overhead
        (0.1, 2),           # init_per_worker
        (0.05, 1),          # scp_latency
        (100, 1000),        # scp_bandwidth
        (100_000, 10_000_000),  # wordcount_speed
        (0.01, 0.5)         # rmi_lookup_time
    ]

    result = minimize(objective, x0, bounds=bounds, method='L-BFGS-B')

    return ModelParameters(
        init_fixed_overhead=result.x[0],
        init_per_worker=result.x[1],
        scp_latency=result.x[2],
        scp_bandwidth=result.x[3],
        wordcount_speed=result.x[4],
        rmi_lookup_time=result.x[5]
    )


# ============================================================================
#                           VALIDATION
# ============================================================================

def validate_model(model: TheoreticalModel, measured_df: pd.DataFrame,
                   output_dir: str = '.') -> pd.DataFrame:
    """
    Valider le modele en comparant predictions vs mesures.

    Genere des graphiques et calcule les metriques d'erreur.

    Args:
        model: Modele a valider
        measured_df: DataFrame avec les mesures reelles
        output_dir: Repertoire de sortie pour les graphiques

    Returns:
        DataFrame avec predictions et erreurs
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    predictions = []
    for _, row in measured_df.iterrows():
        pred = model.T_total(
            file_size_mb=row['FileSize_MB'],
            n_workers=row['Workers'],
            mode=row['Mode']
        ) * 1000  # ms

        actual = row['T_total_ms']
        error = abs(pred - actual)
        error_pct = error / actual * 100

        predictions.append({
            'Workers': row['Workers'],
            'FileSize_MB': row['FileSize_MB'],
            'Mode': row['Mode'],
            'T_measured_ms': actual,
            'T_predicted_ms': pred,
            'Error_ms': error,
            'Error_pct': error_pct
        })

    pred_df = pd.DataFrame(predictions)

    # Statistiques d'erreur
    mape = pred_df['Error_pct'].mean()
    median_error = pred_df['Error_pct'].median()
    max_error = pred_df['Error_pct'].max()

    print("\n" + "="*60)
    print("VALIDATION DU MODELE")
    print("="*60)
    print(f"Mean Absolute Percentage Error (MAPE): {mape:.2f}%")
    print(f"Median Error: {median_error:.2f}%")
    print(f"Max Error: {max_error:.2f}%")
    print("="*60)

    # === Graphique 1: Predit vs Mesure ===
    fig, ax = plt.subplots(figsize=(8, 8))

    colors = {'SCP': 'blue', 'NFS': 'green'}
    for mode in pred_df['Mode'].unique():
        mode_data = pred_df[pred_df['Mode'] == mode]
        ax.scatter(
            mode_data['T_measured_ms'],
            mode_data['T_predicted_ms'],
            c=colors.get(mode, 'gray'),
            label=mode,
            alpha=0.7,
            s=50
        )

    # Ligne parfaite
    max_val = max(pred_df['T_measured_ms'].max(), pred_df['T_predicted_ms'].max())
    ax.plot([0, max_val], [0, max_val], 'k--', label='Prediction parfaite', alpha=0.5)

    ax.set_xlabel('Temps mesure (ms)', fontsize=12)
    ax.set_ylabel('Temps predit (ms)', fontsize=12)
    ax.set_title(f'Validation du modele\nMAPE = {mape:.1f}%', fontsize=14)
    ax.legend()
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path / 'model_validation.png', dpi=150, bbox_inches='tight')
    plt.close()

    # === Graphique 2: Erreur par configuration ===
    fig, ax = plt.subplots(figsize=(10, 6))

    # Grouper par workers
    grouped = pred_df.groupby(['Workers', 'Mode'])['Error_pct'].mean().unstack()
    grouped.plot(kind='bar', ax=ax, color=['blue', 'green'])

    ax.set_xlabel('Nombre de workers', fontsize=12)
    ax.set_ylabel('Erreur relative (%)', fontsize=12)
    ax.set_title('Erreur du modele par configuration', fontsize=14)
    ax.legend(title='Mode')
    ax.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    plt.savefig(output_path / 'model_error.png', dpi=150, bbox_inches='tight')
    plt.close()

    return pred_df


# ============================================================================
#                           VISUALISATION
# ============================================================================

def generate_prediction_plots(model: TheoreticalModel,
                              file_sizes: List[float] = [100, 1000, 10000],
                              max_workers: int = 64,
                              output_dir: str = '.'):
    """
    Generer les graphiques de prediction du modele.

    Args:
        model: Modele a utiliser
        file_sizes: Liste des tailles de fichiers (MB)
        max_workers: Nombre maximum de workers
        output_dir: Repertoire de sortie
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    workers = [2**i for i in range(int(np.log2(max_workers)) + 1)]
    workers = [w for w in workers if w <= max_workers]
    if 1 not in workers:
        workers = [1] + workers

    # === Graphique 1: Temps d'execution ===
    fig, axes = plt.subplots(1, len(file_sizes), figsize=(5*len(file_sizes), 5))
    if len(file_sizes) == 1:
        axes = [axes]

    for i, size in enumerate(file_sizes):
        ax = axes[i]
        for mode in ['NFS', 'SCP']:
            times = [model.T_total(size, n, mode) for n in workers]
            ax.plot(workers, times, 'o-', label=mode)

        ax.set_xlabel('Nombre de workers')
        ax.set_ylabel('Temps (s)')
        ax.set_title(f'Fichier {size} MB')
        ax.set_xscale('log', base=2)
        ax.legend()
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path / 'predicted_execution_time.png', dpi=150)
    plt.close()

    # === Graphique 2: Speedup ===
    fig, axes = plt.subplots(1, len(file_sizes), figsize=(5*len(file_sizes), 5))
    if len(file_sizes) == 1:
        axes = [axes]

    for i, size in enumerate(file_sizes):
        ax = axes[i]

        # Ligne ideale
        ax.plot(workers, workers, 'k--', label='Ideal', alpha=0.5)

        for mode in ['NFS', 'SCP']:
            speedups = [model.speedup(size, n, mode) for n in workers]
            ax.plot(workers, speedups, 'o-', label=mode)

        ax.set_xlabel('Nombre de workers')
        ax.set_ylabel('Speedup')
        ax.set_title(f'Fichier {size} MB')
        ax.set_xscale('log', base=2)
        ax.set_yscale('log', base=2)
        ax.legend()
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path / 'predicted_speedup.png', dpi=150)
    plt.close()

    # === Graphique 3: Efficacite ===
    fig, axes = plt.subplots(1, len(file_sizes), figsize=(5*len(file_sizes), 5))
    if len(file_sizes) == 1:
        axes = [axes]

    for i, size in enumerate(file_sizes):
        ax = axes[i]

        # Ligne ideale
        ax.axhline(y=1.0, color='k', linestyle='--', alpha=0.5, label='Ideal')

        for mode in ['NFS', 'SCP']:
            efficiencies = [model.efficiency(size, n, mode) for n in workers]
            ax.plot(workers, efficiencies, 'o-', label=mode)

        ax.set_xlabel('Nombre de workers')
        ax.set_ylabel('Efficacite')
        ax.set_title(f'Fichier {size} MB')
        ax.set_xscale('log', base=2)
        ax.set_ylim(0, 1.1)
        ax.legend()
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path / 'predicted_efficiency.png', dpi=150)
    plt.close()

    # === Graphique 4: Decomposition temporelle ===
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    size = file_sizes[len(file_sizes)//2]  # Taille moyenne

    for idx, mode in enumerate(['NFS', 'SCP']):
        ax = axes[idx]

        phases = ['T_init', 'T_split', 'T_dist', 'T_calc', 'T_agg']
        phase_data = {phase: [] for phase in phases}

        for n in workers:
            breakdown = model.breakdown(size, n, mode)
            for phase in phases:
                phase_data[phase].append(breakdown[phase])

        bottom = np.zeros(len(workers))
        colors = plt.cm.Set2(np.linspace(0, 1, len(phases)))

        for phase, color in zip(phases, colors):
            ax.bar(range(len(workers)), phase_data[phase],
                   bottom=bottom, label=phase.replace('T_', ''), color=color)
            bottom += np.array(phase_data[phase])

        ax.set_xticks(range(len(workers)))
        ax.set_xticklabels(workers)
        ax.set_xlabel('Nombre de workers')
        ax.set_ylabel('Temps (s)')
        ax.set_title(f'Decomposition temporelle - {mode} ({size} MB)')
        ax.legend()

    plt.tight_layout()
    plt.savefig(output_path / 'time_breakdown.png', dpi=150)
    plt.close()

    print(f"Graphiques generes dans {output_path}")


# ============================================================================
#                           POINT D'ENTREE
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Modele theorique de performance pour wordcount distribue',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  # Prediction pour 32 workers, fichier 1GB, mode NFS
  python theoretical_model.py --predict --workers 32 --size 1000 --mode NFS

  # Calibrer le modele depuis des mesures
  python theoretical_model.py --calibrate measurements.csv --output params.json

  # Valider le modele
  python theoretical_model.py --validate measurements.csv --params params.json

  # Generer les graphiques de prediction
  python theoretical_model.py --plots --output ./figures
        """
    )

    # Mode de fonctionnement
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--predict', action='store_true',
                       help='Faire une prediction')
    group.add_argument('--calibrate', type=str, metavar='CSV',
                       help='Calibrer depuis un fichier CSV')
    group.add_argument('--validate', type=str, metavar='CSV',
                       help='Valider contre un fichier CSV')
    group.add_argument('--plots', action='store_true',
                       help='Generer les graphiques de prediction')

    # Parametres de prediction
    parser.add_argument('--workers', type=int, default=8,
                        help='Nombre de workers (defaut: 8)')
    parser.add_argument('--size', type=float, default=1000,
                        help='Taille du fichier en MB (defaut: 1000)')
    parser.add_argument('--mode', choices=['NFS', 'SCP'], default='NFS',
                        help='Mode de transfert (defaut: NFS)')

    # Fichiers
    parser.add_argument('--params', type=str,
                        help='Fichier de parametres JSON')
    parser.add_argument('--output', type=str, default='.',
                        help='Repertoire de sortie')

    args = parser.parse_args()

    # Charger ou creer les parametres
    if args.params:
        params = ModelParameters.load(args.params)
    else:
        params = ModelParameters()

    model = TheoreticalModel(params)

    if args.predict:
        # Mode prediction
        breakdown = model.breakdown(args.size, args.workers, args.mode)

        print("\n" + "="*60)
        print("PREDICTION DU MODELE THEORIQUE")
        print("="*60)
        print(f"Configuration:")
        print(f"  - Taille fichier: {args.size} MB")
        print(f"  - Workers: {args.workers}")
        print(f"  - Mode: {args.mode}")
        print("-"*60)
        print("Decomposition temporelle:")
        for phase, time in breakdown.items():
            if phase != 'T_total':
                print(f"  {phase}: {time:.3f} s")
        print("-"*60)
        print(f"TEMPS TOTAL: {breakdown['T_total']:.3f} s")
        print(f"Speedup: {model.speedup(args.size, args.workers, args.mode):.2f}x")
        print(f"Efficacite: {model.efficiency(args.size, args.workers, args.mode):.1%}")
        print("="*60)

    elif args.calibrate:
        # Mode calibration
        print(f"Calibration depuis {args.calibrate}...")
        df = pd.read_csv(args.calibrate)
        calibrated = calibrate_model(df)

        output_file = Path(args.output) / 'calibrated_params.json'
        calibrated.save(str(output_file))
        print(f"Parametres calibres sauvegardes dans {output_file}")

    elif args.validate:
        # Mode validation
        print(f"Validation contre {args.validate}...")
        df = pd.read_csv(args.validate)
        validate_model(model, df, args.output)

    elif args.plots:
        # Mode generation de graphiques
        generate_prediction_plots(model, output_dir=args.output)


if __name__ == "__main__":
    main()
