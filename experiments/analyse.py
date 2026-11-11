"""Hypervolume, statistics and comparison with today's layouts -> results/analysis.json

Variants: algorithm (nsga2, nsga3) x objectives (3, 4) x crossover (regional, uniform).
Each front is scored with the hypervolume of its own objectives (HV3 or HV4) and, to
compare the formulations, with HV4 (every front records the distance of its layouts).
"""

import glob
import itertools
import json
import os

import numpy as np
from common import CITIES, RESULTS, load
from pymoo.indicators.hv import HV
from scipy import stats

from services.equity import pixel_unserved
from services.pareto import non_dominated_fronts

ALGORITHMS, OBJECTIVES, CROSSOVERS = ("nsga2", "nsga3"), (3, 4), ("regional", "uniform")
VARIANTS = [f"{a}-{o}_{x}" for a, o, x in itertools.product(ALGORITHMS, OBJECTIVES, CROSSOVERS)]


def a12(x, y):
    """Vargha-Delaney A: probability that a run of x beats a run of y (higher is better)."""
    x, y = np.asarray(x), np.asarray(y)
    wins = (x[:, None] > y[None, :]).sum() + 0.5 * (x[:, None] == y[None, :]).sum()
    return float(wins / (x.size * y.size))


def compare(x, y):
    return {"p": float(stats.mannwhitneyu(x, y, alternative="two-sided").pvalue), "a12": a12(x, y)}


def holm(pvalues):
    """Holm-Bonferroni adjusted p-values."""
    p = np.asarray(pvalues, dtype=float)
    order = np.argsort(p)
    adjusted = np.maximum.accumulate((p.size - np.arange(p.size)) * p[order])
    out = np.empty_like(p)
    out[order] = np.minimum(adjusted, 1.0)
    return out


def summary(values):
    v = np.asarray(values, dtype=float)
    return {
        "mean": float(v.mean()),
        "sd": float(v.std(ddof=1)),
        "median": float(np.median(v)),
        "iqr": float(np.subtract(*np.percentile(v, [75, 25]))),
    }


out = {}
for city in CITIES:
    runs = {
        v: [
            np.load(f, allow_pickle=True)
            for f in sorted(glob.glob(os.path.join(RESULTS, f"{city}_{v}_*.npz")))
        ]
        for v in VARIANTS
    }
    runs = {v: r for v, r in runs.items() if r}
    if not runs:
        continue
    p = load(city)
    k0 = p.current_containers
    ev = p.evaluate_current(1000)
    cur_ineq = p.neighbourhoods.inequity(
        pixel_unserved(p.people, ev.pixel_site, ev.loads, ev.capacities)
    )
    current = np.array([k0, ev.overload, cur_ineq, ev.mean_distance, ev.p95_distance])

    # front rows: containers, unserved, inequity, mean distance, p95, Moran's I
    allF = np.vstack([r["front"][:, :4] for rs in runs.values() for r in rs])
    lo = np.array([k0 // 2, allF[:, 1].min(), 0.0, allF[:, 3].min()])
    hi = np.array(
        [
            round(k0 * 1.5),
            allF[:, 1].max(),
            max(allF[:, 2].max(), cur_ineq),
            max(allF[:, 3].max(), ev.mean_distance),
        ]
    )
    hv3, hv4 = HV(ref_point=np.full(3, 1.1)), HV(ref_point=np.full(4, 1.1))

    def H(F, m, lo=lo, hi=hi, hv3=hv3, hv4=hv4):
        F = np.asarray(F, dtype=float)[:, :m]
        F = F[non_dominated_fronts(F)[0]]
        return float((hv3 if m == 3 else hv4)((F - lo[:m]) / (hi[:m] - lo[:m])))

    res = {
        "current": current.round(4).tolist(),
        "bounds": [lo.tolist(), hi.tolist()],
        "variants": {},
    }
    for v, rs in runs.items():
        m = int(v.split("_")[0].split("-")[1])
        own = [H(r["front"], m) for r in rs]
        conv = np.array([[H(s, m) for s in r["snapshots"]] for r in rs])
        at_k0 = [r["front"][r["front"][:, 0] == k0] for r in rs]
        better = [f[(f[:, 1] <= ev.overload) & (f[:, 2] <= cur_ineq)] for f in at_k0]
        res["variants"][v] = {
            "runs": len(rs),
            "hv": own,
            "hv_summary": summary(own),
            "hv3": [H(r["front"], 3) for r in rs],
            "hv4": [H(r["front"], 4) for r in rs],
            "convergence_mean": conv.mean(0).tolist(),
            "convergence_sd": conv.std(0).tolist(),
            "front_size": float(np.mean([len(r["front"]) for r in rs])),
            "elapsed": float(np.mean([float(r["elapsed"]) for r in rs])),
            # with today's number of containers
            "k0_better_than_current": float(np.mean([len(b) > 0 for b in better])),
            "k0_better_incl_distance": float(
                np.mean([bool((b[:, 3] <= ev.mean_distance).any()) for b in better])
            ),
            "k0_fairest": np.median([b[b[:, 2].argmin()] for b in better if len(b)], 0).tolist(),
            "k0_closest": np.median([b[b[:, 3].argmin()] for b in better if len(b)], 0).tolist(),
            "k0_fewest_unserved": np.median(
                [f[f[:, 1].argmin()] for f in at_k0 if len(f)], 0
            ).tolist(),
        }
        res["variants"][v]["hv3_summary"] = summary(res["variants"][v]["hv3"])
        res["variants"][v]["hv4_summary"] = summary(res["variants"][v]["hv4"])

    # Comparisons, Holm-adjusted within the city
    V = res["variants"]
    tests = {}
    for a, o in itertools.product(ALGORITHMS, OBJECTIVES):
        x, y = f"{a}-{o}_regional", f"{a}-{o}_uniform"
        if x in V and y in V:
            tests[f"crossover {a}-{o}"] = compare(V[x]["hv"], V[y]["hv"])
    for o in OBJECTIVES:
        x, y = f"nsga3-{o}_regional", f"nsga2-{o}_regional"
        if x in V and y in V:
            tests[f"algorithm {o}"] = compare(V[x]["hv"], V[y]["hv"])
    for a in ALGORITHMS:
        x, y = f"{a}-4_regional", f"{a}-3_regional"
        if x in V and y in V:
            tests[f"formulation {a}"] = compare(V[x]["hv4"], V[y]["hv4"])
            tests[f"formulation-hv3 {a}"] = compare(V[x]["hv3"], V[y]["hv3"])
    if tests:
        adjusted = holm([t["p"] for t in tests.values()])
        for t, q in zip(tests.values(), adjusted, strict=True):
            t["p_holm"] = float(q)
    res["tests"] = tests

    single = [json.load(open(f)) for f in glob.glob(os.path.join(RESULTS, f"single_{city}_*.json"))]
    if single:
        res["single"] = {
            key: float(np.median([r[key] for r in single]))
            for key in ("unserved", "inequity", "mean_distance", "p95")
        }
        res["single"]["runs"] = len(single)
    out[city] = res

    print(
        f"== {city}: current unserved {ev.overload:.0f} ineq {cur_ineq * 100:.1f} "
        f"dist {ev.mean_distance:.0f}; single {res.get('single')}"
    )
    for v in VARIANTS:
        if v in V:
            s = V[v]
            print(
                f"  {v:18s} HV {s['hv_summary']['mean']:.4f}±{s['hv_summary']['sd']:.4f} "
                f"HV4 {s['hv4_summary']['mean']:.4f} front {s['front_size']:5.1f} "
                f"t {s['elapsed']:4.0f}s better {s['k0_better_than_current']:.2f}/"
                f"{s['k0_better_incl_distance']:.2f} fairest {np.round(s['k0_fairest'][1:4], 3)} "
                f"closest {np.round(s['k0_closest'][1:4], 3)}"
            )
    for name, t in tests.items():
        print(f"  {name:22s} A12 {t['a12']:.2f} p_holm {t['p_holm']:.1e}")

with open(os.path.join(RESULTS, "analysis.json"), "w") as file:
    json.dump(out, file, indent=1)
