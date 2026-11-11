#!/bin/sh
# Builds the directory that analyse.py expects (factorial + recombination
# variants with short names) from the outputs of run.py, with symbolic links.
#   sh link_results.sh RUNS_DIR [RUNS_DIR...] OUT_DIR
# e.g. on the cluster: sh link_results.sh results results_rev results_all
set -eu
out=$(eval echo "\${$#}")
mkdir -p "$out"
while [ $# -gt 1 ]; do
  src=$(cd "$1" && pwd); shift
  for f in "$src"/*.npz "$src"/single_*.json "$src"/bounds_*.json; do
    [ -e "$f" ] || continue
    name=$(basename "$f")
    case "$name" in
      *_nsga2-4_regional+crossover_rate=0.0_*) new=$(echo "$name" | sed 's/regional+crossover_rate=0.0/none/') ;;
      *_nsga2-3_none_*) new=$name ;;
      *_nsga2-4_regional+region_share=0.001,0.005_*) new=$(echo "$name" | sed 's/regional+region_share=0.001,0.005/regional-small/') ;;
      *_nsga2-4_graph+graph_centres=1+graph_depth=1_*) new=$(echo "$name" | sed 's/graph+graph_centres=1+graph_depth=1/graph-small/') ;;
      *+*) continue ;;  # other revision runs: analyse_revision.py reads them in place
      *) new=$name ;;
    esac
    ln -sf "$f" "$out/$new"
  done
done
echo "$(ls "$out" | wc -l) files in $out"
