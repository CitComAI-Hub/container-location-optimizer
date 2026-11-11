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


# Main configuration (the one the service uses) and the 3-objective counterpart
MAIN = os.environ.get("MAIN_VARIANT", "nsga2-4_regional")
BASE3 = MAIN.replace("-4_", "-3_")
NSGA2, NSGA3 = RX, UX  # colour = algorithm, line style = crossover


# 1. Hypervolume convergence: rows = 3 / 4 objectives, one panel per city --------
fig, axes = plt.subplots(2, 5, figsize=(10, 4.2))
for row, n_obj in enumerate((3, 4)):
    for ax, city in zip(axes[row], CITIES, strict=True):
        variants = analysis[city]["variants"]
        for algorithm, color in (("nsga2", NSGA2), ("nsga3", NSGA3)):
            for crossover, style in (("regional", "-"), ("uniform", "--")):
                v = variants.get(f"{algorithm}-{n_obj}_{crossover}")
                if v is None:
                    continue
                mean = np.array(v["convergence_mean"])
                sd = np.array(v["convergence_sd"])
                gens = np.arange(mean.size) * 10
                gens[-1] = 300
                label = f"{algorithm.upper().replace('NSGA', 'NSGA-')}, {crossover}"
                ax.plot(gens, mean, color=color, ls=style, lw=1.6, label=label)
                ax.fill_between(gens, mean - sd, mean + sd, color=color, alpha=0.12, lw=0)
        if row == 0:
            ax.set_title(NAMES[city], fontsize=9, color=INK)
        if row == 1:
            ax.set_xlabel("Generation")
        ax.set_xlim(0, 300)
    axes[row][0].set_ylabel(f"HV, {n_obj} objectives")
axes[0][0].legend(loc="lower right", fontsize=6)
fig.tight_layout()
save(fig, "convergence")


def median_run(city, variant=MAIN):
    hv = analysis[city]["variants"][variant]["hv"]
    files = sorted(glob.glob(os.path.join(RESULTS, f"{city}_{variant}_*.npz")))
    i = int(np.argsort(hv)[len(hv) // 2])
    return np.load(files[i], allow_pickle=True)


# 2. Today's number of containers: inequity vs mean distance ------------------
def k0_layouts(city, variant):
    """Layouts of all runs with today's size and no more unserved people than today."""
    cur = analysis[city]["current"]
    rows = []
    for f in sorted(glob.glob(os.path.join(RESULTS, f"{city}_{variant}_*.npz"))):
        F = np.load(f, allow_pickle=True)["front"]
        rows.append(F[(F[:, 0] == cur[0]) & (F[:, 1] <= cur[1])])
    return np.vstack(rows)


def pareto_2d(points):
    """Non-dominated points (minimising both columns), sorted by the first."""
    points = points[np.lexsort((points[:, 1], points[:, 0]))]
    keep, best = [], np.inf
    for x, y in points:
        if y < best:
            keep.append((x, y))
            best = y
    return np.array(keep)


fig, axes = plt.subplots(1, 5, figsize=(10, 2.7))
for ax, city in zip(axes, CITIES, strict=True):
    a = analysis[city]
    cur = a["current"]
    for variant, color, label in ((BASE3, UX, "3 objectives"), (MAIN, RX, "4 objectives")):
        F = k0_layouts(city, variant)
        xy = np.column_stack((F[:, 3], F[:, 2] * 100))
        ax.scatter(xy[:, 0], xy[:, 1], s=4, c=color, alpha=0.25, lw=0, zorder=2)
        nd = pareto_2d(xy)
        ax.plot(
            nd[:, 0],
            nd[:, 1],
            color=color,
            lw=1.6,
            marker="o",
            ms=3.5,
            zorder=3,
            label=f"{label} (30 runs, non-dominated)",
        )
    ax.scatter([cur[3]], [cur[2] * 100], marker="D", s=30, c=INK, zorder=4, label="Current")
    if "single" in a:
        s = a["single"]
        ax.scatter(
            [s["mean_distance"]],
            [s["inequity"] * 100],
            marker="s",
            s=30,
            facecolors="white",
            edgecolors=INK,
            linewidths=1.2,
            zorder=4,
            label="Single-objective",
        )
    ax.set_title(f"{NAMES[city]} ($k_0={int(cur[0])}$)", fontsize=9, color=INK)
    ax.set_xlabel("Mean distance (m)")
axes[0].set_ylabel("Spatial inequity (points)")
handles, labels = axes[0].get_legend_handles_labels()
fig.legend(handles, labels, loc="lower center", ncol=4, fontsize=7, bbox_to_anchor=(0.5, -0.06))
fig.tight_layout(rect=(0, 0.06, 1, 1))
save(fig, "tradeoff_k0")


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
    cur = analysis[city]["current"]
    # the run whose fairest layout with today's size (and no more unserved people)
    # has the median inequity, and that layout
    candidates = []
    for f in sorted(glob.glob(os.path.join(RESULTS, f"{city}_{MAIN}_*.npz"))):
        run = np.load(f, allow_pickle=True)
        F = run["front"]
        ok = np.flatnonzero((F[:, 0] == k0) & (F[:, 1] <= cur[1]))
        if ok.size:
            candidates.append((F[ok, 2].min(), f))
    candidates.sort()
    run = np.load(candidates[len(candidates) // 2][1], allow_pickle=True)
    F, layouts = run["front"], run["layouts"]
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
