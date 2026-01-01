#!/usr/bin/env python3
"""
Calibration du Modele Theorique de Performance
Wordcount Distribue sur Grid5000

Ce script:
1. Lit les mesures des benchmarks
2. Extrait les parametres du modele
3. Genere le fichier de configuration du modele
"""

import os
import csv
import glob
import argparse
from dataclasses import dataclass
from typing import Optional, Tuple
from datetime import datetime


@dataclass
class ModelParameters:
    """Parametres calibres du modele theorique"""
    alpha: float = 0.5
    beta: float = 1.0
    L_rmi: float = 50.0
    o_rmi: float = 10.0
    L_scp: float = 200.0
    BW_scp: float = 100.0
    L_nfs: float = 5.0
    BW_nfs: float = 500.0
    V_wc: float = 100000.0
    T_agg: float = 0.05
    T_parse: float = 0.01
    V_split: float = 500.0


def load_rmi_params(results_dir: str) -> Tuple[Optional[float], Optional[float]]:
    """Charge les parametres RMI depuis les benchmarks"""
    pattern = os.path.join(results_dir, "rmi", "rmi_summary_*.csv")
    files = sorted(glob.glob(pattern))

    if not files:
        print(f"  Aucun fichier RMI trouve dans {results_dir}/rmi/")
        return None, None

    latest = files[-1]
    print(f"  Lecture: {os.path.basename(latest)}")

    L_rmi_values = []
    o_rmi_values = []

    with open(latest, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                L_rmi_values.append(float(row['L_rmi_mean_ms']))
                o_rmi_values.append(float(row['o_rmi_mean_ms']))
            except (KeyError, ValueError):
                continue

    if not L_rmi_values:
        return None, None

    return sum(L_rmi_values) / len(L_rmi_values), sum(o_rmi_values) / len(o_rmi_values)


def load_transfer_params(results_dir: str) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    """Charge les parametres de transfert depuis les benchmarks"""
    pattern = os.path.join(results_dir, "transfer", "transfer_params_*.txt")
    files = sorted(glob.glob(pattern))

    if not files:
        print(f"  Aucun fichier transfert trouve dans {results_dir}/transfer/")
        return None, None, None, None

    latest = files[-1]
    print(f"  Lecture: {os.path.basename(latest)}")

    params = {}
    with open(latest, 'r') as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, value = line.split('=')
                params[key.strip()] = float(value.strip())

    return (
        params.get('L_scp_ms'),
        params.get('BW_scp_mbps'),
        params.get('L_nfs_ms'),
        params.get('BW_nfs_mbps')
    )


def load_compute_params(results_dir: str) -> Optional[float]:
    """Charge les parametres de calcul depuis les benchmarks"""
    pattern = os.path.join(results_dir, "compute", "wordcount_stats_*.csv")
    files = sorted(glob.glob(pattern))

    if not files:
        print(f"  Aucun fichier compute trouve dans {results_dir}/compute/")
        return None

    latest = files[-1]
    print(f"  Lecture: {os.path.basename(latest)}")

    V_wc_values = []
    with open(latest, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        for row in rows[-3:]:  # 3 plus grandes tailles
            try:
                V_wc_values.append(float(row['mean_lines_per_s']))
            except (KeyError, ValueError):
                continue

    if not V_wc_values:
        return None

    return sum(V_wc_values) / len(V_wc_values)


def load_init_params(results_dir: str) -> Tuple[Optional[float], Optional[float]]:
    """Charge les parametres d'initialisation depuis les benchmarks"""
    pattern = os.path.join(results_dir, "init", "init_params_*.txt")
    files = sorted(glob.glob(pattern))

    if not files:
        print(f"  Aucun fichier init trouve dans {results_dir}/init/")
        return None, None

    latest = files[-1]
    print(f"  Lecture: {os.path.basename(latest)}")

    params = {}
    with open(latest, 'r') as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, value = line.split('=')
                params[key.strip()] = float(value.strip())

    return params.get('alpha'), params.get('beta')


def calibrate_model(results_dir: str) -> ModelParameters:
    """Calibre le modele a partir des mesures"""

    params = ModelParameters()

    print("\n" + "=" * 60)
    print("CALIBRATION DU MODELE THEORIQUE")
    print("=" * 60)

    # 1. Parametres RMI
    print("\n[1/4] Parametres RMI...")
    L_rmi, o_rmi = load_rmi_params(results_dir)
    if L_rmi is not None:
        params.L_rmi = L_rmi
        params.o_rmi = o_rmi
        print(f"  OK: L_rmi = {L_rmi:.3f} ms")
        print(f"  OK: o_rmi = {o_rmi:.3f} ms")
    else:
        print(f"  DEFAUT: L_rmi = {params.L_rmi} ms")

    # 2. Parametres de transfert
    print("\n[2/4] Parametres de transfert...")
    L_scp, BW_scp, L_nfs, BW_nfs = load_transfer_params(results_dir)
    if L_scp is not None:
        params.L_scp = L_scp
        params.BW_scp = BW_scp
        params.L_nfs = L_nfs
        params.BW_nfs = BW_nfs
        print(f"  OK: L_scp = {L_scp:.3f} ms, BW_scp = {BW_scp:.2f} MB/s")
        print(f"  OK: L_nfs = {L_nfs:.3f} ms, BW_nfs = {BW_nfs:.2f} MB/s")
    else:
        print(f"  DEFAUT: L_scp = {params.L_scp} ms")

    # 3. Parametres de calcul
    print("\n[3/4] Parametres de calcul...")
    V_wc = load_compute_params(results_dir)
    if V_wc is not None:
        params.V_wc = V_wc
        print(f"  OK: V_wc = {V_wc:.0f} lignes/s")
    else:
        print(f"  DEFAUT: V_wc = {params.V_wc} lignes/s")

    # 4. Parametres d'initialisation
    print("\n[4/4] Parametres d'initialisation...")
    alpha, beta = load_init_params(results_dir)
    if alpha is not None:
        params.alpha = alpha
        params.beta = beta
        print(f"  OK: alpha = {alpha:.4f} s/worker")
        print(f"  OK: beta = {beta:.4f} s")
    else:
        print(f"  DEFAUT: alpha = {params.alpha} s/worker")

    return params


def save_model_config(params: ModelParameters, output_file: str):
    """Sauvegarde la configuration du modele"""

    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    with open(output_file, 'w') as f:
        f.write("# Configuration du Modele Theorique de Performance\n")
        f.write("# Wordcount Distribue sur Grid5000\n")
        f.write(f"# Genere le: {datetime.now()}\n")
        f.write("#\n")
        f.write("# Formule: T_total = T_init + T_seq + T_comm + T_calc + T_agg\n")
        f.write("#\n\n")

        f.write("[initialization]\n")
        f.write(f"# T_init(n) = alpha * n + beta\n")
        f.write(f"alpha = {params.alpha}\n")
        f.write(f"beta = {params.beta}\n\n")

        f.write("[rmi]\n")
        f.write(f"# Latence lookup RMI (ms)\n")
        f.write(f"L_rmi = {params.L_rmi}\n")
        f.write(f"# Overhead appel RMI (ms)\n")
        f.write(f"o_rmi = {params.o_rmi}\n\n")

        f.write("[transfer_scp]\n")
        f.write(f"# Latence SCP (ms)\n")
        f.write(f"L_scp = {params.L_scp}\n")
        f.write(f"# Bande passante SCP (MB/s)\n")
        f.write(f"BW_scp = {params.BW_scp}\n\n")

        f.write("[transfer_nfs]\n")
        f.write(f"# Latence NFS (ms)\n")
        f.write(f"L_nfs = {params.L_nfs}\n")
        f.write(f"# Bande passante NFS (MB/s)\n")
        f.write(f"BW_nfs = {params.BW_nfs}\n\n")

        f.write("[compute]\n")
        f.write(f"# Vitesse wordcount (lignes/s)\n")
        f.write(f"V_wc = {params.V_wc}\n\n")

        f.write("[sequential]\n")
        f.write(f"# Temps de parsing (s)\n")
        f.write(f"T_parse = {params.T_parse}\n")
        f.write(f"# Vitesse de split (MB/s)\n")
        f.write(f"V_split = {params.V_split}\n\n")

        f.write("[aggregation]\n")
        f.write(f"# Temps d'agregation (s)\n")
        f.write(f"T_agg = {params.T_agg}\n")

    print(f"\nConfiguration sauvegardee: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Calibration du modele theorique")
    parser.add_argument("--results-dir", default="benchmarks/results",
                       help="Repertoire des resultats de benchmark")
    parser.add_argument("--output", default="model/model_config.ini",
                       help="Fichier de sortie")

    args = parser.parse_args()

    # Calibrer le modele
    params = calibrate_model(args.results_dir)

    # Sauvegarder
    save_model_config(params, args.output)

    # Afficher le resume
    print("\n" + "=" * 60)
    print("RESUME DES PARAMETRES")
    print("=" * 60)
    print(f"""
T_init(n) = {params.alpha:.4f} * n + {params.beta:.4f}

T_comm_scp(S, n) = n * ({params.L_scp:.1f}ms + S/n / {params.BW_scp:.1f} MB/s)
T_comm_nfs(S, n) = {params.L_nfs:.1f}ms

T_calc(S, n) = S / ({params.V_wc:.0f} * n) + n * ({params.L_rmi:.1f} + {params.o_rmi:.1f})ms

T_agg = {params.T_agg:.3f}s
""")


if __name__ == "__main__":
    main()
