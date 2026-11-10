# ruff: noqa: E501 (LaTeX)
"""LaTeX tables of the paper from results/analysis.json -> figures/tables.tex"""

import json
import os

from common import CITIES, HERE, NAMES, RESULTS

a = json.load(open(os.path.join(RESULTS, "analysis.json")))
out = []


def p_value(p):
    if p >= 0.001:
        return f"{p:.3f}"
    mantissa, exponent = f"{p:.1e}".split("e")
    return f"${mantissa} \\cdot 10^{{{int(exponent)}}}$"


out.append(r"""\begin{table}[htbp]
\centering
\small
\caption{Hypervolume after 300 generations (30 runs per city and crossover): mean ($\mu$), standard deviation ($\sigma$), median ($m$) and interquartile range (IQR); two-sided Mann--Whitney U test and Vargha--Delaney $\hat{A}_{12}$ (probability that a run with regional crossover beats one with uniform crossover).}
\label{tab:hv}
\begin{tabular}{llcccccc}
\toprule
\textbf{City} & \textbf{Crossover} & $\mu$ & $\sigma$ & $m$ & IQR & $p$ & $\hat{A}_{12}$ \\
\midrule""")
for c in CITIES:
    r = a[c]
    best = max(("regional", "uniform"), key=lambda v: r[v]["hv_mean"])
    for i, (v, label) in enumerate((("uniform", "Uniform (UX)"), ("regional", "Regional (RX)"))):
        x = r[v]
        mean = f"{x['hv_mean']:.4f}"
        mean = f"\\textbf{{{mean}}}" if v == best else mean
        city = f"\\multirow{{2}}{{*}}{{{NAMES[c]}}}" if i == 0 else ""
        tail = (
            (
                f"\\multirow{{2}}{{*}}{{{p_value(r['mannwhitney_p'])}}} & "
                f"\\multirow{{2}}{{*}}{{{r['a12_regional_vs_uniform']:.2f}}}"
            )
            if i == 0
            else " & "
        )
        out.append(
            f"{city} & {label} & {mean} & {x['hv_sd']:.4f} & {x['hv_median']:.4f} & "
            f"{x['hv_iqr']:.4f} & {tail} \\\\"
        )
    out.append(r"\midrule" if c != CITIES[-1] else r"\bottomrule")
out.append(r"""\end{tabular}
\end{table}
""")

out.append(r"""\begin{table}[htbp]
\centering
\small
\caption{Layouts with today's number of containers: the current one, the single-objective genetic algorithm (median of 5 runs), and two layouts of the front of each run with regional crossover (medians over 30 runs): the one with fewest unserved people, and the fairest one among those with no more unserved people than today. Distances are straight-line, population-weighted.}
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
    m = r["regional"]["k0_min_unserved_layout_median"]
    rows.append(("Front, fewest unserved", m[1], m[2], m[3], m[4]))
    f = r["regional"]["k0_fairest_layout_median"]
    rows.append(("Front, fairest", f[1], f[2], f[3], f[4]))
    for i, (label, u, q, d, d95) in enumerate(rows):
        city = f"\\multirow{{{len(rows)}}}{{*}}{{{NAMES[c]} ($k={int(cur[0])}$)}}" if i == 0 else ""
        out.append(f"{city} & {label} & {u:,.0f} & {q * 100:.1f} & {d:.0f} & {d95:.0f} \\\\")
    out.append(r"\midrule" if c != CITIES[-1] else r"\bottomrule")
out.append(r"""\end{tabular}
\end{table}
""")
os.makedirs(os.path.join(HERE, "figures"), exist_ok=True)
with open(os.path.join(HERE, "figures", "tables.tex"), "w") as file:
    file.write("\n".join(out))
print("\n".join(out))
