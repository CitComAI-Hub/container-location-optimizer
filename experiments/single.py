"""The single-objective GA at today's number of containers: python single.py CITY SEED"""

import json
import os
import sys

from common import RESULTS, load

from services.genetic import GeneticAlgorithm, Parameters

city, seed = sys.argv[1], int(sys.argv[2])
out = os.path.join(RESULTS, f"single_{city}_{seed}.json")
if os.path.exists(out):
    sys.exit(0)
p = load(city)
params = Parameters(containers=p.current_containers, generations=300, seed=seed)
best, _ = GeneticAlgorithm(p, params).run()
ev = p.evaluate(best, 1000)
equity = p.equity(ev)
os.makedirs(RESULTS, exist_ok=True)
with open(out, "w") as file:
    json.dump(
        {
            "unserved": ev.overload,
            "inequity": equity["inequity"],
            "morans_i": equity["morans_i"],
            "mean_distance": ev.mean_distance,
            "p95": ev.p95_distance,
        },
        file,
    )
print(out)
