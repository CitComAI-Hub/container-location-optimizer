# Running the experiments with Slurm

One core per run. On the cluster, with the repository in `$HOME/container-location/code`, the environment in
`$HOME/envs/container-location` and the GHS-POP tiles in `$HOME/container-location/ghs` (compute nodes may have no
internet):

```console
cd $HOME/container-location && mkdir -p logs
(for s in $(seq 1 30); do for c in donostia valladolid valencia malaga sevilla; do
   for x in regional uniform; do echo "run.py $c $x $s"; done; done; done
 for s in 1 2 3 4 5; do for c in donostia valladolid valencia malaga sevilla; do echo "single.py $c $s"; done; done
) > tasks.txt
sbatch --array=0-324%64 code/experiments/slurm/job.sbatch tasks.txt
```

Results land in `$HOME/container-location/results`; copy them back and run `analyse.py`, `figures.py` and `tables.py`
with `RESULTS_DIR` pointing to them.
