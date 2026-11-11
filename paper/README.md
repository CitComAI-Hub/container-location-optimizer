# Paper: Multi-Objective Optimization for UCO Container Placement

Draft for a journal (Wiley NJD template, `\documentclass[AMA,Times1COL]{WileyNJDv5}`), rewritten in November 2026
from the 2025 draft (see [RESEARCH.md](../RESEARCH.md) for what changed and why). **Not compiled yet**: compile it in
Overleaf (pdfLaTeX + BibTeX) and review it.

| File | Section |
|---|---|
| `main.tex` | Title, authors, abstract, includes |
| `introduction.tex`, `literature.tex` | Introduction, literature review |
| `problem_definition.tex` | Objectives `f1`–`f4`, the equity measure, why not Moran's I, relation to classical measures |
| `ga.tex` | The algorithm (NSGA-II/III, mutation, optional crossovers, the old boundary crossover) |
| `experiments.tex` | Data, setup and the five studies |
| `conclusions.tex` | Conclusions and limitations |
| `references.bib` | Bibliography |
| `figures/` | Generated: `*.pdf` by `experiments/figures.py`, `table_*.tex` by `experiments/tables.py` |

Regenerate the tables from the summary data in the repository (no runs needed), and copy them here:

```console
cd experiments
RESULTS_DIR=summary REVISION_DIR=summary python tables.py && cp figures/table_*.tex ../paper/figures/
```

The figures need the raw runs (see `experiments/README.md`): `RESULTS_DIR=<results_all> REVISION_DIR=<results_rev>
python figures.py`, then copy `convergence.pdf`, `tradeoff_k0.pdf` and `map_donostia.pdf`.

The template's `Fonts/` folder (13 MB) is not included: it is only needed for its STIX and Lato options, not for
`Times1COL`. Nor are the author guidelines and the template's sample files.

The paper extends the single-objective method of Moreno et al. (IDEAL 2024), `moreno2024optimizing` in
`references.bib`.
