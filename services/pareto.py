"""Multi-objective variant: the trade-off between how many containers, how many
people they leave unserved, how fairly that is spread and how far people walk.

Instead of one layout for a fixed number of containers, it returns a Pareto
front of layouts with between ``min_containers`` and ``max_containers``
containers. Every objective is minimised:

1. **containers**: the number of sites (one container each),
2. **unserved**: people above the capacity of their container (the overload of
   the single-objective algorithm),
3. **inequity**: how unequally the unserved are spread between neighbourhoods
   (:mod:`services.equity`),
4. **mean distance** to the nearest container (``distance=True``, the default).

The algorithm is NSGA-II (non-dominated sorting, crowding distance, elitist
survival) on sets of candidate indices of variable size:

- *regional* crossover (default): a child takes one parent's sites inside a
  random disc and the other parent's sites outside it, so it inherits two
  spatially coherent partial layouts instead of a scatter of single sites;
  *uniform* crossover (keep the common sites, take each other site with
  probability 1/2) is the classic alternative,
- mutation moves sites to a nearby candidate, and sometimes changes the
  number of containers (adding next to the most loaded sites or removing the
  least loaded),
- the sizes are restricted to ``levels`` evenly spaced values plus today's, so
  layouts of the same size compete with each other,
- the current layout is seeded into the first population.

NSGA-III survival (``algorithm="nsga3"``, pymoo) is available for comparison;
on five cities it was no better than NSGA-II, with three or four objectives
(see experiments/).
"""

import time
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from services.equity import Neighbourhoods, pixel_unserved
from services.problem import Problem

OBJECTIVES = ("containers", "unserved", "inequity", "mean_distance")


@dataclass(frozen=True)
class ParetoParameters:
    min_containers: int
    max_containers: int
    service_level: float = 1000
    generations: int = 200
    population_size: int = 100
    crossover: str = "regional"  # or "uniform", or "graph" (Jordán et al.)
    crossover_rate: float = 0.9
    mutation: float = 0.5  # probability that a child is mutated
    moved_share: float = 0.02  # share of its sites a mutation changes
    local_moves: float = 0.8  # share of moves to a neighbour candidate
    resize: float = 0.2  # probability that a mutation also changes the number of containers
    levels: int = 11  # allowed numbers of containers, evenly spaced in the range (0: all)
    region_share: tuple[float, float] = (0.1, 0.5)  # share of candidates in the disc
    graph_centres: int = 1  # graph crossover: subgraphs exchanged
    graph_depth: int = 5  # graph crossover: hops from each centre (Delaunay graph)
    # Switches for the ablation study (all on in the service)
    quantize: bool = True  # compare unserved people in steps of service_level / 10
    guided_resize: bool = True  # resize by the loads of the sites (else at random)
    seed_current: bool = True  # seed the current layout into the first population
    distance: bool = True  # 4th objective: mean distance to the nearest container
    algorithm: str = "nsga2"  # or "nsga3" (reference-direction survival; needs pymoo)
    cell: float = 500.0  # equity: cell size (m)
    radius: float = 1000.0  # equity: neighbourhood radius (m)
    time_limit: float | None = None
    seed: int | None = None


Progress = Callable[[int, dict], None]


# --------------------------------------------------------------------- #
def non_dominated_fronts(F: np.ndarray) -> list[np.ndarray]:
    """Fronts of non-dominated sorting (minimisation), best first."""
    le = (F[:, None, :] <= F[None, :, :]).all(axis=2)
    lt = (F[:, None, :] < F[None, :, :]).any(axis=2)
    dominates = le & lt  # [i, j]: i dominates j
    count = dominates.sum(axis=0)
    fronts = []
    current = np.flatnonzero(count == 0)
    while current.size:
        fronts.append(current)
        count = count - dominates[current].sum(axis=0)
        count[current] = -1
        current = np.flatnonzero(count == 0)
    return fronts


def crowding_distance(F: np.ndarray) -> np.ndarray:
    n, m = F.shape
    if n <= 2:
        return np.full(n, np.inf)
    distance = np.zeros(n)
    for j in range(m):
        order = np.argsort(F[:, j], kind="stable")
        span = F[order[-1], j] - F[order[0], j]
        distance[order[[0, -1]]] = np.inf
        if span > 0:
            distance[order[1:-1]] += (F[order[2:], j] - F[order[:-2], j]) / span
    return distance


# --------------------------------------------------------------------- #
class ParetoAlgorithm:
    def __init__(self, problem: Problem, params: ParetoParameters):
        if not 1 <= params.min_containers <= params.max_containers <= problem.size:
            raise ValueError(
                f"containers must satisfy 1 <= min <= max <= {problem.size} (candidate sites)"
            )
        if params.crossover not in ("regional", "uniform", "graph"):
            raise ValueError("crossover must be 'regional', 'uniform' or 'graph'")
        if params.algorithm not in ("nsga2", "nsga3"):
            raise ValueError("algorithm must be 'nsga2' or 'nsga3'")
        self.n_objectives = 4 if params.distance else 3
        self.problem = problem
        self.params = params
        self.rng = np.random.default_rng(params.seed)
        if (params.cell, params.radius) == (500.0, 1000.0):
            self.neighbourhoods = problem.neighbourhoods
        else:
            self.neighbourhoods = Neighbourhoods.build(
                problem.pixels_xy, problem.people, params.cell, params.radius
            )
        self._cache: dict[bytes, tuple[np.ndarray, np.ndarray]] = {}
        lo, hi = params.min_containers, params.max_containers
        if params.levels <= 0 or params.levels > hi - lo + 1:
            self.levels = np.arange(lo, hi + 1)
        else:
            self.levels = np.unique(np.round(np.linspace(lo, hi, params.levels)).astype(int))
        if lo <= problem.current_containers <= hi:
            # Today's number of containers, to compare like with like
            self.levels = np.union1d(self.levels, [problem.current_containers])

    # -- evaluation --------------------------------------------------- #
    def measure(self, layout: np.ndarray) -> dict:
        """Objectives and metrics of a layout (sorted candidate indices)."""
        p = self.problem
        ev = p.evaluate(layout, self.params.service_level)
        unserved = pixel_unserved(p.people, ev.pixel_site, ev.loads, ev.capacities)
        return {
            "containers": int(layout.size),
            "unserved": ev.overload,
            "inequity": self.neighbourhoods.inequity(unserved),
            "morans_i": self.neighbourhoods.morans_i(unserved),
            "evaluation": ev,
        }

    def objectives(self, layout: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """(objectives, loads per site); cached."""
        key = layout.tobytes()
        if key not in self._cache:
            m = self.measure(layout)
            # Unserved in steps of a tenth of the service level: smaller
            # differences are below the population of a pixel (noise), and
            # would shelter unfair layouts from layouts as good but fairer
            step = max(1.0, self.params.service_level / 10)
            unserved = m["unserved"]
            if self.params.quantize:
                unserved = np.floor(unserved / step) * step
            f = [m["containers"], unserved, m["inequity"]]
            if self.params.distance:
                f.append(round(m["evaluation"].mean_distance, 1))
            f = np.array(f, dtype=float)
            self._cache[key] = (f, m["evaluation"].loads)
        return self._cache[key]

    # -- operators ---------------------------------------------------- #
    def _snap(self, k: int) -> int:
        return int(self.levels[np.abs(self.levels - k).argmin()])

    def _resize(self, sites: list[int], target: int, loads: np.ndarray | None = None) -> list[int]:
        """Add or remove sites until there are ``target``. With the loads of the
        sites, it removes the least loaded ones and adds next to the most loaded;
        otherwise at random, adding next to existing sites."""
        neighbours = self.problem.candidate_neighbours
        chosen = set(sites)
        if len(sites) > target:
            if loads is not None and len(loads) == len(sites):
                drop = [sites[i] for i in np.argsort(loads)[: len(sites) - target]]
            else:
                drop = self.rng.choice(sites, len(sites) - target, replace=False).tolist()
            dropped = set(drop)
            return [s for s in sites if s not in dropped]
        order = (
            np.argsort(-loads)
            if loads is not None and len(loads) == len(sites)
            else self.rng.permutation(len(sites))
        )
        anchors = [sites[i] for i in order]
        added = []
        tries = 0
        while len(sites) + len(added) < target:
            anchor = anchors[tries % len(anchors)] if anchors else None
            tries += 1
            options = (
                [c for c in neighbours[anchor] if c not in chosen]
                if anchor is not None and neighbours.shape[1] and tries <= 3 * len(anchors)
                else []
            )
            new = (
                int(self.rng.choice(options))
                if options
                else int(self.rng.integers(self.problem.size))
            )
            if new not in chosen:
                chosen.add(new)
                added.append(new)
        return sites + added

    def _repair(self, layout: np.ndarray) -> np.ndarray:
        """Unique sites, as many as the nearest allowed number of containers."""
        sites = np.unique(layout).tolist()
        return np.sort(np.asarray(self._resize(sites, self._snap(len(sites))), dtype=int))

    def random_layout(self) -> np.ndarray:
        k = int(self.rng.choice(self.levels))
        return np.sort(self.rng.choice(self.problem.size, k, replace=False))

    def seeds(self) -> list[np.ndarray]:
        """The current layout, cut or extended to the nearest allowed size."""
        if not self.params.seed_current:
            return []
        k = self._snap(self.problem.current_containers)
        return [self.problem.seed(k, self.rng)]

    def crossover(self, a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        if self.params.crossover == "uniform":
            common = np.intersect1d(a, b, assume_unique=True)
            others = np.setxor1d(a, b, assume_unique=True)
            take = self.rng.random(others.size) < 0.5
            return (
                self._repair(np.concatenate((common, others[take]))),
                self._repair(np.concatenate((common, others[~take]))),
            )
        if self.params.crossover == "graph":
            return self._exchange(a, b, self._graph_region())
        # Regional: a disc around a random candidate holding a random share of them
        xy = self.problem.candidates_xy
        centre = xy[self.rng.integers(len(xy))]
        low, high = self.params.region_share
        k = max(1, int(self.rng.uniform(low, high) * len(xy)))
        _, inside = self.problem.candidate_tree.query(centre, k=k)
        mask = np.zeros(len(xy), dtype=bool)
        mask[np.atleast_1d(inside)] = True
        return self._exchange(a, b, mask)

    def _exchange(self, a: np.ndarray, b: np.ndarray, mask: np.ndarray):
        """Children that swap the parents' sites inside the region ``mask``."""
        return (
            self._repair(np.concatenate((a[~mask[a]], b[mask[b]]))),
            self._repair(np.concatenate((b[~mask[b]], a[mask[a]]))),
        )

    def _graph_region(self) -> np.ndarray:
        """Graph crossover (Jordán et al., 2025): the union of ``graph_centres``
        subgraphs, each a random candidate and its neighbours up to
        ``graph_depth`` hops in the Delaunay graph of the candidates."""
        if not hasattr(self, "_graph"):
            from scipy.spatial import Delaunay

            n = self.problem.size
            if n >= 4:
                indptr, indices = Delaunay(self.problem.candidates_xy).vertex_neighbor_vertices
            else:
                indptr, indices = np.arange(n + 1) * 0, np.array([], dtype=int)
            self._graph = (indptr, indices)
        indptr, indices = self._graph
        mask = np.zeros(self.problem.size, dtype=bool)
        for _ in range(self.params.graph_centres):
            frontier = np.array([self.rng.integers(self.problem.size)])
            mask[frontier] = True
            for _ in range(self.params.graph_depth):
                nxt = np.concatenate([indices[indptr[i] : indptr[i + 1]] for i in frontier])
                nxt = nxt[~mask[nxt]] if nxt.size else nxt
                if not nxt.size:
                    break
                nxt = np.unique(nxt)
                mask[nxt] = True
                frontier = nxt
        return mask

    def mutate(self, layout: np.ndarray) -> np.ndarray:
        """Move sites (mostly to a neighbour candidate); sometimes, also change
        to the next allowed number of containers."""
        p = self.params
        _, loads = self.objectives(layout)
        sites = layout.tolist()
        chosen = set(sites)
        neighbours = self.problem.candidate_neighbours
        for _ in range(max(1, self.rng.binomial(len(sites), p.moved_share))):
            i = int(self.rng.integers(len(sites)))
            options = []
            if self.rng.random() < p.local_moves and neighbours.shape[1]:
                options = [c for c in neighbours[sites[i]] if c not in chosen]
            new = (
                int(self.rng.choice(options))
                if options
                else int(self.rng.integers(self.problem.size))
            )
            if new not in chosen:
                chosen.discard(sites[i])
                chosen.add(new)
                sites[i] = new
        if self.levels.size > 1 and self.rng.random() < p.resize:
            # Loads still describe the sites of the parent closely enough
            level = int(np.searchsorted(self.levels, len(sites)))
            level += 1 if self.rng.random() < 0.5 else -1
            level = min(max(level, 0), self.levels.size - 1)
            guide = loads if p.guided_resize else None
            sites = self._resize(sites, int(self.levels[level]), guide)
        return self._repair(np.asarray(sites, dtype=int))

    # -- loop --------------------------------------------------------- #
    def _rank(self, F: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        rank = np.empty(len(F), dtype=int)
        crowd = np.empty(len(F))
        for r, front in enumerate(non_dominated_fronts(F)):
            rank[front] = r
            crowd[front] = crowding_distance(F[front])
        return rank, crowd

    def _survive(self, F: np.ndarray, n: int) -> np.ndarray:
        """Indices of the n survivors among F."""
        if self.params.algorithm == "nsga3":
            return self._nsga3_survival(F, n)
        survivors: list[int] = []
        for front in non_dominated_fronts(F):
            if len(survivors) + front.size <= n:
                survivors.extend(front.tolist())
            else:
                cd = crowding_distance(F[front])
                survivors.extend(
                    front[np.argsort(-cd, kind="stable")[: n - len(survivors)]].tolist()
                )
                break
        return np.asarray(survivors, dtype=int)

    def _nsga3_survival(self, F: np.ndarray, n: int) -> np.ndarray:
        """NSGA-III (Deb and Jain, 2014): non-dominated sorting, then niching
        around Das-Dennis reference directions on the normalised objectives.
        pymoo's implementation; its state (ideal and nadir points) persists
        across generations, as in the original algorithm."""
        from pymoo.algorithms.moo.nsga3 import ReferenceDirectionSurvival
        from pymoo.core.population import Population
        from pymoo.core.problem import Problem as PymooProblem
        from pymoo.util.ref_dirs import get_reference_directions

        if not hasattr(self, "_nsga3"):
            partitions = {3: 12, 4: 6}[self.n_objectives]  # 91 and 84 directions
            directions = get_reference_directions(
                "das-dennis", self.n_objectives, n_partitions=partitions
            )
            self._nsga3 = ReferenceDirectionSurvival(directions)
            self._nsga3_problem = PymooProblem(n_var=1, n_obj=self.n_objectives)
        population = Population.new(F=F, index=np.arange(len(F)))
        survivors = self._nsga3.do(self._nsga3_problem, population, n_survive=n)
        return np.asarray(survivors.get("index"), dtype=int)

    def _tournament(self, rank, crowd) -> int:
        i, j = self.rng.choice(len(rank), 2, replace=False)
        if rank[i] != rank[j]:
            return i if rank[i] < rank[j] else j
        return i if crowd[i] >= crowd[j] else j

    def run(self, progress: Progress | None = None) -> tuple[list[np.ndarray], list[dict]]:
        """The non-dominated layouts found, and the history of the run."""
        p = self.params
        start = time.monotonic()
        population = self.seeds()
        while len(population) < p.population_size:
            population.append(self.random_layout())
        F = np.array([self.objectives(x)[0] for x in population])
        history = []

        for generation in range(p.generations + 1):
            rank, crowd = self._rank(F)
            if p.algorithm == "nsga3":
                crowd = self.rng.random(len(F))
            front = F[rank == 0]
            record = {
                "generation": generation,
                "front": int(front.shape[0]),
                "min_unserved": round(float(front[:, 1].min())),
                "min_inequity": round(float(front[:, 2].min()), 4),
                "elapsed": round(time.monotonic() - start, 1),
            }
            history.append(record)
            if progress:
                progress(generation, record)
            if generation == p.generations:
                break
            if p.time_limit and time.monotonic() - start > p.time_limit:
                record["stopped"] = "time limit"
                break

            offspring = []
            while len(offspring) < p.population_size:
                a = population[self._tournament(rank, crowd)]
                b = population[self._tournament(rank, crowd)]
                if self.rng.random() < p.crossover_rate:
                    children = self.crossover(a, b)
                else:
                    children = (a.copy(), b.copy())
                for child in children:
                    if self.rng.random() < p.mutation:
                        child = self.mutate(child)
                    offspring.append(child)
            offspring = offspring[: p.population_size]

            # Elitist survival on parents + offspring, without duplicates
            merged, seen = [], set()
            for x in population + offspring:
                key = x.tobytes()
                if key not in seen:
                    seen.add(key)
                    merged.append(x)
            MF = np.array([self.objectives(x)[0] for x in merged])
            survivors = self._survive(MF, p.population_size)
            population = [merged[i] for i in survivors]
            F = MF[survivors]
            if len(self._cache) > 100_000:
                self._cache.clear()

        first = non_dominated_fronts(F)[0]
        best = sorted((population[i] for i in first), key=lambda x: tuple(self.objectives(x)[0]))
        return best, history
