#!/usr/bin/env python3
"""
Generate Academic Report Summary
Creates a comprehensive summary of model validation results

Output: Markdown file ready for conversion to PDF
"""

import os
import sys
import numpy as np
import pandas as pd
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(SCRIPT_DIR, '..', 'benchmarks', 'results')
OUTPUT_DIR = os.path.join(SCRIPT_DIR, 'output')


def generate_report():
    """Generate markdown report."""

    report = f"""# Rapport de Validation du Modèle Théorique
## Wordcount Distribué sur Grid5000

**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## 1. Modèle Théorique

### Formule Principale

$$T_{{total}} = T_{{init}}(n) + T_{{seq}}(S) + T_{{comm}}(S,n,mode) + T_{{calc}}(S,n) + T_{{agg}}$$

### Composantes

| Composante | Formule | Description |
|------------|---------|-------------|
| $T_{{init}}(n)$ | $\\alpha \\cdot n + \\beta$ | Temps d'initialisation du cluster |
| $T_{{seq}}(S)$ | $T_{{parse}} + S / V_{{split}}$ | Traitement séquentiel |
| $T_{{comm}}$ | $n \\cdot (L + S/n / BW)$ | Communication (SCP) |
| $T_{{calc}}(S,n)$ | $(S \\cdot lines/MB) / (n \\cdot V_{{wc}})$ | Calcul parallèle |
| $T_{{agg}}$ | constante | Agrégation des résultats |

### Fondements Académiques

1. **Graham, R.L. (1969)** - "Bounds on Multiprocessing Timing Anomalies"
   - Borne pour l'ordonnancement: $T \\leq \\Sigma T_i / m + T_{{max}}$

2. **Culler et al. (1993)** - "LogP: A Practical Model of Parallel Computation"
   - Modèle de communication: L (latence), o (overhead), g (gap), P (processeurs)

3. **Valiant, L.G. (1990)** - "A Bridging Model for Parallel Computation"
   - Modèle BSP pour la synchronisation

---

## 2. Paramètres Mesurés

"""

    # Try to load and add parameter values
    try:
        from model.performance_model import load_parameters
        config_file = os.path.join(SCRIPT_DIR, '..', 'model', 'model_config.ini')
        params = load_parameters(config_file)

        report += f"""
### Valeurs Calibrées

| Paramètre | Valeur | Unité | Description |
|-----------|--------|-------|-------------|
| $\\alpha$ | {params.alpha:.4f} | s/worker | Pente d'initialisation |
| $\\beta$ | {params.beta:.4f} | s | Overhead fixe |
| $L_{{rmi}}$ | {params.L_rmi:.2f} | ms | Latence RMI lookup |
| $o_{{rmi}}$ | {params.o_rmi:.2f} | ms | Overhead RMI execute |
| $L_{{scp}}$ | {params.L_scp:.2f} | ms | Latence SCP |
| $BW_{{scp}}$ | {params.BW_scp:.2f} | MB/s | Bande passante SCP |
| $L_{{nfs}}$ | {params.L_nfs:.2f} | ms | Latence NFS |
| $BW_{{nfs}}$ | {params.BW_nfs:.2f} | MB/s | Bande passante NFS |
| $V_{{wc}}$ | {params.V_wc:.0f} | lignes/s | Vitesse wordcount |

"""
    except Exception as e:
        report += f"\n*Paramètres non disponibles: {e}*\n\n"

    report += """---

## 3. Protocole de Mesure

### 3.1 Mesure de la Latence RMI

```bash
./benchmarks/run_rmi_benchmark.sh
```

- **Warmup:** 10 itérations (non comptées)
- **Mesures:** 100 itérations
- **Métriques:** Naming.lookup(), executeCommand()

### 3.2 Mesure des Transferts

```bash
./benchmarks/run_transfer_benchmark.sh
```

- **Tailles testées:** 1KB, 10KB, 100KB, 1MB, 10MB, 100MB, 512MB
- **Répétitions:** 30 par configuration
- **Modes:** SCP et NFS

### 3.3 Mesure du Wordcount

```bash
./benchmarks/run_wordcount_benchmark.sh
```

- **Fichiers:** 1K, 10K, 100K, 1M, 5M lignes
- **Répétitions:** 30 par taille

### 3.4 Mesure de l'Initialisation

```bash
./benchmarks/run_init_benchmark.sh
```

- **Workers testés:** 1, 2, 4, 8, 16, 32, 64
- **Répétitions:** 10 par configuration
- **Régression linéaire:** T = αn + β

---

## 4. Validation du Modèle

### 4.1 Métriques de Qualité

| Métrique | Formule | Interprétation |
|----------|---------|----------------|
| R² | $1 - SS_{res}/SS_{tot}$ | >0.9 = excellent |
| MAPE | $\\frac{1}{n}\\sum|\\frac{y-\\hat{y}}{y}|$ | <10% = excellent |
| IC 95% | $\\bar{x} \\pm t_{0.975} \\cdot \\frac{s}{\\sqrt{n}}$ | Intervalle de confiance |

### 4.2 Script de Validation

```bash
./benchmarks/validate_model.sh
```

---

## 5. Graphiques Générés

### Paramètres
- `rmi_latency_distribution.png` - Distribution L_rmi et o_rmi
- `transfer_benchmark.png` - Comparaison SCP vs NFS
- `wordcount_speed.png` - Vitesse V_wc
- `init_time_model.png` - Régression T_init

### Validation
- `validation_predicted_vs_actual_*.png` - Comparaison prédiction/réel
- `speedup_efficiency_*.png` - Courbes d'accélération
- `time_decomposition_*.png` - Décomposition temporelle
- `error_analysis_*.png` - Analyse des erreurs

---

## 6. Commandes de Génération

```bash
# 1. Exécuter les benchmarks (sur Grid5000)
./benchmarks/run_rmi_benchmark.sh
./benchmarks/run_transfer_benchmark.sh
./benchmarks/run_wordcount_benchmark.sh
./benchmarks/run_init_benchmark.sh

# 2. Calibrer le modèle
python benchmarks/calibrate_model.py

# 3. Valider le modèle
./benchmarks/validate_model.sh

# 4. Générer les graphiques
cd plots && pip install -r requirements.txt
python generate_all_plots.py
```

---

## Annexe: Structure des Fichiers

```
wordcount-distributed_test/
├── benchmarks/
│   ├── run_rmi_benchmark.sh
│   ├── run_transfer_benchmark.sh
│   ├── run_wordcount_benchmark.sh
│   ├── run_init_benchmark.sh
│   ├── calibrate_model.py
│   ├── validate_model.sh
│   └── results/
├── model/
│   ├── performance_model.py
│   └── model_config.ini
├── plots/
│   ├── plot_validation.py
│   ├── plot_parameters.py
│   ├── generate_all_plots.py
│   └── output/
├── src/benchmark/
│   └── RMILatencyBenchmark.java
└── CAHIER_DE_LABORATOIRE.org
```

"""

    # Save report
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    report_file = os.path.join(OUTPUT_DIR, 'validation_report.md')
    with open(report_file, 'w') as f:
        f.write(report)

    print(f"Report generated: {report_file}")
    return report_file


if __name__ == "__main__":
    generate_report()
