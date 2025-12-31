#!/bin/bash
#===============================================================================
# measure_rmi_latency.sh
# Script pour mesurer la latence RMI reelle sur Grid'5000
#
# Ce script mesure les deux composantes de la latence RMI:
#   1. Naming.lookup() - Resolution du registry RMI
#   2. executeCommand() - Appel de methode distante
#
# Usage:
#   ./measure_rmi_latency.sh [OPTIONS]
#
# Options:
#   --iterations N    Nombre d'iterations (defaut: 100)
#   --warmup N        Iterations de warmup (defaut: 10)
#   --command CMD     Commande a executer (defaut: "echo test")
#   --output DIR      Repertoire de sortie (defaut: ./rmi_latency_results)
#
#===============================================================================

set -euo pipefail

# === CONFIGURATION ===
ITERATIONS=100
WARMUP=10
TEST_COMMAND="echo test"
OUTPUT_DIR="./rmi_latency_results"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# === PARSING DES ARGUMENTS ===
while [[ $# -gt 0 ]]; do
    case $1 in
        --iterations)
            ITERATIONS="$2"
            shift 2
            ;;
        --warmup)
            WARMUP="$2"
            shift 2
            ;;
        --command)
            TEST_COMMAND="$2"
            shift 2
            ;;
        --output)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --help)
            head -25 "$0" | tail -18
            exit 0
            ;;
        *)
            echo "Option inconnue: $1"
            exit 1
            ;;
    esac
done

# === FONCTIONS ===

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

error() {
    echo "[ERROR] $*" >&2
    exit 1
}

# === VERIFICATION ===

if [[ -z "${OAR_NODEFILE:-}" ]]; then
    error "OAR_NODEFILE non defini. Lancez d'abord une reservation OAR."
fi

# === PREPARATION ===

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RESULTS_DIR="$OUTPUT_DIR/$TIMESTAMP"
mkdir -p "$RESULTS_DIR"

log "Resultats seront dans: $RESULTS_DIR"

# Sauvegarder les metadonnees
cat > "$RESULTS_DIR/metadata.txt" << EOF
Date: $(date)
Iterations: $ITERATIONS
Warmup: $WARMUP
Test Command: $TEST_COMMAND
Git SHA: $(git -C "$PROJECT_DIR" rev-parse HEAD 2>/dev/null || echo "N/A")
EOF

# === IDENTIFIER LES NOEUDS ===

MASTER_NODE=$(cat "$OAR_NODEFILE" | sort -u | head -1)
WORKER_NODES=($(cat "$OAR_NODEFILE" | sort -u | tail -n +2))

log "Master: $MASTER_NODE"
log "Workers: ${#WORKER_NODES[@]}"

# === DEMARRER LES WORKERS ===

log "Demarrage des workers RMI..."

for worker in "${WORKER_NODES[@]}"; do
    log "  Demarrage sur $worker..."

    # Tuer les processus existants
    ssh "$worker" "pkill -f 'WorkerNode' 2>/dev/null || true"
    sleep 1

    # Demarrer le worker
    ssh "$worker" "cd $PROJECT_DIR && java -cp bin network.worker.WorkerNode $worker 3000 &" &

    # Attendre que le worker soit pret
    READY=false
    for i in $(seq 1 30); do
        if ssh "$worker" "netstat -ln 2>/dev/null | grep -q ':3000'" 2>/dev/null; then
            READY=true
            break
        fi
        sleep 0.5
    done

    if ! $READY; then
        log "  ATTENTION: $worker n'est pas pret apres 15s"
    fi
done

log "Workers demarres"
sleep 2

# === FICHIER DE RESULTATS ===

RESULTS_CSV="$RESULTS_DIR/rmi_latency.csv"
echo "Worker,Iteration,LookupTime_ms,ExecTime_ms,TotalTime_ms" > "$RESULTS_CSV"

SUMMARY_CSV="$RESULTS_DIR/rmi_latency_summary.csv"
echo "Worker,LookupMean_ms,LookupStd_ms,ExecMean_ms,ExecStd_ms,TotalMean_ms,TotalStd_ms,N" > "$SUMMARY_CSV"

# === MESURES ===

for worker in "${WORKER_NODES[@]}"; do
    log "Mesure latence vers $worker..."

    # Executer le benchmark
    WORKER_CSV="$RESULTS_DIR/latency_${worker}.csv"

    java -cp "$PROJECT_DIR/bin" benchmark.RMILatencyBenchmark "$worker:3000" "$TEST_COMMAND" > "$WORKER_CSV" 2>&1 || {
        log "  ERREUR: Echec du benchmark pour $worker"
        continue
    }

    # Ajouter au fichier global (avec le nom du worker)
    tail -n +2 "$WORKER_CSV" | while read line; do
        echo "$worker,$line" >> "$RESULTS_CSV"
    done

    # Calculer les statistiques
    if command -v python3 &> /dev/null; then
        python3 - << EOF >> "$SUMMARY_CSV"
import pandas as pd
import sys

try:
    df = pd.read_csv('$WORKER_CSV')
    lookup_mean = df['LookupTime_ms'].mean()
    lookup_std = df['LookupTime_ms'].std()
    exec_mean = df['ExecTime_ms'].mean()
    exec_std = df['ExecTime_ms'].std()
    total_mean = df['TotalTime_ms'].mean()
    total_std = df['TotalTime_ms'].std()
    n = len(df)
    print(f'$worker,{lookup_mean:.3f},{lookup_std:.3f},{exec_mean:.3f},{exec_std:.3f},{total_mean:.3f},{total_std:.3f},{n}')
except Exception as e:
    print(f'$worker,0,0,0,0,0,0,0', file=sys.stderr)
EOF
    fi

    log "  Termine pour $worker"
done

# === ARRETER LES WORKERS ===

log "Arret des workers..."
for worker in "${WORKER_NODES[@]}"; do
    ssh "$worker" "pkill -f 'WorkerNode' 2>/dev/null || true" &
done
wait

# === AFFICHER LE RESUME ===

log ""
log "=============================================="
log "RESUME DES LATENCES RMI"
log "=============================================="

if [[ -f "$SUMMARY_CSV" ]]; then
    cat "$SUMMARY_CSV"
fi

log ""
log "Resultats complets dans: $RESULTS_DIR"
log "  - rmi_latency.csv: Toutes les mesures"
log "  - rmi_latency_summary.csv: Statistiques par worker"
log "  - latency_*.csv: Mesures par worker"
