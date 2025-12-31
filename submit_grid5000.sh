#!/bin/bash
# =============================================================================
# Script de soumission pour Grid'5000
# Lance les mesures en mode batch (non-interactif)
# =============================================================================

# Configuration
WALLTIME="1:00:00"
NODES=1
PROJECT_DIR="$HOME/wordcount-distributed"  # ADAPTEZ CE CHEMIN

echo "=== Soumission du job de mesure sur Grid'5000 ==="
echo ""
echo "Configuration:"
echo "  • Walltime: $WALLTIME"
echo "  • Nodes: $NODES"
echo "  • Répertoire: $PROJECT_DIR"
echo ""

# Vérifier le répertoire
if [[ ! -d "$PROJECT_DIR" ]]; then
    echo "ERREUR: Répertoire $PROJECT_DIR non trouvé"
    echo "Modifiez PROJECT_DIR dans ce script"
    exit 1
fi

# Soumettre le job
oarsub -l nodes=$NODES,walltime=$WALLTIME \
       -O measurement_stdout.log \
       -E measurement_stderr.log \
       "cd $PROJECT_DIR && bash measure_grid5000.sh 3"

echo ""
echo "Job soumis! Vérifiez avec: oarstat -u"
echo "Résultats dans: measurement_stdout.log"
