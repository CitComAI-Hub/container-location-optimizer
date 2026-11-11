"""Graph crossover, ablation and sensitivity of the equity measure.

Reads the main results (``RESULTS_DIR``, with analysis.json) and the revision
runs (``REVISION_DIR``) -> REVISION_DIR/revision.json. HV4 uses the
normalisation bounds of the main analysis, so it is comparable with it; the
sensitivity runs (other block sizes) are normalised among themselves.
"""

import glob
import json
import os
import re
from collections import defaultdict

import numpy as np
from common import CITIES, RESULTS
from pymoo.indicators.hv import HV
from stats_utils import compare, holm, summary

from services.pareto import non_dominated_fronts

REVISION = os.environ.get("REVISION_DIR", RESULTS + "_rev")
MAIN = "nsga2-4_regional"
main = json.load(open(os.path.join(RESULTS, "analysis.json")))
hv4 = HV(ref_point=np.full(4, 1.1))


def score(front, lo, hi):
    F = np.asarray(front, dtype=float)[:, :4]
    F = F[non_dominated_fronts(F)[0]]
    return float(hv4((F - lo) / (hi - lo)))


def runs(directory, city, variant):
    """Fronts of the runs of a variant (its name without the seed)."""
    pattern = os.path.join(directory, f"{city}_{variant}_*.npz")
    files = [f for f in glob.glob(pattern) if re.fullmatch(r"\d+", f.rsplit("_", 1)[1][:-4])]
    return [np.load(f, allow_pickle=True)["front"] for f in sorted(files)]


def variants_in(directory, city):
    names = set()
    for f in glob.glob(os.path.join(directory, f"{city}_*.npz")):
        names.add(os.path.basename(f)[len(city) + 1 :].rsplit("_", 1)[0])
    return sorted(names)


out = {
    "graph_tuning": {},
    "regional_tuning": {},
    "regional": {},
    "no_crossover_tuning": {},
    "no_crossover": {},
    "ablation": {},
    "sensitivity": {},
    "graph": {},
}
for city in CITIES:
    lo, hi = (np.array(b) for b in main[city]["bounds"])
    base = main[city]["variants"][MAIN]["hv4"]
    names = variants_in(REVISION, city)

    # Graph crossover: tuning runs (10 seeds) and the final comparison (30 seeds)
    tuning = {
        n: [score(F, lo, hi) for F in runs(REVISION, city, n)] for n in names if "_graph+" in n
    }
    for n, hvs in tuning.items():
        key = n.split("_graph+", 1)[1]
        target = out["graph_tuning"] if len(hvs) < 30 else out["graph"]
        target.setdefault(city, {})[key] = summary(hvs) | {"runs": len(hvs)}
        if len(hvs) >= 30:
            rx = base
            ux = main[city]["variants"]["nsga2-4_uniform"]["hv4"]
            target[city][key]["vs_regional"] = compare(rx, hvs)
            target[city][key]["vs_uniform"] = compare(hvs, ux)

    # Regional crossover with other region sizes (tuning, 10 seeds; or 30)
    for n in names:
        m = re.fullmatch(rf"{MAIN}\+region_share=([\d.,]+)", n)
        if m:
            hvs = [score(F, lo, hi) for F in runs(REVISION, city, n)]
            target = out["regional_tuning"] if len(hvs) < 30 else out["regional"]
            entry = summary(hvs) | {"runs": len(hvs)}
            if len(hvs) >= 30:
                entry["vs_default"] = compare(hvs, base)
            target.setdefault(city, {})[m.group(1)] = entry

    # Control: no crossover (mutation only)
    for n in names:
        if n == f"{MAIN}+crossover_rate=0.0":
            hvs = [score(F, lo, hi) for F in runs(REVISION, city, n)]
            entry = summary(hvs) | {"runs": len(hvs)}
            target = out["no_crossover_tuning"] if len(hvs) < 30 else out["no_crossover"]
            target[city] = entry

    # Ablation: one switch off at a time, against the main configuration
    ablation = {}
    for n in names:
        m = re.fullmatch(
            rf"{MAIN}\+(levels=0|quantize=False|local_moves=0\.0|"
            r"guided_resize=False|seed_current=False)",
            n,
        )
        if m:
            hvs = [score(F, lo, hi) for F in runs(REVISION, city, n)]
            ablation[m.group(1)] = summary(hvs) | {"runs": len(hvs), **compare(base, hvs)}
    if ablation:
        adjusted = holm([v["p"] for v in ablation.values()])
        for v, q in zip(ablation.values(), adjusted, strict=True):
            v["p_holm"] = float(q)
        out["ablation"][city] = {"main": summary(base), **ablation}

    # Sensitivity: regional vs uniform with other block sizes / radii
    groups = defaultdict(dict)
    for n in names:
        m = re.fullmatch(r"nsga2-4_(regional|uniform)\+(cell=[\d.]+\+radius=[\d.]+)", n)
        if m:
            groups[m.group(2)][m.group(1)] = runs(REVISION, city, n)
    for setting, by_cx in groups.items():
        if len(by_cx) < 2:
            continue
        allF = np.vstack([F[:, :4] for fs in by_cx.values() for F in fs])
        slo = np.array([lo[0], allF[:, 1].min(), 0.0, allF[:, 3].min()])
        shi = np.array([hi[0], allF[:, 1].max(), allF[:, 2].max(), allF[:, 3].max()])
        hv = {cx: [score(F, slo, shi) for F in fs] for cx, fs in by_cx.items()}
        out["sensitivity"].setdefault(city, {})[setting] = {
            cx: summary(v) for cx, v in hv.items()
        } | compare(hv["regional"], hv["uniform"])

with open(os.path.join(REVISION, "revision.json"), "w") as file:
    json.dump(out, file, indent=1)

for city in CITIES:
    print(f"== {city}")
    for key, s in sorted(out["graph_tuning"].get(city, {}).items(), key=lambda kv: -kv[1]["mean"]):
        print(f"   graph tuning {key:30s} HV4 {s['mean']:.4f}±{s['sd']:.4f} ({s['runs']})")
    for key, s in out["graph"].get(city, {}).items():
        print(
            f"   graph {key}: HV4 {s['mean']:.4f}  A12 RX/GX {s['vs_regional']['a12']:.2f} "
            f"(p {s['vs_regional']['p']:.1e})  GX/UX {s['vs_uniform']['a12']:.2f}"
        )
    for key, s in sorted(
        out["regional_tuning"].get(city, {}).items(), key=lambda kv: -kv[1]["mean"]
    ):
        print(f"   regional tuning {key:27s} HV4 {s['mean']:.4f}±{s['sd']:.4f} ({s['runs']})")
    for key in ("no_crossover_tuning", "no_crossover"):
        if city in out[key]:
            s = out[key][city]
            print(f"   {key:43s} HV4 {s['mean']:.4f}±{s['sd']:.4f} ({s['runs']})")
    for key, s in out["regional"].get(city, {}).items():
        print(
            f"   regional {key}: HV4 {s['mean']:.4f}  A12 vs default {s['vs_default']['a12']:.2f}"
        )
    ab = out["ablation"].get(city, {})
    if ab:
        print(f"   main HV4 {ab['main']['mean']:.4f}")
        for key, s in ab.items():
            if key != "main":
                print(
                    f"   ablation {key:22s} HV4 {s['mean']:.4f}  A12 main/abl {s['a12']:.2f} "
                    f"p_holm {s['p_holm']:.1e}"
                )
    for setting, s in out["sensitivity"].get(city, {}).items():
        print(
            f"   sensitivity {setting:26s} RX {s['regional']['mean']:.4f} UX "
            f"{s['uniform']['mean']:.4f} A12 {s['a12']:.2f} p {s['p']:.1e}"
        )
