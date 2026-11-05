import numpy as np
import pytest
from shapely.geometry import box

from services.data_source import Container
from services.population import Population
from services.problem import Problem

# A 2 x 2 km square around Valencia's centre
LON, LAT = -0.376, 39.47
DLON, DLAT = 0.0233, 0.018


@pytest.fixture
def region():
    return box(LON, LAT, LON + DLON, LAT + DLAT)


@pytest.fixture
def population():
    """People on a 20 x 20 grid, all in the west half (so where they live matters)."""
    rng = np.random.default_rng(0)
    xs = LON + (np.arange(20) + 0.5) * DLON / 20
    ys = LAT + (np.arange(20) + 0.5) * DLAT / 20
    lon, lat = np.meshgrid(xs, ys)
    people = np.where(lon < LON + DLON / 2, 100.0, 0.0) + rng.random(lon.shape)
    return Population(np.column_stack((lon.ravel(), lat.ravel())), people.ravel(), "test")


@pytest.fixture
def containers():
    """5 target containers in the empty east half, 100 candidate sites everywhere."""
    rng = np.random.default_rng(1)
    result = [
        Container(f"oil-{i}", LON + DLON * (0.7 + 0.05 * i), LAT + DLAT * 0.5, True)
        for i in range(5)
    ]
    for i in range(100):
        result.append(
            Container(f"c-{i}", LON + DLON * rng.random(), LAT + DLAT * rng.random(), False)
        )
    return result


@pytest.fixture
def problem(region, containers, population):
    return Problem(region, containers, population, candidate_spacing=20)
