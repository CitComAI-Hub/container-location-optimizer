#!/bin/bash
#SBATCH --job-name=cl-bounds
#SBATCH --cpus-per-task=1
#SBATCH --mem=6G
#SBATCH --time=10:00:00
#SBATCH --output=logs/%x-%A_%a.out
# Lagrangian p-median bounds, one city per task: sbatch --array=0-4 bounds.sbatch
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export POPULATION_DIR=$HOME/container-location/ghs CACHE_DIR=$HOME/container-location/cache
export RESULTS_DIR=$HOME/container-location/results ITERATIONS=${ITERATIONS:-20000}
cities=(donostia valladolid valencia malaga sevilla)
export CITY=${cities[$SLURM_ARRAY_TASK_ID]}
source "$HOME/envs/container-location/bin/activate"
cd "$HOME/container-location/code/experiments"
srun python bounds.py
