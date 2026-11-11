# Research notes: the trade-off (multi-objective) variant

State of the research behind the trade-off jobs, to resume the work. The service itself is described in the
[README](./README.md); how to run the experiments, in [`experiments/`](./experiments/README.md); the paper, in
[`paper/`](./paper/README.md).

## Where it comes from

- **Single-objective method**: Moreno et al., *Optimizing UCO container placement in urban environments: a genetic
  algorithm approach*, IDEAL 2024 (see [Publications](./README.md#publications)). Its code
  (`CitCom-VRAIN/optimizing-container-location`) became this service in November 2026.
- **Multi-objective draft (2025)**: the repository `multiobjective-location-problem` (local, not published) and a
  paper draft for a journal (*Multi-Objective Optimization for UCO Container Placement*, Wiley template). It used
  NSGA-III (pymoo) on binary vectors with three objectives (cost, coverage excess, Moran's I), a "boundary-focused"
  crossover and a local search. That repository is superseded by this one; its `paper/` folder is the original
  draft, and its `data/` folder has the raw open data of the five cities (copied here, compacted, to
  `experiments/cities/`).

### What was wrong with the draft (November 2026 review)

- **Moran's I was ill-posed as an objective.** With two containers it is −1 whatever the layout; an empty layout
  scored (0 cost, 0 excess, 0): the ideal point. The saved fronts of the draft contained exactly those degenerate
  solutions. On realistic layouts, with inverse-distance weights between all containers, it stays within ±0.15. It is
  scale-invariant, undefined for uniform excess, and computed on a support (the Voronoi cells) that changes with the
  solution. `experiments/moran.py` reproduces these numbers.
- **The boundary crossover was a uniform crossover.** With the tuned threshold (5.5 km), 100 % of the active genes
  were "boundary" genes. Its HV advantage came from a gentler mutation in its tuned configuration and from the
  degenerate extremes above.
- **Statistics**: 10 runs per variant, not the 30 stated; HV normalised with ad-hoc bounds.

## What is implemented

| File | What |
|---|---|
| `services/equity.py` | Spatial inequity (`f3`): population-weighted s.d. of the unserved share between 1 km neighbourhoods of a fixed 500 m grid; Moran's I of the cells as a diagnostic |
| `services/pareto.py` | The trade-off algorithm: NSGA-II on sets of sites, 4 objectives (containers, people above capacity, inequity, mean distance), 11 size levels + today's, load-guided mutation, no crossover by default. Options kept for experiments: `crossover` (`regional`, `uniform`, `graph`), `algorithm="nsga3"` (pymoo, dev dependency), 3 objectives (`distance=False`), and the ablation switches `levels`, `quantize`, `guided_resize`, `seed_current` |
| `services/problem.py` | Evaluation (nearest-neighbour on population pixels, ~2 ms), `evaluate_sites`, equity metrics of any layout |
| `services/jobs.py`, `server.py`, `static/` | Jobs of kind `pareto`, `GET /api/jobs/<id>/layouts/<n>`, front table in the UI |

Releases: v1.2 (trade-off, regional crossover) deployed on 2026-11-11; v1.3 (no crossover by default) deployed on
2026-11-11 (data space PR #31). In production (VLCi data, 158 oil containers, 8,308 candidate sites, one CPU at low
priority) a 300-generation trade-off job takes 104 s with v1.3 against 291 s with v1.2; with today's 158 containers
its front reaches 0.9 inequity points (today 7.6) and 207 m mean distance (today 379 m).

## Experiments and results

All runs on the VRAIN cluster (Slurm), one core per run, 30 runs per variant and city, five cities (Donostia,
Valladolid, Valencia, Málaga, Sevilla). 3,490 runs in total. Summary data in `experiments/summary/`, from which the
paper's tables are regenerated exactly (`tables.py`); figures need the raw runs.

| Study | Result | Paper |
|---|---|---|
| Factorial: NSGA-II/III × 3/4 objectives × regional (large regions)/uniform crossover | NSGA-III never better (NSGA-II better in 2 cases); regional beats uniform in 20/20 | Table `tab:hv` |
| Formulation (no crossover): 3 vs 4 objectives | 4 objectives cost 2.1–3.3 % of HV3, gain 5.8–22.6 % of HV4 | `tab:formulation`, `fig:tradeoff` |
| Recombination: none vs regional/graph tuned (small regions) vs large regional vs uniform | Tuned crossovers ≈ none (none better in Donostia); large regions and uniform worse; none 1.6–2.4× faster | `tab:recombination` |
| Ablation of the recommended configuration | Size levels and load-guided resize essential (HV4 −18 to −45 %); local moves and quantised `f2` significant; seeding no effect (slightly worse in Sevilla) | `tab:ablation` |
| Equity measure | `f3` robust to cell/radius (Spearman .65–.90); unrelated to non-spatial Gini; Moran's I on the fixed grid correlates (.66–.85) | `tab:equity`, `tab:sensitivity` |
| Accessibility bounds (p-median at today's size) | Lagrangian bound within 1.3–5.8 % of the best known; fair front layouts +6.0–8.4 %; single-objective GA up to +15.8 % (Valladolid) | `tab:bounds` |
| Today's layouts | Every run's front has a layout better in unserved, inequity (2–7×) and distance at once | `tab:k0`, `fig:map` |

Tuning of the crossovers (Donostia and Valencia, seeds 1–10): regional `region_share` from `0.001,0.005` to
`0.1,0.5`; graph `graph_centres` 1/3/10 × `graph_depth` 1–20. The smaller the region, the better; the chosen ones
(regional `0.001,0.005`, graph 1×1) were then run with seeds 1–30, so seeds 1–10 of the two tuning cities are shared.

### Raw data (not in git)

On the cluster (`vrhpcadm1.dsic.upv.es`, see the experiments README), under `~/container-location/`:

| Folder | Content | Slurm jobs |
|---|---|---|
| `results/` | Factorial study and single-objective runs (1,225), `analysis.json`, `bounds_<city>.json` | 170910, 170911, 173787 (bounds) |
| `results_rev/` | Revision: crossover tuning, recombination, ablations (regional and none), sensitivity, `nsga2-3_none` | 172182–3, 173707, 173792, 173893, 174373 |
| `results_all/` | Links built by `experiments/link_results.sh results results_rev results_all`: the input of `analyse.py` | |
| `results_v1/` | First 3-objective batch (superseded) | 170585 |
| `ghs/`, `cache/` | GHS-POP tiles and population cache used by the runs | |

## Partition crossover (branch `feat/partition-crossover`, 2026-11-11)

Why the earlier crossovers did not help: parents of any size were mated (11 size levels), the repair after
crossover dropped or added sites at random, and the exchanged region was chosen blindly.

- **Exact decomposition does not exist here** (`crossover="components"`, kept for the analysis): linking the
  sites that can serve each pixel in a child gives components across which count, unserved people and distance
  are exactly additive (`test_partition_components_are_additive`), but two good parents of the same size give
  a *single* component (Donostia, every size level): their Voronoi cells interlock. A GPX-style partition
  crossover (Whitley) does not transfer.
- **Proposed operator** (`crossover="partition"`, `mating="size"`): a grid of tiles at a random offset (side
  `tile` × mean spacing, default 2); each tile is taken from the parent that dominates in it on (containers,
  unserved, distance × people); ties at random, complementary in the two children; repaired by the loads.
  Same-size mating is essential.
- **Baseline**: `crossover="union"` (Alp, Erkut and Drezner 2003: union, then drop by a weighted cost).
- Moran's I is no longer computed for every evaluation (half of the evaluation time; values unchanged).

Study (NSGA-II, 4 objectives, 5 cities × 30 seeds, 1,200 runs, Slurm 175295/175296 + 176496, raw runs in
`~/container-location/results_ops/`, summary `experiments/summary/operators.json`, `analyse_operators.py`).
Time is the fair budget: the evaluation counter only counts objective evaluations, not the internal ones of
`union` or the repairs. HV4 at the median time of `partition` (41–130 s):

| City | none (300 gen) | none (1200 gen) | **partition** | union | regional + fixes |
|---|---|---|---|---|---|
| Donostia | .577 | .598 | **.626** | .611 | .584 |
| Valladolid | .414 | .425 | **.445** | .448 | .421 |
| Valencia | .483 | .505 | **.536** | .525 | .496 |
| Málaga | .571 | .607 | **.612** | .598 | .578 |
| Sevilla | .566 | .613 | **.617** | .614 | .576 |

- partition vs none with 4× generations (same time): better in 5/5 (+4.6, +4.7, +6.1, +0.8, +0.6 %;
  A12 1.00, 1.00, 1.00, 0.80, 0.74; Holm p < 0.002).
- partition vs union, same time: better in 3/5 (A12 ≥ 0.94), no difference in Valladolid and Sevilla. At the
  same number of generations union is better (−0.2 to −4.3 %), but it is 3–5× slower (132–638 s).
- Ablations: without same-size mating, +3 % over `none` instead of +7–11 % (and not better than none-1200 in
  Málaga/Sevilla); regional crossover with same-size mating and guided repair ≈ none (+1–2 %): the fitness-informed
  choice per tile is what matters. Tile side: 1 worse; 2 and 4 equivalent (4 slightly better in Valladolid/Valencia).
- Caveat: the fairest layouts of the front are less fair with partition (min inequity ≈ 2× that of none-1200);
  the tile choice ignores inequity (not additive). Gains are in the rest of the front.
- **Fair extreme** (Slurm 176505, 176807; 600 more runs): `tile_equity=True` (4th criterion per tile: squared
  deviation of the neighbourhood unserved shares from the parents' mean) lowers min inequity in 4/5 cities
  (A12 0.69–0.83) but not to none-1200's level, and HV4 is mixed (−1 % in the three smaller cities, +0.3–0.7 %
  in Málaga/Sevilla). The fair extreme needs search time: `crossover_rate=0.5` + `tile_equity` + 900
  generations (≈2× the time) matches none-1200's min inequity in every city and has the best final HV4 in
  Donostia, Málaga and Sevilla; at partition's time budget it is worse in the three smaller cities and better
  in Málaga/Sevilla. Kept as options; the default is plain partition.

**Service (v1.4, not released yet)**: `ParetoParameters` defaults to `crossover="partition"`, `mating="size"`
(`run.py` keeps `mating=any` unless named, so earlier runs stay reproducible). 300 generations: Donostia 31 s,
Valencia 122 s locally (none: 10 s, 20 s).

## Open issues and next steps

- **Paper** (`paper/`): not compiled yet (no LaTeX here); compile in Overleaf and review. The co-authors should
  agree on the framing: the contribution is the equity measure, the 4-objective formulation, the mutation-driven
  design (ablation) and the bounds; the negative result on recombination includes the graph crossover of Jordán et
  al. Target suggested in the draft's TODO: *Expert Systems*.
- **Service**: the UI of the trade-off jobs has not been checked in a browser (test jobs "Trade-off v1.2 (prueba)" and "Trade-off v1.3 (prueba)" are in the shared job list).
  The single-objective GA is 16 % above the best known mean distance in Valladolid: the alternating local search of
  `experiments/bounds.py` could polish its result.
- **Method**: with 4 objectives the whole population is non-dominated, so the fairest layouts are less fair than
  with 3 (larger populations or archives per size); `f2` is almost fixed by the size when capacity is short
  (all five cities); walking distances on the street network; real per-site costs; recombination might help with
  other operators or longer runs.
