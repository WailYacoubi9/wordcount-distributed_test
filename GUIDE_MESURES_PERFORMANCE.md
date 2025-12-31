# Guide Académique de Mesures de Performance
## Système Distribué de Wordcount sur Grid'5000

---

## Table des Matières

1. [Méthodologie Expérimentale](#1-méthodologie-expérimentale)
2. [Définition des Métriques](#2-définition-des-métriques)
3. [Paramètres à Mesurer](#3-paramètres-à-mesurer)
4. [Protocole Expérimental](#4-protocole-expérimental)
5. [Scripts de Mesure](#5-scripts-de-mesure)
6. [Analyse Statistique](#6-analyse-statistique)
7. [Modèle Théorique](#7-modèle-théorique)
8. [Présentation des Résultats](#8-présentation-des-résultats)
9. [Cahier de Laboratoire](#9-cahier-de-laboratoire)

---

## 1. Méthodologie Expérimentale

### 1.1 Principes Fondamentaux

Une mesure de performance scientifique doit respecter :

| Principe | Description | Application |
|----------|-------------|-------------|
| **Reproductibilité** | Mêmes conditions → mêmes résultats | Scripts automatisés, versions git fixées |
| **Isolation** | Éliminer les variables parasites | Réservation exclusive des nœuds |
| **Répétition** | Plusieurs mesures par configuration | Minimum 30 runs pour intervalles de confiance |
| **Contrôle** | Maîtriser toutes les variables | Documenter environnement complet |

### 1.2 Variables Expérimentales

```
┌─────────────────────────────────────────────────────────────────┐
│                    VARIABLES INDÉPENDANTES                       │
│                    (Ce que vous contrôlez)                       │
├─────────────────────────────────────────────────────────────────┤
│ • Nombre de workers (n) : 1, 2, 4, 8, 16, 32, 64               │
│ • Taille du fichier d'entrée (S) : 10MB, 100MB, 1GB, 10GB      │
│ • Mode de transfert : SCP vs NFS                                 │
│ • Site Grid'5000 : Nancy, Lille, Grenoble, etc.                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    VARIABLES DÉPENDANTES                         │
│                    (Ce que vous mesurez)                         │
├─────────────────────────────────────────────────────────────────┤
│ • Temps d'exécution total (T_total)                             │
│ • Temps par phase (T_init, T_split, T_dist, T_calc, T_agg)     │
│ • Latence RMI (T_lookup, T_exec)                                │
│ • Débit de transfert (MB/s)                                      │
│ • Utilisation CPU/mémoire                                        │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    VARIABLES PARASITES                           │
│                    (À contrôler/éliminer)                        │
├─────────────────────────────────────────────────────────────────┤
│ • Charge réseau d'autres utilisateurs                           │
│ • État du cache disque/mémoire                                   │
│ • Variations de performance des nœuds                            │
│ • Hétérogénéité du cluster                                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Définition des Métriques

### 2.1 Métriques Primaires

#### Temps d'Exécution (T)
```
T_total = T_init + T_split + T_dist + T_calc + T_agg + T_sync
```

#### Accélération (Speedup)
```
S(n) = T(1) / T(n)

Où :
  T(1) = Temps d'exécution séquentiel (1 worker)
  T(n) = Temps d'exécution avec n workers

Interprétation :
  S(n) = n     → Accélération linéaire (idéale)
  S(n) < n     → Overhead de parallélisation
  S(n) > n     → Super-linéaire (effet de cache)
```

#### Efficacité (Efficiency)
```
E(n) = S(n) / n = T(1) / (n × T(n))

Interprétation :
  E = 1.0   → Parfaitement parallèle
  E = 0.5   → 50% du temps est de l'overhead
  E → 0     → Mauvaise scalabilité
```

#### Passage à l'Échelle (Scalability)
```
Scalabilité forte : Taille fixe, augmenter n
  → Mesure la réduction du temps pour un problème fixe

Scalabilité faible : Taille/n fixe, augmenter n
  → Mesure la capacité à traiter des problèmes plus grands
```

### 2.2 Métriques Secondaires

| Métrique | Formule | Unité |
|----------|---------|-------|
| Débit (Throughput) | `D = Données_traitées / T_total` | MB/s ou mots/s |
| Latence moyenne | `L_avg = Σ L_i / n` | ms |
| Écart-type latence | `σ = √(Σ(L_i - L_avg)² / n)` | ms |
| Coefficient de variation | `CV = σ / L_avg` | % |

---

## 3. Paramètres à Mesurer

### 3.1 Vue d'Ensemble des Composantes Temporelles

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DÉCOMPOSITION TEMPORELLE                             │
│                                                                              │
│  T_total = T_init + T_split + T_dist + T_calc + T_agg                       │
│                                                                              │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐  │
│  │  T_init  │ → │ T_split  │ → │  T_dist  │ → │  T_calc  │ → │  T_agg   │  │
│  │          │   │          │   │          │   │          │   │          │  │
│  │ Démarre  │   │ Découpe  │   │ Envoie   │   │ Exécute  │   │ Fusionne │  │
│  │ workers  │   │ fichier  │   │ partitions│   │ wordcount│   │ résultats│  │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘  │
│      ↓               ↓               ↓               ↓               ↓      │
│  ~500ms/node    ~S/BW_disk    voir 3.3       voir 3.4         ~50ms        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Paramètre 1 : Temps d'Initialisation (T_init)

**Ce qu'il représente** : Temps pour démarrer les workers RMI et établir les connexions.

**Formule théorique** :
```
T_init(n) = α × n + β

Où :
  α = temps par worker (latence SSH + démarrage JVM + création registry)
  β = overhead fixe (démarrage master)
```

**Comment mesurer** :

```java
// Dans MasterCoordinator.java ou nouveau fichier InitBenchmark.java

public class InitBenchmark {
    public static void main(String[] args) throws Exception {
        String[] workers = parseWorkerList(args[0]);
        int n = workers.length;

        // Point de départ
        long startTotal = System.nanoTime();

        // Démarrer les workers (via SSH)
        for (String worker : workers) {
            long startWorker = System.nanoTime();

            ProcessBuilder pb = new ProcessBuilder(
                "ssh", worker,
                "java -cp /path/to/bin network.worker.WorkerNode " + worker + " 3000"
            );
            pb.start();

            // Attendre que le registry soit prêt
            boolean ready = false;
            while (!ready) {
                try {
                    Naming.lookup("rmi://" + worker + ":3000/Worker");
                    ready = true;
                } catch (Exception e) {
                    Thread.sleep(100);
                }
            }

            long endWorker = System.nanoTime();
            System.out.println("INIT_WORKER," + worker + "," +
                ((endWorker - startWorker) / 1_000_000.0));
        }

        long endTotal = System.nanoTime();
        System.out.println("INIT_TOTAL," + n + "," +
            ((endTotal - startTotal) / 1_000_000.0));
    }
}
```

### 3.3 Paramètre 2 : Temps de Distribution (T_dist)

**Ce qu'il représente** : Temps pour transférer les partitions aux workers.

**Formule théorique** :
```
Mode SCP (séquentiel) :
  T_dist = n × (L_scp + S/n / BW_scp)
         = n × L_scp + S / BW_scp

Mode SCP (parallèle avec threads) :
  T_dist = L_scp + S/n / BW_scp  (goulot = plus gros transfert)

Mode NFS :
  T_dist ≈ 0  (accès direct, négligeable)

Où :
  L_scp = latence SCP (~300ms)
  BW_scp = bande passante SCP (~400 MB/s pour gros fichiers)
  S = taille totale du fichier
  n = nombre de workers
```

**Comment mesurer** :

```bash
#!/bin/bash
# measure_distribution.sh

SIZES="10485760 104857600 1073741824"  # 10MB, 100MB, 1GB
WORKERS=$(cat $OAR_NODEFILE | sort -u | tail -n +2)
RESULTS_FILE="dist_times_$(date +%Y%m%d_%H%M%S).csv"

echo "Mode,FileSize_bytes,NumWorkers,Worker,Duration_ms,Bandwidth_MBps" > $RESULTS_FILE

for SIZE in $SIZES; do
    # Créer fichier de test
    dd if=/dev/urandom of=/tmp/testfile bs=1M count=$((SIZE/1048576)) 2>/dev/null

    for worker in $WORKERS; do
        # Mesure SCP
        START=$(date +%s.%N)
        scp /tmp/testfile $worker:/tmp/testfile_$SIZE 2>/dev/null
        END=$(date +%s.%N)

        DURATION=$(echo "($END - $START) * 1000" | bc)
        BW=$(echo "$SIZE / ($END - $START) / 1048576" | bc -l)

        echo "SCP,$SIZE,1,$worker,$DURATION,$BW" >> $RESULTS_FILE

        # Nettoyage
        ssh $worker "rm -f /tmp/testfile_$SIZE"
    done

    rm -f /tmp/testfile
done
```

### 3.4 Paramètre 3 : Latence RMI (T_rmi)

**Ce qu'il représente** : Temps pour effectuer un appel RMI distant.

**Formule théorique** :
```
T_rmi = T_lookup + T_serialize + T_network + T_deserialize + T_execute

Composantes :
  T_lookup    : Résolution du nom dans le registry (~50-200ms)
  T_serialize : Sérialisation des arguments (~1-5ms)
  T_network   : Transmission réseau (L + data/BW)
  T_deserialize : Désérialisation côté serveur (~1-5ms)
  T_execute   : Exécution de la méthode distante (variable)
```

**Comment mesurer** :

```java
// src/benchmark/RMILatencyBenchmark.java
package benchmark;

import network.worker.WorkerInterface;
import java.rmi.Naming;
import java.util.ArrayList;
import java.util.List;

public class RMILatencyBenchmark {

    private static final int WARMUP_ITERATIONS = 10;
    private static final int MEASUREMENT_ITERATIONS = 100;

    public static void main(String[] args) throws Exception {
        if (args.length < 1) {
            System.err.println("Usage: RMILatencyBenchmark <worker_host:port> [command]");
            System.exit(1);
        }

        String workerSpec = args[0];
        String testCommand = args.length > 1 ? args[1] : "echo test";

        String[] parts = workerSpec.split(":");
        String host = parts[0];
        int port = parts.length > 1 ? Integer.parseInt(parts[1]) : 3000;
        String url = "rmi://" + host + ":" + port + "/Worker";

        // === PHASE 1 : WARMUP ===
        System.err.println("Warmup (" + WARMUP_ITERATIONS + " iterations)...");
        for (int i = 0; i < WARMUP_ITERATIONS; i++) {
            WorkerInterface worker = (WorkerInterface) Naming.lookup(url);
            worker.executeCommand("echo warmup");
        }

        // === PHASE 2 : MESURES ===
        System.err.println("Measuring (" + MEASUREMENT_ITERATIONS + " iterations)...");

        List<Double> lookupTimes = new ArrayList<>();
        List<Double> execTimes = new ArrayList<>();

        // Header CSV
        System.out.println("Iteration,LookupTime_ms,ExecTime_ms,TotalTime_ms");

        for (int i = 0; i < MEASUREMENT_ITERATIONS; i++) {
            // Mesure du Lookup
            long startLookup = System.nanoTime();
            WorkerInterface worker = (WorkerInterface) Naming.lookup(url);
            long endLookup = System.nanoTime();
            double lookupMs = (endLookup - startLookup) / 1_000_000.0;

            // Mesure de l'exécution distante
            long startExec = System.nanoTime();
            worker.executeCommand(testCommand);
            long endExec = System.nanoTime();
            double execMs = (endExec - startExec) / 1_000_000.0;

            lookupTimes.add(lookupMs);
            execTimes.add(execMs);

            System.out.printf("%d,%.3f,%.3f,%.3f%n",
                i, lookupMs, execMs, lookupMs + execMs);
        }

        // === PHASE 3 : STATISTIQUES ===
        printStatistics("Lookup", lookupTimes);
        printStatistics("Execution", execTimes);
    }

    private static void printStatistics(String name, List<Double> values) {
        double mean = values.stream().mapToDouble(d -> d).average().orElse(0);
        double variance = values.stream()
            .mapToDouble(d -> Math.pow(d - mean, 2))
            .average().orElse(0);
        double stddev = Math.sqrt(variance);
        double min = values.stream().mapToDouble(d -> d).min().orElse(0);
        double max = values.stream().mapToDouble(d -> d).max().orElse(0);

        // Intervalle de confiance à 95% (z = 1.96)
        double ci95 = 1.96 * stddev / Math.sqrt(values.size());

        System.err.println("\n=== " + name + " Statistics ===");
        System.err.printf("  Mean:     %.3f ms%n", mean);
        System.err.printf("  Std Dev:  %.3f ms%n", stddev);
        System.err.printf("  95%% CI:   [%.3f, %.3f] ms%n", mean - ci95, mean + ci95);
        System.err.printf("  Min:      %.3f ms%n", min);
        System.err.printf("  Max:      %.3f ms%n", max);
    }
}
```

### 3.5 Paramètre 4 : Temps de Calcul (T_calc)

**Ce qu'il représente** : Temps d'exécution du wordcount sur une partition.

**Formule théorique** :
```
T_calc = f(S_partition, V_cpu)

Pour un wordcount :
  T_calc ≈ S_partition / V_traitement

Où :
  S_partition = taille de la partition en bytes ou lignes
  V_traitement = vitesse de traitement (lignes/s ou bytes/s)
```

**Comment mesurer** :

```bash
#!/bin/bash
# measure_wordcount_speed.sh

RESULTS_FILE="wordcount_speed_$(date +%Y%m%d_%H%M%S).csv"
echo "FileSize_bytes,Lines,Words,Duration_ms,Speed_lines_per_sec,Speed_bytes_per_sec" > $RESULTS_FILE

# Générer des fichiers de test de différentes tailles
for size in 1000 10000 100000 1000000 10000000; do
    # Créer fichier avec des mots aléatoires
    TESTFILE="/tmp/wordcount_test_$size.txt"

    # Générer le contenu (environ 10 mots par ligne)
    awk -v n=$size 'BEGIN {
        for(i=1; i<=n; i++) {
            line = ""
            for(j=1; j<=10; j++) {
                line = line " word" int(rand()*1000)
            }
            print line
        }
    }' > $TESTFILE

    FILE_SIZE=$(stat -c%s $TESTFILE)
    LINES=$(wc -l < $TESTFILE)
    WORDS=$(wc -w < $TESTFILE)

    # Mesurer 10 fois
    for run in $(seq 1 10); do
        # Flush cache (nécessite root)
        sync && echo 3 | sudo tee /proc/sys/vm/drop_caches > /dev/null 2>&1 || true

        START=$(date +%s.%N)
        # Utiliser la même commande que votre wordcount
        cat $TESTFILE | tr ' ' '\n' | sort | uniq -c | sort -rn > /dev/null
        END=$(date +%s.%N)

        DURATION=$(echo "($END - $START) * 1000" | bc)
        SPEED_LINES=$(echo "$LINES / ($END - $START)" | bc -l)
        SPEED_BYTES=$(echo "$FILE_SIZE / ($END - $START)" | bc -l)

        echo "$FILE_SIZE,$LINES,$WORDS,$DURATION,$SPEED_LINES,$SPEED_BYTES" >> $RESULTS_FILE
    done

    rm -f $TESTFILE
done

echo "Results saved to $RESULTS_FILE"
```

---

## 4. Protocole Expérimental

### 4.1 Plan d'Expérience Factoriel

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PLAN D'EXPÉRIENCE                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Facteur A : Nombre de workers                                               │
│    Niveaux : 1, 2, 4, 8, 16, 32, 64                                         │
│                                                                              │
│  Facteur B : Taille du fichier                                               │
│    Niveaux : 100 MB, 1 GB, 10 GB                                             │
│                                                                              │
│  Facteur C : Mode de transfert                                               │
│    Niveaux : SCP, NFS                                                        │
│                                                                              │
│  Répétitions par configuration : 30 (pour intervalle de confiance 95%)      │
│                                                                              │
│  Total d'expériences : 7 × 3 × 2 × 30 = 1260 runs                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Procédure Expérimentale Détaillée

```
AVANT CHAQUE SESSION D'EXPÉRIENCES
═══════════════════════════════════════════════════════════════════════════════

1. RÉSERVATION DES RESSOURCES
   ┌────────────────────────────────────────────────────────────────────────┐
   │ # Réserver 64 nœuds exclusifs pour 4 heures                           │
   │ oarsub -I -t exotic -l nodes=64,walltime=4:00:00                      │
   │                                                                        │
   │ # Vérifier l'homogénéité des nœuds                                    │
   │ uniq $OAR_NODEFILE | while read node; do                              │
   │     ssh $node "cat /proc/cpuinfo | grep 'model name' | head -1"       │
   │ done                                                                   │
   └────────────────────────────────────────────────────────────────────────┘

2. DOCUMENTATION DE L'ENVIRONNEMENT
   ┌────────────────────────────────────────────────────────────────────────┐
   │ # Enregistrer le commit git                                            │
   │ git rev-parse HEAD > experiment_info.txt                               │
   │                                                                        │
   │ # Enregistrer les nœuds utilisés                                       │
   │ cat $OAR_NODEFILE >> experiment_info.txt                               │
   │                                                                        │
   │ # Enregistrer la date/heure                                            │
   │ date >> experiment_info.txt                                            │
   │                                                                        │
   │ # Enregistrer les versions logicielles                                 │
   │ java -version 2>> experiment_info.txt                                  │
   │ uname -a >> experiment_info.txt                                        │
   └────────────────────────────────────────────────────────────────────────┘

3. WARMUP DU SYSTÈME
   ┌────────────────────────────────────────────────────────────────────────┐
   │ # Exécuter 5 runs de warmup (résultats ignorés)                       │
   │ for i in $(seq 1 5); do                                                │
   │     ./run_experiment.sh --warmup                                       │
   │ done                                                                   │
   └────────────────────────────────────────────────────────────────────────┘


POUR CHAQUE CONFIGURATION
═══════════════════════════════════════════════════════════════════════════════

4. ISOLATION ET PRÉPARATION
   ┌────────────────────────────────────────────────────────────────────────┐
   │ # Nettoyer les caches (si possible)                                    │
   │ for node in $(cat $OAR_NODEFILE | sort -u); do                        │
   │     ssh $node "sync; echo 3 | sudo tee /proc/sys/vm/drop_caches"      │
   │ done 2>/dev/null || echo "Cache flush skipped (no sudo)"              │
   │                                                                        │
   │ # Attendre stabilisation (30 secondes entre les runs)                 │
   │ sleep 30                                                               │
   └────────────────────────────────────────────────────────────────────────┘

5. EXÉCUTION ET MESURE
   ┌────────────────────────────────────────────────────────────────────────┐
   │ # Enregistrer les timestamps de début/fin                              │
   │ START=$(date +%s.%N)                                                   │
   │                                                                        │
   │ # Exécuter l'expérience avec timestamps internes                       │
   │ java -cp bin scheduler.Main $INPUT_FILE "[$WORKER_LIST]" \            │
   │     --mode $TRANSFER_MODE \                                            │
   │     --timestamps                                                       │
   │                                                                        │
   │ END=$(date +%s.%N)                                                     │
   │                                                                        │
   │ # Calculer le temps total                                              │
   │ DURATION=$(echo "$END - $START" | bc)                                  │
   └────────────────────────────────────────────────────────────────────────┘

6. VALIDATION DES RÉSULTATS
   ┌────────────────────────────────────────────────────────────────────────┐
   │ # Vérifier que le résultat est correct                                 │
   │ diff output.txt expected_output.txt                                    │
   │                                                                        │
   │ # Si différent, marquer le run comme invalide                          │
   │ if [ $? -ne 0 ]; then                                                  │
   │     echo "INVALID,$CONFIG,$RUN" >> invalid_runs.csv                    │
   │ fi                                                                     │
   └────────────────────────────────────────────────────────────────────────┘
```

### 4.3 Ordre d'Exécution Randomisé

Pour éviter les biais systématiques (échauffement, dégradation), randomisez l'ordre :

```python
#!/usr/bin/env python3
# generate_experiment_order.py

import random
import itertools

# Définition des facteurs
workers = [1, 2, 4, 8, 16, 32, 64]
file_sizes = ["100MB", "1GB", "10GB"]
modes = ["SCP", "NFS"]
repetitions = 30

# Générer toutes les configurations
configs = list(itertools.product(workers, file_sizes, modes))

# Répéter chaque configuration
all_runs = configs * repetitions

# Randomiser l'ordre
random.shuffle(all_runs)

# Écrire le plan d'expérience
with open("experiment_plan.csv", "w") as f:
    f.write("RunID,Workers,FileSize,Mode\n")
    for i, (w, s, m) in enumerate(all_runs):
        f.write(f"{i+1},{w},{s},{m}\n")

print(f"Generated {len(all_runs)} experiments in experiment_plan.csv")
```

---

## 5. Scripts de Mesure

### 5.1 Script Principal d'Exécution

```bash
#!/bin/bash
# run_full_benchmark.sh
# Script principal pour exécuter le benchmark complet

set -e

# === CONFIGURATION ===
PROJECT_DIR="$HOME/wordcount-distributed"
RESULTS_DIR="$PROJECT_DIR/benchmark_results/$(date +%Y%m%d_%H%M%S)"
EXPERIMENT_PLAN="$PROJECT_DIR/experiment_plan.csv"

# Fichiers de test (à générer au préalable)
declare -A TEST_FILES
TEST_FILES["100MB"]="$PROJECT_DIR/testdata/test_100MB.txt"
TEST_FILES["1GB"]="$PROJECT_DIR/testdata/test_1GB.txt"
TEST_FILES["10GB"]="$PROJECT_DIR/testdata/test_10GB.txt"

# === INITIALISATION ===
mkdir -p "$RESULTS_DIR"

# Enregistrer les métadonnées
cat > "$RESULTS_DIR/metadata.txt" << EOF
Date: $(date)
Git SHA: $(git -C $PROJECT_DIR rev-parse HEAD)
Git Branch: $(git -C $PROJECT_DIR branch --show-current)
Nodes: $(cat $OAR_NODEFILE | sort -u | tr '\n' ',')
Java Version: $(java -version 2>&1 | head -1)
Kernel: $(uname -r)
EOF

# === FICHIER DE RÉSULTATS PRINCIPAL ===
RESULTS_CSV="$RESULTS_DIR/results.csv"
echo "RunID,Workers,FileSize,Mode,T_init_ms,T_split_ms,T_dist_ms,T_calc_ms,T_agg_ms,T_total_ms,Valid" > "$RESULTS_CSV"

# === EXÉCUTION ===
# Lire le plan d'expérience (ignorer l'en-tête)
tail -n +2 "$EXPERIMENT_PLAN" | while IFS=',' read -r run_id workers file_size mode; do
    echo "=== Run $run_id: workers=$workers, size=$file_size, mode=$mode ==="

    # Sélectionner les workers
    WORKER_LIST=$(cat $OAR_NODEFILE | sort -u | tail -n +2 | head -n $workers | tr '\n' ',' | sed 's/,$//')

    # Fichier d'entrée
    INPUT_FILE="${TEST_FILES[$file_size]}"

    # Attendre entre les runs
    sleep 10

    # Exécuter avec timestamps
    OUTPUT=$("$PROJECT_DIR/run_with_timestamps.sh" "$INPUT_FILE" "$WORKER_LIST" "$mode" 2>&1)

    # Parser les résultats
    T_init=$(echo "$OUTPUT" | grep "T_init:" | cut -d: -f2)
    T_split=$(echo "$OUTPUT" | grep "T_split:" | cut -d: -f2)
    T_dist=$(echo "$OUTPUT" | grep "T_dist:" | cut -d: -f2)
    T_calc=$(echo "$OUTPUT" | grep "T_calc:" | cut -d: -f2)
    T_agg=$(echo "$OUTPUT" | grep "T_agg:" | cut -d: -f2)
    T_total=$(echo "$OUTPUT" | grep "T_total:" | cut -d: -f2)

    # Valider le résultat
    VALID="true"
    # (Ajouter votre logique de validation ici)

    # Enregistrer
    echo "$run_id,$workers,$file_size,$mode,$T_init,$T_split,$T_dist,$T_calc,$T_agg,$T_total,$VALID" >> "$RESULTS_CSV"

done

echo "Benchmark complete. Results in $RESULTS_DIR"
```

### 5.2 Script avec Timestamps Internes

```bash
#!/bin/bash
# run_with_timestamps.sh
# Exécute le système avec mesures de temps détaillées

INPUT_FILE=$1
WORKER_LIST=$2
MODE=$3

PROJECT_DIR="$HOME/wordcount-distributed"
cd "$PROJECT_DIR"

# Compiler si nécessaire
javac -d bin -sourcepath src src/scheduler/Main.java 2>/dev/null

# Timestamp global
T_START=$(date +%s.%N)

# === PHASE 1 : INITIALISATION ===
T_INIT_START=$(date +%s.%N)

# Démarrer les workers
IFS=',' read -ra WORKERS <<< "$WORKER_LIST"
for worker in "${WORKERS[@]}"; do
    ssh "$worker" "java -cp $PROJECT_DIR/bin network.worker.WorkerNode $worker 3000" &
done

# Attendre que tous les workers soient prêts
for worker in "${WORKERS[@]}"; do
    while ! java -cp bin benchmark.CheckWorkerReady "$worker:3000" 2>/dev/null; do
        sleep 0.1
    done
done

T_INIT_END=$(date +%s.%N)
T_INIT=$(echo "($T_INIT_END - $T_INIT_START) * 1000" | bc)

# === PHASE 2 : DÉCOUPAGE ===
T_SPLIT_START=$(date +%s.%N)

NUM_WORKERS=${#WORKERS[@]}
java -cp bin utils.FileSplitter "$INPUT_FILE" "$NUM_WORKERS"

T_SPLIT_END=$(date +%s.%N)
T_SPLIT=$(echo "($T_SPLIT_END - $T_SPLIT_START) * 1000" | bc)

# === PHASE 3 : DISTRIBUTION ===
T_DIST_START=$(date +%s.%N)

if [ "$MODE" == "SCP" ]; then
    i=0
    for worker in "${WORKERS[@]}"; do
        scp "${INPUT_FILE}.part_$i" "$worker:/tmp/partition_$i" &
        ((i++))
    done
    wait
elif [ "$MODE" == "NFS" ]; then
    # NFS : pas de copie nécessaire
    echo "NFS mode: no copy needed"
fi

T_DIST_END=$(date +%s.%N)
T_DIST=$(echo "($T_DIST_END - $T_DIST_START) * 1000" | bc)

# === PHASE 4 : CALCUL ===
T_CALC_START=$(date +%s.%N)

# Exécuter le wordcount sur chaque worker
PIDS=()
i=0
for worker in "${WORKERS[@]}"; do
    java -cp bin network.master.MasterCoordinator \
        "$worker:3000" \
        "cat /tmp/partition_$i | tr ' ' '\n' | sort | uniq -c" \
        > "/tmp/result_$i.txt" &
    PIDS+=($!)
    ((i++))
done

# Attendre tous les workers
for pid in "${PIDS[@]}"; do
    wait $pid
done

T_CALC_END=$(date +%s.%N)
T_CALC=$(echo "($T_CALC_END - $T_CALC_START) * 1000" | bc)

# === PHASE 5 : AGRÉGATION ===
T_AGG_START=$(date +%s.%N)

# Fusionner et re-trier
cat /tmp/result_*.txt | awk '{
    counts[$2] += $1
} END {
    for (word in counts) print counts[word], word
}' | sort -rn > output.txt

T_AGG_END=$(date +%s.%N)
T_AGG=$(echo "($T_AGG_END - $T_AGG_START) * 1000" | bc)

# === TEMPS TOTAL ===
T_END=$(date +%s.%N)
T_TOTAL=$(echo "($T_END - $T_START) * 1000" | bc)

# === OUTPUT ===
echo "T_init:$T_INIT"
echo "T_split:$T_SPLIT"
echo "T_dist:$T_DIST"
echo "T_calc:$T_CALC"
echo "T_agg:$T_AGG"
echo "T_total:$T_TOTAL"

# Nettoyage
for worker in "${WORKERS[@]}"; do
    ssh "$worker" "pkill -f WorkerNode" 2>/dev/null || true
done
```

---

## 6. Analyse Statistique

### 6.1 Script d'Analyse Python

```python
#!/usr/bin/env python3
"""
analyze_results.py
Analyse statistique des résultats de benchmark
"""

import pandas as pd
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt
import seaborn as sns

def load_data(csv_file):
    """Charger et nettoyer les données."""
    df = pd.read_csv(csv_file)
    # Filtrer les runs invalides
    df = df[df['Valid'] == True]
    return df

def compute_statistics(df, groupby_cols, value_col):
    """
    Calculer les statistiques descriptives avec intervalles de confiance.

    Intervalle de confiance à 95% : x̄ ± 1.96 × (σ / √n)
    """
    stats_df = df.groupby(groupby_cols)[value_col].agg([
        ('mean', 'mean'),
        ('std', 'std'),
        ('count', 'count'),
        ('min', 'min'),
        ('max', 'max'),
        ('median', 'median')
    ]).reset_index()

    # Intervalle de confiance 95%
    stats_df['ci95'] = 1.96 * stats_df['std'] / np.sqrt(stats_df['count'])
    stats_df['ci_lower'] = stats_df['mean'] - stats_df['ci95']
    stats_df['ci_upper'] = stats_df['mean'] + stats_df['ci95']

    return stats_df

def compute_speedup_efficiency(df):
    """Calculer speedup et efficacité."""
    # Grouper par configuration
    grouped = df.groupby(['FileSize', 'Mode', 'Workers'])['T_total_ms'].mean().reset_index()

    results = []
    for (size, mode), group in grouped.groupby(['FileSize', 'Mode']):
        # Temps séquentiel (1 worker)
        t1 = group[group['Workers'] == 1]['T_total_ms'].values
        if len(t1) == 0:
            continue
        t1 = t1[0]

        for _, row in group.iterrows():
            n = row['Workers']
            tn = row['T_total_ms']
            speedup = t1 / tn
            efficiency = speedup / n

            results.append({
                'FileSize': size,
                'Mode': mode,
                'Workers': n,
                'T_total_ms': tn,
                'Speedup': speedup,
                'Efficiency': efficiency
            })

    return pd.DataFrame(results)

def plot_execution_time(stats_df, output_file):
    """Tracer le temps d'exécution avec barres d'erreur."""
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    for i, size in enumerate(stats_df['FileSize'].unique()):
        ax = axes[i]
        data = stats_df[stats_df['FileSize'] == size]

        for mode in ['SCP', 'NFS']:
            mode_data = data[data['Mode'] == mode]
            ax.errorbar(
                mode_data['Workers'],
                mode_data['mean'],
                yerr=mode_data['ci95'],
                marker='o',
                capsize=5,
                label=mode
            )

        ax.set_xlabel('Nombre de workers')
        ax.set_ylabel('Temps d\'exécution (ms)')
        ax.set_title(f'Fichier {size}')
        ax.set_xscale('log', base=2)
        ax.legend()
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()

def plot_speedup(perf_df, output_file):
    """Tracer le speedup avec ligne idéale."""
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    for i, size in enumerate(perf_df['FileSize'].unique()):
        ax = axes[i]
        data = perf_df[perf_df['FileSize'] == size]

        # Ligne idéale
        workers = sorted(data['Workers'].unique())
        ax.plot(workers, workers, 'k--', label='Speedup idéal', alpha=0.5)

        for mode in ['SCP', 'NFS']:
            mode_data = data[data['Mode'] == mode]
            ax.plot(
                mode_data['Workers'],
                mode_data['Speedup'],
                marker='o',
                label=f'{mode}'
            )

        ax.set_xlabel('Nombre de workers')
        ax.set_ylabel('Speedup')
        ax.set_title(f'Fichier {size}')
        ax.set_xscale('log', base=2)
        ax.set_yscale('log', base=2)
        ax.legend()
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()

def plot_efficiency(perf_df, output_file):
    """Tracer l'efficacité."""
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    for i, size in enumerate(perf_df['FileSize'].unique()):
        ax = axes[i]
        data = perf_df[perf_df['FileSize'] == size]

        # Ligne idéale
        ax.axhline(y=1.0, color='k', linestyle='--', label='Efficacité idéale', alpha=0.5)

        for mode in ['SCP', 'NFS']:
            mode_data = data[data['Mode'] == mode]
            ax.plot(
                mode_data['Workers'],
                mode_data['Efficiency'],
                marker='o',
                label=f'{mode}'
            )

        ax.set_xlabel('Nombre de workers')
        ax.set_ylabel('Efficacité')
        ax.set_title(f'Fichier {size}')
        ax.set_xscale('log', base=2)
        ax.set_ylim(0, 1.1)
        ax.legend()
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()

def plot_time_breakdown(df, output_file):
    """Tracer la décomposition du temps par phase."""
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))

    # Moyennes par configuration
    grouped = df.groupby(['Workers', 'Mode']).agg({
        'T_init_ms': 'mean',
        'T_split_ms': 'mean',
        'T_dist_ms': 'mean',
        'T_calc_ms': 'mean',
        'T_agg_ms': 'mean'
    }).reset_index()

    phases = ['T_init_ms', 'T_split_ms', 'T_dist_ms', 'T_calc_ms', 'T_agg_ms']
    phase_names = ['Init', 'Split', 'Distribution', 'Calcul', 'Agrégation']
    colors = plt.cm.Set2(np.linspace(0, 1, len(phases)))

    for idx, mode in enumerate(['SCP', 'NFS']):
        ax = axes[idx // 2, idx % 2]
        mode_data = grouped[grouped['Mode'] == mode]

        bottom = np.zeros(len(mode_data))
        for phase, name, color in zip(phases, phase_names, colors):
            ax.bar(
                range(len(mode_data)),
                mode_data[phase],
                bottom=bottom,
                label=name,
                color=color
            )
            bottom += mode_data[phase].values

        ax.set_xticks(range(len(mode_data)))
        ax.set_xticklabels(mode_data['Workers'])
        ax.set_xlabel('Nombre de workers')
        ax.set_ylabel('Temps (ms)')
        ax.set_title(f'Décomposition temporelle - Mode {mode}')
        ax.legend()

    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()

def main():
    # Charger les données
    df = load_data('benchmark_results/results.csv')

    # Statistiques descriptives
    stats_df = compute_statistics(df, ['FileSize', 'Mode', 'Workers'], 'T_total_ms')
    stats_df.to_csv('benchmark_results/statistics.csv', index=False)

    # Speedup et efficacité
    perf_df = compute_speedup_efficiency(df)
    perf_df.to_csv('benchmark_results/performance_metrics.csv', index=False)

    # Graphiques
    plot_execution_time(stats_df, 'benchmark_results/execution_time.png')
    plot_speedup(perf_df, 'benchmark_results/speedup.png')
    plot_efficiency(perf_df, 'benchmark_results/efficiency.png')
    plot_time_breakdown(df, 'benchmark_results/time_breakdown.png')

    print("Analysis complete. Results in benchmark_results/")

if __name__ == "__main__":
    main()
```

### 6.2 Tests Statistiques

```python
# statistical_tests.py
"""
Tests statistiques pour valider les résultats
"""

from scipy import stats
import pandas as pd

def test_normality(data, alpha=0.05):
    """
    Test de normalité de Shapiro-Wilk.
    H0: Les données suivent une distribution normale.
    """
    stat, p_value = stats.shapiro(data)
    is_normal = p_value > alpha
    return {
        'test': 'Shapiro-Wilk',
        'statistic': stat,
        'p_value': p_value,
        'is_normal': is_normal
    }

def test_variance_homogeneity(groups, alpha=0.05):
    """
    Test de Levene pour l'homogénéité des variances.
    H0: Les variances sont égales entre les groupes.
    """
    stat, p_value = stats.levene(*groups)
    is_homogeneous = p_value > alpha
    return {
        'test': 'Levene',
        'statistic': stat,
        'p_value': p_value,
        'is_homogeneous': is_homogeneous
    }

def test_significant_difference(group1, group2, alpha=0.05):
    """
    Test t de Student pour comparer deux groupes.
    H0: Les moyennes sont égales.
    """
    # Vérifier la normalité
    norm1 = test_normality(group1)
    norm2 = test_normality(group2)

    if norm1['is_normal'] and norm2['is_normal']:
        # Test t paramétrique
        stat, p_value = stats.ttest_ind(group1, group2)
        test_name = 't-test'
    else:
        # Test de Mann-Whitney (non-paramétrique)
        stat, p_value = stats.mannwhitneyu(group1, group2)
        test_name = 'Mann-Whitney U'

    is_significant = p_value < alpha
    return {
        'test': test_name,
        'statistic': stat,
        'p_value': p_value,
        'is_significant': is_significant,
        'effect_size': (group1.mean() - group2.mean()) / group1.std()
    }

def compare_scp_vs_nfs(df):
    """Comparer statistiquement SCP vs NFS."""
    results = []

    for size in df['FileSize'].unique():
        for n in df['Workers'].unique():
            scp_data = df[(df['FileSize'] == size) &
                          (df['Workers'] == n) &
                          (df['Mode'] == 'SCP')]['T_total_ms']
            nfs_data = df[(df['FileSize'] == size) &
                          (df['Workers'] == n) &
                          (df['Mode'] == 'NFS')]['T_total_ms']

            if len(scp_data) > 0 and len(nfs_data) > 0:
                test_result = test_significant_difference(scp_data, nfs_data)
                test_result['FileSize'] = size
                test_result['Workers'] = n
                test_result['SCP_mean'] = scp_data.mean()
                test_result['NFS_mean'] = nfs_data.mean()
                results.append(test_result)

    return pd.DataFrame(results)
```

---

## 7. Modèle Théorique

### 7.1 Construction du Modèle

```python
#!/usr/bin/env python3
"""
theoretical_model.py
Modèle théorique de performance pour le système distribué
"""

import numpy as np
from dataclasses import dataclass

@dataclass
class ModelParameters:
    """Paramètres du modèle, calibrés empiriquement."""

    # Initialisation
    init_fixed_overhead: float = 1.5      # secondes (β)
    init_per_worker: float = 0.5          # secondes par worker (α)

    # Découpage fichier
    disk_bandwidth: float = 500           # MB/s

    # Distribution
    scp_latency: float = 0.3              # secondes
    scp_bandwidth: float = 400            # MB/s
    nfs_latency: float = 0.004            # secondes

    # Calcul
    wordcount_speed: float = 1_000_000    # mots/seconde
    lines_per_mb: float = 10_000          # lignes par MB
    scheduling_overhead: float = 0.5      # secondes par batch

    # Agrégation
    aggregation_time: float = 0.05        # secondes

    # RMI
    rmi_lookup_time: float = 0.1          # secondes
    rmi_call_overhead: float = 0.01       # secondes

class TheoreticalModel:
    """
    Modèle théorique basé sur la décomposition :
    T_total = T_init + T_split + T_dist + T_calc + T_agg

    Fondements académiques :
    - Graham (1969) : Borne de scheduling T ≤ Σ/m + T_max
    - LogP (Culler 1993) : Modèle de latence/bande passante
    - BSP (Valiant 1990) : Structure en super-étapes
    """

    def __init__(self, params: ModelParameters = None):
        self.params = params or ModelParameters()

    def T_init(self, n_workers: int) -> float:
        """
        Temps d'initialisation du cluster.

        Modèle : T_init = α × n + β

        Justification : Chaque worker nécessite une connexion SSH,
        le démarrage d'une JVM, et la création d'un registry RMI.
        """
        return (self.params.init_fixed_overhead +
                self.params.init_per_worker * n_workers)

    def T_split(self, file_size_mb: float) -> float:
        """
        Temps de découpage du fichier.

        Modèle : T_split = S / BW_disk

        Justification : Opération I/O bound, linéaire avec la taille.
        """
        return file_size_mb / self.params.disk_bandwidth

    def T_dist(self, file_size_mb: float, n_workers: int,
               mode: str = "NFS") -> float:
        """
        Temps de distribution des partitions.

        Modèle SCP (séquentiel) : T = n × (L + S/n / BW)
        Modèle NFS : T ≈ L (négligeable)

        Justification : LogP model - latence + temps de transfert.
        """
        if mode.upper() == "SCP":
            partition_size = file_size_mb / n_workers
            return n_workers * (self.params.scp_latency +
                               partition_size / self.params.scp_bandwidth)
        else:  # NFS
            return self.params.nfs_latency

    def T_calc(self, file_size_mb: float, n_workers: int) -> float:
        """
        Temps de calcul parallèle.

        Modèle : T_calc = (S × lines/MB × mots/ligne) / (n × vitesse) + overhead

        Borne de Graham : T ≤ Σ T_i / m + T_max
        Dans notre cas, partitions équilibrées → T ≈ T_moyen

        Justification : Le parallélisme divise le travail par n,
        plus un overhead de scheduling.
        """
        total_lines = file_size_mb * self.params.lines_per_mb
        words_estimate = total_lines * 10  # ~10 mots par ligne

        words_per_worker = words_estimate / n_workers
        T_worker = words_per_worker / self.params.wordcount_speed

        # Nombre de "rounds" RMI
        rmi_rounds = n_workers
        T_rmi = rmi_rounds * (self.params.rmi_lookup_time +
                              self.params.rmi_call_overhead)

        return T_worker + T_rmi + self.params.scheduling_overhead

    def T_agg(self) -> float:
        """
        Temps d'agrégation finale.

        Modèle : T_agg = constante

        Justification : Opération locale, indépendante de n.
        """
        return self.params.aggregation_time

    def T_total(self, file_size_mb: float, n_workers: int,
                mode: str = "NFS") -> float:
        """
        Temps total prédit.

        T_total = T_init + T_split + T_dist + T_calc + T_agg
        """
        return (self.T_init(n_workers) +
                self.T_split(file_size_mb) +
                self.T_dist(file_size_mb, n_workers, mode) +
                self.T_calc(file_size_mb, n_workers) +
                self.T_agg())

    def speedup(self, file_size_mb: float, n_workers: int,
                mode: str = "NFS") -> float:
        """
        Accélération théorique : S(n) = T(1) / T(n)
        """
        T_1 = self.T_total(file_size_mb, 1, mode)
        T_n = self.T_total(file_size_mb, n_workers, mode)
        return T_1 / T_n

    def efficiency(self, file_size_mb: float, n_workers: int,
                   mode: str = "NFS") -> float:
        """
        Efficacité théorique : E(n) = S(n) / n
        """
        return self.speedup(file_size_mb, n_workers, mode) / n_workers

def calibrate_model(measured_df):
    """
    Calibrer les paramètres du modèle à partir des mesures.

    Utilise une régression linéaire pour estimer les paramètres.
    """
    import pandas as pd
    from scipy.optimize import minimize

    def objective(params):
        """Fonction objectif : minimiser l'erreur quadratique."""
        model_params = ModelParameters(
            init_fixed_overhead=params[0],
            init_per_worker=params[1],
            scp_latency=params[2],
            scp_bandwidth=params[3],
            wordcount_speed=params[4]
        )
        model = TheoreticalModel(model_params)

        total_error = 0
        for _, row in measured_df.iterrows():
            predicted = model.T_total(
                file_size_mb=row['FileSize_MB'],
                n_workers=row['Workers'],
                mode=row['Mode']
            ) * 1000  # Convertir en ms

            actual = row['T_total_ms']
            total_error += (predicted - actual) ** 2

        return total_error

    # Valeurs initiales
    x0 = [1.5, 0.5, 0.3, 400, 1_000_000]

    # Bornes
    bounds = [
        (0.1, 10),      # init_fixed_overhead
        (0.1, 2),       # init_per_worker
        (0.1, 1),       # scp_latency
        (100, 1000),    # scp_bandwidth
        (100_000, 10_000_000)  # wordcount_speed
    ]

    result = minimize(objective, x0, bounds=bounds, method='L-BFGS-B')

    return ModelParameters(
        init_fixed_overhead=result.x[0],
        init_per_worker=result.x[1],
        scp_latency=result.x[2],
        scp_bandwidth=result.x[3],
        wordcount_speed=result.x[4]
    )
```

### 7.2 Validation du Modèle

```python
def validate_model(model, measured_df, output_dir):
    """
    Valider le modèle en comparant prédictions vs mesures.
    """
    import matplotlib.pyplot as plt

    predictions = []
    for _, row in measured_df.iterrows():
        pred = model.T_total(
            file_size_mb=row['FileSize_MB'],
            n_workers=row['Workers'],
            mode=row['Mode']
        ) * 1000  # ms

        predictions.append({
            'Workers': row['Workers'],
            'FileSize': row['FileSize'],
            'Mode': row['Mode'],
            'T_measured': row['T_total_ms'],
            'T_predicted': pred,
            'Error_pct': abs(pred - row['T_total_ms']) / row['T_total_ms'] * 100
        })

    pred_df = pd.DataFrame(predictions)

    # Statistiques d'erreur
    mae = pred_df['Error_pct'].mean()
    mape = pred_df['Error_pct'].median()
    max_error = pred_df['Error_pct'].max()

    print(f"Mean Absolute Percentage Error (MAPE): {mae:.2f}%")
    print(f"Median Error: {mape:.2f}%")
    print(f"Max Error: {max_error:.2f}%")

    # Graphique prédit vs mesuré
    fig, ax = plt.subplots(figsize=(8, 8))

    for mode in ['SCP', 'NFS']:
        mode_data = pred_df[pred_df['Mode'] == mode]
        ax.scatter(
            mode_data['T_measured'],
            mode_data['T_predicted'],
            label=mode,
            alpha=0.7
        )

    # Ligne parfaite
    max_val = max(pred_df['T_measured'].max(), pred_df['T_predicted'].max())
    ax.plot([0, max_val], [0, max_val], 'k--', label='Prédiction parfaite')

    ax.set_xlabel('Temps mesuré (ms)')
    ax.set_ylabel('Temps prédit (ms)')
    ax.set_title(f'Validation du modèle\nMAPE = {mae:.1f}%')
    ax.legend()
    ax.grid(True, alpha=0.3)

    plt.savefig(f'{output_dir}/model_validation.png', dpi=150, bbox_inches='tight')
    plt.close()

    return pred_df
```

---

## 8. Présentation des Résultats

### 8.1 Règles de Visualisation Académique

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      RÈGLES POUR LES GRAPHIQUES                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. TOUJOURS inclure les barres d'erreur (intervalles de confiance 95%)    │
│                                                                              │
│  2. ÉVITER les tableaux - préférer les graphiques                           │
│                                                                              │
│  3. ÉVITER le lissage - montrer les vraies données                          │
│                                                                              │
│  4. Utiliser des échelles logarithmiques pour les speedups                  │
│                                                                              │
│  5. Inclure une ligne de référence (speedup idéal, efficacité = 1)         │
│                                                                              │
│  6. Légendes claires et lisibles                                            │
│                                                                              │
│  7. Axes avec unités et titres                                              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 8.2 Graphiques Requis pour le Rapport

1. **Temps d'exécution vs nombre de workers** (avec barres d'erreur)
2. **Speedup vs nombre de workers** (avec ligne idéale)
3. **Efficacité vs nombre de workers** (avec seuil 100%)
4. **Décomposition temporelle** (stacked bar chart)
5. **Modèle vs mesures** (scatter plot avec ligne diagonale)
6. **Comparaison SCP vs NFS** (side-by-side)

---

## 9. Cahier de Laboratoire

### 9.1 Template pour Chaque Expérience

```org
* Expérience [NUMÉRO] - [DATE YYYY-MM-DD]

** Objectif
Description de ce que vous cherchez à mesurer/valider.

** Configuration

*** Version du code
- Git SHA: [COMMIT_HASH]
- Branche: [BRANCH_NAME]
- Modifications locales: [OUI/NON]

*** Environnement Grid'5000
- Site: [SITE]
- Cluster: [CLUSTER]
- Nœuds réservés: [NOMBRE]
- Job ID OAR: [JOB_ID]
- Walltime: [DURÉE]

*** Liste des nœuds
#+BEGIN_SRC
node1.site.grid5000.fr
node2.site.grid5000.fr
...
#+END_SRC

*** Versions logicielles
- Java: [VERSION]
- Kernel: [VERSION]
- Python (analyse): [VERSION]

** Scripts utilisés

*** Commande de réservation
#+BEGIN_SRC bash
oarsub -I -t exotic -l nodes=64,walltime=4:00:00
#+END_SRC

*** Commande d'exécution
#+BEGIN_SRC bash
./run_full_benchmark.sh
#+END_SRC

** Résultats

*** Fichiers générés
- benchmark_results/results_[TIMESTAMP].csv
- benchmark_results/statistics_[TIMESTAMP].csv

*** Observations immédiates
Notes prises pendant l'expérience.

** Problèmes rencontrés
- [PROBLÈME 1]: [DESCRIPTION] → [SOLUTION]
- [PROBLÈME 2]: [DESCRIPTION] → [SOLUTION]

** Analyse préliminaire
Premières conclusions, à affiner.

** Suivi
- [x] Données collectées
- [x] Résultats vérifiés (validation)
- [ ] Analyse statistique complète
- [ ] Intégration au rapport
```

### 9.2 Règles du Cahier de Laboratoire

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     RÈGLES D'OR DU CAHIER DE LABORATOIRE                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. NE JAMAIS MODIFIER LE PASSÉ                                             │
│     → Ajouter une correction, ne pas supprimer l'erreur                     │
│                                                                              │
│  2. TOUT DOCUMENTER IMMÉDIATEMENT                                            │
│     → Écrire pendant l'expérience, pas après                                │
│                                                                              │
│  3. INCLURE TOUS LES SCRIPTS                                                 │
│     → Copier les commandes exactes utilisées                                │
│                                                                              │
│  4. VERSIONNER LES DONNÉES                                                   │
│     → git add benchmark_results/ && git commit                              │
│                                                                              │
│  5. NOTER LES ÉCHECS                                                         │
│     → Les expériences ratées sont aussi de l'information                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Annexes

### A. Checklist Avant Chaque Session d'Expériences

```
[ ] Code compilé et testé localement
[ ] Scripts de benchmark testés avec 2-3 nœuds
[ ] Fichiers de test générés et vérifiés
[ ] Cahier de laboratoire ouvert et prêt
[ ] Réservation OAR confirmée
[ ] Espace disque suffisant pour les résultats
[ ] Connexion réseau stable
[ ] Plan d'expérience randomisé généré
```

### B. Références Académiques

1. **Graham, R.L.** (1969). "Bounds on Multiprocessing Timing Anomalies."
   SIAM Journal on Applied Mathematics, 17(2), 416-429.

2. **Amdahl, G.M.** (1967). "Validity of the single processor approach to
   achieving large scale computing capabilities." AFIPS Conference Proceedings.

3. **Gustafson, J.L.** (1988). "Reevaluating Amdahl's Law."
   Communications of the ACM, 31(5), 532-533.

4. **Culler, D. et al.** (1993). "LogP: Towards a Realistic Model of Parallel
   Computation." ACM SIGPLAN Notices, 28(7), 1-12.

5. **Valiant, L.G.** (1990). "A Bridging Model for Parallel Computation."
   Communications of the ACM, 33(8), 103-111.

6. **Jain, R.** (1991). "The Art of Computer Systems Performance Analysis."
   John Wiley & Sons. (Chapitres sur la méthodologie expérimentale)

---

*Document généré le $(date). Dernière mise à jour : voir git log.*
