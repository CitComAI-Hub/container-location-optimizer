"""Statistics shared by the analyses: effect size, tests, Holm correction."""

import numpy as np
from scipy import stats


def a12(x, y):
    """Vargha-Delaney A: probability that a run of x beats a run of y (higher is better)."""
    x, y = np.asarray(x), np.asarray(y)
    wins = (x[:, None] > y[None, :]).sum() + 0.5 * (x[:, None] == y[None, :]).sum()
    return float(wins / (x.size * y.size))


def compare(x, y):
    return {"p": float(stats.mannwhitneyu(x, y, alternative="two-sided").pvalue), "a12": a12(x, y)}


def holm(pvalues):
    """Holm-Bonferroni adjusted p-values."""
    p = np.asarray(pvalues, dtype=float)
    order = np.argsort(p)
    adjusted = np.maximum.accumulate((p.size - np.arange(p.size)) * p[order])
    out = np.empty_like(p)
    out[order] = np.minimum(adjusted, 1.0)
    return out


def summary(values):
    v = np.asarray(values, dtype=float)
    return {
        "mean": float(v.mean()),
        "sd": float(v.std(ddof=1)),
        "median": float(np.median(v)),
        "iqr": float(np.subtract(*np.percentile(v, [75, 25]))),
    }
