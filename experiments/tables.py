# ruff: noqa: E501 (LaTeX)
"""LaTeX tables of the paper from results/analysis.json -> figures/tables.tex"""

import json
import os

from common import CITIES, HERE, NAMES, RESULTS

MAIN = os.environ.get("MAIN_VARIANT", "nsga2-4_regional")
BASE3 = MAIN.replace("-4_", "-3_")
a = json.load(open(os.path.join(RESULTS, "analysis.json")))
out = []


def mark(test):
    """A12 with a dagger when not significant after Holm (alpha 0.05)."""
    return f"{test['a12']:.2f}" + ("" if test["p_holm"] < 0.05 else "$^\\dagger$")


# Hypervolume of the eight variants ------------------------------------------
out.append(r"""\begin{table}[htbp]
\centering
\small
\caption{Hypervolume after 300 generations, mean (standard deviation) of 30 runs, in the objective space of each formulation (HV3 or HV4); the best of each row in bold. $\hat{A}_{12}$: Vargha--Delaney effect size, the probability that a run of the first variant beats a run of the second, for regional (RX) against uniform (UX) crossover and for NSGA-III against NSGA-II (both with RX). Mann--Whitney U tests with Holm correction within each city; $^\dagger$: not significant at $\alpha = 0.05$.}
\label{tab:hv}
\resizebox{\textwidth}{!}{%
\begin{tabular}{llccccccc}
\toprule
& & \multicolumn{2}{c}{\textbf{NSGA-II}} & \multicolumn{2}{c}{\textbf{NSGA-III}} & \multicolumn{3}{c}{$\hat{A}_{12}$} \\
\cmidrule(lr){3-4} \cmidrule(lr){5-6} \cmidrule(lr){7-9}
\textbf{City} & \textbf{Obj.} & RX & UX & RX & UX & RX/UX (II) & RX/UX (III) & III/II \\
\midrule""")
for c in CITIES:
    r = a[c]
    V, T = r["variants"], r["tests"]
    for i, o in enumerate((3, 4)):
        keys = [
            f"nsga2-{o}_regional",
            f"nsga2-{o}_uniform",
            f"nsga3-{o}_regional",
            f"nsga3-{o}_uniform",
        ]
        best = max(keys, key=lambda k: V[k]["hv_summary"]["mean"])
        cells = []
        for k in keys:
            s = V[k]["hv_summary"]
            text = f"{s['mean']:.4f} ({s['sd']:.4f})"
            cells.append(f"\\textbf{{{text}}}" if k == best else text)
        city = f"\\multirow{{2}}{{*}}{{{NAMES[c]}}}" if i == 0 else ""
        out.append(
            f"{city} & {o} & " + " & ".join(cells) + f" & {mark(T[f'crossover nsga2-{o}'])} & "
            f"{mark(T[f'crossover nsga3-{o}'])} & {mark(T[f'algorithm {o}'])} \\\\"
        )
    out.append(r"\midrule" if c != CITIES[-1] else r"\bottomrule")
out.append(r"""\end{tabular}}
\end{table}
""")

# 3 vs 4 objectives ---------------------------------------------------------------
out.append(r"""\begin{table}[htbp]
\centering
\small
\caption{The fronts of both formulations (NSGA-II, regional crossover) scored in both objective spaces: HV3 (containers, unserved people, inequity) and HV4 (plus mean distance), mean (standard deviation) of 30 runs, with the Vargha--Delaney $\hat{A}_{12}$ of the four-objective against the three-objective formulation (Holm-corrected Mann--Whitney U; $^\dagger$: not significant).}
\label{tab:formulation}
\begin{tabular}{lcccccc}
\toprule
& \multicolumn{3}{c}{\textbf{HV3}} & \multicolumn{3}{c}{\textbf{HV4}} \\
\cmidrule(lr){2-4} \cmidrule(lr){5-7}
\textbf{City} & 3 obj. & 4 obj. & $\hat{A}_{12}$ & 3 obj. & 4 obj. & $\hat{A}_{12}$ \\
\midrule""")
for c in CITIES:
    V, T = a[c]["variants"], a[c]["tests"]
    cells = []
    for hv, test in (("hv3", "formulation-hv3 nsga2"), ("hv4", "formulation nsga2")):
        for o in (3, 4):
            s = V[f"nsga2-{o}_regional"][f"{hv}_summary"]
            cells.append(f"{s['mean']:.4f} ({s['sd']:.4f})")
        cells.append(mark(T[test]))
    out.append(f"{NAMES[c]} & " + " & ".join(cells) + r" \\")
out.append(r"""\bottomrule
\end{tabular}
\end{table}
""")

# Today's number of containers -------------------------------------------------
label_main = "4 obj." if "-4_" in MAIN else "3 obj."
out.append(r"""\begin{table}[htbp]
\centering
\small
\caption{Layouts with today's number of containers $k_0$: the current one; the single-objective genetic algorithm (median of 5 runs); and, among the layouts of each front that are no worse than the current one in unserved people and inequity, the fairest and the one with the shortest mean distance (medians over 30 runs, NSGA-II with regional crossover). Distances are straight-line and population-weighted.}
\label{tab:k0}
\begin{tabular}{llrrrr}
\toprule
\textbf{City} & \textbf{Layout} & \textbf{Unserved} & \textbf{Inequity (pts)} & \textbf{Mean dist. (m)} & \textbf{95\% within (m)} \\
\midrule""")
for c in CITIES:
    r = a[c]
    cur = r["current"]
    rows = [("Current", cur[1], cur[2], cur[3], cur[4])]
    if "single" in r:
        s = r["single"]
        rows.append(
            ("Single-objective GA", s["unserved"], s["inequity"], s["mean_distance"], s["p95"])
        )
    for variant, name in ((BASE3, "3 obj."), (MAIN, label_main)):
        v = r["variants"][variant]
        f = v["k0_fairest"]
        rows.append((f"{name}, fairest", f[1], f[2], f[3], f[4]))
        if variant == MAIN:
            f = v["k0_closest"]
            rows.append((f"{name}, shortest distance", f[1], f[2], f[3], f[4]))
    for i, (label, u, q, d, d95) in enumerate(rows):
        city = (
            f"\\multirow{{{len(rows)}}}{{*}}{{\\shortstack[l]{{{NAMES[c]}\\\\($k_0={int(cur[0])}$)}}}}"
            if i == 0
            else ""
        )
        out.append(f"{city} & {label} & {u:,.0f} & {q * 100:.1f} & {d:.0f} & {d95:.0f} \\\\")
    out.append(r"\midrule" if c != CITIES[-1] else r"\bottomrule")
out.append(r"""\end{tabular}
\end{table}
""")

os.makedirs(os.path.join(HERE, "figures"), exist_ok=True)
with open(os.path.join(HERE, "figures", "tables.tex"), "w") as file:
    file.write("\n".join(out))
print("\n".join(out))
