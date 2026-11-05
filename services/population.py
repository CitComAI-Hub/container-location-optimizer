"""Where people live in the region: one point per populated raster pixel.

Sources (``POPULATION``):

- ``ghs`` (default): the GHS-POP grid of the European Commission's JRC
  (R2023A, 3 arc-seconds, ~100 m, global, CC BY 4.0). Only the window of the
  region is read from the remote tiles, so it works for any city with no
  download step.
- A path or http(s) URL of any GeoTIFF of people per pixel (WorldPop, a
  national census grid...), in any CRS.

The result is cached in ``CACHE_DIR``: the remote read happens once.
"""

import hashlib
import logging
import math
import os
from dataclasses import dataclass

import numpy as np
import rasterio
import shapely
from rasterio.warp import transform as warp_transform
from rasterio.warp import transform_bounds
from rasterio.windows import Window, from_bounds

logger = logging.getLogger(__name__)

GHS_BASE = "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_POP_GLOBE_R2023A"
GHS_EPOCHS = tuple(range(1975, 2031, 5))
# Grid of the 4326 tiles: 10 x 10 degrees, row 1 / column 1 at the north-west
GHS_TILE_SIZE = 10.0
GHS_ORIGIN_LON = -180.00791664
GHS_ORIGIN_LAT = 89.09958334

GDAL_REMOTE = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".zip,.tif,.tiff",
    "GDAL_HTTP_MAX_RETRY": "3",
    "GDAL_HTTP_RETRY_DELAY": "2",
}


@dataclass(frozen=True)
class Population:
    """Populated pixels inside the region: centres (lon, lat) and people."""

    lonlat: np.ndarray
    people: np.ndarray
    source: str

    @property
    def total(self) -> float:
        return float(self.people.sum())


def ghs_tiles(bounds: tuple[float, float, float, float]) -> list[tuple[int, int]]:
    """(row, column) of the GHS-POP 4326 tiles that cover a lon/lat bbox."""
    west, south, east, north = bounds
    first_col = math.floor((west - GHS_ORIGIN_LON) / GHS_TILE_SIZE) + 1
    last_col = math.floor((east - GHS_ORIGIN_LON) / GHS_TILE_SIZE) + 1
    first_row = math.floor((GHS_ORIGIN_LAT - north) / GHS_TILE_SIZE) + 1
    last_row = math.floor((GHS_ORIGIN_LAT - south) / GHS_TILE_SIZE) + 1
    return [
        (row, col)
        for row in range(first_row, last_row + 1)
        for col in range(first_col, last_col + 1)
    ]


def ghs_tile_path(row: int, col: int, epoch: int) -> str:
    """GDAL path of a tile inside its remote zip."""
    if epoch not in GHS_EPOCHS:
        raise ValueError(f"GHS_EPOCH must be one of {GHS_EPOCHS}")
    dataset = f"GHS_POP_E{epoch}_GLOBE_R2023A_4326_3ss"
    name = f"{dataset}_V1_0_R{row}_C{col}"
    return f"/vsizip//vsicurl/{GHS_BASE}/{dataset}/V1-0/tiles/{name}.zip/{name}.tif"


def _raster_path(source: str) -> str:
    if source.startswith(("http://", "https://")):
        return f"/vsicurl/{source}"
    return source


def _read_window(path: str, region: shapely.Geometry) -> tuple[np.ndarray, np.ndarray]:
    """Pixel centres (lon, lat) and values of a raster inside the region."""
    with rasterio.open(path) as raster:
        crs = raster.crs
        # A raster without CRS is taken as lon/lat
        reproject = crs is not None and crs.to_epsg() != 4326
        bounds = region.bounds
        if reproject:
            bounds = transform_bounds("EPSG:4326", crs, *bounds)
        window = from_bounds(*bounds, transform=raster.transform)
        col, row = math.floor(window.col_off), math.floor(window.row_off)
        window = Window(
            col,
            row,
            math.ceil(window.col_off + window.width) - col,
            math.ceil(window.row_off + window.height) - row,
        ).intersection(Window(0, 0, raster.width, raster.height))
        values = raster.read(1, window=window, masked=True)
        transform = raster.window_transform(window)

    values = np.ma.filled(values.astype("float64"), 0.0)
    rows, cols = np.nonzero(values > 0)
    if rows.size == 0:
        return np.empty((0, 2)), np.empty(0)
    xs, ys = rasterio.transform.xy(transform, rows, cols, offset="center")
    xs, ys = np.asarray(xs, dtype=float), np.asarray(ys, dtype=float)
    if reproject:
        xs, ys = (np.asarray(v) for v in warp_transform(crs, "EPSG:4326", xs, ys))
    lonlat = np.column_stack((xs, ys))
    people = values[rows, cols]

    inside = shapely.contains_xy(region, lonlat[:, 0], lonlat[:, 1])
    return lonlat[inside], people[inside]


def _cache_file(cache_dir: str, source: str, epoch: int, region: shapely.Geometry) -> str:
    key = hashlib.sha256(f"{source}|{epoch}|".encode() + shapely.to_wkb(region)).hexdigest()
    return os.path.join(cache_dir, f"population-{key[:16]}.npz")


def load_population(
    source: str, region: shapely.Geometry, cache_dir: str | None = None, epoch: int = 2025
) -> Population:
    cache = _cache_file(cache_dir, source, epoch, region) if cache_dir else None
    if cache and os.path.exists(cache):
        data = np.load(cache)
        logger.info("Population from cache %s", cache)
        return Population(data["lonlat"], data["people"], str(data["source"]))

    if source == "ghs":
        paths = [ghs_tile_path(row, col, epoch) for row, col in ghs_tiles(region.bounds)]
        label = f"GHS-POP R2023A, epoch {epoch} (JRC, CC BY 4.0)"
    else:
        paths = [_raster_path(source)]
        label = source

    parts = []
    with rasterio.Env(**GDAL_REMOTE):
        for path in paths:
            logger.info("Reading population from %s", path)
            parts.append(_read_window(path, region))
    lonlat = np.concatenate([p[0] for p in parts]) if parts else np.empty((0, 2))
    people = np.concatenate([p[1] for p in parts]) if parts else np.empty(0)
    if people.size == 0:
        raise ValueError(f"No population inside the region in {label}")

    population = Population(lonlat, people, label)
    if cache:
        os.makedirs(cache_dir, exist_ok=True)
        tmp = f"{cache}.tmp.npz"
        np.savez_compressed(tmp, lonlat=lonlat, people=people, source=label)
        os.replace(tmp, cache)
    logger.info("Population: %d pixels, %.0f people", people.size, population.total)
    return population
