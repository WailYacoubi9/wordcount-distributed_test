#!/bin/bash
#===============================================================================
# run_full_benchmark.sh
# Script principal pour executer le benchmark complet sur Grid'5000
#
# Usage:
#   ./run_full_benchmark.sh [OPTIONS]
#
# Options:
#   --workers-max N    Nombre maximum de workers (defaut: 64)
#   --file-sizes LIST  Liste des tailles de fichiers en MB (defaut: "100,1000")
#   --repetitions N    Nombre de repetitions par config (defaut: 5)
#   --mode MODE        Mode de transfert: SCP, NFS, ou BOTH (defaut: BOTH)
#   --output DIR       Repertoire de sortie (defaut: ./benchmark_results)
#   --dry-run          Afficher les commandes sans executer
#
# Prerequis:
#   - Reservation OAR active avec suffisamment de noeuds
#   - Code compile dans bin/
#   - Fichiers de test generes
#
#===============================================================================

set -euo pipefail

# === CONFIGURATION PAR DEFAUT ===
WORKERS_MAX=64
FILE_SIZES="100,1000"
REPETITIONS=5
TRANSFER_MODE="BOTH"
OUTPUT_DIR="./benchmark_results"
DRY_RUN=false
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# === PARSING DES ARGUMENTS ===
while [[ $# -gt 0 ]]; do
    case $1 in
        --workers-max)
            WORKERS_MAX="$2"
            shift 2
            ;;
        --file-sizes)
            FILE_SIZES="$2"
            shift 2
            ;;
        --repetitions)
            REPETITIONS="$2"
            shift 2
            ;;
        --mode)
            TRANSFER_MODE="$2"
            shift 2
            ;;
        --output)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help)
            head -30 "$0" | tail -20
            exit 0
            ;;
        *)
            echo "Option inconnue: $1"
            exit 1
            ;;
    esac
done

# === FONCTIONS UTILITAIRES ===

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

error() {
    echo "[ERROR] $*" >&2
    exit 1
}

run_cmd() {
    if $DRY_RUN; then
        echo "[DRY-RUN] $*"
    else
        eval "$*"
    fi
}

# === VERIFICATION DES PREREQUIS ===

log "Verification des prerequis..."

# Verifier la reservation OAR
if [[ -z "${OAR_NODEFILE:-}" ]]; then
    error "OAR_NODEFILE non defini. Lancez d'abord: oarsub -I -l nodes=N,walltime=H:M:S"
fi

# Compter les noeuds disponibles
TOTAL_NODES=$(cat "$OAR_NODEFILE" | sort -u | wc -l)
log "Noeuds disponibles: $TOTAL_NODES"

if [[ $TOTAL_NODES -lt 2 ]]; then
    error "Au moins 2 noeuds requis (1 master + 1 worker)"
fi

# Verifier la compilation
if [[ ! -d "$PROJECT_DIR/bin" ]]; then
    error "Repertoire bin/ non trouve. Compilez d'abord le projet."
fi

# === PREPARATION ===

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RESULTS_DIR="$OUTPUT_DIR/$TIMESTAMP"
mkdir -p "$RESULTS_DIR"

log "Resultats seront dans: $RESULTS_DIR"

# Sauvegarder les metadonnees
cat > "$RESULTS_DIR/metadata.txt" << EOF
Date: $(date)
Hostname: $(hostname)
Git SHA: $(git -C "$PROJECT_DIR" rev-parse HEAD 2>/dev/null || echo "N/A")
Git Branch: $(git -C "$PROJECT_DIR" branch --show-current 2>/dev/null || echo "N/A")
Total Nodes: $TOTAL_NODES
Max Workers: $WORKERS_MAX
File Sizes: $FILE_SIZES
Repetitions: $REPETITIONS
Transfer Mode: $TRANSFER_MODE
Java Version: $(java -version 2>&1 | head -1)
Kernel: $(uname -r)

Nodes List:
$(cat "$OAR_NODEFILE" | sort -u)
EOF

log "Metadonnees sauvegardees dans metadata.txt"

# === GENERER LA LISTE DES WORKERS ===

# Le premier noeud est le master
MASTER_NODE=$(cat "$OAR_NODEFILE" | sort -u | head -1)
ALL_WORKERS=($(cat "$OAR_NODEFILE" | sort -u | tail -n +2))

log "Master: $MASTER_NODE"
log "Workers disponibles: ${#ALL_WORKERS[@]}"

# === GENERER LE PLAN D'EXPERIENCE ===

log "Generation du plan d'experience..."

# Liste des nombres de workers (puissances de 2)
WORKER_COUNTS=(1)
n=2
while [[ $n -le $WORKERS_MAX ]] && [[ $n -le ${#ALL_WORKERS[@]} ]]; do
    WORKER_COUNTS+=($n)
    n=$((n * 2))
done

# Modes de transfert
if [[ "$TRANSFER_MODE" == "BOTH" ]]; then
    MODES=("NFS" "SCP")
else
    MODES=("$TRANSFER_MODE")
fi

# Fichier du plan
PLAN_FILE="$RESULTS_DIR/experiment_plan.csv"
echo "RunID,Workers,FileSize_MB,Mode,Repetition" > "$PLAN_FILE"

RUN_ID=0
for size in ${FILE_SIZES//,/ }; do
    for mode in "${MODES[@]}"; do
        for n_workers in "${WORKER_COUNTS[@]}"; do
            for rep in $(seq 1 $REPETITIONS); do
                ((RUN_ID++))
                echo "$RUN_ID,$n_workers,$size,$mode,$rep" >> "$PLAN_FILE"
            done
        done
    done
done

log "Plan genere: $RUN_ID experiences dans $PLAN_FILE"

# Randomiser l'ordre
SHUFFLED_PLAN="$RESULTS_DIR/experiment_plan_shuffled.csv"
head -1 "$PLAN_FILE" > "$SHUFFLED_PLAN"
tail -n +2 "$PLAN_FILE" | shuf >> "$SHUFFLED_PLAN"

log "Plan randomise dans experiment_plan_shuffled.csv"

# === FICHIER DE RESULTATS PRINCIPAL ===

RESULTS_CSV="$RESULTS_DIR/results.csv"
echo "RunID,Workers,FileSize_MB,Mode,Repetition,T_init_ms,T_split_ms,T_dist_ms,T_calc_ms,T_agg_ms,T_total_ms,Valid,ExitCode" > "$RESULTS_CSV"

# === WARMUP ===

log "Phase de warmup (5 runs)..."

WARMUP_WORKERS=$(echo "${ALL_WORKERS[@]}" | tr ' ' ',' | cut -d',' -f1-4)

for i in $(seq 1 5); do
    log "  Warmup run $i/5"
    run_cmd "java -cp $PROJECT_DIR/bin scheduler.Main 100MB_test.txt \"[$WARMUP_WORKERS]\" --mode NFS --quiet" || true
    sleep 2
done

# === EXECUTION DES EXPERIENCES ===

log "Debut des experiences..."
TOTAL_RUNS=$RUN_ID
CURRENT_RUN=0

# Lire le plan randomise
tail -n +2 "$SHUFFLED_PLAN" | while IFS=',' read -r run_id n_workers file_size mode rep; do
    ((CURRENT_RUN++))

    log "[$CURRENT_RUN/$TOTAL_RUNS] Run $run_id: workers=$n_workers, size=${file_size}MB, mode=$mode, rep=$rep"

    # Selectionner les workers
    SELECTED_WORKERS=$(echo "${ALL_WORKERS[@]}" | tr ' ' '\n' | head -n $n_workers | tr '\n' ',' | sed 's/,$//')

    # Fichier d'entree
    INPUT_FILE="$PROJECT_DIR/testdata/test_${file_size}MB.txt"
    if [[ ! -f "$INPUT_FILE" ]]; then
        log "  SKIP: Fichier $INPUT_FILE non trouve"
        echo "$run_id,$n_workers,$file_size,$mode,$rep,0,0,0,0,0,0,false,-1" >> "$RESULTS_CSV"
        continue
    fi

    # Attendre entre les runs
    sleep 5

    # Executer avec timestamps
    START_TIME=$(date +%s.%N)

    OUTPUT=$(java -cp "$PROJECT_DIR/bin" scheduler.Main "$INPUT_FILE" "[$SELECTED_WORKERS]" --mode "$mode" --timestamps 2>&1) || EXIT_CODE=$?
    EXIT_CODE=${EXIT_CODE:-0}

    END_TIME=$(date +%s.%N)

    # Parser les resultats
    T_init=$(echo "$OUTPUT" | grep "T_init:" | cut -d: -f2 || echo "0")
    T_split=$(echo "$OUTPUT" | grep "T_split:" | cut -d: -f2 || echo "0")
    T_dist=$(echo "$OUTPUT" | grep "T_dist:" | cut -d: -f2 || echo "0")
    T_calc=$(echo "$OUTPUT" | grep "T_calc:" | cut -d: -f2 || echo "0")
    T_agg=$(echo "$OUTPUT" | grep "T_agg:" | cut -d: -f2 || echo "0")
    T_total=$(echo "($END_TIME - $START_TIME) * 1000" | bc)

    # Validation
    VALID="true"
    if [[ $EXIT_CODE -ne 0 ]]; then
        VALID="false"
    fi

    # Enregistrer
    echo "$run_id,$n_workers,$file_size,$mode,$rep,$T_init,$T_split,$T_dist,$T_calc,$T_agg,$T_total,$VALID,$EXIT_CODE" >> "$RESULTS_CSV"

    log "  -> T_total=${T_total}ms, Valid=$VALID"

done

# === ANALYSE ===

log "Execution de l'analyse statistique..."

if command -v python3 &> /dev/null; then
    run_cmd "python3 $PROJECT_DIR/model/theoretical_model.py --validate $RESULTS_CSV --output $RESULTS_DIR"
else
    log "Python3 non disponible, analyse skippee"
fi

# === RESUME ===

log "="
log "BENCHMARK TERMINE"
log "="
log "Resultats: $RESULTS_DIR"
log "  - results.csv: Donnees brutes"
log "  - metadata.txt: Configuration"
log "  - experiment_plan.csv: Plan d'experience"
log ""
log "Prochaines etapes:"
log "  1. Telecharger les resultats: scp -r $RESULTS_DIR local_machine:."
log "  2. Analyser: python3 model/theoretical_model.py --validate results.csv"
log "  3. Mettre a jour le cahier de laboratoire"
