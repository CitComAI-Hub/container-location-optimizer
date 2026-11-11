# Experiments of the trade-off variant

Reproduce the evaluation of the multi-objective variant (`services/pareto.py`) on the five Spanish cities of the paper
*Multi-Objective Optimization for UCO Container Placement*.

| File | What it does |
|---|---|
| `cities/<city>.json` | Area of study, current used-oil containers and candidate sites (the other containers, from the municipal open data), GHS-POP epoch |
| `common.py` | Loads a city into the service's `Problem` |
| `run.py CITY ALGORITHM OBJECTIVES CROSSOVER SEED [key=value…]` | One run (300 generations, 100 individuals, 50–150 % of today's containers): `nsga2` or `nsga3`, 3 or 4 objectives, `none`, `regional`, `uniform` or `graph` crossover, and any `ParetoParameters` (e.g. `levels=0`, `region_share=0.001,0.005`) → `results/CITY_ALGORITHM-OBJECTIVES_CROSSOVER[+key=value…]_SEED.npz` |
| `single.py CITY SEED` | The single-objective algorithm of the service at today's number of containers, for comparison |
| `moran.py CITY` | Why Moran's I was dropped as an objective (values on random layouts) |
| `analyse.py` | Hypervolume, statistics and comparison with the current layout → `results/analysis.json` |
| `analyse_revision.py` | Graph and regional crossover tuning, ablation and sensitivity runs → `revision.json` (in `REVISION_DIR`) |
| `equity_measures.py` | Robustness of the equity measure to its parameters and comparison with classical measures |
| `bounds.py` | Lagrangian lower bound and best known solution of the p-median problem at today's size (`slurm/bounds.sbatch`) |
| `stats_utils.py` | Effect size, Mann–Whitney U and Holm correction shared by the analyses |
| `link_results.sh RUNS_DIR… OUT_DIR` | Builds the input directory of `analyse.py` from the outputs of `run.py` (short names for the recombination variants) |
| `summary/` | The outputs of the analyses (`analysis.json`, `revision.json`, `bounds_*.json`, `equity_measures.json`, `single_*.json`): enough to regenerate the paper's tables with `RESULTS_DIR=summary REVISION_DIR=summary python tables.py` |
| `figures.py`, `tables.py` | Figures and LaTeX tables of the paper → `figures/` |

```console
pip install -r requirements-dev.txt pymoo matplotlib
cd experiments
for s in $(seq 1 30); do for c in donostia valladolid valencia malaga sevilla; do
  for a in nsga2 nsga3; do for o in 3 4; do for x in regional uniform; do echo "$c $a $o $x $s"
  done; done; done; done; done | xargs -P 8 -L 1 python run.py
for s in 1 2 3 4 5; do for c in donostia valladolid valencia malaga sevilla; do echo "$c $s"; done; done \
  | xargs -P 8 -L 1 python single.py
python analyse.py && python figures.py && python tables.py
```

The population is read remotely from the JRC, as the service does. To use downloaded GHS-POP tiles instead, set
`POPULATION_DIR` to the folder that holds them (`GHS_POP_E<epoch>_GLOBE_R2023A_4326_3ss_V1_0_R<row>_C<col>.tif`).
A run takes 40–120 s on one core (Donostia to Sevilla). The paper used a Slurm array with one core per run (`slurm/`); the 1,225 runs take about 30 minutes on 96 cores.

Hypervolume is computed on objectives normalised per city: containers over the allowed range, unserved people, inequity
and distance between the best and worst values of all the runs of the city (inequity from 0), reference point 1.1.
Every front is scored with three (HV3) and four objectives (HV4), to compare the formulations.

Data: containers from the open data portals of València (CC BY 4.0), Donostia, Málaga, Sevilla and Valladolid;
population GHS-POP R2023A (JRC, CC BY 4.0).

## The studies of the paper

1. Factorial: `nsga2`/`nsga3` × 3/4 objectives × `regional` (regions of 10–50 %)/`uniform` (the commands above).
2. Recombination (NSGA-II, 4 objectives): tuning on Donostia and Valencia (seeds 1–10) of `regional` with
   `region_share` from `0.001,0.005` to `0.1,0.5` and of `graph` with `graph_centres` 1/3/10 and `graph_depth` 1–20;
   then 30 runs per city of `none`, `regional region_share=0.001,0.005` and `graph graph_centres=1 graph_depth=1`, and
   `nsga2 3 none` for the formulation comparison.
3. Ablation of `nsga2 4 none`: `levels=0`, `guided_resize=False`, `quantize=False`, `local_moves=0.0`,
   `seed_current=False`.
4. Sensitivity: `nsga2 4 regional|uniform` with `cell=250.0 radius=500.0` and `cell=1000.0 radius=2000.0`.
5. `bounds.py` and `equity_measures.py`.

`analyse.py` expects the runs of studies 1–2 in one directory, the tuned and no-crossover variants named
`nsga2-4_none`, `nsga2-4_regional-small`, `nsga2-4_graph-small` and `nsga2-3_none` (links to the files of `run.py`);
`analyse_revision.py` reads the runs of studies 2–4 as `run.py` names them.

The raw runs of the paper (~190 MB of `.npz`) are not in git: they are on the VRAIN cluster under
`~/container-location/` (`results/`, `results_rev/`, `results_all/`), listed in [RESEARCH.md](../RESEARCH.md#raw-data-not-in-git).
To analyse them locally, copy them (`rsync -a vrhpcadm1.dsic.upv.es:container-location/results_all/ …`, with
`-L` to follow the links) and run `analyse.py`, `analyse_revision.py` and `figures.py` with `RESULTS_DIR` and
`REVISION_DIR` pointing to them.
