"""One run of the trade-off algorithm: python run.py CITY ALGORITHM OBJECTIVES CROSSOVER SEED

ALGORITHM nsga2 or nsga3, OBJECTIVES 3 or 4 (4: plus mean distance), CROSSOVER regional or uniform.
Writes results/CITY_ALGORITHM-OBJECTIVES_CROSSOVER_SEED.npz.
"""

import os
import sys
import time

import numpy as np
from common import RESULTS, load

from services.pareto import ParetoAlgorithm, ParetoParameters

GENS = int(os.environ.get("GENS", 300))
EVERY = 10

city, algorithm, n_obj, cx, seed = (
    sys.argv[1],
    sys.argv[2],
    int(sys.argv[3]),
    sys.argv[4],
    int(sys.argv[5]),
)
out = os.path.join(RESULTS, f"{city}_{algorithm}-{n_obj}_{cx}_{seed}.npz")
if os.path.exists(out):
    sys.exit(0)
p = load(city)
k0 = p.current_containers


class Recorded(ParetoAlgorithm):
    snapshots: list = []

    def _rank(self, F):
        rank, crowd = super()._rank(F)
        self.snapshots.append(F[rank == 0].copy())
        return rank, crowd


params = ParetoParameters(
    min_containers=k0 // 2,
    max_containers=int(round(k0 * 1.5)),
    generations=GENS,
    crossover=cx,
    algorithm=algorithm,
    distance=n_obj == 4,
    seed=seed,
)
alg = Recorded(p, params)
t = time.time()
front, history = alg.run()
elapsed = time.time() - t
rows = []
for x in front:
    m = alg.measure(x)
    e = m["evaluation"]
    rows.append(
        [
            m["containers"],
            m["unserved"],
            m["inequity"],
            e.mean_distance,
            e.p95_distance,
            np.nan if m["morans_i"] is None else m["morans_i"],
        ]
    )
snaps = alg.snapshots[::EVERY] + alg.snapshots[-1:]
os.makedirs(RESULTS, exist_ok=True)
np.savez_compressed(
    out,
    front=np.array(rows),
    elapsed=elapsed,
    snapshots=np.array(snaps, dtype=object),
    levels=alg.levels,
    layouts=np.array([x for x in front], dtype=object),
)
print(out, f"{elapsed:.0f}s", len(front))
