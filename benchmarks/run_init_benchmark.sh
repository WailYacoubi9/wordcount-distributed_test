#!/bin/bash
#=============================================================================
# BENCHMARK INITIALISATION CLUSTER
# Mesure alpha (cout par worker) et beta (overhead fixe)
#
# Modele: T_init(n) = alpha * n + beta
#=============================================================================

set -e

PROJECT_DIR="${PROJECT_DIR:-$HOME/wordcount-distributed}"
RESULTS_DIR="$PROJECT_DIR/benchmarks/results/init"
mkdir -p "$RESULTS_DIR"

echo "================================================================"
echo "      BENCHMARK INITIALISATION - Parametres alpha, beta         "
echo "================================================================"

if [ -z "$OAR_NODEFILE" ]; then
    echo "ERREUR: Ce script doit etre execute dans une reservation OAR"
    exit 1
fi

# Configuration
ALL_NODES=$(cat $OAR_NODEFILE | sort -u)
MAX_WORKERS=$(($(echo "$ALL_NODES" | wc -l) - 1))
RUNS=10

echo ""
echo "Configuration:"
echo "  Noeuds disponibles: $((MAX_WORKERS + 1))"
echo "  Max workers testes: $MAX_WORKERS"
echo "  Repetitions: $RUNS"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_FILE="$RESULTS_DIR/init_benchmark_$TIMESTAMP.csv"

echo "num_workers,run,ssh_start_time_s,jvm_start_time_s,rmi_ready_time_s,total_time_s" > "$OUTPUT_FILE"

# Compiler si necessaire
cd "$PROJECT_DIR"
mkdir -p bin
javac -d bin -sourcepath src $(find src -name "*.java") 2>/dev/null || true

# Test pour differents nombres de workers
for num_workers in $(seq 1 $MAX_WORKERS); do
    echo ""
    echo "--- Test avec $num_workers worker(s) ---"

    # Selectionner les workers
    MASTER=$(echo "$ALL_NODES" | head -n 1)
    WORKERS=$(echo "$ALL_NODES" | tail -n +2 | head -n $num_workers)

    for run in $(seq 1 $RUNS); do
        echo "  Run $run/$RUNS..."

        # Nettoyer les workers precedents
        for worker in $WORKERS; do
            ssh $worker "pkill -f WorkerNode 2>/dev/null" || true
        done
        sleep 1

        # Mesure 1: Temps SSH pour lancer les commandes
        START_SSH=$(date +%s.%N)
        for worker in $WORKERS; do
            ssh $worker "echo ready" > /dev/null &
        done
        wait
        END_SSH=$(date +%s.%N)
        SSH_TIME=$(echo "$END_SSH - $START_SSH" | bc)

        # Mesure 2: Temps de demarrage JVM + Worker
        START_JVM=$(date +%s.%N)
        for worker in $WORKERS; do
            ssh $worker "cd $PROJECT_DIR && nohup java -cp bin network.worker.WorkerNode $worker 3000 > /tmp/worker.log 2>&1 &"
        done
        END_JVM=$(date +%s.%N)
        JVM_TIME=$(echo "$END_JVM - $START_JVM" | bc)

        # Mesure 3: Temps jusqu'a ce que RMI soit pret
        START_RMI=$(date +%s.%N)
        all_ready=false
        timeout_counter=0
        while [ "$all_ready" = false ] && [ $timeout_counter -lt 60 ]; do
            ready_count=0
            for worker in $WORKERS; do
                if ssh $worker "netstat -ln 2>/dev/null | grep -q :3000"; then
                    ready_count=$((ready_count + 1))
                fi
            done
            if [ $ready_count -eq $num_workers ]; then
                all_ready=true
            else
                sleep 0.1
                timeout_counter=$((timeout_counter + 1))
            fi
        done
        END_RMI=$(date +%s.%N)
        RMI_TIME=$(echo "$END_RMI - $START_RMI" | bc)

        TOTAL_TIME=$(echo "$SSH_TIME + $JVM_TIME + $RMI_TIME" | bc)

        echo "$num_workers,$run,$SSH_TIME,$JVM_TIME,$RMI_TIME,$TOTAL_TIME" >> "$OUTPUT_FILE"

        # Nettoyer
        for worker in $WORKERS; do
            ssh $worker "pkill -f WorkerNode 2>/dev/null" || true
        done
        sleep 1
    done
done

# Calculer les statistiques et regression lineaire
echo ""
echo "[Analyse] Regression lineaire T_init = alpha * n + beta ..."

STATS_FILE="$RESULTS_DIR/init_stats_$TIMESTAMP.csv"

# Calculer moyennes par nombre de workers
echo "num_workers,mean_total_s,std_total_s" > "$STATS_FILE"

for n in $(seq 1 $MAX_WORKERS); do
    grep "^$n," "$OUTPUT_FILE" | awk -F',' -v n=$n '
    {
        sum += $6
        sumsq += $6 * $6
        count++
    }
    END {
        mean = sum / count
        std = sqrt((sumsq - sum*sum/count) / (count - 1))
        printf "%d,%.4f,%.4f\n", n, mean, std
    }' >> "$STATS_FILE"
done

# Regression lineaire avec awk
REGRESSION=$(cat "$STATS_FILE" | tail -n +2 | awk -F',' '
{
    n[NR] = $1
    t[NR] = $2
    sum_n += $1
    sum_t += $2
    sum_nt += $1 * $2
    sum_nn += $1 * $1
    count = NR
}
END {
    alpha = (count * sum_nt - sum_n * sum_t) / (count * sum_nn - sum_n * sum_n)
    beta = (sum_t - alpha * sum_n) / count

    # R squared
    mean_t = sum_t / count
    ss_tot = 0
    ss_res = 0
    for (i = 1; i <= count; i++) {
        predicted = alpha * n[i] + beta
        ss_res += (t[i] - predicted)^2
        ss_tot += (t[i] - mean_t)^2
    }
    r_squared = 1 - ss_res / ss_tot

    printf "%.4f,%.4f,%.4f", alpha, beta, r_squared
}')

ALPHA=$(echo $REGRESSION | cut -d',' -f1)
BETA=$(echo $REGRESSION | cut -d',' -f2)
R_SQUARED=$(echo $REGRESSION | cut -d',' -f3)

echo ""
echo "================================================================"
echo "           PARAMETRES POUR LE MODELE                             "
echo "================================================================"
echo ""
echo "Regression: T_init(n) = alpha * n + beta"
echo ""
echo "  alpha = $ALPHA secondes/worker"
echo "  beta = $BETA secondes (overhead fixe)"
echo "  R^2 = $R_SQUARED"
echo ""

# Sauvegarder les parametres
PARAMS_FILE="$RESULTS_DIR/init_params_$TIMESTAMP.txt"
cat > "$PARAMS_FILE" << EOF
# Parametres d'initialisation pour le modele theorique
# Date: $(date)
# Regression: T_init(n) = alpha * n + beta

alpha = $ALPHA
beta = $BETA
r_squared = $R_SQUARED
EOF

echo "Fichiers generes:"
echo "  Donnees: $OUTPUT_FILE"
echo "  Stats: $STATS_FILE"
echo "  Parametres: $PARAMS_FILE"
