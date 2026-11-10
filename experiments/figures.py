"""Figures of the paper from results/ (after analyse.py) -> figures/*.pdf, *.png"""

import glob
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from common import CITIES, HERE, NAMES, RESULTS, load  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

from services.equity import pixel_unserved  # noqa: E402

OUT = os.path.join(HERE, "figures")
os.makedirs(OUT, exist_ok=True)

# Reference palette (dataviz skill): categorical slots 1-2, blue sequential ramp, chrome
RX, UX = "#2a78d6", "#eb6834"
INK, INK2, MUTED, GRID, AXIS = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
BLUES = LinearSegmentedColormap.from_list(
    "blues", ["#cde2fb", "#86b6ef", "#3987e5", "#256abf", "#184f95", "#0d366b"]
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
analysis = json.load(open(os.path.join(RESULTS, "analysis.json")))


def save(fig, name):
    fig.savefig(os.path.join(OUT, f"{name}.pdf"), bbox_inches="tight")
    fig.savefig(os.path.join(OUT, f"{name}.png"), bbox_inches="tight")
    plt.close(fig)


# 1. Hypervolume convergence, one panel per city ------------------------------
fig, axes = plt.subplots(1, 5, figsize=(10, 2.2), sharey=False)
for ax, city in zip(axes, CITIES, strict=True):
    a = analysis[city]
    for variant, color, label in (
        ("regional", RX, "Regional (RX)"),
        ("uniform", UX, "Uniform (UX)"),
    ):
        mean = np.array(a[variant]["convergence_mean"])
        sd = np.array(a[variant]["convergence_sd"])
        gens = np.arange(mean.size) * 10
        gens[-1] = 300
        ax.plot(gens, mean, color=color, lw=2, label=label)
        ax.fill_between(gens, mean - sd, mean + sd, color=color, alpha=0.18, lw=0)
    ax.set_title(NAMES[city], fontsize=9, color=INK)
    ax.set_xlabel("Generation")
    ax.set_xlim(0, 300)
axes[0].set_ylabel("Hypervolume")
axes[0].legend(loc="lower right", fontsize=7)
fig.tight_layout()
save(fig, "convergence")


# 2. Fronts: containers vs unserved, colour = inequity (median-HV regional run) -
def median_run(city, variant="regional"):
    hv = analysis[city][variant]["hv"]
    files = sorted(glob.glob(os.path.join(RESULTS, f"{city}_{variant}_*.npz")))
    i = int(np.argsort(hv)[len(hv) // 2])
    return np.load(files[i], allow_pickle=True)


fig, axes = plt.subplots(1, 5, figsize=(10, 2.4))
vmax = max(max(np.array(analysis[c]["current"])[2] for c in CITIES), 0.12) * 100
for ax, city in zip(axes, CITIES, strict=True):
    run = median_run(city)
    F = run["front"]
    cur = analysis[city]["current"]
    sc = ax.scatter(
        F[:, 0],
        F[:, 1] / 1000,
        c=F[:, 2] * 100,
        cmap=BLUES,
        vmin=0,
        vmax=vmax,
        s=14,
        edgecolors="white",
        linewidths=0.6,
        zorder=3,
    )
    ax.scatter(
        [cur[0]],
        [cur[1] / 1000],
        c=[cur[2] * 100],
        cmap=BLUES,
        vmin=0,
        vmax=vmax,
        marker="D",
        s=36,
        edgecolors=INK,
        linewidths=1,
        zorder=4,
    )
    ax.annotate(
        "current",
        (cur[0], cur[1] / 1000),
        xytext=(6, 6),
        textcoords="offset points",
        fontsize=7,
        color=INK2,
    )
    ax.set_title(NAMES[city], fontsize=9, color=INK)
    ax.set_xlabel("Containers ($f_1$)")
axes[0].set_ylabel("Unserved people ($f_2$, thousands)")
cbar = fig.colorbar(sc, ax=axes, shrink=0.85, pad=0.01)
cbar.set_label("Spatial inequity ($f_3$, points)", color=INK2)
cbar.outline.set_visible(False)
save(fig, "fronts")


# 3. Map of the neighbourhood unserved share: current vs a front layout (Valencia)
def shares(problem, ev):
    nb = problem.neighbourhoods
    u = pixel_unserved(problem.people, ev.pixel_site, ev.loads, ev.capacities)
    s = (nb.weights @ nb.unserved_cells(u)) / nb.neighbourhood_people
    return nb, s


DIVERGING = LinearSegmentedColormap.from_list(
    "diverging", ["#184f95", "#3987e5", "#f0efec", "#e66767", "#a32a2a"]
)

for city in ("valencia", "donostia"):
    p = load(city)
    k0 = p.current_containers
    cur_ev = p.evaluate_current(1000)
    run = median_run(city)
    F, layouts = run["front"], run["layouts"]
    cur = analysis[city]["current"]
    ok = np.flatnonzero((F[:, 0] == k0) & (F[:, 1] <= cur[1]))
    pick = ok[np.argmin(F[ok, 2])] if ok.size else int(np.argmin(np.abs(F[:, 0] - k0)))
    new_ev = p.evaluate(np.asarray(layouts[pick], dtype=int), 1000)
    nb = p.neighbourhoods
    # Lower-left corner of each 500 m block (km)
    corner = np.zeros((nb.size, 2))
    corner[nb.pixel_cell] = np.floor(p.pixels_xy / 500) * 0.5
    fig, axes = plt.subplots(1, 2, figsize=(8, 3.9), sharex=True, sharey=True)
    panels = (
        (
            p.projection.to_xy(p.current_lonlat),
            cur_ev,
            f"Current layout\n{k0} containers · unserved {cur[1] / 1000:.0f}k · inequity "
            f"{cur[2] * 100:.1f} pts",
        ),
        (
            p.candidates_xy[np.asarray(layouts[pick], dtype=int)],
            new_ev,
            f"Front layout\n{int(F[pick, 0])} containers · unserved {F[pick, 1] / 1000:.0f}k · "
            f"inequity {F[pick, 2] * 100:.1f} pts",
        ),
    )
    for ax, (sites, ev, title) in zip(axes, panels, strict=True):
        _, share = shares(p, ev)
        mean = float(nb.cell_people @ share / nb.cell_people.sum())
        diff = (share - mean) * 100
        for (x, y), d in zip(corner, diff, strict=True):
            ax.add_patch(
                plt.Rectangle(
                    (x, y),
                    0.5,
                    0.5,
                    lw=0.3,
                    ec="white",
                    fc=DIVERGING((np.clip(d, -25, 25) + 25) / 50),
                )
            )
        ax.scatter(sites[:, 0] / 1000, sites[:, 1] / 1000, s=1.2, c=INK, lw=0, zorder=3)
        ax.set_title(title, fontsize=7, color=INK)
        ax.set_aspect("equal")
        ax.autoscale_view()
        ax.grid(False)
        ax.set_xticks([])
        ax.set_yticks([])
        for side in ("left", "bottom"):
            ax.spines[side].set_visible(False)
    sm = plt.cm.ScalarMappable(cmap=DIVERGING, norm=plt.Normalize(-25, 25))
    cbar = fig.colorbar(sm, ax=axes, shrink=0.75, pad=0.01)
    cbar.set_label("Unserved share of the neighbourhood\nminus the city mean (points)", color=INK2)
    cbar.outline.set_visible(False)
    save(fig, f"map_{city}")
print("figures in", OUT)
