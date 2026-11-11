# Running the experiments with Slurm

One core per run. On the cluster, with the repository in `$HOME/container-location/code`, the environment in
`$HOME/envs/container-location` and the GHS-POP tiles in `$HOME/container-location/ghs` (compute nodes may have no
internet):

```console
cd $HOME/container-location && mkdir -p logs
(for s in $(seq 1 30); do for c in donostia valladolid valencia malaga sevilla; do
   for a in nsga2 nsga3; do for o in 3 4; do for x in regional uniform; do
     echo "run.py $c $a $o $x $s"; done; done; done; done; done
 for s in 1 2 3 4 5; do for c in donostia valladolid valencia malaga sevilla; do echo "single.py $c $s"; done; done
) > tasks.txt
# MaxArraySize may be ~1000: split the 1,225 lines in two files
split -n l/2 -d tasks.txt tasks- && for f in tasks-00 tasks-01; do
  sbatch --array=0-$(($(wc -l < $f) - 1))%48 code/experiments/slurm/job.sbatch $f; done
```

Results land in `$HOME/container-location/results`; copy them back and run `analyse.py`, `figures.py` and `tables.py`
with `RESULTS_DIR` pointing to them.
