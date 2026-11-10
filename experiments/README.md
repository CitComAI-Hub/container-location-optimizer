# Experiments of the trade-off variant

Reproduce the evaluation of the multi-objective variant (`services/pareto.py`) on the five Spanish cities of the paper
*Multi-Objective Optimization for UCO Container Placement*.

| File | What it does |
|---|---|
| `cities/<city>.json` | Area of study, current used-oil containers and candidate sites (the other containers, from the municipal open data), GHS-POP epoch |
| `common.py` | Loads a city into the service's `Problem` |
| `run.py CITY CROSSOVER SEED` | One run (300 generations, 100 individuals, 50–150 % of today's containers) with `regional` or `uniform` crossover → `results/CITY_CROSSOVER_SEED.npz` |
| `single.py CITY SEED` | The single-objective algorithm of the service at today's number of containers, for comparison |
| `moran.py CITY` | Why Moran's I was dropped as an objective (values on random layouts) |
| `analyse.py` | Hypervolume, statistics and comparison with the current layout → `results/analysis.json` |
| `figures.py` | Figures of the paper → `figures/` |

```console
pip install -r requirements-dev.txt pymoo matplotlib
cd experiments
for s in $(seq 1 30); do for c in donostia valladolid valencia malaga sevilla; do
  for x in regional uniform; do echo "$c $x $s"; done; done; done | xargs -P 8 -L 1 python run.py
for s in 1 2 3 4 5; do for c in donostia valladolid valencia malaga sevilla; do echo "$c $s"; done; done \
  | xargs -P 8 -L 1 python single.py
python analyse.py && python figures.py
```

The population is read remotely from the JRC, as the service does. To use downloaded GHS-POP tiles instead, set
`POPULATION_DIR` to the folder that holds them (`GHS_POP_E<epoch>_GLOBE_R2023A_4326_3ss_V1_0_R<row>_C<col>.tif`).
A run takes 1–3 minutes on one core (Donostia to Sevilla); the 300 runs take about 4 hours on 16 cores.

Hypervolume is computed on objectives normalised per city: containers over the allowed range, unserved people and
inequity between the best and worst values of all the runs of the city (inequity from 0), reference point 1.1.

Data: containers from the open data portals of València (CC BY 4.0), Donostia, Málaga, Sevilla and Valladolid;
population GHS-POP R2023A (JRC, CC BY 4.0).
