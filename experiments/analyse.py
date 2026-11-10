"""Hypervolume and statistics of the runs in results/ -> analysis.json + LaTeX snippets."""

import glob
import json
import os

import numpy as np
from common import CITIES, RESULTS, load
from pymoo.indicators.hv import HV
from scipy import stats

from services.equity import pixel_unserved

VARIANTS = ["uniform", "regional"]
out = {}


def a12(x, y):
    """Vargha-Delaney A: probability that a run of x beats a run of y."""
    x, y = np.asarray(x), np.asarray(y)
    return float(
        ((x[:, None] > y[None, :]).sum() + 0.5 * (x[:, None] == y[None, :]).sum())
        / (x.size * y.size)
    )


for city in CITIES:
    runs = {
        v: [
            np.load(f, allow_pickle=True)
            for f in sorted(glob.glob(os.path.join(RESULTS, f"{city}_{v}_*.npz")))
        ]
        for v in VARIANTS
    }
    if not all(runs.values()):
        continue
    p = load(city)
    k0 = p.current_containers
    ev = p.evaluate_current(1000)
    cur_ineq = p.neighbourhoods.inequity(
        pixel_unserved(p.people, ev.pixel_site, ev.loads, ev.capacities)
    )
    current = np.array([k0, ev.overload, cur_ineq, ev.mean_distance, ev.p95_distance])

    allF = np.vstack([r["front"][:, :3] for v in VARIANTS for r in runs[v]])
    lo = np.array([k0 // 2, allF[:, 1].min(), 0.0])
    hi = np.array([round(k0 * 1.5), allF[:, 1].max(), max(allF[:, 2].max(), cur_ineq)])
    hv = HV(ref_point=np.full(3, 1.1))

    def H(F, hv=hv, lo=lo, hi=hi):
        return float(hv((np.asarray(F, float)[:, :3] - lo) / (hi - lo)))

    res = {"current": current.round(4).tolist(), "bounds": [lo.tolist(), hi.tolist()]}
    for v in VARIANTS:
        hvs = [H(r["front"]) for r in runs[v]]
        conv = np.array([[H(s) for s in r["snapshots"]] for r in runs[v]])
        # Layouts with today's number of containers: best unserved and best inequity
        at_k0 = [r["front"][r["front"][:, 0] == k0] for r in runs[v]]
        dom = [int(((f[:, 1] <= ev.overload) & (f[:, 2] <= cur_ineq)).sum() > 0) for f in at_k0]
        dom_dist = [
            int(
                (
                    (f[:, 1] <= ev.overload) & (f[:, 2] <= cur_ineq) & (f[:, 3] <= ev.mean_distance)
                ).sum()
                > 0
            )
            for f in at_k0
        ]
        best_u = [f[:, 1].min() for f in at_k0 if len(f)]
        best_i = [f[:, 2].min() for f in at_k0 if len(f)]
        # The layout of each run at k0 with the fewest unserved people
        pick = [f[f[:, 1].argmin()] for f in at_k0 if len(f)]
        res[v] = {
            "runs": len(hvs),
            "hv": hvs,
            "hv_mean": float(np.mean(hvs)),
            "hv_sd": float(np.std(hvs, ddof=1)),
            "hv_median": float(np.median(hvs)),
            "hv_iqr": float(np.subtract(*np.percentile(hvs, [75, 25]))),
            "shapiro_p": float(stats.shapiro(hvs).pvalue),
            "convergence_mean": conv.mean(0).tolist(),
            "convergence_sd": conv.std(0).tolist(),
            "front_size": float(np.mean([len(r["front"]) for r in runs[v]])),
            "elapsed": float(np.mean([float(r["elapsed"]) for r in runs[v]])),
            "k0_dominates_current": float(np.mean(dom)),
            "k0_dominates_current_with_distance": float(np.mean(dom_dist)),
            "k0_best_unserved_median": float(np.median(best_u)) if best_u else None,
            "k0_best_inequity_median": float(np.median(best_i)) if best_i else None,
            "k0_min_unserved_layout_median": np.median(pick, axis=0).tolist() if pick else None,
        }
    x, y = res["regional"]["hv"], res["uniform"]["hv"]
    res["mannwhitney_p"] = float(stats.mannwhitneyu(x, y, alternative="two-sided").pvalue)
    res["a12_regional_vs_uniform"] = a12(x, y)
    single = [json.load(open(f)) for f in glob.glob(os.path.join(RESULTS, f"single_{city}_*.json"))]
    if single:
        res["single"] = {
            key: float(np.median([r[key] for r in single]))
            for key in ("unserved", "inequity", "mean_distance", "p95")
        }
        res["single"]["runs"] = len(single)
    out[city] = res
    print(
        f"{city:10s} HV RX {res['regional']['hv_mean']:.4f}±{res['regional']['hv_sd']:.4f} "
        f"UX {res['uniform']['hv_mean']:.4f}±{res['uniform']['hv_sd']:.4f} "
        f"p={res['mannwhitney_p']:.2e} A12={res['a12_regional_vs_uniform']:.2f} | "
        f"runs {res['regional']['runs']}/{res['uniform']['runs']} | "
        f"t {res['regional']['elapsed']:.0f}/{res['uniform']['elapsed']:.0f}s | "
        f"dom.cur RX {res['regional']['k0_dominates_current']:.2f} "
        f"UX {res['uniform']['k0_dominates_current']:.2f}"
    )
    print(
        f"   current k0={k0} unserved {ev.overload:.0f} ineq {cur_ineq:.4f} dist "
        f"{ev.mean_distance:.0f} p95 {ev.p95_distance:.0f}; RX@k0 min-unserved layout "
        f"{np.round(res['regional']['k0_min_unserved_layout_median'], 4).tolist()}; "
        f"best ineq {res['regional']['k0_best_inequity_median']:.4f}"
    )

with open(os.path.join(RESULTS, "analysis.json"), "w") as file:
    json.dump(out, file, indent=1)
