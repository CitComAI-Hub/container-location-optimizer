"""Moran's I as an objective (the earlier formulation): python moran.py CITY"""

import sys

import numpy as np
from common import load

SL = 1000.0


def moran_original(problem, selected, ev):
    """As in the 2025 code: Moran's I of the coverage excess of the active
    sites, inverse-distance weights between them, row-standardised."""
    excess = np.clip(ev.loads - ev.capacities, 0, None)
    n = excess.size
    if n < 2 or np.var(excess) == 0:
        return 0.0
    xy = problem.candidates_xy[selected]
    d = np.hypot(*(xy[:, None, :] - xy[None, :, :]).transpose(2, 0, 1))
    with np.errstate(divide="ignore"):
        w = np.where(d > 0, 1 / d, 0.0)
    w /= w.sum(1, keepdims=True)
    z = excess - excess.mean()
    return float(n / w.sum() * (z @ w @ z) / (z @ z))


def neighbour(problem, sel, rng):
    sel = sel.copy()
    i = rng.integers(sel.size)
    options = [c for c in problem.candidate_neighbours[sel[i]] if c not in set(sel)]
    if options:
        sel[i] = rng.choice(options)
    return np.sort(sel)


city = sys.argv[1] if len(sys.argv) > 1 else "donostia"
p = load(city)
rng = np.random.default_rng(0)
k0 = p.current_containers
print(f"== {city}: {p.size} candidates, {k0} current, {p.total_people:.0f} people")

print(
    "k=2 random layouts, original I:",
    sorted(
        {
            round(moran_original(p, s, p.evaluate(s, SL)), 3)
            for s in (np.sort(rng.choice(p.size, 2, replace=False)) for _ in range(20))
        }
    ),
)

for k in (k0 // 2, k0, int(k0 * 1.5), int(p.total_people / SL * 1.3)):
    vals = []
    for _ in range(30):
        s = np.sort(rng.choice(p.size, k, replace=False))
        ev = p.evaluate(s, SL)
        vals.append((moran_original(p, s, ev), ev.overload, (ev.loads > ev.capacities).mean()))
    v = np.array(vals)
    print(
        f"k={k:4d} random: I mean {v[:, 0].mean():+.3f} sd {v[:, 0].std():.3f} "
        f"[{v[:, 0].min():+.3f},{v[:, 0].max():+.3f}]  overload {v[:, 1].mean():.0f}  "
        f"overloaded sites {v[:, 2].mean():.0%}"
    )

# Landscape: a layout and its one-move neighbour (k = current)
pairs = []
for _ in range(200):
    s = np.sort(rng.choice(p.size, k0, replace=False))
    t = neighbour(p, s, rng)
    a, b = p.evaluate(s, SL), p.evaluate(t, SL)
    pairs.append(
        (
            moran_original(p, s, a),
            moran_original(p, t, b),
            a.overload,
            b.overload,
            a.mean_distance,
            b.mean_distance,
        )
    )
q = np.array(pairs)
for name, i in (("Moran I", 0), ("overload", 2), ("mean distance", 4)):
    r = np.corrcoef(q[:, i], q[:, i + 1])[0, 1]
    print(f"one-move correlation of {name}: {r:.3f}")
