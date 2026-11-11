"""Quality of the initial layouts at today's number of containers: python seeds.py -> seeds.json

N layouts per city of each initialisation (random, demand-weighted k-means++ with exponents
0, 1 and 2, balanced recursive bisection) and today's layout: unserved people, inequity and
mean distance, and the time to build one.
"""

import json
import os
import time

import numpy as np
from common import CITIES, RESULTS, load

from services.pareto import ParetoAlgorithm, ParetoParameters

N = int(os.environ.get("N", 30))


def study(city: str) -> dict:
    p = load(city)
    k0 = p.current_containers
    alg = ParetoAlgorithm(
        p, ParetoParameters(min_containers=k0 // 2, max_containers=round(k0 * 1.5), seed=1)
    )

    def measure(x):
        m = alg.measure(x, diagnostics=False)
        return [m["unserved"], m["inequity"], m["evaluation"].mean_distance]

    makers = {
        "random": lambda: np.sort(alg.rng.choice(p.size, k0, replace=False)),
        "demand-0": lambda: alg.demand_layout(k0, 0.0),
        "demand-1": lambda: alg.demand_layout(k0, 1.0),
        "demand-2": lambda: alg.demand_layout(k0, 2.0),
        "balanced": lambda: alg.balanced_layout(k0),
    }
    res = {"current": measure(alg.seeds()[0]), "k0": k0}
    for name, make in makers.items():
        t = time.perf_counter()
        layouts = [make() for _ in range(N)]
        ms = (time.perf_counter() - t) / N * 1000
        res[name] = {"values": [measure(x) for x in layouts], "ms": ms}
    return res


out = {}
for city in CITIES:
    out[city] = study(city)
    summary = {
        k: np.mean(v["values"], 0).round(3).tolist()
        for k, v in out[city].items()
        if isinstance(v, dict)
    }
    print(city, summary)
with open(os.path.join(RESULTS, "seeds.json"), "w") as f:
    json.dump(out, f)
