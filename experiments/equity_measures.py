"""Is spatial inequity robust to its parameters, and different from classical
(non-spatial) equity measures? -> results/equity_measures.json

Layouts: those with today's number of containers in the fronts of the main
configuration (NSGA-II, 4 objectives, regional crossover; 30 runs). For each:
f3 with three block sizes / radii, Moran's I of the blocks, and classical
measures of the list of Marsh and Schilling (1994) on the population: the
population-weighted Gini of the unserved share of each person, of the load per
container, and of the distance to the nearest container.
"""

import glob
import json
import os

import numpy as np
from common import CITIES, RESULTS, load
from scipy import stats

from services.equity import Neighbourhoods, pixel_unserved

SETTINGS = {"250/500": (250.0, 500.0), "500/1000": (500.0, 1000.0), "1000/2000": (1000.0, 2000.0)}
VARIANT = "nsga2-4_regional"


def weighted_gini(values, weights):
    """Gini coefficient of values carried by weights (e.g. people)."""
    order = np.argsort(values)
    v, w = np.asarray(values, float)[order], np.asarray(weights, float)[order]
    cw = np.cumsum(w)
    cvw = np.cumsum(v * w)
    if cvw[-1] == 0:
        return 0.0
    # area under the Lorenz curve by trapezoids
    lorenz = np.concatenate(([0], cvw / cvw[-1]))
    population = np.concatenate(([0], cw / cw[-1]))
    return float(1 - np.sum((population[1:] - population[:-1]) * (lorenz[1:] + lorenz[:-1])))


out = {}
for city in CITIES:
    p = load(city)
    k0 = p.current_containers
    nbs = {
        name: Neighbourhoods.build(p.pixels_xy, p.people, c, r) for name, (c, r) in SETTINGS.items()
    }
    rows = []
    for f in sorted(glob.glob(os.path.join(RESULTS, f"{city}_{VARIANT}_*.npz"))):
        run = np.load(f, allow_pickle=True)
        for front_row, layout in zip(run["front"], run["layouts"], strict=True):
            if front_row[0] != k0:
                continue
            ev = p.evaluate(np.asarray(layout, dtype=int), 1000)
            unserved = pixel_unserved(p.people, ev.pixel_site, ev.loads, ev.capacities)
            share = unserved / p.people
            row = {f"f3 {name}": nb.inequity(unserved) for name, nb in nbs.items()}
            row["Moran's I"] = nbs["500/1000"].morans_i(unserved) or 0.0
            row["Gini unserved share"] = weighted_gini(share, p.people)
            row["Gini load"] = weighted_gini(ev.loads, np.ones_like(ev.loads))
            row["CV load"] = float(ev.loads.std() / ev.loads.mean())
            row["Gini distance"] = weighted_gini(ev.pixel_distance, p.people)
            row["unserved"] = ev.overload
            row["mean distance"] = ev.mean_distance
            rows.append(row)
    names = list(rows[0])
    M = np.array([[r[n] for n in names] for r in rows])
    rho = stats.spearmanr(M).statistic
    out[city] = {"layouts": len(rows), "measures": names, "spearman": np.round(rho, 3).tolist()}
    ref = names.index("f3 500/1000")
    print(f"== {city}: {len(rows)} layouts with k0={k0}; Spearman with f3 500/1000:")
    print("   " + ", ".join(f"{n} {rho[ref, i]:+.2f}" for i, n in enumerate(names) if i != ref))

with open(os.path.join(RESULTS, "equity_measures.json"), "w") as file:
    json.dump(out, file, indent=1)
