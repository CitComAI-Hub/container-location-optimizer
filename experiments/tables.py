# ruff: noqa: E501 (LaTeX)
"""LaTeX tables of the paper from results/analysis.json -> figures/tables.tex"""

import json
import os

import numpy as np
from common import CITIES, HERE, NAMES, RESULTS

MAIN = os.environ.get("MAIN_VARIANT", "nsga2-4_none")
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
\caption{The fronts of both formulations (NSGA-II without crossover) scored in both objective spaces: HV3 (containers, unserved people, inequity) and HV4 (plus mean distance), mean (standard deviation) of 30 runs, with the Vargha--Delaney $\hat{A}_{12}$ of the four-objective against the three-objective formulation (Holm-corrected Mann--Whitney U; $^\dagger$: not significant).}
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
    for hv, test in (("hv3", "formulation-hv3 nsga2-none"), ("hv4", "formulation nsga2-none")):
        for o in (3, 4):
            s = V[f"nsga2-{o}_none"][f"{hv}_summary"]
            cells.append(f"{s['mean']:.4f} ({s['sd']:.4f})")
        cells.append(mark(T[test]))
    out.append(f"{NAMES[c]} & " + " & ".join(cells) + r" \\")
out.append(r"""\bottomrule
\end{tabular}
\end{table}
""")

# Recombination ----------------------------------------------------------------
out.append(r"""\begin{table}[htbp]
\centering
\small
\caption{Recombination (NSGA-II, four objectives): HV4 after 300 generations, mean (standard deviation) of 30 runs, without crossover and with four crossovers: regional and graph crossover with small regions (tuned, Section~\ref{sec:recombination}), regional crossover with large regions (10--50\% of the candidates) and uniform crossover. $\hat{A}_{12}$: probability that a run with the crossover beats a run without it (Holm-corrected Mann--Whitney U; $^\dagger$: not significant).}
\label{tab:recombination}
\resizebox{\textwidth}{!}{%
\begin{tabular}{lccccccccc}
\toprule
& \textbf{None} & \multicolumn{2}{c}{\textbf{Regional, small}} & \multicolumn{2}{c}{\textbf{Graph, small}} & \multicolumn{2}{c}{\textbf{Regional, large}} & \multicolumn{2}{c}{\textbf{Uniform}} \\
\cmidrule(lr){3-4} \cmidrule(lr){5-6} \cmidrule(lr){7-8} \cmidrule(lr){9-10}
\textbf{City} & HV4 & HV4 & $\hat{A}_{12}$ & HV4 & $\hat{A}_{12}$ & HV4 & $\hat{A}_{12}$ & HV4 & $\hat{A}_{12}$ \\
\midrule""")
for c in CITIES:
    V, T = a[c]["variants"], a[c]["tests"]
    cells = []
    for v in (
        "nsga2-4_none",
        "nsga2-4_regional-small",
        "nsga2-4_graph-small",
        "nsga2-4_regional",
        "nsga2-4_uniform",
    ):
        s = V[v]["hv_summary"]
        cells.append(f"{s['mean']:.4f} ({s['sd']:.4f})")
        if v != "nsga2-4_none":
            cells.append(mark(T[f"recombination {v.split('_', 1)[1]}"]))
    out.append(f"{NAMES[c]} & " + " & ".join(cells) + r" \\")
out.append(r"""\bottomrule
\end{tabular}}
\end{table}
""")

# Equity measures --------------------------------------------------------------
equity_file = os.path.join(RESULTS, "equity_measures.json")
if os.path.exists(equity_file):
    eq = json.load(open(equity_file))
    shown = [
        "f3 250/500",
        "f3 1000/2000",
        "Moran's I",
        "Gini unserved share",
        "Gini load",
        "Gini distance",
        "mean distance",
    ]
    heads = [
        "$f_3$ 250/500",
        "$f_3$ 1000/2000",
        "Moran's I",
        "Gini unserved",
        "Gini load",
        "Gini distance",
        "Mean distance",
    ]
    out.append(
        r"""\begin{table}[htbp]
\centering
\small
\caption{Spearman rank correlation between $f_3$ (500\,m blocks, 1\,km neighbourhoods) and other measures, over the layouts with today's number of containers of the 30 fronts of each city (NSGA-II, four objectives, no crossover): $f_3$ with other block sizes and radii, Moran's I of the blocks, and classical non-spatial measures \cite{marsh1994equity}: population-weighted Gini coefficients of the unserved share of each person, of the load of each container and of the distance to the nearest container.}
\label{tab:equity}
\resizebox{\textwidth}{!}{%
\begin{tabular}{lrccccccc}
\toprule
\textbf{City} & \textbf{Layouts} & """
        + " & ".join(heads)
        + r""" \\
\midrule"""
    )
    for c in CITIES:
        e = eq[c]
        ref = e["measures"].index("f3 500/1000")
        row = [f"{e['spearman'][ref][e['measures'].index(m)]:+.2f}" for m in shown]
        out.append(f"{NAMES[c]} & {e['layouts']} & " + " & ".join(row) + r" \\")
    out.append(r"""\bottomrule
\end{tabular}}
\end{table}
""")

# Accessibility bounds ------------------------------------------------------------
bounds = {
    c: json.load(open(f))[c]
    for c in CITIES
    if os.path.exists(f := os.path.join(RESULTS, f"bounds_{c}.json"))
}
if bounds:
    out.append(r"""\begin{table}[htbp]
\centering
\small
\caption{Mean distance (m) with today's number of containers $k_0$: Lagrangian lower bound of the $p$-median problem \cite{beasley1993lagrangean}, best known solution (Lagrangian heuristic or alternating local search), single-objective genetic algorithm (median of 5 runs) and the most accessible layout of the four-objective fronts no worse than the current layout in unserved people and inequity (median of 30 runs); in brackets, the gap to the best known solution. The last column is the inequity of the best known solution.}
\label{tab:bounds}
\begin{tabular}{lrrrrrr}
\toprule
\textbf{City} & $k_0$ & \textbf{Lower bound} & \textbf{Best known} & \textbf{Single-obj.} & \textbf{Front} & \textbf{Ineq. best known (pts)} \\
\midrule""")
    for c in CITIES:
        if c not in bounds:
            continue
        b = bounds[c]
        best = b["best_known"]
        single = a[c]["single"]["mean_distance"]
        front = a[c]["variants"][MAIN]["k0_closest"][3]
        out.append(
            f"{NAMES[c]} & {b['k0']} & {b['lower_bound']:.1f} & {best:.1f} & "
            f"{single:.1f} (+{single / best - 1:.1%}) & {front:.1f} (+{front / best - 1:.1%}) & "
            f"{b['best_known_layout']['inequity'] * 100:.1f} \\\\".replace("%", "\\%")
        )
    out.append(r"""\bottomrule
\end{tabular}
\end{table}
""")

# Ablation and sensitivity (analyse_revision.py) -----------------------------------
revision_file = os.path.join(os.environ.get("REVISION_DIR", RESULTS + "_rev"), "revision.json")
if os.path.exists(revision_file):
    rev = json.load(open(revision_file))
    switches = [
        ("levels=0", "All sizes"),
        ("guided_resize=False", "Random resize"),
        ("quantize=False", "Exact $f_2$"),
        ("local_moves=0.0", "No local moves"),
        ("seed_current=False", "No seed"),
    ]
    out.append(
        r"""\begin{table}[htbp]
\centering
\small
\caption{Ablation of the recommended configuration (NSGA-II, four objectives, no crossover): HV4, mean of 30 runs, with one component removed at a time: the discrete set of sizes (all sizes in the range allowed), the load-guided resizing (random instead), the comparison of $f_2$ in steps (exact values), the local moves of the mutation (all moves to random candidates) and the seeding of the current layout. $\hat{A}_{12}$: probability that a run of the full configuration beats a run without the component (Holm-corrected Mann--Whitney U; $^\dagger$: not significant).}
\label{tab:ablation}
\resizebox{\textwidth}{!}{%
\begin{tabular}{lc"""
        + "cc" * len(switches)
        + r"""}
\toprule
& \textbf{Full} & """
        + " & ".join(f"\\multicolumn{{2}}{{c}}{{\\textbf{{{label}}}}}" for _, label in switches)
        + r""" \\
\textbf{City} & HV4 & """
        + " & ".join("HV4 & $\\hat{A}_{12}$" for _ in switches)
        + r""" \\
\midrule"""
    )
    for c in CITIES:
        ab = rev["ablation"].get(c)
        if not ab:
            continue
        cells = [f"{ab['main']['mean']:.4f}"]
        for key, _ in switches:
            v = ab[key]
            cells += [f"{v['mean']:.4f}", mark(v)]
        out.append(f"{NAMES[c]} & " + " & ".join(cells) + r" \\")
    out.append(r"""\bottomrule
\end{tabular}}
\end{table}
""")

    out.append(r"""\begin{table}[htbp]
\centering
\small
\caption{Sensitivity of the comparison between regional (large regions) and uniform crossover to the parameters of $f_3$ (NSGA-II, four objectives, 30 runs): HV4 with blocks of 250\,m and neighbourhoods of 500\,m, and with blocks of 1\,km and neighbourhoods of 2\,km (each normalized among its own runs), and $\hat{A}_{12}$ of regional against uniform (all differences significant, $p < 10^{-9}$).}
\label{tab:sensitivity}
\begin{tabular}{lcccccc}
\toprule
& \multicolumn{3}{c}{\textbf{250\,m / 500\,m}} & \multicolumn{3}{c}{\textbf{1\,km / 2\,km}} \\
\cmidrule(lr){2-4} \cmidrule(lr){5-7}
\textbf{City} & Regional & Uniform & $\hat{A}_{12}$ & Regional & Uniform & $\hat{A}_{12}$ \\
\midrule""")
    for c in CITIES:
        se = rev["sensitivity"].get(c, {})
        cells = []
        for key in ("cell=250.0+radius=500.0", "cell=1000.0+radius=2000.0"):
            v = se[key]
            cells += [
                f"{v['regional']['mean']:.4f}",
                f"{v['uniform']['mean']:.4f}",
                f"{v['a12']:.2f}",
            ]
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
\caption{Layouts with today's number of containers $k_0$: the current one; the single-objective genetic algorithm (median of 5 runs); and, among the layouts of each front that are no worse than the current one in unserved people and inequity, the fairest and the one with the shortest mean distance (medians over 30 runs, NSGA-II without crossover). Distances are straight-line and population-weighted.}
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

# Operator study (analyse_operators.py, seeds.py, components.py) -------------------
M = "centroid_moves=0.8+init=mixed"
FIX = "mating=size+guided_repair=True"
PXP = f"partition+mating=size+{M}"
operators_file = os.path.join(RESULTS, "operators.json")
if os.path.exists(operators_file):
    ops = json.load(open(operators_file))["cities"]

    def hv(c, v, key="hv_at_time", sd=True):
        s = ops[c]["variants"][v]["summary"][key]
        return f"{s['mean']:.4f} ({s['sd']:.4f})" if sd else f"{s['mean']:.4f}"

    def vs(c, v, key="hv_at_time"):
        """A12 of PX+ against v."""
        return mark(ops[c]["variants"][v]["reference_vs"][key])

    main = [
        ("none", "No crossover, 300 gen."),
        ("none+generations=1200", "No crossover, 1,200 gen."),
        (f"none+{M}+generations=1200", "No crossover, improved mutation and init., 1,200 gen."),
        ("partition+mating=size", "PX, 300 gen."),
        (f"union+{M}+mating=size", "Union (AED), improved mutation and init., 300 gen."),
    ]
    out.append(
        r"""\begin{table}[htbp]
\centering
\small
\caption{The proposed configuration (PX+, in bold: partition crossover with same-size mating, centroid moves and mixed initialization, 300 generations) against no crossover and the other operators at the same computing time: HV4 of the front reached within the median time of a PX+ run (last row), mean (standard deviation) of 30 runs, and $\hat{A}_{12}$, the probability that a run of PX+ beats a run of the variant (Holm-corrected Mann--Whitney U within each city; $^\dagger$: not significant). The first row is the configuration of the earlier sections.}
\label{tab:operators}
\resizebox{\textwidth}{!}{%
\begin{tabular}{l"""
        + "cc" * len(CITIES)
        + r"""}
\toprule
& """
        + " & ".join(f"\\multicolumn{{2}}{{c}}{{\\textbf{{{NAMES[c]}}}}}" for c in CITIES)
        + r""" \\
"""
        + " ".join(f"\\cmidrule(lr){{{2 + 2 * i}-{3 + 2 * i}}}" for i in range(len(CITIES)))
        + r"""
\textbf{Variant} & """
        + " & ".join("HV4 & $\\hat{A}_{12}$" for _ in CITIES)
        + r""" \\
\midrule"""
    )
    for v, label in main:
        out.append(f"{label} & " + " & ".join(f"{hv(c, v)} & {vs(c, v)}" for c in CITIES) + r" \\")
    out.append(
        r"\textbf{PX+, 300 gen.} & "
        + " & ".join(f"\\textbf{{{hv(c, PXP)}}} & --" for c in CITIES)
        + r" \\"
    )
    out.append(
        r"\midrule Time budget (s) & "
        + " & ".join(f"\\multicolumn{{2}}{{c}}{{{ops[c]['budgets']['time']:.0f}}}" for c in CITIES)
        + r" \\"
    )
    out.append(r"""\bottomrule
\end{tabular}}
\end{table}
""")

    literature = [
        ("Uniform", "uniform", f"uniform+{M}", f"uniform+{M}+{FIX}"),
        (
            "One-point \\cite{hosage1986discrete}",
            "onepoint",
            f"onepoint+{M}",
            f"onepoint+{M}+{FIX}",
        ),
        (
            "Half-plane \\cite{deaven1995molecular}",
            "halfplane",
            f"halfplane+{M}",
            f"halfplane+{M}+{FIX}",
        ),
        ("Quadrant \\cite{li2016improved}", "quadrant", f"quadrant+{M}", f"quadrant+{M}+{FIX}"),
        (
            "Regional",
            "regional",
            f"regional+{M}+region_share=0.001,0.005",
            f"regional+{M}+{FIX}+region_share=0.001,0.005",
        ),
        (
            "Graph \\cite{jordan2025crossover}",
            "graph",
            f"graph+{M}+graph_centres=1+graph_depth=1",
            f"graph+{M}+{FIX}+graph_centres=1+graph_depth=1",
        ),
        ("Union \\cite{alp2003efficient}", "union", f"union+{M}", f"union+{M}+mating=size"),
    ]
    out.append(
        r"""\begin{table}[htbp]
\centering
\small
\caption{Crossovers of the literature in the same algorithm (same mutation, initialization and survival as PX+), at the same computing time: HV4, mean of 30 runs, and $\hat{A}_{12}$ of PX+ against each. Original: as published, mating any two parents and repairing at random (the union crossover needs no repair); +MR: with same-size mating and load-guided repair, as in PX+. Holm-corrected Mann--Whitney U within each city; $^\dagger$: not significant. Last row: PX+.}
\label{tab:literature}
\resizebox{\textwidth}{!}{%
\begin{tabular}{ll"""
        + "cc" * len(CITIES)
        + r"""}
\toprule
& & """
        + " & ".join(f"\\multicolumn{{2}}{{c}}{{\\textbf{{{NAMES[c]}}}}}" for c in CITIES)
        + r""" \\
"""
        + " ".join(f"\\cmidrule(lr){{{3 + 2 * i}-{4 + 2 * i}}}" for i in range(len(CITIES)))
        + r"""
\textbf{Crossover} & \textbf{Form} & """
        + " & ".join("HV4 & $\\hat{A}_{12}$" for _ in CITIES)
        + r""" \\
\midrule"""
    )
    for label, _, original, fixed in literature:
        for i, (v, form) in enumerate(((original, "Original"), (fixed, "+MR"))):
            if not all(v in ops[c]["variants"] for c in CITIES):
                continue
            name = f"\\multirow{{2}}{{*}}{{{label}}}" if i == 0 else ""
            out.append(
                f"{name} & {form} & "
                + " & ".join(f"{hv(c, v, sd=False)} & {vs(c, v)}" for c in CITIES)
                + r" \\"
            )
        out.append(r"\midrule")
    out.append(
        r"\textbf{PX+} & & "
        + " & ".join(f"\\textbf{{{hv(c, PXP, sd=False)}}} & --" for c in CITIES)
        + r" \\"
    )
    out.append(r"""\bottomrule
\end{tabular}}
\end{table}
""")

    ablations = [
        ("partition+mating=size+init=mixed", "Without centroid moves"),
        ("partition+mating=size+centroid_moves=0.8", "Random initialization"),
        (f"partition+{M}", "Any mating"),
        (f"partition+mating=size+{M}+tile=1.0", "Tiles of 1 spacing"),
        (f"partition+mating=size+{M}+tile=4.0", "Tiles of 4 spacings"),
        (f"partition+mating=size+{M}+tile=6.0", "Tiles of 6 spacings"),
        (f"partition+mating=size+{M}+tile=8.0", "Tiles of 8 spacings"),
        (f"partition+mating=size+{M}+tile=12.0", "Tiles of 12 spacings"),
        (f"partition+mating=size+{M}+cuts=1", "Regions cut by 1 random line"),
        (f"partition+mating=size+{M}+cuts=2", "Regions cut by 2 random lines"),
        (f"partition+mating=size+{M}+cuts=3", "Regions cut by 3 random lines"),
        (f"components+mating=size+{M}", "Exact components (no tiles)"),
        (f"partition+mating=size+{M}+tile_equity=True", "Equity per tile"),
        (
            f"partition+mating=size+{M}+tile_equity=True+crossover_rate=0.5+generations=900",
            "Equity per tile, $p_c = 0.5$, 900 gen.",
        ),
    ]
    out.append(
        r"""\begin{table}[htbp]
\centering
\small
\caption{Ablation of PX+ at the same computing time: HV4, mean of 30 runs, and $\hat{A}_{12}$ of PX+ against each variant ($^\dagger$: not significant), and the inequity (points) of the fairest layout of the front, mean of 30 runs. Each variant changes one component of PX+ (tiles of 2 spacings, $p_c = 0.9$): the mutation, the initialization or the mating; the shape of the regions (square tiles of 1 to 12 mean spacings, regions between 1 to 3 random lines, or the exact independent components of Section~\ref{sec:crossovers}); or the comparison in each region (equity per tile). The equity-per-tile variant with $p_c = 0.5$ also runs three times as many generations, and is scored at the same time as the others.}
\label{tab:operator_ablation}
\resizebox{\textwidth}{!}{%
\begin{tabular}{l"""
        + "ccc" * len(CITIES)
        + r"""}
\toprule
& """
        + " & ".join(f"\\multicolumn{{3}}{{c}}{{\\textbf{{{NAMES[c]}}}}}" for c in CITIES)
        + r""" \\
"""
        + " ".join(f"\\cmidrule(lr){{{2 + 3 * i}-{4 + 3 * i}}}" for i in range(len(CITIES)))
        + r"""
\textbf{Variant} & """
        + " & ".join("HV4 & $\\hat{A}_{12}$ & $f_3^{\\min}$" for _ in CITIES)
        + r""" \\
\midrule"""
    )

    def fairest(c, v):
        return f"{100 * np.mean(ops[c]['variants'][v]['min_inequity']):.2f}"

    out.append(
        r"\textbf{PX+} & "
        + " & ".join(f"\\textbf{{{hv(c, PXP, sd=False)}}} & -- & {fairest(c, PXP)}" for c in CITIES)
        + r" \\"
    )
    for v, label in ablations:
        if all(v in ops[c]["variants"] for c in CITIES):
            out.append(
                f"{label} & "
                + " & ".join(f"{hv(c, v, sd=False)} & {vs(c, v)} & {fairest(c, v)}" for c in CITIES)
                + r" \\"
            )
    out.append(
        r"No crossover, 1,200 gen. & "
        + " & ".join(
            f"{hv(c, 'none+generations=1200', sd=False)} & {vs(c, 'none+generations=1200')} & "
            f"{fairest(c, 'none+generations=1200')}"
            for c in CITIES
        )
        + r" \\"
    )
    out.append(r"""\bottomrule
\end{tabular}}
\end{table}
""")

seeds_file = os.path.join(RESULTS, "seeds.json")
if os.path.exists(seeds_file):
    seeds = json.load(open(seeds_file))
    kinds = [
        ("random", "Random"),
        ("demand-0", "Demand, $e = 0$"),
        ("demand-1", "Demand, $e = 1$"),
        ("demand-2", "Demand, $e = 2$"),
        ("balanced", "Balanced"),
    ]
    out.append(
        r"""\begin{table}[htbp]
\centering
\small
\caption{Initial layouts with today's number of containers $k_0$: unserved people, inequity (points) and mean distance (m), mean of 30 layouts of each kind, and today's layout. Random: $k_0$ candidates at random; demand: population-weighted $k$-means++ seeding with exponent $e$; balanced: recursive bisection into cells of equal population. Last column: time to build one layout (ms).}
\label{tab:seeds}
\resizebox{\textwidth}{!}{%
\begin{tabular}{ll"""
        + "rrr" * 1
        + r"""r}
\toprule
\textbf{City} & \textbf{Layout} & \textbf{Unserved} & \textbf{Inequity} & \textbf{Distance} & \textbf{ms} \\
\midrule"""
    )
    for c in CITIES:
        if c not in seeds:
            continue
        s = seeds[c]
        cur = s["current"]
        rows = [("Today", cur, None)] + [
            (label, np.mean(s[k]["values"], 0), s[k]["ms"]) for k, label in kinds
        ]
        for i, (label, v, ms) in enumerate(rows):
            city = f"\\multirow{{{len(rows)}}}{{*}}{{{NAMES[c]}}}" if i == 0 else ""
            msx = "--" if ms is None else f"{ms:.0f}"
            out.append(
                f"{city} & {label} & {v[0]:,.0f} & {100 * v[1]:.1f} & {v[2]:.0f} & {msx} \\\\"
            )
        out.append(r"\midrule" if c != CITIES[-1] else r"\bottomrule")
    out.append(r"""\end{tabular}}
\end{table}
""")

components_file = os.path.join(RESULTS, "components.json")
if os.path.exists(components_file):
    comp = json.load(open(components_file))
    out.append(r"""\begin{table}[htbp]
\centering
\small
\caption{Exact decomposition of pairs of layouts with the same number of containers from the final PX+ fronts (10 runs per city): pairs, median number of locations in which they differ, share of pairs whose differences form a single independent component, median number of components, and mean share of the differing locations in the largest component.}
\label{tab:components}
\begin{tabular}{lrrrrr}
\toprule
\textbf{City} & \textbf{Pairs} & \textbf{Differing} & \textbf{One component} & \textbf{Components} & \textbf{Largest} \\
\midrule""")
    for c in CITIES:
        if c in comp:
            r = comp[c]
            out.append(
                f"{NAMES[c]} & {r['pairs']} & {r['median_differing_sites']:.0f} & "
                f"{100 * r['single_component']:.0f}\\% & {r['median_components']:.0f} & "
                f"{100 * r['mean_largest_share']:.0f}\\% \\\\"
            )
    out.append(r"""\bottomrule
\end{tabular}
\end{table}
""")

os.makedirs(os.path.join(HERE, "figures"), exist_ok=True)
with open(os.path.join(HERE, "figures", "tables.tex"), "w") as file:
    file.write("\n".join(out))
# One file per table too (figures/table_<label>.tex), to place each one in the text
text = "\n".join(out)
for chunk in text.split("\\begin{table}")[1:]:
    label = chunk.split("\\label{tab:", 1)[1].split("}", 1)[0]
    with open(os.path.join(HERE, "figures", f"table_{label}.tex"), "w") as file:
        file.write("\\begin{table}" + chunk.split("\\end{table}", 1)[0] + "\\end{table}\n")
print("\n".join(out))
