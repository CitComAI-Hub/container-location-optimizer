#!/bin/bash
#SBATCH --job-name=cl-mo
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=01:00:00
#SBATCH --output=logs/%x-%A_%a.out
# Usage: sbatch --array=0-N%M job.sbatch TASKFILE   (one line per task: script and arguments)
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export POPULATION_DIR=$HOME/container-location/ghs
export CACHE_DIR=$HOME/container-location/cache
export RESULTS_DIR=$HOME/container-location/${RESULTS_SUBDIR:-results}
source "$HOME/envs/container-location/bin/activate"
cd "$HOME/container-location/code/experiments"
line=$(sed -n "$((SLURM_ARRAY_TASK_ID + 1))p" "$HOME/container-location/$1")
echo "task $SLURM_ARRAY_TASK_ID on $(hostname): $line"
srun python $line
