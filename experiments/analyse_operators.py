"""Recombination operators (NSGA-II, 4 objectives) at the same number of generations,
evaluations and time -> operators.json (in RESULTS_DIR)

Reads every CITY_nsga2-4_VARIANT_SEED.npz of RESULTS_DIR written by run.py with the
per-generation budget (``evaluations``, ``times``). The hypervolume (HV4) is computed on
objectives normalised per city between the best and worst values of all the final fronts
(inequity from 0, today's layout included), reference point 1.1, as in analyse.py.

Budgets: each run is also scored with the last snapshot (every 10 generations) within the
median final number of evaluations, and the median final time, of the REFERENCE variant
(the proposed operator), so that a cheaper variant run for longer (e.g. no crossover with
1,200 generations) is compared at the same cost.
"""

import glob
import json
import os
import re
from collections import defaultdict

import numpy as np
from common import CITIES, RESULTS, load
from pymoo.indicators.hv import HV
from stats_utils import compare, holm, summary

from services.equity import pixel_unserved
from services.pareto import non_dominated_fronts

BASELINE = os.environ.get("BASELINE", "none")
REFERENCE = os.environ.get("REFERENCE", "partition+mating=size")
EVERY = 10  # run.py keeps one snapshot every EVERY generations, and the last one


def snapshot_generations(n_generations: int, n_snapshots: int) -> np.ndarray:
    gens = list(range(0, n_generations + 1, EVERY))
    if len(gens) < n_snapshots:
        gens.append(n_generations)
    return np.array(gens[:n_snapshots])


def main():
    out = {"baseline": BASELINE, "reference": REFERENCE, "cities": {}}
    for city in CITIES:
        runs = defaultdict(list)
        for f in sorted(glob.glob(os.path.join(RESULTS, f"{city}_nsga2-4_*.npz"))):
            m = re.match(rf"{city}_nsga2-4_(.+)_(\d+)\.npz$", os.path.basename(f))
            runs[m.group(1)].append(np.load(f, allow_pickle=True))
        if not runs:
            continue
        p = load(city)
        k0 = p.current_containers
        ev = p.evaluate_current(1000)
        cur_ineq = p.neighbourhoods.inequity(
            pixel_unserved(p.people, ev.pixel_site, ev.loads, ev.capacities)
        )
        allF = np.vstack([r["front"][:, :4] for rs in runs.values() for r in rs])
        lo = np.array([k0 // 2, allF[:, 1].min(), 0.0, allF[:, 3].min()])
        hi = np.array(
            [
                round(k0 * 1.5),
                max(allF[:, 1].max(), ev.overload),
                max(allF[:, 2].max(), cur_ineq),
                max(allF[:, 3].max(), ev.mean_distance),
            ]
        )
        hv = HV(ref_point=np.full(4, 1.1))

        def H(F, lo=lo, hi=hi, hv=hv):
            F = np.asarray(F, dtype=float)[:, :4]
            F = F[non_dominated_fronts(F)[0]]
            return float(hv((F - lo) / (hi - lo)))

        def at_budget(r, key, budget):
            """HV4 of the last snapshot within the budget (evaluations or seconds)."""
            snaps = r["snapshots"]
            spent = r["times" if key == "time" else key]
            spent = spent[snapshot_generations(len(spent) - 1, len(snaps))]
            i = max(0, int(np.searchsorted(spent, budget, side="right")) - 1)
            return H(snaps[i])

        ref = runs.get(REFERENCE, [])
        budgets = {
            "evaluations": float(np.median([r["evaluations"][-1] for r in ref])) if ref else None,
            "time": float(np.median([r["times"][-1] for r in ref])) if ref else None,
        }
        res = {"bounds": [lo.tolist(), hi.tolist()], "budgets": budgets, "variants": {}}
        for v, rs in sorted(runs.items()):
            entry = {
                "runs": len(rs),
                "hv": [H(r["front"]) for r in rs],
                "evaluations": [int(r["evaluations"][-1]) for r in rs],
                "time": [float(r["times"][-1]) for r in rs],
                "min_unserved": [float(r["front"][:, 1].min()) for r in rs],
                "min_inequity": [float(r["front"][:, 2].min()) for r in rs],
                "min_distance": [float(r["front"][:, 3].min()) for r in rs],
            }
            # With today's number of containers: layouts no worse than today in
            # unserved people and inequity (and distance)
            at_k0 = [r["front"][r["front"][:, 0] == k0] for r in rs]
            better = [f[(f[:, 1] <= ev.overload) & (f[:, 2] <= cur_ineq)] for f in at_k0]
            entry["k0_better_than_current"] = float(np.mean([len(b) > 0 for b in better]))
            entry["k0_better_incl_distance"] = float(
                np.mean([bool((b[:, 3] <= ev.mean_distance).any()) for b in better])
            )
            if any(len(b) for b in better):
                entry["k0_fairest"] = np.median(
                    [b[b[:, 2].argmin()] for b in better if len(b)], 0
                ).tolist()
                entry["k0_closest"] = np.median(
                    [b[b[:, 3].argmin()] for b in better if len(b)], 0
                ).tolist()
            for key, budget in budgets.items():
                if budget is not None:
                    entry[f"hv_at_{key}"] = [at_budget(r, key, budget) for r in rs]
            # HV4 against time on a common grid (anytime curves), up to twice the budget
            if budgets["time"]:
                grid = np.linspace(0, 2 * budgets["time"], 41)
                curves = []
                for r in rs:
                    snaps = r["snapshots"]
                    times = r["times"][snapshot_generations(len(r["times"]) - 1, len(snaps))]
                    hvs = np.array([H(x) for x in snaps])
                    idx = np.searchsorted(times, grid, side="right") - 1
                    curves.append(np.where(idx >= 0, hvs[np.maximum(idx, 0)], np.nan))
                curves = np.array(curves)
                entry["curve"] = {
                    "time": grid.tolist(),
                    "mean": np.nanmean(curves, 0).tolist(),
                    "sd": np.nanstd(curves, 0).tolist(),
                    "final_time": float(np.median([r["times"][-1] for r in rs])),
                }
            entry["summary"] = {
                k: summary(entry[k])
                for k in ("hv", "hv_at_evaluations", "hv_at_time", "evaluations", "time")
                if k in entry
            }
            res["variants"][v] = entry
        # Every variant against the baseline, Holm-corrected per city and measure
        if BASELINE in runs:
            for measure in ("hv", "hv_at_evaluations", "hv_at_time"):
                others = [v for v in res["variants"] if v != BASELINE]
                tests = [
                    compare(res["variants"][v][measure], res["variants"][BASELINE][measure])
                    for v in others
                    if measure in res["variants"][v]
                ]
                for v, t, padj in zip(others, tests, holm([t["p"] for t in tests]), strict=True):
                    res["variants"][v].setdefault("vs_baseline", {})[measure] = {
                        **t,
                        "p_holm": float(padj),
                    }
        # The reference against every other variant
        if REFERENCE in runs:
            for measure in ("hv", "hv_at_evaluations", "hv_at_time"):
                others = [v for v in res["variants"] if v != REFERENCE]
                tests = [
                    compare(res["variants"][REFERENCE][measure], res["variants"][v][measure])
                    for v in others
                ]
                for v, t, padj in zip(others, tests, holm([t["p"] for t in tests]), strict=True):
                    res["variants"][v].setdefault("reference_vs", {})[measure] = {
                        **t,
                        "p_holm": float(padj),
                    }
        res["current"] = [k0, ev.overload, cur_ineq, ev.mean_distance]
        out["cities"][city] = res
        print(city, {k: round(v) if v else v for k, v in budgets.items()})
        for v, e in res["variants"].items():
            s = e["summary"]
            vs = e.get("vs_baseline", {})
            cells = []
            for k in ("hv", "hv_at_evaluations", "hv_at_time"):
                if k in s:
                    star = "*" if k in vs and vs[k]["p_holm"] < 0.05 else ""
                    vs_text = f" (A={vs[k]['a12']:.2f}{star})" if k in vs else ""
                    cells.append(f"{s[k]['mean']:.4f}{vs_text}")
            print(f"  {v:55s} " + "  ".join(cells) + f"  t={s['time']['mean']:.0f}s")
    path = os.path.join(RESULTS, "operators.json")
    with open(path, "w") as f:
        json.dump(out, f)
    print(path)


if __name__ == "__main__":
    main()
