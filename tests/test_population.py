import numpy as np
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box

from services.population import ghs_tile_path, ghs_tiles, load_population


def test_ghs_tiles_of_valencia():
    # Valencia is in row 5, column 18 (checked against the JRC tile bounds)
    assert ghs_tiles((-0.42, 39.41, -0.28, 39.50)) == [(5, 18)]


def test_ghs_tiles_of_a_region_across_a_tile_border():
    assert ghs_tiles((-0.1, 39.4, 0.1, 39.5)) == [(5, 18), (5, 19)]


def test_ghs_tile_path():
    path = ghs_tile_path(5, 18, 2025)
    assert path.startswith("/vsizip//vsicurl/https://jeodpp.jrc.ec.europa.eu/")
    assert path.endswith("GHS_POP_E2025_GLOBE_R2023A_4326_3ss_V1_0_R5_C18.tif")


def _raster(path, crs, transform, data):
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=data.shape[1],
        height=data.shape[0],
        count=1,
        dtype="float32",
        crs=crs,
        transform=transform,
        nodata=-200,
    ) as dst:
        dst.write(data.astype("float32"), 1)


def test_load_population_from_a_local_raster_with_cache(tmp_path):
    data = np.full((10, 10), 5.0)
    data[0, 0] = -200  # nodata
    raster = tmp_path / "pop.tif"
    _raster(raster, "EPSG:4326", from_origin(0, 10, 1, 1), data)
    region = box(0, 0, 5, 10)  # left half

    population = load_population(str(raster), region, str(tmp_path / "cache"))
    assert population.people.size == 49  # 50 pixels minus the nodata one
    assert population.total == 245
    assert (population.lonlat[:, 0] < 5).all()

    raster.unlink()  # the second load comes from the cache
    again = load_population(str(raster), region, str(tmp_path / "cache"))
    assert again.total == population.total


def test_load_population_from_a_projected_raster(tmp_path):
    raster = tmp_path / "pop.tif"
    # 1 km pixels in ETRS89 / UTM 30N, around Valencia
    _raster(raster, "EPSG:25830", from_origin(720000, 4375000, 1000, 1000), np.ones((10, 10)))
    region = box(-0.45, 39.40, -0.30, 39.48)
    population = load_population(str(raster), region)
    assert population.people.size > 0
    assert (population.lonlat[:, 0] > -0.45).all() and (population.lonlat[:, 1] < 39.48).all()
