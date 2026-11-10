"""Spatial equity of a layout: are the people left unserved concentrated in
some neighbourhoods?

When capacity is short, some people are always unserved (their container is
full). It is fairer if every neighbourhood carries a similar share than if a
few neighbourhoods carry most of it. That share is measured on a **fixed**
support, so layouts with different numbers of containers are comparable:

- the region is divided into square cells (``cell`` metres, 500 by default)
  that hold the populated pixels,
- the *neighbourhood* of a cell is every cell within ``radius`` metres (1 km),
- the unserved share of a neighbourhood is its unserved people over its
  people, where a pixel's unserved people are its people times the share of
  its container's load above capacity.

**Spatial inequity** is the population-weighted standard deviation of that
share between neighbourhoods. It is 0 when every neighbourhood has the same
share (all served, or all short in the same proportion) and grows when the
shortage is both unequal and spatially clustered: a dispersed pattern averages
out within neighbourhoods. It is the magnitude-aware counterpart of Moran's I
(the spatial autocovariance of the share, not its correlation), which is why it
does not degenerate on tiny layouts or when the share is nearly uniform.

Moran's I of the cell shares, with the same weights, is also given as a
diagnostic.
"""

from dataclasses import dataclass

import numpy as np
from scipy import sparse
from scipy.spatial import cKDTree


@dataclass
class Neighbourhoods:
    pixel_cell: np.ndarray  # cell of each pixel
    cell_people: np.ndarray
    weights: sparse.csr_matrix  # cell x cell, 1 within the radius (diagonal included)
    neighbourhood_people: np.ndarray  # people within the radius of each cell

    @classmethod
    def build(
        cls, pixels_xy: np.ndarray, people: np.ndarray, cell: float = 500.0, radius: float = 1000.0
    ) -> "Neighbourhoods":
        keys = np.floor(pixels_xy / cell).astype(np.int64)
        _, pixel_cell = np.unique(keys, axis=0, return_inverse=True)
        pixel_cell = pixel_cell.ravel()
        n = int(pixel_cell.max()) + 1 if pixel_cell.size else 0
        cell_people = np.bincount(pixel_cell, weights=people, minlength=n)
        # Population-weighted centre of each cell
        centres = (
            np.column_stack(
                [
                    np.bincount(pixel_cell, weights=people * pixels_xy[:, i], minlength=n)
                    for i in (0, 1)
                ]
            )
            / np.maximum(cell_people, 1e-9)[:, None]
        )
        pairs = cKDTree(centres).query_pairs(radius, output_type="ndarray")
        rows = np.concatenate((pairs[:, 0], pairs[:, 1], np.arange(n)))
        cols = np.concatenate((pairs[:, 1], pairs[:, 0], np.arange(n)))
        weights = sparse.csr_matrix((np.ones(rows.size), (rows, cols)), shape=(n, n))
        return cls(pixel_cell, cell_people, weights, weights @ cell_people)

    @property
    def size(self) -> int:
        return self.cell_people.size

    def unserved_cells(self, pixel_unserved: np.ndarray) -> np.ndarray:
        return np.bincount(self.pixel_cell, weights=pixel_unserved, minlength=self.size)

    def inequity(self, pixel_unserved: np.ndarray) -> float:
        """Population-weighted s.d. of the unserved share between neighbourhoods (0-1)."""
        share = (self.weights @ self.unserved_cells(pixel_unserved)) / self.neighbourhood_people
        w = self.cell_people
        mean = float(w @ share / w.sum())
        return float(np.sqrt(w @ (share - mean) ** 2 / w.sum()))

    def morans_i(self, pixel_unserved: np.ndarray) -> float | None:
        """Moran's I of the unserved share of the cells (same neighbours, without
        the cell itself, row-standardised). None if the share is uniform."""
        share = self.unserved_cells(pixel_unserved) / self.cell_people
        z = share - share.mean()
        if not np.any(np.abs(z) > 1e-12):
            return None
        w = self.weights - sparse.diags(self.weights.diagonal())
        sums = np.asarray(w.sum(axis=1)).ravel()
        keep = sums > 0
        lag = (w @ z)[keep] / sums[keep]
        return float(z[keep] @ lag / (z @ z) * z.size / keep.sum())


def pixel_unserved(people: np.ndarray, pixel_site: np.ndarray, loads, capacities) -> np.ndarray:
    """Unserved people of each pixel: its people times the share of its
    container's load above capacity."""
    with np.errstate(divide="ignore", invalid="ignore"):
        short = np.where(loads > capacities, 1 - capacities / loads, 0.0)
    return people * short[pixel_site]
