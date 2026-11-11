"""Exact decomposition of pairs of layouts: python components.py -> components.json (in RESULTS_DIR)

For pairs of layouts with the same number of containers from the final fronts of the runs
of VARIANT (seeds 1-10), the number of independent components into which their differences
split (ParetoAlgorithm.components). Partition crossover in the sense of Whitley et al. needs
many components; one means that no part of a parent can be exchanged independently.
"""

import glob
import itertools
import json
import os

import numpy as np
from common import CITIES, RESULTS, load

from services.pareto import ParetoAlgorithm, ParetoParameters

VARIANT = os.environ.get("VARIANT", "partition+mating=size+centroid_moves=0.8+init=mixed")
PAIRS = 10  # per size level and run

out = {}
for city in CITIES:
    files = sorted(glob.glob(os.path.join(RESULTS, f"{city}_nsga2-4_{VARIANT}_*.npz")))[:10]
    if not files:
        continue
    p = load(city)
    k0 = p.current_containers
    alg = ParetoAlgorithm(
        p, ParetoParameters(min_containers=k0 // 2, max_containers=round(k0 * 1.5))
    )
    rng = np.random.default_rng(0)
    rows = []
    for f in files:
        layouts = [np.asarray(x, dtype=int) for x in np.load(f, allow_pickle=True)["layouts"]]
        by_size = {}
        for x in layouts:
            by_size.setdefault(x.size, []).append(x)
        for k, xs in by_size.items():
            pairs = list(itertools.combinations(range(len(xs)), 2))
            for i in rng.permutation(len(pairs))[:PAIRS]:
                a, b = xs[pairs[i][0]], xs[pairs[i][1]]
                differ = np.setxor1d(a, b).size
                if not differ:
                    continue
                union, labels, _, _, comps = alg.components(a, b)
                sizes = np.bincount(labels[np.isin(union, np.setxor1d(a, b))])
                rows.append(
                    {
                        "size": int(k),
                        "differing_sites": int(differ),
                        "components": int(comps.sum()),
                        "largest_share": float(sizes.max() / sizes.sum()),
                    }
                )
    comps = np.array([r["components"] for r in rows])
    out[city] = {
        "pairs": len(rows),
        "single_component": float(np.mean(comps == 1)),
        "median_components": float(np.median(comps)),
        "mean_largest_share": float(np.mean([r["largest_share"] for r in rows])),
        "median_differing_sites": float(np.median([r["differing_sites"] for r in rows])),
        "rows": rows,
    }
    print(city, {k: v for k, v in out[city].items() if k != "rows"})
with open(os.path.join(RESULTS, "components.json"), "w") as f:
    json.dump(out, f)
