"""Figures of the operator study -> figures/*.pdf, *.png

Reads operators.json (analyse_operators.py), seeds.json (seeds.py) and components.json
(components.py) from RESULTS_DIR.
"""

import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from common import HERE, NAMES, RESULTS  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm  # noqa: E402

OUT = os.path.join(HERE, "figures")
os.makedirs(OUT, exist_ok=True)

# Reference palette (dataviz skill): categorical slots in fixed order, chrome, diverging pair
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
INK, INK2, MUTED, GRID, AXIS = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
DIVERGING = LinearSegmentedColormap.from_list(
    "a12", ["#c24a1a", "#f2b49a", "#f0efec", "#9ec5f4", "#1c5cab"]
)
plt.rcParams.update(
    {
        "font.size": 8,
        "axes.edgecolor": AXIS,
        "axes.labelcolor": INK2,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.5,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "legend.frameon": False,
        "text.color": INK,
        "savefig.dpi": 300,
        "figure.facecolor": "white",
    }
)

M = "centroid_moves=0.8+init=mixed"
FIX = "mating=size+guided_repair=True"
PXP = f"partition+mating=size+{M}"
BASE = "none"
LITERATURE = [  # (label, original, with same-size mating and load-guided repair)
    ("Uniform", f"uniform+{M}", f"uniform+{M}+{FIX}"),
    ("One-point", f"onepoint+{M}", f"onepoint+{M}+{FIX}"),
    ("Half-plane", f"halfplane+{M}", f"halfplane+{M}+{FIX}"),
    ("Quadrant", f"quadrant+{M}", f"quadrant+{M}+{FIX}"),
    (
        "Regional",
        f"regional+{M}+region_share=0.001,0.005",
        f"regional+{M}+{FIX}+region_share=0.001,0.005",
    ),
    (
        "Graph",
        f"graph+{M}+graph_centres=1+graph_depth=1",
        f"graph+{M}+{FIX}+graph_centres=1+graph_depth=1",
    ),
    ("Union (AED)", f"union+{M}", f"union+{M}+mating=size"),
]


def save(fig, name):
    fig.savefig(os.path.join(OUT, f"{name}.pdf"), bbox_inches="tight")
    fig.savefig(os.path.join(OUT, f"{name}.png"), bbox_inches="tight")
    plt.close(fig)


def load_json(name):
    path = os.path.join(RESULTS, name)
    return json.load(open(path)) if os.path.exists(path) else None


ops = load_json("operators.json")
if ops:
    C = ops["cities"]

    # 1. Anytime hypervolume ------------------------------------------------------
    curves = [
        (PXP, "PX+ (proposed)", SERIES[0], "-"),
        ("partition+mating=size", "PX", SERIES[2], "-"),
        (f"halfplane+{M}+{FIX}", "Half-plane + mating, repair", SERIES[4], "-"),
        (f"union+{M}+mating=size", "Union (AED)", SERIES[1], "-"),
        (f"none+{M}+generations=1200", "No crossover, improved mutation", SERIES[3], "-"),
        ("none+generations=1200", "No crossover (baseline)", MUTED, "--"),
    ]
    fig, axes = plt.subplots(1, len(C), figsize=(10, 2.4), sharey=False)
    for ax, city in zip(np.atleast_1d(axes), C, strict=True):
        V = C[city]["variants"]
        budget = C[city]["budgets"]["time"]
        for v, label, colour, style in curves:
            if v not in V or "curve" not in V[v]:
                continue
            c = V[v]["curve"]
            t, m, sd = np.array(c["time"]), np.array(c["mean"]), np.array(c["sd"])
            ax.plot(t, m, color=colour, ls=style, lw=1.5, label=label)
            ax.fill_between(t, m - sd, m + sd, color=colour, alpha=0.12, lw=0)
        ax.axvline(budget, color=AXIS, lw=0.8, ls=":")
        ax.set_title(NAMES[city], fontsize=8, color=INK)
        ax.set_xlabel("Time (s)")
        lo = min(np.nanmin(V[v]["curve"]["mean"][5:]) for v, *_ in curves if v in V)
        ax.set_ylim(bottom=lo)
    np.atleast_1d(axes)[0].set_ylabel("HV4")
    handles, labels = np.atleast_1d(axes)[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.2))
    fig.tight_layout()
    save(fig, "anytime_operators")

    # 2. A12 of PX+ against the crossovers of the literature ----------------------
    rows, labels = [], []
    for label, original, fixed in LITERATURE:
        for v, form in ((original, "original"), (fixed, "+ mating, repair")):
            if all(v in C[c]["variants"] for c in C):
                rows.append([C[c]["variants"][v]["reference_vs"]["hv_at_time"]["a12"] for c in C])
                labels.append(f"{label}, {form}")
    for v, label in (
        (f"none+{M}+generations=1200", "No crossover, improved mutation"),
        ("none+generations=1200", "No crossover (baseline)"),
    ):
        if all(v in C[c]["variants"] for c in C):
            rows.append([C[c]["variants"][v]["reference_vs"]["hv_at_time"]["a12"] for c in C])
            labels.append(label)
    if rows:
        A = np.array(rows)
        fig, ax = plt.subplots(figsize=(4.6, 0.26 * len(rows) + 0.8))
        im = ax.imshow(A, cmap=DIVERGING, norm=TwoSlopeNorm(0.5, 0.0, 1.0), aspect="auto")
        ax.set_xticks(range(len(C)), [NAMES[c] for c in C])
        ax.set_yticks(range(len(labels)), labels)
        ax.grid(False)
        ax.tick_params(length=0)
        for s in ax.spines.values():
            s.set_visible(False)
        for i, j in np.ndindex(A.shape):
            ax.text(j, i, f"{A[i, j]:.2f}", ha="center", va="center", fontsize=7, color=INK)
        cb = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
        cb.set_label("$\\hat{A}_{12}$ of PX+ (0.5: no difference)")
        cb.outline.set_visible(False)
        save(fig, "a12_literature")

    # 3. What same-size mating and guided repair do for each crossover --------------
    fig, ax = plt.subplots(figsize=(5, 2.6))
    ys = np.arange(len(LITERATURE))
    for y, (_label, original, fixed) in zip(ys, LITERATURE, strict=True):
        gains = []
        for v in (original, fixed):
            gains.append(
                [
                    100
                    * (
                        C[c]["variants"][v]["summary"]["hv_at_time"]["mean"]
                        / C[c]["variants"][BASE + "+generations=1200"]["summary"]["hv_at_time"][
                            "mean"
                        ]
                        - 1
                    )
                    if v in C[c]["variants"]
                    else np.nan
                    for c in C
                ]
            )
        g = np.array(gains)
        ax.plot(np.nanmean(g, 1), [y, y], color=AXIS, lw=2, zorder=1)
        ax.scatter(np.nanmean(g[0]), y, s=36, color=SERIES[1], zorder=2, label="Original")
        ax.scatter(np.nanmean(g[1]), y, s=36, color=SERIES[0], zorder=2, label="+ mating, repair")
    px = [
        100
        * (
            C[c]["variants"][PXP]["summary"]["hv_at_time"]["mean"]
            / C[c]["variants"][BASE + "+generations=1200"]["summary"]["hv_at_time"]["mean"]
            - 1
        )
        for c in C
    ]
    ax.axvline(np.mean(px), color=SERIES[0], lw=1, ls="--")
    ax.text(np.mean(px), len(LITERATURE) - 0.4, " PX+", color=INK2, fontsize=7, va="bottom")
    ax.axvline(0, color=MUTED, lw=0.8)
    ax.set_yticks(ys, [x[0] for x in LITERATURE])
    ax.invert_yaxis()
    ax.set_xlabel("HV4 at the same time, % over no crossover (baseline), mean of the cities")
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles[:2], labels[:2], loc="upper left", bbox_to_anchor=(0.0, 1.18), ncol=2)
    save(fig, "literature_gain")

seeds = load_json("seeds.json")
if seeds:
    # 4. Initial layouts at today's number of containers ------------------------------
    kinds = [
        ("random", "Random", MUTED),
        ("demand-0", "Demand, exponent 0", SERIES[3]),
        ("demand-2", "Demand, exponent 2", SERIES[1]),
        ("balanced", "Balanced", SERIES[0]),
    ]
    fig, axes = plt.subplots(1, len(seeds), figsize=(10, 2.3))
    for ax, city in zip(np.atleast_1d(axes), seeds, strict=True):
        s = seeds[city]
        for key, label, colour in kinds:
            v = np.array(s[key]["values"])
            ax.scatter(v[:, 2], 100 * v[:, 1], s=10, color=colour, alpha=0.8, lw=0, label=label)
        cur = s["current"]
        ax.scatter(cur[2], 100 * cur[1], marker="D", s=30, color=INK, label="Today", zorder=3)
        ax.set_title(NAMES[city], fontsize=8, color=INK)
        ax.set_xlabel("Mean distance (m)")
    np.atleast_1d(axes)[0].set_ylabel("Inequity (points)")
    handles, labels = np.atleast_1d(axes)[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=5, bbox_to_anchor=(0.5, -0.14))
    fig.tight_layout()
    save(fig, "seeds")

components = load_json("components.json")
if components:
    # 5. Exact decomposition: components per pair of same-size layouts ----------------
    fig, ax = plt.subplots(figsize=(4.4, 2.2))
    data = [[r["components"] for r in components[c]["rows"]] for c in components]
    top = max(max(d) for d in data)
    bins = np.arange(1, top + 2) - 0.5
    for i, (city, d) in enumerate(zip(components, data, strict=True)):
        h, _ = np.histogram(d, bins)
        ax.plot(
            np.arange(1, top + 1),
            100 * h / len(d),
            marker="o",
            ms=3,
            lw=1.2,
            color=SERIES[i],
            label=NAMES[city],
        )
    ax.set_xlabel("Independent components")
    ax.set_ylabel("Pairs of layouts (%)")
    ax.set_xlim(0.5, min(top, 10) + 0.5)
    ax.legend(ncol=2)
    save(fig, "components")
print("figures in", OUT)
