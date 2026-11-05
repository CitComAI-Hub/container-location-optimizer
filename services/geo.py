"""Region of study and a local metric projection.

Distances and Voronoi cells are computed in metres with an equirectangular
projection centred on the region: at city scale its error is far below the
size of a population pixel.
"""

import json
import math
from dataclasses import dataclass

import numpy as np
import requests
import shapely
from shapely.geometry import shape
from shapely.ops import unary_union

EARTH_RADIUS = 6371008.8


def load_region(source: str, timeout: float = 30) -> shapely.Geometry:
    """Union of the polygons of a GeoJSON (file path or http(s) URL).

    Accepts a FeatureCollection, a Feature or a bare geometry.
    """
    if source.startswith(("http://", "https://")):
        response = requests.get(source, timeout=timeout)
        response.raise_for_status()
        data = response.json()
    else:
        with open(source, encoding="utf-8") as file:
            data = json.load(file)

    if data.get("type") == "FeatureCollection":
        geometries = [shape(feature["geometry"]) for feature in data["features"]]
    elif data.get("type") == "Feature":
        geometries = [shape(data["geometry"])]
    else:
        geometries = [shape(data)]

    region = unary_union([g for g in geometries if g.geom_type in ("Polygon", "MultiPolygon")])
    if region.is_empty:
        raise ValueError(f"No polygon in the region {source}")
    return shapely.make_valid(region)


@dataclass(frozen=True)
class LocalProjection:
    lon0: float
    lat0: float

    @classmethod
    def for_geometry(cls, geometry: shapely.Geometry) -> "LocalProjection":
        centroid = geometry.centroid
        return cls(centroid.x, centroid.y)

    @property
    def _kx(self) -> float:
        return math.radians(1) * EARTH_RADIUS * math.cos(math.radians(self.lat0))

    @property
    def _ky(self) -> float:
        return math.radians(1) * EARTH_RADIUS

    def to_xy(self, lonlat: np.ndarray) -> np.ndarray:
        lonlat = np.asarray(lonlat, dtype=float).reshape(-1, 2)
        return np.column_stack(
            ((lonlat[:, 0] - self.lon0) * self._kx, (lonlat[:, 1] - self.lat0) * self._ky)
        )

    def to_lonlat(self, xy: np.ndarray) -> np.ndarray:
        xy = np.asarray(xy, dtype=float).reshape(-1, 2)
        return np.column_stack((xy[:, 0] / self._kx + self.lon0, xy[:, 1] / self._ky + self.lat0))

    def geometry_to_xy(self, geometry: shapely.Geometry) -> shapely.Geometry:
        return shapely.transform(geometry, self.to_xy)

    def geometry_to_lonlat(self, geometry: shapely.Geometry, decimals: int = 6) -> shapely.Geometry:
        return shapely.transform(geometry, lambda xy: np.round(self.to_lonlat(xy), decimals))
