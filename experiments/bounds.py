"""How far from optimal is the accessibility of our layouts? -> results/bounds.json

With today's number of containers k0, minimising the mean distance f4 is the
(uncapacitated) p-median problem on the same candidates and population pixels.
A Lagrangian relaxation of the assignment constraints gives a valid lower bound
(Beasley, 1993); its subproblem solutions, evaluated exactly, give feasible
layouts (upper bounds). Subgradient optimisation with Polyak steps.
"""

import glob
import json
import os

import numpy as np
from common import CITIES, RESULTS, load


def lagrangian_pmedian(dist, weight, k, iterations=None, target=None):
    """Lower bound, best feasible value and its sites for the p-median problem.

    dist: (demand, candidates) distances; weight: demand weights; values are
    normalised by the total weight (a mean distance). ``target``: the value of
    a known feasible solution, used for the step size if better.
    """
    iterations = iterations or int(os.environ.get("ITERATIONS", 3000))
    total = weight.sum()
    cost = (dist * (weight / total)[:, None]).astype(np.float64)  # demand x candidates
    lam = cost.min(axis=1).copy()  # multipliers of "each demand assigned once"
    best_lb, best_ub, best_sites = -np.inf, np.inf, None
    step_scale = 2.0
    stall = 0
    for _ in range(iterations):
        reduced = np.minimum(cost - lam[:, None], 0.0)  # x_ij = 1 where negative
        rho = reduced.sum(axis=0)
        open_ = np.argpartition(rho, k)[:k]
        lb = lam.sum() + rho[open_].sum()
        if lb > best_lb + 1e-12:
            best_lb, stall = lb, 0
        else:
            stall += 1
            if stall >= 100:  # halve the step when the bound stalls
                step_scale, stall = step_scale / 2, 0
        ub = cost[:, open_].min(axis=1).sum()  # exact value of the open sites
        if ub < best_ub:
            best_ub, best_sites = ub, np.sort(open_)
        # subgradient: 1 - number of open sites each demand is assigned to
        assigned = (reduced[:, open_] < 0).sum(axis=1)
        g = 1.0 - assigned
        norm = float(g @ g)
        if norm == 0 or step_scale < 1e-3:
            break
        reference = min(best_ub, target) if target else best_ub
        lam = lam + step_scale * max(reference - lb, 1e-9) / norm * g
    return best_lb, best_ub, best_sites


def improve(dist, weight, sites):
    """Alternating (Maranzana) local search: assign each demand to its nearest
    open site, move each site to the candidate that best serves its demands,
    repeat until nothing changes. Returns the sites and their mean distance."""
    w = weight / weight.sum()
    sites = np.array(sorted(sites))
    while True:
        assign = dist[:, sites].argmin(axis=1)
        new = sites.copy()
        taken = set(sites.tolist())
        for c in range(sites.size):
            members = assign == c
            if not members.any():
                continue
            cost = w[members] @ dist[members]
            for candidate in np.argsort(cost):
                if candidate == sites[c] or candidate not in taken:
                    break
            taken.discard(sites[c])
            taken.add(int(candidate))
            new[c] = candidate
        if np.array_equal(np.sort(new), sites):
            return sites, float(w @ dist[:, sites].min(axis=1))
        sites = np.sort(new)


out = {}
analysis_file = os.path.join(RESULTS, "analysis.json")
analysis = json.load(open(analysis_file)) if os.path.exists(analysis_file) else {}
for city in os.environ.get("CITY", " ".join(CITIES)).split():
    p = load(city)
    k0 = p.current_containers
    d = np.sqrt(((p.pixels_xy[:, None, :] - p.candidates_xy[None, :, :]) ** 2).sum(-1))
    a = analysis.get(city, {})
    target = a.get("single", {}).get("mean_distance")
    d = d.astype(np.float32)
    lb, ub, sites = lagrangian_pmedian(d, p.people, k0, target=target)
    improved = {"lagrangian": improve(d, p.people, sites)}
    # The layouts with k0 containers of the main fronts: the closest one, improved
    best_front, best_layout = np.inf, None
    for f in glob.glob(os.path.join(RESULTS, f"{city}_nsga2-4_regional_*.npz")):
        run = np.load(f, allow_pickle=True)
        for row, layout in zip(run["front"], run["layouts"], strict=True):
            if row[0] == k0 and row[3] < best_front:
                best_front, best_layout = row[3], np.asarray(layout, dtype=int)
    if best_layout is not None:
        improved["front"] = improve(d, p.people, best_layout)
    best_sites, best_known = min(improved.values(), key=lambda sv: sv[1])
    single = a.get("single", {}).get("mean_distance")
    best_known = min(best_known, ub, single or np.inf)
    ev = p.evaluate(best_sites, 1000)
    eq = p.equity(ev)
    out[city] = {
        "k0": k0,
        "lower_bound": lb,
        "lagrangian_heuristic": ub,
        "best_known": best_known,
        "single": single,
        "front_closest": best_front,
        "best_known_layout": {
            "unserved": ev.overload,
            "inequity": eq["inequity"],
            "mean_distance": ev.mean_distance,
            "p95": ev.p95_distance,
        },
    }
    print(
        f"{city:10s} k0={k0} LB {lb:6.1f}  best known {best_known:6.1f} "
        f"(gap {best_known / lb - 1:.1%}, "
        f"inequity {eq['inequity'] * 100:.1f} pts)  single {single or float('nan'):6.1f}  "
        f"front closest {best_front:6.1f} (+{best_front / best_known - 1:.1%} vs best known)",
        flush=True,
    )

name = f"bounds_{os.environ['CITY']}.json" if "CITY" in os.environ else "bounds.json"
with open(os.path.join(RESULTS, name), "w") as file:
    json.dump(out, file, indent=1)
