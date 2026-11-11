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

- the partition crossover cuts the city into tiles and takes each tile from
  the parent that does better there (fewer containers, unserved people and
  distance); both parents have the same number of containers (``mating``),
- mutation moves sites, mostly towards the centre of the people they serve
  (``centroid_moves``) and otherwise to a nearby candidate, and sometimes
  changes the number of containers, adding next to the most loaded sites or
  removing the least loaded,
- the sizes are restricted to ``levels`` evenly spaced values plus today's, so
  layouts of the same size compete with each other,
- unserved people are compared in steps of a tenth of the service level,
- the first population holds the current layout and, besides random ones,
  layouts seeded where people live and layouts of equal-population cells
  (``init="mixed"``).

On five cities (see experiments/ and RESEARCH.md), this configuration gives
better fronts in the same time than mutation alone (the previous default)
and than seven crossovers of the literature (uniform, one-point, half-plane,
quadrant, regional, the graph crossover of Jordán et al. and the union
crossover of Alp, Erkut and Drezner). They remain available (``crossover``),
as does ``crossover="none"``. NSGA-III survival (``algorithm="nsga3"``,
pymoo) was no better than NSGA-II.
"""

import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

from services.equity import Neighbourhoods, pixel_unserved
from services.problem import Problem

OBJECTIVES = ("containers", "unserved", "inequity", "mean_distance")
CROSSOVERS = (
    "none",
    "partition",
    "components",
    "union",
    "regional",
    "uniform",
    "graph",
    "onepoint",
    "halfplane",
    "quadrant",
)


@dataclass(frozen=True)
class ParetoParameters:
    min_containers: int
    max_containers: int
    service_level: float = 1000
    generations: int = 200
    population_size: int = 100
    crossover: str = "partition"  # or "none", "union", "regional", "uniform", "graph"
    crossover_rate: float = 0.9
    mating: str = "size"  # the second parent has as many containers ("any": not)
    guided_repair: bool = False  # regional/uniform/graph: repair by the loads (else at random)
    tile: float = 4.0  # partition: side of the tiles, in mean spacings between sites
    # First population: "random", "demand" (k-means++ by population), "balanced"
    # (equal-population cells) or "mixed" (half each), init_share of it seeded so
    init: str = "mixed"
    init_share: float = 0.5
    cuts: int = 0  # partition: if > 0, regions cut by this many random lines instead of tiles
    tile_max: float = 0.0  # partition: if > tile, the side is drawn in [tile, tile_max]
    tile_count: bool = True  # partition: compare the parents in a tile also by their sites
    tile_equity: bool = False  # partition: ... and by the dispersion of the unserved share
    mutation: float = 0.5  # probability that a child is mutated
    moved_share: float = 0.02  # share of its sites a mutation changes
    local_moves: float = 0.8  # share of moves to a neighbour candidate
    resize: float = 0.2  # probability that a mutation also changes the number of containers
    centroid_moves: float = 0.8  # share of moves to the centre of the people a site serves
    balance: float = 0.0  # probability that a mutation moves the least loaded site next to the most
    levels: int = 11  # allowed numbers of containers, evenly spaced in the range (0: all)
    region_share: tuple[float, float] = (0.001, 0.005)  # share of candidates in the disc
    graph_centres: int = 1  # graph crossover: subgraphs exchanged
    graph_depth: int = 1  # graph crossover: hops from each centre (Delaunay graph)
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
        if params.crossover not in CROSSOVERS:
            raise ValueError(f"crossover must be one of {', '.join(CROSSOVERS)}")
        if params.init not in ("random", "demand", "balanced", "mixed"):
            raise ValueError("init must be 'random', 'demand', 'balanced' or 'mixed'")
        if params.mating not in ("any", "size"):
            raise ValueError("mating must be 'any' or 'size'")
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
        self.evaluations = 0  # layouts evaluated (cache misses)
        # Unserved people and distance of every pixel, for the partition
        # crossover: kept for the last layouts evaluated (parents and children)
        self._pixels: OrderedDict[bytes, tuple[np.ndarray, np.ndarray]] = OrderedDict()
        lo, hi = params.min_containers, params.max_containers
        if params.levels <= 0 or params.levels > hi - lo + 1:
            self.levels = np.arange(lo, hi + 1)
        else:
            self.levels = np.unique(np.round(np.linspace(lo, hi, params.levels)).astype(int))
        if lo <= problem.current_containers <= hi:
            # Today's number of containers, to compare like with like
            self.levels = np.union1d(self.levels, [problem.current_containers])

    # -- evaluation --------------------------------------------------- #
    def measure(self, layout: np.ndarray, diagnostics: bool = True) -> dict:
        """Objectives and metrics of a layout (sorted candidate indices);
        Moran's I (a diagnostic, as costly as the rest) only with ``diagnostics``."""
        p = self.problem
        ev = p.evaluate(layout, self.params.service_level)
        unserved = pixel_unserved(p.people, ev.pixel_site, ev.loads, ev.capacities)
        return {
            "pixel_unserved": unserved,
            "containers": int(layout.size),
            "unserved": ev.overload,
            "inequity": self.neighbourhoods.inequity(unserved),
            "morans_i": self.neighbourhoods.morans_i(unserved) if diagnostics else None,
            "evaluation": ev,
        }

    def objectives(self, layout: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """(objectives, loads per site); cached."""
        key = layout.tobytes()
        if key not in self._cache:
            self.evaluations += 1
            m = self.measure(layout, diagnostics=False)
            if self.params.crossover == "partition":
                self._remember(key, m["pixel_unserved"], m["evaluation"].pixel_distance)
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

    def _guided_repair(self, layout: np.ndarray, target: int | None = None) -> np.ndarray:
        """Unique sites, resized to ``target`` (default: the nearest allowed
        size) by the loads of the sites: the least loaded are removed, new
        sites are added next to the most loaded."""
        sites = np.unique(layout)
        target = self._snap(sites.size) if target is None else target
        if sites.size != target:
            loads = self.problem.evaluate(sites, self.params.service_level).loads
            sites = np.asarray(self._resize(sites.tolist(), target, loads), dtype=int)
        return np.sort(sites)

    def _fix(self, layout: np.ndarray) -> np.ndarray:
        return self._guided_repair(layout) if self.params.guided_repair else self._repair(layout)

    def random_layout(self) -> np.ndarray:
        k = int(self.rng.choice(self.levels))
        return np.sort(self.rng.choice(self.problem.size, k, replace=False))

    def demand_layout(self, k: int | None = None, exponent: float | None = None) -> np.ndarray:
        """A layout seeded where people live (k-means++ weighted by population):
        each site is drawn among the pixels with probability proportional to
        people x d^exponent, d being the distance to the nearest site drawn so
        far, and placed on the nearest free candidate. Exponent 0 follows the
        population (more sites where more people live), 2 spreads the sites
        to shorten walks (the k-means++ rule); by default it is drawn in [0, 2]
        so that the seeds cover the trade-off."""
        p = self.problem
        k = int(self.rng.choice(self.levels)) if k is None else k
        exponent = self.rng.uniform(0, 2) if exponent is None else exponent
        chosen: list[int] = []
        taken = np.zeros(p.size, dtype=bool)
        dist = np.full(len(p.pixels_xy), np.inf)
        for _ in range(k):
            w = p.people * (np.where(np.isfinite(dist), dist, 1.0) ** exponent)
            total = w.sum()
            pixel = (
                int(self.rng.choice(len(w), p=w / total))
                if total > 0
                else int(self.rng.integers(len(w)))
            )
            _, near = p.candidate_tree.query(p.pixels_xy[pixel], k=min(16, p.size))
            free = [int(c) for c in np.atleast_1d(near) if not taken[c]]
            site = free[0] if free else int(self.rng.choice(np.flatnonzero(~taken)))
            taken[site] = True
            chosen.append(site)
            dist = np.minimum(dist, np.hypot(*(p.pixels_xy - p.candidates_xy[site]).T))
        return np.sort(np.asarray(chosen, dtype=int))

    def balanced_layout(self, k: int | None = None) -> np.ndarray:
        """A layout whose cells hold about the same population: the pixels are
        split recursively by a line of random orientation into two parts whose
        populations are proportional to the sites each will hold, until each
        part holds one site, placed on the free candidate nearest to the
        centre of its people. Equal loads leave no capacity idle and spread the
        shortage evenly, the aims of the unserved and inequity objectives."""
        p = self.problem
        k = int(self.rng.choice(self.levels)) if k is None else k
        taken = np.zeros(p.size, dtype=bool)
        chosen: list[int] = []
        stack = [(np.flatnonzero(p.people > 0), k)]
        while stack:
            pixels, m = stack.pop()
            if m == 1 or pixels.size <= 1:
                w = p.people[pixels]
                centre = (p.pixels_xy[pixels] * w[:, None]).sum(0) / max(w.sum(), 1e-9)
                for _ in range(m):
                    _, near = p.candidate_tree.query(centre, k=min(32, p.size))
                    free = [int(c) for c in np.atleast_1d(near) if not taken[c]]
                    site = free[0] if free else int(self.rng.choice(np.flatnonzero(~taken)))
                    taken[site] = True
                    chosen.append(site)
                continue
            angle = self.rng.uniform(0, np.pi)
            along = p.pixels_xy[pixels] @ np.array([np.cos(angle), np.sin(angle)])
            order = pixels[np.argsort(along)]
            left = m // 2
            cumulative = np.cumsum(p.people[order])
            cut = int(np.searchsorted(cumulative, cumulative[-1] * left / m)) + 1
            cut = min(max(cut, 1), order.size - 1)
            stack += [(order[:cut], left), (order[cut:], m - left)]
        return np.sort(np.asarray(chosen, dtype=int))

    def seeds(self) -> list[np.ndarray]:
        """The current layout, cut or extended to the nearest allowed size."""
        if not self.params.seed_current:
            return []
        k = self._snap(self.problem.current_containers)
        return [self.problem.seed(k, self.rng)]

    def crossover(self, a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        if self.params.crossover == "partition":
            return self._partition(a, b)
        if self.params.crossover == "components":
            return self._partition_exact(a, b)
        if self.params.crossover == "union":
            return self._union(a, b, a.size), self._union(a, b, b.size)
        if self.params.crossover == "uniform":
            common = np.intersect1d(a, b, assume_unique=True)
            others = np.setxor1d(a, b, assume_unique=True)
            take = self.rng.random(others.size) < 0.5
            return (
                self._fix(np.concatenate((common, others[take]))),
                self._fix(np.concatenate((common, others[~take]))),
            )
        if self.params.crossover == "graph":
            return self._exchange(a, b, self._graph_region())
        if self.params.crossover == "onepoint":
            # One-point crossover of the binary vectors (Hosage and Goodchild)
            cut = int(self.rng.integers(1, self.problem.size))
            return self._exchange(a, b, np.arange(self.problem.size) >= cut)
        if self.params.crossover in ("halfplane", "quadrant"):
            xy = self.problem.candidates_xy
            centre = xy[self.rng.integers(len(xy))]
            if self.params.crossover == "halfplane":
                # Cut-and-splice (Deaven and Ho): a random line through a random point
                angle = self.rng.uniform(0, np.pi)
                normal = np.array([np.cos(angle), np.sin(angle)])
                return self._exchange(a, b, (xy - centre) @ normal > 0)
            # Quadrant swap (Li and Parrott): one of the four quadrants around a random point
            q = int(self.rng.integers(4))
            right, up = xy[:, 0] > centre[0], xy[:, 1] > centre[1]
            return self._exchange(a, b, (right == bool(q & 1)) & (up == bool(q & 2)))
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
            self._fix(np.concatenate((a[~mask[a]], b[mask[b]]))),
            self._fix(np.concatenate((b[~mask[b]], a[mask[a]]))),
        )

    # -- spatial partition crossover ----------------------------------- #
    def components(self, a: np.ndarray, b: np.ndarray):
        """Split the sites of two parents into independent components.

        Each person uses the nearest site. A child that takes, in every
        component, the sites of one of the parents (shared sites are in both)
        serves a pixel from a site of a | b no farther than the farther of the
        pixel's sites in the parents; linking all those sites makes the
        pixel's site in the child that of the parent its component came from.
        So the containers, unserved people and total distance of a child are
        the sums, component by component, of those of the parent each one
        came from (inequity is not additive).

        Returns (union of the sites, component of each, contributions of a and
        of b per component as rows (containers, unserved, distance), whether
        each component holds sites of only one parent)."""
        p, level = self.problem, self.params.service_level
        ea, eb = p.evaluate(a, level), p.evaluate(b, level)
        union = np.union1d(a, b)
        local = np.full(p.size, -1, dtype=int)
        local[union] = np.arange(union.size)
        sa, sb = a[ea.pixel_site], b[eb.pixel_site]  # serving candidate of each pixel
        rows = np.flatnonzero(sa != sb)
        reach = np.maximum(ea.pixel_distance[rows], eb.pixel_distance[rows]) + 1e-6
        near, dist = p.pixel_neighbours[rows], p.pixel_dists[rows]
        r, c = np.nonzero((local[near] >= 0) & (dist <= reach[:, None]))
        src = [local[sa[rows]], local[sa[rows[r]]]]
        dst = [local[sb[rows]], local[near[r, c]]]
        far = np.flatnonzero(reach > dist[:, -1])  # beyond the precomputed neighbours
        if far.size:
            tree = cKDTree(p.candidates_xy[union])
            found_all = tree.query_ball_point(p.pixels_xy[rows[far]], reach[far])
            for i, found in zip(far, found_all, strict=True):
                src.append(np.full(len(found), local[sa[rows[i]]]))
                dst.append(np.asarray(found, dtype=int))
        src, dst = np.concatenate(src), np.concatenate(dst)
        graph = coo_matrix((np.ones(src.size), (src, dst)), shape=(union.size, union.size))
        n, labels = connected_components(graph, directed=False)

        shared = np.intersect1d(a, b, assume_unique=True)

        def contributions(x, ev):
            lab = labels[local[x]]
            over = np.clip(ev.loads - ev.capacities, 0, None)
            weights = p.people * ev.pixel_distance
            return np.stack(
                [
                    np.bincount(lab[~np.isin(x, shared)], minlength=n),
                    np.bincount(lab, weights=over, minlength=n),
                    np.bincount(lab[ev.pixel_site], weights=weights, minlength=n),
                ],
                axis=1,
            )

        differ = np.zeros(n, dtype=bool)
        differ[labels[local[np.setxor1d(a, b, assume_unique=True)]]] = True
        return union, labels, contributions(a, ea), contributions(b, eb), differ

    def _remember(self, key: bytes, unserved: np.ndarray, distance: np.ndarray) -> None:
        self._pixels[key] = (unserved, distance)
        while len(self._pixels) > 3 * self.params.population_size:
            self._pixels.popitem(last=False)

    def _pixel_measures(self, layout: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Unserved people and distance of every pixel."""
        key = layout.tobytes()
        if key in self._pixels:
            self._pixels.move_to_end(key)
            return self._pixels[key]
        p = self.problem
        ev = p.evaluate(layout, self.params.service_level)
        unserved = pixel_unserved(p.people, ev.pixel_site, ev.loads, ev.capacities)
        self._remember(key, unserved, ev.pixel_distance)
        return unserved, ev.pixel_distance

    def tiles(self, a: np.ndarray, b: np.ndarray):
        """A grid of square tiles at a random offset, of side ``tile`` times
        the mean spacing between the sites of the parents. Returns the tile of
        each candidate and the contributions of a and b to each tile as rows
        (containers, unserved people, distance x people) of the sites and
        pixels in it; with ``tile_equity``, also the population-weighted
        squared deviation of the unserved share of its neighbourhoods (see
        services.equity) from the mean of both parents: inequity is not
        additive, but this is its share in the tile."""
        p = self.problem
        area = np.prod(np.ptp(p.pixels_xy, axis=0)) or 1.0
        tau = self.params.tile
        if self.params.tile_max > tau:
            tau = self.rng.uniform(tau, self.params.tile_max)
        side = tau * np.sqrt(area / max(1, (a.size + b.size) / 2))
        offset = self.rng.random(2) * side
        lo = p.pixels_xy.min(axis=0) - side

        if self.params.cuts > 0:
            # Regions between random lines, each through a random candidate
            through = p.candidates_xy[self.rng.integers(p.size, size=self.params.cuts)]
            angles = self.rng.uniform(0, np.pi, self.params.cuts)
            normals = np.column_stack((np.cos(angles), np.sin(angles)))

            def tile_of(xy):
                sides = ((xy[:, None, :] - through[None]) * normals[None]).sum(2) > 0
                return (sides * (1 << np.arange(self.params.cuts))).sum(1).astype(np.int64)

        else:

            def tile_of(xy):
                ij = np.floor((xy - lo + offset) / side).astype(np.int64)
                return ij[:, 0] * 1_000_003 + ij[:, 1]

        keys, inverse = np.unique(
            np.concatenate((tile_of(p.pixels_xy), tile_of(p.candidates_xy))), return_inverse=True
        )
        pixel_tile, site_tile = inverse[: len(p.pixels_xy)], inverse[len(p.pixels_xy) :]
        n = keys.size

        def contributions(x):
            unserved, distance = self._pixel_measures(x)
            return [
                np.bincount(site_tile[x], minlength=n),
                np.bincount(pixel_tile, weights=unserved, minlength=n),
                np.bincount(pixel_tile, weights=p.people * distance, minlength=n),
            ]

        ca, cb = contributions(a), contributions(b)
        if self.params.tile_equity:
            nb = self.neighbourhoods
            if not hasattr(self, "_cell_xy"):
                self._cell_xy = (
                    np.column_stack(
                        [
                            np.bincount(nb.pixel_cell, weights=p.people * p.pixels_xy[:, i])
                            for i in (0, 1)
                        ]
                    )
                    / np.maximum(nb.cell_people, 1e-9)[:, None]
                )
            cell_tile = np.searchsorted(keys, tile_of(self._cell_xy))
            cell_tile = np.minimum(cell_tile, n - 1)  # a centre in no pixel's tile: rare
            w = nb.cell_people
            shares = [
                (nb.weights @ nb.unserved_cells(self._pixel_measures(x)[0]))
                / nb.neighbourhood_people
                for x in (a, b)
            ]
            mean = np.mean([w @ sh / w.sum() for sh in shares])
            for c, sh in zip((ca, cb), shares, strict=True):
                c.append(np.bincount(cell_tile, weights=w * (sh - mean) ** 2, minlength=n))
        return site_tile, np.stack(ca, axis=1), np.stack(cb, axis=1)

    def _partition(self, a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Partition crossover: cut the city into tiles (see :meth:`tiles`) and
        take, in each, the sites of the parent that does better there (no more
        containers, unserved people or distance, and less of one); where
        neither does, the first child takes the tile from a random parent and
        the second from the other. Then repaired by the loads."""
        site_tile, ca, cb = self.tiles(a, b)
        if not self.params.tile_count:
            ca, cb = ca[:, 1:], cb[:, 1:]
        a_better = (ca <= cb).all(axis=1) & (ca < cb).any(axis=1)
        b_better = (cb <= ca).all(axis=1) & (cb < ca).any(axis=1)
        tie = ~a_better & ~b_better & (ca != cb).any(axis=1)
        coin = self.rng.random(tie.size) < 0.5
        children = []
        for take_b in (b_better | (tie & coin), b_better | (tie & ~coin)):
            child = np.concatenate((a[~take_b[site_tile[a]]], b[take_b[site_tile[b]]]))
            children.append(self._guided_repair(child))
        if not tie.any():  # both children are the same: keep the second parent
            children[1] = b.copy()
        return children[0], children[1]

    def _partition_exact(self, a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Spatial partition crossover: in each independent component (see
        :meth:`components`), take the sites of the parent that is better there
        (no more containers, unserved people or distance, and less of one);
        where neither is, the first child takes them from a random parent and
        the second from the other. Then repaired by the loads."""
        union, labels, ca, cb, differ = self.components(a, b)
        a_better = (ca <= cb).all(axis=1) & (ca < cb).any(axis=1)
        b_better = (cb <= ca).all(axis=1) & (cb < ca).any(axis=1)
        tie = differ & ~a_better & ~b_better
        coin = self.rng.random(tie.size) < 0.5
        in_a, in_b = np.isin(union, a), np.isin(union, b)
        children = []
        for take_b in (b_better | (tie & coin), b_better | (tie & ~coin)):
            from_b = take_b[labels]
            children.append(self._guided_repair(union[np.where(from_b, in_b, in_a)]))
        if not tie.any():  # both children are the same: keep the second parent
            children[1] = b.copy()
        return children[0], children[1]

    def _union(self, a: np.ndarray, b: np.ndarray, target: int) -> np.ndarray:
        """Union crossover (Alp, Erkut and Drezner's for the p-median problem,
        with a random weight between the objectives): start from the sites of
        both parents and drop, a third of the excess at a time, those whose
        removal costs least, until ``target`` remain. The cost of dropping a
        site mixes the extra distance of its people to their next site and
        its load."""
        p, level = self.problem, self.params.service_level
        sites = np.union1d(a, b)
        w = self.rng.random()
        rows = np.arange(len(p.pixels_xy))
        while sites.size > target:
            ev = p.evaluate(sites, level)
            mask = np.zeros(p.size, dtype=bool)
            mask[sites] = True
            hits = mask[p.pixel_neighbours]
            hits[rows, hits.argmax(axis=1)] = False
            second = np.where(
                hits.any(axis=1),
                p.pixel_dists[rows, hits.argmax(axis=1)],
                2 * p.pixel_dists[:, -1],
            )
            extra = np.bincount(
                ev.pixel_site,
                weights=p.people * np.maximum(second - ev.pixel_distance, 0),
                minlength=sites.size,
            )
            cost = w * extra / max(extra.max(), 1e-9) + (1 - w) * ev.loads / max(
                ev.loads.max(), 1e-9
            )
            drop = max(1, (sites.size - target) // 3)
            sites = np.delete(sites, np.argsort(cost, kind="stable")[:drop])
        return self._guided_repair(sites, target)

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
        centres = None
        if p.balance and len(sites) > 1 and self.rng.random() < p.balance:
            # Balancing move: the least loaded site goes next to the most loaded one
            low, high = int(np.argmin(loads)), int(np.argmax(loads))
            options = [c for c in neighbours[sites[high]] if c not in chosen]
            if options and low != high:
                new = int(self.rng.choice(options))
                chosen.discard(sites[low])
                chosen.add(new)
                sites[low] = new
        for _ in range(max(1, self.rng.binomial(len(sites), p.moved_share))):
            i = int(self.rng.integers(len(sites)))
            options = []
            if p.centroid_moves and self.rng.random() < p.centroid_moves:
                # Towards the centre of the people the site serves (Cooper's
                # alternating step for the p-median problem)
                if centres is None:
                    centres = self._centres(layout)
                if np.isfinite(centres[i]).all():
                    _, near = self.problem.candidate_tree.query(centres[i], k=4)
                    options = [int(c) for c in np.atleast_1d(near) if c not in chosen][:1]
            elif self.rng.random() < p.local_moves and neighbours.shape[1]:
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

    def _centres(self, layout: np.ndarray) -> np.ndarray:
        """Population-weighted centre of the pixels each site serves (NaN if none)."""
        p = self.problem
        ev = p.evaluate(layout, self.params.service_level)
        with np.errstate(invalid="ignore", divide="ignore"):
            return (
                np.column_stack(
                    [
                        np.bincount(
                            ev.pixel_site,
                            weights=p.people * p.pixels_xy[:, j],
                            minlength=layout.size,
                        )
                        for j in (0, 1)
                    ]
                )
                / ev.loads[:, None]
            )

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

    def _tournament(self, rank, crowd, among: np.ndarray | None = None) -> int:
        if among is not None and among.size >= 2:
            i, j = self.rng.choice(among, 2, replace=False)
        else:
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
            r = self.rng.random()
            if p.init != "random" and r < p.init_share:
                balanced = p.init == "balanced" or (p.init == "mixed" and r < p.init_share / 2)
                seed = self.balanced_layout() if balanced else self.demand_layout()
            else:
                seed = self.random_layout()
            population.append(seed)
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
                "evaluations": self.evaluations,
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
            sizes = np.array([x.size for x in population])
            while len(offspring) < p.population_size:
                a = population[self._tournament(rank, crowd)]
                same = np.flatnonzero(sizes == a.size) if p.mating == "size" else None
                b = population[self._tournament(rank, crowd, same)]
                if p.crossover != "none" and self.rng.random() < p.crossover_rate:
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
