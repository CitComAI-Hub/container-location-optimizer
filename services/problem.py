"""The location problem: where to put k containers so that nobody is left out.

Each person uses the nearest container (its Voronoi cell). A container serves
up to ``service_level`` people; the objective is, in this order:

1. **overload**: people above the capacity of their container (to minimise),
2. **mean distance**: population-weighted distance to the nearest container.

People are the populated pixels of the population grid, so evaluating a
layout is a nearest-neighbour query (milliseconds), not a polygon overlay.
Voronoi polygons are only built to draw a result.
"""

from dataclasses import dataclass

import numpy as np
import shapely
from scipy.spatial import cKDTree

from services.data_source import Container
from services.geo import LocalProjection
from services.population import Population

# Candidates precomputed per pixel; enough for the nearest one to be among
# them for any reasonable layout (otherwise a KD-tree query is the fallback)
PIXEL_NEIGHBOURS = 32
CANDIDATE_NEIGHBOURS = 8


@dataclass
class Evaluation:
    overload: float
    mean_distance: float
    p95_distance: float
    people: float
    loads: np.ndarray  # people per site
    capacities: np.ndarray

    @property
    def key(self) -> tuple[float, float]:
        """Sort key, lower is better: overload in steps of a tenth of the
        service level (smaller differences are below the population of a
        pixel, i.e. noise), then mean distance."""
        step = max(1.0, float(self.capacities.mean()) / 10) if self.capacities.size else 1.0
        return (float(np.floor(self.overload / step)), round(self.mean_distance, 3))

    def summary(self) -> dict:
        overloaded = self.loads > self.capacities
        capacity = float(self.capacities.sum())
        return {
            "overload": round(self.overload),
            "served_share": round(1 - self.overload / self.people, 4) if self.people else 1.0,
            "capacity": round(capacity),
            "capacity_share": round(min(1.0, capacity / self.people), 4) if self.people else 1.0,
            "mean_distance": round(self.mean_distance, 1),
            "p95_distance": round(self.p95_distance, 1),
            "people": round(self.people),
            "sites": int(self.loads.size),
            "overloaded_sites": int(overloaded.sum()),
            "max_load": round(float(self.loads.max())) if self.loads.size else 0,
        }


def _weighted_quantile(values: np.ndarray, weights: np.ndarray, q: float) -> float:
    order = np.argsort(values)
    cumulative = np.cumsum(weights[order])
    return float(values[order][np.searchsorted(cumulative, q * cumulative[-1])])


def _dedup(xy: np.ndarray, spacing: float) -> np.ndarray:
    """Indices of points kept so that no two are closer than ``spacing``
    (the first ones win)."""
    if len(xy) == 0 or spacing <= 0:
        return np.arange(len(xy))
    tree = cKDTree(xy)
    removed = np.zeros(len(xy), dtype=bool)
    kept = []
    for i in range(len(xy)):
        if removed[i]:
            continue
        kept.append(i)
        removed[tree.query_ball_point(xy[i], spacing)] = True
    return np.asarray(kept, dtype=int)


class Problem:
    def __init__(
        self,
        region: shapely.Geometry,
        containers: list[Container],
        population: Population,
        candidate_spacing: float = 50.0,
        candidates: str = "containers",
    ):
        self.region = region
        self.projection = LocalProjection.for_geometry(region)
        self.region_xy = self.projection.geometry_to_xy(region)
        self.population_source = population.source

        lonlat = np.array([(c.lon, c.lat) for c in containers], dtype=float).reshape(-1, 2)
        target = np.array([c.target for c in containers], dtype=bool)
        inside = shapely.contains_xy(region, lonlat[:, 0], lonlat[:, 1]).astype(bool)
        lonlat, target = lonlat[inside], target[inside]
        if not target.any():
            raise ValueError("No container to optimise inside the region")

        # Current layout: the target containers, grouped by site (same point)
        sites, counts = np.unique(np.round(lonlat[target], 7), axis=0, return_counts=True)
        self.current_lonlat = sites
        self.current_counts = counts
        self.current_containers = int(target.sum())

        # Candidates, at least candidate_spacing apart. The current sites go
        # first, so the current layout is in the search space; then the other
        # containers and/or the populated pixels (useful when the platform
        # only knows a few containers, e.g. the ones with a sensor)
        pools = [lonlat[target]]
        if candidates in ("containers", "both"):
            pools.append(lonlat[~target])
        if candidates in ("population", "both"):
            pools.append(population.lonlat)
        pool = np.concatenate(pools)
        self.candidates_lonlat = pool[_dedup(self.projection.to_xy(pool), candidate_spacing)]
        self.candidates_xy = self.projection.to_xy(self.candidates_lonlat)
        self.candidate_tree = cKDTree(self.candidates_xy)

        self.pixels_xy = self.projection.to_xy(population.lonlat)
        self.people = population.people.astype(float)
        self.total_people = float(self.people.sum())

        k = min(PIXEL_NEIGHBOURS, len(self.candidates_xy))
        dists, idx = self.candidate_tree.query(self.pixels_xy, k=k)
        self.pixel_dists = np.asarray(dists, dtype=float).reshape(len(self.pixels_xy), k)
        self.pixel_neighbours = np.asarray(idx, dtype=int).reshape(len(self.pixels_xy), k)

        k = min(CANDIDATE_NEIGHBOURS + 1, len(self.candidates_xy))
        _, idx = self.candidate_tree.query(self.candidates_xy, k=k)
        self.candidate_neighbours = np.asarray(idx, dtype=int).reshape(-1, k)[:, 1:]

    @property
    def size(self) -> int:
        return len(self.candidates_xy)

    def seed(self, k: int, rng: np.random.Generator) -> np.ndarray:
        """Candidates closest to the current layout (k of them)."""
        _, nearest = self.candidate_tree.query(self.projection.to_xy(self.current_lonlat))
        chosen = list(dict.fromkeys(np.atleast_1d(nearest).tolist()))[:k]
        if len(chosen) < k:
            rest = np.setdiff1d(np.arange(self.size), chosen)
            chosen += rng.choice(rest, k - len(chosen), replace=False).tolist()
        return np.sort(np.asarray(chosen, dtype=int))

    # ------------------------------------------------------------------ #
    def _result(self, site_of_pixel, dist, n_sites, capacities) -> Evaluation:
        loads = np.bincount(site_of_pixel, weights=self.people, minlength=n_sites)
        overload = float(np.clip(loads - capacities, 0, None).sum())
        mean_distance = float((dist * self.people).sum() / self.total_people)
        return Evaluation(
            overload=overload,
            mean_distance=mean_distance,
            p95_distance=_weighted_quantile(dist, self.people, 0.95),
            people=self.total_people,
            loads=loads,
            capacities=capacities,
        )

    def evaluate(self, selected: np.ndarray, service_level: float) -> Evaluation:
        """Evaluate k candidates (indices), one container each."""
        selected = np.asarray(selected, dtype=int)
        mask = np.zeros(self.size, dtype=bool)
        mask[selected] = True
        local = np.full(self.size, -1, dtype=int)
        local[selected] = np.arange(selected.size)

        hits = mask[self.pixel_neighbours]
        found = hits.any(axis=1)
        first = hits.argmax(axis=1)
        rows = np.arange(len(self.pixels_xy))
        site = local[self.pixel_neighbours[rows, first]]
        dist = self.pixel_dists[rows, first].copy()
        if not found.all():
            tree = cKDTree(self.candidates_xy[selected])
            d, j = tree.query(self.pixels_xy[~found])
            site[~found] = j
            dist[~found] = d
        capacities = np.full(selected.size, float(service_level))
        return self._result(site, dist, selected.size, capacities)

    def evaluate_current(self, service_level: float) -> Evaluation:
        """Evaluate the current layout (a site holds one or more containers)."""
        tree = cKDTree(self.projection.to_xy(self.current_lonlat))
        dist, site = tree.query(self.pixels_xy)
        capacities = self.current_counts * float(service_level)
        return self._result(site, dist, len(self.current_lonlat), capacities)

    # ------------------------------------------------------------------ #
    def cells(self, sites_lonlat: np.ndarray, evaluation: Evaluation) -> dict:
        """GeoJSON FeatureCollection of the Voronoi cells, clipped to the region."""
        xy = self.projection.to_xy(sites_lonlat)
        features = []
        if len(xy) == 1:
            polygons = [self.region_xy]
        else:
            voronoi = shapely.voronoi_polygons(
                shapely.MultiPoint(xy), extend_to=self.region_xy, ordered=True
            )
            polygons = list(voronoi.geoms)
        for i, polygon in enumerate(polygons[: len(xy)]):
            cell = shapely.intersection(polygon, self.region_xy)
            if cell.is_empty:
                continue
            features.append(
                {
                    "type": "Feature",
                    "geometry": shapely.geometry.mapping(self.projection.geometry_to_lonlat(cell)),
                    "properties": {
                        "lon": round(float(sites_lonlat[i][0]), 6),
                        "lat": round(float(sites_lonlat[i][1]), 6),
                        "people": round(float(evaluation.loads[i])),
                        "capacity": round(float(evaluation.capacities[i])),
                    },
                }
            )
        return {"type": "FeatureCollection", "features": features}

    def layout(self, sites_lonlat: np.ndarray, evaluation: Evaluation) -> dict:
        return {"metrics": evaluation.summary(), "cells": self.cells(sites_lonlat, evaluation)}
