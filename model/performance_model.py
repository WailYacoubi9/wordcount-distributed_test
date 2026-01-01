#!/usr/bin/env python3
"""
Modele Theorique de Performance - Wordcount Distribue
Systemes Distribues - Projet Makefile Parallele

References academiques:
- Graham, R.L. (1969). Bounds on Multiprocessing Timing Anomalies
- Culler et al. (1993). LogP: A Practical Model of Parallel Computation
- Valiant, L.G. (1990). A Bridging Model for Parallel Computation (BSP)
- Amdahl, G.M. (1967). Validity of the single processor approach

Formule:
    T_total = T_init + T_seq + T_comm + T_calc + T_agg
"""

import os
import configparser
from dataclasses import dataclass
from typing import Literal, Tuple

@dataclass
class ModelParameters:
    """Parametres calibres du modele theorique"""

    # Initialisation: T_init(n) = alpha * n + beta
    alpha: float = 0.5      # secondes par worker
    beta: float = 1.0       # overhead fixe (secondes)

    # RMI: latence et overhead (modele LogP)
    L_rmi: float = 50.0     # latence lookup (ms)
    o_rmi: float = 10.0     # overhead appel (ms)

    # Transfert SCP
    L_scp: float = 200.0    # latence SCP (ms)
    BW_scp: float = 100.0   # bande passante SCP (MB/s)

    # Transfert NFS
    L_nfs: float = 5.0      # latence NFS (ms)
    BW_nfs: float = 500.0   # bande passante NFS (MB/s)

    # Calcul
    V_wc: float = 100000.0  # vitesse wordcount (lignes/s)

    # Agregation
    T_agg: float = 0.05     # temps fixe (secondes)

    # Sequentiel
    T_parse: float = 0.01   # parsing Makefile (secondes)
    V_split: float = 500.0  # vitesse split (MB/s)


def T_init(n: int, params: ModelParameters) -> float:
    """
    Temps d'initialisation du cluster.
    Modele lineaire: T = alpha * n + beta

    Fondement: Overhead de creation de connexions RMI/TCP
    """
    return params.alpha * n + params.beta


def T_seq(size_mb: float, params: ModelParameters) -> float:
    """
    Temps de traitement sequentiel (parsing + split).
    Modele I/O bound: T = T_parse + S / V_split
    """
    return params.T_parse + size_mb / params.V_split


def T_comm(size_mb: float, n: int, mode: str, params: ModelParameters) -> float:
    """
    Temps de communication (distribution des fichiers).

    SCP: T = n * (L + S/n / BW)  [sequentiel par worker]
    NFS: T = L                   [acces direct, negligeable]

    Fondement: Modele LogP - L (latence) + g (gap = 1/BW)
    """
    if mode.upper() == "SCP":
        partition_size = size_mb / n
        return n * (params.L_scp / 1000 + partition_size / params.BW_scp)
    else:  # NFS
        return params.L_nfs / 1000


def T_calc(size_mb: float, n: int, params: ModelParameters,
           words_per_line: int = 5, lines_per_mb: int = 10000) -> float:
    """
    Temps de calcul parallele.

    Modele de Graham: T <= Sigma(T_i) / m + T_max

    Dans notre cas (partitions equilibrees):
    T = (total_lines / n) / V_wc + n * (L_rmi + o_rmi)

    Fondement: Borne de Graham (1969) pour List Scheduling
    """
    total_lines = size_mb * lines_per_mb
    lines_per_worker = total_lines / n

    # Temps de calcul par worker
    T_worker = lines_per_worker / params.V_wc

    # Overhead RMI (n appels)
    T_rmi_overhead = n * (params.L_rmi + params.o_rmi) / 1000

    return T_worker + T_rmi_overhead


def T_total(size_mb: float, n: int, mode: str, params: ModelParameters) -> float:
    """
    Temps total predit par le modele.

    T_total = T_init + T_seq + T_comm + T_calc + T_agg
    """
    return (T_init(n, params) +
            T_seq(size_mb, params) +
            T_comm(size_mb, n, mode, params) +
            T_calc(size_mb, n, params) +
            params.T_agg)


def speedup(size_mb: float, n: int, mode: str, params: ModelParameters) -> float:
    """
    Acceleration: S(n) = T(1) / T(n)

    Fondement: Loi d'Amdahl / Gustafson
    """
    T_1 = T_total(size_mb, 1, mode, params)
    T_n = T_total(size_mb, n, mode, params)
    return T_1 / T_n


def efficiency(size_mb: float, n: int, mode: str, params: ModelParameters) -> float:
    """
    Efficacite: E(n) = S(n) / n

    E = 1 -> parfaitement parallele
    E < 1 -> overhead de parallelisation
    """
    return speedup(size_mb, n, mode, params) / n


def load_parameters(config_file: str) -> ModelParameters:
    """Charge les parametres depuis un fichier de configuration."""
    if not os.path.exists(config_file):
        print(f"Fichier de configuration non trouve: {config_file}")
        print("Utilisation des valeurs par defaut.")
        return ModelParameters()

    config = configparser.ConfigParser()
    config.read(config_file)

    params = ModelParameters()

    if 'initialization' in config:
        params.alpha = float(config['initialization'].get('alpha', params.alpha))
        params.beta = float(config['initialization'].get('beta', params.beta))

    if 'rmi' in config:
        params.L_rmi = float(config['rmi'].get('L_rmi', params.L_rmi))
        params.o_rmi = float(config['rmi'].get('o_rmi', params.o_rmi))

    if 'transfer_scp' in config:
        params.L_scp = float(config['transfer_scp'].get('L_scp', params.L_scp))
        params.BW_scp = float(config['transfer_scp'].get('BW_scp', params.BW_scp))

    if 'transfer_nfs' in config:
        params.L_nfs = float(config['transfer_nfs'].get('L_nfs', params.L_nfs))
        params.BW_nfs = float(config['transfer_nfs'].get('BW_nfs', params.BW_nfs))

    if 'compute' in config:
        params.V_wc = float(config['compute'].get('V_wc', params.V_wc))

    if 'sequential' in config:
        params.T_parse = float(config['sequential'].get('T_parse', params.T_parse))
        params.V_split = float(config['sequential'].get('V_split', params.V_split))

    if 'aggregation' in config:
        params.T_agg = float(config['aggregation'].get('T_agg', params.T_agg))

    return params


def print_predictions(params: ModelParameters, size_mb: float = 1000, mode: str = "NFS"):
    """Affiche les predictions du modele."""
    print("=" * 60)
    print("MODELE THEORIQUE DE PERFORMANCE")
    print("Wordcount Distribue sur Grid5000")
    print("=" * 60)
    print(f"\nConfiguration: {size_mb} MB, mode {mode}")
    print("-" * 60)
    print(f"{'Workers':<10} {'T_total (s)':<15} {'Speedup':<10} {'Efficacite':<10}")
    print("-" * 60)

    for n in [1, 2, 4, 8, 16, 32, 64]:
        t = T_total(size_mb, n, mode, params)
        s = speedup(size_mb, n, mode, params)
        e = efficiency(size_mb, n, mode, params)
        print(f"{n:<10} {t:<15.2f} {s:<10.2f} {e:<10.2%}")

    print("\n" + "=" * 60)
    print(f"Decomposition pour 32 workers ({size_mb} MB, {mode}):")
    print("-" * 60)
    n = 32
    print(f"T_init:   {T_init(n, params):.3f} s")
    print(f"T_seq:    {T_seq(size_mb, params):.3f} s")
    print(f"T_comm:   {T_comm(size_mb, n, mode, params):.3f} s")
    print(f"T_calc:   {T_calc(size_mb, n, params):.3f} s")
    print(f"T_agg:    {params.T_agg:.3f} s")
    print(f"TOTAL:    {T_total(size_mb, n, mode, params):.3f} s")
    print("=" * 60)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Modele theorique de performance")
    parser.add_argument("--config", default="model/model_config.ini",
                       help="Fichier de configuration")
    parser.add_argument("--size", type=float, default=1000,
                       help="Taille du fichier (MB)")
    parser.add_argument("--mode", default="NFS", choices=["NFS", "SCP"],
                       help="Mode de transfert")

    args = parser.parse_args()

    params = load_parameters(args.config)
    print_predictions(params, args.size, args.mode)
