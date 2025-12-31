#!/bin/bash
# =============================================================================
# Script de mesure sur Grid'5000
# Projet GNU Make Distribué - Grenoble INP Ensimag
# =============================================================================

set -e

# Couleurs
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

# Configuration
REPETITIONS=${1:-3}
MAKEFILE_DIR=${2:-.}
RESULTS_FILE="grid5000_measurements.txt"

echo -e "${BLUE}=============================================================================${NC}"
echo -e "${BLUE}     MESURE DES COMPOSANTES - GRID'5000${NC}"
echo -e "${BLUE}=============================================================================${NC}"

# Vérifier qu'on est sur Grid'5000
if [[ ! -f /etc/grid5000/hostname ]]; then
    echo -e "${YELLOW}ATTENTION: Vous ne semblez pas être sur Grid'5000${NC}"
    echo "Ce script est optimisé pour Grid'5000 mais peut fonctionner ailleurs."
fi

# Afficher les infos du nœud
echo -e "\n${GREEN}Informations système:${NC}"
echo "  • Hostname: $(hostname)"
echo "  • CPU: $(grep -c processor /proc/cpuinfo) cores"
echo "  • RAM: $(free -h | awk '/^Mem:/{print $2}')"
echo "  • Date: $(date)"

# Aller dans le répertoire du Makefile
cd "$MAKEFILE_DIR"
echo -e "\n${GREEN}Répertoire de travail:${NC} $(pwd)"

# Vérifier la présence du Makefile
if [[ ! -f Makefile ]]; then
    echo -e "${RED}ERREUR: Makefile non trouvé dans $(pwd)${NC}"
    exit 1
fi

# Afficher les cibles disponibles
echo -e "\n${GREEN}Cibles du Makefile:${NC}"
grep -E "^[a-zA-Z_-]+:" Makefile | head -10 || echo "(impossible de parser)"

echo -e "\n${YELLOW}Répétitions: $REPETITIONS${NC}"
echo ""

# =============================================================================
# Fonction de mesure avec timing précis
# =============================================================================

measure() {
    local cmd="$1"
    local start=$(date +%s.%N)
    eval "$cmd" > /dev/null 2>&1 || true
    local end=$(date +%s.%N)
    echo "$end - $start" | bc
}

average() {
    local sum=0
    local n=0
    for v in "$@"; do
        sum=$(echo "$sum + $v" | bc)
        n=$((n + 1))
    done
    echo "scale=3; $sum / $n" | bc
}

# =============================================================================
# MESURES
# =============================================================================

declare -A RESULTS

# --- T_compile ---
echo -e "${GREEN}[1/5] Mesure T_compile...${NC}"
times=()
for i in $(seq 1 $REPETITIONS); do
    make clean > /dev/null 2>&1 || true
    t=$(measure "make compile")
    times+=($t)
    echo "  Run $i: ${t}s"
done
RESULTS[T_compile]=$(average "${times[@]}")
echo -e "  ${YELLOW}→ T_compile = ${RESULTS[T_compile]}s${NC}\n"

# --- T_split ---
echo -e "${GREEN}[2/5] Mesure T_split...${NC}"
times=()
for i in $(seq 1 $REPETITIONS); do
    make clean > /dev/null 2>&1 || true
    make compile > /dev/null 2>&1
    t=$(measure "make split")
    times+=($t)
    echo "  Run $i: ${t}s"
done
RESULTS[T_split]=$(average "${times[@]}")
echo -e "  ${YELLOW}→ T_split = ${RESULTS[T_split]}s${NC}\n"

# --- T_task (une tâche) ---
echo -e "${GREEN}[3/5] Mesure T_task (list1.txt)...${NC}"
times=()
for i in $(seq 1 $REPETITIONS); do
    make clean > /dev/null 2>&1 || true
    make compile > /dev/null 2>&1
    make split > /dev/null 2>&1
    t=$(measure "make list1.txt")
    times+=($t)
    echo "  Run $i: ${t}s"
done
RESULTS[T_task]=$(average "${times[@]}")
echo -e "  ${YELLOW}→ T_task = ${RESULTS[T_task]}s${NC}\n"

# --- T_merge ---
echo -e "${GREEN}[4/5] Mesure T_merge (list.txt)...${NC}"
times=()
for i in $(seq 1 $REPETITIONS); do
    make clean > /dev/null 2>&1 || true
    make compile > /dev/null 2>&1
    make split > /dev/null 2>&1
    # Exécuter toutes les tâches parallèles
    for j in $(seq 1 20); do
        make list${j}.txt > /dev/null 2>&1 || true
    done
    t=$(measure "make list.txt")
    times+=($t)
    echo "  Run $i: ${t}s"
done
RESULTS[T_merge]=$(average "${times[@]}")
echo -e "  ${YELLOW}→ T_merge = ${RESULTS[T_merge]}s${NC}\n"

# --- T_par (20 tâches séquentielles) ---
echo -e "${GREEN}[5/5] Mesure T_par (20 tâches)...${NC}"
times=()
for i in $(seq 1 $REPETITIONS); do
    make clean > /dev/null 2>&1 || true
    make compile > /dev/null 2>&1
    make split > /dev/null 2>&1

    start=$(date +%s.%N)
    for j in $(seq 1 20); do
        make list${j}.txt > /dev/null 2>&1 || true
    done
    end=$(date +%s.%N)
    t=$(echo "$end - $start" | bc)

    times+=($t)
    echo "  Run $i: ${t}s"
done
RESULTS[T_par]=$(average "${times[@]}")
echo -e "  ${YELLOW}→ T_par = ${RESULTS[T_par]}s${NC}\n"

# =============================================================================
# CALCULS ET RÉSUMÉ
# =============================================================================

T_seq=$(echo "${RESULTS[T_compile]} + ${RESULTS[T_split]} + ${RESULTS[T_merge]}" | bc)
T_total=$(echo "$T_seq + ${RESULTS[T_par]}" | bc)

echo -e "${BLUE}=============================================================================${NC}"
echo -e "${BLUE}                    RÉSULTATS GRID'5000${NC}"
echo -e "${BLUE}=============================================================================${NC}"
echo ""
echo -e "  ${GREEN}Composantes séquentielles:${NC}"
echo -e "    • T_compile = ${YELLOW}${RESULTS[T_compile]}s${NC}"
echo -e "    • T_split   = ${YELLOW}${RESULTS[T_split]}s${NC}"
echo -e "    • T_merge   = ${YELLOW}${RESULTS[T_merge]}s${NC}"
echo -e "    ────────────────────────────"
echo -e "    • T_seq     = ${YELLOW}${T_seq}s${NC}"
echo ""
echo -e "  ${GREEN}Composantes parallèles:${NC}"
echo -e "    • T_task    = ${YELLOW}${RESULTS[T_task]}s${NC} (1 tâche)"
echo -e "    • T_par     = ${YELLOW}${RESULTS[T_par]}s${NC} (20 tâches)"
echo ""
echo -e "  ${GREEN}Temps total (N=1):${NC}"
echo -e "    • T(1)      = ${YELLOW}${T_total}s${NC}"
echo ""

# Fraction parallèle
f_par=$(echo "scale=4; ${RESULTS[T_par]} / $T_total" | bc)
echo -e "  ${GREEN}Fraction parallèle:${NC} ${YELLOW}${f_par}${NC} ($(echo "scale=1; $f_par * 100" | bc)%)"
echo ""

# =============================================================================
# EXPORT
# =============================================================================

cat > "$RESULTS_FILE" << EOF
# Mesures Grid'5000
# Date: $(date)
# Host: $(hostname)
# Répétitions: $REPETITIONS

T_COMPILE=${RESULTS[T_compile]}
T_SPLIT=${RESULTS[T_split]}
T_MERGE=${RESULTS[T_merge]}
T_SEQ=${T_seq}
T_TASK=${RESULTS[T_task]}
T_PAR=${RESULTS[T_par]}
T_TOTAL_1=${T_total}
FRACTION_PAR=${f_par}
EOF

echo -e "Résultats sauvegardés: ${GREEN}$RESULTS_FILE${NC}"
echo ""

# Formule à utiliser
echo -e "${BLUE}=============================================================================${NC}"
echo -e "${BLUE}  PARAMÈTRES POUR LE MODÈLE D'AMDAHL${NC}"
echo -e "${BLUE}=============================================================================${NC}"
echo ""
echo "  Utilisez ces valeurs dans amdahl_analysis.py:"
echo ""
echo "  T_seq = ${T_seq}    # Mesuré (compile + split + merge)"
echo "  T_par = ${RESULTS[T_par]}   # Mesuré (20 tâches)"
echo "  # C = à calibrer par régression sur vos données multi-workers"
echo ""
