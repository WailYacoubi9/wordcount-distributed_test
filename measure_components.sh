#!/bin/bash
# =============================================================================
# Script de mesure des composantes du Makefile distribué
# Projet Grenoble INP - Ensimag
#
# Ce script mesure individuellement chaque étape pour calibrer
# le modèle d'Amdahl avec des données réelles.
# =============================================================================

set -e

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Fichier de résultats
RESULTS_FILE="measured_times.txt"

# Nombre de répétitions pour moyenner
REPETITIONS=${1:-3}

echo -e "${BLUE}=============================================================================${NC}"
echo -e "${BLUE}     MESURE DES COMPOSANTES DU MAKEFILE DISTRIBUÉ${NC}"
echo -e "${BLUE}=============================================================================${NC}"
echo ""
echo -e "Répétitions par mesure: ${YELLOW}$REPETITIONS${NC}"
echo ""

# =============================================================================
# Fonctions utilitaires
# =============================================================================

# Fonction pour mesurer le temps d'exécution (en secondes avec décimales)
measure_time() {
    local start=$(date +%s.%N)
    eval "$1" > /dev/null 2>&1
    local end=$(date +%s.%N)
    echo "$end - $start" | bc
}

# Fonction pour calculer la moyenne
average() {
    local sum=0
    local count=0
    for val in "$@"; do
        sum=$(echo "$sum + $val" | bc)
        count=$((count + 1))
    done
    echo "scale=2; $sum / $count" | bc
}

# Fonction pour nettoyer avant chaque test
clean_build() {
    make clean > /dev/null 2>&1 || true
}

# =============================================================================
# ÉTAPE 1: Mesurer T_compile (compilation)
# =============================================================================

echo -e "${GREEN}[1/5] Mesure de T_compile (compilation)...${NC}"

compile_times=()
for i in $(seq 1 $REPETITIONS); do
    clean_build
    t=$(measure_time "make compile")
    compile_times+=($t)
    echo "  Run $i: ${t}s"
done

T_COMPILE=$(average "${compile_times[@]}")
echo -e "  ${YELLOW}→ T_compile = ${T_COMPILE}s${NC}"
echo ""

# =============================================================================
# ÉTAPE 2: Mesurer T_split (découpage)
# =============================================================================

echo -e "${GREEN}[2/5] Mesure de T_split (découpage en chunks)...${NC}"

split_times=()
for i in $(seq 1 $REPETITIONS); do
    clean_build
    make compile > /dev/null 2>&1  # Prérequis
    t=$(measure_time "make split")
    split_times+=($t)
    echo "  Run $i: ${t}s"
done

T_SPLIT=$(average "${split_times[@]}")
echo -e "  ${YELLOW}→ T_split = ${T_SPLIT}s${NC}"
echo ""

# =============================================================================
# ÉTAPE 3: Mesurer T_task (une tâche parallèle)
# =============================================================================

echo -e "${GREEN}[3/5] Mesure de T_task (une tâche listX.txt)...${NC}"

task_times=()
for i in $(seq 1 $REPETITIONS); do
    clean_build
    make compile > /dev/null 2>&1
    make split > /dev/null 2>&1
    # Mesurer une seule tâche (list1.txt par exemple)
    t=$(measure_time "make list1.txt")
    task_times+=($t)
    echo "  Run $i: ${t}s"
done

T_TASK=$(average "${task_times[@]}")
echo -e "  ${YELLOW}→ T_task = ${T_TASK}s (pour 1 tâche)${NC}"
echo ""

# =============================================================================
# ÉTAPE 4: Mesurer T_merge (fusion)
# =============================================================================

echo -e "${GREEN}[4/5] Mesure de T_merge (fusion des résultats)...${NC}"

merge_times=()
for i in $(seq 1 $REPETITIONS); do
    clean_build
    make compile > /dev/null 2>&1
    make split > /dev/null 2>&1
    # Exécuter toutes les tâches parallèles d'abord
    for j in $(seq 1 20); do
        make list${j}.txt > /dev/null 2>&1 || true
    done
    # Maintenant mesurer le merge
    t=$(measure_time "make list.txt")
    merge_times+=($t)
    echo "  Run $i: ${t}s"
done

T_MERGE=$(average "${merge_times[@]}")
echo -e "  ${YELLOW}→ T_merge = ${T_MERGE}s${NC}"
echo ""

# =============================================================================
# ÉTAPE 5: Mesurer toutes les tâches parallèles (séquentiellement)
# =============================================================================

echo -e "${GREEN}[5/5] Mesure de T_par (20 tâches en séquentiel)...${NC}"

par_times=()
for i in $(seq 1 $REPETITIONS); do
    clean_build
    make compile > /dev/null 2>&1
    make split > /dev/null 2>&1

    # Mesurer les 20 tâches une par une
    start=$(date +%s.%N)
    for j in $(seq 1 20); do
        make list${j}.txt > /dev/null 2>&1 || true
    done
    end=$(date +%s.%N)
    t=$(echo "$end - $start" | bc)

    par_times+=($t)
    echo "  Run $i: ${t}s"
done

T_PAR=$(average "${par_times[@]}")
echo -e "  ${YELLOW}→ T_par = ${T_PAR}s (20 tâches séquentielles)${NC}"
echo ""

# =============================================================================
# RÉSUMÉ ET CALCULS
# =============================================================================

T_SEQ=$(echo "$T_COMPILE + $T_SPLIT + $T_MERGE" | bc)
T_TOTAL_1=$(echo "$T_SEQ + $T_PAR" | bc)

echo -e "${BLUE}=============================================================================${NC}"
echo -e "${BLUE}                         RÉSULTATS MESURÉS${NC}"
echo -e "${BLUE}=============================================================================${NC}"
echo ""
echo -e "  ${GREEN}Composantes séquentielles:${NC}"
echo -e "    • T_compile = ${YELLOW}${T_COMPILE}s${NC}"
echo -e "    • T_split   = ${YELLOW}${T_SPLIT}s${NC}"
echo -e "    • T_merge   = ${YELLOW}${T_MERGE}s${NC}"
echo -e "    ─────────────────────────"
echo -e "    • T_seq     = ${YELLOW}${T_SEQ}s${NC}"
echo ""
echo -e "  ${GREEN}Composantes parallèles:${NC}"
echo -e "    • T_task    = ${YELLOW}${T_TASK}s${NC} (1 tâche)"
echo -e "    • T_par     = ${YELLOW}${T_PAR}s${NC} (20 tâches)"
echo ""
echo -e "  ${GREEN}Temps total théorique (N=1):${NC}"
echo -e "    • T(1)      = ${YELLOW}${T_TOTAL_1}s${NC}"
echo ""
echo -e "${BLUE}=============================================================================${NC}"
echo ""

# =============================================================================
# EXPORT DES RÉSULTATS
# =============================================================================

cat > $RESULTS_FILE << EOF
# Mesures des composantes du Makefile distribué
# Généré le $(date)
# Répétitions: $REPETITIONS

T_COMPILE=$T_COMPILE
T_SPLIT=$T_SPLIT
T_MERGE=$T_MERGE
T_SEQ=$T_SEQ
T_TASK=$T_TASK
T_PAR=$T_PAR
T_TOTAL_1=$T_TOTAL_1
EOF

echo -e "Résultats sauvegardés dans: ${GREEN}$RESULTS_FILE${NC}"
echo ""
echo -e "${YELLOW}Utilisez ces valeurs dans le script Python:${NC}"
echo ""
echo "  T_seq = $T_SEQ   # Temps séquentiel mesuré"
echo "  T_par = $T_PAR   # Temps parallèle mesuré"
echo ""
